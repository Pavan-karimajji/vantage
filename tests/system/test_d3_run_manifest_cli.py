# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""S-D3 slice 2 system test: `UT-D3-4`, "the GUI builds a valid run
manifest that the CLI accepts verbatim" -- proven against the REAL `sim
resim` CLI parsing and fallback-resolution path (`cli/resim.run`), not a
reimplementation of it. `sim resim --pipeline <manifest.yaml>` alone (no
recording positional, no `--config`, no `--project`) must resolve exactly
the `recording:`/`project:`/`config:` the manifest carries.

`Pipeline.load`/`resim_pipeline` themselves are mocked here on purpose:
the real CLI entry point resolves `impl:` through `dll:`/`stubdll:` only
(no `components=` injection seam -- `test_c2_record_resim.py`'s own
documented limitation), so exercising a REAL resim through it would need a
built `df_sil`/`echo_stub`, which is a `sil_host`-side C++ fixture this
Python-only suite does not have. What this test actually changed and
needs to prove is the argument-resolution logic in `run()` -- so it
asserts the exact recording/project/config `Pipeline.load`/`resim_pipeline`
were called with, which is the real, complete claim `UT-D3-4` makes about
this half of the round trip.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from adas_sim.cli.resim import run as resim_run
from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.manifest import write_run_manifest


def _manifest(*, component: str, outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=(), outputs=tuple(outputs), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _noop(dt_ns, inputs):
    del dt_ns, inputs
    return {}


def _seed_pipeline(tmp_path: Path) -> Pipeline:
    path = tmp_path / "seed.yaml"
    path.write_text(yaml.safe_dump({
        "name": "seed", "stages": [{"name": "upstream", "mode": "simulate", "impl": "stub:upstream", "inputs": {}}],
    }, sort_keys=False), encoding="utf-8")
    manifest = _manifest(component="upstream", outputs=[PortSpec(name="objects", proto_type="test.Objects")])
    upstream = InProcessSilComponent("upstream", manifest, _noop)
    upstream.init()
    return Pipeline.load(path, components={"upstream": upstream})


def test_sim_resim_reads_recording_project_config_from_the_manifest_alone(tmp_path):
    seed = _seed_pipeline(tmp_path)
    recording_path = tmp_path / "recordings" / "session.mcap"
    recording_path.parent.mkdir()
    recording_path.write_bytes(b"")
    config_path = tmp_path / "config"
    config_path.mkdir()

    manifest_path = tmp_path / "run_manifest.yaml"
    write_run_manifest(manifest_path, pipeline=seed, recording=recording_path, project="cus1", config=config_path)

    fake_pipeline = MagicMock()
    fake_pipeline.stages = ()
    with patch("adas_sim.cli.resim.Pipeline.load", return_value=fake_pipeline) as mock_load, \
         patch("adas_sim.cli.resim.resim_pipeline", return_value=[]) as mock_resim:
        exit_code = resim_run(["--pipeline", str(manifest_path)])

    assert exit_code == 0
    mock_load.assert_called_once()
    assert mock_load.call_args.args[0] == manifest_path
    fake_pipeline.init_components.assert_called_once_with(config_path)
    mock_resim.assert_called_once_with(fake_pipeline, recording_path)


def test_an_explicit_cli_flag_wins_over_the_manifests_own_value(tmp_path):
    seed = _seed_pipeline(tmp_path)
    manifest_recording = tmp_path / "recordings" / "manifest_session.mcap"
    manifest_recording.parent.mkdir()
    manifest_recording.write_bytes(b"")
    override_recording = tmp_path / "override_session.mcap"
    override_recording.write_bytes(b"")

    manifest_path = tmp_path / "run_manifest.yaml"
    write_run_manifest(manifest_path, pipeline=seed, recording=manifest_recording, project="cus1")

    fake_pipeline = MagicMock()
    fake_pipeline.stages = ()
    with patch("adas_sim.cli.resim.Pipeline.load", return_value=fake_pipeline), \
         patch("adas_sim.cli.resim.resim_pipeline", return_value=[]) as mock_resim:
        exit_code = resim_run(["--pipeline", str(manifest_path), str(override_recording), "--project", "base"])

    assert exit_code == 0
    mock_resim.assert_called_once_with(fake_pipeline, override_recording)


def test_missing_recording_in_both_the_cli_and_the_manifest_is_an_authoring_error(tmp_path):
    seed = _seed_pipeline(tmp_path)
    manifest_path = tmp_path / "run_manifest.yaml"
    write_run_manifest(manifest_path, pipeline=seed)  # no recording= given at all

    import pytest
    from adas_sim.core.errors import AuthoringError

    with pytest.raises(AuthoringError, match="recording"):
        resim_run(["--pipeline", str(manifest_path)])
