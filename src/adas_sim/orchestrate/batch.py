# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim batch`'s engine (`S-D7`, `R-SIM-19`); `cli/batch.py` carries no logic (`GT-9`).

`run_batch` launches **one fresh subprocess per recording** via
`batch_worker.py` -- never a reused worker, because a segfault in recording 3
must not corrupt recording 4 -- and classifies each into the closed,
never-merged outcomes `R-SIM-19` requires:

- **ok** -- the worker reported success.
- **fail** -- the worker reported a clean, expected failure it caught and
  reported before exiting.
- **crash** -- `--out-json` is missing or unreadable **and** the process
  exited abnormally. Classified from the outside, never from a value a dying
  process claims about itself: a real segfault inside a library never reaches
  the worker's own reporting code.
- **timeout** -- `subprocess.run` raised `TimeoutExpired`.

`-j N` bounds how many subprocesses run concurrently; the concurrency is in
the supervision, not in reusing an interpreter. Isolation is unchanged: still
one subprocess per recording, always.
"""

from __future__ import annotations

import functools
import glob
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from adas_sim.orchestrate import limits as _limits
from adas_sim.orchestrate import watchdog as _watchdog
from adas_sim.orchestrate.progress import CancelToken, ProgressSink
from adas_sim.runspec.manifest import ResolvedRunConfig, build_manifest, resolve_swept_config, write_manifest

#: `RecordingOutcome.outcome` -> `RunManifest.outcome` (`runspec/manifest.py`'s
#: own closed vocabulary, `"completed"|"failed"|"crashed"|"timeout"`) --
#: `IMP-0222`'s own "written from OUTSIDE the worker" half: a crash/timeout
#: is classified by THIS module (`_classify`, from process exit code/timer),
#: never by the worker's own `finally` (which a real crash never reaches).
_MANIFEST_OUTCOME_OF = {"ok": "completed", "fail": "failed", "crash": "crashed", "timeout": "timeout"}

#: The closed outcome vocabulary (R-SIM-19: "never merged"). Kept as a tuple,
#: not an enum -- RecordingOutcome.outcome is compared/formatted as a plain
#: string throughout this module and its report, same as Mode/RecordVerb-
#: adjacent code elsewhere favours where no verb-specific behaviour hangs
#: off the type itself.
OUTCOMES = ("ok", "fail", "crash", "timeout")

#: Tail of captured stderr kept per recording -- enough for `ST-D7-6`'s own
#: "reproduce it interactively" need (the recording/pipeline/tick/run_id do
#: the real reproduction; this is a first-glance diagnostic only) without a
#: multi-megabyte report from one runaway recording.
_STDERR_EXCERPT_BYTES = 4000


@dataclass(frozen=True, slots=True)
class RecordingOutcome:
    recording: Path
    outcome: str  # one of OUTCOMES
    duration_s: float
    tick_count: int | None = None
    last_tick_ns: int | None = None
    error: str = ""
    stderr_excerpt: str = ""
    #: `SW-0248`: `""` (no breach), `"memory"` -- never a fifth `outcome`
    #: value (R-SIM-19's vocabulary stays exactly four); a memory breach
    #: still reports `outcome="fail"`, distinguished here instead.
    limit_breach: str = ""
    #: `SW-0235`: set when a caller-supplied `CancelToken` was cancelled
    #: while this recording's subprocess was in flight -- same "fail" outcome,
    #: same distinguish-by-field pattern `limit_breach` already established,
    #: never a fifth `outcome` value.
    cancelled: bool = False
    #: `SW-0246`/`SW-0247`: `""` (no watchdog fired), `"processing"` or
    #: `"responsiveness"` -- which of the two independent watchdogs killed
    #: this job. Same pattern as `limit_breach`/`cancelled`.
    watchdog: str = ""


def expand_recordings(args: Sequence[str]) -> list[Path]:
    """Each positional CLI arg is a literal path, a glob pattern, or a
    newline-separated list file (`sim_resim_and_recording.md`'s own
    `<recordings...|glob|list.txt>` shape). A list file's blank lines and
    `#`-prefixed comment lines are skipped; every other line is one path,
    relative to the CURRENT directory (not the list file's own location --
    matching how a shell-expanded glob argument would also resolve)."""
    result: list[Path] = []
    for arg in args:
        path = Path(arg)
        if path.suffix == ".txt" and path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    result.append(Path(stripped))
        elif any(ch in arg for ch in "*?["):
            result.extend(sorted(Path(p) for p in glob.glob(arg)))
        else:
            result.append(path)
    return result


def read_checkpoint_tick(checkpoint_json: Path) -> tuple[int | None, int | None]:
    """`(tick_count, last_tick_ns)` from `simengine`'s own real `progress.json`
    (`SW-0119`, `src/simcore/runner/checkpoint.cpp::Checkpoint::Write`), or
    `(None, None)` if it was never written or is unreadable -- a crashing
    process can leave no checkpoint at all (it died before the first cycle
    completed) or, in principle, a torn one; either way this reports
    `unknown` rather than a guessed value (`R-SIM-25`/`NR-SIM-4`). `simengine`
    writes this file via a temp-then-rename, so a fully-written-but-stale
    checkpoint (from a PREVIOUS cycle) is the only failure mode this needs
    to tolerate, and `json.loads` alone already handles that -- it is never
    torn. Field names (`last_completed_tick_index`/`last_completed_log_time_ns`)
    are the C++ writer's own, not this module's choosing -- shared with
    `orchestrate/worker.py`, which reads the exact same file for its own
    `ok`/`fail` result."""
    if not checkpoint_json.is_file():
        return None, None
    try:
        data = json.loads(checkpoint_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    return data.get("last_completed_tick_index"), data.get("last_completed_log_time_ns")


def _classify(
    recording: Path, proc: subprocess.CompletedProcess[str] | None, out_json: Path, checkpoint_json: Path,
    duration_s: float, *, timed_out: bool, timeout_stderr: str,
) -> RecordingOutcome:
    if timed_out:
        tick_count, last_tick_ns = read_checkpoint_tick(checkpoint_json)
        return RecordingOutcome(
            recording=recording, outcome="timeout", duration_s=duration_s,
            tick_count=tick_count, last_tick_ns=last_tick_ns,
            stderr_excerpt=timeout_stderr[-_STDERR_EXCERPT_BYTES:],
        )

    assert proc is not None  # only None when timed_out (mypy-style local invariant, not a runtime guard)
    result: dict[str, object] | None = None
    if out_json.is_file():
        try:
            result = json.loads(out_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            result = None

    if result is not None and result.get("outcome") == "ok":
        return RecordingOutcome(
            recording=recording, outcome="ok", duration_s=duration_s,
            tick_count=result.get("tick_count"), last_tick_ns=result.get("last_tick_ns"),  # type: ignore[arg-type]
        )
    if result is not None and result.get("outcome") == "fail":
        return RecordingOutcome(
            recording=recording, outcome="fail", duration_s=duration_s,
            tick_count=result.get("tick_count"), last_tick_ns=result.get("last_tick_ns"),  # type: ignore[arg-type]
            error=str(result.get("error", "")), stderr_excerpt=proc.stderr[-_STDERR_EXCERPT_BYTES:],
        )

    # No readable, self-reported outcome: the process died before it could
    # write one. That is exactly what a crash looks like from the outside
    # (R-SIM-19) -- never inferred from anything the process itself claimed.
    # The checkpoint file is the one thing that CAN survive this death
    # (UT-D7-7) -- it is written by simengine itself, one process further
    # in, read here by the parent regardless of which of the two died.
    tick_count, last_tick_ns = read_checkpoint_tick(checkpoint_json)
    return RecordingOutcome(
        recording=recording, outcome="crash", duration_s=duration_s,
        tick_count=tick_count, last_tick_ns=last_tick_ns,
        error=f"exit code {proc.returncode}", stderr_excerpt=proc.stderr[-_STDERR_EXCERPT_BYTES:],
    )


def _entry_paths(out_dir: Path, index: int, recording: Path) -> tuple[Path, Path]:
    """Deterministic per-entry filenames (`{index:04d}_{stem}`), unlike the
    random `uuid4` suffix a one-shot temp-dir run used -- `SW-0249`'s resume
    needs to find yesterday's own `out_json` for entry N without keeping a
    separate ledger, and a fresh `uuid4` per call would make that
    unrecoverable across process restarts."""
    stem = f"{index:04d}_{recording.stem}"
    return out_dir / f"{stem}.json", out_dir / f"{stem}.checkpoint.json"


def _write_outcome_manifest(out_dir: Path, index: int, recording: Path, pipeline_path: Path, outcome: RecordingOutcome) -> None:
    """`IMP-0222`/`SW-0222`: a standalone `run_manifest.json` written for
    EVERY entry, including a `crash`/`timeout` this module classified from
    the outside (`_classify`) -- never only for `ok`. `last_completed_cycle`
    is `outcome.tick_count` when the worker's own result or `simengine`'s
    real `progress.json` (`SW-0119`, closed) reported one, else `-1` -- a
    run whose engine never reached a completed cycle (`Pipeline.load`
    failed, or a crash before cycle 1) genuinely has none, honest rather
    than a guess. `run_kind="resim"`: a batch
    entry executes an existing recording exactly like `sim resim` does
    (`SW-0233`), and `"batch"` is not itself in the manifest schema's own
    closed `run_kind` enum."""
    manifest = build_manifest(
        pipeline_path=pipeline_path, run_kind="resim", source_kind="mcap", recording_path=recording,
        outcome=_MANIFEST_OUTCOME_OF[outcome.outcome],
        last_completed_cycle=outcome.tick_count if outcome.tick_count is not None else -1,
        cancelled=outcome.cancelled,
    )
    write_manifest(manifest, out_dir / "manifest" / f"{index:04d}_{recording.stem}")


def _load_completed(out_json: Path, recording: Path) -> RecordingOutcome | None:
    """`SW-0249`: a run is "completed" when the WORKER itself wrote a
    terminal result (`ok`/`fail`) -- never when the parent merely
    remembers launching it. `crash`/`timeout` leave no readable `out_json`
    by construction (`_classify`'s own reasoning), so they are correctly
    NOT recognized as completed here and are re-executed on resume, which
    is the right behaviour for a run nobody ever saw finish."""
    if not out_json.is_file():
        return None
    try:
        data = json.loads(out_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    outcome = data.get("outcome")
    if outcome not in ("ok", "fail"):
        return None
    return RecordingOutcome(
        recording=recording, outcome=outcome, duration_s=0.0,
        tick_count=data.get("tick_count"), last_tick_ns=data.get("last_tick_ns"),
        error=str(data.get("error", "")),
    )


def _launch_worker(
    entry: tuple[int, Path], *, pipeline_path: Path, search: tuple[Path, ...], config: Path | None, timeout_s: float,
    test_stub_echo: tuple[str, ...], out_dir: Path, resume: bool, memory_limit_mb: float | None,
    progress: ProgressSink | None = None, cancel: CancelToken | None = None,
    watchdogs: _watchdog.WatchdogThresholds | None = None,
) -> RecordingOutcome:
    index, recording = entry
    out_json, checkpoint_json = _entry_paths(out_dir, index, recording)

    if resume:
        existing = _load_completed(out_json, recording)
        if existing is not None:
            return existing

    cmd = [
        sys.executable, "-m", "adas_sim.orchestrate.worker",
        "--recording", str(recording), "--pipeline", str(pipeline_path), "--out-json", str(out_json),
        "--checkpoint-json", str(checkpoint_json),
    ]
    for directory in search:
        cmd += ["--search", str(directory)]
    if config is not None:
        cmd += ["--config", str(config)]
    for name in test_stub_echo:
        cmd += ["--test-stub-echo", name]

    start = time.monotonic()
    #: `IMP-0235`: the polling path (checkpoint-tick progress, cancellation,
    #: watchdog heartbeats, memory) is only entered when a caller actually
    #: asks for one of those -- `subprocess.run` below stays the unmodified
    #: fast path for the overwhelming common case (no caller-visible change
    #: for every existing call site that passes none of these).
    if memory_limit_mb is not None or progress is not None or cancel is not None or watchdogs is not None:
        limit = (
            _limits.MemoryLimit(limit_bytes=int(memory_limit_mb * 1024 * 1024)) if memory_limit_mb is not None
            else None
        )
        result = _launch_worker_polled(
            cmd, recording, out_json, checkpoint_json, start, timeout_s=timeout_s, limit=limit,
            progress=progress, cancel=cancel, watchdogs=watchdogs,
        )
    else:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            duration_s = time.monotonic() - start
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            result = _classify(
                recording, None, out_json, checkpoint_json, duration_s, timed_out=True, timeout_stderr=stderr,
            )
        else:
            duration_s = time.monotonic() - start
            result = _classify(recording, proc, out_json, checkpoint_json, duration_s, timed_out=False, timeout_stderr="")

    _write_outcome_manifest(out_dir, index, recording, pipeline_path, result)
    return result


@dataclass(slots=True)
class _PollFinding:
    """Set by `_launch_worker_polled`'s own watcher thread, read by the main
    thread after `communicate()` returns -- plain attribute writes/reads, not
    an `Event` per condition: only one watcher thread ever writes, and it
    stops polling (and therefore stops writing) the instant it sets one, so
    there is no concurrent-write race to guard against."""

    memory_breached: bool = False
    cancelled: bool = False
    watchdog: str = ""  # "" | "processing" | "responsiveness"

    @property
    def triggered(self) -> bool:
        return self.memory_breached or self.cancelled or bool(self.watchdog)


def _launch_worker_polled(
    cmd: list[str], recording: Path, out_json: Path, checkpoint_json: Path, start: float, *,
    timeout_s: float, limit: _limits.MemoryLimit | None,
    progress: ProgressSink | None, cancel: CancelToken | None, watchdogs: _watchdog.WatchdogThresholds | None,
) -> RecordingOutcome:
    """`IMP-0235`/`SW-0248`'s shared polling path: a `Popen`, watched on its
    own thread while the main thread blocks in `communicate(timeout=
    timeout_s)` (never blocking the caller beyond the existing wall-time
    cap). Each poll tick, at `watchdogs.poll_interval_s` (default from
    `MemoryLimit.poll_interval_s`, `0.5s`, when only a memory limit is set):

    - reads `--checkpoint-json` (`read_checkpoint_tick`) -- an advancing
      tick count reports `progress.on_progress` and heartbeats
      `ProcessingWatchdog`; the subprocess merely still being alive at this
      poll heartbeats `ResponsivenessWatchdog` (`SW-0247`'s own "any sign of
      life", not only a completed unit of work).
    - checks the memory limit, when given (`SW-0248`, unchanged behaviour
      from the pre-2026-08-25 memory-only path).
    - checks `cancel.cancelled`, when a `CancelToken` was supplied.

    Any one of memory/cancel/watchdog terminates the subprocess; `_classify`
    then reads exactly as it does for an ordinary crash (no readable
    `out_json`, abnormal exit), and the specific reason is layered on
    afterward via `RecordingOutcome.limit_breach`/`cancelled`/`watchdog` --
    the same distinguish-by-field pattern throughout this module, never a
    fifth `outcome` value (`R-SIM-19`)."""
    poll_interval_s = (
        watchdogs.poll_interval_s if watchdogs is not None
        else limit.poll_interval_s if limit is not None
        else 0.5
    )
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    finding = _PollFinding()
    processing = _watchdog.ProcessingWatchdog(watchdogs.processing_s, poll_interval_s) if watchdogs else None
    responsiveness = (
        _watchdog.ResponsivenessWatchdog(watchdogs.responsiveness_s, poll_interval_s) if watchdogs else None
    )
    #: `_PollingWatchdog._last_heartbeat` defaults to `0.0`, not the current
    #: clock -- `time.monotonic()` is an arbitrary reference point (uptime on
    #: most platforms), so an un-seeded watchdog would read `now - 0.0` as
    #: already past threshold and fire on its very first poll. Every real
    #: caller (`tests/unit/test_si15_orchestrate.py`'s own watchdog tests)
    #: seeds `heartbeat` immediately after construction; this is that seed.
    if processing is not None:
        processing.heartbeat(start)
    if responsiveness is not None:
        responsiveness.heartbeat(start)
    last_tick_count: int | None = None

    def _watch() -> None:
        nonlocal last_tick_count
        while proc.poll() is None:
            now = time.monotonic()
            if responsiveness is not None:
                responsiveness.heartbeat(now)
            tick_count, _ = read_checkpoint_tick(checkpoint_json)
            if tick_count is not None and tick_count != last_tick_count:
                last_tick_count = tick_count
                if processing is not None:
                    processing.heartbeat(now)
                if progress is not None:
                    progress.report(tick_count)
            if limit is not None and _limits.breach_reason(_limits.rss_bytes(proc.pid), limit):
                finding.memory_breached = True
                proc.terminate()
                return
            if cancel is not None and cancel.cancelled:
                finding.cancelled = True
                proc.terminate()
                return
            if processing is not None and processing.poll(now):
                finding.watchdog = "processing"
                proc.terminate()
                return
            if responsiveness is not None and responsiveness.poll(now):
                finding.watchdog = "responsiveness"
                proc.terminate()
                return
            time.sleep(poll_interval_s)

    watcher = threading.Thread(target=_watch, daemon=True)
    watcher.start()
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        duration_s = time.monotonic() - start
        watcher.join(timeout=1.0)
        if finding.triggered:
            return _finding_outcome(finding, recording, duration_s, limit, stderr)
        return _classify(
            recording, None, out_json, checkpoint_json, duration_s, timed_out=True, timeout_stderr=stderr,
        )
    watcher.join(timeout=1.0)
    duration_s = time.monotonic() - start
    if finding.triggered:
        return _finding_outcome(finding, recording, duration_s, limit, stderr)
    completed = subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    return _classify(recording, completed, out_json, checkpoint_json, duration_s, timed_out=False, timeout_stderr="")


def _finding_outcome(
    finding: _PollFinding, recording: Path, duration_s: float, limit: _limits.MemoryLimit | None, stderr: str,
) -> RecordingOutcome:
    """One `RecordingOutcome` for whichever `_PollFinding` fired -- always
    `outcome="fail"` (a deliberate supervisor action, not a self-reported
    result and not a plain wall-timeout), distinguished by exactly one of
    `limit_breach`/`cancelled`/`watchdog` (`_PollFinding.triggered` is only
    `True` when the watcher stopped at its first match, so exactly one is
    ever set)."""
    if finding.memory_breached:
        assert limit is not None
        return RecordingOutcome(
            recording=recording, outcome="fail", duration_s=duration_s,
            error=f"memory limit {limit.limit_bytes} bytes exceeded", stderr_excerpt=stderr[-_STDERR_EXCERPT_BYTES:],
            limit_breach="memory",
        )
    if finding.cancelled:
        return RecordingOutcome(
            recording=recording, outcome="fail", duration_s=duration_s,
            error="cancelled", stderr_excerpt=stderr[-_STDERR_EXCERPT_BYTES:], cancelled=True,
        )
    return RecordingOutcome(
        recording=recording, outcome="fail", duration_s=duration_s,
        error=f"{finding.watchdog} watchdog fired", stderr_excerpt=stderr[-_STDERR_EXCERPT_BYTES:],
        watchdog=finding.watchdog,
    )


def run_batch(
    recordings: Sequence[Path], pipeline_path: Path, *,
    search: Sequence[Path] = (), config: Path | None = None, jobs: int = 1, timeout_s: float = 300.0,
    test_stub_echo: Sequence[str] = (), out_dir: Path | None = None, resume: bool = False,
    memory_limit_mb: float | None = None,
    progress: ProgressSink | None = None, cancel: CancelToken | None = None,
    watchdogs: _watchdog.WatchdogThresholds | None = None,
) -> list[RecordingOutcome]:
    """Runs `pipeline_path` -- the SAME file `sim resim` would take,
    unmodified (`R-SIM-16`, `ST-D7-3`) -- against every recording in
    `recordings`, one subprocess each. Returns results in `recordings`'
    OWN order regardless of completion order (`ThreadPoolExecutor.map`'s own
    guarantee) -- a deterministic report is worth more than a marginally
    earlier print of whichever recording happened to finish first.

    `out_dir`, when given, is used as a PERSISTENT per-entry artifact
    directory (deterministic filenames, `_entry_paths`) instead of a
    one-shot temp directory -- required for `resume=True` (`SW-0249`) and
    for `reconcile` (`SW-0244`) to find these files after this call
    returns. `out_dir` is never created/removed by this function; a caller
    owns its lifetime (typically `orchestrate/artifacts.py::run_dir`'s own
    `checkpoints/` subdirectory).

    `progress`/`cancel`/`watchdogs` (`IMP-0235`/`IMP-0246`/`IMP-0247`), when
    given, are shared across every job the same `ProgressSink` already is
    across `sim run`/`sim resim` (`orchestrate/progress.py`'s own docstring)
    -- each job's own subprocess is polled on `watchdogs.poll_interval_s`
    (or `0.5s` with no `watchdogs`) for an advancing checkpoint tick
    (`progress.on_progress`), the subprocess's mere aliveness
    (`ResponsivenessWatchdog.heartbeat`) and `cancel.cancelled`. None of
    the three changes behaviour for a caller that passes none of them --
    `_launch_worker` only enters the polling path when at least one of
    `memory_limit_mb`/`progress`/`cancel`/`watchdogs` is given."""
    if out_dir is not None:
        worker = functools.partial(
            _launch_worker, pipeline_path=pipeline_path, search=tuple(search), config=config,
            timeout_s=timeout_s, test_stub_echo=tuple(test_stub_echo), out_dir=out_dir, resume=resume,
            memory_limit_mb=memory_limit_mb, progress=progress, cancel=cancel, watchdogs=watchdogs,
        )
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
            return list(executor.map(worker, enumerate(recordings)))

    with tempfile.TemporaryDirectory(prefix="adas_sim_batch_") as tmp_dir:
        worker = functools.partial(
            _launch_worker, pipeline_path=pipeline_path, search=tuple(search), config=config,
            timeout_s=timeout_s, test_stub_echo=tuple(test_stub_echo), out_dir=Path(tmp_dir), resume=False,
            memory_limit_mb=memory_limit_mb, progress=progress, cancel=cancel, watchdogs=watchdogs,
        )
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
            return list(executor.map(worker, enumerate(recordings)))


def reconcile(out_dir: Path, recordings: Sequence[Path]) -> list[RecordingOutcome]:
    """`SW-0244`: rebuilds the aggregate from the per-run artifacts on disk
    -- never from an in-memory accumulator -- so the aggregate and the
    individual results cannot disagree by construction. Mirrors `_classify`'s
    own crash/timeout inference: an entry with no readable `out_json` and no
    checkpoint is reported `crash` (the honest read of "the worker never
    told us anything"), since `reconcile` has no live process or exit code
    to distinguish a genuine crash from a timeout after the fact -- a
    caller wanting that distinction keeps `run_batch`'s own live return
    value; `reconcile` answers "what does the directory say happened","""
    results: list[RecordingOutcome] = []
    for index, recording in enumerate(recordings):
        out_json, checkpoint_json = _entry_paths(out_dir, index, recording)
        completed = _load_completed(out_json, recording)
        if completed is not None:
            results.append(completed)
            continue
        tick_count, last_tick_ns = read_checkpoint_tick(checkpoint_json)
        results.append(RecordingOutcome(
            recording=recording, outcome="crash", duration_s=0.0,
            tick_count=tick_count, last_tick_ns=last_tick_ns, error="no readable out_json (reconciled from disk)",
        ))
    return results


def sweep_configs(
    base_config: Path, param: str, values: Sequence[object], *, project: str = "base",
) -> dict[object, ResolvedRunConfig]:
    """`SW-0250`: one derived config bundle per swept value, each differing
    from `base_config` in exactly `param` -- the diffable unit `UT-ORC-16`
    asserts. Reuses `runspec/manifest.py::resolve_swept_config`
    (`NR-SIM-6`'s own mechanism, already `DONE`) rather than re-deriving
    bundles here; a caller owns every `ResolvedRunConfig.scratch_dir`
    returned and must remove it (same lifetime discipline
    `resolve_swept_config` itself documents)."""
    return {value: resolve_swept_config(base_config, {param: value}, project=project) for value in values}


def sweep(
    recordings: Sequence[Path], pipeline_path: Path, param: str, values: Sequence[object], *,
    base_config: Path, project: str = "base", **run_batch_kwargs: object,
) -> dict[object, list[RecordingOutcome]]:
    """`batch.py::sweep` (`IMP-0250`): runs the whole batch once per swept
    value, each against its own derived bundle -- `SW-0256`'s "no batch-only
    configuration format" holds because every entry is a plain `run_batch`
    call with a differently-resolved `config`."""
    results: dict[object, list[RecordingOutcome]] = {}
    resolved_by_value = sweep_configs(base_config, param, values, project=project)
    try:
        for value, resolved in resolved_by_value.items():
            results[value] = run_batch(
                recordings, pipeline_path, config=resolved.effective_config, **run_batch_kwargs,  # type: ignore[arg-type]
            )
    finally:
        for resolved in resolved_by_value.values():
            if resolved.scratch_dir is not None:
                shutil.rmtree(resolved.scratch_dir, ignore_errors=True)
    return results


def write_report(results: Sequence[RecordingOutcome], path: Path) -> None:
    counts = Counter(r.outcome for r in results)
    lines = [
        "# sim batch report", "", f"{len(results)} recording(s)", "",
        "| recording | outcome | duration_s | ticks | error |", "|---|---|---|---|---|",
    ]
    for r in results:
        first_error_line = r.error.splitlines()[0] if r.error else ""
        error_cell = first_error_line.replace("|", "\\|")
        ticks_cell = "" if r.tick_count is None else str(r.tick_count)
        lines.append(f"| {r.recording} | {r.outcome} | {r.duration_s:.2f} | {ticks_cell} | {error_cell} |")
    lines += ["", "## summary", ""]
    lines += [f"- {outcome}: {counts.get(outcome, 0)}" for outcome in OUTCOMES]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
