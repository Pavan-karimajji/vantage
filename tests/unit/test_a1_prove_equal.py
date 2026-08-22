# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-15a: IMP-0019 / SW-0019 / ANL-SW-09 -- `prove_equal.py` is tested, not
trusted (IMP-0370). These are structural/unit tests against synthetic rows
-- they do not require sil_host's or simcore's gtest binaries to be built,
so this file is green regardless of what a given checkout has compiled.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from prove_equal import ROWS, Row, RowResult, main, prove_equal  # noqa: E402


def _fake_pass(row: Row) -> RowResult:
    return RowResult(row, "PASS", "synthetic pass")


def _fake_pending(row: Row) -> RowResult:
    return RowResult(row, "PENDING", "synthetic pending, closed by: nothing real -- test only")


def _fake_fail(row: Row) -> RowResult:
    return RowResult(row, "FAIL", "synthetic planted failure")


def test_all_seven_rows_are_named_and_carry_a_non_empty_corpus():
    assert [r.n for r in ROWS] == [1, 2, 3, 4, 5, 6, 7]
    for row in ROWS:
        assert row.capability
        assert row.survivor
        assert row.dies
        assert row.corpus, f"row {row.n} ({row.capability}) has no corpus named"


def test_row_capabilities_match_design_section_28_3():
    names = [r.capability for r in ROWS]
    assert names == [
        "Recording read and cycle grouping",
        "Pipeline load and validation",
        "Ingest map parsing",
        "Component host",
        "Base-grid computation",
        "Library resolution",
        "Codec implementation",
    ]


def test_prove_equal_returns_one_result_per_row_in_order():
    rows = (Row(1, "a", "sv", "d", ("x",), _fake_pass), Row(2, "b", "sv", "d", ("y",), _fake_pending))
    results = prove_equal(rows)
    assert [r.status for r in results] == ["PASS", "PENDING"]


def test_main_exits_zero_when_all_rows_pass(monkeypatch, capsys):
    monkeypatch.setattr("prove_equal.ROWS", (Row(1, "a", "sv", "d", ("x",), _fake_pass),))
    monkeypatch.setattr("prove_equal.prove_equal", lambda rows=None: [_fake_pass(Row(1, "a", "sv", "d", ("x",), _fake_pass))])
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "0 FAIL" in out


def test_main_exits_zero_when_a_row_is_honestly_pending_not_fabricated_green(monkeypatch, capsys):
    monkeypatch.setattr("prove_equal.prove_equal", lambda rows=None: [_fake_pending(Row(1, "a", "sv", "d", ("x",), _fake_pending))])
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "1 PENDING" in out
    assert "PENDING" in out


def test_main_exits_nonzero_on_a_planted_unexplained_failure(monkeypatch, capsys):
    """The check's own teeth (IMP-0370): a genuine, unexplained failure must
    fail the build -- a gate that always reports green regardless of input
    is not a gate."""
    monkeypatch.setattr(
        "prove_equal.prove_equal",
        lambda rows=None: [_fake_pass(Row(1, "a", "sv", "d", ("x",), _fake_pass)),
                            _fake_fail(Row(2, "b", "sv", "d", ("y",), _fake_fail))],
    )
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 1
    assert "1 unexplained failure" in out
    assert "synthetic planted failure" in out


def test_run_pytest_reports_a_real_failure_from_a_planted_bad_test(tmp_path):
    from prove_equal import run_pytest  # noqa: PLC0415

    bad = tmp_path / "test_planted_bad.py"
    bad.write_text("def test_deliberately_false():\n    assert False\n", encoding="utf-8")
    ok, detail = run_pytest((str(bad),))
    assert ok is False
    assert "FAILED" in detail


def test_run_gtest_reports_not_built_when_no_binary_exists(tmp_path):
    from prove_equal import run_gtest  # noqa: PLC0415

    status, detail = run_gtest((tmp_path / "no_such_binary_here.exe",), "Suite.*")
    assert status == "not_built"
    assert "build it" in detail
