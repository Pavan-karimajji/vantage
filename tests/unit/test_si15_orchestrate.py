# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-15 orchestrate` unit tests (`WP-23`) -- `UT-ORC-01`...`UT-ORC-22`,
`UT-ERR-06`. Real-`simengine`-backed tests (a genuine crash/hang batch run)
already live in `tests/unit/test_d7_batch.py`; this file covers the pure
logic new in `WP-23`: `verbs.py`, `progress.py`, `artifacts.py`,
`severity.py`, `reset.py`, `readerror.py`, `watchdog.py`, `limits.py`,
`reopen.py`, and `batch.py`'s own `reconcile`/resume/`sweep` additions."""

from __future__ import annotations

import ast
import json
import time
from pathlib import Path

import pytest
import yaml

from adas_sim.orchestrate import artifacts, limits, readerror, reset, severity, watchdog
from adas_sim.orchestrate.batch import RecordingOutcome, reconcile, run_batch, sweep_configs
from adas_sim.orchestrate.progress import CancelToken, ProgressSink
from adas_sim.orchestrate.reopen import open_on_bench
from adas_sim.orchestrate.verbs import VERBS, assert_dry_run_table_complete, verb_count


# --------------------------------------------------------------------------
# UT-ORC-01 / ANL-SW-39 -- cli/*.py holds no logic
# --------------------------------------------------------------------------

_CLI_DIR = Path(__file__).resolve().parents[2] / "src" / "adas_sim" / "cli"


def test_cli_dispatch_matches_published_verbs():
    """`ANL-SW-40`: `cli/__init__.py`'s own registered subparser names must
    equal `VERBS`'s own keys -- a verb in one and not the other fails."""
    source = (_CLI_DIR / "__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    registered: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_parser"
            and node.args and isinstance(node.args[0], ast.Constant)
        ):
            registered.add(node.args[0].value)
    assert registered == set(VERBS.keys())
    assert verb_count() == len(registered)


def test_every_cli_module_imports_only_stdlib_or_adas_sim():
    """`ANL-SW-39`'s own static check, run directly against the source
    (never executed): every `cli/*.py` module's top-level imports resolve
    to the standard library or `adas_sim` -- never a third-party package
    imported directly (a verb pulling in Qt/matplotlib/mcap goes through
    its own deferred import inside `run()`, which this AST walk still
    allows since it only inspects MODULE-LEVEL imports)."""
    import sys

    stdlib = set(sys.stdlib_module_names)
    offenders: dict[str, list[str]] = {}
    for path in _CLI_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:  # module level only
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name != "adas_sim" and name not in stdlib and name != "__future__":
                    offenders.setdefault(path.name, []).append(name)
    assert offenders == {}


# --------------------------------------------------------------------------
# UT-ORC-03 -- dry run
# --------------------------------------------------------------------------

def test_every_verb_has_a_dry_run_and_it_executes_nothing(tmp_path, capsys):
    assert_dry_run_table_complete()
    missing_recording = tmp_path / "does_not_exist.mcap"
    missing_pipeline = tmp_path / "does_not_exist.yaml"
    rc = VERBS["resim"].dry_run([str(missing_recording), "--pipeline", str(missing_pipeline)])
    assert rc == 0  # never touches the missing files -- would raise if it did
    out = capsys.readouterr().out
    assert "dry run" in out
    assert "sim resim" in out


def test_adding_a_verb_with_no_dry_run_fails_at_construction():
    from adas_sim.orchestrate.verbs import VerbEntry

    with pytest.raises(TypeError):
        VerbEntry(run=lambda argv=None: 0)  # type: ignore[call-arg]  -- dry_run omitted


# --------------------------------------------------------------------------
# orchestrate/run.py -- UT-ORC-06, ANL-SW-41
# --------------------------------------------------------------------------

_SRC_DIR = Path(__file__).resolve().parents[2] / "src" / "adas_sim"


def test_engine_bridge_run_engine_has_exactly_one_call_site():
    """`ANL-SW-41`: `engine.bridge.run_engine` is the true bottom of the
    stack -- the one place a `simengine` subprocess is actually launched.
    Every higher-level helper (`run_pipeline_via_engine`,
    `run_pipeline_merged_via_engine`, `orchestrate/run.py::invoke_engine`)
    funnels through it, so asserting exactly one CALL to `run_engine(` (as
    opposed to its own `def`) across the whole package is the real "one
    invocation shape" check -- counting callers of the higher-level
    wrappers would instead penalise having wrappers at all."""
    call_sites: list[str] = []
    for path in _SRC_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "run_engine(" in line and "def run_engine(" not in line:
                call_sites.append(f"{path}:{lineno}")
    assert len(call_sites) == 1, call_sites
    assert call_sites[0].startswith(str(_SRC_DIR / "engine" / "bridge.py"))


def test_resim_check_and_worker_all_call_invoke_engine_not_the_bridge_directly():
    """`ANL-SW-41`'s own resim-shaped-caller half: `cli/resim.py`,
    `check/runner.py` and `orchestrate/worker.py` each import
    `orchestrate.run.invoke_engine`, never `engine.bridge.
    run_pipeline_via_engine` directly."""
    for rel in ("cli/resim.py", "check/runner.py", "orchestrate/worker.py"):
        text = (_SRC_DIR / rel).read_text(encoding="utf-8")
        assert "invoke_engine" in text, rel
        assert "run_pipeline_via_engine(" not in text, rel  # a call, not a docstring mention


def test_record_run_resim_are_three_distinct_verbs_not_a_mode_flag():
    """`UT-ORC-02`/`SW-0233`: producing, producing-and-executing, and
    executing-an-existing-artifact are three separate `VERBS` entries with
    three separate module implementations -- never one verb with a flag."""
    assert VERBS["record"].run is not VERBS["run"].run
    assert VERBS["run"].run is not VERBS["resim"].run
    assert VERBS["record"].produces_executes == "produces"
    assert VERBS["run"].produces_executes == "produces_and_executes"
    assert VERBS["resim"].produces_executes == "executes"


def test_no_intra_run_thread_pool_only_batch_supervision(tmp_path):
    """`ANL-SW-62`/`SW-0368`: the only `threading`/`ThreadPoolExecutor` use
    in `orchestrate/**` is batch-level supervision (launching/polling
    separate subprocesses), never inside one run's own execution path
    (`engine/bridge.py`, `orchestrate/run.py::invoke_engine`)."""
    for rel in ("orchestrate/run.py", "engine/bridge.py"):
        text = (_SRC_DIR / rel).read_text(encoding="utf-8")
        assert "import threading" not in text, rel
        assert "ThreadPoolExecutor" not in text, rel


# --------------------------------------------------------------------------
# progress.py -- UT-ORC-04
# --------------------------------------------------------------------------

def test_progress_sink_reports_and_can_be_cancelled():
    seen: list[tuple[int, int]] = []
    messages: list[str] = []
    sink = ProgressSink(on_progress=lambda d, t: seen.append((d, t)), on_message=messages.append)
    sink.report(1, 10)
    sink.message("hello")
    assert seen == [(1, 10)]
    assert messages == ["hello"]
    assert not sink.cancelled
    sink.cancel.cancel()
    assert sink.cancelled


def test_cancel_token_default_state():
    token = CancelToken()
    assert not token.cancelled
    token.cancel()
    assert token.cancelled


# --------------------------------------------------------------------------
# artifacts.py -- UT-ORC-05, IT-17
# --------------------------------------------------------------------------

def test_run_dir_creates_declared_layout(tmp_path):
    directory = artifacts.run_dir(tmp_path, "run-abc123")
    assert directory == tmp_path / "run-abc123"
    for name in ("spec", "manifest", "exports", "logs", "checkpoints", "config"):
        assert (directory / name).is_dir()


def test_run_dir_is_idempotent_and_two_run_ids_never_collide(tmp_path):
    a = artifacts.run_dir(tmp_path, "run-a")
    (a / "logs" / "note.txt").write_text("hi", encoding="utf-8")
    a_again = artifacts.run_dir(tmp_path, "run-a")
    assert (a_again / "logs" / "note.txt").read_text(encoding="utf-8") == "hi"  # untouched, not recreated

    b = artifacts.run_dir(tmp_path, "run-b")
    assert a != b
    assert not (b / "logs" / "note.txt").exists()


def test_self_contained_directory_carries_config_bundle(tmp_path):
    directory = artifacts.run_dir(tmp_path, "run-c")
    ok, reasons = artifacts.is_self_contained(directory)
    assert ok, reasons

    bundle_dir = tmp_path / "bundle_src"
    bundle_dir.mkdir()
    (bundle_dir / "default.yaml").write_text("a: 1\n", encoding="utf-8")
    (bundle_dir / "bundle.sha256").write_text("deadbeef\n", encoding="utf-8")
    artifacts.embed_config_bundle(directory, bundle_dir)

    ok, reasons = artifacts.is_self_contained(directory)
    assert ok, reasons
    assert (directory / "config" / "default.yaml").exists()
    assert (directory / "config" / "bundle.sha256").exists()


def test_self_contained_flags_a_config_dir_with_no_bundle_hash(tmp_path):
    directory = artifacts.run_dir(tmp_path, "run-d")
    (directory / "config" / "stray.yaml").write_text("x: 1\n", encoding="utf-8")
    ok, reasons = artifacts.is_self_contained(directory)
    assert not ok
    assert any("bundle.sha256" in r for r in reasons)


# --------------------------------------------------------------------------
# severity.py -- UT-ERR-06
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["warning", "alert", "error", "exception"])
def test_each_severity_threshold_is_individually_demonstrable(name):
    threshold = severity.parse_exit_on(name)
    events = [severity.Severity.WARNING, severity.Severity.ALERT, severity.Severity.ERROR, severity.Severity.EXCEPTION]
    verdict = severity.evaluate(events, threshold)
    assert verdict.should_exit
    assert verdict.exit_code == 1
    assert verdict.triggered == threshold  # the FIRST event reaching it -- events are ascending here


def test_no_event_reaching_threshold_does_not_exit():
    verdict = severity.evaluate([severity.Severity.WARNING], severity.Severity.ERROR)
    assert not verdict.should_exit
    assert verdict.exit_code == 0
    assert verdict.triggered is None


def test_parse_exit_on_rejects_unknown_value():
    with pytest.raises(ValueError, match="not in"):
        severity.parse_exit_on("catastrophe")


def test_severity_gate_latches_on_first_trigger():
    gate = severity.SeverityGate(severity.Severity.ERROR)
    assert not gate.observe(severity.Severity.WARNING)
    assert gate.observe(severity.Severity.ERROR)
    assert gate.observe(severity.Severity.WARNING)  # stays triggered
    verdict = gate.verdict()
    assert verdict.triggered == severity.Severity.ERROR
    assert verdict.exit_code == 1


# --------------------------------------------------------------------------
# reset.py -- UT-ORC-17
# --------------------------------------------------------------------------

def test_default_reset_policy_is_reset_init_before_every_entry():
    assert reset.DEFAULT_RESET_POLICY.mode == reset.ResetMode.RESET_INIT
    assert reset.DEFAULT_RESET_POLICY.when == reset.ResetWhen.ENTRY


@pytest.mark.parametrize("index", [0, 1, 2, 5])
def test_default_policy_resets_before_every_entry_making_order_irrelevant(index):
    assert reset.should_reset_before(reset.DEFAULT_RESET_POLICY, index=index, is_first_in_section=False)


def test_none_mode_never_resets_proving_the_test_has_power():
    policy = reset.ResetPolicy(mode=reset.ResetMode.NONE, when=reset.ResetWhen.ENTRY)
    assert not reset.should_reset_before(policy, index=0, is_first_in_section=True)
    assert not reset.should_reset_before(policy, index=3, is_first_in_section=False)


def test_batch_timing_resets_only_at_index_zero():
    policy = reset.ResetPolicy(mode=reset.ResetMode.RESET, when=reset.ResetWhen.BATCH)
    assert reset.should_reset_before(policy, index=0, is_first_in_section=False)
    assert not reset.should_reset_before(policy, index=1, is_first_in_section=False)


def test_section_timing_resets_only_at_section_boundaries():
    policy = reset.ResetPolicy(mode=reset.ResetMode.RESET_INIT, when=reset.ResetWhen.SECTION)
    assert reset.should_reset_before(policy, index=0, is_first_in_section=True)
    assert not reset.should_reset_before(policy, index=1, is_first_in_section=False)
    assert reset.should_reset_before(policy, index=2, is_first_in_section=True)


# --------------------------------------------------------------------------
# readerror.py -- UT-ORC-18/19
# --------------------------------------------------------------------------

def test_read_error_is_a_closed_set_of_four():
    assert {e.value for e in readerror.ReadError} == {"stop", "skip_entry", "abort_batch", "skip_package"}


def test_retry_succeeds_within_bound():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("transient")
        return "ok"

    result, outcome = readerror.retry(flaky, bound_s=5.0, retry_interval_s=0.0)
    assert result == "ok"
    assert outcome.succeeded
    assert outcome.attempts == 3
    assert len(outcome.errors) == 2


def test_retry_is_bounded_and_gives_up():
    fake_now = {"t": 0.0}

    def clock():
        return fake_now["t"]

    def always_fails():
        fake_now["t"] += 1.0
        raise OSError("still broken")

    result, outcome = readerror.retry(always_fails, bound_s=2.5, retry_interval_s=0.0, clock=clock)
    assert result is None
    assert not outcome.succeeded
    assert outcome.attempts >= 1
    assert outcome.errors


# --------------------------------------------------------------------------
# watchdog.py -- UT-ORC-12/13
# --------------------------------------------------------------------------

def test_parse_threshold_accepts_bare_number_and_reports_assumed_unit():
    seconds, unit, explicit = watchdog.parse_threshold(30)
    assert seconds == 30.0
    assert unit == watchdog.WatchdogUnit.SECONDS
    assert not explicit


def test_parse_threshold_accepts_explicit_units():
    seconds, unit, explicit = watchdog.parse_threshold("1500ms")
    assert seconds == 1.5
    assert unit == watchdog.WatchdogUnit.MILLISECONDS
    assert explicit

    seconds, unit, explicit = watchdog.parse_threshold("30s")
    assert seconds == 30.0
    assert explicit


def test_processing_watchdog_fires_when_no_heartbeat_within_threshold():
    dog = watchdog.ProcessingWatchdog(threshold_s=5.0, poll_interval_s=1.0)
    dog.heartbeat(0.0)
    assert not dog.poll(4.0)
    assert dog.poll(6.0)
    assert dog.fired
    assert dog.fired_at == 6.0


def test_watchdog_fired_state_latches():
    dog = watchdog.ResponsivenessWatchdog(threshold_s=2.0, poll_interval_s=0.5)
    dog.heartbeat(0.0)
    assert dog.poll(3.0)
    dog.heartbeat(3.1)  # a late heartbeat after firing does not un-latch
    assert dog.poll(3.2)


def test_the_two_watchdogs_are_independent_one_fires_without_the_other():
    """`UT-ORC-13`'s own scenario: a run whose modules are all within their
    processing threshold (frequent per-tick heartbeats) but whose PROCESS
    has stopped responding (no responsiveness heartbeat at all) trips only
    the responsiveness watchdog."""
    processing = watchdog.ProcessingWatchdog(threshold_s=100.0, poll_interval_s=1.0)
    responsiveness = watchdog.ResponsivenessWatchdog(threshold_s=5.0, poll_interval_s=1.0)
    processing.heartbeat(0.0)
    responsiveness.heartbeat(0.0)

    # ticks keep completing (processing heartbeats), but nothing else signals life
    for t in (1.0, 2.0, 3.0, 4.0, 5.0, 6.0):
        processing.heartbeat(t)

    assert not processing.poll(6.0)
    assert responsiveness.poll(6.0)


# --------------------------------------------------------------------------
# limits.py -- UT-ORC-14
# --------------------------------------------------------------------------

def test_rss_bytes_of_current_process_is_a_positive_number_or_unknown():
    value = limits.rss_bytes_of_this_process = limits.rss_bytes
    import os

    rss = value(os.getpid())
    assert rss is None or rss > 0


def test_breach_reason_true_only_at_or_above_limit():
    limit = limits.MemoryLimit(limit_bytes=1000)
    assert not limits.breach_reason(999, limit)
    assert limits.breach_reason(1000, limit)
    assert limits.breach_reason(2000, limit)
    assert not limits.breach_reason(None, limit)  # unknown never breaches


# --------------------------------------------------------------------------
# reopen.py -- UT-ORC-11
# --------------------------------------------------------------------------

def test_open_on_bench_uses_last_tick_ns_when_known():
    outcome = RecordingOutcome(
        recording=Path("rec.mcap"), outcome="crash", duration_s=1.0, last_tick_ns=7_500_000_000,
    )
    recording, pipeline, at_s = open_on_bench(outcome, Path("pipeline.yaml"))
    assert recording == Path("rec.mcap")
    assert pipeline == Path("pipeline.yaml")
    assert at_s == pytest.approx(7.5)


def test_open_on_bench_falls_back_to_zero_when_tick_unknown():
    outcome = RecordingOutcome(recording=Path("rec.mcap"), outcome="crash", duration_s=1.0)
    _, _, at_s = open_on_bench(outcome, Path("pipeline.yaml"))
    assert at_s == 0.0


# --------------------------------------------------------------------------
# batch.py -- UT-ORC-10 (reconcile), UT-ORC-15 (resume), UT-ORC-16 (sweep)
# --------------------------------------------------------------------------

_TINY = Path(__file__).resolve().parent.parent / "fixtures" / "tiny.mcap"


def test_reconcile_rebuilds_aggregate_from_persisted_out_json(tmp_path):
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    (out_dir / "0000_a.json").write_text(
        json.dumps({"outcome": "ok", "tick_count": 20, "last_tick_ns": None}), encoding="utf-8",
    )
    (out_dir / "0001_b.json").write_text(
        json.dumps({"outcome": "fail", "error": "bad pipeline"}), encoding="utf-8",
    )
    recordings = [Path("a.mcap"), Path("b.mcap"), Path("c.mcap")]  # c has no out_json at all

    results = reconcile(out_dir, recordings)

    assert [r.outcome for r in results] == ["ok", "fail", "crash"]
    assert results[0].tick_count == 20
    assert results[1].error == "bad pipeline"
    assert "no readable out_json" in results[2].error


def test_resume_skips_a_completed_entry_and_reruns_a_never_finished_one(tmp_path):
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    # entry 0 already completed successfully -- resume must not relaunch it.
    (out_dir / "0000_a.json").write_text(json.dumps({"outcome": "ok", "tick_count": 42}), encoding="utf-8")
    missing_pipeline = tmp_path / "does_not_exist.yaml"

    results = run_batch([Path("a.mcap")], missing_pipeline, out_dir=out_dir, resume=True)

    assert results[0].outcome == "ok"
    assert results[0].tick_count == 42
    # confirms nothing was relaunched: a real launch against a missing
    # pipeline would report "fail" (see test_a_bad_pipeline_reports_fail_not_crash
    # in test_d7_batch.py), not the pre-recorded "ok".


def test_resume_reruns_an_entry_with_no_persisted_result(tmp_path):
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    missing_pipeline = tmp_path / "does_not_exist.yaml"

    results = run_batch([_TINY], missing_pipeline, out_dir=out_dir, resume=True)

    assert results[0].outcome == "fail"  # really launched -- a missing pipeline is a clean "fail"
    assert (out_dir / "0000_tiny.json").is_file()


def test_sweep_configs_produce_one_bundle_per_value_differing_only_in_the_swept_field(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "default.yaml").write_text(
        "aeb:\n  AEB_TTC_PRE_WARNING_THRESHOLD_S: 1.0\n  AEB_MIN_SPEED_MPS: 1.0\n", encoding="utf-8",
    )

    resolved = sweep_configs(base, "aeb.AEB_TTC_PRE_WARNING_THRESHOLD_S", [1.1, 1.2, 1.3], project="base")

    assert set(resolved.keys()) == {1.1, 1.2, 1.3}
    seen_values = set()
    try:
        for value, r in resolved.items():
            data = yaml.safe_load((r.effective_config / "default.yaml").read_text(encoding="utf-8"))
            assert data["aeb"]["AEB_TTC_PRE_WARNING_THRESHOLD_S"] == value
            assert data["aeb"]["AEB_MIN_SPEED_MPS"] == 1.0  # the one field NOT swept, unchanged
            seen_values.add(data["aeb"]["AEB_TTC_PRE_WARNING_THRESHOLD_S"])
    finally:
        import shutil
        for r in resolved.values():
            if r.scratch_dir is not None:
                shutil.rmtree(r.scratch_dir, ignore_errors=True)
    assert seen_values == {1.1, 1.2, 1.3}


# --------------------------------------------------------------------------
# batch.py -- IMP-0222 (SW-0222), landed as a byproduct of this package's
# own orchestrate/run.py::invoke_engine wiring (WP-22 left this row [~]
# with exactly this follow-on named as its own closing condition).
# --------------------------------------------------------------------------

def test_a_crashed_and_a_timed_out_entry_each_get_a_manifest_written_from_outside_the_worker(tmp_path, monkeypatch):
    """`SW-0222`'s own hard half: "a crashed run's manifest is written from
    outside the worker" -- neither a crash nor a hang ever reaches the
    worker's own `finally`, so `batch.py` (the parent, classifying from
    exit code / timer) must be the one writing it."""
    from adas_sim.runspec.manifest import RUN_MANIFEST_FILENAME

    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    pipeline = tmp_path / "p.yaml"
    pipeline.write_text("version: 1\nname: t\nstages: []\n", encoding="utf-8")

    monkeypatch.setenv("ADAS_SIM_BATCH_TEST_STUB", "crash")
    run_batch([_TINY], pipeline, out_dir=out_dir, timeout_s=15.0)
    manifest_path = out_dir / "manifest" / "0000_tiny" / RUN_MANIFEST_FILENAME
    assert manifest_path.is_file()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["outcome"] == "crashed"

    monkeypatch.setenv("ADAS_SIM_BATCH_TEST_STUB", "hang")
    run_batch([_TINY], pipeline, out_dir=out_dir, timeout_s=1.0)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["outcome"] == "timeout"


def test_a_clean_fail_also_gets_a_manifest(tmp_path):
    from adas_sim.runspec.manifest import RUN_MANIFEST_FILENAME

    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    missing_pipeline = tmp_path / "does_not_exist.yaml"

    run_batch([_TINY], missing_pipeline, out_dir=out_dir)

    manifest_path = out_dir / "manifest" / "0000_tiny" / RUN_MANIFEST_FILENAME
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["outcome"] == "failed"


def test_memory_limit_is_reported_distinctly_from_a_plain_fail(tmp_path):
    """`SW-0248`'s own distinctness Accept clause, exercised without a real
    memory hog: a limit of 1 byte is breached by any real process
    immediately, proving the plumbing reports `limit_breach="memory"`
    rather than a bare `fail`."""
    missing_pipeline = tmp_path / "does_not_exist.yaml"
    results = run_batch([_TINY], missing_pipeline, memory_limit_mb=0.000001, timeout_s=15.0)
    assert results[0].limit_breach == "memory"
    assert results[0].outcome in ("fail", "crash", "timeout")


def test_a_pre_cancelled_token_terminates_the_job_and_is_reported_distinctly(tmp_path):
    """`IMP-0235`: `run_batch` enters the polling path (`_launch_worker_polled`)
    the instant a `CancelToken` is supplied, even one already cancelled
    before launch -- the very first poll tick sees `cancel.cancelled` and
    terminates the subprocess, reported `cancelled=True` rather than a bare
    `fail` (same distinguish-by-field pattern as `limit_breach`)."""
    missing_pipeline = tmp_path / "does_not_exist.yaml"
    cancel = CancelToken()
    cancel.cancel()
    results = run_batch([_TINY], missing_pipeline, cancel=cancel, timeout_s=15.0)
    assert results[0].cancelled is True
    assert results[0].outcome == "fail"


def test_a_cancelled_job_s_manifest_carries_cancelled_true(tmp_path):
    """`IMP-0235`'s own manifest half: `RecordingOutcome.cancelled` reaches
    the on-disk `run_manifest.json` through `_write_outcome_manifest` ->
    `build_manifest(cancelled=...)` -- the same fact this test's sibling
    above checks at the batch-report layer, checked here at the manifest
    layer `IMP-0235`'s own "Closed by" named as the remaining gap."""
    from adas_sim.runspec.manifest import RUN_MANIFEST_FILENAME

    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    missing_pipeline = tmp_path / "does_not_exist.yaml"
    cancel = CancelToken()
    cancel.cancel()

    run_batch([_TINY], missing_pipeline, out_dir=out_dir, cancel=cancel, timeout_s=15.0)

    manifest_path = out_dir / "manifest" / "0000_tiny" / RUN_MANIFEST_FILENAME
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["cancelled"] is True
    assert data["outcome"] == "failed"


def test_a_zero_threshold_watchdog_terminates_the_job_and_names_which_one(tmp_path):
    """`IMP-0246`/`IMP-0247`: a `WatchdogThresholds` with an effectively-zero
    processing threshold fires on the first poll tick (the subprocess has
    not completed a cycle yet), terminating the job and reporting
    `watchdog="processing"` -- proves the poll loop actually drives the
    watchdog from a real subprocess, not just the pure clock-injected unit
    tests above."""
    missing_pipeline = tmp_path / "does_not_exist.yaml"
    thresholds = watchdog.WatchdogThresholds(processing_s=0.0, responsiveness_s=100.0, poll_interval_s=0.05)
    results = run_batch([_TINY], missing_pipeline, watchdogs=thresholds, timeout_s=15.0)
    assert results[0].watchdog == "processing"
    assert results[0].outcome == "fail"


def test_a_progress_sink_does_not_change_outcome_for_a_run_with_nothing_to_report(tmp_path):
    """`IMP-0235`: supplying a `ProgressSink` alone (no memory limit, no
    cancel, no watchdogs) still routes `_launch_worker` through the polling
    path (`_launch_worker_polled`) instead of the untouched `subprocess.run`
    fast path -- this is the plumbing smoke test that the switch is
    transparent when nothing actually fires. `on_progress` is never called
    here (a missing pipeline never advances a checkpoint tick), so this
    intentionally does not assert on `calls` -- a real subprocess's own
    tick-by-tick reporting is exercised live in Bench/CI against a built
    `simengine`, out of reach of this environment's own test double.
    Deliberately tolerant on the exact outcome, same as
    `test_memory_limit_is_reported_distinctly_from_a_plain_fail` above --
    a missing pipeline's own `fail`-vs-`crash` classification is
    `test_a_bad_pipeline_reports_fail_not_crash`'s concern, not this test's;
    this one only proves the polling path does not raise."""
    missing_pipeline = tmp_path / "does_not_exist.yaml"
    sink = ProgressSink()
    results = run_batch([_TINY], missing_pipeline, progress=sink, timeout_s=15.0)
    assert results[0].outcome in ("fail", "crash")
