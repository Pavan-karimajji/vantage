# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-28` `SI-22 launcher` -- `IT-21` (`launcher/write.py::launch`,
`SW-0343`): `launch()` reached through the written path, real end to end
through `simengine` -- the same `echo_stub`/`simengine` pairing
`test_d15b_cli_resim.py` proves `sim resim` against, driven here through
`launcher.write.to_run_config`/`launch` instead of the CLI directly, so
"a run started from the written file and a headless `sim resim` of it are
identical" is proven by calling the SAME underlying function
(`adas_sim.cli.resim.run`), not merely asserted. Skips (never fails) when
this platform's own `simengine`/`echo_stub` build is absent, same
discipline `test_d15b_cli_resim.py` uses."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.diagnostics.errors import EnvironmentError_
from adas_sim.engine.bridge import resolve_simengine_executable
from adas_sim.graph.pipeline import Pipeline
from adas_sim.launcher.model import Selection
from adas_sim.launcher.write import launch, to_run_config

from tests.system.test_d15b_engine_bridge import _echo_stub_path, _write_heartbeat_recording


def _require_engine_and_stub() -> Path:
    try:
        engine = resolve_simengine_executable()
    except EnvironmentError_ as exc:
        pytest.skip(f"no built simengine found: {exc}")
    stub = _echo_stub_path(engine)
    if stub is None:
        pytest.skip("no built echo_stub found paired with the resolved simengine binary")
    return stub


def _stub_env(monkeypatch) -> None:
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_NAME", "echo_stub")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_PERIOD_NS", "10000000")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PROTO_TYPE", "test.Echo")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_MAX_BYTES", "64")


def test_launch_reaches_a_real_run_only_through_the_written_path(tmp_path, monkeypatch, capsys):
    stub_path = _require_engine_and_stub()
    _stub_env(monkeypatch)

    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    stub_copy = lib_dir / ("echo_stub" + stub_path.suffix)
    stub_copy.write_bytes(stub_path.read_bytes())

    recording_path = tmp_path / "in.mcap"
    _write_heartbeat_recording(recording_path)

    base_pipeline = Pipeline.load(_write_pipeline_file(tmp_path), search=(lib_dir,))
    selection = Selection(
        base_pipeline=base_pipeline, recordings=(recording_path,), selected_recording=recording_path,
        search=(lib_dir,),
    )

    config_path = tmp_path / "launcher_run" / "config.yaml"
    written = to_run_config(selection, config_path)
    assert written == config_path

    exit_code = launch(config_path, search=(lib_dir,))

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "resim complete:" in captured.out  # reached cli.resim.run, not a second implementation


def _write_pipeline_file(tmp_path: Path) -> Path:
    path = tmp_path / "base_pipeline.yaml"
    path.write_text(
        "name: launcher_it21\nrun_setup:\n  readiness_limit_steps: 8\n  fallback_max_gap: 6\nstages:\n"
        "  - name: sut\n    mode: simulate\n    impl: dll:echo_stub\n    inputs: {}\n"
        "    trigger: ''\n    buffer_depth: {'*': 16}\n",
        encoding="utf-8",
    )
    return path


# `SW-0342`'s "a BROKEN chain blocks before `cli.resim.run` is ever
# invoked" is proven at the unit level in `test_lnc_write.py` (mocked
# reload, no compiled component needed) -- `echo_stub` declares no input
# ports (`_echo_manifest()`'s own `inputs=()`), so a genuine multi-stage
# consumption chain cannot be wired through it here without a second stub
# fixture; not worth adding only to re-prove a fact `LaunchBlocked`'s own
# unit test already covers.
