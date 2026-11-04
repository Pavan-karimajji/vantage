# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`RCT:SYT-CTL-03`..`07` and `RCT:SYT-RSY-04` on Vantage (`RCT_Test_Spec.md` sections 2 and 3), run on the
engine-run recording of the lab cases. Each test names its case id, cites the `Accept` it checks (`RCT:SYS-0008`..`0012`,
`0016`) and states the FAIL side the spec states.

Where the spec leaves a step open it is chosen so the case can fail:
- `F-LAB-JUMP` is `running_example` `base` `jump` on `F-TAP` with a jump from 500 ms to 1500 ms (`test_vnt_gate_g3.py`);
  `F-LAB` is `base` `cut_c`; `F-LAB-RESTART` is `restart` `replay`; `F-LAB-FAULT` is `fault` `replay`, compared with
  `base` `all_simulated`, the run without the fault (the same stages, the recording without the fault);
- the run `k` of a stage is its `k`-th `control` message; its `compState` and each data output (a `pro` port except
  `refSync` and `compState`) is that stage's `k`-th message of the topic, and a topic with another count is a failure;
- `SYT-CTL-04.c2` is `data_triggered` `base` `by_data`: the control `k` of `T` is paired with the `k`-th `source.X`
  sample, the one that triggers `T`;
- `SYT-CTL-06.c1` takes the "first run after a jump" to be the first `control` of the stage logged at or after the
  jump target; the sequence is checked over every simulated stage;
- `SYT-RSY-04` runs every exact case of the catalogue except the jump case, whose equality after a jump is
  `SYT-EQO-01` (`D28 (4)`: a stage with memory is warming up after it); a reproduced output is paired with the recorded
  message of the same topic and `measurement_counter`, from the stage's second run (its first RUN run) on, and each pair
  goes through the lab's `equal_outputs`.
"""
from __future__ import annotations

import json

import pytest

from tests.support.engine_runs import (
    Recording, case_params, exact_cases, lab_compare, ran, simulated_names, tap_case,
)
from tests.support.lab_cases import LabCase, lab_case

JUMP = (500, 1500)  # ms
RESTART, RUN = 0, 1  # `CycleControl.OpMode`
NOT_INITIALIZED, ERROR = 0, 2  # `CompState.State`


def _setup(case: LabCase) -> dict:
    return json.loads(case.setup.read_text(encoding="utf-8"))


def _data_ports(case: LabCase, stage: str) -> list[str]:
    """The data outputs of a simulated stage: its `pro` ports except `refSync` and `compState`."""
    for declared in _setup(case)["stages"]:
        if declared["name"] == stage:
            return [p["name"] for p in declared["ports"] if p["dir"] == "pro" and p["name"] not in ("refSync", "compState")]
    return []


def _controls(recording: Recording, stage: str) -> list[tuple[int, int, object]]:
    return recording.decoded(f"{stage}.control")


def _op_modes(recording: Recording, stage: str) -> list[int]:
    return [message.op_mode for _i, _t, message in _controls(recording, stage)]


def _jump_run(case: LabCase, directory) -> Recording:
    tapped = tap_case(case, directory, "jump", jump=JUMP)
    assert tapped.returncode == 0, f"{case.topology}/{case.scenario}/{case.case}: the tap run failed: {tapped.stderr[-400:]}"
    return Recording(tapped.recording)


# ---- SYT-CTL-03 ---------------------------------------------------------------------------------------------------

def test_syt_ctl_03_c1_restart_runs_publish_defaults(tmp_path):  # RCT:SYT-CTL-03.c1
    """`RCT:SYT-CTL-03.c1`, `RCT:SYS-0008` Accept: in every RESTART run of the jump run, `compState.state` is
    NOT_INITIALIZED and every `dataOut` `sig_status` is 0. FAIL: any other state or sticker."""
    case = lab_case("running_example", "jump")
    recording = _jump_run(case, tmp_path)
    restart_runs = 0
    failures: list[str] = []
    for stage in simulated_names(case):
        modes = _op_modes(recording, stage)
        states = recording.decoded(f"{stage}.compState")
        assert len(states) == len(modes), f"RCT:SYT-CTL-03.c1: {stage} has {len(modes)} runs but {len(states)} compState messages"
        outputs = {port: recording.decoded(f"{stage}.{port}") for port in _data_ports(case, stage)}
        for port, messages in outputs.items():
            assert len(messages) == len(modes), f"RCT:SYT-CTL-03.c1: {stage}.{port} has {len(messages)} messages for {len(modes)} runs"
        for run, mode in enumerate(modes):
            if mode != RESTART:
                continue
            restart_runs += 1
            state = states[run][2].state
            if state != NOT_INITIALIZED:
                failures.append(f"{stage} run {run + 1}: compState {state}")
            for port, messages in outputs.items():
                sticker = messages[run][2].sig_header.sig_status
                if sticker != 0:
                    failures.append(f"{stage}.{port} run {run + 1}: sticker {sticker}")
    assert restart_runs > 2 * len(simulated_names(case)) - 1, \
        f"RCT:SYT-CTL-03.c1: only {restart_runs} RESTART runs, so the jump's RESTART runs were not selected"
    assert not failures, f"RCT:SYT-CTL-03.c1: a RESTART run published another state or sticker ({len(failures)}); first: {failures[0]}"


# ---- SYT-CTL-04 ---------------------------------------------------------------------------------------------------

def _header_fields(message) -> tuple[int, int]:
    return message.sig_header.measurement_counter, message.sig_header.source_timestamp_us


def test_syt_ctl_04_c1_control_headers_equal_the_recorded_controls(tmp_path):  # RCT:SYT-CTL-04.c1
    """`RCT:SYT-CTL-04.c1`, `RCT:SYS-0009` Accept: with recorded controls, `measurement_counter` and
    `source_timestamp_us` of each control equal the recorded control's. FAIL: any difference."""
    case = lab_case("running_example", "cut_c")
    _run, produced = ran(case, tmp_path, "ctl04a")
    recorded = Recording(case.recording)
    compared = 0
    for stage in simulated_names(case):
        mine, theirs = _controls(produced, stage), _controls(recorded, stage)
        assert len(mine) == len(theirs), f"RCT:SYT-CTL-04.c1: {stage} ran {len(mine)} times, the recording holds {len(theirs)} controls"
        for run, ((_i, _t, a), (_j, _u, b)) in enumerate(zip(mine, theirs), start=1):
            compared += 1
            assert _header_fields(a) == _header_fields(b), \
                f"RCT:SYT-CTL-04.c1: {stage} run {run}: control {_header_fields(a)} is not the recorded {_header_fields(b)}"
    assert compared, "RCT:SYT-CTL-04.c1: no control compared, so the case could not fail"


def test_syt_ctl_04_c2_control_headers_equal_the_trigger_sample(tmp_path):  # RCT:SYT-CTL-04.c2
    """`RCT:SYT-CTL-04.c2`, `RCT:SYS-0009` Accept, on `data_triggered` `by_data` (`T` triggered by `in_X`, the sample
    of `source.X`): both fields of each control equal the trigger sample's. FAIL: any difference."""
    case = lab_case("data_triggered", "by_data")
    run, produced = ran(case, tmp_path, "ctl04b")
    stage = "T"
    declared = next(s for s in _setup(case)["stages"] if s["name"] == stage)
    assert declared["trigger"] == "in_X", f"RCT:SYT-CTL-04.c2: the case does not trigger T by data: {declared['trigger']!r}"
    controls = _controls(produced, stage)
    triggers = produced.decoded("source.X")
    assert len(controls) == len(triggers), f"RCT:SYT-CTL-04.c2: {len(controls)} runs for {len(triggers)} trigger samples"
    assert controls, "RCT:SYT-CTL-04.c2: no run, so the case could not fail"
    for run_number, ((_i, _t, control), (_j, _u, sample)) in enumerate(zip(controls, triggers), start=1):
        assert _header_fields(control) == _header_fields(sample), \
            f"RCT:SYT-CTL-04.c2: T run {run_number}: control {_header_fields(control)} is not the trigger sample's {_header_fields(sample)}"


# ---- SYT-CTL-05 ---------------------------------------------------------------------------------------------------

def test_syt_ctl_05_c1_control_messages_are_ok_and_counted(tmp_path):  # RCT:SYT-CTL-05.c1
    """`RCT:SYT-CTL-05.c1`, `RCT:SYS-0010` Accept: every control has sticker 1 and a `cycle_counter` one more than
    the component's previous control. FAIL: another sticker, or a counter step other than 1."""
    case = lab_case("running_example", "cut_c")
    _run, produced = ran(case, tmp_path, "ctl05")
    seen = 0
    for stage in simulated_names(case):
        previous = None
        for _i, _t, control in _controls(produced, stage):
            seen += 1
            assert control.sig_header.sig_status == 1, \
                f"RCT:SYT-CTL-05.c1: {stage} control {seen}: sticker {control.sig_header.sig_status}, not 1"
            counter = control.sig_header.cycle_counter
            if previous is not None:
                assert counter == previous + 1, f"RCT:SYT-CTL-05.c1: {stage}: cycle_counter {previous} then {counter}"
            previous = counter
    assert seen > 2, "RCT:SYT-CTL-05.c1: no control read, so the case could not fail"


# ---- SYT-CTL-06 ---------------------------------------------------------------------------------------------------

def test_syt_ctl_06_c1_restart_at_start_and_after_a_jump(tmp_path):  # RCT:SYT-CTL-06.c1
    """`RCT:SYT-CTL-06.c1`, `RCT:SYS-0011` Accept: on the jump run each component's `op_mode` sequence is RESTART,
    RUN ... RUN, RESTART, RUN ... RUN, the second RESTART its first run after the jump. FAIL: a RESTART elsewhere, or a
    RUN where RESTART is due."""
    case = lab_case("running_example", "jump")
    recording = _jump_run(case, tmp_path)
    jump_to_ns = JUMP[1] * 1_000_000
    for stage in simulated_names(case):
        controls = _controls(recording, stage)
        modes = [m.op_mode for _i, _t, m in controls]
        after = next((k for k, (_i, t, _m) in enumerate(controls) if t >= jump_to_ns), None)
        assert after is not None and 0 < after, f"RCT:SYT-CTL-06.c1: {stage} has no run after the jump"
        expected = [RESTART] + [RUN] * (after - 1) + [RESTART] + [RUN] * (len(modes) - after - 1)
        assert modes == expected, (
            f"RCT:SYT-CTL-06.c1: {stage}: RESTART at runs {[k + 1 for k, m in enumerate(modes) if m == RESTART]}, "
            f"due at runs 1 and {after + 1}")


def test_syt_ctl_06_c2_a_recorded_restart_is_repeated(tmp_path):  # RCT:SYT-CTL-06.c2
    """`RCT:SYT-CTL-06.c2`, `RCT:SYS-0011` Accept, on `restart` `replay`: the replayed `op_mode` sequence of the
    restarted component has RESTART at exactly the recorded run. FAIL: it is missing there, or appears anywhere else
    after the first run."""
    case = lab_case("running_example", "replay", "restart")
    _run, produced = ran(case, tmp_path, "ctl06b")
    recorded = Recording(case.recording)
    restarted = _op_modes(recorded, "D")
    at = [k + 1 for k, mode in enumerate(restarted) if mode == RESTART]
    assert len(at) > 1, f"RCT:SYT-CTL-06.c2: the recording holds no mid-run RESTART of D (RESTART at runs {at})"
    replayed = _op_modes(produced, "D")
    where = [k + 1 for k, mode in enumerate(replayed) if mode == RESTART]
    assert where == at, f"RCT:SYT-CTL-06.c2: D replays RESTART at runs {where}, recorded at {at}"
    for stage in simulated_names(case):
        if stage != "D":
            others = [k + 1 for k, mode in enumerate(_op_modes(produced, stage)) if mode == RESTART]
            assert others == [1], f"RCT:SYT-CTL-06.c2: {stage} replays RESTART at runs {others}, only the first is due"


# ---- SYT-CTL-07 ---------------------------------------------------------------------------------------------------

def test_syt_ctl_07_c1_an_error_leaves_the_op_mode_alone(tmp_path):  # RCT:SYT-CTL-07.c1
    """`RCT:SYT-CTL-07.c1`, `RCT:SYS-0012` Accept: with a component reporting ERROR the `op_mode` sequences are
    identical to the same run without the fault. FAIL: any difference."""
    faulted = lab_case("running_example", "replay", "fault")
    clean = lab_case("running_example", "all_simulated", "base")
    _r1, with_fault = ran(faulted, tmp_path, "ctl07a")
    _r2, without = ran(clean, tmp_path, "ctl07b")
    errors = {stage: sum(1 for _i, _t, s in with_fault.decoded(f"{stage}.compState") if s.state == ERROR)
              for stage in simulated_names(faulted)}
    assert any(errors.values()), f"RCT:SYT-CTL-07.c1: no component reported ERROR, so the case could not fail: {errors}"
    for stage in simulated_names(faulted):
        mine, theirs = _op_modes(with_fault, stage), _op_modes(without, stage)
        assert mine == theirs, (
            f"RCT:SYT-CTL-07.c1: {stage} ({errors[stage]} ERROR runs): op_mode sequences differ, RESTART at "
            f"{[k + 1 for k, m in enumerate(mine) if m == RESTART]} against {[k + 1 for k, m in enumerate(theirs) if m == RESTART]}")


# ---- SYT-RSY-04 ---------------------------------------------------------------------------------------------------

def _rsy_cases() -> list[tuple[str, str, str]]:
    return [c for c in exact_cases() if not _jumps(*c)]


def _jumps(topology: str, scenario: str, name: str) -> bool:
    from tests.support.lab_cases import lab_root
    import yaml
    declared = yaml.safe_load((lab_root() / "catalogue" / f"{topology}.yaml").read_text(encoding="utf-8"))
    for entry in declared.get("scenarios", []):
        if entry["name"] == scenario:
            return any(c["name"] == name and c.get("jump_to_ms") for c in entry.get("resim", []))
    return False


@pytest.mark.parametrize(("topology", "scenario", "name"), case_params(_rsy_cases()))
def test_syt_rsy_04_c1_inputs_by_ref_sync_reproduce_the_car(tmp_path, topology, scenario, name):  # RCT:SYT-RSY-04.c1
    """`RCT:SYT-RSY-04.c1`, `RCT:SYS-0016` Accept: each simulated component's `dataOut` equals the recording's from its
    first RUN run on. FAIL: any byte differing outside `cycle_counter`, naming topology, component and run."""
    compare, messages = lab_compare()
    case = lab_case(topology, name, scenario)
    _run, produced = ran(case, tmp_path, "rsy04")
    recorded = Recording(case.recording)
    compared = 0
    for stage in simulated_names(case):
        for port in _data_ports(case, stage):
            topic = f"{stage}.{port}"
            theirs = {}
            for _i, _t, payload in recorded.of(topic):
                theirs.setdefault(recorded.decode(topic, payload).sig_header.measurement_counter, payload)
            schema, descriptor_set = recorded.schemas.get(topic) or produced.schemas[topic]
            factory = messages.MessageFactory(descriptor_set)
            for run, (_i, _t, payload) in enumerate(produced.of(topic), start=1):
                if run == 1:  # the RESTART run is not compared (`SYS-0016`: from the first RUN run on)
                    continue
                counter = produced.decode(topic, payload).sig_header.measurement_counter
                assert counter in theirs, f"RCT:SYT-RSY-04.c1: {topology}/{scenario}/{name}: {stage}.{port} run {run}: no recorded message of counter {counter}"
                result = compare.equal_outputs([theirs[counter]], [payload], factory, schema)
                assert result.equal, f"RCT:SYT-RSY-04.c1: {topology}/{scenario}/{name}: {stage}.{port} run {run}: {result.reason}"
                compared += 1
    assert compared, f"RCT:SYT-RSY-04.c1: {topology}/{scenario}/{name}: no output compared, so the case could not fail"
