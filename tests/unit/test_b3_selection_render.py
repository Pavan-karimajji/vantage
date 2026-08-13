# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 5 `render/bev.py` test: selected prims get `object.selected`
styling plus a halo (`sim_visualization_spec.md` §7.1). No Qt -- `render/bev.py`
is matplotlib/`Agg`, headless since `S-B1`."""

from __future__ import annotations

import numpy as np

from adas_sim.render.bev import render_scene
from adas_sim.scene.types import Layer, Prim, Scene
from adas_sim.player.panels.viewport import Viewport

_VP = Viewport(size_px=(200, 200), scale_px_per_m=10.0)


def _scene():
    return Scene(layers=(Layer(id="sim.test", group="sim", prims=(
        Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=2.0, width_m=2.0, yaw_rad=0.0,
             style="ego.body", pick_id="ego"),
    )),))


def test_selecting_the_only_prim_changes_the_rendered_pixels():
    scene = _scene()
    unselected = render_scene(scene, _VP, "dark")
    selected = render_scene(scene, _VP, "dark", selection=frozenset({"ego"}))
    assert not np.array_equal(unselected, selected)


def test_selecting_a_different_pick_id_leaves_the_frame_unchanged():
    scene = _scene()
    unselected = render_scene(scene, _VP, "dark")
    other_selected = render_scene(scene, _VP, "dark", selection=frozenset({"someone-else"}))
    assert np.array_equal(unselected, other_selected)


def test_default_selection_is_empty_so_old_callers_are_unaffected():
    """Every caller written before this slice (goldens, other tests) calls
    `render_scene` with no `selection` argument at all."""
    scene = _scene()
    assert np.array_equal(render_scene(scene, _VP, "dark"), render_scene(scene, _VP, "dark", selection=frozenset()))
