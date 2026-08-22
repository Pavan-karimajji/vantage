# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-15a: IMP-0019 / ANL-SW-09 -- `check_coverage_delta.py` is tested, not
trusted (IMP-0370). Exercises `check_against_baseline` against a synthetic
baseline file, never the real `coverage_baseline.json` -- these tests do
not depend on any gtest binary being built."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import check_coverage_delta as ccd  # noqa: E402


def _write_baseline(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps({"provenance": {}, "rows": rows}), encoding="utf-8")


def test_check_against_baseline_passes_when_survivor_count_holds(tmp_path):
    baseline = tmp_path / "baseline.json"
    _write_baseline(baseline, [{"row": 2, "capability": "x", "survivor_count": 49}])
    with mock.patch.object(ccd, "measure_row", return_value={"row": 2, "capability": "x", "survivor_count": 49}):
        findings = ccd.check_against_baseline(baseline)
    assert findings == []


def test_check_against_baseline_fails_on_a_planted_coverage_drop(tmp_path):
    """The exact defect ANL-SW-09 exists to catch: a deletion that silently
    drops a test case."""
    baseline = tmp_path / "baseline.json"
    _write_baseline(baseline, [{"row": 2, "capability": "pipeline load", "survivor_count": 49}])
    with mock.patch.object(ccd, "measure_row", return_value={"row": 2, "capability": "pipeline load", "survivor_count": 40}):
        findings = ccd.check_against_baseline(baseline)
    assert len(findings) == 1
    assert "49 -> 40" in findings[0]


def test_check_against_baseline_reports_missing_baseline_file(tmp_path):
    findings = ccd.check_against_baseline(tmp_path / "does_not_exist.json")
    assert len(findings) == 1
    assert "no baseline" in findings[0]


def test_check_against_baseline_flags_a_survivor_that_became_unmeasurable(tmp_path):
    baseline = tmp_path / "baseline.json"
    _write_baseline(baseline, [{"row": 4, "capability": "component host", "survivor_count": 14}])
    with mock.patch.object(ccd, "measure_row", return_value={"row": 4, "capability": "component host", "survivor_count": None}):
        findings = ccd.check_against_baseline(baseline)
    assert len(findings) == 1
    assert "no longer measurable" in findings[0]


def test_main_check_exits_nonzero_on_regression(tmp_path, monkeypatch, capsys):
    baseline = tmp_path / "baseline.json"
    monkeypatch.setattr(ccd, "BASELINE_PATH", baseline)
    with mock.patch.object(ccd, "check_against_baseline", return_value=["row 2: dropped"]):
        rc = ccd.main(["--check"])
    assert rc == 1
    assert "1 coverage regression" in capsys.readouterr().out


def test_main_check_exits_zero_when_clean(monkeypatch, capsys):
    with mock.patch.object(ccd, "check_against_baseline", return_value=[]):
        rc = ccd.main(["--check"])
    assert rc == 0
    assert "no regression" in capsys.readouterr().out
