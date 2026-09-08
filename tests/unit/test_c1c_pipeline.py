# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C1c pipeline tests: UT-C1c-6, UT-C1c-7, UT-C1c-8, UT-C1c-9, UT-C1c-10,
UT-C1c-11, UT-C1c-12, UT-C1c-13, UT-C1c-14, UT-C1c-16, UT-C1c-17 (the
pipeline-wiring half; `override.py`'s own semantics are
`test_c1c_override.py`'s), UT-C1c-18, UT-C1c-19, UT-C1c-20, UT-C1c-21,
ST-C1c-2 (docs/sim_implementation_plan.md).

Every fixture here is a synthetic, invented component ("producer",
"widget", ...) driven through `InProcessSilComponent` and injected via
`Pipeline.load`'s `components=` -- pure Python, no DLL, no `interfaces`
checkout, and no real function name anywhere (`R-SIM-1`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from google.protobuf import descriptor_pb2 as _dpb
from google.protobuf import descriptor_pool as _dpool
from google.protobuf import message_factory as _mfactory

from adas_sim.graph import pipeline as pipeline_mod
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.config.fault import Fault, FaultVerb
from adas_sim.config.override import Override, OverrideVerb
from adas_sim.graph.pipeline import Pipeline
from adas_sim.diagnostics.errors import AuthoringError, ContractError, InternalError, ProvenanceWarning
from adas_sim.diagnostics.tap import Tap


def _manifest(
    *, component: str, inputs=(), outputs=(), period_ns: int = 0, descriptor_set: bytes = b"", project: str = "base",
) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs),
        project=project, config_bundle_sha256="", descriptor_set=descriptor_set, period_ns=period_ns,
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


# ---------------------------------------------------------------------------
# UT-C1c-20 -- rate: base grid is the GCD of declared periods; each stage
# executes only on its due ticks; a non-multiple period is a load error
# ---------------------------------------------------------------------------


def test_base_grid_is_the_gcd_of_declared_periods(tmp_path):
    """UT-C1c-20."""
    a = _manifest(component="a", period_ns=20_000_000)
    b = _manifest(component="b", period_ns=50_000_000)
    stages = [
        {"name": "a", "mode": "simulate", "impl": "stub:a", "inputs": {}},
        {"name": "b", "mode": "simulate", "impl": "stub:b", "inputs": {}},
    ]
    path = _write_pipeline(tmp_path, stages)

    pipeline = Pipeline.load(path, components={"a": _stub("a", a), "b": _stub("b", b)})

    assert pipeline.base_grid_ns == 10_000_000


def test_each_stage_executes_only_on_its_due_ticks(tmp_path):
    """UT-C1c-20."""
    a_manifest = _manifest(component="a", outputs=[PortSpec(name="out", proto_type="test.A")], period_ns=20_000_000)
    b_manifest = _manifest(component="b", outputs=[PortSpec(name="out", proto_type="test.A")], period_ns=50_000_000)
    stages = [
        {"name": "a", "mode": "simulate", "impl": "stub:a", "inputs": {}},
        {"name": "b", "mode": "simulate", "impl": "stub:b", "inputs": {}},
    ]
    path = _write_pipeline(tmp_path, stages)

    a_calls: list[int] = []
    b_calls: list[int] = []

    def _a_fn(dt_ns, inputs):
        a_calls.append(dt_ns)
        return {"out": b"a"}

    def _b_fn(dt_ns, inputs):
        b_calls.append(dt_ns)
        return {"out": b"b"}

    a_comp = InProcessSilComponent("a", a_manifest, _a_fn)
    a_comp.init()
    b_comp = InProcessSilComponent("b", b_manifest, _b_fn)
    b_comp.init()
    pipeline = Pipeline.load(path, components={"a": a_comp, "b": b_comp})

    for _ in range(5):  # 5 * 10ms base-grid steps = 50ms elapsed
        pipeline.step(10_000_000, {})

    assert len(a_calls) == 2  # due at 20ms, 40ms
    assert len(b_calls) == 1  # due at 50ms


def test_require_multiple_rejects_a_period_that_is_not_a_multiple_of_the_grid():
    """UT-C1c-20, the validator tested directly. A base grid genuinely
    derived as the GCD of a period set can never actually fail this check
    against any period in that same set (GCD divides every member of the
    set it came from, by definition) -- there is no way to construct a
    *reachable* failure through `Pipeline.load` today. The guard is tested
    here instead, against numbers that do not come from a real GCD, because
    `R-SIM-18` states the invariant explicitly and a future way of supplying
    periods could make it reachable; recording that it is unreachable today
    is the honest alternative to deleting a check the rule requires."""
    with pytest.raises(AuthoringError) as excinfo:
        pipeline_mod._require_multiple(25_000_000, 10_000_000, stage_name="a")
    message = str(excinfo.value)
    assert "25000000" in message
    assert "10000000" in message


# ---------------------------------------------------------------------------
# UT-C1c-21 -- a held port reads updated=False with an exact age_s, and the
# consumer still receives its full port set
# ---------------------------------------------------------------------------


def test_held_port_reads_updated_false_with_exact_age_s_and_the_full_port_set(tmp_path):
    """UT-C1c-21."""
    a_manifest = _manifest(component="a", outputs=[PortSpec(name="out", proto_type="test.A")], period_ns=50_000_000)
    stages = [{"name": "a", "mode": "simulate", "impl": "stub:a", "inputs": {}}]
    path = _write_pipeline(tmp_path, stages)

    a_comp = InProcessSilComponent("a", a_manifest, lambda dt_ns, inputs: {"out": b"fresh"})
    a_comp.init()
    pipeline = Pipeline.load(path, components={"a": a_comp})

    not_yet = pipeline.step(10_000_000, {})  # elapsed=10ms, not due (period 50ms), never produced
    assert not_yet["a.out"].valid is False

    fresh = pipeline.step(40_000_000, {})  # elapsed=50ms, due
    assert fresh["a.out"].updated is True
    assert fresh["a.out"].age_s == 0.0
    assert fresh["a.out"].message == b"fresh"

    held = pipeline.step(10_000_000, {})  # elapsed=60ms, not due -- held
    assert "a.out" in held  # full port set: still present even though not due
    assert held["a.out"].updated is False
    assert held["a.out"].age_s == pytest.approx(0.01)  # 60ms - 50ms
    assert held["a.out"].message == b"fresh"  # the held value, not empty


# ---------------------------------------------------------------------------
# S-C1cΔ -- overrides are applied on the input path (UT-C1c-24..26 cover the
# grammar/application logic itself in test_c1c_binding.py; these are the
# Pipeline-integration half, plus UT-C1c-25's "manifest silent about
# fixed_slots" load-time check, only reachable through a real PortSpec).
# ---------------------------------------------------------------------------


def _scalar_message_cls():
    """A real `Scalar { x: float }` schema -- what an override's arithmetic
    verb actually decodes and re-encodes on a stage's own input port."""
    fdp = _dpb.FileDescriptorProto()
    fdp.name = "c1c_pipeline_scalar.proto"
    fdp.package = "adas_sim.test.c1cpipeline"
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
    cls = _mfactory.GetMessageClass(pool.FindMessageTypeByName("adas_sim.test.c1cpipeline.Scalar"))
    return cls, fds.SerializeToString()


def test_a_const_override_is_actually_applied_before_the_stage_sees_it(tmp_path):
    """S-C1cΔ: the input path, not just load-time declaration -- the
    algorithm receives the overridden value, never the original."""
    scalar_cls, descriptor_set = _scalar_message_cls()
    consumer = _manifest(
        component="consumer", inputs=[PortSpec(name="egoDyn", proto_type="adas_sim.test.c1cpipeline.Scalar")],
        descriptor_set=descriptor_set,
    )
    stages = [
        {
            "name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"egoDyn": "source.veh_dyn"},
            "overrides": {"egoDyn.x": {"verb": "const", "value": 42.0}},
        },
    ]
    path = _write_pipeline(tmp_path, stages)

    seen: list[float] = []

    def _algorithm(dt_ns, inputs):
        received = scalar_cls()
        received.ParseFromString(inputs["egoDyn"])
        seen.append(received.x)
        return {}

    component = InProcessSilComponent("consumer", consumer, _algorithm)
    component.init()
    pipeline = Pipeline.load(path, components={"consumer": component})

    stimulus_msg = scalar_cls(x=1.0)
    pipeline.exec(50_000_000, {"veh_dyn": stimulus_msg.SerializeToString()})

    assert seen == [42.0]  # never 1.0 -- the override, not the stimulus


def test_hold_override_freezes_at_the_first_ticks_value_across_two_execs(tmp_path):
    """S-C1cΔ: `hold`'s cross-tick memory is the Pipeline's own job
    (`contracts/binding.apply_override` stays pure)."""
    scalar_cls, descriptor_set = _scalar_message_cls()
    consumer = _manifest(
        component="consumer", inputs=[PortSpec(name="egoDyn", proto_type="adas_sim.test.c1cpipeline.Scalar")],
        descriptor_set=descriptor_set,
    )
    stages = [
        {
            "name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"egoDyn": "source.veh_dyn"},
            "overrides": {"egoDyn.x": {"verb": "hold"}},
        },
    ]
    path = _write_pipeline(tmp_path, stages)

    seen: list[float] = []

    def _algorithm(dt_ns, inputs):
        received = scalar_cls()
        received.ParseFromString(inputs["egoDyn"])
        seen.append(received.x)
        return {}

    component = InProcessSilComponent("consumer", consumer, _algorithm)
    component.init()
    pipeline = Pipeline.load(path, components={"consumer": component})

    pipeline.exec(50_000_000, {"veh_dyn": scalar_cls(x=5.0).SerializeToString()})
    pipeline.exec(50_000_000, {"veh_dyn": scalar_cls(x=99.0).SerializeToString()})

    assert seen == [5.0, 5.0]  # frozen at the first tick's value, never 99.0


def test_an_override_addressing_an_undeclared_port_raises_at_load(tmp_path):
    """`_validate_overrides`: an override must address one of the stage's
    own declared input ports."""
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="egoDyn", proto_type="test.A")])
    stages = [
        {
            "name": "consumer", "mode": "simulate", "impl": "stub:consumer",
            "inputs": {"egoDyn": "source.veh_dyn"},
            "overrides": {"noSuchPort": {"verb": "hold"}},
        },
    ]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={"consumer": _stub("consumer", consumer)})
    message = str(excinfo.value)
    assert "noSuchPort" in message
    assert "egoDyn" in message


def test_drop_on_a_port_silent_about_fixed_slots_raises_at_load_naming_port_and_field(tmp_path):
    """UT-C1c-25 (second half, through a REAL `PortSpec` -- which carries
    no `fixed_slots` field until `S-C1aΔ2`/`S-C1d`): this is the only
    reachable path today, and it is the honest state, not a gap."""
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="objects", proto_type="test.Objects")])
    stages = [
        {
            "name": "consumer", "mode": "simulate", "impl": "stub:consumer",
            "inputs": {"objects": "source.objects"},
            "overrides": {"objects.items[0]": {"verb": "drop"}},
        },
    ]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(ContractError) as excinfo:
        Pipeline.load(path, components={"consumer": _stub("consumer", consumer)})
    message = str(excinfo.value)
    assert "objects" in message
    assert "fixed_slots" in message


def test_an_override_entry_with_an_extra_key_is_refused_naming_the_alternative(tmp_path):
    """S-C1cΔ: `at_tick:`/`condition:`/anything beyond `verb:`/`value:` is
    exactly the shape someone reaches for to make an override time-varying
    or conditional -- refused, pointing at the two real alternatives."""
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="egoDyn", proto_type="test.A")])
    stages = [
        {
            "name": "consumer", "mode": "simulate", "impl": "stub:consumer",
            "inputs": {"egoDyn": "source.veh_dyn"},
            "overrides": {"egoDyn": {"verb": "const", "value": 1.0, "at_tick": 50}},
        },
    ]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={"consumer": _stub("consumer", consumer)})
    message = str(excinfo.value)
    assert "at_tick" in message
    assert "scenario" in message and "stub" in message


def test_an_override_with_a_non_numeric_value_is_refused_naming_the_alternative(tmp_path):
    """S-C1cΔ: a `value:` that is not a plain number (a dict, attempting a
    conditional shape) is refused the same way, not accepted and left to
    fail confusingly at apply time."""
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="egoDyn", proto_type="test.A")])
    stages = [
        {
            "name": "consumer", "mode": "simulate", "impl": "stub:consumer",
            "inputs": {"egoDyn": "source.veh_dyn"},
            "overrides": {"egoDyn": {"verb": "const", "value": {"if": "x > 1", "then": 5}}},
        },
    ]
    path = _write_pipeline(tmp_path, stages)

    with pytest.raises(AuthoringError) as excinfo:
        Pipeline.load(path, components={"consumer": _stub("consumer", consumer)})
    message = str(excinfo.value)
    assert "scenario" in message and "stub" in message


# ---------------------------------------------------------------------------
# S-C3 -- Pipeline.init_components/shutdown_components (a real dll:/stubdll:
# stage needs .init() called before exec(); every earlier test injects a
# pre-initialised InProcessSilComponent via _stub() and so never exercised
# this -- core.resim.resim_pipeline/check.runner.check_scenario both call it
# now for a real component to work at all).
# ---------------------------------------------------------------------------


def test_init_components_activates_every_stage_before_exec(tmp_path):
    manifest = _manifest(component="widget", outputs=[PortSpec(name="out", proto_type="test.A")])
    component = InProcessSilComponent("widget", manifest, lambda dt_ns, inputs: {"out": b"x"})
    stages = [{"name": "widget", "mode": "simulate", "impl": "stub:widget", "inputs": {}}]
    path = _write_pipeline(tmp_path, stages)
    pipeline = Pipeline.load(path, components={"widget": component})

    with pytest.raises(InternalError):
        pipeline.exec(50_000_000, {})  # not yet init()'d

    pipeline.init_components()
    assert pipeline.exec(50_000_000, {})["widget"]["out"] == b"x"


def test_shutdown_components_deactivates_every_stage(tmp_path):
    manifest = _manifest(component="widget", outputs=[PortSpec(name="out", proto_type="test.A")])
    component = InProcessSilComponent("widget", manifest, lambda dt_ns, inputs: {"out": b"x"})
    stages = [{"name": "widget", "mode": "simulate", "impl": "stub:widget", "inputs": {}}]
    path = _write_pipeline(tmp_path, stages)
    pipeline = Pipeline.load(path, components={"widget": component})

    pipeline.init_components()
    pipeline.exec(50_000_000, {})  # proves init worked
    pipeline.shutdown_components()

    with pytest.raises(InternalError):
        pipeline.exec(50_000_000, {})


# ---------------------------------------------------------------------------
# S-C3 -- `run.faults:` (`contracts/fault.py`) actually applied to the
# STIMULUS by `Pipeline.exec`/`step`, not merely declared (SS9.2). `drop`/
# `corrupt` are pure bytes; `stale`/`invalidate`/`delay` are only observable
# through the `InputMeta` a consuming stage's `exec()` receives -- inspected
# via `InProcessSilComponent.last_input_meta` (real `valid`/`ageS` reaching
# `CtypesSilComponent`'s ABI struct is `test_c1c_component.py`'s own test).
# ---------------------------------------------------------------------------


def test_drop_fault_removes_the_stimulus_port_before_the_stage_sees_it(tmp_path):
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="egoDyn", proto_type="test.A")])
    stages = [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"egoDyn": "source.veh_dyn"}}]
    path = _write_pipeline(tmp_path, stages)

    seen: list[bool] = []

    def _algorithm(dt_ns, inputs):
        seen.append("egoDyn" in inputs)
        return {}

    component = InProcessSilComponent("consumer", consumer, _algorithm)
    component.init()
    fault = Fault(verb=FaultVerb.DROP, address="veh_dyn", from_s=0.0, to_s=10.0)
    pipeline = Pipeline.load(path, components={"consumer": component}, faults=[fault])

    pipeline.exec(50_000_000, {"veh_dyn": b"whatever"})

    assert seen == [False]  # absent, not merely empty bytes -- R-SIM's own convention


def test_corrupt_fault_mutates_stimulus_bytes_before_the_stage_sees_it(tmp_path):
    scalar_cls, descriptor_set = _scalar_message_cls()
    consumer = _manifest(
        component="consumer", inputs=[PortSpec(name="egoDyn", proto_type="adas_sim.test.c1cpipeline.Scalar")],
        descriptor_set=descriptor_set,
    )
    stages = [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"egoDyn": "source.veh_dyn"}}]
    path = _write_pipeline(tmp_path, stages)

    seen: list[float] = []

    def _algorithm(dt_ns, inputs):
        received = scalar_cls()
        received.ParseFromString(inputs["egoDyn"])
        seen.append(received.x)
        return {}

    component = InProcessSilComponent("consumer", consumer, _algorithm)
    component.init()
    # message_cls for the STIMULUS port "veh_dyn" is resolved by finding
    # this same stage's own wiring to it (`_message_cls_for_source_port`)
    # -- the stimulus itself carries no schema of its own.
    fault = Fault(verb=FaultVerb.CORRUPT, address="veh_dyn.x", value=42.0, from_s=0.0, to_s=10.0)
    pipeline = Pipeline.load(path, components={"consumer": component}, faults=[fault])

    pipeline.exec(50_000_000, {"veh_dyn": scalar_cls(x=1.0).SerializeToString()})

    assert seen == [42.0]  # never 1.0


def test_stale_fault_grows_age_s_in_input_meta_across_execs(tmp_path):
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="egoDyn", proto_type="test.A")])
    stages = [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"egoDyn": "source.veh_dyn"}}]
    path = _write_pipeline(tmp_path, stages)

    component = InProcessSilComponent("consumer", consumer, lambda dt_ns, inputs: {})
    component.init()
    fault = Fault(verb=FaultVerb.STALE, address="veh_dyn", from_s=0.0, to_s=10.0)
    pipeline = Pipeline.load(path, components={"consumer": component}, faults=[fault])

    pipeline.exec(50_000_000, {"veh_dyn": b"x"})
    first = component.last_input_meta["egoDyn"]
    pipeline.exec(50_000_000, {"veh_dyn": b"x"})
    second = component.last_input_meta["egoDyn"]

    assert first.valid is True
    assert first.age_s == pytest.approx(0.0)  # just went stale
    assert second.age_s == pytest.approx(0.05)  # a full tick stale now


def test_invalidate_fault_marks_input_meta_invalid_but_keeps_the_bytes(tmp_path):
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="egoDyn", proto_type="test.A")])
    stages = [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"egoDyn": "source.veh_dyn"}}]
    path = _write_pipeline(tmp_path, stages)

    seen: list[bytes] = []

    def _algorithm(dt_ns, inputs):
        seen.append(inputs["egoDyn"])
        return {}

    component = InProcessSilComponent("consumer", consumer, _algorithm)
    component.init()
    fault = Fault(verb=FaultVerb.INVALIDATE, address="veh_dyn", from_s=0.0, to_s=10.0)
    pipeline = Pipeline.load(path, components={"consumer": component}, faults=[fault])

    pipeline.exec(50_000_000, {"veh_dyn": b"still-here"})

    assert seen == [b"still-here"]  # bytes survive, unlike drop
    assert component.last_input_meta["egoDyn"].valid is False


def test_delay_fault_sets_a_constant_age_s_offset(tmp_path):
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="egoDyn", proto_type="test.A")])
    stages = [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"egoDyn": "source.veh_dyn"}}]
    path = _write_pipeline(tmp_path, stages)

    component = InProcessSilComponent("consumer", consumer, lambda dt_ns, inputs: {})
    component.init()
    fault = Fault(verb=FaultVerb.DELAY, address="veh_dyn", value=0.2, from_s=0.0, to_s=10.0)
    pipeline = Pipeline.load(path, components={"consumer": component}, faults=[fault])

    pipeline.exec(50_000_000, {"veh_dyn": b"x"})

    meta = component.last_input_meta["egoDyn"]
    assert meta.valid is True
    assert meta.age_s == pytest.approx(0.2)


def test_a_fault_outside_its_window_leaves_stimulus_and_input_meta_untouched(tmp_path):
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="egoDyn", proto_type="test.A")])
    stages = [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"egoDyn": "source.veh_dyn"}}]
    path = _write_pipeline(tmp_path, stages)

    component = InProcessSilComponent("consumer", consumer, lambda dt_ns, inputs: {})
    component.init()
    fault = Fault(verb=FaultVerb.DROP, address="veh_dyn", from_s=5.0, to_s=6.0)
    pipeline = Pipeline.load(path, components={"consumer": component}, faults=[fault])

    pipeline.exec(50_000_000, {"veh_dyn": b"x"})  # t_s == 0.05, well outside [5.0, 6.0]

    assert component.last_input_meta == {}  # the documented default -- fresh and valid, no entry needed


def test_step_propagates_a_held_producers_staleness_into_a_downstream_input_meta(tmp_path):
    """The `R-SIM-18` gap this pass closes: a half-rate producer's held
    output used to reach `SilComponent.exec` as `valid=1, ageS=0.0`
    regardless of true staleness -- indistinguishable from fresh. Now a
    downstream stage's own `input_meta` carries the real elapsed time since
    the producer last actually ran."""
    producer_manifest = _manifest(
        component="producer", outputs=[PortSpec(name="out", proto_type="test.A")], period_ns=20_000_000,
    )
    consumer_manifest = _manifest(
        component="consumer", inputs=[PortSpec(name="in", proto_type="test.A")], period_ns=10_000_000,
    )
    stages = [
        {"name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {}},
        {"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {"in": "producer.out"}},
    ]
    path = _write_pipeline(tmp_path, stages)

    producer = InProcessSilComponent("producer", producer_manifest, lambda dt_ns, inputs: {"out": b"p"})
    producer.init()
    consumer = InProcessSilComponent("consumer", consumer_manifest, lambda dt_ns, inputs: {})
    consumer.init()
    pipeline = Pipeline.load(path, components={"producer": producer, "consumer": consumer})

    pipeline.step(10_000_000, {})  # t=10ms: producer not yet due -- nothing produced yet
    pipeline.step(10_000_000, {})  # t=20ms: producer due, fresh
    fresh_meta = consumer.last_input_meta["in"]
    pipeline.step(10_000_000, {})  # t=30ms: producer held -- one base-grid tick stale
    held_meta = consumer.last_input_meta["in"]

    assert fresh_meta.valid is True
    assert fresh_meta.age_s == pytest.approx(0.0)
    assert held_meta.valid is True
    assert held_meta.age_s == pytest.approx(0.01)


def test_schedule_disagreement_detected_when_a_due_port_is_not_actually_updated(tmp_path):
    """`R-SIM-18`'s closing line ("the DLL's own updated flag is
    authoritative ... a disagreement is reported, never hidden"): the
    port's own declared `period_us` predicts due on every tick here (it
    equals the base grid); the stand-in's second call withholds the port
    anyway (simulating a real ABI reporting `updated=0`), which `step()`
    must surface rather than silently treat as an ordinary held value."""
    calls = {"n": 0}

    def fn(dt_ns, inputs):
        calls["n"] += 1
        return {} if calls["n"] == 2 else {"out": b"x"}

    manifest = _manifest(
        component="stage", outputs=[PortSpec(name="out", proto_type="test.A", period_us=50_000)],
        period_ns=50_000_000,
    )
    stages = [{"name": "stage", "mode": "simulate", "impl": "stub:stage", "inputs": {}}]
    path = _write_pipeline(tmp_path, stages)
    component = InProcessSilComponent("stage", manifest, fn)
    component.init()
    pipeline = Pipeline.load(path, components={"stage": component})

    with pytest.warns(ProvenanceWarning, match="stage 'stage' port 'out'"):
        pipeline.step(50_000_000, {})
        pipeline.step(50_000_000, {})

    disagreements = pipeline.schedule_disagreements
    assert len(disagreements) == 1
    d = disagreements[0]
    assert (d.stage, d.port, d.predicted_due, d.actual_updated) == ("stage", "out", True, False)
    assert d.tick_index == 1  # 0-indexed: the second step() call


def test_no_schedule_disagreement_when_the_actual_flag_agrees_with_the_declared_period(tmp_path):
    manifest = _manifest(
        component="stage", outputs=[PortSpec(name="out", proto_type="test.A", period_us=50_000)],
        period_ns=50_000_000,
    )
    stages = [{"name": "stage", "mode": "simulate", "impl": "stub:stage", "inputs": {}}]
    path = _write_pipeline(tmp_path, stages)
    component = InProcessSilComponent("stage", manifest, lambda dt_ns, inputs: {"out": b"x"})
    component.init()
    pipeline = Pipeline.load(path, components={"stage": component})

    pipeline.step(50_000_000, {})
    pipeline.step(50_000_000, {})

    assert pipeline.schedule_disagreements == ()


def test_schedule_disagreement_never_checked_for_an_undeclared_port_period(tmp_path):
    """`period_us == 0` is "undeclared," not "always due at the fastest
    possible rate" -- an undeclared port can never disagree, the same
    convention `PortSpec.period_us`'s own docstring already states for
    `ComponentManifest.period_ns`."""
    manifest = _manifest(component="stage", outputs=[PortSpec(name="out", proto_type="test.A")])
    stages = [{"name": "stage", "mode": "simulate", "impl": "stub:stage", "inputs": {}}]
    path = _write_pipeline(tmp_path, stages)
    component = InProcessSilComponent("stage", manifest, lambda dt_ns, inputs: {})  # never returns "out"
    component.init()
    pipeline = Pipeline.load(path, components={"stage": component})

    pipeline.step(50_000_000, {})

    assert pipeline.schedule_disagreements == ()


def test_schedule_disagreement_not_checked_for_a_measured_stage(tmp_path):
    """A `measured` stage injects fixture data -- there is no real ABI
    `exec()` call at all for it to disagree with (`_check_schedule_
    disagreements` is only ever called from the live-`exec()` branch)."""
    manifest = _manifest(component="stage", outputs=[PortSpec(name="out", proto_type="test.A", period_us=50_000)])
    stages = [{"name": "stage", "mode": "measured", "impl": "stub:stage", "inputs": {}}]
    path = _write_pipeline(tmp_path, stages)
    component = InProcessSilComponent("stage", manifest, lambda dt_ns, inputs: {"out": b"x"})
    component.init()
    pipeline = Pipeline.load(path, components={"stage": component})

    pipeline.step(50_000_000, {}, measured={"stage": {}})  # withheld -- would disagree if checked at all

    assert pipeline.schedule_disagreements == ()


# ---------------------------------------------------------------------------
# OD-11 -- cross-component project/ego-parameter agreement
# (sim_sil_contract.md SS9.1, sim_implementation_plan.md S-C5 Milestone 2)
# ---------------------------------------------------------------------------


class _FakeComponentForAgreement:
    """Just enough of `SilComponent` for `_validate_cross_component_agreement`
    -- it reads only `.manifest.project`, never execs."""

    def __init__(self, project: str) -> None:
        self.manifest = _manifest(component="fake", project=project)


def _bundle_dir(tmp_path: Path, name: str, *, ego: dict | None = None) -> Path:
    bundle_dir = tmp_path / name
    (bundle_dir / "vehicle").mkdir(parents=True)
    (bundle_dir / "vehicle" / "ego_params.yaml").write_text(
        yaml.safe_dump(ego if ego is not None else {"EGO_WHEELBASE_M": 2.7}), encoding="utf-8",
    )
    return bundle_dir


def test_fewer_than_two_known_bundles_is_a_no_op(tmp_path):
    bundle_dirs = {"a": _bundle_dir(tmp_path, "a"), "b": None}
    components = {"a": _FakeComponentForAgreement("base"), "b": _FakeComponentForAgreement("base")}
    mixed = pipeline_mod._validate_cross_component_agreement(bundle_dirs, components, allow_mixed_projects=False)
    assert mixed is False


def test_agreeing_bundles_across_two_stages_pass_silently(tmp_path):
    bundle_dirs = {
        "a": _bundle_dir(tmp_path, "a", ego={"EGO_WHEELBASE_M": 2.7}),
        "b": _bundle_dir(tmp_path, "b", ego={"EGO_WHEELBASE_M": 2.7}),
    }
    components = {"a": _FakeComponentForAgreement("base"), "b": _FakeComponentForAgreement("base")}
    mixed = pipeline_mod._validate_cross_component_agreement(bundle_dirs, components, allow_mixed_projects=False)
    assert mixed is False


def test_project_mismatch_warns_by_default_and_is_suppressed_by_the_escape(tmp_path):
    bundle_dirs = {
        "a": _bundle_dir(tmp_path, "a", ego={"EGO_WHEELBASE_M": 2.7}),
        "b": _bundle_dir(tmp_path, "b", ego={"EGO_WHEELBASE_M": 2.7}),
    }
    components = {"a": _FakeComponentForAgreement("base"), "b": _FakeComponentForAgreement("cus1")}

    with pytest.warns(pipeline_mod.ProvenanceWarning):
        mixed = pipeline_mod._validate_cross_component_agreement(bundle_dirs, components, allow_mixed_projects=False)
    assert mixed is True

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning raised here fails the test
        mixed = pipeline_mod._validate_cross_component_agreement(bundle_dirs, components, allow_mixed_projects=True)
    assert mixed is True  # still reports the mismatch was found, just doesn't warn about it


def test_ego_parameter_mismatch_is_a_hard_error_naming_both_components_and_the_key(tmp_path):
    bundle_dirs = {
        "a": _bundle_dir(tmp_path, "a", ego={"EGO_WHEELBASE_M": 2.7}),
        "b": _bundle_dir(tmp_path, "b", ego={"EGO_WHEELBASE_M": 2.9}),
    }
    components = {"a": _FakeComponentForAgreement("base"), "b": _FakeComponentForAgreement("base")}

    with pytest.raises(AuthoringError) as excinfo:
        pipeline_mod._validate_cross_component_agreement(bundle_dirs, components, allow_mixed_projects=False)

    message = str(excinfo.value)
    assert "EGO_WHEELBASE_M" in message
    assert "'a'" in message and "'b'" in message


def test_ego_parameter_mismatch_is_not_suppressed_by_allow_mixed_projects(tmp_path):
    """`UT-C5-10`: the escape widens the project-name warning only. An escape
    hatch that also swallowed the ego hard error would make two components
    silently disagree about the wheelbase -- a wrong result AND a wrong
    picture, with no legitimate reading (`OD-11`)."""
    bundle_dirs = {
        "a": _bundle_dir(tmp_path, "a", ego={"EGO_WHEELBASE_M": 2.7}),
        "b": _bundle_dir(tmp_path, "b", ego={"EGO_WHEELBASE_M": 2.9}),
    }
    components = {"a": _FakeComponentForAgreement("base"), "b": _FakeComponentForAgreement("cus1")}

    with pytest.raises(AuthoringError) as excinfo:
        pipeline_mod._validate_cross_component_agreement(bundle_dirs, components, allow_mixed_projects=True)
    assert "EGO_WHEELBASE_M" in str(excinfo.value)


def test_pipeline_load_parses_allow_mixed_projects_and_exposes_mixed_projects(tmp_path):
    """The pipeline-file-level wiring: `allow_mixed_projects:` is read at
    `Pipeline.load` and both facts end up on the loaded `Pipeline` (`OD-11`,
    for `core.manifest.build_manifest` to record)."""
    consumer = _manifest(component="consumer")
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        yaml.safe_dump({
            "name": "test", "version": 1, "allow_mixed_projects": True,
            "stages": [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {}}],
        }),
        encoding="utf-8",
    )

    pipeline = Pipeline.load(path, components={"consumer": _stub("consumer", consumer)})

    assert pipeline.allow_mixed_projects is True
    assert pipeline.mixed_projects is False  # only one real bundle dir known (none, here) -- nothing to compare


def test_pipeline_load_parses_and_validates_taps(tmp_path):
    """`IMP-0285`: `taps:` is validated at LOAD (same discipline every other
    `raw` field on `Pipeline.load` already follows), exposed on the loaded
    `Pipeline`, and round-trips through `to_yaml`."""
    producer = _manifest(component="producer", outputs=[PortSpec(name="debug", proto_type="test.Debug")])
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        yaml.safe_dump({
            "name": "test", "version": 1, "taps": {"producer": ["debug"]},
            "stages": [{"name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {}}],
        }),
        encoding="utf-8",
    )

    pipeline = Pipeline.load(path, components={"producer": _stub("producer", producer)})

    assert pipeline.taps == (Tap(stage="producer", port="debug"),)
    assert "taps:" in pipeline.to_yaml()
    assert yaml.safe_load(pipeline.to_yaml())["taps"] == {"producer": ["debug"]}


def test_pipeline_load_refuses_a_tap_naming_an_unknown_port(tmp_path):
    producer = _manifest(component="producer", outputs=[PortSpec(name="debug", proto_type="test.Debug")])
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        yaml.safe_dump({
            "name": "test", "version": 1, "taps": {"producer": ["no_such_port"]},
            "stages": [{"name": "producer", "mode": "simulate", "impl": "stub:producer", "inputs": {}}],
        }),
        encoding="utf-8",
    )

    with pytest.raises(AuthoringError, match="no_such_port"):
        Pipeline.load(path, components={"producer": _stub("producer", producer)})


def test_pipeline_load_refuses_a_tap_naming_an_input_port(tmp_path):
    """`IMP-0285`'s own consumer-side scope limit: `Pipeline.step()` returns
    no value for an input port (this class's own `step()` docstring), so a
    tap naming one would resolve cleanly and then record nothing -- refused
    here instead, at load, rather than left as a silent gap (`R-SIM-25`).
    `tap.py::resolve_taps` itself is unchanged -- still allows either kind,
    per its own docstring; this is `Pipeline.load`'s own restriction."""
    consumer = _manifest(component="consumer", inputs=[PortSpec(name="egoDyn", proto_type="test.VehDyn")])
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        yaml.safe_dump({
            "name": "test", "version": 1, "taps": {"consumer": ["egoDyn"]},
            "stages": [{"name": "consumer", "mode": "simulate", "impl": "stub:consumer", "inputs": {}}],
        }),
        encoding="utf-8",
    )

    with pytest.raises(AuthoringError, match="input"):
        Pipeline.load(path, components={"consumer": _stub("consumer", consumer)})
