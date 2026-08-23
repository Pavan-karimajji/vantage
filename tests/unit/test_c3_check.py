# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C3 `sim check` wiring tests (docs/sim_implementation_plan.md):
`check/runner.py` (recording/pipeline discovery, resim + decode) and
`check/report.py` (formatting). No function name anywhere (`R-SIM-1`) --
the single stage under test is `widget`, same convention
`test_c1c_pipeline.py`/`test_c2_record_resim.py` already use.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
import yaml
from google.protobuf import descriptor_pb2 as _dpb
from google.protobuf import descriptor_pool as _dpool
from google.protobuf import message_factory as _mfactory

from adas_sim.check.expect import ExpectationResult
from adas_sim.check.report import format_report_json, format_report_md, suite_passed, write_report
from adas_sim.check.runner import (
    ScenarioCheckResult, check_scenario, check_scenarios, default_recording_stem_for, discover_pipelines,
)
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.graph.build import Pipeline
from adas_sim.config.scenario import (
    EgoScenario, RoadHint, RunControl, Scenario, ScenarioContent, SensorModelRef, SutRef,
)
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.runspec.manifest import build_manifest
from adas_sim.sources.recorder import Recorder
from adas_sim.sources.synthetic import SyntheticSource
from tests.system.test_d15b_engine_bridge import _echo_stub_path
from adas_sim.engine.bridge import resolve_simengine_executable


# ---------------------------------------------------------------------------
# default_recording_for / discover_pipelines -- pure path helpers
# ---------------------------------------------------------------------------


def test_default_recording_stem_for_swaps_sibling_folder_with_no_extension():
    scenario_path = Path("modules/df/tests/carla_scenarios/widget/widget_case.yaml")
    assert default_recording_stem_for(scenario_path) == Path("modules/df/tests/carla_testruns/widget/widget_case")


def test_default_recording_stem_for_raises_when_convention_does_not_apply():
    with pytest.raises(AuthoringError, match="carla_scenarios"):
        default_recording_stem_for(Path("some/other/layout/case.yaml"))


def test_discover_pipelines_scans_modules_star_sim_pipelines(tmp_path):
    pipeline_dir = tmp_path / "modules" / "widget" / "sim" / "pipelines"
    pipeline_dir.mkdir(parents=True)
    (pipeline_dir / "widget_only.yaml").write_text("name: widget_only\nstages: []\n", encoding="utf-8")

    pipelines = discover_pipelines(superproject_root=tmp_path)
    assert pipelines == {"widget_only": pipeline_dir / "widget_only.yaml"}


# ---------------------------------------------------------------------------
# check_scenario -- skip cases (ST-C3-3-equivalent) and the load error
# ---------------------------------------------------------------------------


def _write_scenario(
    path: Path, *, sut_pipeline: str | None = None, expect: list | None = None, faults: list | None = None,
) -> None:
    data = {
        "schema": 2, "id": path.stem, "doc": "fixture",
        "scenario": {"ego": {"speed_mps": 10.0}, "actors": []},
        "world": {}, "sensor_model": {}, "run": {"faults": faults or []},
        "sut": {"pipeline": sut_pipeline, "project": "base"},
        "markers": [],
        "expect": expect or [],
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_check_scenario_skips_when_recording_missing(tmp_path):
    scenario_path = tmp_path / "case.yaml"
    _write_scenario(scenario_path, sut_pipeline="widget_only")

    result = check_scenario(scenario_path, recording_path=tmp_path / "does_not_exist.mcap")
    assert result.skipped is True
    assert "recording not found" in result.skip_reason
    assert result.passed is True  # a skip is not a failure


def test_check_scenario_skips_when_no_sut_pipeline_declared(tmp_path):
    scenario_path = tmp_path / "case.yaml"
    _write_scenario(scenario_path, sut_pipeline=None)
    recording_path = tmp_path / "recording.mcap"
    recording_path.touch()  # existence is all the recording check needs here

    result = check_scenario(scenario_path, recording_path=recording_path)
    assert result.skipped is True
    assert "sut.pipeline" in result.skip_reason


def test_check_scenario_raises_when_named_pipeline_unknown(tmp_path):
    scenario_path = tmp_path / "case.yaml"
    _write_scenario(scenario_path, sut_pipeline="does_not_exist")
    recording_path = tmp_path / "recording.mcap"
    recording_path.touch()

    with pytest.raises(AuthoringError, match="does_not_exist"):
        check_scenario(scenario_path, recording_path=recording_path, pipelines={})


# ---------------------------------------------------------------------------
# check_scenario -- end to end: record a real value series, resim it, and
# evaluate expect: against the decoded result
# ---------------------------------------------------------------------------


def _scalar_message_cls():
    """A real `Scalar { x: float }` schema (mirrors
    `test_c1c_pipeline.py`'s own `_scalar_message_cls`) -- what
    `check/runner.py`'s eager decode actually parses."""
    fdp = _dpb.FileDescriptorProto()
    fdp.name = "c3_check_scalar.proto"
    fdp.package = "adas_sim.test.c3check"
    fdp.syntax = "proto3"
    msg = fdp.message_type.add()
    msg.name = "Scalar"
    f = msg.field.add()
    f.name, f.number, f.type = "x", 1, _dpb.FieldDescriptorProto.TYPE_FLOAT
    f.label = _dpb.FieldDescriptorProto.LABEL_OPTIONAL

    fds = _dpb.FileDescriptorSet()
    fds.file.append(fdp)

    pool = _dpool.DescriptorPool()
    pool.Add(fdp)
    cls = _mfactory.GetMessageClass(pool.FindMessageTypeByName("adas_sim.test.c3check.Scalar"))
    return cls, fds.SerializeToString()


def _widget_manifest(descriptor_set: bytes) -> ComponentManifest:
    return ComponentManifest(
        component="widget", version="1", abi_version=1, build_id="test",
        inputs=(), outputs=(PortSpec(name="outputs", proto_type="adas_sim.test.c3check.Scalar"),),
        project="base", config_bundle_sha256="", descriptor_set=descriptor_set, period_ns=100_000_000,
    )


def _write_widget_pipeline(path: Path, *, mode: str, component: InProcessSilComponent) -> Pipeline:
    stages = [{"name": "widget", "mode": mode, "impl": "stub:widget", "inputs": {}}]
    path.write_text(yaml.safe_dump({"name": "widget_only", "stages": stages}, sort_keys=False), encoding="utf-8")
    return Pipeline.load(path, components={"widget": component})


def _record_widget_recording(tmp_path: Path, values: list[float], *, descriptor_set: bytes, scalar_cls) -> Path:
    manifest = _widget_manifest(descriptor_set)
    remaining = iter(values)
    component = InProcessSilComponent("widget", manifest, lambda dt_ns, inputs: {"outputs": scalar_cls(x=next(remaining)).SerializeToString()})
    component.init()

    record_pipeline_path = tmp_path / "record_pipeline.yaml"
    pipeline = _write_widget_pipeline(record_pipeline_path, mode="simulate", component=component)

    source = SyntheticSource([{} for _ in values])
    recording_path = tmp_path / "recording.mcap"
    meta = build_manifest(pipeline=pipeline, pipeline_path=record_pipeline_path, run_kind="sim", source_kind="synthetic")
    recorder = Recorder(pipeline, source, recording_path, meta=meta)
    recorder.open(Scenario(
        schema=2, id="t", doc="",
        scenario=ScenarioContent(road=RoadHint(), ego=EgoScenario(speed_mps=0.0), actors=()),
        sensor_model=SensorModelRef(), run=RunControl(), sut=SutRef(),
    ))
    for _ in values:
        recorder.tick(100_000_000)
    recorder.close()
    return recording_path


def test_check_scenario_end_to_end_resims_and_evaluates_expect(tmp_path):
    scalar_cls, descriptor_set = _scalar_message_cls()
    values = [0.0, 0.2, 0.6, 1.0]
    recording_path = _record_widget_recording(tmp_path, values, descriptor_set=descriptor_set, scalar_cls=scalar_cls)

    check_pipeline_path = tmp_path / "check_pipeline.yaml"

    def _never(dt_ns, inputs):
        raise AssertionError("a measured stage must never execute during resim")

    check_component = InProcessSilComponent("widget", _widget_manifest(descriptor_set), _never)
    check_component.init()
    _write_widget_pipeline(check_pipeline_path, mode="measured", component=check_component)

    scenario_path = tmp_path / "case.yaml"
    _write_scenario(scenario_path, expect=[
        {"id": "EXP-BECOMES", "signal": "widget.outputs.x", "becomes": 1.0, "within_s": 0.15, "of": "marker.crossing"},
        {"id": "EXP-NEVER", "signal": "widget.outputs.x", "never": 5.0},
        {"id": "EXP-ALWAYS", "signal": "widget.outputs.x", "equals": 1.0, "always": True},
    ])
    raw = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    raw["markers"] = [{"id": "crossing", "at": {"first": "widget.outputs.x", "crosses": 0.5, "dir": "rising"}}]
    scenario_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = check_scenario(
        scenario_path, recording_path=recording_path, pipeline_path=check_pipeline_path,
        components={"widget": check_component},
    )

    assert result.skipped is False
    by_id = {r.id: r for r in result.results}
    assert by_id["EXP-BECOMES"].passed is True
    assert by_id["EXP-NEVER"].passed is True
    assert by_id["EXP-ALWAYS"].passed is False  # x is 0.0/0.2/0.6 before it ever reaches 1.0
    assert result.passed is False  # one failed expectation fails the scenario


# ---------------------------------------------------------------------------
# S-C3 -- `scenario.run.faults` actually reaches the resim, not just the
# schema (`check/runner.check_scenario` -> `Pipeline.load(faults=...)` ->
# `Pipeline.exec`'s own stimulus fault application, `test_c1c_pipeline.py`'s
# own unit level). `widget` here has a real INPUT wired to `source.stim`
# and echoes it -- a `mode: measured` stage (the earlier test's shape) never
# touches the stimulus at all, so this needs its own fixture.
#
# `WP-15b`: `check_scenario` now drives a real `simengine` subprocess
# (`engine.bridge`), which cannot run an injected `InProcessSilComponent`
# for a `mode: simulate` stage (no file on disk -> `pipeline_to_run_spec`
# emits an empty `impl`, `simengine` refuses to start). The real, built
# `echo_stub` fixture (`tests/fixtures/echo_stub`) gained a genuine
# input->output raw-byte echo for exactly this gap (see its own docstring,
# `ADAS_SIL_TEST_STUB_INPUT_PORT`) -- these two tests drive it for real,
# through `dll:echo_stub`, `ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA=1` giving
# it a real, decodable `abi_test.AbiPort{double value}` schema (the same
# one `WP-14a`'s own `UT-ABI-02` fixture uses) since check/runner.py's own
# decode needs a real `descriptor_set` to resolve a message class from
# (`resolve_message_classes`, `R-SIM-11`) -- `test.Echo`'s empty default
# schema cannot round-trip through that. Skipped, never failed, when this
# platform's own `simengine`/`echo_stub` build is absent, same discipline
# `test_d15b_engine_bridge.py` uses.
# ---------------------------------------------------------------------------


def _encode_abi_port(value: float) -> bytes:
    """`abi_test.AbiPort { double value = 1; }`, hand-encoded (field 1,
    wire type 1/fixed64) -- the exact wire format
    `echo_stub.cpp::EncodeAbiTestPort` produces, so a value written here
    round-trips through a real `abi_test.AbiPort` message class on the
    decode side with no protobuf pool needed on this end."""
    return struct.pack("<Bd", (1 << 3) | 1, value)


def _require_real_echo_stub() -> tuple[object, object]:
    try:
        engine = resolve_simengine_executable()
    except Exception as exc:  # noqa: BLE001 -- EnvironmentError_, re-raised as a skip below
        pytest.skip(f"no built simengine found: {exc}")
    stub = _echo_stub_path(engine)
    if stub is None:
        pytest.skip("no built echo_stub found paired with the resolved simengine binary")
    return engine, stub


def _configure_real_echo_stub(monkeypatch, *, lib_dir: Path, stub_path) -> None:
    lib_dir.mkdir(exist_ok=True)
    (lib_dir / ("echo_stub" + stub_path.suffix)).write_bytes(stub_path.read_bytes())
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_NAME", "widget")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_PERIOD_NS", "100000000")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_PORT", "outputs")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_OUTPUT_REAL_SCHEMA", "1")
    monkeypatch.setenv("ADAS_SIL_TEST_STUB_INPUT_PORT", "in")


def _write_real_echo_pipeline(path: Path) -> None:
    stages = [{"name": "widget", "mode": "simulate", "impl": "dll:echo_stub", "inputs": {"in": "source.stim"}}]
    path.write_text(yaml.safe_dump({"name": "widget_only", "stages": stages}, sort_keys=False), encoding="utf-8")


def _record_stim_recording(tmp_path: Path, name: str, values: list[float]) -> Path:
    """A recording carrying only a `/source/stim` topic -- all a
    `mode: simulate` stage with `inputs: {in: source.stim}` needs, since
    (unlike a `measured` stage) its own output is computed fresh, never
    read back from the recording."""
    from adas_sim.io.base import Provenance, RunManifest, TopicInfo
    from adas_sim.plugins.registry import writer_for

    recording_path = tmp_path / name
    writer = writer_for(recording_path)
    writer.open(
        recording_path, RunManifest(),
        {"/source/stim": TopicInfo(schema_name="abi_test.AbiPort", provenance=Provenance.MEASURED)},
    )
    for i, v in enumerate(values):
        t_ns = i * 100_000_000
        writer.write("/source/stim", t_ns, _encode_abi_port(v), capture_time_ns=t_ns)
    writer.close()
    return recording_path


def test_check_scenario_applies_scenario_faults_during_resim(tmp_path, monkeypatch):
    engine, stub = _require_real_echo_stub()
    _configure_real_echo_stub(monkeypatch, lib_dir=tmp_path / "lib", stub_path=stub)

    recording_path = _record_stim_recording(tmp_path, "echo_recording.mcap", [1.0, 2.0, 3.0])
    check_pipeline_path = tmp_path / "check_pipeline_echo.yaml"
    _write_real_echo_pipeline(check_pipeline_path)

    scenario_path = tmp_path / "case.yaml"
    _write_scenario(
        scenario_path,
        expect=[{"id": "EXP-CORRUPTED", "signal": "widget.outputs.value", "equals": 99.0, "always": True}],
        faults=[{"verb": "corrupt", "address": "stim.value", "value": 99.0, "from_s": 0.0, "to_s": 10.0}],
    )

    result = check_scenario(
        scenario_path, recording_path=recording_path, pipeline_path=check_pipeline_path,
        search=[tmp_path / "lib"],
    )

    assert result.skipped is False
    by_id = {r.id: r for r in result.results}
    # never 1.0/2.0/3.0 -- every tick's echoed value is the corrupt fault's value
    assert by_id["EXP-CORRUPTED"].passed is True


def test_check_scenario_expect_signal_resolves_self_dot_port_against_the_sole_simulate_stage(tmp_path, monkeypatch):
    """`S-C1cΔ`, `UT-C1c-22`: an `expect:`/marker `signal:` naming
    `self.outputs.value` resolves against `check_scenario`'s own
    `Pipeline` (its sole `mode: simulate` stage, `ST-C1c-2`'s canonical
    shape), producing the identical result the spelled
    `widget.outputs.value` signal already proves above --
    `contracts.binding.resolve` genuinely wired into `sim check`, not
    only unit-tested in isolation."""
    engine, stub = _require_real_echo_stub()
    _configure_real_echo_stub(monkeypatch, lib_dir=tmp_path / "lib", stub_path=stub)

    values = [0.0, 0.2, 0.6, 1.0]
    recording_path = _record_stim_recording(tmp_path, "self_recording.mcap", values)
    check_pipeline_path = tmp_path / "check_pipeline_self.yaml"
    _write_real_echo_pipeline(check_pipeline_path)

    scenario_path = tmp_path / "case_self.yaml"
    _write_scenario(scenario_path, expect=[
        {"id": "EXP-SELF-BECOMES", "signal": "self.outputs.value", "becomes": 1.0, "within_s": 0.15, "of": "marker.crossing"},
        {"id": "EXP-SELF-NEVER", "signal": "self.outputs.value", "never": 5.0},
    ])
    raw = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    raw["markers"] = [{"id": "crossing", "at": {"first": "self.outputs.value", "crosses": 0.5, "dir": "rising"}}]
    scenario_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = check_scenario(
        scenario_path, recording_path=recording_path, pipeline_path=check_pipeline_path,
        search=[tmp_path / "lib"],
    )

    assert result.skipped is False
    by_id = {r.id: r for r in result.results}
    assert by_id["EXP-SELF-BECOMES"].passed is True
    assert by_id["EXP-SELF-NEVER"].passed is True


def test_check_scenario_self_dot_port_raises_when_no_sole_simulate_stage(tmp_path):
    """No `mode: simulate` stage (a pure-`measured` check pipeline) means
    `self` is undefined -- a `self.`-prefixed signal raises naming why,
    never silently resolving to something guessed (`UT-C1c-23`,
    `R-SIM-25`/`NR-SIM-4`)."""
    scalar_cls, descriptor_set = _scalar_message_cls()
    values = [0.0, 0.2]
    recording_path = _record_widget_recording(tmp_path, values, descriptor_set=descriptor_set, scalar_cls=scalar_cls)

    check_pipeline_path = tmp_path / "check_pipeline_measured.yaml"

    def _never(dt_ns, inputs):
        raise AssertionError("a measured stage must never execute during resim")

    check_component = InProcessSilComponent("widget", _widget_manifest(descriptor_set), _never)
    check_component.init()
    _write_widget_pipeline(check_pipeline_path, mode="measured", component=check_component)

    scenario_path = tmp_path / "case_self_undefined.yaml"
    _write_scenario(scenario_path, expect=[{"id": "EXP-SELF", "signal": "self.outputs.x", "never": 5.0}])

    with pytest.raises(AuthoringError, match="self.outputs.x"):
        check_scenario(
            scenario_path, recording_path=recording_path, pipeline_path=check_pipeline_path,
            components={"widget": check_component},
        )


def test_check_scenarios_aggregates_a_directory(tmp_path):
    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir()
    _write_scenario(scenario_dir / "always_one.yaml", expect=[
        {"id": "EXP-1", "signal": "widget.outputs.x", "equals": 1.0, "always": True},
    ])

    results = check_scenarios(scenario_dir)
    # This scenario's path is outside the carla_scenarios/carla_testruns
    # convention (it lives directly under tmp_path), so recording
    # resolution itself is a skip -- exercising "skip, don't crash" over a
    # whole batch, rather than the real resim path (`test_..._end_to_end`
    # above, which passes an explicit recording_path/pipeline_path).
    assert len(results) == 1
    assert results[0].skipped is True


# ---------------------------------------------------------------------------
# report.py -- formatting only, never re-deriving pass/fail
# ---------------------------------------------------------------------------


def _fake_result(scenario_id: str, *, passed: bool) -> ScenarioCheckResult:
    expectation = ExpectationResult(
        id="EXP-1", doc="", signal="widget.outputs.x", passed=passed,
        detail="== 1.0 always" if passed else "was 0.0 at t=0.000s, expected always 1.0",
        actual_value=None if passed else 0.0, actual_time_s=None if passed else 0.0,
    )
    return ScenarioCheckResult(scenario_id=scenario_id, scenario_path=Path(f"{scenario_id}.yaml"), skipped=False, results=(expectation,))


def test_format_report_md_shows_pass_and_fail_marks():
    text = format_report_md([_fake_result("a", passed=True), _fake_result("b", passed=False)])
    assert "a" in text and "1/1 PASS" in text
    assert "b" in text and "0/1 FAIL" in text
    assert "✓" in text and "✗" in text


def test_format_report_md_shows_skipped_scenarios():
    skipped = ScenarioCheckResult(scenario_id="c", scenario_path=Path("c.yaml"), skipped=True, skip_reason="recording not found: x.mcap")
    text = format_report_md([skipped])
    assert "SKIPPED (recording not found: x.mcap)" in text


def test_format_report_json_round_trips():
    text = format_report_json([_fake_result("a", passed=True), _fake_result("b", passed=False)])
    payload = json.loads(text)
    assert payload[0]["scenario_id"] == "a"
    assert payload[0]["passed"] is True
    assert payload[1]["expectations"][0]["passed"] is False


def test_write_report_dispatches_by_extension(tmp_path):
    results = [_fake_result("a", passed=True)]
    md_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"

    write_report(results, md_path)
    write_report(results, json_path)

    assert "a" in md_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8"))[0]["scenario_id"] == "a"


def test_suite_passed_is_false_if_any_scenario_fails():
    """ST-C3-2 (unit half): suite_passed both ways -- all-pass is True, one
    failure is False."""
    assert suite_passed([_fake_result("a", passed=True)]) is True
    assert suite_passed([_fake_result("a", passed=True), _fake_result("b", passed=False)]) is False
