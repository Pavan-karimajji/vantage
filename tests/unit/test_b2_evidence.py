# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B2Δ `core/evidence.py` tests (docs/sim_implementation_plan.md's
`core/evidence.py` scope box -- seeded here, no standalone `UT-` id of its
own yet, same as `core/explain.py`'s own S-B2 seed)."""

from __future__ import annotations

from adas_sim.diagnostics.evidence import EVIDENCE_FIELDS, evidence, format_evidence
from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick

_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


def _session() -> Session:
    tick = Tick(
        index=0, t_ns=0, dt_ns=0,
        ports={"sim.test.port": PortValue(name="sim.test.port", message=b"\x01", origin="measured")},
        pose=_POSE,
    )
    return Session(run_id="run-123", name="s", ticks=(tick,))


def test_evidence_resolves_the_run_id():
    session = _session()
    record = evidence("run-123", session, 0)
    assert record.kind == "run_id"
    assert record.value == "run-123"
    assert record.topic is None
    assert record.origin is None


def test_evidence_resolves_a_port_present_at_that_tick():
    session = _session()
    record = evidence("sim.test.port", session, 0)
    assert record.kind == "port"
    assert record.origin == "measured"
    assert record.topic == "sim.test.port"
    assert record.run_id == "run-123"


def test_evidence_reports_unknown_for_an_unresolvable_address():
    session = _session()
    record = evidence("no.such.port", session, 0)
    assert record.kind == "unknown"
    assert record.value == ""
    assert record.origin is None


def test_format_evidence_renders_every_field_in_the_fixed_order():
    session = _session()
    record = evidence("sim.test.port", session, 0)
    rows = format_evidence(record)
    assert tuple(name for name, _text in rows) == EVIDENCE_FIELDS
    assert dict(rows)["origin"] == "measured"
    assert dict(rows)["topic"] == "sim.test.port"


def test_format_evidence_prints_unknown_never_a_bare_none():
    """UT-D3-8/`R-SIM-25`/`NR-SIM-4`: a field this stage could not fill
    reads "unknown" on every surface that calls this formatter -- never
    Python's own str(None)."""
    session = _session()
    record = evidence("no.such.port", session, 0)
    rows = dict(format_evidence(record))
    assert rows["topic"] == "unknown"
    assert rows["origin"] == "unknown"
    assert "None" not in rows.values()
