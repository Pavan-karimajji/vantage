# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C2 system tests: `ST-C2-1` (`sim record` on the synthetic source
produces a recording that `sim resim` consumes with every stage `measured`
except one) and `ST-C2-2` (`sim resim` reproduces byte-identical outputs
across two runs) -- `docs/sim_implementation_plan.md`.

Drives the real engines underneath the CLI verbs (`sources.recorder.Recorder`,
`cli.resim.resim_pipeline`) rather than `cli.record.run`/`cli.resim.run`
themselves: those top-level entry points resolve `impl:` through
`dll:`/`stubdll:` only (no `components=` registry to inject a Python stub,
same limitation `test_c1c_pipeline.py`'s own fixtures accept), and no
compiled SIL library exists in this Python-only test environment.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from adas_sim.cli.resim import resim_pipeline
from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.manifest import build_manifest
from adas_sim.sources.base import Scenario
from adas_sim.sources.recorder import Recorder
from adas_sim.sources.synthetic import SyntheticSource


def _manifest(*, component: str, inputs=(), outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


_UPSTREAM_MANIFEST = _manifest(
    component="upstream", inputs=[PortSpec(name="egoDyn", proto_type="test.VehDyn")],
    outputs=[PortSpec(name="objects", proto_type="test.Objects")],
)
_UNDER_TEST_MANIFEST = _manifest(
    component="under_test", inputs=[PortSpec(name="objects", proto_type="test.Objects")],
    outputs=[PortSpec(name="verdict", proto_type="test.Verdict")],
)


def _upstream_fn(dt_ns, inputs):
    return {"objects": inputs["egoDyn"] + b"-objects"}


def _under_test_fn(dt_ns, inputs):
    return {"verdict": inputs["objects"] + b"-verdict"}


def _write_pipeline(path: Path, stages: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"name": "algo_test", "stages": stages}, sort_keys=False), encoding="utf-8")


def _record_pipeline(path: Path) -> Pipeline:
    """Both stages `simulate` -- what produced the recording (`sim run
    --record`'s shape, `sources.recorder.Recorder`)."""
    stages = [
        {"name": "upstream", "mode": "simulate", "impl": "stub:upstream", "inputs": {"egoDyn": "source.veh_dyn"}},
        {"name": "under_test", "mode": "simulate", "impl": "stub:under_test", "inputs": {"objects": "upstream.objects"}},
    ]
    _write_pipeline(path, stages)
    upstream = InProcessSilComponent("upstream", _UPSTREAM_MANIFEST, _upstream_fn)
    upstream.init()
    under_test = InProcessSilComponent("under_test", _UNDER_TEST_MANIFEST, _under_test_fn)
    under_test.init()
    return Pipeline.load(path, components={"upstream": upstream, "under_test": under_test})


def _resim_pipeline_(path: Path) -> Pipeline:
    """`upstream` -> `measured` (fed from the recording), `under_test` ->
    `simulate` (executed live) -- ST-C2-1's own "every stage measured
    except one," the canonical algo-test shape (`ST-C1c-2`)."""
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


def _record(tmp_path: Path) -> Path:
    record_pipeline_path = tmp_path / "record_pipeline.yaml"
    pipeline = _record_pipeline(record_pipeline_path)
    source = SyntheticSource([{"veh_dyn": f"vd{i}".encode()} for i in range(5)])
    recording_path = tmp_path / "recording.mcap"
    meta = build_manifest(
        pipeline=pipeline, pipeline_path=record_pipeline_path, run_kind="sim", source_kind="synthetic",
    )
    recorder = Recorder(pipeline, source, recording_path, meta=meta)
    recorder.open(Scenario(name="algo_test", raw={}))
    for _ in range(5):
        recorder.tick(50_000_000)
    recorder.close()
    return recording_path


def test_st_c2_1_record_on_synthetic_then_resim_consumes_it_with_one_stage_simulate(tmp_path):
    recording_path = _record(tmp_path)

    resim_path = tmp_path / "resim_pipeline.yaml"
    pipeline = _resim_pipeline_(resim_path)
    outputs = resim_pipeline(pipeline, recording_path)

    verdicts = [tick_outputs["under_test"]["verdict"] for _t_ns, tick_outputs in outputs]
    assert verdicts == [f"vd{i}-objects-verdict".encode() for i in range(5)]


def test_st_c2_2_resim_reproduces_byte_identical_outputs_across_two_runs(tmp_path):
    recording_path = _record(tmp_path)

    resim_path = tmp_path / "resim_pipeline.yaml"
    first_pipeline = _resim_pipeline_(resim_path)
    first = resim_pipeline(first_pipeline, recording_path)

    second_pipeline = _resim_pipeline_(resim_path)  # fresh InProcessSilComponent instances -- no shared state
    second = resim_pipeline(second_pipeline, recording_path)

    # The comparison is over (topic, log_time_ns, bytes) for declared ports
    # (sim_resim_and_recording.md's own clarification) -- port values, never
    # file bytes.
    assert first == second
