# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-11 graph` -- grid derivation and cycle detection (`WP-20`).

`derive_step`/`check_period_multiples` are `graph/build.py::
_compute_base_grid_ns`/`_require_multiple`'s own logic, relocated
(`IMP-0063`/`IMP-0172`, `DEDUPE`) -- `build.py` keeps calling through to
these two rather than a second copy, so nothing importing the old private
names breaks.

`check_zero_delay_cycles` is genuinely new (`IMP-0074`). Today's wiring
grammar (`Stage.inputs`, `build.py::_validate_wiring`) only ever references
an EARLIER-declared stage -- `_validate_wiring`'s own forward-reference
check already refuses anything else -- so a same-tick cycle is already
structurally impossible: there is no "previous-tick"/delayed reference
syntax to close a loop with. This function proves that invariant rather
than searching for a cycle nothing can produce yet. `SW-0074`'s Accept
clause also names "a loop broken by a one-step delay loads" -- that half is
a real wiring-grammar addition (a delayed/previous-tick reference shape)
belonging to whichever `WP` actually adds feedback wiring; naming it here
rather than inventing a delay syntax as a side effect of this check.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import reduce
from math import gcd

from adas_sim.diagnostics.errors import AuthoringError


def derive_step(periods: Sequence[int]) -> int:
    """`R-SIM-18`: the base grid is the GCD of every declared (nonzero)
    period -- derived, never configured, never rounded. No declared periods
    at all -> no grid (`0`)."""
    nonzero = [p for p in periods if p > 0]
    if not nonzero:
        return 0
    return reduce(gcd, nonzero)


def check_period_multiples(period_ns: int, base_grid_ns: int, *, stage_name: str) -> None:
    """Every declared period must be an integer multiple of the derived
    base grid. Tautologically true for a grid that IS the GCD of the set it
    derives from -- kept anyway because `R-SIM-18` states the invariant
    explicitly and a future non-GCD grid source could make this reachable
    (`build.py::_require_multiple`'s own docstring, unchanged by the move)."""
    if period_ns % base_grid_ns != 0:
        raise AuthoringError(
            expected=f"period_ns to be an integer multiple of the base grid ({base_grid_ns} ns)",
            found=f"stage '{stage_name}' period_ns={period_ns}",
            where="Pipeline base grid (R-SIM-18)",
            hint=f"base grid {base_grid_ns} ns is the GCD of every stage's declared period_ns",
        )


def check_zero_delay_cycles(
    stage_names_in_order: Sequence[str], inputs_by_stage: Mapping[str, Mapping[str, str]],
) -> None:
    """`SW-0074`: refuse a same-tick cycle, naming every stage in the loop
    in traversal order. A `"source.*"` reference and a reference to an
    undeclared stage are both skipped -- both are `_validate_wiring`'s own
    concern, and a name absent from `inputs_by_stage`'s own key set cannot
    participate in a cycle by definition."""
    index = {name: i for i, name in enumerate(stage_names_in_order)}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stage: str, path: list[str]) -> None:
        if stage in visited:
            return
        visiting.add(stage)
        path.append(stage)
        for ref in inputs_by_stage.get(stage, {}).values():
            producer, _, _ = ref.partition(".")
            if producer == "source" or producer not in index:
                continue
            if producer in visiting:
                loop = path[path.index(producer):] + [producer]
                raise AuthoringError(
                    expected="no zero-delay cycle in the wiring graph",
                    found=" -> ".join(loop), where="pipeline stages",
                    hint="break the loop with a one-step delay (not yet a supported wiring "
                         "form) or remove the cyclic reference",
                )
            visit(producer, path)
        path.pop()
        visiting.discard(stage)
        visited.add(stage)

    for name in stage_names_in_order:
        visit(name, [])
