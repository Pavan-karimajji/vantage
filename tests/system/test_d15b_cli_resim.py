# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-15b` (`IMP-0422`): `cli.resim.run` (`sim resim`) end to end, through
the real `simengine` executable -- the first test to ever exercise this CLI
entry point for real (`test_c2_record_resim.py`'s own docstring: no
compiled SIL library existed in this Python-only test environment before
this package added a real, resolvable `echo_stub` path). Skips (never
fails) when this platform's own `simengine`/`echo_stub` build is absent."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.cli.resim import run as resim_run
from adas_sim.diagnostics.errors import EnvironmentError_
from adas_sim.engine.bridge import resolve_simengine_executable
from adas_sim.io.base import Provenance, RunManifest, TopicInfo
from adas_sim.plugins.registry import reader_for, writer_for

from tests.system.test_d15b_engine_bridge import (
    _echo_stub_path,
    _write_heartbeat_recording,
)


def _require_engine_and_stub() -> Path:
    stub = _echo_stub_path()
    if stub is None:
        pytest.skip("no built echo_stub found for this platform")
    try:
        resolve_simengine_executable()
    except EnvironmentError_ as exc:
        pytest.skip(f"no built simengine found: {exc}")
    return stub


def test_sim_resim_cli_runs_a_real_stage_through_simengine(tmp_path, monkeypatch, capsys):
    stub_path = _require_engine_and_stub()

    monkeypatch.setenv("ADAS_SIL_TEST_STUB_NAME", "echo_stub")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_PERIOD_NS", "10000000")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PROTO_TYPE", "test.Echo")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_MAX_BYTES", "64")

    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    stub_copy = lib_dir / ("echo_stub" + stub_path.suffix)
    stub_copy.write_bytes(stub_path.read_bytes())

    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text(
        "name: cli_resim_test\nstages:\n"
        "  - name: sut\n    mode: simulate\n    impl: dll:echo_stub\n    inputs: {}\n",
        encoding="utf-8",
    )
    recording_path = tmp_path / "in.mcap"
    _write_heartbeat_recording(recording_path)
    save_path = tmp_path / "out.mcap"

    exit_code = resim_run([
        str(recording_path), "--pipeline", str(pipeline_path), "--search", str(lib_dir),
        "--save", str(save_path),
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert f"wrote {save_path}" in captured.out
    assert "resim complete:" in captured.out
    assert save_path.is_file()

    reader = reader_for(save_path)
    try:
        assert "/sut/outputs" in reader.topics()
    finally:
        reader.close()


def test_sim_resim_cli_without_save_still_reports_ticks_and_cleans_up(tmp_path, monkeypatch, capsys):
    stub_path = _require_engine_and_stub()

    monkeypatch.setenv("ADAS_SIL_TEST_STUB_NAME", "echo_stub")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_PERIOD_NS", "10000000")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PROTO_TYPE", "test.Echo")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_MAX_BYTES", "64")

    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    stub_copy = lib_dir / ("echo_stub" + stub_path.suffix)
    stub_copy.write_bytes(stub_path.read_bytes())

    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text(
        "name: cli_resim_test2\nstages:\n"
        "  - name: sut\n    mode: simulate\n    impl: dll:echo_stub\n    inputs: {}\n",
        encoding="utf-8",
    )
    recording_path = tmp_path / "in.mcap"
    _write_heartbeat_recording(recording_path)

    exit_code = resim_run([str(recording_path), "--pipeline", str(pipeline_path), "--search", str(lib_dir)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "wrote" not in captured.out
    assert "resim complete: 3 tick(s)" in captured.out
