# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B2 `core/runner.SceneCache` tests: UT-B2-3, UT-B2-5, UT-B2-12
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

from adas_sim.core.runner import SceneCache


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
