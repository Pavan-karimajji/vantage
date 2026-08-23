# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 system test: `ST-D6-2` (`sim_implementation_plan.md`) -- a pipeline
with a real, applied override (`S-C1cΔ`, `R-SIM-15`) resims reproducibly:
two fresh, independent runs against the same recording produce
byte-identical outputs and identical run manifests. `Pipeline.exec`'s own
determinism is exercised elsewhere (`test_st_c2_2_resim_reproduces_byte_
identical_outputs_across_two_runs`, no override involved); this is the same
claim with an override actually on the input path, so a per-run mutable
state leak in `_apply_input_overrides`/`_override_first_seen` (`hold`'s own
cross-tick memory) would show up as a divergence here and nowhere else.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from google.protobuf import descriptor_pb2 as _dpb
from google.protobuf import descriptor_pool as _dpool
from google.protobuf import message_factory as _mfactory

from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.graph.build import Pipeline
from adas_sim.config.scenario import (
    EgoScenario, RoadHint, RunControl, Scenario, ScenarioContent, SensorModelRef, SutRef,
)
from adas_sim.runspec.manifest import build_manifest
from adas_sim.sources.recorder import Recorder
from adas_sim.sources.synthetic import SyntheticSource

from tests.support.resim_for_tests import resim_pipeline


def _scalar_message_cls():
    """A real `Scalar { x: float }` schema -- `apply_override`'s `const`
    verb decodes and re-encodes a real field, so a bare-bytes stand-in
    port cannot exercise it (same reasoning `test_c1c_pipeline.py`'s own
    helper of this name gives)."""
    fdp = _dpb.FileDescriptorProto()
    fdp.name = "d6_override_determinism_scalar.proto"
    fdp.package = "adas_sim.test.d6overridedeterminism"
    fdp.syntax = "proto3"
    msg = fdp.message_type.add()
    msg.name = "Scalar"
    f = msg.field.add()
    f.name, f.number, f.type = "x", 1, _dpb.FieldDescriptorProto.TYPE_FLOAT
    f.label = _dpb.FieldDescriptorProto.LABEL_OPTIONAL

    fds = _dpb.FileDescriptorSet()
    fds.file.append(fdp)

    pool = _dpool.DescriptorPool()
    pool.Add(fdp)
    cls = _mfactory.GetMessageClass(pool.FindMessageTypeByName("adas_sim.test.d6overridedeterminism.Scalar"))
    return cls, fds.SerializeToString()


def _scenario() -> Scenario:
    return Scenario(
        schema=2, id="d6_override_determinism", doc="",
        scenario=ScenarioContent(road=RoadHint(), ego=EgoScenario(speed_mps=0.0), actors=()),
        sensor_model=SensorModelRef(), run=RunControl(), sut=SutRef(),
    )


def _record_source_only(tmp_path: Path, scalar_cls) -> Path:
    """`pipeline=None` (`R-SIM-12`: "`sim record` produces and executes
    nothing") -- the recording carries only `source.veh_dyn`, which is all
    an overridden `simulate` stage needs to resim against."""
    recording_path = tmp_path / "recording.mcap"
    source = SyntheticSource([{"veh_dyn": scalar_cls(x=float(i)).SerializeToString()} for i in range(5)])
    meta = build_manifest(run_kind="sim", source_kind="synthetic")
    recorder = Recorder(None, source, recording_path, meta=meta)
    recorder.open(_scenario())
    for _ in range(5):
        recorder.tick(50_000_000)
    recorder.close()
    return recording_path


def _resim_pipeline(pipeline_path: Path, scalar_cls, descriptor_set: bytes, seen: list[float]) -> Pipeline:
    stages = [
        {
            "name": "under_test", "mode": "simulate", "impl": "stub:under_test",
            "inputs": {"egoDyn": "source.veh_dyn"},
            "overrides": {"egoDyn.x": {"verb": "const", "value": 42.0}},
        },
    ]
    pipeline_path.write_text(yaml.safe_dump({"name": "d6_override_determinism", "stages": stages}, sort_keys=False), encoding="utf-8")
    manifest = ComponentManifest(
        component="under_test", version="1", abi_version=1, build_id="test",
        inputs=(PortSpec(name="egoDyn", proto_type="adas_sim.test.d6overridedeterminism.Scalar"),),
        outputs=(PortSpec(name="verdict", proto_type="adas_sim.test.d6overridedeterminism.Scalar"),),
        project="base", config_bundle_sha256="", descriptor_set=descriptor_set, period_ns=0,
    )

    def _algorithm(dt_ns, inputs):
        del dt_ns
        received = scalar_cls()
        received.ParseFromString(inputs["egoDyn"])
        seen.append(received.x)
        return {"verdict": inputs["egoDyn"]}  # echoes the (overridden) input straight back

    component = InProcessSilComponent("under_test", manifest, _algorithm)
    component.init()
    return Pipeline.load(pipeline_path, components={"under_test": component})


def test_st_d6_2_a_pipeline_with_an_override_resims_reproducibly(tmp_path):
    scalar_cls, descriptor_set = _scalar_message_cls()
    recording_path = _record_source_only(tmp_path, scalar_cls)

    pipeline_path = tmp_path / "resim_pipeline.yaml"

    first_seen: list[float] = []
    first_pipeline = _resim_pipeline(pipeline_path, scalar_cls, descriptor_set, first_seen)
    first_outputs = resim_pipeline(first_pipeline, recording_path)

    second_seen: list[float] = []
    second_pipeline = _resim_pipeline(pipeline_path, scalar_cls, descriptor_set, second_seen)  # fresh instances, no shared state
    second_outputs = resim_pipeline(second_pipeline, recording_path)

    # The override actually applied -- every tick saw 42.0, never the
    # original stimulus (0.0, 1.0, 2.0, 3.0, 4.0). Proves this test would
    # fail if the override silently stopped applying, not just that two
    # (possibly unoverridden) runs happen to agree.
    assert first_seen == [42.0] * 5
    assert second_seen == [42.0] * 5

    # Byte-identical outputs across two fresh, independent runs (port
    # values, per sim_resim_and_recording.md's own clarification -- same
    # comparison ST-C2-2 makes).
    assert first_outputs == second_outputs

    # Identical run manifests: same explicit clock removes the one field
    # (`created_utc`) that would otherwise legitimately differ between two
    # calls -- run_id's own hash (pipeline_sha, overrides_repr, ...) is
    # already clock-independent (`core/ids.py::new_run_id`).
    from datetime import datetime, timezone
    clock = datetime(2026, 8, 5, tzinfo=timezone.utc)
    first_manifest = build_manifest(
        pipeline=first_pipeline, pipeline_path=pipeline_path, run_kind="resim", source_kind="synthetic",
        recording_path=recording_path, clock=clock,
    )
    second_manifest = build_manifest(
        pipeline=second_pipeline, pipeline_path=pipeline_path, run_kind="resim", source_kind="synthetic",
        recording_path=recording_path, clock=clock,
    )
    assert first_manifest == second_manifest
