# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The reconciling warning summary (`SW-0130`, `IMP-0130`): every run ends
with a compact table of warning/error counts by category, and the totals
reconcile EXACTLY with `diagnostics/logging.py::log`'s own structured
output -- because the summary is counted from those same lines, never from
a second, independently-incremented counter that could drift from them
(`R-REQ-1`'s "no drift" principle applied to a run's own diagnostics: a
mismatch between the two would itself be a bug in this module, so there is
only one number to get right)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: `diagnostics/logging.py::log`'s own fixed field order (N-10): the level
#: token is the second whitespace-separated field, `event=<name>` always
#: present. Matched positionally plus by prefix, not by a full-line regex,
#: so a `msg=` field containing the substring `"WARN"` cannot be mistaken
#: for the level column.
_COUNTED_LEVELS = ("WARN", "ERROR")


@dataclass(frozen=True, slots=True)
class WarningSummary:
    """`counts` is category (the log line's own `event=` value) -> number of
    `WARN`/`ERROR` lines carrying it. `total` is `sum(counts.values())` --
    never stored independently, so it cannot itself drift from `counts`."""

    counts: Sequence[tuple[str, int]]  # sorted by category, for a stable printed order
    total: int

    def as_mapping(self) -> dict[str, int]:
        return dict(self.counts)


def _event_of(log_line: str) -> str | None:
    for token in log_line.split():
        if token.startswith("event="):
            return token[len("event=") :]
    return None


def _level_of(log_line: str) -> str | None:
    parts = log_line.split(maxsplit=2)
    if len(parts) < 2:
        return None
    level = parts[1].strip()
    return level if level in _COUNTED_LEVELS else None


def summarize(log_lines: Sequence[str]) -> WarningSummary:
    """Every `WARN`/`ERROR` line in `log_lines` (`diagnostics/logging.py::
    log`'s own emitted text, one call site's output per line), counted by
    its `event=` category. A line whose level is neither `WARN` nor `ERROR`
    (i.e. `INFO`) is not counted -- this is a WARNING summary, not a full
    log digest."""
    counts: dict[str, int] = {}
    for line in log_lines:
        if _level_of(line) is None:
            continue
        event = _event_of(line)
        if event is None:
            continue
        counts[event] = counts.get(event, 0) + 1
    ordered = tuple(sorted(counts.items()))
    return WarningSummary(counts=ordered, total=sum(counts.values()))


def format_summary(summary: WarningSummary) -> str:
    """The one line-per-category rendering both `cli/` and a script's own
    `print(format_summary(...))` use -- `sim explain`/evidence's own "one
    producer" shape applied to this run-end report."""
    if summary.total == 0:
        return "warnings: none"
    lines = [f"warnings: {summary.total} total"]
    for category, count in summary.counts:
        lines.append(f"  {category:<20} {count}")
    return "\n".join(lines)


def reconciles(summary: WarningSummary, log_lines: Sequence[str]) -> bool:
    """`SW-0130`'s own Accept, callable directly: `summary`'s counts equal a
    fresh count taken from `log_lines` right now. Exists so a caller (or a
    test) states the reconciliation check as one call rather than
    re-deriving `summarize(log_lines) == summary` by hand."""
    return summary == summarize(log_lines)
