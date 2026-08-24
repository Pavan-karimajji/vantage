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
from dataclasses import dataclass, replace
from pathlib import Path

from adas_sim.orchestrate import limits as _limits
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


def _read_checkpoint(checkpoint_json: Path) -> tuple[int | None, int | None]:
    """`(tick_count, last_tick_ns)` from `batch_worker.py`'s own
    `--checkpoint-json`, or `(None, None)` if it was never written or is
    unreadable -- a crashing process can leave no checkpoint at all (it died
    before the first tick) or, in principle, a torn one; either way this
    reports `unknown` rather than a guessed value (`R-SIM-25`/`NR-SIM-4`).
    The worker writes this file via `os.replace`, so a fully-written-but-
    stale checkpoint (from a PREVIOUS tick) is the only failure mode this
    needs to tolerate, and `json.loads` alone already handles that -- it is
    never torn."""
    if not checkpoint_json.is_file():
        return None, None
    try:
        data = json.loads(checkpoint_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    return data.get("tick_count"), data.get("last_tick_ns")


def _classify(
    recording: Path, proc: subprocess.CompletedProcess[str] | None, out_json: Path, checkpoint_json: Path,
    duration_s: float, *, timed_out: bool, timeout_stderr: str,
) -> RecordingOutcome:
    if timed_out:
        tick_count, last_tick_ns = _read_checkpoint(checkpoint_json)
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
    # (UT-D7-7) -- it is written by the worker, read here by the parent.
    tick_count, last_tick_ns = _read_checkpoint(checkpoint_json)
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
    is `outcome.tick_count` when the worker or a checkpoint reported one,
    else `-1` (`SW-0119` pending: no per-tick checkpoint channel across the
    `simengine` subprocess boundary yet, `orchestrate/worker.py`'s own
    documented gap) -- honest, never a guess. `run_kind="resim"`: a batch
    entry executes an existing recording exactly like `sim resim` does
    (`SW-0233`), and `"batch"` is not itself in the manifest schema's own
    closed `run_kind` enum."""
    manifest = build_manifest(
        pipeline_path=pipeline_path, run_kind="resim", source_kind="mcap", recording_path=recording,
        outcome=_MANIFEST_OUTCOME_OF[outcome.outcome],
        last_completed_cycle=outcome.tick_count if outcome.tick_count is not None else -1,
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
    if memory_limit_mb is not None:
        result = _launch_worker_with_memory_limit(
            cmd, recording, out_json, checkpoint_json, start, timeout_s=timeout_s,
            limit=_limits.MemoryLimit(limit_bytes=int(memory_limit_mb * 1024 * 1024)),
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


def _launch_worker_with_memory_limit(
    cmd: list[str], recording: Path, out_json: Path, checkpoint_json: Path, start: float, *,
    timeout_s: float, limit: _limits.MemoryLimit,
) -> RecordingOutcome:
    """`SW-0248`'s memory half: a `Popen`, polled on its own thread (never
    blocking the caller -- `subprocess.run` above is the no-limit fast path,
    kept unchanged for the overwhelming common case). A breach terminates
    the process and the result is reported `outcome="fail"` with
    `limit_breach="memory"` -- distinct from a plain `fail`, never merged
    into `crash`/`timeout` (`R-SIM-19`)."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    breached = threading.Event()

    def _watch() -> None:
        while proc.poll() is None:
            rss = _limits.rss_bytes(proc.pid)
            if _limits.breach_reason(rss, limit):
                breached.set()
                proc.terminate()
                return
            time.sleep(limit.poll_interval_s)

    watcher = threading.Thread(target=_watch, daemon=True)
    watcher.start()
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        duration_s = time.monotonic() - start
        watcher.join(timeout=1.0)
        if breached.is_set():
            return RecordingOutcome(
                recording=recording, outcome="fail", duration_s=duration_s,
                error=f"memory limit {limit.limit_bytes} bytes exceeded", stderr_excerpt=stderr[-_STDERR_EXCERPT_BYTES:],
                limit_breach="memory",
            )
        return _classify(
            recording, None, out_json, checkpoint_json, duration_s, timed_out=True, timeout_stderr=stderr,
        )
    watcher.join(timeout=1.0)
    duration_s = time.monotonic() - start
    completed = subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    result = _classify(recording, completed, out_json, checkpoint_json, duration_s, timed_out=False, timeout_stderr="")
    if breached.is_set() and result.outcome != "ok":
        result = replace(result, limit_breach="memory")
    return result


def run_batch(
    recordings: Sequence[Path], pipeline_path: Path, *,
    search: Sequence[Path] = (), config: Path | None = None, jobs: int = 1, timeout_s: float = 300.0,
    test_stub_echo: Sequence[str] = (), out_dir: Path | None = None, resume: bool = False,
    memory_limit_mb: float | None = None,
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
    `checkpoints/` subdirectory)."""
    if out_dir is not None:
        worker = functools.partial(
            _launch_worker, pipeline_path=pipeline_path, search=tuple(search), config=config,
            timeout_s=timeout_s, test_stub_echo=tuple(test_stub_echo), out_dir=out_dir, resume=resume,
            memory_limit_mb=memory_limit_mb,
        )
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
            return list(executor.map(worker, enumerate(recordings)))

    with tempfile.TemporaryDirectory(prefix="adas_sim_batch_") as tmp_dir:
        worker = functools.partial(
            _launch_worker, pipeline_path=pipeline_path, search=tuple(search), config=config,
            timeout_s=timeout_s, test_stub_echo=tuple(test_stub_echo), out_dir=Path(tmp_dir), resume=False,
            memory_limit_mb=memory_limit_mb,
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
        tick_count, last_tick_ns = _read_checkpoint(checkpoint_json)
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
