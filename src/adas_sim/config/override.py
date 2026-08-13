# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The CLOSED override verb list (sim_api_reference.md SS3.4, R-SIM-15).

Six verbs, forever: four arithmetic -- `const`, `hold`, `offset`, `scale` --
plus two structural, added at `S-C1cΔ` (`OD-8`): `select`, `drop`. There is
no expression language, no `python:`, no user-supplied callable -- an
open-ended per-argument mapping scheme is the failure this
bounds. A seventh verb is a design change requiring a requirement, never a
runtime extension point. The line that keeps the list closed: **an
override may destroy or attenuate information; it may never create an
entity** -- which is what rules out `insert`/`move`/`duplicate` on
principle, not on taste.

`select`/`drop` address a repeated element through the closed index
grammar (`contracts/binding.py`, index or `*` only, never a predicate) and
apply to real bytes there -- this module keeps only the vocabulary and the
arithmetic four's bare-float math.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from adas_sim.diagnostics.errors import AuthoringError


class OverrideVerb(StrEnum):
    CONST = "const"
    HOLD = "hold"
    OFFSET = "offset"
    SCALE = "scale"
    SELECT = "select"
    DROP = "drop"


#: `hold` freezes at the first-seen value; `select`/`drop` take their
#: target entirely from the address's own index/`*` (`contracts/binding.py`).
#: None of the three need a `value:` of their own -- every arithmetic verb
#: but `hold` does.
_NO_VALUE_NEEDED = frozenset({OverrideVerb.HOLD, OverrideVerb.SELECT, OverrideVerb.DROP})


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
                where="Override", hint=f"'{self.verb.value}' requires value: -- only "
                                        f"{'/'.join(v.value for v in _NO_VALUE_NEEDED)} do not",
            )

    def apply(self, current: float, first: float) -> float:
        """The four arithmetic verbs' bare-float math. `select`/`drop` are
        structural, never called here -- `contracts/binding.apply_override`
        branches to them before this method is ever reached."""
        if self.verb is OverrideVerb.CONST:
            return self.value
        if self.verb is OverrideVerb.HOLD:
            return first
        if self.verb is OverrideVerb.OFFSET:
            return current + self.value
        if self.verb is OverrideVerb.SCALE:
            return current * self.value
        raise AuthoringError(
            expected="an arithmetic verb (const/hold/offset/scale)", found=self.verb.value,
            where="Override.apply", hint="select/drop are structural -- contracts.binding.apply_override, not this method",
        )


def parse_override_verb(raw: str, *, where: str) -> OverrideVerb:
    """The closed-list gate: a verb outside the six is a load error, never
    a warning (`R-SIM-15`, `UT-C1c-17`)."""
    try:
        return OverrideVerb(raw)
    except ValueError as exc:
        raise AuthoringError(
            expected=f"one of: {', '.join(v.value for v in OverrideVerb)}", found=repr(raw), where=where,
            hint="there is no seventh verb -- no expression language, no python:, no callable (R-SIM-15)",
        ) from exc
