# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The closed five-verb fault vocabulary (`sim_scenarios_and_expectations.md`
SS9.2, `R-SIM-8`): `drop` · `stale` · `delay` · `invalidate` · `corrupt` --
the set of ways `PortValue`'s four metadata fields (`valid`, `updated`, its
capture stamp, its payload) can be made to lie, *derived* from `PortValue`'s
own shape rather than invented. A sixth verb is a design change, never a
runtime extension point -- the same discipline `contracts/override.py`
applies to its own six.

**Faults reuse the override address grammar** (`contracts/binding.py`) -- a
third addressing scheme for the same objects is how a tool becomes
inconsistent (`NR-SIM-8`). `corrupt` specifically reuses the override
`CONST` verb's own byte-level mutation (`apply_override`): a corrupted
field is exactly a const override, tagged as a fault rather than a
deliberate what-if -- never a second byte-mutation mechanism.

**Wired into `Pipeline.exec`/`step`** (`Pipeline._apply_stimulus_faults`,
S-C3 follow-up): this module stays the vocabulary, the load-time
validation and the pure per-tick effect on one `PortValue` -- the
injection point applies it to the STIMULUS, before any stage sees it
(SS9.2's own "a failure of the sensor or the transport"), the same way
`Pipeline._apply_input_overrides` applies an override to a stage's own
input. Not yet wired: a fault's *record* side -- landing in the run
manifest, tagging its topic `origin: overridden`, a HUD badge (tracked
separately, `sim_implementation_plan.md`'s own `S-C3` gate).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from adas_sim.contracts.binding import apply_override, parse_address
from adas_sim.contracts.override import Override, OverrideVerb
from adas_sim.core.errors import AuthoringError, InternalError
from adas_sim.core.tick import PortValue


class FaultVerb(StrEnum):
    DROP = "drop"
    STALE = "stale"
    DELAY = "delay"
    INVALIDATE = "invalidate"
    CORRUPT = "corrupt"


#: `corrupt` needs the replacement value it reuses from `Override(CONST)`;
#: `delay` needs its latency in seconds. `drop`/`stale`/`invalidate` are
#: pure metadata flips and need none.
_VALUE_REQUIRED = frozenset({FaultVerb.CORRUPT, FaultVerb.DELAY})

_ALLOWED_FAULT_KEYS = frozenset({"verb", "address", "value", "from_s", "to_s", "after_tick"})


@dataclass(frozen=True, slots=True)
class Fault:
    """One `run.faults:` entry: a verb, an address (the override grammar),
    a value where the verb needs one, and exactly one window --
    `from_s`+`to_s`, or `after_tick` (SS9.2: "each fault carries a
    window")."""

    verb: FaultVerb
    address: str
    value: float | None = None
    from_s: float | None = None
    to_s: float | None = None
    after_tick: int | None = None

    def __post_init__(self) -> None:
        if self.verb in _VALUE_REQUIRED and self.value is None:
            raise AuthoringError(
                expected=f"a numeric value for verb '{self.verb.value}'", found="value: absent",
                where="Fault", hint=f"'{self.verb.value}' requires value: -- only "
                                     f"{'/'.join(v.value for v in FaultVerb if v not in _VALUE_REQUIRED)} do not",
            )
        has_from, has_to, has_after = self.from_s is not None, self.to_s is not None, self.after_tick is not None
        if has_from != has_to:
            raise AuthoringError(
                expected="from_s and to_s together", found=f"from_s={self.from_s} to_s={self.to_s}",
                where="Fault", hint="a window is either both from_s/to_s, or after_tick alone",
            )
        has_range = has_from and has_to
        if has_range == has_after:  # neither declared, or both declared
            raise AuthoringError(
                expected="exactly one window: from_s+to_s, or after_tick",
                found="both declared" if has_range else "neither declared", where="Fault",
                hint="every fault carries a window (SS9.2)",
            )

    def active_at(self, *, t_s: float, tick_index: int) -> bool:
        if self.after_tick is not None:
            return tick_index >= self.after_tick
        return self.from_s <= t_s <= self.to_s


def parse_fault_verb(raw: str, *, where: str) -> FaultVerb:
    """The closed-list gate: a verb outside the five is a load error naming
    the closed set, never a warning (`UT-C3-8`'s "a sixth fault name is a
    schema error")."""
    try:
        return FaultVerb(raw)
    except ValueError as exc:
        raise AuthoringError(
            expected=f"one of: {', '.join(v.value for v in FaultVerb)}", found=repr(raw), where=where,
            hint="the fault vocabulary is closed at five, derived from PortValue's own fields (SS9.2)",
        ) from exc


def parse_fault(raw: Mapping[str, object], *, where: str) -> Fault:
    extra = set(raw) - _ALLOWED_FAULT_KEYS
    if extra:
        raise AuthoringError(
            expected=f"only {sorted(_ALLOWED_FAULT_KEYS)} in a fault entry",
            found=f"also has: {sorted(extra)}", where=where, hint="",
        )
    verb = parse_fault_verb(raw.get("verb"), where=where)
    address = raw.get("address")
    if not address:
        raise AuthoringError(expected="an 'address:' (the override grammar)", found=repr(address), where=where, hint="")
    parse_address(address, where=where)  # grammar validated now; re-resolved when actually applied
    value = raw.get("value")
    return Fault(
        verb=verb, address=str(address), value=float(value) if value is not None else None,
        from_s=raw.get("from_s"), to_s=raw.get("to_s"), after_tick=raw.get("after_tick"),
    )


def apply_fault(
    port_value: PortValue, fault: Fault, *, t_s: float, tick_index: int,
    first_active_t_s: float | None = None, message_cls: type | None = None,
) -> tuple[PortValue, float | None]:
    """`port_value`'s faulted form this tick, and the `first_active_t_s` to
    thread into the next call -- `stale`'s own cross-tick memory (its
    `age_s` must grow across ticks, `UT-C3-8`), mirroring
    `apply_override`'s `first_seen`: this function stays pure, the caller
    keeps the state. Returns `(port_value, None)` unchanged when the
    fault's window is not active this tick.

    `message_cls` is required only for `corrupt`: `apply_override`'s own
    `CONST` verb performs the actual byte mutation (SS9.2), so this
    function never re-implements one.
    """
    if not fault.active_at(t_s=t_s, tick_index=tick_index):
        return port_value, None

    active_since = t_s if first_active_t_s is None else first_active_t_s

    if fault.verb is FaultVerb.DROP:
        # "the port does not arrive" -- no bytes, no decoded value either.
        result = PortValue(
            name=port_value.name, message=None, origin="overridden", valid=False, updated=False, t_ns=port_value.t_ns,
        )
    elif fault.verb is FaultVerb.STALE:
        result = PortValue(
            name=port_value.name, message=port_value.message, origin="overridden", valid=port_value.valid,
            updated=False, hold_age_s=t_s - active_since, t_ns=port_value.t_ns,
        )
    elif fault.verb is FaultVerb.DELAY:
        capture_ns = port_value.t_ns - int(fault.value * 1_000_000_000)
        result = PortValue(
            name=port_value.name, message=port_value.message, origin="overridden", valid=port_value.valid,
            updated=port_value.updated, capture_ns=capture_ns, t_ns=port_value.t_ns,
        )
    elif fault.verb is FaultVerb.INVALIDATE:
        # "valid=False with bytes still present" -- the payload survives,
        # only the metadata lies (a sensor reporting its own fault, SS9.2).
        result = PortValue(
            name=port_value.name, message=port_value.message, origin="overridden", valid=False,
            updated=port_value.updated, t_ns=port_value.t_ns,
        )
    elif fault.verb is FaultVerb.CORRUPT:
        if message_cls is None:
            raise AuthoringError(
                expected="message_cls= (corrupt reuses apply_override's byte-level CONST mutation)",
                found="message_cls=None", where="adas_sim.contracts.fault.apply_fault", hint="",
            )
        address = parse_address(fault.address, where=f"fault address {fault.address!r}")
        new_payload, _ = apply_override(
            port_value.raw_bytes, message_cls, address, Override(verb=OverrideVerb.CONST, value=fault.value),
        )
        result = PortValue(
            name=port_value.name, message=new_payload, origin="overridden", valid=True,
            updated=port_value.updated, t_ns=port_value.t_ns,
            schema_bytes=port_value.schema_bytes, schema_name=port_value.schema_name,
        )
    else:  # pragma: no cover -- exhaustive over the closed FaultVerb
        raise InternalError(
            expected="a recognised FaultVerb", found=repr(fault.verb),
            where="adas_sim.contracts.fault.apply_fault", hint="",
        )

    return result, active_since
