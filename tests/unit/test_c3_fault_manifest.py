# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C3's own status-note claim, closed 2026-08-06: "a fault is declared in
`run.faults:`, lands in the run manifest" -- `R-SIM-15`'s "declared, never
smuggled" extended from overrides (`UT-D6-2`) to faults. `contracts.fault`'s
own behavioural-effect tests (`test_c3_fault.py`, `UT-C3-8`) are a different
concern; this covers the manifest-legibility half only.

**No topic tag exists for this, and deliberately so** -- same finding
`UT-D6-2` made for overrides: a fault mutates the STIMULUS right before a
stage sees it, but the recorded `source.*` topic is `Recorder.tick`'s own
raw, pre-fault `stimulus`. See `io.base.FaultRecord`'s own docstring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.contracts.fault import Fault, FaultVerb
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.manifest import build_manifest

_CLOCK = datetime(2026, 8, 6, 12, 0, 0, tzinfo=timezone.utc)


def _manifest(*, component: str, inputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=(), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _pipeline(tmp_path: Path, *, faults: list[Fault] = ()) -> tuple[Pipeline, Path]:
    stage = {"name": "df", "mode": "simulate", "impl": "stub:df", "inputs": {"egoDyn": "source.veh_dyn"}}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"name": "test", "stages": [stage]}, sort_keys=False), encoding="utf-8")
    manifest = _manifest(component="df", inputs=[PortSpec(name="egoDyn", proto_type="test.A")])
    component = InProcessSilComponent("df", manifest, lambda dt_ns, inputs: {})
    component.init()
    pipeline = Pipeline.load(path, components={"df": component}, faults=faults)
    return pipeline, path


def test_pipeline_exposes_its_own_declared_faults_publicly(tmp_path):
    fault = Fault(verb=FaultVerb.STALE, address="veh_dyn", from_s=0.0, to_s=10.0)
    pipeline, _ = _pipeline(tmp_path, faults=[fault])
    assert pipeline.faults == (fault,)


def test_manifest_carries_a_declared_fault(tmp_path):
    fault = Fault(verb=FaultVerb.STALE, address="veh_dyn", from_s=0.0, to_s=10.0)
    pipeline, path = _pipeline(tmp_path, faults=[fault])

    manifest = build_manifest(pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)

    assert len(manifest.faults) == 1
    record = manifest.faults[0]
    assert record.verb == "stale"
    assert record.address == "veh_dyn"
    assert record.from_s == 0.0
    assert record.to_s == 10.0
    assert record.value is None
    assert record.after_tick is None


def test_manifest_carries_a_corrupt_fault_with_its_value(tmp_path):
    fault = Fault(verb=FaultVerb.CORRUPT, address="veh_dyn.x", value=42.0, after_tick=5)
    pipeline, path = _pipeline(tmp_path, faults=[fault])

    manifest = build_manifest(pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)

    assert manifest.faults[0].verb == "corrupt"
    assert manifest.faults[0].value == 42.0
    assert manifest.faults[0].after_tick == 5


def test_manifest_faults_are_empty_with_no_declared_faults(tmp_path):
    pipeline, path = _pipeline(tmp_path)
    manifest = build_manifest(pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    assert manifest.faults == ()


def test_manifest_faults_are_empty_with_no_pipeline():
    manifest = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    assert manifest.faults == ()


def test_run_id_differs_when_faults_differ(tmp_path):
    plain_dir, faulted_dir = tmp_path / "plain", tmp_path / "faulted"
    plain_dir.mkdir()
    faulted_dir.mkdir()
    plain, plain_path = _pipeline(plain_dir)
    faulted, faulted_path = _pipeline(
        faulted_dir, faults=[Fault(verb=FaultVerb.DROP, address="veh_dyn", from_s=0.0, to_s=5.0)],
    )

    plain_manifest = build_manifest(pipeline=plain, pipeline_path=plain_path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    faulted_manifest = build_manifest(pipeline=faulted, pipeline_path=faulted_path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)

    assert plain_manifest.run_id != faulted_manifest.run_id
