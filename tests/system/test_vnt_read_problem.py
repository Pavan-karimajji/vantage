# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`VNT-CLEAN-1` part C: a recording the reader finds damaged ends the engine run (`kSimExitInput`). `cut_c` on a copy of
its recording cut inside a message at 60 % of its bytes exits 5 with an error naming the file. FAIL: exit 0 (the run
passed on part of a recording), another code, or an error that does not name the file. That the live measurement of
such a run closes `fail` is `IMP_0083_ARecordingCutOffEndsTheRunWithInputAndWritesFail` (gtest): the run fails before any
component call, so no reader of a process started beside it can be held attached."""
from __future__ import annotations

from tests.support.engine_runs import point_at_recording, run_case
from tests.support.lab_cases import lab_case


def test_a_recording_cut_mid_message_ends_the_run_with_exit_5_naming_the_file(tmp_path):
    case = lab_case("running_example", "cut_c")
    cut = tmp_path / "cut60.mcap"
    data = case.recording.read_bytes()
    cut.write_bytes(data[: int(len(data) * 0.6)])
    run = run_case(case, tmp_path, "cut", change=lambda setup: point_at_recording(setup, cut))
    assert run.returncode == 5, f"a recording cut mid-message exited {run.returncode}, not 5: {run.stderr[-300:]}"
    assert cut.name in run.error_text(), f"the error does not name the file {cut.name}: {run.stderr[-300:]}"
