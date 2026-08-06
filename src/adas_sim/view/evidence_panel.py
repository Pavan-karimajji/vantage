# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`EvidencePanelState` -- the docked evidence panel's state (S-D3 slice 5,
`UT-D3-8`, `R-SIM-25`, `sim_architecture.md` §5.19's `OD-6`): the SAME
`core.evidence.evidence` call and `core.evidence.format_evidence` formatter
`cli/explain.py --at` already uses, wrapped for a live `Session` and the
current tick -- "one producer, two formatters" applied to the GUI half,
`cli/explain.py` being the other. Pure state, no pixels, no Qt -- `view/`
stays headless-testable, the same discipline `view/pipeline_panel.py` and
`view/inspector.py` already follow.

**Values are never cached** (same discipline `InspectorState` uses):
`view_for` re-derives from the live `Session` every call, so a stale tick
or address is never shown -- there is no separate invalidation to get
wrong.

**Address, not yet prim -- the still-open half of `R-SIM-25`'s join.** A
rendered `Prim`'s `pick_id` does not yet resolve to the port/topic that
produced it; that join (`Layer.id` -> a provider's resolved `requires` ->
ports) is `ST-D6-3`'s own separate, still-open scope (`sim_implementation_
plan.md`'s R39 row). This panel accepts whatever address the caller
selects -- today, `MainWindow` tries the current BEV selection's `pick_id`
directly -- and degrades exactly the way `evidence()` already does for
anything unresolved: `kind="unknown"`, every field `format_evidence`
cannot fill reading `"unknown"` (`R-SIM-25`, `NR-SIM-4`), never a guess.
That degrade is honest today (most `pick_id`s are not port names) and
becomes precise for free once `ST-D6-3` lands the real join -- this
class's contract does not change, only what address it is handed.
"""

from __future__ import annotations

from dataclasses import dataclass

from adas_sim.core.evidence import evidence, format_evidence
from adas_sim.core.session import Session


@dataclass(frozen=True, slots=True)
class EvidenceView:
    """One address's evidence, rendered -- `rows` is `format_evidence`'s
    own output, unchanged, so this panel and `cli/explain.py --at` display
    identical text for identical bytes (`UT-D3-8`)."""

    address: str
    rows: tuple[tuple[str, str], ...]


class EvidencePanelState:
    """One instance per `Session` -- mirrors `PipelinePanelState`'s own
    "one instance per (pipeline, recording)" scope."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def view_for(self, address: str, tick: int) -> EvidenceView:
        record = evidence(address, self._session, tick)
        return EvidenceView(address=address, rows=format_evidence(record))
