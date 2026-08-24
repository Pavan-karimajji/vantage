# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Duration estimate with its own stated accuracy (`SW-0272`, `IMP-0272`,
`ANL-SW-43`).

`OQ-14`, closed 2026-08-13: no absolute accuracy bound was ever supplied for
this row, so -- same discipline `ANL-SW-63`'s throughput bound already
used -- the bound is **seeded** from the first real campaign on SysReq
§18.0's reference configuration rather than awaited. `estimate_duration`
always returns a number; `accuracy_factor` is `None` until `seed()` has
recorded at least one real measurement for a shape, honestly distinguishing
"no campaign has run yet" from "the campaign measured perfect accuracy."
`record_measurement` is what a later campaign calls after each real run,
updating the band and reporting whether THIS run's own estimate fell inside
the factor a prior campaign already seeded (`ANL-SW-43`'s own mechanism:
failable from the second measurement, never merely observed)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

#: A per-tick, per-stage cost used only when no history exists at all for any
#: shape -- a starting guess, never presented as measured (`accuracy_factor`
#: stays `None` in that case).
_DEFAULT_PER_TICK_PER_STAGE_S = 0.001

#: The very first measurement for a shape has no spread to compute a factor
#: from (`worst_factor` over one point is always exactly `1.0`, i.e. "no
#: tolerance at all," which is not what "seeded" is supposed to mean).
#: `OQ-14`'s own "declared from the first campaign" therefore starts the
#: band at this stated, conservative margin -- real variance takes over
#: (and only ever WIDENS it, never narrows below this floor) once a second
#: measurement exists to compute one from.
_SEED_MARGIN_FACTOR = 1.5


@dataclass(frozen=True, slots=True)
class Shape:
    """What "a run of the same shape" means for this estimator: stage count
    and tick count -- the two knobs that dominate wall-clock cost in this
    package's own architecture (`SI-09`, `R-SIM-19`: isolation is per
    subprocess/recording, not per stage, so cost scales with both)."""

    stage_count: int
    tick_count: int

    def key(self) -> str:
        return f"{self.stage_count}x{self.tick_count}"


@dataclass(frozen=True, slots=True)
class Measurement:
    shape: Shape
    measured_s: float


@dataclass(frozen=True, slots=True)
class DurationEstimate:
    """`estimate_s` is always present. `accuracy_factor` is the
    multiplicative band the estimate has been measured to fall within on
    the reference configuration (`|measured/estimate|` and its reciprocal,
    whichever is larger) -- `None` when no measurement has ever seeded a
    band for this shape (`R-SIM-25`: unknown, never a plausible-looking
    default). `seeded_from` names the run that produced the current band,
    for the "seeding run marked" half of `ANL-SW-43`'s own closed note."""

    estimate_s: float
    accuracy_factor: float | None
    seeded_from: str | None


def _load_history(path: Path) -> dict[str, list[dict[str, object]]]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_history(path: Path, history: dict[str, list[dict[str, object]]]) -> None:
    path.write_text(json.dumps(history, indent=2, sort_keys=True), encoding="utf-8")


def estimate_duration(shape: Shape, *, history_path: Path | None = None) -> DurationEstimate:
    """`shape`'s estimate. With no history file, or no entry for this exact
    shape, the estimate falls back to `_DEFAULT_PER_TICK_PER_STAGE_S` and
    `accuracy_factor` is `None` -- honest "never run before," not a
    fabricated confidence. With history, the estimate is the mean of every
    prior measurement's own per-tick-per-stage cost for this shape, and
    `accuracy_factor` is the worst ratio any single measurement's actual
    duration diverged from that mean by."""
    history = _load_history(history_path) if history_path is not None else {}
    entries = history.get(shape.key(), [])
    if not entries:
        estimate_s = _DEFAULT_PER_TICK_PER_STAGE_S * shape.stage_count * shape.tick_count
        return DurationEstimate(estimate_s=estimate_s, accuracy_factor=None, seeded_from=None)

    measured = [float(e["measured_s"]) for e in entries]
    mean = sum(measured) / len(measured)
    worst_factor = _SEED_MARGIN_FACTOR
    for value in measured:
        if value <= 0 or mean <= 0:
            continue
        worst_factor = max(worst_factor, value / mean, mean / value)
    seeded_from = str(entries[0].get("run_id", "")) or None
    return DurationEstimate(estimate_s=mean, accuracy_factor=worst_factor, seeded_from=seeded_from)


def record_measurement(
    shape: Shape, measured_s: float, *, run_id: str, history_path: Path,
) -> DurationEstimate:
    """Appends one real measurement for `shape` and returns the estimate
    computed AFTER including it -- the seeding mechanism `ANL-SW-43`
    describes: the first call for a shape has no prior band (`accuracy_
    factor=None` on the estimate this same call would have produced before
    appending), and every call from the second seeds/tightens the band the
    next estimate is checked against."""
    history = _load_history(history_path)
    entries = history.setdefault(shape.key(), [])
    entries.append({"measured_s": measured_s, "run_id": run_id})
    _save_history(history_path, history)
    return estimate_duration(shape, history_path=history_path)


def within_band(estimate: DurationEstimate, measured_s: float) -> bool:
    """`ANL-SW-43`'s own pass/fail: `True` when no band has been seeded yet
    (nothing to fail against -- the seeding run itself always passes), else
    whether `measured_s` falls within `estimate.accuracy_factor` of
    `estimate.estimate_s` in either direction."""
    if estimate.accuracy_factor is None or estimate.estimate_s <= 0:
        return True
    ratio = measured_s / estimate.estimate_s
    return (1.0 / estimate.accuracy_factor) <= ratio <= estimate.accuracy_factor
