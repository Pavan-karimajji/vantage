# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`SYT-RUN-10` (`SYS-0048`, `IMP-0052`, fixture `F-RUN-CONFIG`): the launcher
writes a run setup only from a run configuration that gives every `⊘` value
and each simulated stage's trigger, and supplies no default.

The fixture is a pipeline file for the `echo_stub` stage on the generic ABI.
The tests stop the run at the engine call (a stand-in for `run_engine` that
reports failure) and read the run setup the real writer produced just before
it, so what is checked is the setup the three launcher paths write -- `sim
resim`, the batch worker and `sim check` -- not the engine's behaviour.
Skips (never fails) when this platform's `echo_stub` build is absent.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

import adas_sim.engine.bridge as bridge
from adas_sim.check.runner import check_scenario
from adas_sim.cli.resim import run as resim_run
from adas_sim.diagnostics.errors import AuthoringError, EnvironmentError_
from adas_sim.engine.bridge import EngineRunResult, resolve_simengine_executable
from adas_sim.orchestrate.worker import main as worker_main

from tests.system.test_d15b_engine_bridge import _echo_stub_path, _write_heartbeat_recording
from tests.unit.test_c3_check import _write_scenario

#: Values chosen to differ from every provisional number the lab uses, so a
#: default filled in by code cannot be mistaken for a configured value.
_LIVEMEAS = {
    "name": "run_config_probe", "cycle_slot_count": 5, "cycle_slot_size": 4096,
    "bulk_slot_count": 3, "bulk_slot_size": 2048,
}
_RUN_CONFIG = {
    "name": "run_config_fixture",
    "run_setup": {"readiness_limit_steps": 11, "fallback_max_gap": 7, "livemeas": _LIVEMEAS},
    "stages": [{
        "name": "sut", "mode": "simulate", "impl": "dll:echo_stub", "inputs": {},
        "trigger": "", "buffer_depth": {"*": 9, "outputs": 13}, "bulk": ["outputs"],
    }],
}


def _require_stub() -> Path:
    try:
        engine = resolve_simengine_executable()
    except EnvironmentError_ as exc:
        pytest.skip(f"no built simengine found: {exc}")
    stub = _echo_stub_path(engine)
    if stub is None:
        pytest.skip("no built echo_stub found paired with the resolved simengine binary")
    return stub


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """The stub library beside a recording, and the two stand-ins: the
    writer is wrapped (its setups are kept) and the engine call reports
    failure, so the run ends right after the setup is written."""
    stub = _require_stub()
    for name, value in (
        ("NAME", "echo_stub"), ("PERIOD_NS", "10000000"), ("OUTPUT_PORT", "outputs"),
        ("OUTPUT_PROTO_TYPE", "test.Echo"), ("OUTPUT_MAX_BYTES", "64"),
    ):
        monkeypatch.setenv(f"ADAS_SIL_TEST_STUB_{name}", value)
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / ("echo_stub" + stub.suffix)).write_bytes(stub.read_bytes())
    recording = tmp_path / "in.mcap"
    _write_heartbeat_recording(recording)

    written: list[dict] = []
    real_write = bridge.write_run_spec

    def _write(spec, path):
        digest = real_write(spec, path)
        written.append(json.loads(Path(path).read_text(encoding="utf-8")))
        return digest

    def _engine_stopped(spec_path, *, output_path=None, **_kwargs):
        return EngineRunResult(
            exit_code=1, ok=False, stdout="", stderr="engine stopped by the test", output_path=output_path,
        )

    monkeypatch.setattr(bridge, "write_run_spec", _write)
    monkeypatch.setattr(bridge, "run_engine", _engine_stopped)
    return {"dir": tmp_path, "lib": lib_dir, "recording": recording, "written": written}


def _write_config(path: Path, remove: str | None = None) -> Path:
    config = yaml.safe_load(yaml.safe_dump(_RUN_CONFIG))
    if remove == "readiness_limit_steps":
        del config["run_setup"]["readiness_limit_steps"]
    elif remove == "fallback_max_gap":
        del config["run_setup"]["fallback_max_gap"]
    elif remove == "trigger":
        del config["stages"][0]["trigger"]
    elif remove == "buffer_depth":
        del config["stages"][0]["buffer_depth"]
    elif remove is not None:
        raise AssertionError(remove)
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


_REMOVALS = (
    ("readiness_limit_steps", "run_setup.readiness_limit_steps"),
    ("fallback_max_gap", "run_setup.fallback_max_gap"),
    ("trigger", "stages[sut].trigger"),
    ("buffer_depth", "stages[sut].ports[outputs].buffer_depth"),
)


@pytest.mark.parametrize(("removed", "named"), _REMOVALS)
def test_syt_run_10_c1_each_missing_value_is_refused_by_name_and_no_setup_is_written(rig, removed, named):
    """SYT-RUN-10.c1"""
    pipeline = _write_config(rig["dir"] / "pipeline.yaml", remove=removed)

    with pytest.raises(AuthoringError, match=re.escape(named)):
        resim_run([str(rig["recording"]), "--pipeline", str(pipeline), "--search", str(rig["lib"])])

    assert rig["written"] == []
    assert not list(rig["dir"].glob("**/*.spec.json"))


def _assert_configured_values(spec: dict) -> None:
    assert spec["readiness_limit_steps"] == 11
    assert spec["fallback_max_gap"] == 7
    assert spec["outputs"]["livemeas"] == _LIVEMEAS
    (stage,) = spec["stages"]
    assert stage["trigger"] == ""
    (port,) = stage["ports"]
    assert (port["name"], port["buffer_depth"], port["bulk"]) == ("outputs", 13, True)


def test_syt_run_10_c2_sim_resim_writes_exactly_the_configured_values(rig):
    """SYT-RUN-10.c2 (sim resim)"""
    pipeline = _write_config(rig["dir"] / "pipeline.yaml")

    with pytest.raises(AuthoringError, match="simengine to exit ok"):
        resim_run([str(rig["recording"]), "--pipeline", str(pipeline), "--search", str(rig["lib"])])

    (spec,) = rig["written"]
    _assert_configured_values(spec)


def test_syt_run_10_c2_the_batch_worker_writes_exactly_the_configured_values(rig):
    """SYT-RUN-10.c2 (orchestrate/worker.py)"""
    pipeline = _write_config(rig["dir"] / "pipeline.yaml")
    out_json = rig["dir"] / "worker_out.json"

    exit_code = worker_main([
        "--recording", str(rig["recording"]), "--pipeline", str(pipeline), "--out-json", str(out_json),
        "--search", str(rig["lib"]),
    ])

    assert exit_code == 1  # the stopped engine; the setup was written before it
    (spec,) = rig["written"]
    _assert_configured_values(spec)


def test_syt_run_10_c1_the_batch_worker_reports_a_missing_value_by_name(rig):
    """SYT-RUN-10.c1 (orchestrate/worker.py)"""
    pipeline = _write_config(rig["dir"] / "pipeline.yaml", remove="fallback_max_gap")
    out_json = rig["dir"] / "worker_out.json"

    exit_code = worker_main([
        "--recording", str(rig["recording"]), "--pipeline", str(pipeline), "--out-json", str(out_json),
        "--search", str(rig["lib"]),
    ])

    assert exit_code == 1
    assert "run_setup.fallback_max_gap" in json.loads(out_json.read_text(encoding="utf-8"))["error"]
    assert rig["written"] == []


def test_syt_run_10_c2_sim_check_writes_exactly_the_configured_values(rig):
    """SYT-RUN-10.c2 (sim check)"""
    pipeline = _write_config(rig["dir"] / "pipeline.yaml")
    scenario = rig["dir"] / "case.yaml"
    _write_scenario(scenario)

    with pytest.raises(AuthoringError, match="simengine to exit ok"):
        check_scenario(
            scenario, recording_path=rig["recording"], pipeline_path=pipeline, search=[rig["lib"]],
        )

    (spec,) = rig["written"]
    _assert_configured_values(spec)


def test_syt_run_10_c1_sim_check_refuses_a_missing_value_by_name(rig):
    """SYT-RUN-10.c1 (sim check)"""
    pipeline = _write_config(rig["dir"] / "pipeline.yaml", remove="trigger")
    scenario = rig["dir"] / "case.yaml"
    _write_scenario(scenario)

    with pytest.raises(AuthoringError, match=re.escape("stages[sut].trigger")):
        check_scenario(
            scenario, recording_path=rig["recording"], pipeline_path=pipeline, search=[rig["lib"]],
        )

    assert rig["written"] == []
