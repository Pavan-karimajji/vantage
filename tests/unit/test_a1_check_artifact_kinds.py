# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-01: IMP-0415 / ANL-SW-76 -- `check_artifact_kinds.py` is tested, not
trusted (IMP-0370)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_artifact_kinds import check_artifact_kinds  # noqa: E402


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_check_artifact_kinds_passes_on_the_real_conf_file():
    findings, checked = check_artifact_kinds()
    assert findings == []
    # 3 kinds, down from 5 (was recording/export/run_manifest/report/snapshot;
    # export/snapshot retired 2026-08-29 with the Python scene/render/player
    # tree that wrote them, SM-12) -> recording/run_manifest/report.
    assert checked == 3


def test_check_artifact_kinds_reports_missing_yaml(tmp_path):
    findings, checked = check_artifact_kinds(sim_root=tmp_path, kinds_yaml=tmp_path / "nope.yaml")
    assert checked == 0
    assert findings
    assert "does not exist" in findings[0]


def test_check_artifact_kinds_fails_on_a_planted_orphaned_writer(tmp_path):
    """The exact defect the check exists for: a writer that was renamed or
    deleted but whose kind declaration was not updated."""
    _write(tmp_path, "src/writer.py", "def real_writer():\n    pass\n")
    kinds_yaml = tmp_path / "artifact_kinds.yaml"
    kinds_yaml.write_text(
        "kinds:\n"
        "  - name: recording\n"
        "    cited: false\n"
        "    writers:\n"
        "      - src/writer.py::renamed_away\n",
        encoding="utf-8",
    )
    findings, checked = check_artifact_kinds(sim_root=tmp_path, kinds_yaml=kinds_yaml)
    assert checked == 1
    assert findings
    assert "orphaned declaration" in findings[0]


def test_check_artifact_kinds_passes_on_a_planted_valid_writer(tmp_path):
    _write(tmp_path, "src/writer.py", "def real_writer():\n    pass\n")
    kinds_yaml = tmp_path / "artifact_kinds.yaml"
    kinds_yaml.write_text(
        "kinds:\n"
        "  - name: recording\n"
        "    cited: false\n"
        "    writers:\n"
        "      - src/writer.py::real_writer\n",
        encoding="utf-8",
    )
    findings, checked = check_artifact_kinds(sim_root=tmp_path, kinds_yaml=kinds_yaml)
    assert findings == []
    assert checked == 1


def test_check_artifact_kinds_fails_on_a_kind_declared_with_no_writers(tmp_path):
    kinds_yaml = tmp_path / "artifact_kinds.yaml"
    kinds_yaml.write_text(
        "kinds:\n"
        "  - name: mystery\n"
        "    cited: false\n"
        "    writers: []\n",
        encoding="utf-8",
    )
    findings, checked = check_artifact_kinds(sim_root=tmp_path, kinds_yaml=kinds_yaml)
    assert checked == 1
    assert findings
    assert "no writers" in findings[0]
