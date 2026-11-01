# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim batch`'s per-recording subprocess entry point (`S-D7`, `R-SIM-19`).

`core/batch.py` launches one of these per recording -- isolation is at run
granularity, never per tick. This module does one recording's worth of
`Pipeline.load` -> `engine.bridge.run_pipeline_via_engine` and writes its
outcome as JSON to `--out-json`.

**It only ever reports `ok` or `fail` about itself.** A real crash kills this
process before it can write anything, so the parent classifies
`crash`/`timeout`/`fail` from the outside (missing JSON plus an abnormal exit)
rather than trusting a value a dying process claims about its own death.

`WP-15b` (`IMP-0422`): execution moved to `simengine`, one further
subprocess out from this one (`engine.bridge` -- `simcore` is a STATIC
library with no in-process ABI artifact to bind, see that module's own
docstring). Two consequences, found live and left as named follow-ons
rather than guessed at here:

- **`--checkpoint-json` is now `simengine`'s own `progress.json` (`SW-0119`,
  closed 2026-08-24).** `WP-14a`'s ABI/CLI gap is closed (`simEngineCreate`
  writes it directly, `src/simcore/runner/checkpoint.cpp`), so this process
  no longer writes the file itself -- it forwards `args.checkpoint_json`
  straight through to `invoke_engine` as `checkpoint_path`, and `simengine`
  flushes it after every completed cycle **in its own subprocess**, which is
  exactly what lets it survive a crash of that subprocess (and of this one).
  `orchestrate/batch.py::read_checkpoint_tick` reads it directly on a
  `crash`/`timeout` classification. **Still not a live channel:** the file
  is only observable once written to disk, so a `ProgressSink`/
  `CancelToken` mid-run check (`orchestrate/progress.py`) and either
  watchdog (`orchestrate/watchdog.py`) still have no per-tick signal while
  this process's own child is still running -- that gap is unchanged by
  this fix and needs `orchestrate/batch.py` polling the file on a timer
  instead of blocking on `subprocess.run`, a separate follow-on.
- **`--test-stub-echo`'s own `InProcessSilComponent` injection is gone.**
  A Python closure has no equivalent once this stage runs through
  `simengine`'s own subprocess boundary (the same gap `WP-14a`'s addendum
  names for all three of `WP-15b`'s remaining call sites). The flag is
  still accepted for CLI compatibility with `orchestrate/batch.py`'s own
  `--test-stub-echo` forwarding, but is now a no-op: a stage still needs a
  real `impl: dll:<stem>` resolvable via `--search` (the real,
  built `echo_stub` test fixture, `tests/fixtures/echo_stub`, is the
  real answer for a test needing a real component with no production
  library -- see `tests/unit/test_d7_batch.py`'s own updated fixtures).

Two test-only hooks remain live (unaffected by the above -- both fire
before `Pipeline.load`, so neither ever touches the engine):

- `ADAS_SIM_BATCH_TEST_STUB=crash|hang` -- die or hang with no pipeline
  involved, so the parent's classifier can be tested without a component that
  can be told to segfault. `ADAS_SIM_BATCH_TEST_STUB_MAP="stemA=crash;stemB=hang"`
  is the per-recording form.
- `ADAS_SIM_TEST_FORCE_ABORT` (forwarded to the `simengine` child via the
  environment) aborts inside `simengine` itself -- `src/simengine/main.cpp`'s
  own hook, reused here rather than duplicated (`UT-D7-7`'s own "genuine
  abnormal termination" case, now one level further out).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from adas_sim.graph.pipeline import Pipeline
from adas_sim.diagnostics.errors import SimError
from adas_sim.engine.bridge import count_ticks
from adas_sim.orchestrate.batch import read_checkpoint_tick
from adas_sim.orchestrate.readerror import ReadError, probe_recording
from adas_sim.orchestrate.run import invoke_engine

#: Values `ADAS_SIM_BATCH_TEST_STUB` recognizes -- a closed set, same
#: discipline every other closed vocabulary in this codebase uses, so a typo
#: fails loudly (KeyError) rather than silently running the real pipeline.
_TEST_HOOKS = ("crash", "hang")


def _hook_for_recording(recording: Path | None) -> str | None:
    """Two ways to name a hook, both explicit and neither reachable from a
    real `sim batch` invocation:

    - `ADAS_SIM_BATCH_TEST_STUB=crash|hang` -- applies unconditionally,
      regardless of which recording this process was launched for. Simplest
      shape, for a test driving one worker process directly.
    - `ADAS_SIM_BATCH_TEST_STUB_MAP="stemA=crash;stemB=hang"` -- keyed by
      `recording.stem`, so ONE `sim batch` invocation over a real recording
      SET can make specific recordings crash/hang while the rest run for
      real (`ST-D7-5`'s own scenario: "one deliberately crashing and one
      deliberately hanging" inside a single batch of 20).
    """
    blanket = os.environ.get("ADAS_SIM_BATCH_TEST_STUB")
    if blanket is not None:
        return blanket
    mapping = os.environ.get("ADAS_SIM_BATCH_TEST_STUB_MAP")
    if mapping is None or recording is None:
        return None
    for entry in mapping.split(";"):
        stem, _, hook = entry.partition("=")
        if stem == recording.stem:
            return hook
    return None


def _maybe_run_test_hook(recording: Path | None) -> None:
    """`recording` is `None` when called before argument parsing (the
    blanket-only, single-process case); real per-recording dispatch via
    `_TEST_STUB_MAP` needs `args.recording`, so `main()` calls this a
    second time, harmlessly, once parsing has happened."""
    hook = _hook_for_recording(recording)
    if hook is None:
        return
    if hook not in _TEST_HOOKS:
        raise ValueError(f"test stub hook {hook!r} not in {_TEST_HOOKS}")
    if hook == "crash":
        # Dies immediately with no chance to write --out-json -- the exact
        # shape a real segfault leaves for the parent to classify from
        # (UT-D7-7): abnormal exit, no result file.
        os._exit(139)
    # hook == "hang": never returns. The PARENT's subprocess timeout is what
    # ends this (UT-D7-8) -- there is deliberately no in-process timeout
    # here to race against it.
    time.sleep(10_000_000)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adas_sim.orchestrate.worker")
    parser.add_argument("--recording", type=Path, required=True)
    parser.add_argument("--pipeline", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--search", type=Path, action="append", default=[])
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--test-stub-echo", action="append", default=[], metavar="STAGE_NAME")
    parser.add_argument("--checkpoint-json", type=Path, default=None)
    parser.add_argument("--on-read-error", choices=[e.value for e in ReadError], default=ReadError.SKIP_ENTRY.value)
    parser.add_argument("--read-retry-bound-s", type=float, default=5.0)
    return parser


def _write_result(out_json: Path, **fields: object) -> None:
    out_json.write_text(json.dumps(fields, sort_keys=True), encoding="utf-8")


def _checkpoint_result(checkpoint_json: Path | None) -> tuple[int | None, int | None]:
    """`(tick_count, last_tick_ns)` from `simengine`'s real `progress.json`
    (`orchestrate/batch.py::read_checkpoint_tick`, shared rather than
    reimplemented), or `(None, None)` when no `--checkpoint-json` was given
    at all -- distinct from that file existing but reporting nothing, which
    `read_checkpoint_tick` itself already returns as `(None, None)`."""
    if checkpoint_json is None:
        return None, None
    return read_checkpoint_tick(checkpoint_json)


def main(argv: list[str] | None = None) -> int:
    _maybe_run_test_hook(None)  # the blanket-only shortcut, before paying for argparse

    args = _build_parser().parse_args(argv)
    _maybe_run_test_hook(args.recording)  # the per-recording ADAS_SIM_BATCH_TEST_STUB_MAP case
    # args.test_stub_echo: accepted for CLI compatibility with
    # orchestrate/batch.py's own forwarding, still a no-op -- see this
    # module's own docstring for why. args.checkpoint_json is forwarded to
    # invoke_engine below -- no longer a no-op.

    # `IMP-0252`/`IMP-0253`: a genuine Python-side read of `--recording`
    # before `Pipeline.load` -- today's only other pre-flight this file
    # gets is `simengine`'s own C++ decoder, once, with no retry and no
    # classification. `readerror.probe_recording` is a standalone,
    # directly-testable function -- see its own docstring for what it does
    # and why `skipped_packages` is only ever nonzero under `SKIP_PACKAGE`.
    skipped_packages, read_outcome = probe_recording(
        args.recording, on_read_error=args.on_read_error, bound_s=args.read_retry_bound_s,
    )
    if not read_outcome.succeeded:
        # Every policy value is reported the same way from inside ONE
        # worker -- this process only ever sees its own recording, so
        # `stop`/`abort_batch`'s own "beyond this one entry" behaviour is
        # enacted by the PARENT (`orchestrate/batch.py::run_batch`'s own
        # pre-flight for `stop`, `_launch_worker`'s own cancel-on-abort for
        # `abort_batch`), never here -- this worker reports the fact
        # (`read_error`, the policy it was launched with) and exits
        # cleanly, same as any other expected `fail`.
        _write_result(
            args.out_json, outcome="fail",
            error=f"read error after {read_outcome.attempts} attempt(s): "
                  f"{read_outcome.errors[-1] if read_outcome.errors else ''}",
            read_error=args.on_read_error, read_retry_attempts=read_outcome.attempts,
            tick_count=None, last_tick_ns=None,
        )
        return 1

    try:
        pipeline = Pipeline.load(args.pipeline, search=tuple(args.search))
        setup_values = pipeline.setup_values()  # `IMP-0052`: a missing value is refused, named
        with tempfile.TemporaryDirectory(prefix="adas_sim_batch_worker_") as tmp_dir:
            output_path = Path(tmp_dir) / "out.mcap"
            result = invoke_engine(
                pipeline, args.recording, run_id=f"batch-{args.recording.stem}", output_path=output_path,
                config_path=args.config, checkpoint_path=args.checkpoint_json,
                setup_values=setup_values,
            )
            if not result.ok:
                tick_count, last_tick_ns = _checkpoint_result(args.checkpoint_json)
                _write_result(
                    args.out_json, outcome="fail",
                    error=f"simengine exit_code={result.exit_code}: {result.stderr or result.stdout}",
                    tick_count=tick_count, last_tick_ns=last_tick_ns,
                )
                return 1
            tick_count = count_ticks(output_path)
            _, last_tick_ns = _checkpoint_result(args.checkpoint_json)
    except SimError as exc:
        # `IMP-0128`: `exc.kind` is this SimError's own closed taxonomy
        # value ("authoring"|"environment"|"contract"|"internal") -- the
        # real event `--exit-on` gates against (`orchestrate/severity.py::
        # severity_for_kind`), reported as a fact here, evaluated by the
        # parent (`orchestrate/batch.py`), same distinguish-by-field
        # pattern `read_error`/`cancelled` already use.
        _write_result(
            args.out_json, outcome="fail", error=str(exc), error_kind=exc.kind, tick_count=None, last_tick_ns=None,
        )
        return 1
    except Exception as exc:  # noqa: BLE001 -- a framework bug is still a clean "fail" report,
        # never a silent process death; only os._exit (the test hook above) or a real
        # crash inside a C library skips this reporting path entirely. An uncaught
        # non-SimError exception IS what InternalError's own docstring describes
        # ("anything uncaught is this, by definition") -- tagged the same "internal"
        # kind even though nothing here constructs the class itself.
        _write_result(
            args.out_json, outcome="fail", error=f"{type(exc).__name__}: {exc}", error_kind="internal",
            tick_count=None, last_tick_ns=None,
        )
        return 1

    _write_result(
        args.out_json, outcome="ok", tick_count=tick_count, last_tick_ns=last_tick_ns,
        skipped_packages=skipped_packages,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
