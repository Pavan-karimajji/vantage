# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-01: IMP-0106 / IMP-0361 / ANL-SW-24 -- `check_closed_sets.py` is
tested, not trusted (IMP-0370)."""

from __future__ import annotations

import sys
from enum import StrEnum
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_closed_sets import check_closed_sets  # noqa: E402


def test_check_closed_sets_passes_on_the_current_skeleton():
    findings, checked, not_yet = check_closed_sets()
    assert findings == []
    assert checked == 2  # OverrideVerb, FaultVerb
    assert not_yet == 4  # Origin, Rung, MergePolicy, ErrorKind


def test_check_closed_sets_fails_on_a_planted_extra_verb():
    """The exact defect the check exists for: a seventh verb added without
    a requirement change."""

    class _SevenVerbs(StrEnum):
        CONST = "const"
        HOLD = "hold"
        OFFSET = "offset"
        SCALE = "scale"
        SELECT = "select"
        DROP = "drop"
        SNEAKY = "insert"  # the exact thing R-SIM-15 forbids

    # Import path must resolve via module attribute lookup, so expose the
    # fake enum on this test module under the expected name.
    globals()["_seven_verbs_holder"] = _SevenVerbs
    findings, checked, not_yet = check_closed_sets(
        closed_sets={
            "OverrideVerb": (__name__, "_seven_verbs_holder", frozenset(
                {"const", "hold", "offset", "scale", "select", "drop"}
            ), "R-SIM-15"),
        }
    )
    assert checked == 1
    assert findings
    assert "unexpected" in findings[0]
    assert "insert" in findings[0]


def test_check_closed_sets_fails_on_a_planted_missing_verb():
    class _FiveVerbs(StrEnum):
        CONST = "const"
        HOLD = "hold"
        OFFSET = "offset"
        SCALE = "scale"
        SELECT = "select"
        # DROP missing

    globals()["_five_verbs_holder"] = _FiveVerbs
    findings, checked, not_yet = check_closed_sets(
        closed_sets={
            "OverrideVerb": (__name__, "_five_verbs_holder", frozenset(
                {"const", "hold", "offset", "scale", "select", "drop"}
            ), "R-SIM-15"),
        }
    )
    assert checked == 1
    assert findings
    assert "missing" in findings[0]
    assert "drop" in findings[0]


def test_check_closed_sets_reports_unimportable_module():
    findings, checked, not_yet = check_closed_sets(
        closed_sets={
            "Nonexistent": ("adas_sim.does_not_exist", "Whatever", frozenset(), "N/A"),
        }
    )
    assert checked == 1
    assert findings
    assert "cannot import" in findings[0]
