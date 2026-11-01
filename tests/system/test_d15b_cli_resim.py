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
    # Paired by the resolved engine binary's own format, never by os.name --
    # see test_d15b_engine_bridge.py::_echo_stub_path's own docstring for
    # the exact "Bad Image" (0xc000012f) bug this pairing avoids.
    try:
        engine = resolve_simengine_executable()
    except EnvironmentError_ as exc:
        pytest.skip(f"no built simengine found: {exc}")
    stub = _echo_stub_path(engine)
    if stub is None:
        pytest.skip("no built echo_stub found paired with the resolved simengine binary")
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
        "name: cli_resim_test\n"
        "run_setup:\n  readiness_limit_steps: 8\n  fallback_max_gap: 6\n"
        "stages:\n"
        "  - name: sut\n    mode: simulate\n    impl: dll:echo_stub\n    inputs: {}\n"
        "    trigger: ''\n    buffer_depth: {'*': 16}\n",
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
        # IMP-0216: --save's own build_manifest call now receives a real
        # spec_sha256 (engine.bridge.run_pipeline_via_engine's own returned
        # write_run_spec hash, previously discarded) instead of the field's
        # "" default.
        assert reader.meta().run_spec_sha256
    finally:
        reader.close()


def _write_recording_with_wrong_recorded_output(path: Path) -> None:
    """Same three-tick heartbeat grid `_write_heartbeat_recording` writes,
    PLUS a `/sut/outputs` topic at every tick carrying a single `0xFF`
    byte -- a payload `echo_stub`'s own real, deterministic output
    (`EncodeAbiTestPort`'s encoding of `ADAS_SIL_TEST_STUB_OUTPUT_VALUE`,
    several bytes, never one raw `0xFF`) cannot coincidentally match, so a
    real run through the real engine genuinely diverges at tick 0 --
    `IMP-0224`'s own end-to-end fixture, not a mocked latch."""
    writer = writer_for(path)
    writer.open(
        path, meta=RunManifest(),
        topics={
            "/dummy/heartbeat": TopicInfo(schema_name="test.Heartbeat", provenance=Provenance.MEASURED),
            "/sut/outputs": TopicInfo(schema_name="test.Echo", provenance=Provenance.MEASURED),
        },
    )
    for t_ns in (0, 10_000_000, 20_000_000):
        writer.write("/dummy/heartbeat", t_ns, b"\x01", capture_time_ns=t_ns)
        writer.write("/sut/outputs", t_ns, b"\xff", capture_time_ns=t_ns)
    writer.close()


def test_sim_resim_cli_save_carries_a_real_divergence_in_its_manifest(tmp_path, monkeypatch, capsys):
    """`IMP-0224` (`SW-0224`): `simcore::runner::DivergenceLatch`'s first
    observed divergence, plumbed through `checkpoint.cpp`'s `progress.json`
    and `orchestrate.batch.read_checkpoint_divergence`, reaches the
    `--save`'d manifest's own `divergence` field -- real, through the real
    `simengine` executable, not a Python-side simulation of the C++ latch."""
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
        "name: cli_resim_divergence_test\n"
        "run_setup:\n  readiness_limit_steps: 8\n  fallback_max_gap: 6\n"
        "stages:\n"
        "  - name: sut\n    mode: simulate\n    impl: dll:echo_stub\n    inputs: {}\n"
        "    trigger: ''\n    buffer_depth: {'*': 16}\n",
        encoding="utf-8",
    )
    recording_path = tmp_path / "in.mcap"
    _write_recording_with_wrong_recorded_output(recording_path)
    save_path = tmp_path / "out.mcap"

    exit_code = resim_run([
        str(recording_path), "--pipeline", str(pipeline_path), "--search", str(lib_dir),
        "--save", str(save_path),
    ])

    assert exit_code == 0
    reader = reader_for(save_path)
    try:
        divergence = reader.meta().divergence
    finally:
        reader.close()
    assert divergence != "unknown"
    assert "tick 0" in divergence
    assert "'sut.outputs'" in divergence


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
        "name: cli_resim_test2\n"
        "run_setup:\n  readiness_limit_steps: 8\n  fallback_max_gap: 6\n"
        "stages:\n"
        "  - name: sut\n    mode: simulate\n    impl: dll:echo_stub\n    inputs: {}\n"
        "    trigger: ''\n    buffer_depth: {'*': 16}\n",
        encoding="utf-8",
    )
    recording_path = tmp_path / "in.mcap"
    _write_heartbeat_recording(recording_path)

    exit_code = resim_run([str(recording_path), "--pipeline", str(pipeline_path), "--search", str(lib_dir)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "wrote" not in captured.out
    assert "resim complete: 3 tick(s)" in captured.out
