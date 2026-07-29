# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`Transport` -- the head model (R-SIM-17, sim_api_reference.md §2.4). The
**head** is the furthest tick computed; behind it a `Session` is immutable
data (seek, scrub, step back are free and never re-execute); at it, execution
advances. Stepping backwards leaves execution mode and enters review;
resuming forward offers exactly two named choices, so silently continuing
from a rewound tick is not representable in this API.

In `view/`, not `core/`: transport is view state, and `core/` must stay
importable by a headless resim that has no cursor.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from adas_sim.core.errors import AuthoringError
from adas_sim.core.session import Session


class CancelToken:
    """A cooperative cancel flag for `Transport.advance`'s one job."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def __repr__(self) -> str:
        return f"<CancelToken cancelled={self._cancelled}>"


class ResumeOption(StrEnum):
    SKIP_TO_HEAD = "skip_to_head"
    RECOMPUTE_FROM_ZERO = "recompute_from_zero"


@dataclass(frozen=True, slots=True)
class NamedResumeOption:
    option: ResumeOption
    available: bool = True
    #: Why unavailable, when `available` is False (`N-8`).
    reason: str = ""

    def __repr__(self) -> str:
        return f"<NamedResumeOption {self.option.value} available={self.available}>"


#: `advance_fn(n, on_progress, cancel) -> tick_reached` -- stands in for a
#: real SUT's `exec()` loop, which does not exist until a component's DLL is
#: wired (S-C1+). Phase B's whole point is testing the head/review-mode
#: invariants without one.
AdvanceFn = Callable[[int, Callable[[int, int], None], CancelToken], int]


class Transport:
    """Play/pause, step, speed, loop marks, goto, and the head."""

    def __init__(self, session: Session, advance_fn: AdvanceFn, *, head_tick: int = 0) -> None:
        self.session = session
        self._advance_fn = advance_fn
        self.head_tick = head_tick
        self.cursor = head_tick
        self.review_mode = False
        self.playing = False
        self.speed = 1.0
        self.loop_marks: tuple[int, int] | None = None

    def __repr__(self) -> str:
        return f"<Transport cursor={self.cursor} head_tick={self.head_tick} review_mode={self.review_mode}>"

    @property
    def is_at_head(self) -> bool:
        return self.cursor == self.head_tick and not self.review_mode

    def play(self) -> None:
        self.playing = True

    def pause(self) -> None:
        self.playing = False

    def _last_index(self) -> int:
        return len(self.session) - 1

    def step_forward(self, n: int = 1) -> None:
        """Executes iff at head; moving within the already-computed range
        while rewound is always free."""
        target = min(self.cursor + n, self._last_index())
        if target <= self.head_tick:
            self.cursor = target
            self.review_mode = self.cursor != self.head_tick
            return
        self._require_not_review_mode("step_forward", n)
        self.head_tick = self._advance_fn(target - self.head_tick, lambda _d, _t: None, CancelToken())
        self.cursor = self.head_tick
        self.review_mode = False

    def step_back(self, n: int = 1) -> None:
        """Enters review mode. Never calls `exec()`; there is no inverse."""
        self.cursor = max(0, self.cursor - n)
        self.review_mode = self.cursor != self.head_tick

    def goto(self, tick_index: int) -> None:
        clamped = max(0, min(tick_index, self._last_index()))
        if clamped > self.head_tick:
            self._require_not_review_mode("goto", tick_index)
            self.head_tick = self._advance_fn(clamped - self.head_tick, lambda _d, _t: None, CancelToken())
            self.cursor = self.head_tick
            self.review_mode = False
            return
        self.cursor = clamped
        self.review_mode = self.cursor != self.head_tick

    def jump_to_event(self, t_ns: int) -> None:
        self.goto(self.session.seek_ns(t_ns))

    def advance(
        self,
        n: int,
        *,
        on_progress: Callable[[int, int], None] | None = None,
        cancel: CancelToken | None = None,
    ) -> int:
        """Advance-N as ONE cancellable job. Returns the tick reached, which
        becomes `head_tick`."""
        self._require_not_review_mode("advance", n)
        reached = self._advance_fn(n, on_progress or (lambda _d, _t: None), cancel or CancelToken())
        self.head_tick = reached
        self.cursor = reached
        self.review_mode = False
        return reached

    def _require_not_review_mode(self, verb: str, arg: int) -> None:
        if self.review_mode:
            raise AuthoringError(
                expected="an explicit resume() choice before advancing past the head while rewound",
                found=f"{verb}({arg}) from cursor={self.cursor} while head_tick={self.head_tick}",
                where="adas_sim.view.transport.Transport",
                hint="call resume(ResumeOption.SKIP_TO_HEAD) or resume(ResumeOption.RECOMPUTE_FROM_ZERO) first",
            )

    def resume_options(self) -> tuple[NamedResumeOption, ...]:
        """Exactly two, both named. `RECOMPUTE_FROM_ZERO` is offered only
        when `session.deterministic`; otherwise it carries its `.reason`.
        Silently continuing from a rewound tick is not representable in this
        API -- that is the point (R-SIM-17)."""
        skip = NamedResumeOption(option=ResumeOption.SKIP_TO_HEAD)
        if self.session.deterministic:
            recompute = NamedResumeOption(option=ResumeOption.RECOMPUTE_FROM_ZERO)
        else:
            recompute = NamedResumeOption(
                option=ResumeOption.RECOMPUTE_FROM_ZERO,
                available=False,
                reason="session is not deterministic (a live sim run) -- recompute-from-0 would not reproduce it",
            )
        return (skip, recompute)

    def resume(self, option: ResumeOption) -> None:
        chosen = {o.option: o for o in self.resume_options()}[option]
        if not chosen.available:
            raise AuthoringError(
                expected="an available resume option", found=f"{option.value} ({chosen.reason})",
                where="adas_sim.view.transport.Transport.resume", hint="",
            )
        if option is ResumeOption.SKIP_TO_HEAD:
            self.cursor = self.head_tick
        else:
            self.head_tick = 0
            self.cursor = 0
        self.review_mode = False
