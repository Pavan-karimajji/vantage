# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`@layer_provider` -- discovery **by import** (sim_api_reference.md §5,
§6.4's registry note). A component adds a layer by existing: importing the
module that defines a decorated function is what registers it, so there is no
central roster to keep in sync (`R-VAR-2`'s "no central roster" principle,
extended from components to layers).

**`@inspector_fields` (`S-A3`) lived here and is gone.** It only ever
registered field *names* against the decorated function object, with no way
to resolve *values* for a picked entity -- and since `layer_provider` may
wrap that same function in `gated` (when `requires` is given), the
registration key and `LayerProviderEntry.func` could silently diverge. Never
called anywhere. Replaced (`S-B3` slice 5) by `Prim.fields`: the provider
that builds a prim already has the raw entity in hand, so it computes the
inspector's (name, value) pairs inline, the same pass -- one fewer moving
part, and no identity to keep in sync.

**`@signal`/`registered_signals` (`S-A3`) lived here too and moved.**
Unused anywhere until `S-B3` slice 6 needed them for real, at which point
they belong next to the resolver that reads them -- `core/signals.py`, not
here (`NR-SIM-8`).
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

    `reacts_to`, when given, names which `Interaction` fields (`"cursor"`,
    `"selection"`, `"modifiers"`, `"toggles"`) this provider's output
    depends on (`sim_visualization_spec.md` §7.5). The provider stays a pure
    function of `(tick, ctx)` either way -- `reacts_to` only tells
    `core/runner.SceneCache` which tier to put it in, so a provider
    declaring nothing is never re-rendered on a mouse move.
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
                # 2026-08-07): manifests are live now (`sim probe`, `S-C1d`,
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


# `AR-52` (2026-08-07): the framework ships a default layer set -- unlike a
# component's plug-in (imported lazily, only if its checkout/library is on
# the plug-in path, `model.plugins.PluginBundle`), these three are the
# framework's OWN contribution and must be registered unconditionally,
# before any plug-in is ever loaded. `layer_provider` is already defined
# above this line, so `default_layers`' own `from adas_sim.scene.registry
# import layer_provider` resolves against this (partially-initialized but
# sufficient) module rather than deadlocking.
from adas_sim.scene import default_layers  # noqa: E402,F401
