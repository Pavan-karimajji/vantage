# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""SM-02's own exit-gate check, tested rather than trusted (R-REQ-9):
ANL-SM-04 -- a consumer linking `adas-sim::io` acquires no engine
dependency and no first-party component, checked by parsing the resolved
Conan graph."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_engine_boundary import check_anl_sm_04  # noqa: E402

CLEAN_REFS = [
    "adas-sim/0.1.0",
    "mcap/1.2.0#2646e6d7f5fb6342d08b96ab6c31502b",
    "lz4/1.9.4#a2f02ad3908618757c68d3618256a196",
    "zstd/1.5.5#a4398ab5244b10fb081eeac217b5ef9f",
]

# Planted violation: as if `simcore` had gained a first-party requires --
# exactly the trigger SM-02's own escape-hatch note names ("the day
# adas-sim gains a first-party requires on a component").
DIRTY_REFS = CLEAN_REFS + ["adas-df/1.0.0"]


def test_check_anl_sm_04_passes_on_the_real_resolved_graph_shape():
    assert check_anl_sm_04(CLEAN_REFS) == []


def test_check_anl_sm_04_fails_on_a_planted_first_party_dependency():
    findings = check_anl_sm_04(DIRTY_REFS)
    assert findings
    assert "ANL-SM-04" in findings[0]
    assert "adas-df" in findings[0]


def test_check_anl_sm_04_fails_on_an_empty_graph():
    """Scope-staleness guard, same discipline check_no_sim_edge.py's own
    ANL-VZ-05 uses -- an empty ref list must never read as a silent pass."""
    findings = check_anl_sm_04([])
    assert findings
    assert "stale" in findings[0]


def test_check_anl_sm_04_fails_if_adas_sim_itself_is_missing():
    """A second staleness guard: a graph with no adas-sim/* ref at all means
    this was never adas-sim's own graph in the first place."""
    findings = check_anl_sm_04(["mcap/1.2.0"])
    assert findings
    assert "stale" in findings[0]
