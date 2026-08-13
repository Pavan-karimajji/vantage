# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D3 slice 5 unit test: `EvidencePanelState` (`view/evidence_panel.py`)
is a thin, headless wrapper around `core.evidence.evidence` +
`format_evidence` -- no Qt needed to prove it, same bar
`test_d3_pipeline_panel_state.py` sets for its own state module."""

from __future__ import annotations

from adas_sim.diagnostics.evidence import evidence, format_evidence
from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick
from adas_sim.player.panels.evidence_panel import EvidencePanelState

_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


def _session() -> Session:
    tick = Tick(
        index=0, t_ns=0, dt_ns=0,
        ports={"sim.test.port": PortValue(name="sim.test.port", message=b"\x01", origin="measured")},
        pose=_POSE,
    )
    return Session(run_id="run-123", name="s", ticks=(tick,))


def test_view_for_matches_format_evidence_of_the_same_evidence_call():
    session = _session()
    state = EvidencePanelState(session)

    view = state.view_for("sim.test.port", 0)

    assert view.address == "sim.test.port"
    assert view.rows == format_evidence(evidence("sim.test.port", session, 0))


def test_view_for_an_unresolved_address_reads_unknown_never_a_bare_none():
    session = _session()
    state = EvidencePanelState(session)

    view = state.view_for("no.such.port", 0)

    rows = dict(view.rows)
    assert rows["kind"] == "unknown"
    assert rows["topic"] == "unknown"
    assert rows["origin"] == "unknown"
