# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C2 slice 1: the `Source` Protocol's own wiring hook, plus `record:`
policy parsing/validation (`sim_implementation_plan.md` S-C2, `NR-SIM-42`).
Fixtures mirror `test_c1c_pipeline.py`'s own style: synthetic, invented
components, no real function name anywhere (`R-SIM-1`)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.contracts.pipeline import Pipeline, RecordPolicy, RecordVerb, Stage, record_policy_for, validate_recordable
from adas_sim.contracts.scenario import Scenario
from adas_sim.core.errors import AuthoringError
from adas_sim.sources.base import Source


def _manifest(*, component: str, inputs=(), outputs=(), period_ns: int = 0) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=period_ns,
    )


def _stub(name: str, manifest: ComponentManifest) -> InProcessSilComponent:
    component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
    component.init()
    return component


def _write_pipeline(tmp_path: Path, stages: list[dict]) -> Path:
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"name": "test", "stages": stages}, sort_keys=False), encoding="utf-8")
    return path


class _FakeSource:
    """Just enough of `Source` for the wiring check -- `poll()`/`start()`/
    `stop()` are never called by `Pipeline.load`."""

    def __init__(self, name: str, ports: frozenset[str]) -> None:
        self.name = name
        self._ports = ports

    def emits(self) -> frozenset[str]:
        return self._ports

    def start(self, scenario: Scenario) -> None:  # pragma: no cover -- unused here
        raise NotImplementedError

    def poll(self):  # pragma: no cover -- unused here
        raise NotImplementedError

    def stop(self) -> None:  # pragma: no cover -- unused here
        raise NotImplementedError


# ---------------------------------------------------------------------------
# UT-C2-10 -- emits() is honoured: a pipeline requesting a port the source
# cannot produce fails at load naming the source and the port
# ---------------------------------------------------------------------------


def test_source_port_outside_emits_raises_naming_source_and_port(tmp_path):
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="in", proto_type="test.A")])
    stages = [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"in": "source.nope"}}]
    path = _write_pipeline(tmp_path, stages)
    source = _FakeSource("fake", frozenset({"gen_object_list"}))

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={"consumer": _stub("consumer", consumer)}, source=source)
    message = str(excinfo.value)
    assert "fake" in message
    assert "nope" in message
    assert "gen_object_list" in message


def test_source_port_inside_emits_does_not_raise(tmp_path):
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="in", proto_type="test.A")])
    stages = [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"in": "source.gen_object_list"}}]
    path = _write_pipeline(tmp_path, stages)
    source = _FakeSource("fake", frozenset({"gen_object_list"}))

    Pipeline.load(path, components={"consumer": _stub("consumer", consumer)}, source=source)  # must not raise


def test_no_source_supplied_leaves_source_refs_unchecked(tmp_path):
    """Backward-compatible: every pre-S-C2 caller (`test_c1c_pipeline.py`)
    passes no `source=` and must keep loading unchanged."""
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="in", proto_type="test.A")])
    stages = [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"in": "source.anything"}}]
    path = _write_pipeline(tmp_path, stages)

    Pipeline.load(path, components={"consumer": _stub("consumer", consumer)})  # must not raise


# ---------------------------------------------------------------------------
# record: policy -- parsing, resolution, closed vocabulary (NR-SIM-42)
# ---------------------------------------------------------------------------


def test_record_policy_parses_full_excluded_and_decimate(tmp_path):
    producer = _manifest(component="producer", outputs=[
        PortSpec(name="camera_front", proto_type="test.A"), PortSpec(name="radar_cube", proto_type="test.A"),
    ])
    stages = [{
        "name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {},
        "record": {"*": "full", "camera_front": {"decimate": 10}, "radar_cube": "excluded"},
    }]
    path = _write_pipeline(tmp_path, stages)

    pipeline = Pipeline.load(path, components={"producer": _stub("producer", producer)})

    stage = pipeline.stages[0]
    assert record_policy_for(stage, "camera_front") == RecordPolicy(RecordVerb.DECIMATE, decimate_n=10)
    assert record_policy_for(stage, "radar_cube") == RecordPolicy(RecordVerb.EXCLUDED)
    assert record_policy_for(stage, "anything_else") == RecordPolicy(RecordVerb.FULL)  # via "*"


def test_record_absent_defaults_every_port_to_full(tmp_path):
    producer = _manifest(component="producer", outputs=[PortSpec(name="out", proto_type="test.A")])
    stages = [{"name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {}}]
    path = _write_pipeline(tmp_path, stages)

    pipeline = Pipeline.load(path, components={"producer": _stub("producer", producer)})

    assert record_policy_for(pipeline.stages[0], "out") == RecordPolicy(RecordVerb.FULL)


def test_record_policy_outside_the_closed_vocabulary_is_a_load_error(tmp_path):
    producer = _manifest(component="producer")
    stages = [{
        "name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {},
        "record": {"out": "sometimes"},
    }]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={"producer": _stub("producer", producer)})
    assert "sometimes" in str(excinfo.value)


def test_decimate_without_a_count_is_a_load_error(tmp_path):
    producer = _manifest(component="producer")
    stages = [{
        "name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {},
        "record": {"out": "decimate"},
    }]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(AuthoringError):
        Pipeline.load(path, components={"producer": _stub("producer", producer)})


def test_record_survives_a_with_mode_round_trip(tmp_path):
    producer = _manifest(component="producer", outputs=[PortSpec(name="out", proto_type="test.A")])
    stages = [{
        "name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {},
        "record": {"out": "excluded"},
    }]
    path = _write_pipeline(tmp_path, stages)
    pipeline = Pipeline.load(path, components={"producer": _stub("producer", producer)})

    toggled = pipeline.with_mode("producer", "measured", close_gaps=False)

    assert record_policy_for(toggled.stages[0], "out") == RecordPolicy(RecordVerb.EXCLUDED)


def test_to_yaml_round_trips_record_policy(tmp_path):
    producer = _manifest(component="producer", outputs=[PortSpec(name="camera_front", proto_type="test.A")])
    stages = [{
        "name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {},
        "record": {"camera_front": {"decimate": 10}},
    }]
    path = _write_pipeline(tmp_path, stages)
    pipeline = Pipeline.load(path, components={"producer": _stub("producer", producer)})

    reloaded_path = tmp_path / "roundtrip.yaml"
    reloaded_path.write_text(pipeline.to_yaml(), encoding="utf-8")
    reloaded = Pipeline.load(reloaded_path, components={"producer": _stub("producer", producer)})

    assert record_policy_for(reloaded.stages[0], "camera_front") == RecordPolicy(RecordVerb.DECIMATE, decimate_n=10)


# ---------------------------------------------------------------------------
# UT-C2-14 -- excluding/decimating an input a `simulate` stage consumes is a
# record-time load error naming the stage and the port; the same pipeline
# still loads fine for resim (Pipeline.load itself never raises this)
# ---------------------------------------------------------------------------


def test_validate_recordable_raises_when_a_simulate_stage_consumes_an_excluded_output(tmp_path):
    producer = _manifest(component="producer", outputs=[PortSpec(name="objects", proto_type="test.A")])
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="objects", proto_type="test.A")])
    stages = [
        {
            "name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {},
            "record": {"objects": "excluded"},
        },
        {"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"objects": "producer.objects"}},
    ]
    path = _write_pipeline(tmp_path, stages)
    pipeline = Pipeline.load(path, components={"producer": _stub("producer", producer), "consumer": _stub("consumer", consumer)})

    with pytest.raises(AuthoringError) as excinfo:
        validate_recordable(pipeline.stages, pipeline._components)
    message = str(excinfo.value)
    assert "producer" in message
    assert "objects" in message


def test_validate_recordable_allows_a_decimated_output_consumed_only_downstream_measured(tmp_path):
    """The recording-time check is about `mode: simulate` consumers only --
    a `measured` consumer reads the recording directly, so an excluded
    upstream port consumed only there is not this rule's business."""
    producer = _manifest(component="producer", outputs=[PortSpec(name="objects", proto_type="test.A")])
    consumer_manifest = _manifest(component="consumer", inputs=[PortSpec(name="objects", proto_type="test.A")])
    stages = [
        {
            "name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {},
            "record": {"objects": "excluded"},
        },
        {"name": "consumer", "mode": "measured", "impl": "stub:consumer", "inputs": {"objects": "producer.objects"}},
    ]
    path = _write_pipeline(tmp_path, stages)
    pipeline = Pipeline.load(
        path, components={"producer": _stub("producer", producer), "consumer": _stub("consumer", consumer_manifest)},
    )

    validate_recordable(pipeline.stages, pipeline._components)  # must not raise


def test_validate_recordable_ignores_source_fed_inputs(tmp_path):
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="objects", proto_type="test.A")])
    stages = [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"objects": "source.objects"}}]
    path = _write_pipeline(tmp_path, stages)
    pipeline = Pipeline.load(path, components={"consumer": _stub("consumer", consumer)})

    validate_recordable(pipeline.stages, pipeline._components)  # must not raise -- no producer stage to check
