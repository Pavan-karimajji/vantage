# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""WP-17: IMP-0113 / ANL-06 (SYS-0104) -- ``check_supervisor_boundary.py`` is tested, not trusted.

ANL-06 .c1 is the clean run over ``src/simengine``, .c2 a planted ``liveMeasStep`` call and .c3 a planted
``Component::Exec`` call in ``RunWithSupervision``, each reported with file and line; the script's own
``--selftest`` plants the same two in a copy of the real file (R-REQ-9).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import check_supervisor_boundary as script  # noqa: E402

MAIN = "src/simengine/main.cpp"

CLEAN = """\
// RunWithSupervision never calls liveMeasStep or Component::Exec: this is a comment
SimExitCode RunOnce(const Args& args) {
  return RunStage(args);  // the worker's path, outside the supervisor's functions
}
SimExitCode RunWithSupervision(const Args& args) {
  const char* note = "liveMeasClose in a message";
  return ClassifyWorkerEnd(note);
}
SimExitCode ClassifyWorkerEnd(const char*) { return kSimExitOk; }
"""


@pytest.fixture
def clean_tree(tmp_path):
    path = tmp_path / MAIN
    path.parent.mkdir(parents=True)
    path.write_text(CLEAN, encoding="utf-8")
    return tmp_path


def plant(root: Path, line: str) -> None:
    path = root / MAIN
    text = path.read_text(encoding="utf-8")
    anchor = "SimExitCode RunWithSupervision(const Args& args) {\n"
    path.write_text(text.replace(anchor, anchor + line + "\n"), encoding="utf-8")


def test_anl_06_c1_a_clean_tree_has_no_finding(clean_tree, capsys):
    """ANL-06 .c1: no finding (a run call outside the supervisor's functions, and words in a comment or a string,
    are not findings)."""
    assert script.check_supervisor_boundary(clean_tree) == []
    assert script.main(["--root", str(clean_tree)]) == 0
    assert "clean" in capsys.readouterr().out


def test_anl_06_c1_the_real_supervisor_has_no_finding():
    """ANL-06 .c1 over the file as checked in."""
    assert script.check_supervisor_boundary(script.SIM_ROOT) == []


def test_anl_06_c2_a_planted_live_meas_step_is_reported_with_file_and_line(clean_tree, capsys):
    """ANL-06 .c2: the planted ``liveMeasStep`` is reported with file and line."""
    plant(clean_tree, "  liveMeasStep(handle, 0, 0, nullptr, 0, nullptr, 0);")
    findings = script.check_supervisor_boundary(clean_tree)
    assert len(findings) == 1
    assert findings[0].startswith(f"{MAIN}:6: liveMeasStep in RunWithSupervision: ")
    assert script.main(["--root", str(clean_tree)]) == 1
    assert f"{MAIN}:6:" in capsys.readouterr().out


def test_anl_06_c3_a_planted_component_exec_is_reported_with_file_and_line(clean_tree):
    """ANL-06 .c3: the planted ``Component::Exec`` call is reported with file and line."""
    plant(clean_tree, "  simcore::module_host::Component::Exec(component, 0);")
    findings = script.check_supervisor_boundary(clean_tree)
    assert len(findings) == 1
    assert findings[0].startswith(f"{MAIN}:6: Component::Exec in RunWithSupervision: ")


def test_anl_06_a_planted_run_stage_and_live_meas_close_are_reported(clean_tree):
    plant(clean_tree, "  RunStage(args);\n  liveMeasClose(handle, 1);")
    kinds = sorted(f.split(": ")[1].split(" ")[0] for f in script.check_supervisor_boundary(clean_tree))
    assert kinds == ["RunStage", "liveMeasClose"]


def test_selftest_plants_c2_and_c3_in_the_real_file_and_passes(capsys):
    assert script.selftest() == 0
    assert capsys.readouterr().out.count("PASS") == 2
