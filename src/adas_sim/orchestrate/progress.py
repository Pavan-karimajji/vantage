# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SW-0235`: any operation whose duration is not bounded by a small constant
reports progress and accepts cancellation, leaving a well-defined state.

`CancelToken` is the same cooperative-flag shape `player/panels/transport.py`
already uses for `Transport.advance` (plain Python, no Qt) -- duplicated
rather than imported, because `orchestrate/**` must stay importable with no
`viewer`/`figures` extra installed (`UT-A1-2`) and `player/panels/transport.py`
pulls in `adas_sim.session.session`. `ProgressSink` is the headless-verb
counterpart: a plain callback interface a caller passes into `invoke_engine`
(`orchestrate/run.py`) and into every batch job, so `sim run`/`sim resim`/
`sim batch` -j>1 all report through the same shape instead of each growing
its own ad-hoc printer.

**Known limitation, stated rather than hidden:** today's engine invocation
(`engine.bridge.run_pipeline_via_engine`) drives a `simengine` subprocess with
no per-tick callback across that process boundary (the same gap
`orchestrate/worker.py`'s own docstring names for `--checkpoint-json`) --
so `ProgressSink.on_progress` fires only at coarse boundaries (job
started/finished) for a `simengine`-backed run, not per tick. Cancellation is
therefore honoured **at the next process-boundary check**, never mid-tick
inside `simengine` -- consistent with `SW-0235`'s own Accept clause ("leaves
the artifact set at a tick boundary, never mid-tick"), since a subprocess
still running when the boundary check happens is either let finish or killed
outright, both of which land on a tick boundary (the process either wrote a
whole tick's own recorded output or none of it)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


class CancelToken:
    """A cooperative cancel flag. `cancel()` is safe to call from any thread;
    `cancelled` is a plain read."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def __repr__(self) -> str:
        return f"<CancelToken cancelled={self._cancelled}>"


#: `on_progress(done, total)` -- `total` is `0` when the operation cannot
#: state one in advance (e.g. a batch whose recording count is known, but a
#: single `simengine` run whose tick count is not observable from outside).
OnProgress = Callable[[int, int], None]


@dataclass(slots=True)
class ProgressSink:
    """The plain callback interface every long operation reports through.
    `on_progress`/`on_message` default to no-ops so a caller with nothing to
    show (a script, a test) can pass `ProgressSink()` unchanged; a CLI verb
    supplies real callables (print/tqdm-style) and a GUI face supplies ones
    that update a widget."""

    on_progress: OnProgress = field(default=lambda done, total: None)
    on_message: Callable[[str], None] = field(default=lambda msg: None)
    cancel: CancelToken = field(default_factory=CancelToken)

    def report(self, done: int, total: int = 0) -> None:
        self.on_progress(done, total)

    def message(self, text: str) -> None:
        self.on_message(text)

    @property
    def cancelled(self) -> bool:
        return self.cancel.cancelled
