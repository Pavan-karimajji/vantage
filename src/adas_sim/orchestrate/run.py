# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SW-0238`: one engine invocation shape for every face. `invoke_engine`
wraps `engine.bridge.run_pipeline_via_engine` -- already the single function
every resim-shaped call site drives `simengine` through -- adding
`ProgressSink`/`CancelToken` awareness (`SW-0235`) so a caller reports
progress and can ask for cancellation without duplicating the
spec-build-then-run sequence itself.

**Known invocation sites, and one deliberate exception:** `check/runner.py`,
`cli/resim.py` and `orchestrate/worker.py` are resim-shaped (pipeline against
an existing recording) and are rewired here to call `invoke_engine` rather
than `run_pipeline_via_engine` directly, so `ANL-SW-41` finds one shape
across all three. `cli/run.py` (`sim run`, the live-source face) is **not**
rewired: it drives `pipeline.step()` in process against a live `Source`,
which has no Run Spec / recording to hand `simengine` -- unifying it would
mean teaching `simengine` to consume a live source, a `SI-02`/engine-level
change outside this package's own `Files:` scope (`adas_sim/orchestrate/**`,
`adas_sim/cli/**` argparse only). Left as a named, tracked gap rather than
forced."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence

from adas_sim.engine.bridge import EngineRunResult, run_pipeline_via_engine
from adas_sim.graph.build import Pipeline
from adas_sim.orchestrate.progress import ProgressSink


def invoke_engine(
    pipeline: Pipeline, recording_path: Path, *, run_id: str, output_path: Path,
    config_path: Path | None = None, exec_timeout_ms: int = 250,
    spec_json_path: Path | None = None, simengine_path: Path | None = None, search: Sequence[Path] = (),
    progress: ProgressSink | None = None,
) -> EngineRunResult:
    """The one call every face makes to drive `simengine` against an
    existing recording (the interactive workspace, `sim resim`, `sim check`,
    a `sim batch` worker). `progress` is optional -- a caller with nothing to show passes
    `None` -- and, per this module's own docstring, fires only at the
    process boundary: `"starting"` before the subprocess launches, then
    `"cancelled before start"` (never launched) or the finished/failed
    message after it returns. `CancelToken.cancelled` is checked once,
    before launch, because there is no per-tick channel across the
    `simengine` subprocess boundary to check it again mid-run
    (`orchestrate/worker.py`'s own documented gap) -- consistent with
    `SW-0235`'s tick-boundary guarantee: a process never launched is exactly
    as "at a boundary" as one that ran to completion."""
    sink = progress if progress is not None else ProgressSink()
    if sink.cancelled:
        sink.message("cancelled before start")
        return EngineRunResult(exit_code=-1, ok=False, stdout="", stderr="cancelled before start", output_path=output_path)

    sink.message(f"starting run {run_id}")
    sink.report(0, 0)
    result = run_pipeline_via_engine(
        pipeline, recording_path, run_id=run_id, output_path=output_path, config_path=config_path,
        exec_timeout_ms=exec_timeout_ms, spec_json_path=spec_json_path, simengine_path=simengine_path, search=search,
    )
    sink.report(1, 1)
    sink.message(f"finished run {run_id}: ok={result.ok}")
    return result
