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

from check_closed_sets import _CLOSED_SETS, check_closed_sets  # noqa: E402


def test_check_closed_sets_passes_on_the_current_skeleton():
    findings, checked, not_yet = check_closed_sets()
    assert findings == []
    assert checked == 3  # OverrideVerb, FaultVerb, Origin
    assert not_yet == 3  # Rung, MergePolicy, ErrorKind


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
            "OverrideVerb": ("py", (__name__, "_seven_verbs_holder"), None, frozenset(
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
            "OverrideVerb": ("py", (__name__, "_five_verbs_holder"), None, frozenset(
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
            "Nonexistent": ("py", ("adas_sim.does_not_exist", "Whatever"), None, frozenset(), "N/A"),
        }
    )
    assert checked == 1
    assert findings
    assert "cannot import" in findings[0]


def test_check_closed_sets_fails_on_a_planted_cpp_origin_extra_value(tmp_path):
    """ANL-SW-15's own planted-violation case, over the C++ path (R-REQ-9):
    a seventh Origin value added to bus.hpp without a requirement change."""
    planted = tmp_path / "bus.hpp"
    planted.write_text(
        "enum class Origin { Measured, Truth, Mocked, Simulated, Overridden, Unknown, Sneaky };\n",
        encoding="utf-8",
    )
    findings, checked, not_yet = check_closed_sets(
        closed_sets={
            "Origin": ("cpp", None, (planted, "Origin"), frozenset(
                {"measured", "truth", "mocked", "simulated", "overridden", "unknown"}
            ), "SW-0048"),
        }
    )
    assert checked == 1
    assert findings
    assert "unexpected" in findings[0]
    assert "sneaky" in findings[0]


def test_check_closed_sets_passes_on_the_real_cpp_origin_enum():
    findings, checked, not_yet = check_closed_sets(
        closed_sets={"Origin": _CLOSED_SETS["Origin"]}
    )
    assert findings == []
    assert checked == 1


def test_check_closed_sets_reports_unreadable_cpp_header(tmp_path):
    findings, checked, not_yet = check_closed_sets(
        closed_sets={
            "Origin": ("cpp", None, (tmp_path / "does_not_exist.hpp", "Origin"), frozenset(), "SW-0048"),
        }
    )
    assert checked == 1
    assert findings
    assert "cannot read" in findings[0]
