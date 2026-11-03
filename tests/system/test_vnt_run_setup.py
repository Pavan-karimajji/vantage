# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0044`: the system tests of the run setup, `SYT-RUN-01` to `SYT-RUN-09` and `SYT-RUN-11`
(`VANTAGE_Test_Spec.md` section 2), one test per case `.cN`, each run on `simengine` or `step_tap` over a lab case.
Every assertion message names the FAIL side the spec states for the case.

`SYT-RUN-10` (`SYS-0048`, the launcher refusing a missing run-setup value) is held by
`tests/system/test_vnt_run_config.py` (`IMP-0052`); it is not repeated here.

A test whose lab output, library or tool is missing skips with the reason printed (`tests/support`).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.support.engine_runs import (
    EngineRun, Recording, bare_environment, compare_recordings, point_at_recording, port_of, run_case, stage_of,
    tap_case, tool_path,
)
from tests.support.lab_cases import edit_recording, lab_case
from tests.system.test_vnt_wp13_recordings import _DUMP_CANDIDATES, _what_vantages_reader_returns

SCHEMA = "adas.sim.runspec/2.0"


def _refused_at_load(run: EngineRun, case_id: str, what: str, *names: str) -> None:
    """The engine ended with a load error, before any step, naming every one of `names`."""
    assert run.returncode != 0 and run.error_text(), f"{case_id}: {what}: the run started (exit {run.returncode})"
    assert not run.started, f"{case_id}: {what}: the engine got past load (a plan or a recording was written)"
    text = run.error_text()
    for name in names:
        assert name in text, f"{case_id}: {what}: the message does not name {name!r}: {text.strip()}"


def _cut_c():
    return lab_case("running_example", "cut_c")


def test_syt_run_01_c1_the_run_setup_is_the_only_input(tmp_path):  # SYT-RUN-01.c1
    case = _cut_c()
    beside = run_case(case, tmp_path / "beside", "beside")
    nowhere = tmp_path / "empty_working_directory"
    nowhere.mkdir()
    away = run_case(case, tmp_path / "away", "away", cwd=nowhere, env=bare_environment())

    assert beside.returncode == 0, f"SYT-RUN-01.c1: the run beside its setup failed: {beside.stderr[-400:]}"
    assert away.returncode == 0, f"SYT-RUN-01.c1: the second run fails to start: {away.stderr[-400:]}"
    assert not list(nowhere.iterdir()), "SYT-RUN-01.c1: the working directory was not empty (it must hold no YAML or ingest map)"
    differences = compare_recordings(Recording(beside.recording), Recording(away.recording))
    assert differences == [], f"SYT-RUN-01.c1: any difference on a port: {differences}"


@pytest.mark.parametrize("key", ["sampling", "on_missing"])
def test_syt_run_02_sampling_and_on_missing_are_refused(tmp_path, key):  # SYT-RUN-02.c1 (sampling), SYT-RUN-02.c2 (on_missing)
    case_id = "SYT-RUN-02.c1" if key == "sampling" else "SYT-RUN-02.c2"
    run = run_case(_cut_c(), tmp_path, key, change=lambda s: port_of(stage_of(s, "A"), "in_X").update({key: "x"}))
    _refused_at_load(run, case_id, f"{key} on A.in_X", key, "A", "in_X")


def test_syt_run_03_c1_each_missing_value_is_refused_by_name(tmp_path):  # SYT-RUN-03.c1
    removals = {
        "readiness_limit_steps": lambda s: s.pop("readiness_limit_steps"),
        "fallback_max_gap": lambda s: s.pop("fallback_max_gap"),
        "buffer_depth": lambda s: port_of(stage_of(s, "A"), "in_X").pop("buffer_depth"),
        **{key: (lambda s, key=key: s["outputs"]["livemeas"].pop(key))
           for key in ("bulk_slot_count", "bulk_slot_size", "cycle_slot_count", "cycle_slot_size")},
    }
    case = _cut_c()
    for key, remove in removals.items():
        run = run_case(case, tmp_path, f"without_{key}", change=remove)
        _refused_at_load(run, "SYT-RUN-03.c1", f"{key} removed", key)
        others = [other for other in removals if other != key and other in run.error_text()]
        assert not others, f"SYT-RUN-03.c1: removing {key}, the error names another key {others}: {run.error_text().strip()}"


def test_syt_run_03_c2_a_setup_without_livemeas_loads_and_runs(tmp_path):  # SYT-RUN-03.c2
    run = run_case(_cut_c(), tmp_path, "no_livemeas", change=lambda s: s["outputs"].pop("livemeas"))
    assert run.returncode == 0 and run.recording is not None and run.recording.is_file(), (
        f"SYT-RUN-03.c2: a load error naming a geometry value: {run.error_text().strip() or run.stderr[-300:]}")


def test_syt_run_04_c1_a_changed_schema_is_refused_with_both_strings(tmp_path):  # SYT-RUN-04.c1
    found = SCHEMA[:-1] + "1"
    run = run_case(_cut_c(), tmp_path, "changed", change=lambda s: s.update(schema=found))
    _refused_at_load(run, "SYT-RUN-04.c1", "schema changed", found, SCHEMA)


def test_syt_run_04_c2_a_removed_schema_is_refused_naming_the_expected_string(tmp_path):  # SYT-RUN-04.c2
    run = run_case(_cut_c(), tmp_path, "removed", change=lambda s: s.pop("schema"))
    _refused_at_load(run, "SYT-RUN-04.c2", "schema removed", SCHEMA)


def test_syt_run_05_c1_two_files_are_one_recording(tmp_path):  # SYT-RUN-05.c1
    case = _cut_c()
    one, two = tmp_path / "part_one.mcap", tmp_path / "part_two.mcap"
    messages = Recording(case.recording).messages
    sources = {topic for topic, _t, _p in messages if topic.startswith("source.")}
    edit_recording(case, one, lambda ms: [m for m in ms if m[0] in sources], drop_topics=[t for t in {m[0] for m in messages} if t not in sources])
    edit_recording(case, two, lambda ms: [m for m in ms if m[0] not in sources], drop_topics=sources)

    whole = tap_case(case, tmp_path / "whole", "whole")
    split = tap_case(case, tmp_path / "split", "split", change=lambda setup: point_at_recording(setup, one, two))

    assert whole.returncode == 0, f"SYT-RUN-05.c1: the unsplit run failed: {whole.stderr[-300:]}"
    assert split.returncode == 0, f"SYT-RUN-05.c1: the split run failed: {split.stderr[-300:]}"
    assert len(split.steps) == len(whole.steps), (
        f"SYT-RUN-05.c1: any difference: {len(split.steps)} steps from two files, {len(whole.steps)} from one")
    differences = compare_recordings(Recording(whole.recording), Recording(split.recording))
    assert differences == [], f"SYT-RUN-05.c1: any difference on a port: {differences}"


def _counter_after(candidate: int, wanted: int) -> bool:
    """`candidate` is later than `wanted` by `counterDistance` (a 32-bit counter that wraps; 0 is unknown)."""
    return candidate != 0 and wanted != 0 and 0 < (candidate - wanted) % 2**32 < 2**31


def _marked_runs(case, setup: dict) -> dict[tuple[str, int], list[str]]:
    """`{(stage, control counter): [ports]}` of the runs whose recorded refSync names a sample older than the port's
    newest at that step. A step takes in every recorded message at its instant, and a simulated producer's sample is
    in the port from the step its run is in (`VANTAGE_Architecture.md` section 7), so a simulated producer's sample
    counts from its control's reception time and any other from its own."""
    recording = Recording(case.recording)
    simulated = {s["name"] for s in setup["stages"] if s["mode"] == "simulate"}

    def arrivals(topic: str) -> list[tuple[int, int]]:
        producer = topic.split(".", 1)[0]
        if producer in simulated:
            control_time = {m.sig_header.measurement_counter: t for _i, t, m in recording.decoded(f"{producer}.control")}
            return [(control_time.get(m.sig_header.measurement_counter, t), m.sig_header.measurement_counter)
                    for _i, t, m in recording.decoded(topic)]
        return [(t, m.sig_header.measurement_counter) for _i, t, m in recording.decoded(topic)]

    marked: dict[tuple[str, int], list[str]] = {}
    for stage in setup["stages"]:
        if stage["mode"] != "simulate":
            continue
        topic_of = {i["port"]: (f"source.{i['producer_port']}" if i["producer"] == "source"
                                else f"{i['producer']}.{i['producer_port']}") for i in stage["inputs"]}
        runs = zip(recording.decoded(f"{stage['name']}.control"), recording.decoded(f"{stage['name']}.refSync"))
        for (_ci, control_time, control), (_ri, _rt, ref_sync) in runs:
            for entry in ref_sync.inputs:
                if entry.measurement_counter == 0:
                    continue
                arrived = [k for t, k in arrivals(topic_of[entry.port]) if t <= control_time]
                if arrived and _counter_after(arrived[-1], entry.measurement_counter):
                    marked.setdefault((stage["name"], control.sig_header.measurement_counter), []).append(entry.port)
    return marked


def _depth_one(setup: dict) -> None:
    for stage in setup["stages"]:
        for port in stage["ports"]:
            port["buffer_depth"] = 1


def test_syt_run_06_c1_depth_one_raises_fallback_in_exactly_the_marked_runs(tmp_path):  # SYT-RUN-06.c1
    case = lab_case("running_example", "all_simulated")
    setup = json.loads(case.setup.read_text(encoding="utf-8"))
    marked = _marked_runs(case, setup)
    assert marked, "SYT-RUN-06.c1: no run of the case is marked, so the case could not fail (the lab recording changed?)"

    tapped = tap_case(case, tmp_path, "tap", change=_depth_one)
    engine = run_case(case, tmp_path, "engine", change=_depth_one)
    assert tapped.returncode == 0 and engine.returncode == 0, (
        f"SYT-RUN-06.c1: depth 1 stopped a run: tap exit {tapped.returncode} {tapped.stderr[-200:]}, "
        f"engine exit {engine.returncode} {engine.error_text().strip()}")

    # The step each run is in: the logging time of that run's outputs in the engine-run recording.
    produced = Recording(engine.recording)
    step_time = {}
    for stage in {stage for stage, _k in marked}:
        for _i, t, message in produced.decoded(f"{stage}.refSync"):
            step_time[(stage, message.sig_header.measurement_counter)] = t
    marked_steps = {(stage, step_time.get((stage, k))) for (stage, k) in marked}
    missing_runs = sorted(f"{stage} run {k}" for (stage, k) in marked if (stage, k) not in step_time)

    # A run is in a step where KIND_FALLBACK on one of its stage's ports counted up since the step before.
    raised: set[tuple[str, int]] = set()
    previous: dict[str, int] = {}
    for step in tapped.steps:
        for badge in step["badges"]:
            if badge["kind"] == "KIND_FALLBACK":
                if badge["count"] > previous.get(badge["subject"], 0):
                    raised.add((badge["subject"].split(".", 1)[0], step["time_ns"]))
                previous[badge["subject"]] = badge["count"]

    problems = []
    if missing_runs:
        problems.append(f"a marked run without KIND_FALLBACK, the run is not in the engine-run recording: {missing_runs}")
    without = sorted(s for s in marked_steps - raised if s[1] is not None)
    if without:
        problems.append(f"a marked run without KIND_FALLBACK (stage, step time ns): {without}")
    wrongly = sorted(raised - marked_steps)
    if wrongly:
        problems.append(f"an unmarked run with KIND_FALLBACK (stage, step time ns): {wrongly}")
    for (stage, _k), ports in marked.items():
        for port in ports:
            if tapped.badge_count("KIND_FALLBACK", f"{stage}.{port}") == 0:
                problems.append(f"a marked run without KIND_FALLBACK on its own port {stage}.{port}")
    assert not problems, "SYT-RUN-06.c1: " + "; ".join(problems)


def test_syt_run_06_c2_the_provisional_depth_raises_no_fallback(tmp_path):  # SYT-RUN-06.c2
    case = lab_case("running_example", "all_simulated")
    tapped = tap_case(case, tmp_path, "provisional")
    assert tapped.returncode == 0, f"SYT-RUN-06.c2: the run failed: {tapped.stderr[-300:]}"
    assert tapped.steps, "SYT-RUN-06.c2: the tap printed no step"
    assert tapped.badges("KIND_FALLBACK") == {}, f"SYT-RUN-06.c2: KIND_FALLBACK raised: {tapped.badges('KIND_FALLBACK')}"


def test_syt_run_07_c1_a_measured_stage_without_recorded_outputs_is_refused(tmp_path):  # SYT-RUN-07.c1
    case = _cut_c()
    without = edit_recording(case, tmp_path / "without_c_out.mcap", lambda ms: [m for m in ms if m[0] != "C.out"],
                             drop_topics=["C.out"])
    run = run_case(case, tmp_path, "run", change=lambda s: point_at_recording(s, without))
    _refused_at_load(run, "SYT-RUN-07.c1", "C.out removed from the recording", "C", "out")


def _probe_copy(directory: Path, stage: str, log: Path) -> Path:
    """The exec probe's library copied to `directory/probe_<stage>/` with its own `config/` naming the stage and
    the call log (the probe reads no other input)."""
    source = tool_path("exec_probe")
    folder = directory / f"probe_{stage}"
    (folder / "config").mkdir(parents=True)
    library = folder / source.name
    shutil.copyfile(source, library)
    (folder / "config" / "default.yaml").write_text(
        f"PROBE_STAGE_NAME: {stage}\nPROBE_LOG_FILE: {log.as_posix()}\nPROBE_SPIN_MS: 0\n", encoding="utf-8")
    return library


def _probe_calls(case, directory: Path, mode: str) -> tuple[EngineRun, int]:
    log = directory / f"{mode}.calls.log"
    library = _probe_copy(directory / mode, "C", log)

    def put_probe(setup: dict) -> None:
        stage = stage_of(setup, "C")
        stage["impl"]["path"] = library.as_posix()
        stage["mode"] = mode

    run = run_case(case, directory, mode, change=put_probe)
    calls = sum(1 for line in log.read_text(encoding="utf-8").splitlines() if "event=enter" in line) if log.exists() else 0
    return run, calls


@pytest.mark.parametrize(("mode", "case_id"), [("measured", "SYT-RUN-08.c1"), ("off", "SYT-RUN-08.c2")])
def test_syt_run_08_a_measured_or_off_stage_is_never_called(tmp_path, mode, case_id):  # SYT-RUN-08.c1 (measured), SYT-RUN-08.c2 (off)
    run, calls = _probe_calls(_cut_c(), tmp_path, mode)
    assert run.returncode == 0, f"{case_id}: the run failed, so no call proves nothing: {run.stderr[-300:]}"
    assert calls == 0, f"{case_id}: {calls} call(s) of the probe on a {mode} stage"


def test_syt_run_08_c3_a_simulated_stage_is_called_once_per_recorded_control(tmp_path):  # SYT-RUN-08.c3
    case = _cut_c()
    run, calls = _probe_calls(case, tmp_path, "simulate")
    recorded = len(Recording(case.recording).of("C.control"))
    assert run.returncode == 0, f"SYT-RUN-08.c3: the run failed: {run.stderr[-300:]}"
    assert recorded > 0 and calls == recorded, f"SYT-RUN-08.c3: {calls} calls for {recorded} recorded C controls"


def test_syt_run_09_c1_each_retired_key_is_refused_with_its_place(tmp_path):  # SYT-RUN-09.c1
    case = _cut_c()
    plantings = (
        ("delay_steps", "stages[B].inputs[in_A]", lambda s: stage_of(s, "B")["inputs"][0].update(delay_steps=1)),
        ("grid_step_ns", "top level", lambda s: s.update(grid_step_ns=1_000_000)),
        ("order", "top level", lambda s: s.update(order=["A", "B"])),
    )
    for key, place, plant in plantings:
        run = run_case(case, tmp_path, f"with_{key}", change=plant)
        _refused_at_load(run, "SYT-RUN-09.c1", f"{key} added", key, place)


def test_syt_run_09_c2_an_unknown_key_is_refused_naming_it_and_its_stage(tmp_path):  # SYT-RUN-09.c2
    run = run_case(_cut_c(), tmp_path, "colour", change=lambda s: stage_of(s, "A").update(colour="red"))
    _refused_at_load(run, "SYT-RUN-09.c2", "colour added to stage A", "colour", "stages[A]")


def test_syt_run_09_c3_impl_pattern_is_refused_naming_it_and_its_stage(tmp_path):  # SYT-RUN-09.c3
    run = run_case(_cut_c(), tmp_path, "pattern", change=lambda s: stage_of(s, "A")["impl"].update(pattern="x*"))
    _refused_at_load(run, "SYT-RUN-09.c3", "pattern added to A's impl", "pattern", "stages[A].impl")


def _engine_run_bundle(tmp_path: Path):
    case = _cut_c()
    run = run_case(case, tmp_path, "bundles")
    assert run.returncode == 0, f"the cut_c run failed: {run.stderr[-300:]}"
    dump = next((c for c in _DUMP_CANDIDATES if c.is_file()), None)
    if dump is None:
        pytest.skip(f"recording_dump is not built (build.bat -t gtest); looked for {[str(c) for c in _DUMP_CANDIDATES]}")
    held = _what_vantages_reader_returns(dump, run.recording)["blocks"].get("config_bundle")
    return case, json.loads(run.setup.read_text(encoding="utf-8")), held


def test_syt_run_11_c1_the_recording_embeds_exactly_the_simulated_stages_bundles(tmp_path):  # SYT-RUN-11.c1
    _case, setup, held = _engine_run_bundle(tmp_path)
    assert held, "SYT-RUN-11.c1: the recording has no config_bundle block"
    simulated = {s["name"] for s in setup["stages"] if s["mode"] == "simulate"}
    named = {key.split("/", 1)[0] for key in held}
    assert named == simulated, f"SYT-RUN-11.c1: a stage missing or extra: the block names {sorted(named)}, the simulated stages are {sorted(simulated)}"

    on_disk: dict[str, str] = {}
    for stage in setup["stages"]:
        if stage["mode"] != "simulate":
            continue
        folder = Path(stage["impl"]["path"]).parent / "config"
        for item in sorted(folder.rglob("*")):
            if item.is_file():
                on_disk[f"{stage['name']}/{item.relative_to(folder).as_posix()}"] = item.read_bytes().decode("utf-8")
    assert sorted(held) == sorted(on_disk), (
        f"SYT-RUN-11.c1: a file missing or extra: missing {sorted(set(on_disk) - set(held))}, extra {sorted(set(held) - set(on_disk))}")
    different = sorted(key for key in on_disk if held[key] != on_disk[key])
    assert not different, f"SYT-RUN-11.c1: a file different from the folder's: {different}"


def test_syt_run_11_c2_each_bundle_hash_equals_the_setups(tmp_path):  # SYT-RUN-11.c2
    _case, setup, held = _engine_run_bundle(tmp_path)
    assert held, "SYT-RUN-11.c2: the recording has no config_bundle block"
    for stage in setup["stages"]:
        if stage["mode"] != "simulate":
            continue
        text = held.get(f"{stage['name']}/bundle.sha256")
        assert text is not None, f"SYT-RUN-11.c2: stage {stage['name']} has no bundle.sha256 in the block"
        assert text.strip() == stage["config_bundle_sha256"], (
            f"SYT-RUN-11.c2: stage {stage['name']}: bundle.sha256 {text.strip()!r} differs from the setup's {stage['config_bundle_sha256']!r}")
