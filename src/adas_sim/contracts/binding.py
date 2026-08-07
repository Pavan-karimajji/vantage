# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The override address grammar and its byte-level application (`S-C1cΔ`,
`OD-8`, `R-SIM-15`). `contracts/override.py` is the closed six-verb
vocabulary and the arithmetic four's bare-float math; this module is where
an address becomes structure and a verb meets real bytes.

**The address grammar, closed:** `port` · `port.field` ·
`port.repeated[i]` · `port.repeated[*]` · a field within either. Index and
`*` only, never a predicate -- `objects[?class=="truck"]` is an
expression, and an expression grammar is the over-configuration this
design exists to answer.

**Fixed-slot behaviour is keyed on a manifest attribute no real component
populates yet.** `select`/`drop` clear an addressed element **in place**
on a port whose manifest declares `fixed_slots=True` (compaction would
renumber every later index and break track association silently); they
**compact** (remove and shift) on `fixed_slots=False`. `PortSpec.
fixed_slots` exists as of `S-C1aΔ2` (build order #11), but no real
component's manifest sets it yet -- that is `S-C1d`'s own job (build
order #12, generating it from `conf/ports.yaml`), still pending -- so
today, every real `select`/`drop` is still a load error naming the port
and the undeclared attribute (`apply_override`'s own `fixed_slots=None`
branch). Never a default: `False` would mean "safe to compact" and `True`
would mean "safe to zero", and both are guesses about someone else's data
(`NR-SIM-4`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from adas_sim.contracts.component import ComponentManifest
from adas_sim.contracts.override import Override, OverrideVerb
from adas_sim.core.errors import AuthoringError, ContractError

#: One segment: a bare identifier, or an identifier indexed by a digit
#: string or `*`. Anything else -- a predicate, an operator, a slice --
#: fails this match outright (`UT-C1c-24`).
_SEGMENT_RE = re.compile(r"^(\w+)(?:\[(\d+|\*)\])?$")

Index = int | Literal["*"]


@dataclass(frozen=True, slots=True)
class AddressSegment:
    name: str
    index: Index | None = None

    def __repr__(self) -> str:
        return f"{self.name}[{self.index}]" if self.index is not None else self.name


@dataclass(frozen=True, slots=True)
class Address:
    """`port`, then zero or more field segments (`R-SIM-15`'s closed
    grammar) -- `path` is empty for a bare-port address."""

    raw: str
    port: str
    path: tuple[AddressSegment, ...] = ()

    def __repr__(self) -> str:
        return f"<Address {self.raw!r}>"


def parse_address(raw: str, *, where: str) -> Address:
    """The one place an override key becomes structure. A predicate-shaped
    segment (`objects[?class=="truck"]`) fails `_SEGMENT_RE` outright and
    is named alongside the closed grammar (`UT-C1c-24`); the port segment
    itself may never carry an index (a port is one message, never a list).
    """
    segments: list[AddressSegment] = []
    for part in raw.split("."):
        match = _SEGMENT_RE.match(part)
        if not match:
            raise AuthoringError(
                expected="port · port.field · port.repeated[i] · port.repeated[*] "
                         "(index or * only, never a predicate)",
                found=repr(raw), where=where,
                hint=f"{part!r} is not a valid address segment (R-SIM-15's closed index grammar)",
            )
        name, index_raw = match.group(1), match.group(2)
        index: Index | None = None if index_raw is None else ("*" if index_raw == "*" else int(index_raw))
        segments.append(AddressSegment(name=name, index=index))

    if segments[0].index is not None:
        raise AuthoringError(
            expected="the port segment to carry no index -- a port is one message, never a list",
            found=repr(raw), where=where,
            hint="index the field within the port, e.g. 'port.repeated[0]', not the port itself",
        )
    return Address(raw=raw, port=segments[0].name, path=tuple(segments[1:]))


def _match_component_ref(ref: str, *, known_ports: Iterable[str]) -> list[str] | None:
    """`None` when `ref` carries no `self.` prefix (already concrete, never
    matched against anything); otherwise every qualified name in
    `known_ports` whose segment after the stage prefix equals `ref`'s own
    port half."""
    if not ref.startswith("self."):
        return None
    wanted = ref[len("self."):]
    return [name for name in known_ports if name.partition(".")[2] == wanted]


def resolve_component_ref(ref: str, *, known_ports: Iterable[str], where: str) -> str:
    """Component-relative port binding (`R-SIM-21`, arch `D13`): `self.<port>`
    resolves to the one qualified address in `known_ports` -- this run's
    actual port universe (a recording's own topics, `S-B1Δ`) -- whose
    segment after the stage prefix equals `<port>`. A ref with no `self.`
    prefix is already concrete and passes through unchanged.

    Strict: zero or more than one match raises, naming `where` (the
    plug-in), the requested ref and every port actually known this run
    (`N-8`). For a caller that has not already established the port is part
    of this run (a layer's `requires=` gate), use `try_resolve_component_ref`
    instead -- this one is for a caller (`LayerCtx.port`) reached only after
    that gate already passed, where a miss is a real, unambiguous defect.
    """
    matches = _match_component_ref(ref, known_ports=known_ports)
    if matches is None:
        return ref
    if len(matches) != 1:
        raise AuthoringError(
            expected=f"exactly one port matching {ref!r} across this run's components",
            found=f"{len(matches)} matches: {sorted(matches)}" if matches else "no matching port",
            where=where,
            hint=f"known ports this run: {sorted(known_ports)}",
        )
    return matches[0]


def try_resolve_component_ref(ref: str, *, known_ports: Iterable[str], where: str) -> str | None:
    """The tolerant half `resolve_component_ref` deliberately isn't: `None`
    when `ref` matches no known port at all, rather than raising.

    **Why zero matches must not raise (checked with the user, `S-B1Δ`).**
    Block 1 discovers layer providers by import into one process-global
    registry (`R-VAR-2`) with no live component manifest and no per-session
    plug-in scoping yet (that arrives at `S-C8`/`S-D3`) -- so "this port does
    not exist anywhere" and "this recording's pipeline never wired that
    component at all" are indistinguishable from a single recording's own
    topic set alone. Treating a zero-match as a hard error would crash every
    layer provider the moment it renders a recording that simply does not
    include the component it draws for, which is the ordinary case, not a
    bug. **More than one match stays an unambiguous, same-run collision and
    still raises** -- that evidence does not depend on a live manifest to be
    real.
    """
    matches = _match_component_ref(ref, known_ports=known_ports)
    if matches is None:
        return ref
    if not matches:
        return None
    if len(matches) > 1:
        raise AuthoringError(
            expected=f"at most one port matching {ref!r} across this run's components",
            found=f"{len(matches)} matches: {sorted(matches)}",
            where=where,
            hint=f"known ports this run: {sorted(known_ports)}",
        )
    return matches[0]


def resolve(ref: str, *, component: str, manifest: ComponentManifest, where: str) -> str:
    """`S-C1cΔ`'s resolver (added, sim build queue row 4 sub-row
    4, `UT-C1c-22`/`UT-C1c-23`) -- the one this module's own delta note
    names: `Pipeline` already knows every manifest in a run and already
    builds the concrete address (`f"{stage.name}.{port.name}"`), so
    resolution happens **once, at load** (`R-SIM-21`), against the ONE
    component `ref` is relative to -- never searched for across a run's
    whole port universe the way `resolve_component_ref` (below) must, for
    the different reason given in its own docstring.

    `ref` a bare `<port>` (no `self.` prefix) is already concrete and
    passes through unchanged, same convention as `resolve_component_ref`.
    `self.<port>` resolves to `f"{component}.{port}"` **iff** `<port>`
    exactly matches one of `manifest.inputs`/`manifest.outputs`' own
    `PortSpec.name` -- no search, no ambiguity possible, because `component`
    already names the one manifest this call resolves against. A `<port>`
    matching neither raises `AuthoringError` naming the reference, `component`
    and every port `manifest` actually declares (`N-8`, `UT-C1c-23`) --
    never a sentinel a caller could mistake for "absent".

    **Not `resolve_component_ref`, on purpose (`S-B1Δ`'s own note).** That
    resolver exists because a layer provider replays from a `Session` alone,
    with no live `Pipeline` in the loop (`R-SIM-13`) -- it stays exactly as
    it is. This one is for a caller that already holds a `Pipeline` (`sim
    check`'s expectation evaluator, today's own consumer -- `S-D3`
    viewpoints and `S-D7` export column selection remain unwired: neither
    has an established "which stage is `self`" convention documented
    anywhere, and inventing one here would be a scenario/pipeline-file
    schema decision, not a resolver-wiring one).
    """
    if not ref.startswith("self."):
        return ref
    port = ref[len("self."):]
    declared = tuple(spec.name for spec in (*manifest.inputs, *manifest.outputs))
    if port not in declared:
        raise AuthoringError(
            expected=f"one of {component!r}'s declared ports: {sorted(declared)}",
            found=repr(ref), where=where,
            hint=f"{component!r} is the stage {ref!r} resolves relative to",
        )
    return f"{component}.{port}"


def _descend(message: object, path: tuple[AddressSegment, ...]) -> object:
    obj = message
    for segment in path:
        value = getattr(obj, segment.name)
        obj = value[segment.index] if segment.index is not None else value
    return obj


def _resolve_scalar_target(message: object, path: tuple[AddressSegment, ...], *, address: str) -> tuple[object, str, int | None]:
    """`(container, attr_name, index)` for an arithmetic verb's target --
    the whole port (`path` empty) has no single number to override, and
    `[*]` means every element, which only `select`/`drop` operate on."""
    if not path:
        raise AuthoringError(
            expected="a field path for an arithmetic override (const/hold/offset/scale)",
            found=f"{address!r} addresses the whole port", where="contracts.binding.apply_override",
            hint="a whole-message port has no single number to override -- address a field",
        )
    last = path[-1]
    if last.index == "*":
        raise AuthoringError(
            expected="a single index for an arithmetic override, never '*'",
            found=f"{address!r} addresses every element", where="contracts.binding.apply_override",
            hint="'*' means every element -- only select/drop operate on a whole set at once",
        )
    container = _descend(message, path[:-1])
    return container, last.name, last.index


def _read_scalar(container: object, attr_name: str, index: int | None) -> float:
    value = getattr(container, attr_name)
    return value[index] if index is not None else value


def _write_scalar(container: object, attr_name: str, index: int | None, value: float) -> None:
    if index is not None:
        getattr(container, attr_name)[index] = value
    else:
        setattr(container, attr_name, value)


def _resolve_repeated_target(message: object, path: tuple[AddressSegment, ...], *, address: str) -> tuple[object, Index]:
    """The repeated container + index/`*` for `select`/`drop`. The final
    segment must itself carry an index -- `port.repeated` with no
    `[i]`/`[*]` addresses a whole field, not an element, and a structural
    verb only ever touches elements."""
    if not path or path[-1].index is None:
        raise AuthoringError(
            expected="an indexed repeated field for select/drop, e.g. 'port.repeated[i]' or '[*]'",
            found=repr(address), where="contracts.binding.apply_override",
            hint="select/drop address one or every element of a repeated field, never a bare field",
        )
    last = path[-1]
    container = getattr(_descend(message, path[:-1]), last.name)
    return container, last.index


def _clear_element_in_place(container: object, index: int) -> None:
    """A message element clears itself; a scalar element resets to its own
    type's zero value -- either way the slot survives, never renumbered."""
    item = container[index]
    if hasattr(item, "Clear"):
        item.Clear()
    else:
        container[index] = type(item)()


def _apply_structural(container: object, index: Index, verb: OverrideVerb, *, fixed_slots: bool) -> None:
    length = len(container)
    if verb is OverrideVerb.SELECT:
        keep = set(range(length)) if index == "*" else {index}
        targets = [i for i in range(length) if i not in keep]
    else:  # OverrideVerb.DROP
        targets = list(range(length)) if index == "*" else [index]

    if fixed_slots:
        for i in targets:
            _clear_element_in_place(container, i)
    else:
        for i in sorted(targets, reverse=True):  # highest index first -- del must not renumber an unvisited target
            del container[i]


def apply_override(
    payload: bytes, message_cls: type, address: Address, override: Override, *,
    first_seen: float | None = None, fixed_slots: bool | None = None,
) -> tuple[bytes, float | None]:
    """Decodes `payload` as `message_cls`, applies `override` at `address`,
    re-serializes. Returns `(new_payload, first_seen_for_next_call)` --
    `hold`'s own memory is the caller's to keep (one entry per stage +
    address, `Pipeline`'s own job), never this function's: it stays pure
    and independently testable either way.

    `fixed_slots` governs `select`/`drop` only (`NR-SIM-4`): `None` means
    the port's manifest does not declare it, which is a `ContractError`
    naming the port and the missing attribute -- never a guessed default.
    """
    message = message_cls()
    message.ParseFromString(payload)

    if override.verb in (OverrideVerb.SELECT, OverrideVerb.DROP):
        if fixed_slots is None:
            raise ContractError(
                expected=f"the port's manifest to declare fixed_slots for a {override.verb.value} override",
                found="fixed_slots absent from the manifest", where=f"address {address.raw!r}",
                hint="drop/select on a repeated field needs fixed_slots declared true or false -- "
                     "neither may be guessed (NR-SIM-4); arrives at S-C1d",
            )
        container, index = _resolve_repeated_target(message, address.path, address=address.raw)
        _apply_structural(container, index, override.verb, fixed_slots=fixed_slots)
        return message.SerializeToString(), first_seen

    container, attr_name, index = _resolve_scalar_target(message, address.path, address=address.raw)
    current = _read_scalar(container, attr_name, index)
    effective_first = current if first_seen is None else first_seen
    new_value = override.apply(current=current, first=effective_first)
    _write_scalar(container, attr_name, index, new_value)
    return message.SerializeToString(), effective_first
