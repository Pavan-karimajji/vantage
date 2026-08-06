# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D7 `sim batch` unit tests (`docs/sim_implementation_plan.md`):
`UT-D7-7` (a crashing stage is contained and classified `crash`, and the
tick it got to before dying is captured via `--checkpoint-json`),
`UT-D7-8` (a hung stage is contained and classified `timeout`, never
`crash`/`fail`), plus `core/batch.py`'s own building blocks
(`expand_recordings`, order preservation, `write_report`). Uses the
`batch_worker`'s explicitly test-only hooks (`ADAS_SIM_BATCH_TEST_STUB[_MAP]`,
`ADAS_SIM_BATCH_TEST_CRASH_AFTER_TICK`, `--test-stub-echo`) -- see
`core/batch_worker.py`'s own docstring for why these exist and why they can
never fire from a real `sim batch` invocation.
"""

from __future__ import annotations

from pathlib import Path

from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.batch import RecordingOutcome, expand_recordings, run_batch, write_report
from adas_sim.core.resim import resim_pipeline

_TINY = Path(__file__).resolve().parent.parent / "fixtures" / "tiny.mcap"


def _echo_pipeline(tmp_path: Path, stage_name: str = "echo") -> Path:
    path = tmp_path / f"{stage_name}_pipeline.yaml"
    path.write_text(
        f"version: 1\nname: {stage_name}_test\nstages:\n"
        f"  - name: {stage_name}\n    mode: simulate\n    impl: \"stub:{stage_name}\"\n    inputs: {{}}\n",
        encoding="utf-8",
    )
    return path


def test_expand_recordings_literal_glob_and_list_file(tmp_path):
    (tmp_path / "a.mcap").write_bytes(b"")
    (tmp_path / "b.mcap").write_bytes(b"")
    list_file = tmp_path / "recs.txt"
    list_file.write_text(f"# comment\n{tmp_path / 'a.mcap'}\n\n{tmp_path / 'b.mcap'}\n", encoding="utf-8")

    assert expand_recordings([str(tmp_path / "a.mcap")]) == [tmp_path / "a.mcap"]
    assert sorted(expand_recordings([str(tmp_path / "*.mcap")])) == sorted([tmp_path / "a.mcap", tmp_path / "b.mcap"])
    assert expand_recordings([str(list_file)]) == [tmp_path / "a.mcap", tmp_path / "b.mcap"]


def test_ok_recording_runs_the_real_pipeline_end_to_end(tmp_path):
    """The non-test-hook path: a real Pipeline.load/init_components/
    resim_pipeline/shutdown_components sequence, over tiny.mcap's 20 ticks."""
    pipeline = _echo_pipeline(tmp_path)
    results = run_batch([_TINY], pipeline, test_stub_echo=("echo",))
    assert len(results) == 1
    assert results[0].outcome == "ok"
    assert results[0].tick_count == 20


def test_a_bad_pipeline_reports_fail_not_crash(tmp_path):
    missing_pipeline = tmp_path / "does_not_exist.yaml"
    results = run_batch([_TINY], missing_pipeline)
    assert results[0].outcome == "fail"
    assert results[0].error  # names what went wrong, never a bare failure


def test_crashing_stage_is_contained_and_classified_crash(tmp_path, monkeypatch):
    """UT-D7-7."""
    monkeypatch.setenv("ADAS_SIM_BATCH_TEST_STUB", "crash")
    pipeline = _echo_pipeline(tmp_path)
    results = run_batch([_TINY], pipeline, test_stub_echo=("echo",))
    assert results[0].outcome == "crash"
    assert "exit code" in results[0].error


def _direct_resim_outputs(pipeline_path: Path) -> list[tuple[int, dict]]:
    """A direct, non-subprocess resim of `_TINY` against `pipeline_path`, for
    comparison against a batch result's own `last_tick_ns` -- same pattern
    `test_d7_batch_isolation.py::test_pipeline_runs_identically_under_
    resim_and_batch` already uses."""
    manifest = ComponentManifest(
        component="echo", version="test", abi_version=1, build_id="test-stub-echo",
        inputs=(), outputs=(), project="", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )
    component = InProcessSilComponent(name="echo", manifest=manifest, fn=lambda dt_ns, inputs: {})
    pipeline = Pipeline.load(pipeline_path, components={"echo": component})
    pipeline.init_components(None)
    try:
        return resim_pipeline(pipeline, _TINY)
    finally:
        pipeline.shutdown_components()


def test_crash_mid_run_reports_the_real_last_tick_via_checkpoint(tmp_path, monkeypatch):
    """UT-D7-7's own "last tick" gap: unlike the blanket ADAS_SIM_BATCH_TEST_STUB
    hook (which dies before any pipeline runs), ADAS_SIM_BATCH_TEST_CRASH_AFTER_TICK
    lets a real resim run N ticks for real -- against tiny.mcap's actual 20 --
    then die from inside `on_tick`. The checkpoint file, written after every
    tick and read by the parent from the outside, is what survives; the
    worker's own in-memory state does not."""
    monkeypatch.setenv("ADAS_SIM_BATCH_TEST_CRASH_AFTER_TICK", "7")
    pipeline_path = _echo_pipeline(tmp_path)
    results = run_batch([_TINY], pipeline_path, test_stub_echo=("echo",))
    assert results[0].outcome == "crash"
    assert results[0].tick_count == 7

    direct_outputs = _direct_resim_outputs(pipeline_path)
    assert results[0].last_tick_ns == direct_outputs[6][0]  # tick 7, 0-indexed


def test_hung_stage_is_contained_and_classified_timeout_not_crash_or_fail(tmp_path, monkeypatch):
    """UT-D7-8."""
    monkeypatch.setenv("ADAS_SIM_BATCH_TEST_STUB", "hang")
    pipeline = _echo_pipeline(tmp_path)
    results = run_batch([_TINY], pipeline, test_stub_echo=("echo",), timeout_s=2.0)
    assert results[0].outcome == "timeout"


def test_recording_order_is_preserved_regardless_of_completion_order(tmp_path, monkeypatch):
    """The FIRST recording is made to hang (so it finishes LAST in wall-clock
    terms, since it alone pays the full timeout) while the other two
    complete quickly -- the returned list must still read back in the
    original order, not completion order."""
    pipeline = _echo_pipeline(tmp_path)
    first = tmp_path / "rec_a.mcap"
    second = tmp_path / "rec_b.mcap"
    third = tmp_path / "rec_c.mcap"
    for path in (first, second, third):
        path.write_bytes(_TINY.read_bytes())
    recordings = [first, second, third]

    monkeypatch.setenv("ADAS_SIM_BATCH_TEST_STUB_MAP", f"{first.stem}=hang")
    results = run_batch(recordings, pipeline, test_stub_echo=("echo",), jobs=3, timeout_s=2.0)

    assert [r.recording for r in results] == recordings
    assert results[0].outcome == "timeout"
    assert results[1].outcome == "ok"
    assert results[2].outcome == "ok"


def test_write_report_counts_every_outcome(tmp_path):
    results = [
        RecordingOutcome(recording=Path("a.mcap"), outcome="ok", duration_s=1.0, tick_count=10),
        RecordingOutcome(recording=Path("b.mcap"), outcome="crash", duration_s=0.5, error="exit code -11"),
        RecordingOutcome(recording=Path("c.mcap"), outcome="timeout", duration_s=5.0),
    ]
    report_path = tmp_path / "report.md"
    write_report(results, report_path)
    text = report_path.read_text(encoding="utf-8")
    assert "- ok: 1" in text
    assert "- crash: 1" in text
    assert "- timeout: 1" in text
    assert "- fail: 0" in text
    assert "a.mcap" in text and "b.mcap" in text and "c.mcap" in text
