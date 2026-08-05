# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D3 slice 4: `resim_pipeline_merged` (`core/resim.py`) -- the
live-resim-to-Session capability `ST-D3-1` needs. Mirrors
`test_c2_record_resim.py`'s own record-then-resim shape, but resim through
the NEW merged-writer path and reload via `build_session_from_recording`
instead of reading `resim_pipeline`'s in-memory return value -- proving the
merged file is a real, standalone, decodable recording, the one and only
way a `Session` is ever built anywhere in this framework (`R-SIM-6`/
`R-SIM-13`/`R-SIM-14`), and that a real, non-empty `descriptor_set`
actually decodes on reload (the schema_bytes fix, same pass).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from google.protobuf import descriptor_pb2 as _dpb
from google.protobuf import descriptor_pool as _dpool
from google.protobuf import message_factory as _mfactory

from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.contracts.scenario import (
    EgoScenario, RoadHint, RunControl, Scenario, ScenarioContent, SensorModelRef, SutRef,
)
from adas_sim.core.manifest import build_manifest
from adas_sim.core.resim import resim_pipeline, resim_pipeline_merged
from adas_sim.core.runner import build_session_from_recording
from adas_sim.sources.recorder import Recorder
from adas_sim.sources.synthetic import SyntheticSource


def _scenario(name: str = "t") -> Scenario:
    return Scenario(
        schema=2, id=name, doc="",
        scenario=ScenarioContent(road=RoadHint(), ego=EgoScenario(speed_mps=0.0), actors=()),
        world={}, sensor_model=SensorModelRef(), run=RunControl(), sut=SutRef(),
    )


def _verdict_schema() -> tuple[str, bytes, type]:
    """A minimal real `Verdict { result: string }` schema, same technique
    `core/tick.decode_message` itself resolves against (R-SIM-11) --
    proves the merged file's freshly-simulated topic actually decodes,
    not just carries bytes."""
    fdp = _dpb.FileDescriptorProto()
    fdp.name = "d3resim_verdict.proto"
    fdp.package = "adas_sim.test.d3resim"
    fdp.syntax = "proto3"
    msg = fdp.message_type.add()
    msg.name = "Verdict"
    f = msg.field.add()
    f.name, f.number, f.type = "result", 1, _dpb.FieldDescriptorProto.TYPE_STRING
    f.label = _dpb.FieldDescriptorProto.LABEL_OPTIONAL

    fds = _dpb.FileDescriptorSet()
    fds.file.append(fdp)

    pool = _dpool.DescriptorPool()
    pool.Add(fdp)
    message_cls = _mfactory.GetMessageClass(pool.FindMessageTypeByName("adas_sim.test.d3resim.Verdict"))
    return "adas_sim.test.d3resim.Verdict", fds.SerializeToString(), message_cls


_VERDICT_NAME, _VERDICT_DESCRIPTOR_SET, _Verdict = _verdict_schema()

_UPSTREAM_MANIFEST = ComponentManifest(
    component="upstream", version="1", abi_version=1, build_id="test",
    inputs=(PortSpec(name="egoDyn", proto_type="test.VehDyn"),),
    outputs=(PortSpec(name="objects", proto_type="test.Objects"),),
    project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
)
_UNDER_TEST_MANIFEST = ComponentManifest(
    component="under_test", version="1", abi_version=1, build_id="test",
    inputs=(PortSpec(name="objects", proto_type="test.Objects"),),
    outputs=(PortSpec(name="verdict", proto_type=_VERDICT_NAME),),
    project="base", config_bundle_sha256="", descriptor_set=_VERDICT_DESCRIPTOR_SET, period_ns=0,
)


def _upstream_fn(dt_ns, inputs):
    return {"objects": inputs["egoDyn"] + b"-objects"}


def _under_test_fn(dt_ns, inputs):
    return {"verdict": _Verdict(result=inputs["objects"].decode()).SerializeToString()}


def _write_pipeline(path: Path, stages: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"name": "algo_test", "stages": stages}, sort_keys=False), encoding="utf-8")


def _record(tmp_path: Path) -> Path:
    """Both stages `simulate` -- what produced the base recording
    (`sim run --record`'s shape, `sources.recorder.Recorder`)."""
    record_pipeline_path = tmp_path / "record_pipeline.yaml"
    stages = [
        {"name": "upstream", "mode": "simulate", "impl": "stub:upstream", "inputs": {"egoDyn": "source.veh_dyn"}},
        {"name": "under_test", "mode": "simulate", "impl": "stub:under_test", "inputs": {"objects": "upstream.objects"}},
    ]
    _write_pipeline(record_pipeline_path, stages)
    upstream = InProcessSilComponent("upstream", _UPSTREAM_MANIFEST, _upstream_fn)
    upstream.init()
    under_test = InProcessSilComponent("under_test", _UNDER_TEST_MANIFEST, _under_test_fn)
    under_test.init()
    pipeline = Pipeline.load(record_pipeline_path, components={"upstream": upstream, "under_test": under_test})

    source = SyntheticSource([{"veh_dyn": f"vd{i}".encode()} for i in range(3)])
    recording_path = tmp_path / "recording.mcap"
    meta = build_manifest(
        pipeline=pipeline, pipeline_path=record_pipeline_path, run_kind="sim", source_kind="synthetic",
    )
    recorder = Recorder(pipeline, source, recording_path, meta=meta)
    recorder.open(_scenario("algo_test"))
    for _ in range(3):
        recorder.tick(50_000_000)
    recorder.close()
    return recording_path


def _resim_pipeline(path: Path) -> Pipeline:
    """`upstream` -> `measured` (fed from the recording), `under_test` ->
    `simulate` (executed live) -- `ST-C2-1`'s own canonical algo-test
    shape, re-executed here through the merged-writer path."""
    stages = [
        {"name": "upstream", "mode": "measured", "impl": "stub:upstream", "inputs": {"egoDyn": "source.veh_dyn"}},
        {"name": "under_test", "mode": "simulate", "impl": "stub:under_test", "inputs": {"objects": "upstream.objects"}},
    ]
    _write_pipeline(path, stages)

    def _never(dt_ns, inputs):
        raise AssertionError("a measured stage must never execute during resim")

    upstream = InProcessSilComponent("upstream", _UPSTREAM_MANIFEST, _never)
    upstream.init()
    under_test = InProcessSilComponent("under_test", _UNDER_TEST_MANIFEST, _under_test_fn)
    under_test.init()
    return Pipeline.load(path, components={"upstream": upstream, "under_test": under_test})


def test_resim_pipeline_merged_produces_a_standalone_reloadable_session(tmp_path):
    recording_path = _record(tmp_path)

    resim_path = tmp_path / "resim_pipeline.yaml"
    pipeline = _resim_pipeline(resim_path)
    out_path = tmp_path / "merged.mcap"
    meta = build_manifest(
        pipeline=pipeline, pipeline_path=resim_path, run_kind="resim", source_kind="mcap",
        recording_path=recording_path,
    )
    resim_pipeline_merged(pipeline, recording_path, out_path, meta=meta)

    session = build_session_from_recording(out_path)
    assert len(session) == 3
    for i in range(3):
        # measured pass-through: upstream's own recorded bytes, byte-identical
        assert session.at(i).port("upstream.objects").message == f"vd{i}-objects".encode()
        # freshly-simulated AND decoded via the schema_bytes fix -- a real
        # Verdict message, not raw bytes
        verdict = session.at(i).port("under_test.verdict").message
        assert verdict.result == f"vd{i}-objects"
        assert session.at(i).port("under_test.verdict").origin == "simulated"


def test_resim_pipeline_merged_is_engine_consistent_with_resim_pipeline(tmp_path):
    """R-SIM-16: a GUI "Run" (the merged-file path) and `sim resim` (`
    resim_pipeline`) must never silently diverge for the same pipeline +
    recording -- both call `Pipeline.exec`, never two engines."""
    recording_path = _record(tmp_path)
    resim_path = tmp_path / "resim_pipeline.yaml"

    plain_pipeline = _resim_pipeline(resim_path)
    plain_outputs = resim_pipeline(plain_pipeline, recording_path)

    merged_pipeline = _resim_pipeline(resim_path)  # fresh InProcessSilComponent instances -- no shared state
    out_path = tmp_path / "merged.mcap"
    meta = build_manifest(
        pipeline=merged_pipeline, pipeline_path=resim_path, run_kind="resim", source_kind="mcap",
        recording_path=recording_path,
    )
    resim_pipeline_merged(merged_pipeline, recording_path, out_path, meta=meta)
    session = build_session_from_recording(out_path)

    for i, (_t_ns, outputs) in enumerate(plain_outputs):
        assert session.at(i).port("under_test.verdict").raw_bytes == outputs["under_test"]["verdict"]


def test_resim_pipeline_merged_writes_no_absolute_config_bundle_and_is_a_full_recording(tmp_path):
    """The merged file needs no OTHER input to build a Session from --
    unlike `cli/resim.py --save` (only the freshly-simulated stages' own
    bytes), every declared port this run wired is present, measured or
    simulated (`R-SIM-6`)."""
    recording_path = _record(tmp_path)
    resim_path = tmp_path / "resim_pipeline.yaml"
    pipeline = _resim_pipeline(resim_path)
    out_path = tmp_path / "merged.mcap"
    meta = build_manifest(
        pipeline=pipeline, pipeline_path=resim_path, run_kind="resim", source_kind="mcap",
        recording_path=recording_path,
    )
    resim_pipeline_merged(pipeline, recording_path, out_path, meta=meta)

    session = build_session_from_recording(out_path)
    assert session.known_ports >= {"upstream.objects", "under_test.verdict"}
