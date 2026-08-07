# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`AR-53` (`docs/sim_audit_log.md` run 4, `sim_implementation_plan.md`
`S-B1Δ`/`S-D6`): a required-but-unbound layer is named and badged in the
`LayersPanel` tree, never silently dropped. `tests/unit/test_b1_registry_
gating.py` and `tests/unit/test_b3_layers.py` already prove the registry
and state halves (no Qt); this is the third: the actual `QTreeWidgetItem`
a user would see carries the reason, both in its own label (visible
without hovering) and its tooltip (the full text)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

from adas_sim.render.viewer import LayersPanel  # noqa: E402
from adas_sim.scene.types import Layer  # noqa: E402
from adas_sim.view.layers import LayerTreeState  # noqa: E402


def _app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_an_unavailable_layer_renders_a_disabled_badged_tree_item():
    _app()
    state = LayerTreeState()
    panel = LayersPanel(state)
    reason = "requires 'self.bsd.outputs', which no port in this run resolves to"
    panel.sync_from_scene((Layer(id="bsd.warning", group="bsd", label="BSD warning", unavailable=reason),))

    group_item = panel._tree.topLevelItem(0)
    assert group_item.text(0) == "bsd"
    layer_item = group_item.child(0)
    assert "BSD warning" in layer_item.text(0)
    assert "unavailable" in layer_item.text(0)
    assert layer_item.toolTip(0) == reason
    # No checkbox affordance -- there is nothing to toggle (no prims exist
    # regardless of checked state), so this item must not claim otherwise.
    assert not (layer_item.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable)


def test_an_ordinary_layer_still_renders_checkable_and_unbadged():
    """Converse, in the same panel: an unrelated ordinary layer is
    unaffected -- the badge path is additive, not a change to the default
    rendering."""
    _app()
    state = LayerTreeState()
    panel = LayersPanel(state)
    panel.sync_from_scene((Layer(id="bsd.zone", group="bsd", label="BSD zone"),))

    layer_item = panel._tree.topLevelItem(0).child(0)
    assert layer_item.text(0) == "BSD zone"
    assert layer_item.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable
