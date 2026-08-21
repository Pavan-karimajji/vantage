# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`IMP-0193`/`SW-0193` -- the closed unit vocabulary an ingest map's
`provides:` entry may name (`unit:`), each resolving to a **factor and an
offset** applied so `value_in_port_unit = value * factor + offset`
(`R-SIM-23`, `CN-0309`'s deliberate widening of "renames and tags only").

`ANL-SW-36` (`IMP-0202`) enforces the boundary this widening must not
cross: this is the *only* file under `adas_sim/ingest/**` permitted to
contain an arithmetic operator token, and the only two operations are the
multiply-and-add above -- never a unit *conversion pipeline*, never a
per-signal formula. A unit not in `_UNITS` is refused, naming what was
asked for and the closed table, rather than silently accepting an
arbitrary factor typed in a map (which would turn `provides:` into an
expression language one entry at a time).

`INSP-SW-03` reviews `_UNITS` against this checklist by hand:
  1. every entry's `base` is itself a key in `_UNITS` (closed under
     composition -- resolving a unit never chases an undeclared name);
  2. `factor`/`offset` are literal constants, never derived from another
     row at import time (no unit is defined "in terms of" another's
     current value, which would make the table order-dependent);
  3. an angular unit's base is `rad` and a temperature unit's base is
     `kelvin` -- the two families in this project with a legitimate
     `offset != 0`; every other family's `offset` is `0.0`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from adas_sim.diagnostics.errors import AuthoringError


@dataclass(frozen=True, slots=True)
class Unit:
    """`value_in_base = value * factor + offset`."""

    name: str
    base: str
    factor: float = 1.0
    offset: float = 0.0

    def __repr__(self) -> str:
        return f"<Unit {self.name!r} -> {self.base!r} x{self.factor}+{self.offset}>"


#: Closed by convention until `check_closed_sets.py`/`ANL-SW-24` grows an
#: entry for it (`Rung`/`MergePolicy`/`ErrorKind`'s own current state,
#: `WP-11`'s Exit note) -- `units` is not one of the six `SV-8` vocabularies
#: (those are cross-cutting bus/mutate enums), so its closure is `ANL-SW-36`
#: (no operator outside this file) plus `INSP-SW-03`'s manual review, not a
#: schema comparison.
_UNITS: dict[str, Unit] = {
    "unitless": Unit("unitless", "unitless"),
    "m": Unit("m", "m"),
    "km": Unit("km", "m", factor=1000.0),
    "mm": Unit("mm", "m", factor=0.001),
    "m_s": Unit("m_s", "m_s"),
    "km_h": Unit("km_h", "m_s", factor=1.0 / 3.6),
    "mph": Unit("mph", "m_s", factor=0.44704),
    "m_s2": Unit("m_s2", "m_s2"),
    "rad": Unit("rad", "rad"),
    "deg": Unit("deg", "rad", factor=math.pi / 180.0),
    "rad_s": Unit("rad_s", "rad_s"),
    "deg_s": Unit("deg_s", "rad_s", factor=math.pi / 180.0),
    "kelvin": Unit("kelvin", "kelvin"),
    "celsius": Unit("celsius", "kelvin", offset=273.15),
}


def resolve_unit(name: str, *, where: str) -> Unit:
    """The one lookup every caller in this package goes through -- never a
    raw `factor:`/`offset:` typed directly into a map (that would make the
    table's closure meaningless: anyone could still supply an arbitrary
    pair). A name outside `_UNITS` is an `AuthoringError` naming the closed
    table, never a guessed identity conversion."""
    unit = _UNITS.get(name)
    if unit is None:
        raise AuthoringError(
            expected=f"a unit from the closed table {sorted(_UNITS)}", found=repr(name), where=where,
            hint="the unit vocabulary is closed (R-SIM-23) -- add a real, reviewed entry to "
                 "adas_sim/ingest/units.py rather than a per-map conversion",
        )
    return unit


def factor_offset(name: str, *, where: str) -> tuple[float, float]:
    unit = resolve_unit(name, where=where)
    return unit.factor, unit.offset
