# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""WP-16: IMP-0102 / ANL-05 (SYS-0087) -- ``check_inspector_items.py`` is tested, not trusted.

ANL-05 .c1 is the clean run over ``src/inspector``, .c2 a planted ``"B.refSync"`` literal in ``check.cpp`` reported
with file and line; the script's own ``--selftest`` plants the same in a copy of the real tree (R-REQ-9).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import check_inspector_items as script  # noqa: E402

CHECK = "src/inspector/check.cpp"


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def clean_tree(tmp_path):
    write(
        tmp_path,
        CHECK,
        '#include "inspector.hpp"\n'
        "// a name in a comment: B.refSync\n"
        'const char* const kRole = "control";\n'
        "int Check() { return 0; }\n",
    )
    return tmp_path


def test_anl_05_c1_a_clean_tree_has_no_finding(clean_tree, capsys):
    """ANL-05 .c1: no finding."""
    assert script.check_inspector_items(clean_tree) == []
    assert script.main(["--root", str(clean_tree)]) == 0
    assert "clean" in capsys.readouterr().out


def test_anl_05_c1_the_real_inspector_has_no_finding():
    """ANL-05 .c1 over the tree as checked in."""
    names = script.catalogue_names(script.DEFAULT_CATALOGUE) if script.DEFAULT_CATALOGUE.is_dir() else set()
    assert script.check_inspector_items(script.SIM_ROOT, names) == []


def test_anl_05_c2_a_planted_stage_port_literal_is_reported_with_file_and_line(clean_tree, capsys):
    """ANL-05 .c2: the planted ``"B.refSync"`` is reported with file and line."""
    path = clean_tree / CHECK
    path.write_text(path.read_text(encoding="utf-8") + 'const char* const kPlanted = "B.refSync";\n', encoding="utf-8")
    findings = script.check_inspector_items(clean_tree)
    assert len(findings) == 1
    assert findings[0].startswith(f"{CHECK}:5: stage.port literal: ")
    assert script.main(["--root", str(clean_tree)]) == 1
    assert f"{CHECK}:5:" in capsys.readouterr().out


def test_anl_05_a_catalogue_name_literal_is_reported(clean_tree):
    path = clean_tree / CHECK
    path.write_text(path.read_text(encoding="utf-8") + 'const char* const kPlanted = "Cam";\n', encoding="utf-8")
    assert script.check_inspector_items(clean_tree) == []  # not a name the scan knows without a catalogue
    findings = script.check_inspector_items(clean_tree, {"Cam", "X"})
    assert len(findings) == 1 and ":5: catalogue name literal: " in findings[0]


def test_anl_05_catalogue_names_are_the_sources_and_components_of_the_topology_files(tmp_path):
    write(
        tmp_path,
        "t.yaml",
        "topology: t\nsources:\n  - {name: X, period_ms: 10}\ncomponents:\n  - name: B\n    period_ms: 4\n"
        "scenarios:\n  - name: base\n",
    )
    assert script.catalogue_names(tmp_path) == {"X", "B"}


def test_selftest_plants_c2_in_the_real_tree_and_passes(capsys):
    assert script.selftest() == 0
    assert "PASS" in capsys.readouterr().out
