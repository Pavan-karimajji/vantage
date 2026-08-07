# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`Workspace` -- a dock arrangement plus a permission set, nothing else
(`S-D8`, `sim_player.md` §1: "a workspace is a mode of one window, not a
separate application"). `BENCH` is permissive (overrides, live mode
toggles, the Python console); `CAMPAIGN` is locked (none of the three) --
"not because they are dangerous, but because a report whose inputs were
poked by hand is not a report" (`sim_player.md` §5).

**Switching workspace never reloads the engine and never touches the open
pipeline file** (`R-SIM-16` made visible in one gesture, `UT-D8-1`) --
`Workspace` therefore carries no `Session`/`Pipeline` reference of its own;
`app/shell/window.py` holds those once, and a workspace is only ever a lens
over them. This module -- and everything under `app/` -- is the one place
the tokens `Vantage`/`Bench`/`Campaign` may appear at all (`UT-D8-9`,
`sim_player.md`'s own naming rule: "no workspace name appears in
`adas_sim/` outside `app/`" -- the same discipline `R-SIM-1` applies to a
driving function's name, applied here to a UI arrangement's).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WorkspaceName = Literal["bench", "campaign"]


class WorkspacePermissionError(Exception):
    """Raised when an action the CURRENT workspace forbids is attempted.

    Deliberately not one of `core.errors.SimError`'s closed four
    (`AuthoringError`/`EnvironmentError_`/`ContractError`/`InternalError`,
    `DG-5`) -- that taxonomy is about a RUN failing with a CLI exit code;
    this is a GUI interaction refused before anything ran, caught by the
    widget that offered the action, never propagated to a process exit.
    Lives here, in `app/`, because `core/errors.py` must never learn a
    workspace exists (`UT-D8-9`).

    `UT-D8-2`'s own requirement: "the refusal names the workspace, not a
    generic 'not permitted'" -- `action` and `workspace` are both named,
    every time, never folded into one opaque string only at the end.
    """

    def __init__(self, *, action: str, workspace: WorkspaceName) -> None:
        self.action = action
        self.workspace = workspace
        super().__init__(
            f"{action!r} is not permitted in the {workspace} workspace -- "
            f"open this recording on the Bench to {action}"
        )


@dataclass(frozen=True, slots=True)
class Workspace:
    """`sim_player.md` §4/§5's two workspaces, made data. `locked` is
    derived, never a fourth independent flag that could disagree with the
    other three -- "locked" means exactly "none of overrides/mode toggles/
    console," nothing else, so there is no way to construct a workspace
    that is locked yet still permits one of them."""

    name: WorkspaceName
    allow_overrides: bool
    allow_mode_toggles: bool
    allow_console: bool

    @property
    def locked(self) -> bool:
        return not (self.allow_overrides or self.allow_mode_toggles or self.allow_console)

    def __repr__(self) -> str:
        return f"<Workspace {self.name!r} locked={self.locked}>"

    def require(self, action: str, *, allowed: bool) -> None:
        """The mechanism a permission-gated action WOULD route through, if
        `CampaignWidget` ever grew an override affordance, a mode toggle or
        a console it had to grey out -- `allowed` is the caller's own
        already-computed answer (`self.allow_overrides`, …), passed in
        rather than looked up by a string key, so a typo in the action name
        can never accidentally bypass the real check.

        **Has zero call sites in `src/` today.**
        `CampaignWidget` locks the stronger way instead -- it never
        constructs an override affordance, a mode toggle or a console dock
        at all, so there is nothing here to grey out and nothing to bypass.
        That is the mechanism actually proven by `UT-D8-2`
        (`test_d8_campaign.py`); this method's own correctness (a refused
        action names the workspace, never a generic message) is real and
        tested (`test_d8_workspace.py`), but unused in production until a
        real disableable control exists to call it."""
        if not allowed:
            raise WorkspacePermissionError(action=action, workspace=self.name)


#: `sim_player.md` §4: "Everything permissive is here and nowhere else."
BENCH = Workspace(name="bench", allow_overrides=True, allow_mode_toggles=True, allow_console=True)

#: `sim_player.md` §5: "Campaign is locked: no per-port overrides, no live
#: mode toggles, no Python console... Editing anything offers to open it
#: on the Bench."
CAMPAIGN = Workspace(name="campaign", allow_overrides=False, allow_mode_toggles=False, allow_console=False)

WORKSPACES: dict[WorkspaceName, Workspace] = {"bench": BENCH, "campaign": CAMPAIGN}
