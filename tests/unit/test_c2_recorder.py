# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C2 slice 3: `sources/recorder.py` -- `UT-C2-5` (via `core/manifest.py`,
`test_c2_manifest.py`), `UT-C2-6`, `UT-C2-7`, `UT-C2-8`, `UT-C2-13`,
`ST-C2-3` (`sim_implementation_plan.md`). `UT-C2-9` (manifest-mismatch vs.
library-hash-mismatch severity) is a resim-time check, `S-C2` slice 4's
own tests."""

from __future__ import annotations

from pathlib import Path

import yaml

from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.manifest import build_manifest
from adas_sim.io.base import CAPTURE_TIME_MANIFEST_VERSION, Provenance, RunManifest
from adas_sim.io.mcap import McapReader
from adas_sim.sources.base import Scenario
from adas_sim.sources.recorder import REVISE_AFTER_TICKS, Recorder
from adas_sim.sources.synthetic import SyntheticSource


def _manifest(*, component: str, inputs=(), outputs=(), max_bytes: int = 0) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _under_test_component(fn) -> InProcessSilComponent:
    manifest = _manifest(
        component="under_test", inputs=[PortSpec(name="egoDyn", proto_type="test.VehDyn")],
        outputs=[PortSpec(name="verdict", proto_type="test.Verdict", max_bytes=64)],
    )
    component = InProcessSilComponent("under_test", manifest, fn)
    component.init()
    return component, manifest


def _pipeline(tmp_path: Path, *, record: dict | None = None, component=None) -> Pipeline:
    stage = {
        "name": "under_test", "mode": "simulate", "impl": "stub:under_test",
        "inputs": {"egoDyn": "source.veh_dyn"},
    }
    if record is not None:
        stage["record"] = record
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"name": "test", "stages": [stage]}, sort_keys=False), encoding="utf-8")
    if component is None:
        component, _ = _under_test_component(lambda dt_ns, inputs: {"verdict": b"ok"})
    return Pipeline.load(path, components={"under_test": component})


def _manifest_for(pipeline: Pipeline, path: Path) -> object:
    return build_manifest(pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic")


# ---------------------------------------------------------------------------
# UT-C2-6 -- the recorder's topic list equals the union of the pipeline's
# declared ports; UT-C2-7 -- the source-fed ego-signal port is recorded
# ---------------------------------------------------------------------------


def test_topic_list_equals_the_declared_ports_including_the_source_port(tmp_path):
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline = _pipeline(tmp_path)
    source = SyntheticSource([{"veh_dyn": b"vd0"}, {"veh_dyn": b"vd1"}])
    out_path = tmp_path / "out.mcap"
    recorder = Recorder(pipeline, source, out_path, meta=_manifest_for(pipeline, pipeline_path))

    recorder.open(Scenario(name="t", raw={}))
    recorder.tick(50_000_000)
    recorder.tick(50_000_000)
    recorder.close()

    reader = McapReader(out_path)
    topics = set(reader.topics())
    reader.close()

    assert topics == {"source/veh_dyn", "under_test/verdict"}  # UT-C2-6, UT-C2-7


# ---------------------------------------------------------------------------
# UT-C2-8 -- provenance tags: mocked/truth source ports, simulated stage
# outputs
# ---------------------------------------------------------------------------


def test_provenance_tags_source_and_stage_output_ports(tmp_path):
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline = _pipeline(tmp_path)
    source = SyntheticSource([{"veh_dyn": b"vd0"}])
    out_path = tmp_path / "out.mcap"
    recorder = Recorder(
        pipeline, source, out_path, meta=_manifest_for(pipeline, pipeline_path),
        source_provenance=Provenance.TRUTH,
    )

    recorder.open(Scenario(name="t", raw={}))
    recorder.tick(50_000_000)
    recorder.close()

    reader = McapReader(out_path)
    topics = reader.topics()
    reader.close()

    assert topics["source/veh_dyn"].provenance is Provenance.TRUTH
    assert topics["under_test/verdict"].provenance is Provenance.SIMULATED


def test_provenance_can_be_tagged_per_source_port(tmp_path):
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline = _pipeline(tmp_path)
    source = SyntheticSource([{"veh_dyn": b"vd0"}])
    out_path = tmp_path / "out.mcap"
    recorder = Recorder(
        pipeline, source, out_path, meta=_manifest_for(pipeline, pipeline_path),
        source_provenance={"veh_dyn": Provenance.MOCKED},
    )

    recorder.open(Scenario(name="t", raw={}))
    recorder.tick(50_000_000)
    recorder.close()

    reader = McapReader(out_path)
    topics = reader.topics()
    reader.close()

    assert topics["source/veh_dyn"].provenance is Provenance.MOCKED


# ---------------------------------------------------------------------------
# UT-C2-13 -- capture and reception time are both written
# ---------------------------------------------------------------------------


def test_capture_and_reception_time_are_both_written(tmp_path):
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline = _pipeline(tmp_path)
    source = SyntheticSource([{"veh_dyn": b"vd0"}])
    out_path = tmp_path / "out.mcap"
    recorder = Recorder(pipeline, source, out_path, meta=_manifest_for(pipeline, pipeline_path))

    recorder.open(Scenario(name="t", raw={}))
    recorder.tick(50_000_000)
    recorder.close()

    reader = McapReader(out_path)
    messages = list(reader.messages())
    reader.close()

    assert messages  # something was written
    for _topic, log_time_ns, capture_time_ns, _payload in messages:
        assert capture_time_ns == log_time_ns  # known, not defaulted -- see Recorder._write_one


# ---------------------------------------------------------------------------
# record: policy honoured by the recorder itself -- excluded is never a
# topic, decimate keeps only every Nth tick
# ---------------------------------------------------------------------------


def test_excluded_output_port_is_never_a_topic(tmp_path):
    pipeline = _pipeline(tmp_path, record={"verdict": "excluded"})
    pipeline_path = tmp_path / "pipeline.yaml"
    source = SyntheticSource([{"veh_dyn": b"vd0"}])
    out_path = tmp_path / "out.mcap"
    recorder = Recorder(pipeline, source, out_path, meta=_manifest_for(pipeline, pipeline_path))

    recorder.open(Scenario(name="t", raw={}))
    recorder.tick(50_000_000)
    recorder.close()

    reader = McapReader(out_path)
    topics = set(reader.topics())
    reader.close()

    assert "under_test/verdict" not in topics
    assert topics == {"source/veh_dyn"}


def test_decimated_output_port_keeps_only_every_nth_tick(tmp_path):
    pipeline = _pipeline(tmp_path, record={"verdict": {"decimate": 3}})
    pipeline_path = tmp_path / "pipeline.yaml"
    source = SyntheticSource([{"veh_dyn": f"vd{i}".encode()} for i in range(6)])
    out_path = tmp_path / "out.mcap"
    recorder = Recorder(pipeline, source, out_path, meta=_manifest_for(pipeline, pipeline_path))

    recorder.open(Scenario(name="t", raw={}))
    for _ in range(6):
        recorder.tick(50_000_000)
    recorder.close()

    reader = McapReader(out_path)
    verdict_messages = [m for m in reader.messages() if m[0] == "under_test/verdict"]
    reader.close()

    assert len(verdict_messages) == 2  # ticks 0 and 3 of 6 (index % 3 == 0)


# ---------------------------------------------------------------------------
# pipeline=None -- sim record's own case (sim_resim_and_recording.md §9:
# "produces an artifact: yes, executes a SUT: no"): every source.emits()
# port is recorded, nothing is computed.
# ---------------------------------------------------------------------------


def test_pipeline_none_records_every_emitted_source_port_and_nothing_else(tmp_path):
    source = SyntheticSource([{"veh_dyn": b"vd0", "gen_object_list": b"gol0"}])
    out_path = tmp_path / "out.mcap"
    meta = RunManifest(manifest_version=CAPTURE_TIME_MANIFEST_VERSION, run_id="20260101T000000Z-deadbeef", source_kind="synthetic")
    recorder = Recorder(None, source, out_path, meta=meta)

    recorder.open(Scenario(name="t", raw={}))
    recorder.tick(50_000_000)
    recorder.close()

    reader = McapReader(out_path)
    topics = set(reader.topics())
    reader.close()

    assert topics == {"source/veh_dyn", "source/gen_object_list"}


# ---------------------------------------------------------------------------
# ST-C2-3 -- size estimate before starting; revised after ~100 ticks
# ---------------------------------------------------------------------------


def test_estimate_upper_bound_scales_with_ticks(tmp_path):
    pipeline = _pipeline(tmp_path)
    pipeline_path = tmp_path / "pipeline.yaml"
    source = SyntheticSource([])
    out_path = tmp_path / "out.mcap"
    recorder = Recorder(pipeline, source, out_path, meta=_manifest_for(pipeline, pipeline_path))

    ten = recorder.estimate_upper_bound_bytes(10)
    hundred = recorder.estimate_upper_bound_bytes(100)

    assert ten > 0
    assert hundred == ten * 10


def test_revised_estimate_is_none_before_the_threshold_and_a_number_after(tmp_path):
    pipeline = _pipeline(tmp_path)
    pipeline_path = tmp_path / "pipeline.yaml"
    script = [{"veh_dyn": b"vd"} for _ in range(REVISE_AFTER_TICKS)]
    source = SyntheticSource(script)
    out_path = tmp_path / "out.mcap"
    recorder = Recorder(pipeline, source, out_path, meta=_manifest_for(pipeline, pipeline_path))

    recorder.open(Scenario(name="t", raw={}))
    for i in range(REVISE_AFTER_TICKS):
        assert recorder.revised_estimate_bytes(REVISE_AFTER_TICKS * 2) is None
        recorder.tick(50_000_000)
    recorder.close()

    assert recorder.revised_estimate_bytes(REVISE_AFTER_TICKS * 2) is not None
