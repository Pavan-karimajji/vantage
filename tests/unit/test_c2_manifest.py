# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C2 slice 3: `core/manifest.py` -- `UT-C2-5` (manifest fields present,
hashes stable)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.manifest import build_manifest
from adas_sim.io.base import CAPTURE_TIME_MANIFEST_VERSION


def _manifest(*, component: str, inputs=(), outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _stub(name: str, manifest: ComponentManifest) -> InProcessSilComponent:
    component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
    component.init()
    return component


def _pipeline(
    tmp_path: Path, *, overrides: dict | None = None, record: dict | None = None,
) -> tuple[Pipeline, Path]:
    stage = {
        "name": "under_test", "mode": "simulate", "impl": "stub:under_test",
        "inputs": {"egoDyn": "source.veh_dyn"},
    }
    if overrides:
        stage["overrides"] = overrides
    if record:
        stage["record"] = record
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"name": "test", "stages": [stage]}, sort_keys=False), encoding="utf-8")
    manifest = _manifest(
        component="under_test", inputs=[PortSpec(name="egoDyn", proto_type="test.A")],
        outputs=[PortSpec(name="verdict", proto_type="test.A")],
    )
    return Pipeline.load(path, components={"under_test": _stub("under_test", manifest)}), path


_CLOCK = datetime(2026, 8, 3, 12, 0, 0, tzinfo=timezone.utc)


def test_build_manifest_carries_declared_fields(tmp_path):
    pipeline, path = _pipeline(tmp_path)

    manifest = build_manifest(
        pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic",
        project="base", scenario_name="my_case", seed=7, clock=_CLOCK,
    )

    assert manifest.manifest_version == CAPTURE_TIME_MANIFEST_VERSION
    assert manifest.run_kind == "sim"
    assert manifest.source_kind == "synthetic"
    assert manifest.project == "base"
    assert manifest.scenario == "my_case"
    assert manifest.pipeline == "test"
    assert manifest.seed == 7
    assert manifest.created_utc == "2026-08-03T12:00:00Z"
    assert manifest.run_id.startswith("20260803T120000Z-")
    assert [c.name for c in manifest.components] == ["under_test"]


def test_run_id_is_stable_for_identical_inputs(tmp_path):
    pipeline, path = _pipeline(tmp_path)

    first = build_manifest(pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    second = build_manifest(pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)

    assert first.run_id == second.run_id


def test_run_id_differs_when_overrides_differ(tmp_path):
    plain_dir, overridden_dir = tmp_path / "plain", tmp_path / "overridden"
    plain_dir.mkdir()
    overridden_dir.mkdir()
    plain, plain_path = _pipeline(plain_dir)
    overridden, overridden_path = _pipeline(overridden_dir, overrides={"egoDyn": {"verb": "hold"}})

    plain_manifest = build_manifest(pipeline=plain, pipeline_path=plain_path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    overridden_manifest = build_manifest(
        pipeline=overridden, pipeline_path=overridden_path, run_kind="sim", source_kind="synthetic", clock=_CLOCK,
    )

    assert plain_manifest.run_id != overridden_manifest.run_id


def test_manifest_overrides_are_legible_not_only_hashed(tmp_path):
    """UT-D6-2: `R-SIM-15`'s "declared, never smuggled" made legible --
    previously an override only affected `run_id`'s hash (the test above),
    with no way to read back WHICH override actually applied from the
    manifest itself."""
    pipeline, path = _pipeline(tmp_path, overrides={"egoDyn": {"verb": "hold"}})
    manifest = build_manifest(pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)

    assert len(manifest.overrides) == 1
    record = manifest.overrides[0]
    assert record.stage == "under_test"
    assert record.address == "egoDyn"
    assert record.verb == "hold"
    assert record.value is None  # hold carries no value


def test_manifest_carries_a_const_override_with_its_value(tmp_path):
    pipeline, path = _pipeline(tmp_path, overrides={"egoDyn": {"verb": "const", "value": 5.0}})
    manifest = build_manifest(pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)

    assert manifest.overrides[0].verb == "const"
    assert manifest.overrides[0].value == 5.0


def test_manifest_overrides_are_empty_with_no_pipeline():
    manifest = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    assert manifest.overrides == ()


def test_manifest_records_the_full_policy_by_default_not_only_exceptions(tmp_path):
    """UT-C2-12: `full` is written too, not omitted -- a reader must be
    able to tell "recorded in full, by declaration" from "nothing here
    ever said anything about this port," which are different facts."""
    pipeline, path = _pipeline(tmp_path)  # no record: block at all
    manifest = build_manifest(pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)

    assert len(manifest.record_policies) == 1
    record = manifest.record_policies[0]
    assert record.port == "under_test.verdict"
    assert record.verb == "full"
    assert record.decimate_n == 0


def test_manifest_records_an_excluded_port_rather_than_omitting_it(tmp_path):
    pipeline, path = _pipeline(tmp_path, record={"verdict": "excluded"})
    manifest = build_manifest(pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)

    assert manifest.record_policies[0].verb == "excluded"


def test_manifest_records_a_decimated_port_with_its_n(tmp_path):
    pipeline, path = _pipeline(tmp_path, record={"verdict": {"decimate": 10}})
    manifest = build_manifest(pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)

    assert manifest.record_policies[0].verb == "decimate"
    assert manifest.record_policies[0].decimate_n == 10


def test_manifest_record_policies_are_empty_with_no_pipeline():
    manifest = build_manifest(run_kind="sim", source_kind="synthetic", clock=_CLOCK)
    assert manifest.record_policies == ()


def test_off_stage_is_excluded_from_components(tmp_path):
    stages = [
        {"name": "under_test", "mode": "simulate", "impl": "stub:under_test", "inputs": {}},
        {"name": "disabled", "mode": "off", "impl": "stub:disabled", "inputs": {}},
    ]
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"name": "test", "stages": stages}, sort_keys=False), encoding="utf-8")
    components = {
        "under_test": _stub("under_test", _manifest(component="under_test")),
        "disabled": _stub("disabled", _manifest(component="disabled")),
    }
    pipeline = Pipeline.load(path, components=components)

    manifest = build_manifest(pipeline=pipeline, pipeline_path=path, run_kind="sim", source_kind="synthetic", clock=_CLOCK)

    assert [c.name for c in manifest.components] == ["under_test"]
