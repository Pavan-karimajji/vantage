# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 layer-tree test: UT-B3-1 (docs/sim_implementation_plan.md) -- group
tri-state, solo/mute, persistence round-trips. No Qt: `view/layers.py` is
pure state (`UT-B3-17`'s own layering)."""

from __future__ import annotations

from adas_sim.scene.types import Layer
from adas_sim.view.layers import LayerTreeState

_LAYERS = (
    Layer(id="df.common.ego", group="df", label="Ego", level=1, default_on=True),
    Layer(id="df.common.trail", group="df", label="Ego trail", level=2, default_on=True),
    Layer(id="bsd.zone", group="bsd", label="BSD zone", level=1, default_on=True),
    Layer(id="bsd.warning", group="bsd", label="BSD warning", level=1, default_on=False),
)


def _synced_state() -> LayerTreeState:
    state = LayerTreeState()
    state.sync(_LAYERS)
    return state


def test_group_tristate_reflects_the_layers_effective_visibility():
    state = _synced_state()
    assert state.group_state("df") == "mixed"  # trail is level 2, group level defaults to 1
    assert state.group_state("bsd") == "mixed"  # zone on, warning off by default

    state.set_group_visible("bsd", True)
    assert state.group_state("bsd") == "on"

    state.set_group_visible("bsd", False)
    assert state.group_state("bsd") == "off"


def test_group_verbosity_level_gates_higher_level_layers():
    state = _synced_state()
    assert state.is_visible("df.common.trail") is False  # level 2 > default group level 1

    state.set_group_level("df", 2)
    assert state.is_visible("df.common.trail") is True


def test_solo_shows_only_that_group_and_toggling_again_unsolos():
    state = _synced_state()
    state.set_group_visible("bsd", True)
    assert state.is_visible("bsd.zone") is True

    state.toggle_solo("df")
    assert state.solo_group == "df"
    assert state.is_visible("df.common.ego") is True
    assert state.is_visible("bsd.zone") is False  # solo'd out, despite being "on"

    state.toggle_solo("df")
    assert state.solo_group is None
    assert state.is_visible("bsd.zone") is True  # restored, not lost


def test_mute_hides_a_group_without_touching_its_stored_overrides():
    state = _synced_state()
    state.toggle_mute("bsd")
    assert state.is_muted("bsd") is True
    assert state.is_visible("bsd.zone") is False

    state.toggle_mute("bsd")
    assert state.is_muted("bsd") is False
    assert state.is_visible("bsd.zone") is True  # back to its own default_on, unaffected by the mute


def test_a_layer_missing_from_one_ticks_scene_is_not_forgotten():
    """`sync()` never drops a previously-seen id -- a gated provider skipping
    one tick must not silently reset the user's earlier choice for it."""
    state = _synced_state()
    state.set_visible("bsd.warning", True)
    state.sync(_LAYERS[:2])  # a tick where bsd's providers produced nothing
    assert state.is_visible("bsd.warning") is True


def test_search_filters_the_tree_listing_but_never_rendered_visibility():
    state = _synced_state()
    assert state.matches_search("df.common.ego") is True
    state.set_search("trail")
    assert state.matches_search("df.common.trail") is True
    assert state.matches_search("df.common.ego") is False
    # Search narrows the tree's own listing only -- rendering is unaffected.
    assert state.is_visible("df.common.ego") is True


def test_persistence_round_trips_every_kind_of_state():
    """Real usage is sync() (fresh discovery) then load() (saved overrides on
    top) -- `_known` itself is never persisted, so a comparison must sync
    `restored` the same way before loading."""
    state = _synced_state()
    state.set_visible("bsd.warning", True)
    state.set_group_level("df", 2)
    state.toggle_mute("bsd")
    state.toggle_solo("df")

    restored = LayerTreeState()
    restored.sync(_LAYERS)
    restored.load_dict(state.to_dict())

    assert restored.to_dict() == state.to_dict()
    assert restored.solo_group == "df"
    assert restored.group_state("df") == state.group_state("df")


def test_save_and_load_round_trip_through_a_real_file(tmp_path):
    state = _synced_state()
    state.set_visible("bsd.warning", True)
    state.toggle_solo("bsd")
    path = tmp_path / "layers" / "base.df_only.json"

    state.save(path)
    assert path.is_file()

    restored = LayerTreeState()
    restored.sync(_LAYERS)
    restored.load(path)
    assert restored.to_dict() == state.to_dict()


def test_loading_a_missing_file_is_a_silent_no_op(tmp_path):
    state = _synced_state()
    before = state.to_dict()
    state.load(tmp_path / "does-not-exist.json")
    assert state.to_dict() == before
