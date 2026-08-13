# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-01: IMP-0020 / ANL-SW-10 -- `check_no_duplication.py` is tested, not
trusted (IMP-0370)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_no_duplication import CAPABILITY_HOMES, KNOWN_PENDING_DUPLICATION, check_no_duplication  # noqa: E402


def _write(path: Path, text: str = "x = 1\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_check_no_duplication_passes_on_the_current_skeleton():
    findings, notes, checked = check_no_duplication()
    assert findings == []
    assert checked == 7
    assert len(notes) == len(KNOWN_PENDING_DUPLICATION)


def test_check_no_duplication_all_seven_capabilities_are_named():
    assert set(CAPABILITY_HOMES) == {
        "pipeline_load_validate", "ingest_map_parse", "component_host",
        "recording_read_group", "library_resolve", "multi_rate_scheduler",
        "codec",
    }


def test_check_no_duplication_fails_on_a_planted_new_codec_duplication(tmp_path):
    """The one capability with no known-pending entry: a C++ codec
    appearing beside the Python one, with neither deleted, must fail
    immediately -- this is the check's real teeth from day one."""
    py = tmp_path / "mcap.py"
    cpp = tmp_path / "mcap.cpp"
    _write(py)
    _write(cpp)
    findings, notes, checked = check_no_duplication(homes={"codec": (py, cpp)}, known_pending={})
    assert checked == 1
    assert findings
    assert "codec" in findings[0]
    assert "two implementations" in findings[0]


def test_check_no_duplication_reports_stale_known_pending_entry(tmp_path):
    """WP-16 deletes the sil_host half; if only one home remains, the
    KNOWN_PENDING_DUPLICATION entry is now stale and must be removed --
    the check catches a forgotten cleanup, same as trace_check.py's
    bidirectional KNOWN_UNPARENTED check."""
    py = tmp_path / "pipeline.py"
    cpp = tmp_path / "pipeline.cpp"
    _write(py)
    # cpp half deleted by WP-16 -- do not create it.
    findings, notes, checked = check_no_duplication(
        homes={"pipeline_load_validate": (py, cpp)},
        known_pending={"pipeline_load_validate": "closed by WP-16"},
    )
    assert checked == 1
    assert findings
    assert "only one home remains" in findings[0]


def test_check_no_duplication_known_pending_entry_with_both_homes_is_a_note_not_a_failure(tmp_path):
    py = tmp_path / "pipeline.py"
    cpp = tmp_path / "pipeline.cpp"
    _write(py)
    _write(cpp)
    findings, notes, checked = check_no_duplication(
        homes={"pipeline_load_validate": (py, cpp)},
        known_pending={"pipeline_load_validate": "closed by WP-16"},
    )
    assert findings == []
    assert len(notes) == 1


def test_check_no_duplication_single_home_is_clean(tmp_path):
    py = tmp_path / "mcap.py"
    cpp = tmp_path / "mcap.cpp"  # never created
    _write(py)
    findings, notes, checked = check_no_duplication(homes={"codec": (py, cpp)}, known_pending={})
    assert findings == []
    assert notes == []
