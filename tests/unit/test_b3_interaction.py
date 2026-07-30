# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 4 tests: `Interaction` on `LayerCtx` + `reacts_to=` on the
provider decorator, and the `SceneCache` split this makes possible
(`sim_visualization_spec.md` §7.5). Ties directly to `UT-B3-13`/`UT-B3-14`
(a reactive provider updates on the interaction it declared; a provider
declaring nothing never does) at the mechanics level -- `render/viewer.py`'s
own offscreen tests cover the same claim wired through a real `MainWindow`.
"""

from __future__ import annotations

import pytest

from adas_sim.core.errors import AuthoringError
from adas_sim.core.history import Interaction, interaction_cache_key
from adas_sim.core.runner import SceneCache
from adas_sim.scene.registry import layer_provider, registered_providers
from adas_sim.scene.types import Layer, Scene


def test_reacts_to_rejects_a_field_interaction_does_not_have():
    with pytest.raises(AuthoringError) as excinfo:
        @layer_provider("sim.test.interaction.bad_field", reacts_to=("mouse_wheel",))
        def _provider(ctx):
            return ()

    assert "mouse_wheel" in excinfo.value.found


def test_reacts_to_accepts_real_interaction_fields_and_is_stored():
    @layer_provider("sim.test.interaction.reactive", reacts_to=("cursor", "selection"))
    def _provider(ctx):
        return ()

    assert registered_providers()["sim.test.interaction.reactive"].reacts_to == ("cursor", "selection")


def test_a_provider_declaring_nothing_has_an_empty_reacts_to():
    @layer_provider("sim.test.interaction.static")
    def _provider(ctx):
        return ()

    assert registered_providers()["sim.test.interaction.static"].reacts_to == ()


def test_interaction_itself_is_not_hashable_because_of_toggles():
    """The reason `interaction_cache_key` exists rather than relying on
    `Interaction`'s dataclass-generated `__hash__`: `toggles` is a
    `Mapping`, and a `MappingProxyType` is not hashable on its own."""
    interaction = Interaction(toggles={"x": True})
    with pytest.raises(TypeError):
        hash(interaction)


def test_interaction_cache_key_is_hashable_and_reflects_every_field():
    a = Interaction(cursor=(1.0, 2.0), selection=frozenset({"x"}),
                     modifiers=frozenset({"shift"}), toggles={"x": True})
    b = Interaction(cursor=(1.0, 2.0), selection=frozenset({"x"}),
                     modifiers=frozenset({"shift"}), toggles={"x": True})
    c = Interaction(cursor=(9.0, 9.0))

    key_a, key_b, key_c = interaction_cache_key(a), interaction_cache_key(b), interaction_cache_key(c)
    hash(key_a)  # must not raise
    assert key_a == key_b
    assert key_a != key_c


def test_scene_cache_reactive_tier_recomputes_only_on_interaction_change():
    """`UT-B3-13`/`UT-B3-14` at the cache-mechanics level: the static tier
    never sees `build_reactive`'s interaction changes; the reactive tier
    rebuilds exactly when the interaction key actually changes."""
    static_calls: list[int] = []
    reactive_calls: list[tuple[float, float] | None] = []

    def build_static(tick_index, layer_selection, theme):
        static_calls.append(1)
        return Scene(t_s=0.0, layers=(Layer(id="static", group="g", prims=()),))

    def build_reactive(tick_index, layer_selection, theme, interaction):
        reactive_calls.append(interaction.cursor)
        return (Layer(id="reactive", group="g", prims=()),)

    cache = SceneCache(build_static, build_reactive=build_reactive)

    scene = cache.get(0, frozenset(), "dark", Interaction(cursor=(1.0, 2.0)))
    assert [layer.id for layer in scene.layers] == ["static", "reactive"]
    assert len(static_calls) == 1
    assert len(reactive_calls) == 1

    # Same interaction again -- both tiers are cached (UT-B3-14's own claim,
    # generalised: not even the *reactive* tier is re-run for a no-op change).
    cache.get(0, frozenset(), "dark", Interaction(cursor=(1.0, 2.0)))
    assert len(static_calls) == 1
    assert len(reactive_calls) == 1

    # The interaction actually changes -- only the reactive tier rebuilds
    # (UT-B3-14: a provider declaring nothing is never re-rendered for this).
    cache.get(0, frozenset(), "dark", Interaction(cursor=(3.0, 4.0)))
    assert len(static_calls) == 1
    assert len(reactive_calls) == 2
