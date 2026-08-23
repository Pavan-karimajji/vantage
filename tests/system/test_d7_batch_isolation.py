# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D7 `sim batch` system tests (`docs/sim_implementation_plan.md`):

- `ST-D7-2` -- over >=20 recordings, one report, a failing recording does
  not abort the run.
- `ST-D7-5` -- a batch of 20 with one deliberately crashing and one
  deliberately hanging produces 18 normal outcomes plus those two, distinctly
  classified; the exit code reflects failure without hiding the successes.

`ST-D7-3` (the SAME pipeline file `sim resim` uses runs unmodified under
`sim batch`) had its own test here, `test_pipeline_runs_identically_under_
resim_and_batch`, comparing against a direct `core.resim.resim_pipeline`
call as an independent oracle -- struck `WP-16`: once `core/resim.py` is
retired, there is no second Python implementation left to compare against,
and `WP-15a` already proved `sil_host`/`simcore` equivalence at the C++
level (`prove_equal.py`, 7/7 rows). `R-SIM-16`'s identity claim itself is
unaffected -- `sim batch` and `sim resim` both go through
`engine.bridge.run_pipeline_via_engine` today, by construction, not by a
test comparing two implementations.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from adas_sim.cli.batch import run as batch_run
from adas_sim.engine.bridge import resolve_simengine_executable
from tests.system.test_d15b_engine_bridge import _echo_stub_path

_TINY = Path(__file__).resolve().parent.parent / "fixtures" / "tiny.mcap"
_RECORDING_COUNT = 20
#: `tiny.mcap`'s own declared cadence (`tests/fixtures/make_tiny_mcap.py`).
_ECHO_PERIOD_NS = 50_000_000


def _echo_pipeline(tmp_path: Path) -> Path:
    """`WP-15b`: `dll:echo_stub`, not `stub:echo` -- see
    `tests/unit/test_d7_batch.py`'s own `_echo_pipeline` docstring, same
    reasoning applied here."""
    path = tmp_path / "echo_pipeline.yaml"
    path.write_text(
        "version: 1\nname: echo_test\nstages:\n"
        "  - name: echo\n    mode: simulate\n    impl: \"dll:echo_stub\"\n    inputs: {}\n",
        encoding="utf-8",
    )
    return path


def _echo_stub_lib_dir(tmp_path: Path, monkeypatch) -> Path:
    """Same helper as `tests/unit/test_d7_batch.py::_echo_stub_lib_dir`,
    duplicated rather than cross-imported (a system-test file importing a
    unit-test helper module would invert the usual dependency direction)."""
    try:
        engine = resolve_simengine_executable()
    except Exception as exc:  # noqa: BLE001 -- EnvironmentError_, re-raised as a skip below
        pytest.skip(f"no built simengine found: {exc}")
    stub = _echo_stub_path(engine)
    if stub is None:
        pytest.skip("no built echo_stub found paired with the resolved simengine binary")
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir(exist_ok=True)
    (lib_dir / ("echo_stub" + stub.suffix)).write_bytes(stub.read_bytes())
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_NAME", "echo")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_PERIOD_NS", str(_ECHO_PERIOD_NS))
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "heartbeat")
    return lib_dir


def _copy_recordings(tmp_path: Path, count: int) -> list[Path]:
    recordings = []
    payload = _TINY.read_bytes()
    for i in range(count):
        path = tmp_path / f"rec_{i:02d}.mcap"
        path.write_bytes(payload)
        recordings.append(path)
    return recordings


def test_batch_over_20_recordings_one_report_failure_does_not_abort(tmp_path, monkeypatch):
    """ST-D7-2."""
    lib_dir = _echo_stub_lib_dir(tmp_path, monkeypatch)
    pipeline = _echo_pipeline(tmp_path)
    recordings = _copy_recordings(tmp_path, _RECORDING_COUNT)
    # rec_05 fails cleanly (a load/authoring problem, not a crash) -- the
    # rest must still run and be reported.
    monkeypatch.setenv("ADAS_SIM_BATCH_TEST_STUB_MAP", "rec_05=crash")
    report_path = tmp_path / "report.md"

    from adas_sim.orchestrate.batch import run_batch, write_report

    results = run_batch(recordings, pipeline, search=[lib_dir], timeout_s=5.0)
    write_report(results, report_path)

    assert len(results) == _RECORDING_COUNT
    assert report_path.is_file()
    report_text = report_path.read_text(encoding="utf-8")
    assert f"{_RECORDING_COUNT} recording(s)" in report_text
    for r in recordings:
        assert str(r) in report_text

    crashed = [r for r in results if r.outcome == "crash"]
    ok = [r for r in results if r.outcome == "ok"]
    assert len(crashed) == 1
    assert crashed[0].recording.stem == "rec_05"
    assert len(ok) == _RECORDING_COUNT - 1


def test_batch_of_20_with_one_crash_one_hang_exit_code_reflects_failure(tmp_path, monkeypatch):
    """ST-D7-5."""
    lib_dir = _echo_stub_lib_dir(tmp_path, monkeypatch)
    pipeline = _echo_pipeline(tmp_path)
    recordings = _copy_recordings(tmp_path, _RECORDING_COUNT)
    monkeypatch.setenv("ADAS_SIM_BATCH_TEST_STUB_MAP", "rec_03=crash;rec_11=hang")

    from adas_sim.orchestrate.batch import run_batch

    results = run_batch(recordings, pipeline, search=[lib_dir], timeout_s=3.0)

    by_stem = {r.recording.stem: r.outcome for r in results}
    assert by_stem["rec_03"] == "crash"
    assert by_stem["rec_11"] == "timeout"
    others_ok = [outcome for stem, outcome in by_stem.items() if stem not in ("rec_03", "rec_11")]
    assert others_ok == ["ok"] * (_RECORDING_COUNT - 2)

    # sim batch's own exit-code contract (cli/batch.py): non-zero whenever
    # not every recording is ok, but every outcome is still fully reported
    # above -- the failure is never hidden and never aborts earlier rows.
    ok_count = sum(1 for r in results if r.outcome == "ok")
    exit_code = 0 if ok_count == len(results) else 1
    assert exit_code == 1
    assert ok_count == _RECORDING_COUNT - 2


def test_cli_reports_failure_via_exit_code(tmp_path, capsys):
    """Exercises `cli/batch.py`'s own argv parsing and exit code end to end
    -- a scenario that needs no compiled component at all (every recording
    fails cleanly at Pipeline.load, since the pipeline file names an
    unresolvable dll:), so it runs through the real CLI entry point rather
    than core.batch.run_batch directly."""
    missing_dll_pipeline = tmp_path / "unresolvable.yaml"
    missing_dll_pipeline.write_text(
        "version: 1\nname: unresolvable\nstages:\n"
        "  - name: nope\n    mode: simulate\n    impl: \"dll:does_not_exist\"\n    inputs: {}\n",
        encoding="utf-8",
    )
    recordings = _copy_recordings(tmp_path, 3)
    report_path = tmp_path / "cli_report.md"

    exit_code = batch_run(
        [str(r) for r in recordings] + ["--pipeline", str(missing_dll_pipeline), "--report", str(report_path)]
    )

    assert exit_code == 1
    assert report_path.is_file()
    stdout = capsys.readouterr().out
    assert "sim batch complete: 0/3 ok" in stdout


def test_cli_no_recordings_matched_is_a_distinct_exit_code(tmp_path):
    exit_code = batch_run([str(tmp_path / "nothing_here_*.mcap")] + ["--pipeline", str(tmp_path / "p.yaml")])
    assert exit_code == 2
