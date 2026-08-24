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

- **`--checkpoint-json` is currently never written.** It existed to record
  progress after every tick (`_write_checkpoint`, driven by
  `resim_pipeline`'s own `on_tick` callback) so a mid-run crash's last tick
  survived the crash. `simengine` has real per-cycle checkpointing in C++
  (`src/simcore/runner/checkpoint.cpp`) but no ABI/CLI path exposing it yet
  (`WP-14a`'s own addendum names this gap) -- there is currently no
  mechanism for this process to observe a tick boundary inside its own
  child subprocess. The flag is still accepted (never written) so
  `orchestrate/batch.py`'s own `--checkpoint-json` plumbing needs no
  change; a crash's `tick_count`/`last_tick_ns` now read `unknown`
  (`R-SIM-25`/`NR-SIM-4`) rather than the last real tick, which is the
  honest answer, not a regression papered over.
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

from adas_sim.graph.build import Pipeline
from adas_sim.diagnostics.errors import SimError
from adas_sim.engine.bridge import count_ticks
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
    return parser


def _write_result(out_json: Path, **fields: object) -> None:
    out_json.write_text(json.dumps(fields, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _maybe_run_test_hook(None)  # the blanket-only shortcut, before paying for argparse

    args = _build_parser().parse_args(argv)
    _maybe_run_test_hook(args.recording)  # the per-recording ADAS_SIM_BATCH_TEST_STUB_MAP case
    # args.test_stub_echo, args.checkpoint_json: accepted for CLI
    # compatibility with orchestrate/batch.py's own forwarding, both
    # currently no-ops -- see this module's own docstring for why.

    try:
        pipeline = Pipeline.load(args.pipeline, search=tuple(args.search))
        with tempfile.TemporaryDirectory(prefix="adas_sim_batch_worker_") as tmp_dir:
            output_path = Path(tmp_dir) / "out.mcap"
            result = invoke_engine(
                pipeline, args.recording, run_id=f"batch-{args.recording.stem}", output_path=output_path,
                config_path=args.config,
            )
            if not result.ok:
                _write_result(
                    args.out_json, outcome="fail",
                    error=f"simengine exit_code={result.exit_code}: {result.stderr or result.stdout}",
                    tick_count=None, last_tick_ns=None,
                )
                return 1
            tick_count = count_ticks(output_path)
    except SimError as exc:
        _write_result(args.out_json, outcome="fail", error=str(exc), tick_count=None, last_tick_ns=None)
        return 1
    except Exception as exc:  # noqa: BLE001 -- a framework bug is still a clean "fail" report,
        # never a silent process death; only os._exit (the test hook above) or a real
        # crash inside a C library skips this reporting path entirely.
        _write_result(
            args.out_json, outcome="fail", error=f"{type(exc).__name__}: {exc}", tick_count=None, last_tick_ns=None,
        )
        return 1

    _write_result(args.out_json, outcome="ok", tick_count=tick_count, last_tick_ns=None)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
