# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The CLOSED override verb list (sim_api_reference.md SS3.4, R-SIM-15).

Four verbs, forever: `const`, `hold`, `offset`, `scale`. There is no
expression language, no `python:`, no user-supplied callable -- the
reference console's per-argument mapping rules are the failure this
bounds. A fifth verb is a design change requiring a requirement, never a
runtime extension point.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from adas_sim.core.errors import AuthoringError


class OverrideVerb(StrEnum):
    CONST = "const"
    HOLD = "hold"
    OFFSET = "offset"
    SCALE = "scale"


#: `hold` freezes at the first-seen value; it needs no `value:` of its own.
#: Every other verb does.
_NO_VALUE_NEEDED = frozenset({OverrideVerb.HOLD})


@dataclass(frozen=True, slots=True)
class Override:
    """One override, addressable at a port or at a field path
    (`"egoDyn.vx"`) in a `Stage.overrides` mapping."""

    verb: OverrideVerb
    value: float | None = None  # required for const/offset/scale

    def __post_init__(self) -> None:
        if self.verb not in _NO_VALUE_NEEDED and self.value is None:
            raise AuthoringError(
                expected=f"a numeric value for verb '{self.verb.value}'", found="value: absent",
                where="Override", hint=f"'{self.verb.value}' requires value:; only 'hold' does not",
            )

    def apply(self, current: float, first: float) -> float:
        if self.verb is OverrideVerb.CONST:
            return self.value
        if self.verb is OverrideVerb.HOLD:
            return first
        if self.verb is OverrideVerb.OFFSET:
            return current + self.value
        return current * self.value  # OverrideVerb.SCALE -- the closed list's last member


def parse_override_verb(raw: str, *, where: str) -> OverrideVerb:
    """The closed-list gate: a verb outside the four is a load error, never
    a warning (`R-SIM-15`, `UT-C1c-17`)."""
    try:
        return OverrideVerb(raw)
    except ValueError as exc:
        raise AuthoringError(
            expected=f"one of: {', '.join(v.value for v in OverrideVerb)}", found=repr(raw), where=where,
            hint="there is no fifth verb -- no expression language, no python:, no callable (R-SIM-15)",
        ) from exc
