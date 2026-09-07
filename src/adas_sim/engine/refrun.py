# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-12`, `refrun` item (`SW-0048`..`SW-0050`): a candidate build run
side by side against a staged reference (`R-SIM-24`'s determinism axes,
applied to two DIFFERENT builds rather than two runs of one). `RefRun`
drives both from one resolved input set per tick; `first_divergence`
compares their recorded outputs field by field; the two roles' outputs are
recorded under distinguishable topic prefixes so a recording alone answers
which build produced what (`SW-0050`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

#: The only two roles a side-by-side run ever has -- never a third, since
#: nothing here compares more than one candidate against one reference.
Role = Literal["candidate", "reference"]


class TickSource(Protocol):
    """`F-EXEC-STUB`'s own shape: one build under test, driven one tick at
    a time."""

    def exec(self, inputs: Mapping[str, object]) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class RefRun:
    """`WP-12` (`SW-0048`): drives `candidate` and `reference` from one
    resolved input set per tick. `tick` resolves the inputs exactly once
    and hands the SAME mapping object to both -- "did both builds see the
    same input" is then true by construction (structural equality), never
    a runtime check this class has to perform."""

    candidate: TickSource
    reference: TickSource

    def tick(self, inputs: Mapping[str, object]) -> tuple[Mapping[str, object], Mapping[str, object]]:
        return self.candidate.exec(inputs), self.reference.exec(inputs)


@dataclass(frozen=True, slots=True)
class Divergence:
    """`WP-12` (`SW-0049`): the first tick/port/field where the two builds'
    outputs disagreed, and what each side actually produced."""

    tick: int
    port: str
    field: str
    candidate_value: object
    reference_value: object


def first_divergence(
    port_order: Sequence[str],
    candidate_ticks: Sequence[Mapping[str, Mapping[str, object]]],
    reference_ticks: Sequence[Mapping[str, Mapping[str, object]]],
) -> Divergence | None:
    """`WP-12` (`SW-0049`): walks ticks in order, then `port_order` (the
    declared manifest order, never a discovered one), then fields in a
    stable order -- returns the FIRST difference found, never a full diff.
    `None` when every tick agrees on every port and field."""
    for tick_index, (candidate_tick, reference_tick) in enumerate(zip(candidate_ticks, reference_ticks)):
        for port in port_order:
            candidate_fields = candidate_tick.get(port, {})
            reference_fields = reference_tick.get(port, {})
            for field in sorted(set(candidate_fields) | set(reference_fields)):
                candidate_value = candidate_fields.get(field)
                reference_value = reference_fields.get(field)
                if candidate_value != reference_value:
                    return Divergence(
                        tick=tick_index, port=port, field=field,
                        candidate_value=candidate_value, reference_value=reference_value,
                    )
    return None


def topic_for(role: Role, port: str) -> str:
    """`WP-12` (`SW-0050`): the topic a build's own output port is
    recorded under -- role-prefixed, so one flat recording still separates
    the two builds without a side-car index."""
    return f"{role}.{port}"
