# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0052` (`SYS-0048`): `Pipeline.load` reads the run-setup values from the
run configuration and `Pipeline.setup_values` returns them, refusing a missing
one by name with no default. Two stages, `P` -> `C`, so a previous-cycle input
and a per-stage `trigger` both exist. System-level evidence (`SYT-RUN-10`) is
`tests/system/test_vnt_run_config.py`."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.graph.pipeline import Pipeline
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.runspec.emit import LiveMeasSpec


def _component(name: str, *, inputs=(), outputs=()) -> InProcessSilComponent:
    manifest = ComponentManifest(
        component=name, version="1", abi_version=1, build_id="test", inputs=tuple(inputs), outputs=tuple(outputs),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )
    component = InProcessSilComponent(name, manifest, lambda dt_ns, values: {})
    component.init()
    return component


def _components() -> dict[str, InProcessSilComponent]:
    return {
        "P": _component("P", outputs=[PortSpec(name="out", proto_type="test.A")]),
        "C": _component(
            "C", inputs=[PortSpec(name="in", proto_type="test.A")], outputs=[PortSpec(name="res", proto_type="test.B")],
        ),
    }


def _config() -> dict:
    return {
        "name": "two",
        "run_setup": {
            "readiness_limit_steps": 3, "fallback_max_gap": 5,
            "livemeas": {
                "name": "lm", "cycle_slot_count": 2, "cycle_slot_size": 64, "bulk_slot_count": 1, "bulk_slot_size": 32,
            },
        },
        "stages": [
            {"name": "P", "mode": "simulate", "impl": "stub:P", "inputs": {}, "trigger": "", "buffer_depth": {"*": 4}},
            {
                "name": "C", "mode": "simulate", "impl": "stub:C", "inputs": {"in": "P.out"}, "trigger": "in",
                "buffer_depth": {"*": 6, "res": 8}, "bulk": ["res"], "previous_cycle": ["in"],
            },
        ],
    }


def _load(tmp_path: Path, config: dict) -> Pipeline:
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return Pipeline.load(path, components=_components())


def test_every_configured_value_reaches_the_setup_values(tmp_path):
    values = _load(tmp_path, _config()).setup_values()

    assert (values.readiness_limit_steps, values.fallback_max_gap) == (3, 5)
    assert dict(values.trigger) == {"P": "", "C": "in"}
    assert dict(values.buffer_depth) == {"P.out": 4, "C.in": 6, "C.res": 8}  # an exact entry wins over '*'
    assert values.bulk == frozenset({"C.res"})
    assert values.previous_cycle == frozenset({"C.in"})
    assert values.livemeas == LiveMeasSpec(
        name="lm", cycle_slot_count=2, cycle_slot_size=64, bulk_slot_count=1, bulk_slot_size=32,
    )


def test_bulk_previous_cycle_and_livemeas_absent_mean_none(tmp_path):
    config = _config()
    del config["run_setup"]["livemeas"]
    del config["stages"][1]["bulk"], config["stages"][1]["previous_cycle"]

    values = _load(tmp_path, config).setup_values()

    assert (values.bulk, values.previous_cycle, values.livemeas) == (frozenset(), frozenset(), None)


def _drop(config: dict, what: str) -> None:
    if what == "readiness_limit_steps":
        del config["run_setup"]["readiness_limit_steps"]
    elif what == "fallback_max_gap":
        del config["run_setup"]["fallback_max_gap"]
    elif what == "run_setup":
        del config["run_setup"]
    elif what == "trigger":
        del config["stages"][1]["trigger"]
    elif what == "buffer_depth":
        del config["stages"][0]["buffer_depth"]
    elif what == "port_depth":
        config["stages"][1]["buffer_depth"] = {"res": 8}
    elif what == "livemeas_geometry":
        del config["run_setup"]["livemeas"]["bulk_slot_size"]
    else:
        raise AssertionError(what)


@pytest.mark.parametrize(("what", "named"), [
    ("readiness_limit_steps", "run_setup.readiness_limit_steps"),
    ("fallback_max_gap", "run_setup.fallback_max_gap"),
    ("run_setup", "run_setup.readiness_limit_steps"),
    ("trigger", "stages[C].trigger"),
    ("buffer_depth", "stages[P].ports[out].buffer_depth"),
    ("port_depth", "stages[C].ports[in].buffer_depth"),
    ("livemeas_geometry", "run_setup.livemeas.bulk_slot_size"),
])
def test_a_missing_value_is_an_authoring_error_naming_it(tmp_path, what, named):
    config = _config()
    _drop(config, what)
    pipeline = _load(tmp_path, config)  # loading a file that lacks a value is not the refusal

    with pytest.raises(AuthoringError, match=re.escape(named)):
        pipeline.setup_values()


def test_a_trigger_is_not_required_of_a_stage_that_is_not_simulated(tmp_path):
    config = _config()
    config["stages"][1]["mode"] = "off"
    del config["stages"][1]["trigger"]

    assert "C" not in _load(tmp_path, config).setup_values().trigger


@pytest.mark.parametrize("edit", [
    lambda c: c["run_setup"].update(colour="red"),
    lambda c: c["stages"][0].update(trigger=3),
    lambda c: c["stages"][0].update(buffer_depth={"*": "deep"}),
    lambda c: c["stages"][1].update(previous_cycle=["not_wired"]),
    lambda c: c["stages"][1].update(bulk="res"),
])
def test_a_malformed_key_is_refused_at_load(tmp_path, edit):
    config = _config()
    edit(config)

    with pytest.raises(AuthoringError):
        _load(tmp_path, config)


def test_a_value_that_is_not_an_integer_is_refused_by_name(tmp_path):
    config = _config()
    config["run_setup"]["fallback_max_gap"] = "6"

    with pytest.raises(AuthoringError, match="fallback_max_gap"):
        _load(tmp_path, config).setup_values()


def test_a_port_the_stage_does_not_declare_is_refused(tmp_path):
    config = _config()
    config["stages"][1]["bulk"] = ["nope"]

    with pytest.raises(AuthoringError, match=re.escape("stages[C].bulk")):
        _load(tmp_path, config).setup_values()


def test_the_values_survive_to_yaml_and_a_mode_change(tmp_path):
    pipeline = _load(tmp_path, _config())
    reloaded_path = tmp_path / "again.yaml"
    reloaded_path.write_text(pipeline.to_yaml(), encoding="utf-8")

    reloaded = Pipeline.load(reloaded_path, components=_components())
    flipped = pipeline.with_mode("C", "off")

    assert reloaded.setup_values() == pipeline.setup_values()
    assert flipped.setup_values().readiness_limit_steps == 3
    assert flipped.setup_values().trigger["C"] == "in"
