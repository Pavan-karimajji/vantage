# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`@layer_provider` -- discovery **by import** (api reference §5).

A component adds a layer by existing: importing the module that defines a
decorated function is what registers it, so there is no central roster to keep
in sync (`R-VAR-2`, extended from components to layers).

Two decorators that once lived here are gone, both deliberately:

- **`@inspector_fields`** registered field *names* against the decorated
  function with no way to resolve values, and could silently diverge from
  `LayerProviderEntry.func` when `layer_provider` wrapped it in `gated`.
  Replaced by `Prim.fields`: the provider already has the entity in hand, so
  it computes the inspector pairs inline -- one fewer moving part.
- **`@signal`/`registered_signals`** moved to `core/signals.py`, next to the
  resolver that reads them (`NR-SIM-8`).
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields
from types import MappingProxyType

from adas_sim.contracts.binding import try_resolve_component_ref
from adas_sim.core.errors import AuthoringError
from adas_sim.core.history import Interaction
from adas_sim.scene.types import Layer

#: The vocabulary a provider's `reacts_to=` may name -- read off `Interaction`
#: itself rather than duplicated here, so the two cannot drift apart.
_INTERACTION_FIELDS = frozenset(f.name for f in fields(Interaction))


@dataclass(frozen=True, slots=True)
class LayerProviderEntry:
    id: str
    func: Callable[..., object]
    module: str
    qualname: str
    group: str = ""
    requires: tuple[str, ...] = ()
    #: `Interaction` fields (`sim_visualization_spec.md` §7.5) this
    #: provider's output depends on -- empty means "never re-rendered on a
    #: mouse move" (`core/runner.SceneCache`'s static tier).
    reacts_to: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return f"<LayerProviderEntry {self.id!r} from {self.module}.{self.qualname}>"


_PROVIDERS: dict[str, LayerProviderEntry] = {}


def layer_provider(
    layer_id: str, *, group: str = "", requires: Sequence[str] = (),
    reacts_to: Sequence[str] = (),
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Register `func` under `layer_id`. A duplicate id raises naming **both**
        providers (`N-8`) -- the failure that prevents is two components silently
        drawing over the same layer id.

        `requires`, when given, **gates** the call: a `Tick` lacking one of those
        ports yields no layers and raises nothing (`UT-B1-1`). The wrapped function
        is never called, so its body may assume every required port is present and
        call `Tick.port(name)` without a guard of its own.

        `reacts_to` names which `Interaction` fields (`"cursor"`, `"selection"`,
        `"modifiers"`, `"toggles"`) the output depends on (viz §7.5). The provider
        stays a pure function either way -- this only tells `SceneCache` which tier
        to use, so a provider declaring nothing is never re-rendered on a mouse
        move.

        "Now" is `ctx.history`'s most recent entry: a windowed view over ticks up
        to now already carries one, so there is no second `tick` parameter.

    """
    for field_name in reacts_to:
        if field_name not in _INTERACTION_FIELDS:
            raise AuthoringError(
                expected=f"a reacts_to field from {sorted(_INTERACTION_FIELDS)}",
                found=repr(field_name),
                where=f"adas_sim.scene.registry.layer_provider({layer_id!r})",
                hint="check the field name against core.history.Interaction",
            )

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
            where = f"{func.__module__}.{func.__qualname__} requires"

            @functools.wraps(func)
            def gated(ctx, *args, **kwargs):
                current = ctx.history.last(1)
                if not current:
                    return ()
                # A `self.<port>` name matching more than one known port is
                # an unambiguous same-run collision and raises loudly.
                # A resolved name simply absent from *this* tick stays a
                # legitimate "nothing to draw yet" (`D13`, `S-B1Δ`) -- it
                # was already discovered on an earlier tick and will
                # populate again, so `view/layers.py`'s own `LayerTreeState.
                # sync` keeps it in the tree deliberately.
                #
                # A ZERO-match `requires=` entry is different (`AR-53`,
                #: manifests are live now (`sim probe`, `S-C1d`,
                # `R-SIM-23`'s ingest maps) -- "this port does not exist
                # anywhere in this run" is no longer indistinguishable from
                # "this run never wired that component" the way it was at
                # `S-B1Δ`. Returning `()` here is silent absence for a
                # reference that will NEVER resolve; a placeholder layer,
                # named and carrying no prims, is what lets the layer list
                # say so instead of looking identical to "never warned".
                resolved: list[str] = []
                for name in requires:
                    ref = try_resolve_component_ref(name, known_ports=ctx.known_ports, where=where)
                    if ref is None:
                        return (Layer(
                            id=layer_id, group=group, prims=(),
                            unavailable=f"requires {name!r}, which no port in this run resolves to",
                        ),)
                    resolved.append(ref)
                if not all(name in current[-1].ports for name in resolved):
                    return ()
                return func(ctx, *args, **kwargs)
            registered_func = gated
        else:
            registered_func = func

        _PROVIDERS[layer_id] = LayerProviderEntry(
            id=layer_id, func=registered_func, module=func.__module__, qualname=func.__qualname__,
            group=group, requires=tuple(requires), reacts_to=tuple(reacts_to),
        )
        return registered_func

    return decorator


def registered_providers() -> Mapping[str, LayerProviderEntry]:
    return MappingProxyType(_PROVIDERS)


# `AR-52`: the framework ships a default layer set -- unlike a
# component's plug-in (imported lazily, only if its checkout/library is on
# the plug-in path, `model.plugins.PluginBundle`), these three are the
# framework's OWN contribution and must be registered unconditionally,
# before any plug-in is ever loaded. `layer_provider` is already defined
# above this line, so `default_layers`' own `from adas_sim.scene.registry
# import layer_provider` resolves against this (partially-initialized but
# sufficient) module rather than deadlocking.
from adas_sim.scene import default_layers  # noqa: E402,F401
