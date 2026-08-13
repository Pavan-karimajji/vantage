# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-01: IMP-0371 / ANL-SW-65 -- `check_trace.py` is tested, not trusted
(IMP-0370)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_trace import check_test_ids_appear_in_tests, run_trace_check  # noqa: E402


def test_run_trace_check_passes_on_the_current_document_set():
    assert run_trace_check() == 0


def test_check_test_ids_appear_in_tests_finds_an_id_present_in_a_planted_file(tmp_path):
    """A cited id that genuinely appears in a test file (by docstring
    citation, this module's own convention) is not reported missing."""
    cited_id = "ANL-SW-10"  # a real IMP-0020 test id, cited in SwReq's Verify column
    (tmp_path / "test_planted.py").write_text(
        f'"""Exercises {cited_id}."""\n\ndef test_planted():\n    assert True\n',
        encoding="utf-8",
    )
    findings, checked = check_test_ids_appear_in_tests(tests_root=tmp_path)
    assert checked > 0
    missing = {f.split(":")[0] for f in findings}
    assert cited_id not in missing


def test_check_test_ids_appear_in_tests_fails_on_a_planted_missing_id(tmp_path):
    """The check is tested, not trusted: a cited id absent from every test
    file must be reported, not silently passed."""
    (tmp_path / "test_empty.py").write_text("def test_nothing():\n    assert True\n", encoding="utf-8")

    findings, checked = check_test_ids_appear_in_tests(tests_root=tmp_path)
    assert checked > 0
    assert findings
    assert "cited by a requirement" in findings[0]


def test_check_test_ids_appear_in_tests_reports_missing_root(tmp_path):
    missing_root = tmp_path / "does_not_exist"
    findings, checked = check_test_ids_appear_in_tests(tests_root=missing_root)
    assert checked == 0
    assert findings
    assert "does not exist" in findings[0]
