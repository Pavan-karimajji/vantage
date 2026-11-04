# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`SYT-LCH-01` and `SYT-LCH-03`..`08` (`VANTAGE_Test_Spec.md` section 11): the launcher. `F-LAUNCH` is the launcher model driven from
Python on a lab case: `tests/support/launch_runs.py::pipeline_file` writes the run configuration the lab case's setup implies, a
`Selection` of it is the case's selection, and the run setup is what `launcher.write.write_run_setup` writes for it. No test here
starts an engine run.

Where the spec leaves a step open it is chosen so the case can fail:
- "the run setup" of `SYT-LCH-01` is the run configuration file `to_run_config` writes and `Selection.from_spec` reads (the launcher's
  own state), and of `SYT-LCH-06`/`07` the engine's setup `write_run_setup` writes (`impl.path`, `sources[].sha256`,
  `coherence_verdict`);
- "every lab case" of `SYT-LCH-06` is every exact case of the catalogue that `Pipeline.load` can load: not the `feedback` topology (see
  `_LAUNCHABLE`); a cut with a measured stage between simulated ones is started with the waiver `SYS-0116` asks for;
- the zeroed copy of `SYT-LCH-04` keeps every message's time and topic and sets each payload byte to 0;
- the three single-field changes of `SYT-LCH-01.c4` are the engine's call timeout, the run id and one stage's mode.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import warnings
from pathlib import Path

import pytest
import yaml

from adas_sim.cli import main as sim_main
from adas_sim.config.paths import ConfigPaths
from adas_sim.diagnostics.errors import AuthoringError, EnvironmentError_, exit_code_meaning
from adas_sim.graph.waiver import Policy, WaiverForbidden, waive
from adas_sim.launcher.availability import check_availability
from adas_sim.launcher.classify import LaunchBlocked, classify, forget_warned_orphans, remedies_for
from adas_sim.launcher.cuts import stage_facts, topic_index
from adas_sim.launcher.dry_run import dry_run
from adas_sim.launcher.model import Selection
from adas_sim.launcher.write import to_run_config, write_run_setup
from tests.support.engine_runs import case_params, exact_cases
from tests.support.lab_cases import edit_recording, lab_case
from tests.support.launch_runs import pipeline_file


def _selection(case, tmp_path, name="lab", modes=None):
    path, search = pipeline_file(case, tmp_path, name=name, modes=modes)
    return Selection.from_spec(path, search=search), path, search


def test_syt_lch_01_the_launcher_keeps_no_state_outside_the_setup(tmp_path):  # SYT-LCH-01
    """`SYT-LCH-01`, `SYS-0106`, `SYS-0118`, `SYS-0197`, `SYS-0198` Accept."""
    case = lab_case("running_example", "cut_c")
    selection, _path, search = _selection(case, tmp_path)
    first = to_run_config(selection, tmp_path / "first.yaml")
    again = to_run_config(Selection.from_spec(first, search=search), tmp_path / "again.yaml")
    assert first.read_bytes() == again.read_bytes(), "SYT-LCH-01.c1: the setup written, read back and written again differs"

    before = to_run_config(selection, tmp_path / "before.yaml").read_bytes()
    extra = tmp_path / "other.mcap"
    extra.write_bytes(selection.selected_recording.read_bytes())
    for label, change in (("set_mode", lambda s: s.set_mode("B", "measured")), ("set_impl", lambda s: s.set_impl("B", "dll:lab_running_example_B")),
                          ("isolate", lambda s: s.isolate("B")), ("add_recording", lambda s: s.add_recording(extra))):
        assert change(selection) is not selection, f"SYT-LCH-01.c2: {label} returned the selection it was given"
        assert to_run_config(selection, tmp_path / f"after_{label}.yaml").read_bytes() == before, f"SYT-LCH-01.c2: {label} changed the original"

    one = selection.set_mode("C", "measured").set_mode("B", "simulate").add_recording(extra)
    other = selection.add_recording(extra).set_mode("B", "simulate").set_mode("C", "measured")
    assert to_run_config(one, tmp_path / "one.yaml").read_bytes() == to_run_config(other, tmp_path / "other.yaml").read_bytes(), \
        "SYT-LCH-01.c3: two orders of the same choices write different setups"

    def hash_of(sel, **kwargs):
        return json.loads(write_run_setup(sel, tmp_path / "h.run.json", **kwargs).read_text(encoding="utf-8"))["spec_sha256"]

    hashes = [hash_of(selection), hash_of(selection)]
    assert hashes[0] == hashes[1] and hashes[0], "SYT-LCH-01.c4: one setup written twice gives two hashes"
    changed = {hash_of(selection, exec_timeout_ms=251), hash_of(selection, run_id="another"), hash_of(selection.set_mode("A", "measured"))}
    assert len(changed | {hashes[0]}) == 4, "SYT-LCH-01.c4: a changed field left spec_sha256 unchanged"


def test_syt_lch_03_the_exit_codes_meaning_is_printed():  # SYT-LCH-03
    """`SYT-LCH-03`, `SYS-0111` Accept: each of the eight codes prints its name and one line; 1 and 9 print as unknown. FAIL: an unlisted
    code printed as a name, or a listed one printed as unknown."""
    names = {0: "ok", 2: "config", 3: "coherence", 4: "module", 5: "input", 6: "infra", 7: "timeout", 8: "crash"}
    for code, name in names.items():
        text = exit_code_meaning(code)
        assert text.startswith(f"{code} {name}: ") and len(text) > len(f"{code} {name}: "), f"SYT-LCH-03.c1: {text!r}"
    for code in (1, 9):
        assert exit_code_meaning(code) == f"{code} unknown", f"SYT-LCH-03.c1: {exit_code_meaning(code)!r}"


def _without_topic(case, tmp_path, name, topic):
    return edit_recording(case, tmp_path / name, lambda ms: [m for m in ms if m[0] != topic], drop_topics=[topic])


def test_syt_lch_04_feasible_cuts_come_from_the_index_and_measured_is_checked(tmp_path):  # SYT-LCH-04
    """`SYT-LCH-04`, `SYS-0112` and `SYS-0113` Accept."""
    case = lab_case("running_example", "cut_c")
    selection, _path, _search = _selection(case, tmp_path)
    whole = topic_index(case.recording)
    zeroed = edit_recording(case, tmp_path / "zeroed.mcap", lambda ms: [(t, ns, bytes(len(p))) for t, ns, p in ms])
    facts = stage_facts(selection, whole)
    assert {f.stage for f in facts} == {"A", "B", "C", "D", "E"} and all(f.outputs and f.control and f.ref_sync for f in facts), \
        f"SYT-LCH-04.c1: the report of the whole recording is {facts}"
    assert stage_facts(selection, topic_index(zeroed)) == facts, "SYT-LCH-04.c1: a recording with zeroed payloads gives another report"

    without = _without_topic(case, tmp_path, "no_c_out.mcap", "C.out")
    blocked = selection.add_recording(without).select_recording(without)
    with pytest.raises(AuthoringError) as refused:
        blocked.set_mode("C", "measured")
    assert "'C'" in str(refused.value) and "out" in str(refused.value), f"SYT-LCH-04.c2: {refused.value}"
    assert not list(tmp_path.glob("*.run.json")), "SYT-LCH-04.c2: a setup was written for the refusal"
    assert selection.set_mode("C", "measured") is not None  # the recording that holds the topic accepts it


def test_syt_lch_05_a_trigger_is_offered_only_as_the_recording_allows(tmp_path):  # SYT-LCH-05
    """`SYT-LCH-05`, `SYS-0114` Accept: `in_X`, `in_Y` and, with the topic, `control`; without it no `control`. FAIL: `control` offered
    without its topic, or an undeclared input offered."""
    case = lab_case("data_triggered", "by_data")
    selection, _path, _search = _selection(case, tmp_path)
    assert set(selection.offered_triggers("T")) == {"in_X", "in_Y", "control"}, selection.offered_triggers("T")
    without = _without_topic(case, tmp_path, "no_t_control.mcap", "T.control")
    narrowed = selection.add_recording(without).select_recording(without)
    assert set(narrowed.offered_triggers("T")) == {"in_X", "in_Y"}, narrowed.offered_triggers("T")


#: `Pipeline.load` still refuses a stage fed by one declared after it (`_validate_wiring`, the grid-era "declaration order is execution
#: order" rule), and the `feedback` topology declares `B` before the `A` it reads; the engine orders by wiring (`ARCH §5`). The launcher cannot
#: load that topology until the check goes (`IMP-0162`, `WP-23`): its cases are left out here and reported.
_LAUNCHABLE = [case for case in exact_cases() if case[0] != "feedback"]


@pytest.mark.parametrize(("topology", "scenario", "name"), case_params(_LAUNCHABLE))
def test_syt_lch_06_c1_every_written_setup_names_absolute_libraries_and_the_sources_hash(tmp_path, topology, scenario, name):  # SYT-LCH-06
    """`SYT-LCH-06.c1` and `.c3`, `SYS-0119` and `SYS-0193` Accept over every exact case. FAIL: a relative path, a missing file, a hash that does
    not match the file."""
    case = lab_case(topology, name, scenario)
    selection, _path, _search = _selection(case, tmp_path)
    # A cut with a measured stage between simulated ones is a broken chain the launcher refuses (`SYS-0115`); the fake car ran it, so
    # the case is started with the waiver `SYS-0116` asks for.
    blocking = classify(selection.working_pipeline).blocking
    waivers = tuple(waive(finding, "the lab case's fake car ran this cut") for finding in blocking)
    setup = json.loads(write_run_setup(selection, tmp_path / "w.run.json", waivers=waivers).read_text(encoding="utf-8"))
    simulated = [s for s in setup["stages"] if s["mode"] == "simulate"]
    assert simulated, f"SYT-LCH-06.c1: {topology}/{scenario}/{name} has no simulated stage, so the case could not fail"
    for stage in simulated:
        library = Path(stage["impl"]["path"])
        assert library.is_absolute() and library.is_file(), f"SYT-LCH-06.c1: {stage['name']} impl.path {library} is not an absolute existing file"
    for source in setup["sources"]:
        assert source["sha256"] == hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest(), "SYT-LCH-06.c3: the hash is not the file's"


def test_syt_lch_06_c1_a_stage_with_no_library_ends_the_launcher_before_a_file_is_written(tmp_path):  # SYT-LCH-06.c1
    case = lab_case("running_example", "cut_c")
    path, search = pipeline_file(case, tmp_path)
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document["stages"][0]["impl"] = "dll:no_such_stem_for_lch"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    with pytest.raises((AuthoringError, EnvironmentError_)) as refused:
        write_run_setup(Selection.from_spec(path, search=search), tmp_path / "never.run.json")
    assert "no_such_stem_for_lch" in str(refused.value) and "A" in str(refused.value), f"SYT-LCH-06.c1: {refused.value}"
    assert not (tmp_path / "never.run.json").exists(), "SYT-LCH-06.c1: a setup was written"


def test_syt_lch_06_c2_availability_is_told_without_loading(tmp_path):  # SYT-LCH-06.c2
    """`SYT-LCH-06.c2`, `SYS-0120` Accept: a garbage file with a library's name is reported present and no load is made; a missing one is
    reported absent with the reason. FAIL: a load attempt, or a missing file reported present."""
    import sys

    suffix = ".dll" if sys.platform == "win32" else ".so"
    (tmp_path / f"fake_lib{suffix}").write_bytes(b"not a library at all")
    found = check_availability("F", "dll:fake_lib", search=[tmp_path])
    assert found.available and found.reason == "", f"SYT-LCH-06.c2: {found}"
    missing = check_availability("G", "dll:absent_lib", search=[tmp_path])
    assert not missing.available and "absent_lib" in missing.reason, f"SYT-LCH-06.c2: {missing}"


def test_syt_lch_07_coherence_is_classified_at_selection_time(tmp_path):  # SYT-LCH-07
    """`SYT-LCH-07`, `SYS-0115`, `SYS-0116`, `SYS-0117` Accept on `measured_middle` (`A` and `B` simulate, `M` measured)."""
    case = lab_case("measured_middle", "cut_m")
    broken, _p, _s = _selection(case, tmp_path)
    with pytest.raises(LaunchBlocked) as blocked:
        write_run_setup(broken, tmp_path / "blocked.run.json")
    message = str(blocked.value)
    assert all(name in message for name in "AMB") and remedies_for(blocked.value.blocking[0]), f"SYT-LCH-07.c1: {message}"
    assert not (tmp_path / "blocked.run.json").exists(), "SYT-LCH-07.c1: a setup was written for the blocked selection"
    fixed, _p2, _s2 = _selection(case, tmp_path / "fixed", modes={"M": "simulate"})
    assert write_run_setup(fixed, tmp_path / "fixed.run.json").is_file(), "SYT-LCH-07.c1: M simulate did not pass"

    finding = blocked.value.blocking[0]
    granted = waive(finding, "known gap, the car ran M by hand")
    verdict = json.loads(write_run_setup(broken, tmp_path / "waived.run.json", waivers=(granted,)).read_text(encoding="utf-8"))["coherence_verdict"]
    assert "known gap, the car ran M by hand" in verdict and "waived" in verdict, f"SYT-LCH-07.c2: {verdict!r}"
    with pytest.raises(ValueError):
        waive(finding, "   ")
    with pytest.raises(WaiverForbidden):
        waive(finding, "a reason", policy=Policy(waivers_allowed=False))
    assert not (tmp_path / "forbidden.run.json").exists()

    forget_warned_orphans()
    orphan, _p3, _s3 = _selection(case, tmp_path / "orphan", modes={"M": "measured", "B": "measured"})
    assert classify(orphan.working_pipeline).findings[0].verdict.value == "orphan"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for n in range(3):
            write_run_setup(orphan, tmp_path / f"orphan_{n}.run.json")
    named = [w for w in caught if "'A'" in str(w.message)]
    assert len(named) == 1, f"SYT-LCH-07.c3: {len(named)} warnings naming the orphan A"


def test_syt_lch_08_the_dry_run_prints_each_value_with_its_layer(tmp_path, monkeypatch, capsys):  # SYT-LCH-08
    """`SYT-LCH-08`, `SYS-0121` Accept: every key printed with its layer and no process started. FAIL: a key without a layer, or a process
    started."""
    started = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: started.append(a) or (_ for _ in ()).throw(AssertionError("a process started")))
    composition = tmp_path / "composition"
    composition.mkdir()
    (composition / "package.yaml").write_text("version: 1\nunits:\n  - name: a\n    impl: dll:lab_a\n", encoding="utf-8")
    from adas_sim.config.kinds import FileKind

    lines = dry_run(ConfigPaths(project_root=tmp_path), cli={FileKind.COMPOSITION: {"version": 1}})
    assert lines and all("[" in line and line.rstrip().endswith("]") for line in lines), f"SYT-LCH-08: {lines}"
    assert any("[cli" in line for line in lines) and any("[package" in line for line in lines), f"SYT-LCH-08: two layers expected in {lines}"
    assert sim_main(["explain", str(tmp_path)]) == 0 and "composition.units" in capsys.readouterr().out
    assert started == [], "SYT-LCH-08: a process started"
