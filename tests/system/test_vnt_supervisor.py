# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0122`: the supervisor, `SYT-SUP-01`..`15` (`VANTAGE_Test_Spec.md` section 10). `F-SUPERVISED` is
`lab_tools.supervise.run_under_supervisor` with `F-READER --until-finished` attached; where a test must watch the run
while it lives (the process tree, the status, the writer's pid) it starts `simengine --supervise` itself and reads the
live measurement with `LiveRegion`. Each test names its case id, cites the `Accept` it checks and states the FAIL side.

Where the spec leaves a step open it is chosen so the case can fail:
- `hang` and `crash` run on the case's own bundle (`LAB_B_HANG_AFTER_RUNS`, `LAB_B_CRASH_AFTER_RUNS`); `hang` under
  the supervisor has `limits.exec_timeout_ms` 0, so the engine's own call timeout cannot end it and only the
  supervisor's deadline can;
- a worker "killed by the test through a process kill" is ended by pid with an unhandled-exception status
  (`TerminateProcess(0xC0000005)` on Windows, `SIGKILL` elsewhere): a plain Windows kill gives exit code 1, which no
  supervisor can tell from a clean failure;
- "the worker binary renamed" (`SYT-SUP-03`): the supervisor starts its own executable, which cannot be renamed under
  it, so the worker's start is made to fail by running the supervisor where the system allows no second process (a
  Windows job object limited to one active process), the same `kFailedToStart`;
- a setup "refused at load" is `cut_c` on a copy of its recording cut at 30 %, whose measured stage `C` then lacks its
  outputs: the engine refuses it with exit 2 after the supervisor has loaded the setup.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.support.engine_runs import (
    Recording, case_change, case_params, compare_recordings, engine_exe, exact_cases, ran, run_case, run_engine,
    stage_of, tool_path, point_at_recording,
)
from tests.support.lab_cases import LabCase, edit_setup, lab_case
from tests.support.livemeas_runs import (
    LiveRegion, add_held_stage, case_bundles, descendants, held_library, held_run, inspect, kill_as_crash, pid_alive, process_table,
)

def supervise():
    from lab_tools import supervise as module  # the lab's own LAB-53 module; `engine_runs` put its package on the path

    return module


def cut_c() -> LabCase:
    return lab_case("running_example", "cut_c")


def hang_case() -> LabCase:
    return lab_case("running_example", "hang")


def crash_case() -> LabCase:
    return lab_case("running_example", "crash")


def _prepared(case: LabCase, directory: Path, label: str, *, change=None, hang: bool = False) -> Path:
    """The case's setup in `directory` (its own folder: `reproducers/` and the attempt file land beside it)."""
    directory = Path(directory) / label
    bundles = case_bundles(case, directory)

    def apply(setup: dict) -> None:
        bundles(setup)
        if hang:
            setup["limits"]["exec_timeout_ms"] = 0
        if change is not None:
            change(setup)

    return edit_setup(case, directory, case_change(label, apply), name=label, outputs=directory / f"{label}.mcap")


def _supervised(case, directory, label, *, deadline_ms=60000, restart=0, reader=False, change=None, hang=False, env=None):
    gate = Path(directory) / label / f"{label}.gate"
    if reader:  # `F-LM-HELD`: the run is held in the stage `H` until the reader is attached
        library = held_library(Path(directory) / label, label, gate)
        inner = change

        def with_held_stage(setup: dict) -> None:
            if inner is not None:
                inner(setup)
            add_held_stage(setup, library)

        change = with_held_stage
    setup = _prepared(case, directory, label, change=change, hang=hang)
    run = supervise().run_under_supervisor(setup, simengine=engine_exe(), attempt_timeout_ms=deadline_ms,
                                           restart_on_crash=restart, reader=tool_path("lm_reader") if reader else None,
                                           cwd=setup.parent, env=env, gate_file=gate if reader else None)
    return setup, run


def _run_where_no_second_process_may_start(command: list[str], cwd: Path) -> int:
    """The exit code of `command` run where the system refuses it a second process."""
    if os.name != "nt":
        import resource

        def limit() -> None:
            resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))

        return subprocess.run(command, capture_output=True, text=True, timeout=120, cwd=cwd, preexec_fn=limit).returncode
    import ctypes
    import ctypes.wintypes as wt

    kernel, ntdll = ctypes.WinDLL("kernel32", use_last_error=True), ctypes.WinDLL("ntdll")
    kernel.CreateJobObjectW.restype = wt.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]

    class BasicLimits(ctypes.Structure):  # JOBOBJECT_BASIC_LIMIT_INFORMATION
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", wt.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wt.DWORD), ("Affinity", ctypes.c_size_t), ("PriorityClass", wt.DWORD),
                    ("SchedulingClass", wt.DWORD)]

    job = kernel.CreateJobObjectW(None, None)
    limits = BasicLimits(LimitFlags=0x8, ActiveProcessLimit=1)  # JOB_OBJECT_LIMIT_ACTIVE_PROCESS
    assert kernel.SetInformationJobObject(wt.HANDLE(job), 2, ctypes.byref(limits), ctypes.sizeof(limits))
    process = subprocess.Popen(command, creationflags=0x4, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)  # suspended
    assert kernel.AssignProcessToJobObject(wt.HANDLE(job), wt.HANDLE(int(process._handle)))
    ntdll.NtResumeProcess(wt.HANDLE(int(process._handle)))
    process.communicate(timeout=120)
    kernel.CloseHandle(wt.HANDLE(job))
    return process.returncode


def _cut_recording(case: LabCase, directory: Path) -> Path:
    cut = Path(directory) / "cut30.mcap"
    data = case.recording.read_bytes()
    cut.write_bytes(data[: int(len(data) * 0.3)])
    return cut


def _watched(case, directory, label, *, deadline_ms=60000, restart=0, hang=False, env=None, change=None, sample=None):
    """`simengine --supervise` started here and the live measurement watched while it runs: returns
    `(setup, returncode, stderr, region, pid, samples)`, `samples` the `(worker alive, status)` pairs seen."""
    setup = _prepared(case, directory, label, change=change, hang=hang)
    name = json.loads(setup.read_text(encoding="utf-8"))["outputs"].get("livemeas", {}).get("name")
    command = supervise().build_command(setup, simengine=engine_exe(), attempt_timeout_ms=deadline_ms, restart_on_crash=restart)
    err_path = setup.parent / f"{label}.sup.err.txt"
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=open(err_path, "w"), cwd=setup.parent, env=env)
    region, pid, samples, seen = None, None, [], False
    while process.poll() is None:
        if name is not None and region is None:
            try:
                region = LiveRegion(name)
                pid = region.status().writer_pid
            except LookupError:
                pass
        if region is not None:
            status = region.status().status
            samples.append((pid_alive(pid), status))
            if sample is not None and not seen:
                seen = sample(region, pid)
        time.sleep(0.0005)
    code = process.wait()
    return setup, code, err_path.read_text(encoding="utf-8", errors="replace"), region, pid, samples


def _attempts(setup: Path) -> list[dict]:
    return supervise().read_attempts(setup)


# ---- SYT-SUP-01, 02 -------------------------------------------------------------------------------------------------

def test_syt_sup_01_one_worker_no_grandchild(tmp_path):
    """`SYT-SUP-01`, `SYS-0088` Accept. `.c1`: with `--supervise` one child and no grandchild, without it none. FAIL:
    two children, a grandchild, or a child without the flag."""
    supervised = held_run(cut_c(), tmp_path / "with", "sup01a", supervise_ms=120000)
    try:
        region = LiveRegion(supervised.name)
        table = process_table()
        children = [c for c in descendants(supervised.pid, table)]
        direct_children_of_supervisor = [c for c, (parent, _n) in table.items() if parent == supervised.pid]
        worker = region.status().writer_pid
        supervised.release()
        assert supervised.finish().returncode == 0
    finally:
        supervised.close()
    plain = held_run(cut_c(), tmp_path / "without", "sup01b")
    try:
        table = process_table()
        without = descendants(plain.pid, table)
        plain.release()
        plain.finish()
    finally:
        plain.close()
    assert direct_children_of_supervisor == [worker] and children == [worker], \
        f"SYT-SUP-01.c1: children {direct_children_of_supervisor}, all descendants {children}, the writer {worker}"
    assert without == [], f"SYT-SUP-01.c1: a process without the flag has children {without}"


def test_syt_sup_02_the_deadline(tmp_path):
    """`SYT-SUP-02`, `SYS-0089`, `SYS-0090` Accept. `.c1`: `hang` with a deadline below the hang: the worker gone after
    the deadline and exit 7. FAIL: the worker alive, or another code. `.c2`: `cut_c` with a deadline above it exits 0.
    FAIL: another code. `.c3`: no deadline option: exit 2 naming it, no worker, no live measurement. FAIL: a worker
    starts."""
    started = time.monotonic()
    setup, code, _err, region, pid, _s = _watched(hang_case(), tmp_path, "sup02a", deadline_ms=2000, hang=True)
    took = time.monotonic() - started
    assert code == 7, f"SYT-SUP-02.c1: hang exited {code}"
    assert pid is not None and not pid_alive(pid), "SYT-SUP-02.c1: the worker is still alive after the supervisor's end"
    assert took >= 2.0, f"SYT-SUP-02.c1: the supervisor ended after {took:.2f} s, before its 2 s deadline"
    _setup, run = _supervised(cut_c(), tmp_path, "sup02b", deadline_ms=120000)
    assert run.exit_code == 0, f"SYT-SUP-02.c2: cut_c exited {run.exit_code}: {run.stderr[-300:]}"

    plain = _prepared(cut_c(), tmp_path, "sup02c")
    name = json.loads(plain.read_text(encoding="utf-8"))["outputs"]["livemeas"]["name"]
    refused = subprocess.run([str(engine_exe()), str(plain), "--supervise"], capture_output=True, text=True, timeout=60)
    assert refused.returncode == 2 and "--attempt-timeout-ms" in refused.stderr, \
        f"SYT-SUP-02.c3: exit {refused.returncode}, {refused.stderr!r}"
    assert not supervise().attempts_path(plain).exists(), "SYT-SUP-02.c3: a worker started (an attempt record exists)"
    assert inspect("attach", name).code == 6, "SYT-SUP-02.c3: a live measurement exists"


# ---- SYT-SUP-03, 04, 05 ---------------------------------------------------------------------------------------------

def test_syt_sup_03_five_outcomes_five_endings(tmp_path):
    """`SYT-SUP-03`, `SYS-0091` Accept. `.c1`: a passing case, a setup refused at load, `crash`, `hang` and a worker
    that cannot start give 0, the worker's own non-zero code, 8, 7 and 6, all different. FAIL: two outcomes sharing a
    code, or a code outside these."""
    lab = cut_c()
    codes = {}
    codes["pass"] = _supervised(lab, tmp_path, "sup03a")[1].exit_code
    cut = _cut_recording(lab, tmp_path)
    codes["refused"] = _supervised(lab, tmp_path, "sup03b", change=lambda s: point_at_recording(s, cut))[1].exit_code
    codes["crash"] = _supervised(crash_case(), tmp_path, "sup03c")[1].exit_code
    codes["hang"] = _supervised(hang_case(), tmp_path, "sup03d", deadline_ms=2000, hang=True)[1].exit_code

    # a worker that cannot start: the supervisor runs where the system allows it no second process (a Windows job object
    # with an active-process limit of one; on POSIX `RLIMIT_NPROC` of the current count), so starting its worker is refused.
    # `--config` is no longer an option of `simengine` (`D31 (1)`), so it can no longer be made too long.
    setup = _prepared(lab, tmp_path, "sup03e")
    started = _run_where_no_second_process_may_start(
        [str(engine_exe()), str(setup), "--supervise", "--attempt-timeout-ms", "60000"], setup.parent)
    codes["no start"] = started
    assert codes["pass"] == 0 and codes["crash"] == 8 and codes["hang"] == 7 and codes["no start"] == 6, f"SYT-SUP-03.c1: {codes}"
    assert codes["refused"] not in (0, 6, 7, 8), f"SYT-SUP-03.c1: the worker's own code {codes['refused']} is not its own"
    assert len(set(codes.values())) == 5, f"SYT-SUP-03.c1: two outcomes share a code: {codes}"


def test_syt_sup_04_never_a_raw_platform_code(tmp_path):
    """`SYT-SUP-04`, `SYS-0092` Accept. `.c1`: with `ADAS_SIM_TEST_FORCE_ABORT` set, and with the worker ended by the
    test through a process kill, both exit 8. FAIL: a platform status or any other code."""
    env = dict(os.environ, ADAS_SIM_TEST_FORCE_ABORT="1")
    _setup, aborted = _supervised(cut_c(), tmp_path, "sup04a", env=env, reader=False)
    assert aborted.exit_code == 8, f"SYT-SUP-04.c1: the aborting worker gave exit {aborted.exit_code}"

    killed = held_run(cut_c(), tmp_path, "sup04b", supervise_ms=120000)
    try:
        worker = LiveRegion(killed.name).status().writer_pid
        kill_as_crash(worker)
        code = killed.process.wait(timeout=120)
    finally:
        killed.close()
    assert code == 8, f"SYT-SUP-04.c1: the killed worker gave exit {code}"


def test_syt_sup_05_a_clean_failure_is_not_retried(tmp_path):
    """`SYT-SUP-05`, `SYS-0093` Accept. `.c1`: a setup refused at load with `--restart-on-crash 2`: one attempt and the
    worker's own code. FAIL: two attempts, or code 0."""
    lab = cut_c()
    cut = _cut_recording(lab, tmp_path)
    setup, run = _supervised(lab, tmp_path, "sup05", restart=2, change=lambda s: point_at_recording(s, cut), reader=False)
    assert len(run.attempts) == 1 and run.attempts[0]["outcome"] == "fail", f"SYT-SUP-05.c1: attempts {run.attempts}"
    assert run.exit_code == run.attempts[0]["exit_code"] != 0, f"SYT-SUP-05.c1: exit {run.exit_code}, the worker's {run.attempts[0]}"


# ---- SYT-SUP-06, 11, 12 ---------------------------------------------------------------------------------------------

def test_syt_sup_06_restarts_are_bounded_and_off_by_default(tmp_path):
    """`SYT-SUP-06`, `SYS-0094` Accept. `.c1`: `crash` with `--restart-on-crash 2`: three attempts, exit 8. FAIL:
    another count. `.c2`: without the option one attempt. FAIL: more. `.c3`: `hang` with 2: one attempt, exit 7. FAIL:
    a restart."""
    _s, bounded = _supervised(crash_case(), tmp_path, "sup06a", restart=2, reader=False)
    assert bounded.exit_code == 8 and len(bounded.attempts) == 3, f"SYT-SUP-06.c1: {bounded.exit_code}, {len(bounded.attempts)} attempts"
    _s, off = _supervised(crash_case(), tmp_path, "sup06b", reader=False)
    assert len(off.attempts) == 1 and off.exit_code == 8, f"SYT-SUP-06.c2: {len(off.attempts)} attempts, exit {off.exit_code}"
    _s, hung = _supervised(hang_case(), tmp_path, "sup06c", restart=2, deadline_ms=2000, hang=True, reader=False)
    assert len(hung.attempts) == 1 and hung.exit_code == 7, f"SYT-SUP-06.c3: {len(hung.attempts)} attempts, exit {hung.exit_code}"


def test_syt_sup_11_the_attempt_manifest(tmp_path):
    """`SYT-SUP-11`, `SYS-0099` Accept. `.c1`: `crash` with `--restart-on-crash 1`: two records numbered 1 and 2,
    outcome `crash` in both, the second marked last. FAIL: another count, number, outcome or last mark."""
    _s, run = _supervised(crash_case(), tmp_path, "sup11", restart=1, reader=False)
    assert [r["attempt"] for r in run.attempts] == [1, 2], f"SYT-SUP-11.c1: {run.attempts}"
    assert [r["outcome"] for r in run.attempts] == ["crash", "crash"], f"SYT-SUP-11.c1: {run.attempts}"
    assert [r["last"] for r in run.attempts] == [False, True], f"SYT-SUP-11.c1: {run.attempts}"


def test_syt_sup_12_the_stage_in_the_record(tmp_path):
    """`SYT-SUP-12`, `SYS-0100` Accept. `.c1`: `B` for `crash` and `hang`. FAIL: another stage or none. `.c2`: `unknown`
    for the abort before any call. FAIL: a stage."""
    _s, crashed = _supervised(crash_case(), tmp_path, "sup12a", reader=False)
    _s, hung = _supervised(hang_case(), tmp_path, "sup12b", deadline_ms=2000, hang=True, reader=False)
    assert crashed.attempts[0]["stages"] == ["B"], f"SYT-SUP-12.c1: crash {crashed.attempts}"
    assert hung.attempts[0]["stages"] == ["B"], f"SYT-SUP-12.c1: hang {hung.attempts}"
    _s, aborted = _supervised(cut_c(), tmp_path, "sup12c", env=dict(os.environ, ADAS_SIM_TEST_FORCE_ABORT="1"), reader=False)
    assert aborted.attempts[0]["stages"] == "unknown", f"SYT-SUP-12.c2: {aborted.attempts}"


# ---- SYT-SUP-07, 08, 09, 10 -----------------------------------------------------------------------------------------

def test_syt_sup_07_the_seal(tmp_path):
    """`SYT-SUP-07`, `SYS-0095` Accept. `.c1`: `crash`: the attached reader reads finished with `crash`. FAIL: status
    running, or another outcome. `.c2`: `hang`: finished with `timeout`. FAIL: as `.c1`. `.c3`: the status changes
    only after the worker has ended. FAIL: before."""
    _s, crashed = _supervised(crash_case(), tmp_path, "sup07a", reader=True)
    assert crashed.exit_code == 8 and crashed.sealed_outcome == 3, \
        f"SYT-SUP-07.c1: exit {crashed.exit_code}, the reader read outcome {crashed.sealed_outcome} (3 is crash)"
    _s, hung = _supervised(hang_case(), tmp_path, "sup07b", deadline_ms=2000, hang=True, reader=True)
    assert hung.exit_code == 7 and hung.sealed_outcome == 4, \
        f"SYT-SUP-07.c2: exit {hung.exit_code}, the reader read outcome {hung.sealed_outcome} (4 is timeout)"
    _s, code, _e, region, pid, samples = _watched(crash_case(), tmp_path, "sup07c")
    assert region is not None and code == 8
    finished_while_alive = [s for s in samples if s[0] and s[1] == 3]
    assert not finished_while_alive, f"SYT-SUP-07.c3: the status was finished while the worker was alive ({len(finished_while_alive)} samples)"
    assert region.status().status == 3 and region.status().outcome == 3


def test_syt_sup_08_the_seal_writes_two_fields(tmp_path):
    """`SYT-SUP-08`, `SYS-0096` Accept. `.c1`: with the worker held and killed, only `outcome` and `status` differ
    between the segments copied before and after the supervisor's end, `outcome` reading `crash`. FAIL: any other byte
    differs, or another outcome."""
    held = held_run(cut_c(), tmp_path, "sup08", supervise_ms=120000)
    try:
        region = LiveRegion(held.name)
        data_before, bulk_before = region.copy()
        worker = region.status().writer_pid
        time.sleep(0.3)
        kill_as_crash(worker)
        held.process.wait(timeout=120)
        data_after, bulk_after = region.copy()
    finally:
        held.close()
    differing = [i for i, (a, b) in enumerate(zip(data_before, data_after)) if a != b]
    allowed = set(range(20, 28))  # `status` (20..23) and `outcome` (24..27) of MeasStatus
    assert differing and set(differing) <= allowed, f"SYT-SUP-08.c1: bytes other than status and outcome differ: {[i for i in differing if i not in allowed][:8]}"
    assert region.status().outcome == 3 and region.status().status == 3, "SYT-SUP-08.c1: not finished with crash"
    assert bulk_before == bulk_after, "SYT-SUP-08.c1: the bulk segment changed"


def test_syt_sup_09_no_seal_of_a_live_or_self_closed_run(tmp_path):
    """`SYT-SUP-09`, `SYS-0097` Accept. `.c1`: `cut_c` (passes): outcome stays `pass` and the segments are unchanged by
    the supervisor. FAIL: a change. `.c2`: `crash`: status not finished while the worker lives. FAIL: finished before
    its end."""
    held = held_run(cut_c(), tmp_path, "sup09", supervise_ms=120000)
    try:
        region = LiveRegion(held.name)
        held.release()
        deadline = time.monotonic() + 60
        while region.status().status != 3 and time.monotonic() < deadline:
            time.sleep(0.0005)
        closed = region.copy()
        held.process.wait(timeout=120)
        later = region.copy()
    finally:
        held.close()
    assert region.status().outcome == 1, f"SYT-SUP-09.c1: outcome {region.status().outcome}, not pass"
    assert closed == later, "SYT-SUP-09.c1: the supervisor changed the segments of a run that closed itself"
    _s, code, _e, crashed_region, _pid, samples = _watched(crash_case(), tmp_path, "sup09b")
    assert code == 8 and crashed_region is not None
    assert not [s for s in samples if s[0] and s[1] == 3], "SYT-SUP-09.c2: status finished while the worker lived"
    assert samples and any(s[0] for s in samples), "SYT-SUP-09.c2: the worker was never seen alive, so the case could not fail"


def test_syt_sup_10_nothing_to_seal(tmp_path):
    """`SYT-SUP-10`, `SYS-0098` Accept. `.c1`: `crash` with `outputs.livemeas` removed: exit 8 and no live measurement
    created. FAIL: one created, or another code."""
    lab = crash_case()
    name = json.loads(lab.setup.read_text(encoding="utf-8"))["outputs"]["livemeas"]["name"] + "_sup10"
    setup, code, _e, region, _pid, _s = _watched(lab, tmp_path, "sup10", change=lambda s: s["outputs"].pop("livemeas"))
    assert code == 8, f"SYT-SUP-10.c1: exit {code}"
    assert region is None and inspect("attach", name).code == 6, "SYT-SUP-10.c1: a live measurement was created"


# ---- SYT-SUP-13, 14, 15 ---------------------------------------------------------------------------------------------

def test_syt_sup_13_the_reproducer(tmp_path):
    """`SYT-SUP-13`, `SYS-0101` Accept. `.c1`: `crash`: the package holds the run's setup, the last step equal to the
    highest step the attached reader read, the run id, standard error and `B`. FAIL: a missing item or another value.
    `.c2`: none after `hang` or a passing case. FAIL: a package written."""
    setup, code, _e, region, _pid, _s = _watched(crash_case(), tmp_path, "sup13a")
    assert code == 8 and region is not None
    packages = sorted((setup.parent / "reproducers").glob("*"))
    assert len(packages) == 1, f"SYT-SUP-13.c1: packages {packages}"
    package = packages[0]
    assert (package / "run_spec.json").read_bytes() == setup.read_bytes(), "SYT-SUP-13.c1: the package's setup is not the run's"
    assert (package / "stderr.txt").is_file(), "SYT-SUP-13.c1: no standard error"
    crash = json.loads((package / "crash.json").read_text(encoding="utf-8"))
    highest = region.newest_step()
    assert crash["failing_cycle"] == highest, f"SYT-SUP-13.c1: last step {crash['failing_cycle']}, the reader's highest {highest}"
    assert crash["run_id"] == json.loads(setup.read_text(encoding="utf-8"))["run_id"], "SYT-SUP-13.c1: run id"
    assert crash["stages"] == ["B"], f"SYT-SUP-13.c1: stages {crash['stages']}"

    hung_setup, hung = _supervised(hang_case(), tmp_path, "sup13b", deadline_ms=2000, hang=True, reader=False)
    passed_setup, passed = _supervised(cut_c(), tmp_path, "sup13c", reader=False)
    assert hung.exit_code == 7 and passed.exit_code == 0
    for folder in (hung_setup.parent / "reproducers", passed_setup.parent / "reproducers"):
        assert not folder.exists() or not list(folder.glob("*")), f"SYT-SUP-13.c2: a package written in {folder}"


def test_syt_sup_14_an_isolated_stages_crash(tmp_path):
    """`SYT-SUP-14`, `SYS-0102` Accept. `.c1`: `B` of `crash` hosted through `F-ISOLATE`: outcome `crash`, exit 8, `B`
    named, the asker alive. FAIL: the asker ends, or the stage is unnamed."""
    lab = crash_case()

    def only_b(setup: dict) -> None:
        for stage in setup["stages"]:
            if stage["name"] != "B":
                stage["mode"] = "measured"

    setup = _prepared(lab, tmp_path, "sup14", change=only_b)
    asked = subprocess.run([str(tool_path("isolate_stage")), str(setup), "B", str(engine_exe())],
                           capture_output=True, text=True, timeout=300)
    report = asked.stdout.strip().splitlines()[-1] if asked.stdout.strip() else ""  # the hosted child prints its pid first
    assert asked.returncode == 0 and report == "outcome=crash exit=8 stage=B asker_alive=1", \
        f"SYT-SUP-14.c1: asker exit {asked.returncode}, said {asked.stdout!r} {asked.stderr[-200:]}"


@pytest.mark.parametrize("topology,scenario,case", case_params(exact_cases()))
def test_syt_sup_15_supervision_changes_no_output(tmp_path, topology, scenario, case):
    """`SYT-SUP-15`, `SYS-0103` Accept. `.c1`: with `--supervise` and started directly the engine-run recordings are
    equal outputs and the event logs identical. FAIL: any difference."""
    lab = lab_case(topology, case, scenario)
    direct, direct_recording = ran(lab, tmp_path, "direct")
    setup = edit_setup(lab, tmp_path / "supervised", case_change("supervised", None), name="supervised",
                       outputs=tmp_path / "supervised" / "supervised.mcap")
    run = supervise().run_under_supervisor(setup, simengine=engine_exe(), attempt_timeout_ms=120000, cwd=setup.parent)
    where = f"{topology}/{scenario}/{case}"
    assert run.exit_code == 0 and len(run.attempts) == 1, f"SYT-SUP-15.c1: {where}: supervised exit {run.exit_code}: {run.stderr[-300:]}"
    recording = Path(json.loads(setup.read_text(encoding="utf-8"))["outputs"]["path"])
    differences = compare_recordings(direct_recording, Recording(recording))
    assert not differences, f"SYT-SUP-15.c1: {where}: outputs differ: {differences[:3]}"
    log = recording.with_suffix(".events.log")
    events = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
    assert direct.events == events, f"SYT-SUP-15.c1: {where}: the event logs differ"
