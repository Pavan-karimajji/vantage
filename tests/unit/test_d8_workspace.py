# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`S-D8` `app/shell/workspace.py` tests (`docs/sim_implementation_plan.md`,
`sim_player.md` §1/§4/§5): `Workspace` is a dock arrangement plus a
permission set, nothing else -- no `Session`/`Pipeline` reference, so
switching workspace can never itself reload anything (`UT-D8-1`'s own
claim lives at the `app/shell/window.py` level; this file is the pure
data/permission half underneath it). `UT-D8-2`: a refused action names
the workspace, not a generic "not permitted"."""

from __future__ import annotations

import pytest

from adas_sim.app.shell.workspace import BENCH, CAMPAIGN, WORKSPACES, Workspace, WorkspacePermissionError


def test_bench_permits_everything():
    assert BENCH.allow_overrides is True
    assert BENCH.allow_mode_toggles is True
    assert BENCH.allow_console is True
    assert BENCH.locked is False


def test_campaign_is_locked():
    assert CAMPAIGN.allow_overrides is False
    assert CAMPAIGN.allow_mode_toggles is False
    assert CAMPAIGN.allow_console is False
    assert CAMPAIGN.locked is True


def test_locked_is_derived_not_independently_settable():
    """A workspace permitting even one action is never `locked` -- there is
    no fourth flag that could disagree with the other three."""
    partly_permissive = Workspace(name="bench", allow_overrides=True, allow_mode_toggles=False, allow_console=False)
    assert partly_permissive.locked is False


def test_workspaces_registry_has_exactly_bench_and_campaign():
    assert WORKSPACES == {"bench": BENCH, "campaign": CAMPAIGN}


def test_require_passes_silently_when_allowed():
    BENCH.require("override a port", allowed=BENCH.allow_overrides)  # must not raise


def test_require_raises_naming_the_action_and_the_workspace_never_a_generic_message():
    """`UT-D8-2`: the refusal names the workspace, not a generic 'not
    permitted'."""
    with pytest.raises(WorkspacePermissionError) as exc_info:
        CAMPAIGN.require("override a port", allowed=CAMPAIGN.allow_overrides)
    message = str(exc_info.value)
    assert "override a port" in message
    assert "campaign" in message
    assert exc_info.value.action == "override a port"
    assert exc_info.value.workspace == "campaign"


def test_require_raises_for_every_locked_action_kind():
    for action, allowed in (
        ("override a port", CAMPAIGN.allow_overrides),
        ("toggle a stage's mode", CAMPAIGN.allow_mode_toggles),
        ("open the console", CAMPAIGN.allow_console),
    ):
        with pytest.raises(WorkspacePermissionError):
            CAMPAIGN.require(action, allowed=allowed)


def test_workspace_repr_names_lock_state():
    assert "locked=True" in repr(CAMPAIGN)
    assert "locked=False" in repr(BENCH)
