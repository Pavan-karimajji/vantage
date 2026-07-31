# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C1c pipeline tests: UT-C1c-6, UT-C1c-7, UT-C1c-8, UT-C1c-9, UT-C1c-10,
UT-C1c-11, UT-C1c-12, UT-C1c-13, UT-C1c-14, UT-C1c-16, UT-C1c-17 (the
pipeline-wiring half; `override.py`'s own semantics are
`test_c1c_override.py`'s), UT-C1c-18, UT-C1c-19, ST-C1c-2
(docs/sim_implementation_plan.md).

Every fixture here is a synthetic, invented component ("producer",
"widget", ...) driven through `InProcessSilComponent` and injected via
`Pipeline.load`'s `components=` -- pure Python, no DLL, no `interfaces`
checkout, and no real function name anywhere (`R-SIM-1`).

Multi-rate scheduling (`period_ns`/GCD due-tick gating, held-port `age_s`)
and `contracts/override.py` are later slices' scope -- `Pipeline.exec` here
is single-rate: every stage runs every call.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.contracts.override import Override, OverrideVerb
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.errors import AuthoringError


def _manifest(*, component: str, inputs=(), outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _stub(name: str, manifest: ComponentManifest) -> InProcessSilComponent:
    """Pre-initialised: harmless for the load-only tests (`Pipeline.load`
    never touches a component's handle) and required for the `.exec()`
    tests (`SilComponent.exec` raises if `init()` was never called)."""
    component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
    component.init()
    return component


def _write_pipeline(tmp_path: Path, stages: list[dict], *, version: int | None = 1, filename: str = "pipeline.yaml") -> Path:
    data: dict[str, object] = {"name": "test", "stages": stages}
    if version is not None:
        data["version"] = version
    path = tmp_path / filename
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


class _FakeRecording:
    """Just enough of `io.base.RecordingReader` for `Pipeline.load`'s
    `mode: measured` topic check (`.topics()` only)."""

    def __init__(self, topic_names: list[str]) -> None:
        self._topics = dict.fromkeys(topic_names)

    def topics(self):
        return self._topics


# ---------------------------------------------------------------------------
# UT-C1c-6 -- proto_type mismatch raises naming both ends
# ---------------------------------------------------------------------------


def test_port_type_mismatch_raises_naming_both_ends(tmp_path):
    producer = _manifest(component="producer", outputs=[PortSpec(name="out", proto_type="test.A")])
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="in", proto_type="test.B")])
    stages = [
        {"name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {}},
        {"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"in": "producer.out"}},
    ]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={"producer": _stub("producer", producer), "consumer": _stub("consumer", consumer)})

    message = str(excinfo.value)
    assert "test.A" in message
    assert "test.B" in message


# ---------------------------------------------------------------------------
# UT-C1c-7 -- missing required input raises naming the port
# ---------------------------------------------------------------------------


def test_missing_required_input_raises_naming_the_port(tmp_path):
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="widget_in", proto_type="test.A", optional=False)])
    path = _write_pipeline(tmp_path, [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {}}])

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={"consumer": _stub("consumer", consumer)})

    assert "widget_in" in str(excinfo.value)


def test_missing_optional_input_does_not_raise(tmp_path):
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="widget_in", proto_type="test.A", optional=True)])
    path = _write_pipeline(tmp_path, [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {}}])

    Pipeline.load(path, components={"consumer": _stub("consumer", consumer)})  # must not raise


# ---------------------------------------------------------------------------
# UT-C1c-8 -- a reference to a port nobody produces raises
# ---------------------------------------------------------------------------


def test_reference_to_an_undeclared_stage_raises(tmp_path):
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="in", proto_type="test.A")])
    stages = [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"in": "nobody.out"}}]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={"consumer": _stub("consumer", consumer)})
    assert "nobody" in str(excinfo.value)


def test_reference_to_a_port_the_named_stage_does_not_produce_raises(tmp_path):
    producer = _manifest(component="producer", outputs=[PortSpec(name="out", proto_type="test.A")])
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="in", proto_type="test.A")])
    stages = [
        {"name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {}},
        {"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"in": "producer.nonexistent"}},
    ]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={"producer": _stub("producer", producer), "consumer": _stub("consumer", consumer)})
    assert "nonexistent" in str(excinfo.value)


# ---------------------------------------------------------------------------
# UT-C1c-9 -- a forward reference raises; no silent last-tick value
# ---------------------------------------------------------------------------


def test_a_stage_consuming_its_own_output_raises(tmp_path):
    manifest = _manifest(
        component="solo", inputs=[PortSpec(name="in", proto_type="test.A")], outputs=[PortSpec(name="out", proto_type="test.A")],
    )
    stages = [{"name": "solo", "mode": "simulate", "impl": "stub:solo", "inputs": {"in": "solo.out"}}]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(AuthoringError):
        Pipeline.load(path, components={"solo": _stub("solo", manifest)})


# ---------------------------------------------------------------------------
# UT-C1c-10 -- mode: measured against a recording lacking the topics raises
# ---------------------------------------------------------------------------


def test_measured_stage_missing_from_the_recording_raises_naming_missing_topics(tmp_path):
    producer = _manifest(component="producer", outputs=[PortSpec(name="out", proto_type="test.A")])
    stages = [{"name": "producer", "mode": "measured", "impl": "stub:producer", "inputs": {}}]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={"producer": _stub("producer", producer)}, recording=_FakeRecording([]))
    assert "out" in str(excinfo.value)


def test_measured_stage_present_in_the_recording_does_not_raise(tmp_path):
    producer = _manifest(component="producer", outputs=[PortSpec(name="out", proto_type="test.A")])
    stages = [{"name": "producer", "mode": "measured", "impl": "stub:producer", "inputs": {}}]
    path = _write_pipeline(tmp_path, stages)

    Pipeline.load(path, components={"producer": _stub("producer", producer)}, recording=_FakeRecording(["out"]))


# ---------------------------------------------------------------------------
# UT-C1c-13 -- flipping mode does not require impl: to change
# ---------------------------------------------------------------------------


def test_with_mode_preserves_impl_and_inputs(tmp_path):
    manifest = _manifest(component="solo")
    path = _write_pipeline(tmp_path, [{"name": "solo", "mode": "simulate", "impl": "stub:solo", "inputs": {}}])
    pipeline = Pipeline.load(path, components={"solo": _stub("solo", manifest)})

    measured = pipeline.with_mode("solo", "measured")
    assert measured.stages[0].mode == "measured"
    assert measured.stages[0].impl == "stub:solo"

    back = measured.with_mode("solo", "simulate")
    assert back.stages[0].mode == "simulate"
    assert back.stages[0].impl == "stub:solo"
    # the caller's original object is untouched -- undoable (R-SIM-17-style)
    assert pipeline.stages[0].mode == "simulate"


# ---------------------------------------------------------------------------
# UT-C1c-14 (load-time half) -- declaration order contradicting wiring is a
# load error
# ---------------------------------------------------------------------------


def test_a_stage_wired_to_a_later_stages_output_is_a_load_error(tmp_path):
    a_manifest = _manifest(component="a", inputs=[PortSpec(name="in", proto_type="test.A")])
    b_manifest = _manifest(component="b", outputs=[PortSpec(name="out", proto_type="test.A")])
    stages = [
        {"name": "a", "mode": "simulate", "impl": "stub:a", "inputs": {"in": "b.out"}},
        {"name": "b", "mode": "simulate", "impl": "stub:b", "inputs": {}},
    ]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={"a": _stub("a", a_manifest), "b": _stub("b", b_manifest)})
    message = str(excinfo.value)
    assert "a" in message and "b" in message


# ---------------------------------------------------------------------------
# UT-C1c-16 -- severed chain detected; off -> measured -> simulate is not
# ---------------------------------------------------------------------------


def _severed_chain_stages(upstream_mode: str) -> list[dict]:
    return [
        {"name": "upstream", "mode": upstream_mode, "impl": "stub:upstream", "inputs": {}},
        {"name": "measured", "mode": "measured", "impl": "stub:measured", "inputs": {"in": "upstream.out"}},
        {"name": "downstream", "mode": "simulate", "impl": "stub:downstream", "inputs": {"in": "measured.out"}},
    ]


def _severed_chain_components() -> dict:
    upstream = _manifest(component="upstream", outputs=[PortSpec(name="out", proto_type="test.A")])
    measured = _manifest(
        component="measured", inputs=[PortSpec(name="in", proto_type="test.A")], outputs=[PortSpec(name="out", proto_type="test.B")],
    )
    downstream = _manifest(component="downstream", inputs=[PortSpec(name="in", proto_type="test.B")])
    return {"upstream": _stub("upstream", upstream), "measured": _stub("measured", measured), "downstream": _stub("downstream", downstream)}


def test_simulate_measured_simulate_is_a_severed_chain(tmp_path):
    path = _write_pipeline(tmp_path, _severed_chain_stages("simulate"))
    pipeline = Pipeline.load(path, components=_severed_chain_components())

    chains = pipeline.severed_chains()

    assert len(chains) == 1
    assert chains[0].upstream == "upstream"
    assert chains[0].measured == "measured"
    assert chains[0].downstream == "downstream"


def test_off_measured_simulate_is_not_flagged(tmp_path):
    path = _write_pipeline(tmp_path, _severed_chain_stages("off"))
    pipeline = Pipeline.load(path, components=_severed_chain_components())

    assert pipeline.severed_chains() == ()


# ---------------------------------------------------------------------------
# UT-C1c-18 -- version: newer than the reader is a load error naming both
# ---------------------------------------------------------------------------


def test_a_pipeline_version_newer_than_the_reader_raises_naming_both(tmp_path):
    path = _write_pipeline(tmp_path, [], version=999)

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={})
    message = str(excinfo.value)
    assert "999" in message
    assert str(1) in message


# ---------------------------------------------------------------------------
# UT-C1c-19 -- an unversioned pipeline file is read as v1
# ---------------------------------------------------------------------------


def test_an_unversioned_pipeline_file_is_read_as_v1(tmp_path):
    path = _write_pipeline(tmp_path, [], version=None)
    assert "version" not in path.read_text(encoding="utf-8")

    pipeline = Pipeline.load(path, components={})

    assert pipeline.version == 1


# ---------------------------------------------------------------------------
# UT-C1c-11 -- mode: measured ignores that stage's inputs and injects
# recorded outputs
# ---------------------------------------------------------------------------


def test_measured_stage_ignores_its_inputs_and_injects_recorded_outputs(tmp_path):
    """UT-C1c-11."""
    producer = _manifest(component="producer", outputs=[PortSpec(name="out", proto_type="test.A")])
    measured_manifest = _manifest(
        component="measured", inputs=[PortSpec(name="in", proto_type="test.A")], outputs=[PortSpec(name="out", proto_type="test.B")],
    )
    stages = [
        {"name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {}},
        {"name": "measured", "mode": "measured", "impl": "stub:measured", "inputs": {"in": "producer.out"}},
    ]
    path = _write_pipeline(tmp_path, stages)

    def _never(dt_ns, inputs):
        raise AssertionError("a measured stage must never execute")

    measured_comp = InProcessSilComponent("measured", measured_manifest, _never)
    measured_comp.init()
    pipeline = Pipeline.load(path, components={"producer": _stub("producer", producer), "measured": measured_comp})

    result = pipeline.exec(50_000_000, {}, measured={"measured": {"out": b"recorded-bytes"}})

    assert result["measured"] == {"out": b"recorded-bytes"}


# ---------------------------------------------------------------------------
# UT-C1c-12 -- mode: off yields valid == 0 downstream
# ---------------------------------------------------------------------------


def test_off_stage_is_absent_from_the_result_and_from_a_consumers_inputs(tmp_path):
    """UT-C1c-12: `off` -> `valid=0` downstream, via the same "absent port"
    convention `SilComponent` already uses -- no special-casing needed in
    `Pipeline.exec` itself."""
    producer = _manifest(component="producer", outputs=[PortSpec(name="out", proto_type="test.A")])
    consumer_manifest = _manifest(component="consumer", inputs=[PortSpec(name="in", proto_type="test.A", optional=True)])
    stages = [
        {"name": "producer", "mode": "off", "impl": "stub:producer", "inputs": {}},
        {"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"in": "producer.out"}},
    ]
    path = _write_pipeline(tmp_path, stages)

    seen_inputs: dict[str, bytes] = {}

    def _consumer_fn(dt_ns, inputs):
        seen_inputs.update(inputs)
        return {}

    consumer_comp = InProcessSilComponent("consumer", consumer_manifest, _consumer_fn)
    consumer_comp.init()
    pipeline = Pipeline.load(path, components={"producer": _stub("producer", producer), "consumer": consumer_comp})

    result = pipeline.exec(50_000_000, {})

    assert "producer" not in result
    assert "in" not in seen_inputs


# ---------------------------------------------------------------------------
# UT-C1c-14 (runtime half) -- stages execute in declaration order,
# single-threaded
# ---------------------------------------------------------------------------


def test_stages_execute_in_declaration_order(tmp_path):
    """UT-C1c-14 (runtime half)."""
    a_manifest = _manifest(component="a", outputs=[PortSpec(name="out", proto_type="test.A")])
    b_manifest = _manifest(component="b", outputs=[PortSpec(name="out", proto_type="test.A")])
    stages = [
        {"name": "a", "mode": "simulate", "impl": "stub:a", "inputs": {}},
        {"name": "b", "mode": "simulate", "impl": "stub:b", "inputs": {}},
    ]
    path = _write_pipeline(tmp_path, stages)

    order: list[str] = []

    def _mark(name: str):
        def _fn(dt_ns, inputs):
            order.append(name)
            return {}
        return _fn

    a_comp = InProcessSilComponent("a", a_manifest, _mark("a"))
    a_comp.init()
    b_comp = InProcessSilComponent("b", b_manifest, _mark("b"))
    b_comp.init()
    pipeline = Pipeline.load(path, components={"a": a_comp, "b": b_comp})

    pipeline.exec(50_000_000, {})

    assert order == ["a", "b"]


# ---------------------------------------------------------------------------
# ST-C1c-2 -- an algo-test pipeline runs with everything measured except one
# stage, the canonical shape of R-SIM-12
# ---------------------------------------------------------------------------


def test_algo_test_pipeline_runs_with_everything_measured_except_one_stage(tmp_path):
    """ST-C1c-2."""
    upstream_manifest = _manifest(component="upstream", outputs=[PortSpec(name="objects", proto_type="test.Objects")])
    under_test_manifest = _manifest(
        component="under_test",
        inputs=[PortSpec(name="objects", proto_type="test.Objects")],
        outputs=[PortSpec(name="verdict", proto_type="test.Verdict")],
    )
    stages = [
        {"name": "upstream", "mode": "measured", "impl": "stub:upstream", "inputs": {}},
        {"name": "under_test", "mode": "simulate", "impl": "stub:under_test", "inputs": {"objects": "upstream.objects"}},
    ]
    path = _write_pipeline(tmp_path, stages)

    def _algorithm(dt_ns, inputs):
        assert inputs["objects"] == b"three-objects"
        return {"verdict": b"brake"}

    under_test_comp = InProcessSilComponent("under_test", under_test_manifest, _algorithm)
    under_test_comp.init()
    pipeline = Pipeline.load(
        path, components={"upstream": _stub("upstream", upstream_manifest), "under_test": under_test_comp},
    )

    result = pipeline.exec(50_000_000, {}, measured={"upstream": {"objects": b"three-objects"}})

    assert result["under_test"] == {"verdict": b"brake"}


# ---------------------------------------------------------------------------
# UT-C1c-17 (pipeline-wiring half) -- an override applies at a port and at a
# field path; a verb outside the closed four is a load error
# ---------------------------------------------------------------------------


def test_stage_overrides_accepts_a_bare_port_key_and_a_field_path_key(tmp_path):
    """UT-C1c-17."""
    manifest = _manifest(component="solo", inputs=[PortSpec(name="egoDyn", proto_type="test.VehDyn")])
    stages = [
        {
            "name": "solo", "mode": "simulate", "impl": "stub:solo", "inputs": {"egoDyn": "source.veh_dyn"},
            "overrides": {
                "egoDyn": {"verb": "hold"},
                "egoDyn.vx": {"verb": "const", "value": 10.0},
            },
        },
    ]
    path = _write_pipeline(tmp_path, stages)

    pipeline = Pipeline.load(path, components={"solo": _stub("solo", manifest)})

    overrides = pipeline.stages[0].overrides
    assert overrides["egoDyn"] == Override(verb=OverrideVerb.HOLD)
    assert overrides["egoDyn.vx"] == Override(verb=OverrideVerb.CONST, value=10.0)


def test_an_override_verb_outside_the_closed_four_is_a_load_error(tmp_path):
    """UT-C1c-17."""
    manifest = _manifest(component="solo")
    stages = [
        {
            "name": "solo", "mode": "simulate", "impl": "stub:solo", "inputs": {},
            "overrides": {"whatever": {"verb": "interpolate"}},
        },
    ]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={"solo": _stub("solo", manifest)})
    assert "interpolate" in str(excinfo.value)
