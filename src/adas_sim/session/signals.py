# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The one signal resolver (`NR-SIM-8`, api reference §2.3):
`<component>.<port>.<field>`, `source.*`, `truth.*`, `derived.*`.

Raw port fields resolve with **no registration**. A port name is itself dotted
(`N-2`), so resolution is the longest known port name that prefixes the
address, then a plain attribute walk over the remainder. Only a *computed*
signal -- one no ProPort carries, such as TTC -- registers, via `@signal`.

**Lives in `core/`, not `view/`**, so that every consumer can depend on it in
the normal direction: `check/`'s expectation evaluator is headless and must
not import something named `view/`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.session.history import FrameTree, HistoryView, LayerCtx
from adas_sim.session.tick import Tick
from adas_sim.config.project import ProjectModel

_SIGNALS: dict[str, tuple[Callable[..., object], str]] = {}  # name -> (func, unit)
_INDEX_RE = re.compile(r"^(\w+)\[(\d+)\]$")


def signal(name: str, *, unit: str = "") -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Registers a **computed** signal under the one address space
    (`NR-SIM-8`). `func(tick, ctx)` -- the same `(tick, ctx)` shape a layer
    provider gets (`sim_visualization_spec.md` §7.4's own example), so a
    computed signal can read history/project exactly like a layer can. A
    duplicate name raises naming both (`N-8`), same discipline as
    `layer_provider`."""

    def decorator(func: Callable[..., object]) -> Callable[..., object]:
        existing = _SIGNALS.get(name)
        if existing is not None:
            existing_func, _existing_unit = existing
            raise AuthoringError(
                expected=f"a signal name not already registered (currently "
                         f"{existing_func.__module__}.{existing_func.__qualname__})",
                found=f"{name!r} requested again by {func.__module__}.{func.__qualname__}",
                where="adas_sim.session.signals.signal",
                hint=f"rename one of the two signals ({existing_func.__module__}.{existing_func.__qualname__} "
                     f"and {func.__module__}.{func.__qualname__})",
            )
        _SIGNALS[name] = (func, unit)
        return func

    return decorator


def registered_signals() -> Mapping[str, tuple[Callable[..., object], str]]:
    return MappingProxyType(_SIGNALS)


def _find_port(tick: Tick, address: str) -> tuple[str, str] | None:
    """`(port_name, remaining_field_path)` for the **longest** entry in
    `tick.ports` that prefixes `address`, or `None`. Longest, not first: a
    port `"a.b"` and a port `"a.b.c"` can both exist, and only the longer
    one can be right for an address starting `"a.b.c."`."""
    best: str | None = None
    for port_name in tick.ports:
        if address == port_name or address.startswith(port_name + "."):
            if best is None or len(port_name) > len(best):
                best = port_name
    if best is None:
        return None
    return best, address[len(best):].lstrip(".")


def _walk_field_path(value: object, field_path: str, *, address: str) -> object:
    walked: list[str] = []
    for segment in field_path.split("."):
        match = _INDEX_RE.match(segment)
        attr_name = match.group(1) if match else segment
        # A protobuf enum field decodes to a bare int by default; captured
        # here (before `getattr`, off the PARENT message's own descriptor)
        # so an `equals: NORMAL`-style expectation compares a name against
        # a name, not a name against `1` -- the same resolver a plot panel
        # or the HUD reads, which want the name too, never a raw int.
        descriptor = getattr(value, "DESCRIPTOR", None)
        field_descriptor = descriptor.fields_by_name.get(attr_name) if descriptor is not None else None
        try:
            value = getattr(value, attr_name)
        except AttributeError:
            raise AuthoringError(
                expected=f"field {attr_name!r} on {'.'.join(walked) or 'the port message'}",
                found=f"no such field, resolving {address!r}",
                where="adas_sim.session.signals.resolve_tick",
                hint="check the field name against the port's schema",
            ) from None
        if match:
            index = int(match.group(2))
            try:
                value = value[index]
            except IndexError:
                raise AuthoringError(
                    expected=f"index {index} to exist in {attr_name!r} (len {len(value)})",
                    found=f"out of range, resolving {address!r}",
                    where="adas_sim.session.signals.resolve_tick", hint="",
                ) from None
        if field_descriptor is not None and field_descriptor.enum_type is not None:
            value = field_descriptor.enum_type.values_by_number[value].name
        walked.append(segment)
    return value


def resolve_tick(tick: Tick, address: str, *, ctx: LayerCtx | None = None) -> object:
    """One tick's value for `address` (`NR-SIM-8`). `derived.*` calls the
    registered function with `(tick, ctx)` -- `ctx` is required for those
    (`AuthoringError` naming the signal if omitted); every other prefix
    (`<component>.<port>`, `source.*`, `truth.*`) needs no `ctx` at all, so
    a live HUD reading a raw port field pays no project-resolution cost."""
    if address in _SIGNALS:
        func, _unit = _SIGNALS[address]
        if ctx is None:
            raise AuthoringError(
                expected="a LayerCtx (derived.* signals are computed, not raw ports)",
                found="ctx=None", where="adas_sim.session.signals.resolve_tick",
                hint=f"pass ctx=..., or call resolve_series (builds it), to resolve {address!r}",
            )
        return func(tick, ctx)

    found = _find_port(tick, address)
    if found is None:
        raise AuthoringError(
            expected="a registered derived.* signal, or an address prefixed by a real port name",
            found=repr(address), where="adas_sim.session.signals.resolve_tick",
            hint=f"known ports this tick: {sorted(tick.ports)}",
        )
    port_name, field_path = found
    message = tick.port(port_name).message
    if not field_path:
        return message
    if message is None:
        raise AuthoringError(
            expected=f"port {port_name!r} to carry a value", found="message is None (invalid this tick)",
            where="adas_sim.session.signals.resolve_tick", hint=f"resolving {address!r}",
        )
    return _walk_field_path(message, field_path, address=address)


def resolve_series(
    ticks: Sequence[Tick], address: str, *, project: str = "base",
) -> tuple[tuple[int, object], ...]:
    """`address`'s value at every tick, as `(tick.index, value)` pairs --
    what a timeline lane or plot panel plots in one call (`NR-SIM-8`: "one
    resolver, five consumers"). `ctx` (project + a growing history window,
    same shape `core/runner.build_scene` gives a layer provider) is built
    per tick **only** when `address` is a registered `derived.*` signal --
    a raw port field never pays for `ProjectModel.resolve`."""
    needs_ctx = address in _SIGNALS
    model = ProjectModel.resolve(project=project) if needs_ctx else None
    results = []
    for index, tick in enumerate(ticks):
        ctx = None
        if needs_ctx:
            ctx = LayerCtx(model=model, history=HistoryView(_ticks=tuple(ticks[:index + 1])), frames=FrameTree(tick.pose))
        results.append((tick.index, resolve_tick(tick, address, ctx=ctx)))
    return tuple(results)
