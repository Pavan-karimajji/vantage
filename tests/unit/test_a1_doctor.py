# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A1 smoke tests for `sim doctor` v0 (DG-3) and the console UTF-8
reconfiguration (P-4) -- both are S-A1 checklist items with no assigned
UT-A1-n label of their own."""

from __future__ import annotations

from adas_sim.cli import main
from adas_sim.core.console import reconfigure_console_utf8
from adas_sim.core.diagnostics import doctor_report


def test_doctor_report_carries_the_s_a1_environment_facts():
    report = doctor_report()
    for key in (
        "python_executable", "python_version", "adas_sim_install_mode",
        "platform", "stdout_encoding", "stderr_encoding", "os_line_separator",
    ):
        assert key in report


def test_reconfigure_console_utf8_is_safe_to_call_repeatedly():
    reconfigure_console_utf8()
    reconfigure_console_utf8()


def test_sim_doctor_cli_runs_and_prints_every_fact(capsys):
    exit_code = main(["doctor"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "python_executable" in out
    assert "adas_sim_install_mode" in out
