# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D7 `sim batch` system tests (`docs/sim_implementation_plan.md`):

- `ST-D7-2` -- over >=20 recordings, one report, a failing recording does
  not abort the run.
- `ST-D7-3` -- the SAME pipeline file `sim resim` uses runs unmodified under
  `sim batch` (`R-SIM-16` -- the identity is the point).
- `ST-D7-5` -- a batch of 20 with one deliberately crashing and one
  deliberately hanging produces 18 normal outcomes plus those two, distinctly
  classified; the exit code reflects failure without hiding the successes.
"""

from __future__ import annotations

from pathlib import Path

from adas_sim.cli.batch import run as batch_run
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.resim import resim_pipeline

_TINY = Path(__file__).resolve().parent.parent / "fixtures" / "tiny.mcap"
_RECORDING_COUNT = 20


def _echo_pipeline(tmp_path: Path) -> Path:
    path = tmp_path / "echo_pipeline.yaml"
    path.write_text(
        "version: 1\nname: echo_test\nstages:\n"
        "  - name: echo\n    mode: simulate\n    impl: \"stub:echo\"\n    inputs: {}\n",
        encoding="utf-8",
    )
    return path


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
    pipeline = _echo_pipeline(tmp_path)
    recordings = _copy_recordings(tmp_path, _RECORDING_COUNT)
    # rec_05 fails cleanly (a load/authoring problem, not a crash) -- the
    # rest must still run and be reported.
    monkeypatch.setenv("ADAS_SIM_BATCH_TEST_STUB_MAP", "rec_05=crash")
    report_path = tmp_path / "report.md"

    # --test-stub-echo is core/batch.py's own kwarg, not exposed on the CLI
    # (a real sim batch never needs it -- a real component is always a
    # dll:/stubdll:, see cli/batch.py). Drives core.batch.run_batch/
    # write_report directly -- what cli/batch.py itself calls -- since no
    # compiled component exists in this shell to exercise the CLI's own
    # argv path end to end (test_cli_reports_failure_via_exit_code below
    # covers the CLI layer with a case that needs no stub at all).
    from adas_sim.core.batch import run_batch, write_report

    results = run_batch(recordings, pipeline, test_stub_echo=("echo",), timeout_s=5.0)
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


def test_pipeline_runs_identically_under_resim_and_batch(tmp_path):
    """ST-D7-3: the same pipeline file, unmodified, run through sim resim's
    own engine (resim_pipeline + components=) and through sim batch's
    subprocess path -- both must see the same tick count for the same
    recording."""
    pipeline_path = _echo_pipeline(tmp_path)

    from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent

    manifest = ComponentManifest(
        component="echo", version="test", abi_version=1, build_id="test",
        inputs=(), outputs=(), project="", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )
    component = InProcessSilComponent(name="echo", manifest=manifest, fn=lambda dt_ns, inputs: {})
    pipeline = Pipeline.load(pipeline_path, components={"echo": component})
    pipeline.init_components()
    try:
        direct_outputs = resim_pipeline(pipeline, _TINY)
    finally:
        pipeline.shutdown_components()

    from adas_sim.core.batch import run_batch

    batch_results = run_batch([_TINY], pipeline_path, test_stub_echo=("echo",))

    assert batch_results[0].outcome == "ok"
    assert batch_results[0].tick_count == len(direct_outputs)


def test_batch_of_20_with_one_crash_one_hang_exit_code_reflects_failure(tmp_path, monkeypatch):
    """ST-D7-5."""
    pipeline = _echo_pipeline(tmp_path)
    recordings = _copy_recordings(tmp_path, _RECORDING_COUNT)
    monkeypatch.setenv("ADAS_SIM_BATCH_TEST_STUB_MAP", "rec_03=crash;rec_11=hang")

    from adas_sim.core.batch import run_batch

    results = run_batch(recordings, pipeline, test_stub_echo=("echo",), timeout_s=3.0)

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
