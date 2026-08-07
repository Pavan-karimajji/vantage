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
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

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


def _launch_worker(
    recording: Path, *, pipeline_path: Path, search: tuple[Path, ...], config: Path | None, timeout_s: float,
    test_stub_echo: tuple[str, ...], out_dir: Path,
) -> RecordingOutcome:
    out_json = out_dir / f"{recording.stem}-{uuid4().hex[:8]}.json"
    checkpoint_json = out_dir / f"{recording.stem}-{uuid4().hex[:8]}.checkpoint.json"
    cmd = [
        sys.executable, "-m", "adas_sim.core.batch_worker",
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
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        duration_s = time.monotonic() - start
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return _classify(
            recording, None, out_json, checkpoint_json, duration_s, timed_out=True, timeout_stderr=stderr,
        )

    duration_s = time.monotonic() - start
    return _classify(recording, proc, out_json, checkpoint_json, duration_s, timed_out=False, timeout_stderr="")


def run_batch(
    recordings: Sequence[Path], pipeline_path: Path, *,
    search: Sequence[Path] = (), config: Path | None = None, jobs: int = 1, timeout_s: float = 300.0,
    test_stub_echo: Sequence[str] = (),
) -> list[RecordingOutcome]:
    """Runs `pipeline_path` -- the SAME file `sim resim` would take,
    unmodified (`R-SIM-16`, `ST-D7-3`) -- against every recording in
    `recordings`, one subprocess each. Returns results in `recordings`'
    OWN order regardless of completion order (`ThreadPoolExecutor.map`'s own
    guarantee) -- a deterministic report is worth more than a marginally
    earlier print of whichever recording happened to finish first."""
    with tempfile.TemporaryDirectory(prefix="adas_sim_batch_") as tmp_dir:
        worker = functools.partial(
            _launch_worker, pipeline_path=pipeline_path, search=tuple(search), config=config,
            timeout_s=timeout_s, test_stub_echo=tuple(test_stub_echo), out_dir=Path(tmp_dir),
        )
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
            return list(executor.map(worker, recordings))


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
