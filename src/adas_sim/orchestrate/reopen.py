# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SW-0245`: every crash record carries what it takes to reopen the
failure in process on a developer machine -- recording, pipeline,
configuration, captured stderr, run identifier and (`SW-0119`, pending) the
last completed cycle.

`open_on_bench` is the pure decision `player/shell/shell/window.py`'s own
open-on-bench signal handler already makes ad hoc, factored out here so it
is callable with no Qt present (a script, a test, a future headless
"reopen this crash" CLI verb) -- **not yet wired back into the GUI call
site** (`R-STYLE-2` minimal diffs: `player/shell/shell/campaign.py`'s own
open-on-bench signal already emits exactly this tuple today; rewiring it to
call through here is a same-behaviour refactor with no test-visible
difference, left as a named follow-on rather than touched speculatively --
`player/shell/**` is the one place these workspace names are the whole
point, `UT-D8-9`).

**`last_completed_cycle` gap, closed 2026-08-25 (`SW-0119`):** a `crash`/
`timeout` `RecordingOutcome.last_tick_ns` now comes from `simengine`'s own
real `progress.json`, forwarded through `orchestrate/worker.py` and read by
`orchestrate/batch.py::read_checkpoint_tick`. `open_on_bench` still falls
back to `at_s=0.0` -- identical to the GUI's own existing fallback for a
non-crash row -- for the residual case a checkpoint file itself cannot
cover: no `--checkpoint-json` path was ever given, or the process died
before its first cycle completed (nothing to have written), honestly rather
than guessing a tick (`R-SIM-25`/`NR-SIM-4`)."""

from __future__ import annotations

from pathlib import Path

from adas_sim.graph.build import Pipeline
from adas_sim.orchestrate.batch import RecordingOutcome


def open_on_bench(outcome: RecordingOutcome, pipeline_path: Path) -> tuple[Path, Path, float]:
    """`(recording, pipeline_path, at_s)` -- the exact triple the GUI's own
    open-on-bench signal carries and its interactive workspace consumes.
    `at_s` is derived from `outcome.last_tick_ns` when known (a crash or
    timeout that DID capture a checkpoint), else `0.0`."""
    at_s = outcome.last_tick_ns / 1e9 if outcome.last_tick_ns is not None else 0.0
    return outcome.recording, pipeline_path, at_s


def reproduce_in_process(outcome: RecordingOutcome, pipeline_path: Path, *, search: tuple[Path, ...] = ()) -> Pipeline:
    """`SW-0245`'s own Accept clause, the part reachable with no GUI: loads
    the SAME pipeline `open_on_bench` names, in this process, so a caller
    reaches "the failure is reopened in process on a developer machine" up
    to (not including) the Qt seek-to-tick step the interactive workspace
    itself performs. Raises whatever `Pipeline.load` raises -- naming the
    real problem is more useful here than swallowing it, since this
    function's whole job is diagnosing a crash."""
    return Pipeline.load(pipeline_path, search=search)
