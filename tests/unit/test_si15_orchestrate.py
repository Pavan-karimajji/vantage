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
from adas_sim.orchestrate.reset import ResetMode, ResetPolicy, ResetWhen
from adas_sim.orchestrate.batch import RecordingOutcome, reconcile, run_batch, sweep, sweep_configs
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


def test_run_batch_probes_a_shared_recording_index_cache_once_per_unique_path(tmp_path, monkeypatch):
    """`IMP-0254`: `recording_index_cache`, when given, is populated once per
    UNIQUE recording path before any job dispatches -- a duplicate entry in
    `recordings` is probed once, not once per occurrence."""
    import adas_sim.orchestrate.batch as batch_module

    calls: list[Path] = []
    real = batch_module.describe_recording

    def _counting(path):
        calls.append(path)
        return real(path)

    monkeypatch.setattr(batch_module, "describe_recording", _counting)

    missing_pipeline = tmp_path / "does_not_exist.yaml"
    cache: dict[Path, object] = {}
    run_batch([_TINY, _TINY], missing_pipeline, recording_index_cache=cache, timeout_s=15.0)

    assert calls == [_TINY]
    assert _TINY in cache


def test_sweep_shares_one_recording_index_cache_across_every_swept_value(tmp_path, monkeypatch):
    """`IMP-0254`'s own named "amortize across workers" story: `sweep` re-runs
    the SAME recording list once per swept value -- without a shared cache
    that would re-probe every recording once per value; with one, each
    unique recording is probed exactly once across the whole sweep."""
    import adas_sim.orchestrate.batch as batch_module

    calls: list[Path] = []
    real = batch_module.describe_recording

    def _counting(path):
        calls.append(path)
        return real(path)

    monkeypatch.setattr(batch_module, "describe_recording", _counting)

    base = tmp_path / "base"
    base.mkdir()
    (base / "default.yaml").write_text(
        "aeb:\n  AEB_TTC_PRE_WARNING_THRESHOLD_S: 1.0\n  AEB_MIN_SPEED_MPS: 1.0\n", encoding="utf-8",
    )
    missing_pipeline = tmp_path / "does_not_exist.yaml"

    sweep(
        [_TINY], missing_pipeline, "aeb.AEB_TTC_PRE_WARNING_THRESHOLD_S", [1.1, 1.2, 1.3],
        base_config=base, project="base", timeout_s=15.0,
    )

    assert calls == [_TINY]


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


def _missing_library_pipeline(tmp_path: Path, filename: str = "missing_lib.yaml") -> Path:
    """Deterministic `EnvironmentError_` trigger (kind `"environment"`,
    `IMP-0128`'s own `ERROR` mapping) -- `impl: dll:` naming a stem no
    directory can resolve raises from `resolve_library` itself, with no
    real component build needed and no dependence on this environment's
    own `simengine`/`echo_stub` state."""
    path = tmp_path / filename
    path.write_text(
        "version: 1\nname: missing_lib_test\nstages:\n"
        "  - name: sut\n    mode: simulate\n    impl: \"dll:no_such_stem_anywhere\"\n    inputs: {}\n",
        encoding="utf-8",
    )
    return path


def test_a_missing_library_reports_environment_error_kind(tmp_path):
    """`IMP-0128`: `orchestrate/worker.py`'s own caught `SimError.kind`
    reaches `RecordingOutcome.error_kind` -- a real trigger (`resolve_library`
    raising `EnvironmentError_`), not a mocked one."""
    pipeline = _missing_library_pipeline(tmp_path)
    results = run_batch([_TINY], pipeline, timeout_s=15.0)
    assert results[0].error_kind == "environment"
    assert results[0].outcome == "fail"


def test_exit_on_stops_a_still_running_job_when_one_entry_s_severity_meets_the_threshold(tmp_path):
    """`IMP-0128`: `exit_on` reaches beyond the failing entry the same way
    `on_read_error="abort_batch"` does -- reusing `IMP-0235`'s `CancelToken`
    machinery (auto-created here since the caller supplied none), the
    failing entry's own `error_kind` (`"environment"` -> `Severity.ERROR`)
    meets `exit_on=Severity.ERROR` and cancels the shared token, which the
    second entry's own poll loop picks up and terminates on."""
    pipeline = _missing_library_pipeline(tmp_path)
    results = run_batch(
        [_TINY, _TINY], pipeline, exit_on=severity.Severity.ERROR, jobs=1, timeout_s=15.0,
    )
    assert results[0].error_kind == "environment"
    assert results[1].cancelled is True


def test_exit_on_does_not_fire_below_its_own_threshold(tmp_path):
    """The mirror case: `exit_on=Severity.EXCEPTION` is ABOVE `"environment"`'s
    own `ERROR` mapping, so an environment failure never triggers it -- the
    second entry runs for real (never cancelled)."""
    pipeline = _missing_library_pipeline(tmp_path)
    results = run_batch(
        [_TINY, _TINY], pipeline, exit_on=severity.Severity.EXCEPTION, jobs=1, timeout_s=15.0,
    )
    assert results[0].error_kind == "environment"
    assert results[1].cancelled is False


def test_a_missing_pipeline_file_reports_internal_error_kind(tmp_path):
    """`IMP-0128`: an uncaught non-`SimError` exception (here, `Pipeline.load`
    reading a pipeline file that does not exist) is tagged `"internal"` --
    `InternalError`'s own docstring: "anything uncaught is this, by
    definition" -- even though nothing here constructs that class."""
    missing_pipeline = tmp_path / "does_not_exist.yaml"
    results = run_batch([_TINY], missing_pipeline, timeout_s=15.0)
    assert results[0].error_kind == "internal"


def test_the_manifest_carries_error_kind(tmp_path):
    from adas_sim.runspec.manifest import RUN_MANIFEST_FILENAME

    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    pipeline = _missing_library_pipeline(tmp_path)

    run_batch([_TINY], pipeline, out_dir=out_dir, timeout_s=15.0)

    manifest_path = out_dir / "manifest" / "0000_tiny" / RUN_MANIFEST_FILENAME
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["error_kind"] == "environment"


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


def _corrupted_mcap(tmp_path: Path) -> Path:
    """A truncated copy of `_TINY` -- opens but fails to parse
    (`McapReader.__init__` raises `OSError` on the truncated stream),
    the genuine damaged-recording fixture `IMP-0252`/`IMP-0253`'s own
    doc row named as their missing piece, built in `tmp_path` rather than
    checked in."""
    corrupted = tmp_path / "corrupted.mcap"
    corrupted.write_bytes(_TINY.read_bytes()[:20])
    return corrupted


def test_a_damaged_recording_is_retried_then_reported_as_a_read_error(tmp_path):
    """`IMP-0252`/`IMP-0253`: the pre-flight read in `orchestrate/worker.py`
    (real Python-side, before `Pipeline.load`) retries within
    `read_retry_bound_s`, then reports `read_error`/`read_retry_attempts`
    -- a real damaged-file test, not just `readerror.py`'s own
    clock-injected unit tests."""
    corrupted = _corrupted_mcap(tmp_path)
    missing_pipeline = tmp_path / "does_not_exist.yaml"

    results = run_batch(
        [corrupted], missing_pipeline, on_read_error="skip_entry", read_retry_bound_s=0.3, timeout_s=15.0,
    )

    assert results[0].outcome == "fail"
    assert results[0].read_error == "skip_entry"
    assert results[0].read_retry_attempts >= 1
    assert "read error" in results[0].error


def test_stop_refuses_the_whole_batch_before_launching_anything(tmp_path):
    """`IMP-0252`: `on_read_error="stop"` pre-flights every recording BEFORE
    any job dispatches -- a damaged recording anywhere in the list raises,
    and nothing is launched (proven by a second, perfectly valid recording
    never getting an out_json written)."""
    corrupted = _corrupted_mcap(tmp_path)
    missing_pipeline = tmp_path / "does_not_exist.yaml"
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()

    with pytest.raises(RuntimeError, match="on-read-error=stop"):
        run_batch([corrupted, _TINY], missing_pipeline, on_read_error="stop", out_dir=out_dir, timeout_s=15.0)

    assert list(out_dir.iterdir()) == []  # nothing dispatched, not even the valid entry


def test_abort_batch_cancels_a_still_running_job_when_one_entry_s_read_fails(tmp_path):
    """`IMP-0252`: `on_read_error="abort_batch"` reaches BEYOND the failing
    entry -- reusing `IMP-0235`'s own `CancelToken` machinery (auto-created
    here since the caller supplied none), the failing entry's own
    `_launch_worker` cancels the shared token, which the still-running/
    not-yet-started entry's own poll loop picks up and terminates on,
    reported `cancelled=True` -- distinct from that entry ever getting a
    chance to run for real."""
    corrupted = _corrupted_mcap(tmp_path)
    missing_pipeline = tmp_path / "does_not_exist.yaml"

    results = run_batch(
        [corrupted, _TINY], missing_pipeline, on_read_error="abort_batch", jobs=1, timeout_s=15.0,
    )

    assert results[0].read_error == "abort_batch"
    assert results[1].cancelled is True


def _multi_chunk_mcap_one_corrupted(tmp_path: Path) -> Path:
    """A real multi-chunk mcap file with exactly one chunk's bytes flipped
    -- `IMP-0252`'s own "one damaged package within an otherwise-good
    recording" fixture (decided 2026-08-25: a "package" is an mcap chunk),
    built directly here rather than checked in, same discipline
    `_corrupted_mcap` above uses for whole-file damage."""
    from mcap.writer import Writer as RawMcapWriter

    path = tmp_path / "one_corrupt.mcap"
    with path.open("wb") as f:
        raw = RawMcapWriter(f, chunk_size=64)
        raw.start(profile="", library="test")
        schema_id = raw.register_schema(name="adas_sim.test.VehDyn", encoding="", data=b"")
        channel_id = raw.register_channel(topic="/source/veh_dyn", message_encoding="protobuf", schema_id=schema_id)
        for i in range(40):
            raw.add_message(channel_id=channel_id, log_time=i, data=bytes([i % 256]) * 16, publish_time=i)
        raw.finish()

    from adas_sim.io.mcap import McapReader

    reader = McapReader(path)
    chunk_indexes = reader._reader.get_summary().chunk_indexes  # test-only reach-in, same as test_a4_mcap.py
    assert len(chunk_indexes) > 1  # the fixture's own precondition: genuinely multi-chunk
    target = chunk_indexes[0]
    reader.close()

    with path.open("r+b") as f:
        victim_offset = target.chunk_start_offset + target.chunk_length - 5
        f.seek(victim_offset)
        byte = f.read(1)
        f.seek(victim_offset)
        f.write(bytes([byte[0] ^ 0xFF]))
    return path


def test_probe_recording_skip_package_counts_and_continues_past_one_damaged_chunk(tmp_path):
    """`IMP-0252`/`IMP-0253`'s own stated residual, closed: `readerror.
    probe_recording` under `ReadError.SKIP_PACKAGE` finds and skips exactly
    the one damaged chunk in an otherwise-good multi-chunk recording (never
    reachable through `topics()` alone, `io/mcap.py::McapReader.
    check_faults`'s own docstring) and reports success -- distinct from
    `skip_entry`'s whole-file-damage behaviour on the SAME fixture shape,
    which this test also proves by contrast."""
    damaged = _multi_chunk_mcap_one_corrupted(tmp_path)

    skipped_packages, outcome = readerror.probe_recording(damaged, on_read_error="skip_package", bound_s=1.0)
    assert outcome.succeeded is True
    assert skipped_packages == 1

    # Contrast: a policy other than skip_package never pays for the chunk
    # scan, so the very same damaged file reports zero and still succeeds
    # -- topics() alone cannot see the corrupted chunk (SW-0252's own
    # "package" concept simply is not checked under that policy).
    skipped_packages_other_policy, other_outcome = readerror.probe_recording(
        damaged, on_read_error="skip_entry", bound_s=1.0,
    )
    assert other_outcome.succeeded is True
    assert skipped_packages_other_policy == 0


def test_probe_recording_skip_package_fails_when_every_chunk_is_damaged(tmp_path):
    """`IMP-0252`: when nothing survives, there is nothing left to
    skip-and-continue -- that is whole-file damage, reported through the
    same retry/fail path every other policy uses, never silently treated
    as "zero packages skipped, run proceeds."."""
    from mcap.writer import Writer as RawMcapWriter

    path = tmp_path / "totally_corrupt.mcap"
    with path.open("wb") as f:
        raw = RawMcapWriter(f, chunk_size=1024 * 1024)
        raw.start(profile="", library="test")
        schema_id = raw.register_schema(name="adas_sim.test.VehDyn", encoding="", data=b"")
        channel_id = raw.register_channel(topic="/source/veh_dyn", message_encoding="protobuf", schema_id=schema_id)
        raw.add_message(channel_id=channel_id, log_time=0, data=b"\x00" * 16, publish_time=0)
        raw.finish()

    from adas_sim.io.mcap import McapReader

    reader = McapReader(path)
    (target,) = reader._reader.get_summary().chunk_indexes  # the one and only chunk
    reader.close()
    with path.open("r+b") as f:
        victim_offset = target.chunk_start_offset + target.chunk_length - 5
        f.seek(victim_offset)
        byte = f.read(1)
        f.seek(victim_offset)
        f.write(bytes([byte[0] ^ 0xFF]))

    skipped_packages, outcome = readerror.probe_recording(path, on_read_error="skip_package", bound_s=0.3)
    assert outcome.succeeded is False
    assert skipped_packages == 0


def test_should_reset_before_is_called_once_per_entry_with_the_real_index(tmp_path, monkeypatch):
    """`IMP-0251`: `run_batch`'s own per-entry lifecycle now calls
    `should_reset_before` for real -- a spy proves it fires once per entry
    with the entry's own index, not just that the pure decision function
    is unit-tested in isolation (`readerror.py`'s own tests above)."""
    import adas_sim.orchestrate.batch as batch_module

    calls: list[tuple[int, bool]] = []
    real = batch_module.should_reset_before

    def _spy(policy, *, index, is_first_in_section):
        calls.append((index, is_first_in_section))
        return real(policy, index=index, is_first_in_section=is_first_in_section)

    monkeypatch.setattr(batch_module, "should_reset_before", _spy)

    missing_pipeline = tmp_path / "does_not_exist.yaml"
    run_batch([_TINY, _TINY, _TINY], missing_pipeline, timeout_s=15.0)

    assert [c[0] for c in calls] == [0, 1, 2]


def test_the_manifest_carries_the_reset_policy_not_the_trivial_decision(tmp_path):
    """`IMP-0251`'s own manifest half: `reset_mode`/`reset_when` reach the
    on-disk manifest as the POLICY this run was configured with -- not the
    per-entry decision, which is trivially always-true under
    `orchestrate/batch.py`'s fresh-subprocess-per-recording isolation and
    would misrepresent what a `ResetMode.NONE`-configured run actually did."""
    from adas_sim.runspec.manifest import RUN_MANIFEST_FILENAME

    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    missing_pipeline = tmp_path / "does_not_exist.yaml"
    policy = ResetPolicy(mode=ResetMode.NONE, when=ResetWhen.SECTION)

    run_batch([_TINY], missing_pipeline, out_dir=out_dir, reset_policy=policy, timeout_s=15.0)

    manifest_path = out_dir / "manifest" / "0000_tiny" / RUN_MANIFEST_FILENAME
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["reset_mode"] == "none"
    assert data["reset_when"] == "section"


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
