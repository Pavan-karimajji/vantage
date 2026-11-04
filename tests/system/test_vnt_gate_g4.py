# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0123`: gate `G4`, `SYT-INS-06` (`VANTAGE_Test_Spec.md` section 1a) and the drill table it names.

**G4 is green when this file and `test_vnt_lms.py`, `test_vnt_live_measurement.py`, `test_vnt_inspector.py` and
`test_vnt_supervisor.py` pass with no failure and no skip.** The drills of the table are run by those four files
(`RCT:SYT-LMS-03`/`04`/`08`/`09`, `SYT-INS-02`/`05`/`12`, `SYT-LMW-10`/`11`/`16`, `SYT-SUP-02`/`03`/`07`/`13`), with test
readers and no viewer; this file holds `SYT-INS-06` and checks that every drill's test is present.

`SYT-INS-06.c1`: every topology's first exact case runs on `F-LM-HELD` with `check --recording` attached while it is
held. `.c2`: `check` on an `F-FLAWED-LM` made from `running_example` `cut_c` with `--drop-port`.
A test whose lab output or tool is missing skips with the reason printed (`tests/support`); none may skip in a
gate run.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.engine_runs import case_params, exact_cases
from tests.support.lab_cases import lab_case
from tests.support.livemeas_runs import held_run, make_flawed, release_and_follow

HERE = Path(__file__).parent


def _first_exact_cases() -> list[tuple[str, str, str]]:
    firsts: dict[str, tuple[str, str, str]] = {}
    for topology, scenario, case in exact_cases():
        firsts.setdefault(topology, (topology, scenario, case))
    return list(firsts.values())


@pytest.mark.parametrize("topology,scenario,case", case_params(_first_exact_cases()))
def test_syt_ins_06_c1_check_finds_nothing_on_the_first_exact_case_of_every_topology(tmp_path, topology, scenario, case):
    """`SYT-INS-06.c1`, `SYS-0080` Accept: `check --recording` on the case run on `F-LM-HELD` reports no finding and
    exits 0. FAIL: a finding, naming topology, step and port."""
    lab = lab_case(topology, case, scenario)
    held = held_run(lab, tmp_path, "g4c1")
    try:
        (checked,) = release_and_follow(held, ("check", "--recording", str(lab.recording)))
        finished = held.finish()
    finally:
        held.close()
    where = f"{topology}/{scenario}/{case}"
    assert finished.returncode == 0, f"{where}: the held run failed: {finished.stderr[-400:]}"
    findings = [line for line in checked.out.splitlines() if line.strip()]
    assert checked.code == 0 and not findings, \
        f"{where}: check found {len(findings)} item(s), exit {checked.code} (FAIL side of SYT-INS-06.c1): {findings[:5]} {checked.err}"


def test_syt_ins_06_c2_check_on_the_flawed_cut_c_names_the_dropped_step_and_port(tmp_path):
    """`SYT-INS-06.c2`, `SYS-0080` Accept: on `F-FLAWED-LM` made from `running_example` `cut_c` with `--drop-port`,
    `check` names the dropped step and port. FAIL: it reports none, so `.c1` could not have failed."""
    lab = lab_case("running_example", "cut_c")
    held = held_run(lab, tmp_path, "g4c2")
    try:
        flawed = make_flawed(held, "dropport", "--drop-port", "10", "B.out")
        checked = flawed.result
        held.finish()
    finally:
        held.close()
    assert checked.code == 1, f"check exited {checked.code} on a live measurement with a dropped port (FAIL side of .c2): {checked.out}"
    assert "step 10: port B.out has neither a value nor an omitted mark" in checked.out.splitlines(), checked.out


def test_syt_ins_06_the_drill_table_names_only_tests_that_exist():
    """The drill table of section 1a (`ARCH §10.3`): each drill's test id appears in one of the four other files."""
    drills = {
        "test_vnt_lms.py": ["RCT:SYT-LMS-03", "RCT:SYT-LMS-04", "RCT:SYT-LMS-08", "RCT:SYT-LMS-09"],
        "test_vnt_inspector.py": ["SYT-INS-02", "SYT-INS-05", "SYT-INS-12"],
        "test_vnt_live_measurement.py": ["SYT-LMW-10", "SYT-LMW-11", "SYT-LMW-16"],
        "test_vnt_supervisor.py": ["SYT-SUP-02", "SYT-SUP-03", "SYT-SUP-07", "SYT-SUP-13"],
    }
    missing = [f"{name}: {test}" for name, ids in drills.items() for test in ids
               if test not in (HERE / name).read_text(encoding="utf-8")]
    assert not missing, f"a drill whose test is not in its file (FAIL side of the drill table): {missing}"
