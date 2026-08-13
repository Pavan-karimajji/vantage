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

**Address or prim -- `R-SIM-25`'s join, closed at `ST-D6-3`.** A rendered
`Prim`'s `pick_id` resolves to the port/topic that produced it
(`core.evidence._resolve_prim`: `Layer.id` -> a provider's declared
`requires` -> `contracts.binding.try_resolve_component_ref`), so
`kind="prim"` now joins `"run_id"`/`"port"`/`"unknown"`. This panel needed
no edit to gain it -- `MainWindow` already passes the current BEV
selection's `pick_id` straight through as `address` (predating this
change), and `evidence()` tries it as a port, then a prim, before
degrading. **One honest limit stays**: a `pick_id` from a layer provider
never imported into this process (no plug-in loaded, `S-C8`'s own separate
scope) still degrades to `kind="unknown"` -- there is no `Prim` to find,
so `format_evidence` prints `"unknown"` on every field it cannot fill
(`R-SIM-25`, `NR-SIM-4`), never a guess.
"""

from __future__ import annotations

from dataclasses import dataclass

from adas_sim.diagnostics.evidence import evidence, format_evidence
from adas_sim.session.session import Session


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
