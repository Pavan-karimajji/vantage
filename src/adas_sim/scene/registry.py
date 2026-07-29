# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`@layer_provider`, `@inspector_fields`, `@signal` -- discovery **by
import** (sim_api_reference.md §5, §6.4's registry note). A component adds a
layer by existing: importing the module that defines a decorated function is
what registers it, so there is no central roster to keep in sync
(`R-VAR-2`'s "no central roster" principle, extended from components to
layers).
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from adas_sim.core.errors import AuthoringError


@dataclass(frozen=True, slots=True)
class LayerProviderEntry:
    id: str
    func: Callable[..., object]
    module: str
    qualname: str
    group: str = ""
    requires: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return f"<LayerProviderEntry {self.id!r} from {self.module}.{self.qualname}>"


_PROVIDERS: dict[str, LayerProviderEntry] = {}
_INSPECTOR_FIELDS: dict[Callable[..., object], tuple[str, ...]] = {}
_SIGNALS: dict[str, Callable[..., object]] = {}


def layer_provider(
    layer_id: str, *, group: str = "", requires: Sequence[str] = ()
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Registers `func` under `layer_id`. A duplicate id raises naming
    **both** providers (`N-8`) -- the failure this prevents is two
    components silently drawing over the same layer id.

    `requires`, when given, **gates** the call: a `Tick` lacking one of these
    ports yields no layers and raises nothing (`UT-B1-1`) -- the wrapped
    function is never even called, so its body may assume every required
    port is present and call `Tick.port(name)` (which otherwise raises)
    without a guard of its own. The current tick is `ctx.history`'s own most
    recent entry (`sim_api_reference.md` §5's `LayerProvider` takes one
    argument, `ctx`; `sim_architecture.md`'s own example sketch shows a
    second, separate `tick` parameter -- resolved by treating "now" as
    history's last windowed tick rather than adding a second parameter,
    since a windowed view "over ticks up to now" already has one).
    """

    def decorator(func: Callable[..., object]) -> Callable[..., object]:
        existing = _PROVIDERS.get(layer_id)
        if existing is not None:
            raise AuthoringError(
                expected=f"a layer id not already registered (currently {existing!r})",
                found=f"{layer_id!r} requested again by {func.__module__}.{func.__qualname__}",
                where="adas_sim.scene.registry.layer_provider",
                hint=f"rename one of the two providers ({existing.module}.{existing.qualname} "
                     f"and {func.__module__}.{func.__qualname__})",
            )

        if requires:
            @functools.wraps(func)
            def gated(ctx, *args, **kwargs):
                current = ctx.history.last(1)
                if not current or not all(name in current[-1].ports for name in requires):
                    return ()
                return func(ctx, *args, **kwargs)
            registered_func = gated
        else:
            registered_func = func

        _PROVIDERS[layer_id] = LayerProviderEntry(
            id=layer_id, func=registered_func, module=func.__module__, qualname=func.__qualname__,
            group=group, requires=tuple(requires),
        )
        return registered_func

    return decorator


def registered_providers() -> Mapping[str, LayerProviderEntry]:
    return MappingProxyType(_PROVIDERS)


def inspector_fields(*fields: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Declares which fields a layer's picked prim exposes to the inspector
    panel (`S-B3`). Registration only; consumed once the inspector exists."""

    def decorator(func: Callable[..., object]) -> Callable[..., object]:
        _INSPECTOR_FIELDS[func] = tuple(fields)
        return func

    return decorator


def registered_inspector_fields() -> Mapping[Callable[..., object], tuple[str, ...]]:
    return MappingProxyType(_INSPECTOR_FIELDS)


def signal(name: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Registers a **computed** signal under the one address space
    (`NR-SIM-8`). A raw port field needs no registration; only a signal
    computed from one does (`S-B3`)."""

    def decorator(func: Callable[..., object]) -> Callable[..., object]:
        if name in _SIGNALS:
            raise AuthoringError(
                expected="a signal name not already registered",
                found=f"{name!r} requested again by {func.__module__}.{func.__qualname__}",
                where="adas_sim.scene.registry.signal",
                hint="rename one of the two signals",
            )
        _SIGNALS[name] = func
        return func

    return decorator


def registered_signals() -> Mapping[str, Callable[..., object]]:
    return MappingProxyType(_SIGNALS)
