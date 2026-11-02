# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""WP-08: IMP-0037 / ANL-01 (SYS-0017) -- ``check_engine_decisions.py`` is tested, not trusted.

ANL-01 .c1 is the clean run, .c2 a planted clock call and .c3 a planted payload parse, each reported with file and
line; the script's own ``--selftest`` plants the same two in a copy of the real tree (R-REQ-9).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import check_engine_decisions as script  # noqa: E402

ORCHESTRATOR = "src/simcore/orchestrator/orchestrator.cpp"
SELECT_INPUTS = "src/simcore/runner/select_inputs.cpp"


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def clean_tree(tmp_path):
    write(
        tmp_path,
        ORCHESTRATOR,
        "// the clock: std::chrono::steady_clock::now() is only named here\n"
        "int Step(int a) {\n"
        '  const char* note = "ParseFromArray and steady_clock in a message";\n'
        "  return a + 100'000;\n"
        "}\n",
    )
    write(tmp_path, SELECT_INPUTS, "SignalHeader h = bus::ReadSignalHeader(payload, descriptor);\n")
    write(tmp_path, "src/simcore/runner/read_ahead.cpp", "int ReadAhead() { return 0; }\n")
    return tmp_path


def test_anl_01_c1_a_clean_tree_has_no_finding(clean_tree, capsys):
    assert script.check_engine_decisions(clean_tree) == []
    assert script.main(["--root", str(clean_tree)]) == 0
    assert "clean" in capsys.readouterr().out


def test_anl_01_c2_a_planted_clock_call_is_reported_with_file_and_line(clean_tree, capsys):
    path = clean_tree / ORCHESTRATOR
    path.write_text(path.read_text(encoding="utf-8") + "auto t = std::chrono::steady_clock::now();\n", encoding="utf-8")
    findings = script.check_engine_decisions(clean_tree)
    assert len(findings) == 1
    assert findings[0].startswith(f"{ORCHESTRATOR}:6: clock call: ")
    assert script.main(["--root", str(clean_tree)]) == 1
    assert f"{ORCHESTRATOR}:6:" in capsys.readouterr().out


def test_anl_01_c3_a_planted_payload_parse_is_reported_with_file_and_line(clean_tree):
    path = clean_tree / SELECT_INPUTS
    path.write_text(path.read_text(encoding="utf-8") + "bool ok = message.ParseFromArray(p, n);\n", encoding="utf-8")
    findings = script.check_engine_decisions(clean_tree)
    assert len(findings) == 1
    assert findings[0].startswith(f"{SELECT_INPUTS}:2: payload parse: ")


@pytest.mark.parametrize(
    "line, kind",
    [
        ("auto id = std::this_thread::get_id();", "thread-id call"),
        ("std::this_thread::sleep_for(std::chrono::milliseconds(1));", "timer call"),
        ("clock_gettime(CLOCK_MONOTONIC, &ts);", "clock call"),
        ("m.ParseFromString(bytes);", "payload parse"),
    ],
)
def test_anl_01_each_kind_of_call_is_reported(clean_tree, line, kind):
    path = clean_tree / "src/simcore/orchestrator/event_queue.cpp"
    path.write_text(line + "\n", encoding="utf-8")
    findings = script.check_engine_decisions(clean_tree)
    assert [f.split(": ")[1] for f in findings] == [kind]


def test_anl_01_files_outside_the_scanned_set_are_not_read(clean_tree):
    write(clean_tree, "src/simcore/runner/run_stage.cpp", "auto t = std::chrono::steady_clock::now();\n")
    write(clean_tree, "src/simcore/bus/signal_header.cpp", "message->ParseFromArray(p, n);\n")
    assert script.check_engine_decisions(clean_tree) == []


def test_anl_01_selftest_plants_both_violations_in_a_copy_of_the_real_tree_and_leaves_the_tree_alone(capsys):
    before = script.check_engine_decisions()
    assert script.main(["--selftest"]) == 0
    out = capsys.readouterr().out
    assert "ANL-01 .c2" in out and "ANL-01 .c3" in out and "FAIL" not in out
    assert script.check_engine_decisions() == before


def test_anl_01_selftest_fails_when_a_planted_violation_would_not_be_reported(tmp_path, monkeypatch, capsys):
    """The selftest is itself checked: with the clock rule gone the .c2 copy passes and the selftest says so."""
    for entry in script.SCANNED:
        source = script.SIM_ROOT / entry
        if source.is_dir():
            shutil.copytree(source, tmp_path / entry)
        else:
            (tmp_path / entry).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / entry).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(script, "_RULES", tuple(rule for rule in script._RULES if rule[0] != "clock call"))
    assert script.selftest(tmp_path) == 1
    assert "ANL-01 .c2 (clock call): FAIL" in capsys.readouterr().out
