# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 9 `view/workspace.py` tests: `UT-B3-11`'s parsing half
(docs/sim_implementation_plan.md) -- opening declared tabs, splits and
ratios, and the missing-file fallback. No Qt (`view/` stays
headless-testable)."""

from __future__ import annotations

import pytest

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.player.panels.workspace import (
    Workspace, WorkspaceSplit, WorkspaceTab, WorkspaceView,
    default_workspace, load_workspace, parse_workspace,
)

_EXAMPLE = {
    "workspaces": {
        "default": {
            "tabs": [
                {
                    "name": "Rear",
                    "split": {"orientation": "vertical", "ratio": [1, 2]},
                    "views": [
                        {"panel": "bev", "viewpoint": "blindspot_l"},
                        {"panel": "timeline", "signals": ["test.warning.left", "derived.ttc"]},
                    ],
                },
                {"name": "Approach", "views": [{"panel": "bev", "viewpoint": "forward"}]},
            ],
        },
    },
}


def test_parse_workspace_reads_tabs_splits_and_ratios():
    """UT-B3-11 (parsing half)."""
    ws = parse_workspace(_EXAMPLE)
    assert ws == Workspace(tabs=(
        WorkspaceTab(
            name="Rear", split=WorkspaceSplit(orientation="vertical", ratio=(1, 2)),
            views=(
                WorkspaceView(panel="bev", viewpoint="blindspot_l"),
                WorkspaceView(panel="timeline", signals=("test.warning.left", "derived.ttc")),
            ),
        ),
        WorkspaceTab(name="Approach", views=(WorkspaceView(panel="bev", viewpoint="forward"),)),
    ))


def test_parse_workspace_a_tab_with_no_split_is_none():
    ws = parse_workspace(_EXAMPLE)
    assert ws.tabs[1].split is None


def test_parse_workspace_unknown_name_raises_naming_available_ones():
    with pytest.raises(AuthoringError) as excinfo:
        parse_workspace(_EXAMPLE, name="nonexistent")
    assert "default" in excinfo.value.found


def test_parse_workspace_a_view_with_no_panel_raises():
    bad = {"workspaces": {"default": {"tabs": [{"name": "t", "views": [{"viewpoint": "x"}]}]}}}
    with pytest.raises(AuthoringError):
        parse_workspace(bad)


def test_parse_workspace_a_tab_with_no_name_raises():
    bad = {"workspaces": {"default": {"tabs": [{"views": []}]}}}
    with pytest.raises(AuthoringError):
        parse_workspace(bad)


def test_parse_workspace_an_unknown_split_orientation_raises():
    bad = {"workspaces": {"default": {"tabs": [
        {"name": "t", "split": {"orientation": "diagonal", "ratio": [1, 1]}, "views": []},
    ]}}}
    with pytest.raises(AuthoringError) as excinfo:
        parse_workspace(bad)
    assert "horizontal" in excinfo.value.expected and "vertical" in excinfo.value.expected


def test_default_workspace_is_bev_plus_timeline():
    """§13b: "a missing workspace is not an error -- the framework falls
    back to a single BEV plus the timeline"."""
    ws = default_workspace()
    assert len(ws.tabs) == 1
    panels = [v.panel for v in ws.tabs[0].views]
    assert panels == ["bev", "timeline"]


def test_load_workspace_reads_a_real_file(tmp_path):
    path = tmp_path / "workspace.yaml"
    path.write_text(
        "workspaces:\n  default:\n    tabs:\n      - name: t\n        views:\n          - {panel: bev}\n",
        encoding="utf-8",
    )
    ws = load_workspace(path)
    assert ws.tabs == (WorkspaceTab(name="t", views=(WorkspaceView(panel="bev"),)),)
