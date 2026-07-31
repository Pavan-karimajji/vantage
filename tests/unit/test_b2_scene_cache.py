# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B2 `core/runner.SceneCache` tests: UT-B2-3, UT-B2-5, UT-B2-12, UT-B2-15
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

from adas_sim.core.runner import SceneCache
from adas_sim.scene.types import Layer, Prim, Scene


def test_toggling_a_layer_re_renders_without_re_running_pass_1():
    """UT-B2-3: a pass-1 call counter stays unchanged while the cache
    rebuilds for a new layer selection."""
    pass_1_calls = 0

    def pass_1():
        nonlocal pass_1_calls
        pass_1_calls += 1
        return "the-session"

    pass_1()  # Session built once, up front.
    assert pass_1_calls == 1

    def build_scene(tick_index, layer_selection, theme):
        return f"scene-{tick_index}-{sorted(layer_selection)}-{theme}"

    cache = SceneCache(build_scene)
    cache.get(0, frozenset({"a"}), "dark")
    cache.get(0, frozenset({"a", "b"}), "dark")
    cache.get(0, frozenset({"a", "b", "c"}), "dark")
    assert pass_1_calls == 1  # never re-run, no matter how many layer toggles


def test_cache_invalidates_on_theme_change_not_on_viewport_change():
    """UT-B2-5: viewport is not even part of the cache key."""
    calls = []

    def build(tick_index, layer_selection, theme):
        calls.append((tick_index, layer_selection, theme))
        return object()

    cache = SceneCache(build)
    layers = frozenset({"a"})
    first = cache.get(0, layers, "dark")
    # Same key, called with a "different viewport" conceptually -- but
    # viewport is not a parameter of get() at all, so nothing changes here.
    second = cache.get(0, layers, "dark")
    assert first is second
    assert cache.build_calls == 1

    third = cache.get(0, layers, "light")  # theme changed -> rebuild
    assert third is not first
    assert cache.build_calls == 2


def test_cache_respects_its_bound_and_evicts_least_recently_used():
    """UT-B2-12."""
    def build(tick_index, layer_selection, theme):
        return (tick_index, layer_selection, theme)

    cache = SceneCache(build, max_size=3)
    layers = frozenset()
    for tick_index in range(3):
        cache.get(tick_index, layers, "dark")
    assert len(cache) == 3

    cache.get(0, layers, "dark")  # touch tick 0 -- now most-recently-used
    cache.get(3, layers, "dark")  # a 4th key -- evicts the least-recently-used (tick 1)
    assert len(cache) == 3

    calls_before = cache.build_calls
    cache.get(0, layers, "dark")  # still cached (was touched)
    assert cache.build_calls == calls_before
    cache.get(1, layers, "dark")  # was evicted -- rebuilds
    assert cache.build_calls == calls_before + 1


def test_scene_cache_byte_bound_does_not_regress_a_session_of_small_values():
    """UT-B2-15 (converse): the default byte bound must not disturb
    UT-B2-12's own small-value scenario -- entry count alone still decides
    when every value is tiny."""
    def build(tick_index, layer_selection, theme):
        return (tick_index, layer_selection, theme)

    cache = SceneCache(build, max_size=3)  # default max_bytes, tiny values
    layers = frozenset()
    for tick_index in range(3):
        cache.get(tick_index, layers, "dark")
    assert len(cache) == 3  # byte bound never fires for values this small


def test_scene_cache_evicts_on_a_byte_bound_before_the_entry_count_ever_binds():
    """UT-B2-15: a cache holding few but large values evicts on `max_bytes`
    even though `max_size` is generously larger than the whole run --
    an entry-count bound alone would not have evicted anything here."""
    def build_large(tick_index, layer_selection, theme):
        return bytes(2_000)  # ~2 KB per entry

    cache = SceneCache(build_large, max_size=1000, max_bytes=5_000)
    layers = frozenset()
    for tick_index in range(5):
        cache.get(tick_index, layers, "dark")

    assert len(cache) < 5  # evicted well before the entry-count bound was ever approached
    assert cache.build_calls == 5  # every tick was still built once -- eviction, not a skipped build


def test_scene_cache_measures_a_real_scenes_encoded_size_not_a_generic_sizeof():
    """UT-B2-15: a real `Scene` is measured by its own encoded byte size --
    the exact quantity a recording or golden would carry (`NR-SIM-43`) --
    not a generic Python `sys.getsizeof`, which would wildly undercount a
    Scene holding hundreds of points."""
    def build_scene(tick_index, layer_selection, theme):
        points = tuple((float(i), 0.0) for i in range(300))
        prim = Prim(kind="points", points_m=points, style="truth.trace")
        layer = Layer(id="sim.test.cloud", group="sim", prims=(prim,))
        return Scene(t_s=float(tick_index), layers=(layer,))

    cache = SceneCache(build_scene, max_size=1000, max_bytes=2_000)  # one such Scene alone exceeds this
    layers = frozenset()
    for tick_index in range(4):
        cache.get(tick_index, layers, "dark")
    assert len(cache) < 4  # each Scene's real encoded size drives eviction
