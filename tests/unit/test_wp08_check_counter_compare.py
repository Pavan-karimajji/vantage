# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""WP-08: IMP-0038 / ANL-02 (SYS-0031) -- ``check_counter_compare.py`` is tested, not trusted.

ANL-02 .c1 is the clean run, .c2 a planted ``<`` and .c3 a planted ``==``, each reported with file and line; the
script's own ``--selftest`` plants the same two in a copy of the real tree (R-REQ-9). Comparing the result of
``counterDistance`` or ``MeasurementCounterDistance`` is allowed.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import check_counter_compare as script  # noqa: E402

SAMPLE_BUFFER = "src/simcore/bus/sample_buffer.cpp"
ORCHESTRATOR = "src/simcore/orchestrator/orchestrator.cpp"

CLEAN = """\
#include <vector>
// a.measurement_counter < b.measurement_counter, in a comment
std::int32_t Same(const Sample& a, const Sample& b) {
  const char* note = "measurement_counter == 0";
  std::vector<std::uint32_t> counters;
  const auto cycle = static_cast<std::int32_t>(a.cycle_counter);
  header.measurement_counter = 7;
  if (!header.measurement_counter.has_value()) return 0;
  if (adas::common::counterDistance(a.measurement_counter, b.measurement_counter) == 0) return 1;
  if (bus::MeasurementCounterDistance(a.cycle_counter, b.cycle_counter) < 0) return -1;
  return counterDistance(a.measurement_counter, b.measurement_counter) >= 2 ? 2 : 3;
}
"""


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def clean_tree(tmp_path):
    write(tmp_path, SAMPLE_BUFFER, CLEAN)
    write(tmp_path, ORCHESTRATOR, "int Run() { return 0; }\n")
    write(tmp_path, "include/simcore/bus.hpp", "struct SignalHeader {\n  Unknown<std::uint32_t> measurement_counter;\n};\n")
    return tmp_path


def append(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def test_anl_02_c1_a_clean_tree_has_no_finding_and_a_distance_may_be_compared(clean_tree, capsys):
    assert script.check_counter_compare(clean_tree) == []
    assert script.main(["--root", str(clean_tree)]) == 0
    assert "clean" in capsys.readouterr().out


def test_anl_02_c2_a_planted_less_than_is_reported_with_file_and_line(clean_tree, capsys):
    append(clean_tree, SAMPLE_BUFFER, "bool Before(const Sample& a, const Sample& b) { return a.measurement_counter < b.measurement_counter; }\n")
    findings = script.check_counter_compare(clean_tree)
    assert len(findings) == 1
    assert findings[0].startswith(f"{SAMPLE_BUFFER}:13: < on measurement_counter: ")
    assert script.main(["--root", str(clean_tree)]) == 1
    assert f"{SAMPLE_BUFFER}:13:" in capsys.readouterr().out


def test_anl_02_c3_a_planted_equality_is_reported_with_file_and_line(clean_tree):
    append(clean_tree, ORCHESTRATOR, "bool Same(const Sample& a, const Sample& b) { return a.measurement_counter == b.measurement_counter; }\n")
    findings = script.check_counter_compare(clean_tree)
    assert len(findings) == 1
    assert findings[0].startswith(f"{ORCHESTRATOR}:2: == on measurement_counter: ")


@pytest.mark.parametrize("operator", ["==", "!=", "<", ">", "<=", ">="])
def test_anl_02_every_comparison_operator_is_reported_on_either_counter_and_on_either_side(clean_tree, operator):
    append(clean_tree, ORCHESTRATOR, f"bool A(const H& h, int x) {{ return h.cycle_counter {operator} x; }}\n")
    append(clean_tree, ORCHESTRATOR, f"bool B(const H& h, int x) {{ return x {operator} h.measurement_counter(); }}\n")
    findings = script.check_counter_compare(clean_tree)
    assert [f.split(":")[1] for f in findings] == ["2", "3"]
    assert all(f" {operator} on " in f for f in findings)


def test_anl_02_a_comparison_split_over_two_lines_is_reported_at_its_operator(clean_tree):
    append(clean_tree, ORCHESTRATOR, "bool C(const H& a, const H& b) {\n  return ready &&\n         a.measurement_counter ==\n         b.measurement_counter;\n}\n")
    findings = script.check_counter_compare(clean_tree)
    assert len(findings) == 1 and findings[0].startswith(f"{ORCHESTRATOR}:4: == on measurement_counter")


def test_anl_02_a_distance_compared_with_a_counter_is_still_reported(clean_tree):
    append(clean_tree, ORCHESTRATOR, "bool D(const H& a, const H& b, const H& c) { return counterDistance(a.measurement_counter, b.measurement_counter) == c.measurement_counter; }\n")
    assert len(script.check_counter_compare(clean_tree)) == 1


def test_anl_02_selftest_plants_both_violations_in_a_copy_of_the_real_tree_and_leaves_the_tree_alone(capsys):
    before = script.check_counter_compare()
    assert script.main(["--selftest"]) == 0
    out = capsys.readouterr().out
    assert "ANL-02 .c2" in out and "ANL-02 .c3" in out and "FAIL" not in out
    assert script.check_counter_compare() == before


def test_anl_02_selftest_fails_when_a_planted_violation_would_not_be_reported(tmp_path, monkeypatch, capsys):
    """The selftest is itself checked: with the counter name matcher gone the copies pass and the selftest says so."""
    for entry in script.DEFAULT_ROOTS:
        shutil.copytree(script.SIM_ROOT / entry, tmp_path / entry)
    monkeypatch.setattr(script, "_COUNTER", re.compile(r"\bno_such_counter\b"))
    assert script.selftest(tmp_path) == 1
    out = capsys.readouterr().out
    assert "ANL-02 .c2 (<): FAIL" in out and "ANL-02 .c3 (==): FAIL" in out
