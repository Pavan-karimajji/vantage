# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-20` `SI-11 graph` -- `UT-GRF-18`, `UT-GRF-19` (`graph/waiver.py`).
Findings are hand-built directly (`coherence.Finding`/`Verdict`) rather than
through a full `Pipeline` -- this module's own logic has no dependency on a
real pipeline beyond the `Finding` values `coherence.classify()` produces,
so testing it standalone against `test_grf_coherence.py`'s already-proven
`classify()` output stays within this file's own concern (`R-REQ-9`-style:
a waiver test should fail because of waiver logic, not because a fixture
pipeline stopped loading)."""

from __future__ import annotations

import pytest

from adas_sim.diagnostics.errors import EXIT_CODES
from adas_sim.graph import waiver
from adas_sim.graph.coherence import Finding, Verdict

_BROKEN = Finding(verdict=Verdict.BROKEN, stale=("perception", "fusion"), path=("vdy", "perception", "fusion", "aeb"), landing="aeb")
_ORPHAN = Finding(verdict=Verdict.ORPHAN, stale=("perception",), path=("vdy", "perception"))


# ---------------------------------------------------------------------------
# UT-GRF-18 -- SW-0180: a waiver requires a flag and a written reason
# ---------------------------------------------------------------------------


def test_waive_succeeds_with_a_flag_and_a_reason():
    granted = waiver.waive(_BROKEN, "known gap, tracked in TICKET-123", policy=waiver.Policy(waivers_allowed=True))
    assert granted.finding is _BROKEN
    assert granted.reason == "known gap, tracked in TICKET-123"


def test_waive_refuses_an_empty_reason():
    with pytest.raises(ValueError, match="reason"):
        waiver.waive(_BROKEN, "", policy=waiver.Policy(waivers_allowed=True))


def test_waive_refuses_a_whitespace_only_reason():
    with pytest.raises(ValueError, match="reason"):
        waiver.waive(_BROKEN, "   ", policy=waiver.Policy(waivers_allowed=True))


def test_waive_refuses_a_non_broken_finding():
    with pytest.raises(ValueError, match="broken"):
        waiver.waive(_ORPHAN, "a real reason", policy=waiver.Policy(waivers_allowed=True))


def test_default_policy_allows_waivers():
    waiver.waive(_BROKEN, "a real reason")  # no policy= supplied, must not raise


# ---------------------------------------------------------------------------
# UT-GRF-19 -- SW-0181: policy can forbid waivers; the exit code is readable
# ---------------------------------------------------------------------------


def test_a_forbidding_policy_refuses_even_a_reasoned_waiver():
    with pytest.raises(waiver.WaiverForbidden):
        waiver.waive(_BROKEN, "a real reason", policy=waiver.Policy(waivers_allowed=False))


def test_waiver_forbidden_carries_the_coherence_exit_code():
    with pytest.raises(waiver.WaiverForbidden) as excinfo:
        waiver.waive(_BROKEN, "a real reason", policy=waiver.Policy(waivers_allowed=False))
    assert excinfo.value.exit_code == EXIT_CODES["coherence"] == 3


# ---------------------------------------------------------------------------
# still_blocking -- IMP-0182's companion: a waived BROKEN finding no longer
# blocks; ORPHAN never blocks regardless.
# ---------------------------------------------------------------------------


def test_still_blocking_excludes_a_waived_finding():
    granted = waiver.waive(_BROKEN, "known gap")
    assert waiver.still_blocking((_BROKEN,), (granted,)) == ()


def test_still_blocking_keeps_an_unwaived_broken_finding():
    other = Finding(verdict=Verdict.BROKEN, stale=("x",), path=("a", "x", "b"), landing="b")
    granted = waiver.waive(_BROKEN, "known gap")
    assert waiver.still_blocking((_BROKEN, other), (granted,)) == (other,)


def test_still_blocking_never_includes_orphan_findings():
    assert waiver.still_blocking((_ORPHAN,), ()) == ()
