# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-01: IMP-0372 / IMP-0408 / IMP-0418 -- `docs/v2/py/trace_check.py` is
tested, not trusted (IMP-0370, ANL-SW-66, ANL-SW-74, ANL-SW-79). Landed
2026-08-13: the script existed and ran clean, but had no planted-violation
test of its own -- `check_falsifiable` (ANL-SW-74) is extracted from
`main()`'s inline block for exactly this reason, per IMP-0408's own row
naming `trace_check.py::check_falsifiable`."""

from __future__ import annotations

import sys
from pathlib import Path

_PY_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "v2" / "py"
if str(_PY_DIR) not in sys.path:
    sys.path.insert(0, str(_PY_DIR))

import trace_check as tc  # noqa: E402


def test_main_passes_on_the_real_document_set(monkeypatch):
    """The end-to-end smoke test: the chain closes today. `main()` reads
    `sys.argv` directly (argparse's default), so pytest's own CLI args
    must not leak through -- they would otherwise fail as unrecognised
    trace_check.py flags."""
    monkeypatch.setattr(sys, "argv", ["trace_check.py"])
    assert tc.main() == 0


# ---- ANL-SW-74: check_falsifiable (IMP-0408) -------------------------------


def test_check_falsifiable_passes_on_the_real_document_set():
    sw = tc.parse_sw(tc._read(tc.SWREQ))
    assert tc.check_falsifiable(sw) == []


def test_check_falsifiable_fails_on_a_planted_missing_accept():
    sw = {"SW-9999": tc.Sw(uid="SW-9999", item="SI-99", accept="", tests={"UT-X-01"})}
    findings = tc.check_falsifiable(sw)
    assert findings
    assert "no Accept clause" in findings[0]


def test_check_falsifiable_fails_on_a_planted_missing_test():
    sw = {"SW-9999": tc.Sw(uid="SW-9999", item="SI-99", accept="something observable", tests=set())}
    findings = tc.check_falsifiable(sw)
    assert findings
    assert "cites no test identifier" in findings[0]


# ---- ANL-SW-79: roll_up's pessimistic aggregation (IMP-0418) ---------------


def test_roll_up_combine_is_pessimistic_any_open_child_makes_the_parent_partial():
    imp = {
        "IMP-0001": tc.Imp(uid="IMP-0001", serves="SW-0001", wp="WP-01", change="NEW"),
        "IMP-0002": tc.Imp(uid="IMP-0002", serves="SW-0001", wp="WP-01", change="NEW"),
    }
    sw = {"SW-0001": tc.Sw(uid="SW-0001", item="SI-01", trace=set(), tests={"UT-X-01"}, accept="x")}
    sysreqs: dict[str, tc.SysR] = {}
    imp_state = {"IMP-0001": tc.DONE, "IMP-0002": tc.OPEN}
    imp_st, sw_st, sys_st, findings = tc.roll_up(imp, sw, sysreqs, imp_state)
    assert sw_st["SW-0001"] == tc.PARTIAL  # never DONE while a sibling is open


def test_roll_up_combine_reports_orphan_when_no_child_decomposes_it():
    imp: dict[str, tc.Imp] = {}
    sw: dict[str, tc.Sw] = {}
    sysreqs = {"SYS-9999": tc.SysR(uid="SYS-9999", trace={"CN-0001"}, tests={"ANL-1"}, accept="x")}
    imp_st, sw_st, sys_st, findings = tc.roll_up(imp, sw, sysreqs, {})
    assert sys_st["SYS-9999"] == tc.ORPHAN  # a gap in decomposition, never coloured as progress


def test_roll_up_deferred_imp_does_not_count_as_open():
    """An `IMP` with no work package is DEFERRED, and a `SW` whose only
    child is deferred stays DEFERRED too -- not OPEN, which would read as
    unstarted work rather than out-of-scope work."""
    imp = {"IMP-0001": tc.Imp(uid="IMP-0001", serves="SW-0001", wp="", change="DROP")}
    sw = {"SW-0001": tc.Sw(uid="SW-0001", item="SI-01", trace=set(), tests={"UT-X-01"}, accept="x")}
    imp_st, sw_st, sys_st, findings = tc.roll_up(imp, sw, {}, {})
    assert imp_st["IMP-0001"] == tc.DEFERRED
    assert sw_st["SW-0001"] == tc.DEFERRED


# ---- apply_built idempotency (IMP-0418, the fourth ANL-SW-79 case) --------


def test_apply_built_is_idempotent():
    text = "**`SW-0001`**\n**Trace.** SYS-0001\nsome trailing prose\n"
    once = tc.apply_built(text, "SW", lambda u: "**Built.** ● done -- x")
    twice = tc.apply_built(once, "SW", lambda u: "**Built.** ● done -- x")
    assert once == twice


def test_apply_built_skips_fenced_code_blocks():
    """A specimen line inside a fenced block is prose about the field, not
    a real requirement block -- rewriting inside one is the exact defect
    this guard exists to prevent (module docstring, `apply_built`)."""
    text = "```\n**`SW-0001`**\n**Trace.** SYS-0001\n```\n"
    out = tc.apply_built(text, "SW", lambda u: "**Built.** ● done -- x")
    assert out == text  # untouched -- the block is fenced


# ---- read_built / write-status disagreement (the fifth check main() does) -


def test_read_built_finds_a_planted_built_line():
    text = "**`SW-0001`**\n**Trace.** SYS-0001\n**Built.** ● done -- x\n"
    found = tc.read_built(text, "SW")
    assert found["SW-0001"] == "**Built.** ● done -- x"


def test_read_built_reports_nothing_when_no_built_line_present():
    text = "**`SW-0001`**\n**Trace.** SYS-0001\n"
    assert tc.read_built(text, "SW") == {}
