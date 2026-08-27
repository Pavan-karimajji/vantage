# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-07: IMP-0046 / ANL-SW-14 -- `check_time_units.py` is tested, not
trusted (`IMP-0370`)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_time_units import check_time_units  # noqa: E402


def test_check_time_units_passes_on_the_current_tree():
    assert check_time_units() == []


def test_check_time_units_catches_a_planted_float_member(tmp_path):
    planted = tmp_path / "bad.hpp"
    planted.write_text(
        "struct Header {\n"
        "  double hold_age_s;  // exactly the defect SW-0046 forbids\n"
        "  int64_t t_sim_ns = 0;\n"
        "};\n",
        encoding="utf-8",
    )
    findings = check_time_units(roots=(tmp_path,))
    assert findings
    assert "hold_age_s" in findings[0]


def test_check_time_units_ignores_a_float_time_member_inside_a_comment(tmp_path):
    planted = tmp_path / "commented.hpp"
    planted.write_text(
        "struct Header {\n"
        "  // double hold_age_s;  -- deliberately commented out, not a real member\n"
        "  int64_t t_sim_ns = 0;\n"
        "};\n",
        encoding="utf-8",
    )
    assert check_time_units(roots=(tmp_path,)) == []


def test_a_time_boundary_marker_exempts_the_line_but_a_bare_one_does_not(tmp_path):
    """R-REQ-9's planted-violation pair for the `TIME-BOUNDARY:` exemption.

    SW-0046 permits float seconds at a boundary. The marker is what makes a
    boundary claim explicit and greppable; a marker with no stated reason is
    a silencer, and must not exempt anything.
    """
    exempt = tmp_path / "boundary.hpp"
    exempt.write_text(
        "struct Meta {\n"
        "  double age_s = 0.0;  // TIME-BOUNDARY: the component ABI takes float seconds\n"
        "};\n",
        encoding="utf-8",
    )
    assert check_time_units(roots=(tmp_path,)) == []

    # A marker with no reason after the colon exempts nothing.
    bare = tmp_path / "bare.hpp"
    bare.write_text(
        "struct Meta {\n"
        "  double age_s = 0.0;  // TIME-BOUNDARY:\n"
        "};\n",
        encoding="utf-8",
    )
    exempt.unlink()
    findings = check_time_units(roots=(tmp_path,))
    assert findings, "a reasonless TIME-BOUNDARY marker must not exempt the line"
    assert "age_s" in findings[0]

    # And a plain interior float second is still caught with no marker at all.
    bare.write_text(
        "struct Meta {\n"
        "  double age_s = 0.0;\n"
        "};\n",
        encoding="utf-8",
    )
    assert check_time_units(roots=(tmp_path,))

def test_check_time_units_ignores_a_float_member_with_an_unrelated_name(tmp_path):
    planted = tmp_path / "ok.hpp"
    planted.write_text(
        "struct Scale {\n"
        "  double scale_factor;  // not a time quantity at all\n"
        "};\n",
        encoding="utf-8",
    )
    assert check_time_units(roots=(tmp_path,)) == []
