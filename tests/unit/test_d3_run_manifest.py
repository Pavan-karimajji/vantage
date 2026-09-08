# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""S-D3 slice 2 unit tests (`sim_implementation_plan.md`): `UT-D3-4`
(a valid run manifest the CLI accepts verbatim -- covered against the real
`sim resim` CLI in `test_d3_run_manifest_cli.py`, this file covers the
writer/reader pair beneath it), `UT-D3-5` (round-trip: stages survive
unchanged) and `UT-D3-6` (no absolute path). No Qt.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.graph.pipeline import Pipeline
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.runspec.manifest import RunSpec, load_run_spec, write_run_manifest


def _manifest(*, component: str, outputs=(), inputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _noop(dt_ns, inputs):
    del dt_ns, inputs
    return {}


def _load_pipeline(tmp_path: Path, *, stage_inputs=None) -> Pipeline:
    path = tmp_path / "source_pipeline.yaml"
    path.write_text(yaml.safe_dump({
        "name": "d3_manifest_fixture",
        "stages": [
            {"name": "upstream", "mode": "simulate", "impl": "stub:upstream", "inputs": stage_inputs or {}},
        ],
    }, sort_keys=False), encoding="utf-8")
    manifest = _manifest(component="upstream", outputs=[PortSpec(name="objects", proto_type="test.Objects")])
    upstream = InProcessSilComponent("upstream", manifest, _noop)
    upstream.init()
    return Pipeline.load(path, components={"upstream": upstream})


def test_ut_d3_5_stages_survive_a_write_then_load_round_trip_unchanged(tmp_path):
    pipeline = _load_pipeline(tmp_path)
    manifest_path = tmp_path / "run.yaml"
    write_run_manifest(manifest_path, pipeline=pipeline, mode_overrides={"upstream": "measured"})

    reloaded = Pipeline.load(manifest_path, components={
        "upstream": InProcessSilComponent(
            "upstream", _manifest(component="upstream", outputs=[PortSpec(name="objects", proto_type="test.Objects")]),
            _noop,
        ),
    })
    assert len(reloaded.stages) == 1
    stage = reloaded.stages[0]
    assert stage.name == "upstream"
    assert stage.mode == "measured"  # the override, not the original "simulate"
    assert stage.impl == "stub:upstream"  # unchanged


def test_ut_d3_4_recording_project_config_recovered_by_load_run_spec(tmp_path):
    pipeline = _load_pipeline(tmp_path)
    manifest_path = tmp_path / "sub" / "run.yaml"
    manifest_path.parent.mkdir()
    recording_path = tmp_path / "recordings" / "session.mcap"
    recording_path.parent.mkdir()
    recording_path.write_bytes(b"")
    config_path = tmp_path / "config"
    config_path.mkdir()

    write_run_manifest(
        manifest_path, pipeline=pipeline, recording=recording_path, project="cus1", config=config_path,
    )

    spec = load_run_spec(manifest_path)
    assert spec.recording == recording_path.resolve()
    assert spec.project == "cus1"
    assert spec.config == config_path.resolve()


def test_a_plain_pipeline_file_with_no_run_spec_keys_loads_as_the_default_run_spec(tmp_path):
    pipeline = _load_pipeline(tmp_path)
    spec = load_run_spec(tmp_path / "source_pipeline.yaml")
    assert spec == RunSpec()


def test_ut_d3_6_write_run_manifest_never_writes_an_absolute_path(tmp_path):
    pipeline = _load_pipeline(tmp_path)
    manifest_path = tmp_path / "run.yaml"
    recording_path = tmp_path / "recordings" / "session.mcap"
    recording_path.parent.mkdir()
    recording_path.write_bytes(b"")

    write_run_manifest(manifest_path, pipeline=pipeline, recording=recording_path, config=tmp_path)

    raw_text = manifest_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in raw_text, "an absolute path leaked into the written manifest"


def test_ut_d3_6_load_run_spec_rejects_an_absolute_path_naming_the_file(tmp_path):
    manifest_path = tmp_path / "run.yaml"
    manifest_path.write_text(yaml.safe_dump({
        "name": "bad", "stages": [], "recording": str(tmp_path / "somewhere.mcap"),
    }), encoding="utf-8")

    with pytest.raises(AuthoringError, match="recording"):
        load_run_spec(manifest_path)


def test_write_run_manifest_refuses_to_silently_drop_an_existing_overrides_block(tmp_path):
    path = tmp_path / "with_overrides.yaml"
    path.write_text(yaml.safe_dump({
        "name": "has_overrides",
        "stages": [{
            "name": "upstream", "mode": "simulate", "impl": "stub:upstream", "inputs": {"objects": "source.objects"},
            "overrides": {"objects": {"verb": "hold"}},
        }],
    }, sort_keys=False), encoding="utf-8")
    manifest = _manifest(
        component="upstream", outputs=[PortSpec(name="objects", proto_type="test.Objects")],
        inputs=[PortSpec(name="objects", proto_type="test.Objects")],
    )
    upstream = InProcessSilComponent("upstream", manifest, _noop)
    upstream.init()
    pipeline = Pipeline.load(path, components={"upstream": upstream})

    with pytest.raises(AuthoringError, match="overrides"):
        write_run_manifest(tmp_path / "out.yaml", pipeline=pipeline)
