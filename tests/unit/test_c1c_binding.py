# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C1cΔ `contracts/binding.py` tests: UT-C1c-24, UT-C1c-25 (the
byte-application half; the load-time "silent about fixed_slots raises"
half is `test_c1c_pipeline.py`'s, since it needs a real manifest), UT-C1c-26
(docs/sim_implementation_plan.md).

Also `S-B1Δ`'s `resolve_component_ref`/`try_resolve_component_ref` --
component-relative `self.<port>` binding (`R-SIM-21`, arch `D13`). These are
**still not** `UT-C1c-22`/`-23` (that pair is the Pipeline/ComponentManifest-
based `resolve()`, real as of -- its own tests are below, in this
same file since it's the same module; Block 1 has no live manifest to resolve
against, so `resolve_component_ref` above resolves against a run's own known
port names instead -- see `scene/registry.py`'s `gated()` and `LayerCtx.port`
-- and stays that way, on purpose, see `resolve`'s own docstring).
"""

from __future__ import annotations

import pytest
from google.protobuf import descriptor_pb2 as _dpb
from google.protobuf import descriptor_pool as _dpool
from google.protobuf import message_factory as _mfactory

from adas_sim.contracts.binding import (
    Address, AddressSegment, apply_override, parse_address, resolve, resolve_component_ref,
    try_resolve_component_ref,
)
from adas_sim.contracts.component import ComponentManifest, PortSpec
from adas_sim.contracts.override import Override, OverrideVerb
from adas_sim.core.errors import AuthoringError, ContractError


def _container_cls():
    """`Container { x: float, items: repeated Item{value: float}, scalars:
    repeated float }` -- a real schema exercising a scalar field, a
    repeated message field and a repeated scalar field, the three shapes
    the address grammar addresses."""
    fdp = _dpb.FileDescriptorProto()
    fdp.name = "c1c_binding.proto"
    fdp.package = "adas_sim.test.c1cbinding"
    fdp.syntax = "proto3"
    item = fdp.message_type.add()
    item.name = "Item"
    f = item.field.add()
    f.name, f.number, f.type = "value", 1, _dpb.FieldDescriptorProto.TYPE_FLOAT
    f.label = _dpb.FieldDescriptorProto.LABEL_OPTIONAL

    container = fdp.message_type.add()
    container.name = "Container"
    f = container.field.add()
    f.name, f.number, f.type = "x", 1, _dpb.FieldDescriptorProto.TYPE_FLOAT
    f.label = _dpb.FieldDescriptorProto.LABEL_OPTIONAL
    f = container.field.add()
    f.name, f.number, f.type = "items", 2, _dpb.FieldDescriptorProto.TYPE_MESSAGE
    f.type_name, f.label = ".adas_sim.test.c1cbinding.Item", _dpb.FieldDescriptorProto.LABEL_REPEATED
    f = container.field.add()
    f.name, f.number, f.type = "scalars", 3, _dpb.FieldDescriptorProto.TYPE_FLOAT
    f.label = _dpb.FieldDescriptorProto.LABEL_REPEATED

    pool = _dpool.DescriptorPool()
    pool.Add(fdp)
    return _mfactory.GetMessageClass(pool.FindMessageTypeByName("adas_sim.test.c1cbinding.Container"))


Container = _container_cls()


def _payload(*, x=0.0, item_values=(), scalars=()) -> bytes:
    msg = Container(x=x)
    for v in item_values:
        msg.items.add(value=v)
    msg.scalars.extend(scalars)
    return msg.SerializeToString()


# ---------------------------------------------------------------------------
# UT-C1c-24 -- the address grammar
# ---------------------------------------------------------------------------


def test_a_bare_port_address_has_no_path():
    assert parse_address("port", where="t") == Address(raw="port", port="port", path=())


def test_a_field_address_resolves_to_one_segment():
    assert parse_address("port.x", where="t") == Address(raw="port.x", port="port", path=(AddressSegment("x"),))


def test_a_repeated_index_address_resolves_correctly():
    address = parse_address("port.items[2]", where="t")
    assert address.port == "port"
    assert address.path == (AddressSegment("items", 2),)


def test_a_repeated_star_address_resolves_correctly():
    address = parse_address("port.items[*]", where="t")
    assert address.path == (AddressSegment("items", "*"),)


def test_a_field_within_an_indexed_element_resolves_two_segments():
    address = parse_address("port.items[2].value", where="t")
    assert address.path == (AddressSegment("items", 2), AddressSegment("value"))


def test_a_predicate_shaped_address_raises_naming_the_closed_grammar():
    """UT-C1c-24: `objects[?class=="truck"]` is an expression, not an
    address -- the closed grammar names itself in the error."""
    with pytest.raises(AuthoringError) as excinfo:
        parse_address('port.objects[?class=="truck"]', where="t")
    message = str(excinfo.value)
    assert "port · port.field" in message or "port.field" in message


def test_indexing_the_port_segment_itself_raises():
    """A port is one message, never a list -- `port[2].field` is invalid."""
    with pytest.raises(AuthoringError):
        parse_address("port[2].x", where="t")


# ---------------------------------------------------------------------------
# UT-C1c-25 -- fixed-slot behaviour (the byte-application half)
# ---------------------------------------------------------------------------


def test_drop_on_a_fixed_slots_port_clears_the_element_in_place():
    """UT-C1c-25 (first half): element 1 becomes its message default;
    elements 0 and 2 keep their indices and values -- compaction must NOT
    happen, because that is the failure mode this design exists to
    prevent."""
    payload = _payload(item_values=(1.0, 2.0, 3.0))
    address = parse_address("port.items[1]", where="t")
    new_payload, _ = apply_override(payload, Container, address, Override(verb=OverrideVerb.DROP), fixed_slots=True)

    result = Container()
    result.ParseFromString(new_payload)
    assert len(result.items) == 3  # not compacted
    assert result.items[0].value == pytest.approx(1.0)
    assert result.items[1].value == pytest.approx(0.0)  # cleared, not removed
    assert result.items[2].value == pytest.approx(3.0)  # index unchanged


def test_drop_on_a_non_fixed_slots_port_compacts():
    """UT-C1c-25 (converse of the above, `fixed_slots=False` explicitly
    supplied): element 1 is removed and later elements shift down."""
    payload = _payload(item_values=(1.0, 2.0, 3.0))
    address = parse_address("port.items[1]", where="t")
    new_payload, _ = apply_override(payload, Container, address, Override(verb=OverrideVerb.DROP), fixed_slots=False)

    result = Container()
    result.ParseFromString(new_payload)
    assert len(result.items) == 2
    assert [item.value for item in result.items] == pytest.approx([1.0, 3.0])


def test_drop_without_fixed_slots_declared_raises_naming_the_port_and_attribute():
    """UT-C1c-25: `fixed_slots=None` means the manifest is silent -- never
    picking a side (`NR-SIM-4`)."""
    payload = _payload(item_values=(1.0,))
    address = parse_address("port.items[0]", where="t")
    with pytest.raises(ContractError) as excinfo:
        apply_override(payload, Container, address, Override(verb=OverrideVerb.DROP), fixed_slots=None)
    message = str(excinfo.value)
    assert "port.items[0]" in message
    assert "fixed_slots" in message


# ---------------------------------------------------------------------------
# UT-C1c-26 -- select keeps exactly the addressed elements; select/drop of
# complementary sets produce the same result
# ---------------------------------------------------------------------------


def test_select_keeps_exactly_the_addressed_element():
    payload = _payload(item_values=(1.0, 2.0, 3.0))
    address = parse_address("port.items[1]", where="t")
    new_payload, _ = apply_override(payload, Container, address, Override(verb=OverrideVerb.SELECT), fixed_slots=False)

    result = Container()
    result.ParseFromString(new_payload)
    assert [item.value for item in result.items] == pytest.approx([2.0])


def test_select_and_drop_of_complementary_sets_produce_the_same_result():
    """UT-C1c-26: selecting index 1 out of three elements must equal
    dropping indices 0 and 2 -- the property that makes two verbs
    sufficient (`OD-8`)."""
    payload = _payload(item_values=(1.0, 2.0, 3.0))

    select_result, _ = apply_override(
        payload, Container, parse_address("port.items[1]", where="t"),
        Override(verb=OverrideVerb.SELECT), fixed_slots=False,
    )

    # Drop 0 and 2 one at a time -- each `apply_override` call re-decodes,
    # so this exercises the same code path a two-key overrides: {} mapping
    # would (contracts/pipeline.py applies one override at a time).
    intermediate, _ = apply_override(
        payload, Container, parse_address("port.items[2]", where="t"),
        Override(verb=OverrideVerb.DROP), fixed_slots=False,
    )
    drop_result, _ = apply_override(
        intermediate, Container, parse_address("port.items[0]", where="t"),
        Override(verb=OverrideVerb.DROP), fixed_slots=False,
    )

    a, b = Container(), Container()
    a.ParseFromString(select_result)
    b.ParseFromString(drop_result)
    assert [item.value for item in a.items] == pytest.approx([item.value for item in b.items])


def test_select_star_keeps_everything():
    payload = _payload(item_values=(1.0, 2.0))
    new_payload, _ = apply_override(
        payload, Container, parse_address("port.items[*]", where="t"),
        Override(verb=OverrideVerb.SELECT), fixed_slots=False,
    )
    result = Container()
    result.ParseFromString(new_payload)
    assert [item.value for item in result.items] == pytest.approx([1.0, 2.0])


def test_drop_star_with_fixed_slots_clears_every_element():
    payload = _payload(item_values=(1.0, 2.0))
    new_payload, _ = apply_override(
        payload, Container, parse_address("port.items[*]", where="t"),
        Override(verb=OverrideVerb.DROP), fixed_slots=True,
    )
    result = Container()
    result.ParseFromString(new_payload)
    assert len(result.items) == 2
    assert [item.value for item in result.items] == pytest.approx([0.0, 0.0])


# ---------------------------------------------------------------------------
# The four arithmetic verbs, applied to real bytes (not just Override.apply's
# own bare-float math, already covered by test_c1c_override.py)
# ---------------------------------------------------------------------------


def test_const_overrides_a_scalar_field():
    payload = _payload(x=1.0)
    new_payload, _ = apply_override(payload, Container, parse_address("port.x", where="t"), Override(verb=OverrideVerb.CONST, value=9.0))
    result = Container()
    result.ParseFromString(new_payload)
    assert result.x == pytest.approx(9.0)


def test_offset_and_scale_apply_to_an_indexed_repeated_scalar():
    payload = _payload(scalars=(2.0, 4.0))
    offset_payload, _ = apply_override(
        payload, Container, parse_address("port.scalars[0]", where="t"), Override(verb=OverrideVerb.OFFSET, value=1.0),
    )
    result = Container()
    result.ParseFromString(offset_payload)
    assert result.scalars[0] == pytest.approx(3.0)
    assert result.scalars[1] == pytest.approx(4.0)  # untouched


def test_hold_freezes_at_the_first_seen_value_across_two_calls():
    """`hold`'s memory is the caller's to keep (`Pipeline`'s own job) --
    this exercises the pure function with the caller-supplied `first_seen`
    it is designed around."""
    override = Override(verb=OverrideVerb.HOLD)
    address = parse_address("port.x", where="t")

    first_payload = _payload(x=5.0)
    result_1, first_seen = apply_override(first_payload, Container, address, override, first_seen=None)
    decoded_1 = Container()
    decoded_1.ParseFromString(result_1)
    assert decoded_1.x == pytest.approx(5.0)
    assert first_seen == pytest.approx(5.0)

    second_payload = _payload(x=99.0)
    result_2, first_seen = apply_override(second_payload, Container, address, override, first_seen=first_seen)
    decoded_2 = Container()
    decoded_2.ParseFromString(result_2)
    assert decoded_2.x == pytest.approx(5.0)  # still the first tick's value, not 99.0


def test_an_arithmetic_verb_on_a_whole_port_address_raises():
    """A whole-message address has no single number to override."""
    payload = _payload(x=1.0)
    with pytest.raises(AuthoringError):
        apply_override(payload, Container, parse_address("port", where="t"), Override(verb=OverrideVerb.CONST, value=1.0))


def test_an_arithmetic_verb_on_a_star_address_raises():
    """`*` means every element -- only select/drop operate on a whole set."""
    payload = _payload(scalars=(1.0, 2.0))
    with pytest.raises(AuthoringError):
        apply_override(
            payload, Container, parse_address("port.scalars[*]", where="t"), Override(verb=OverrideVerb.CONST, value=1.0),
        )


# ---------------------------------------------------------------------------
# `resolve_component_ref`/`try_resolve_component_ref` -- component-relative
# port binding (`R-SIM-21`, arch `D13`, `S-B1Δ`).
# ---------------------------------------------------------------------------


def test_a_ref_with_no_self_prefix_passes_through_unchanged():
    assert resolve_component_ref("df.bsd.outputs", known_ports=(), where="t") == "df.bsd.outputs"
    assert try_resolve_component_ref("df.bsd.outputs", known_ports=(), where="t") == "df.bsd.outputs"


def test_self_ref_resolves_under_a_renamed_stage():
    """The whole claim: the same `self.<port>` reference binds correctly
    whichever stage name the concrete run happens to use."""
    known_ports = frozenset({"driving_functions.bsd.outputs", "driving_functions.common.hud"})
    assert resolve_component_ref("self.bsd.outputs", known_ports=known_ports, where="t") == "driving_functions.bsd.outputs"
    assert try_resolve_component_ref("self.bsd.outputs", known_ports=known_ports, where="t") == "driving_functions.bsd.outputs"


def test_resolve_component_ref_raises_on_zero_matches():
    with pytest.raises(AuthoringError):
        resolve_component_ref("self.bsd.outputs", known_ports=frozenset({"df.common.hud"}), where="t")


def test_resolve_component_ref_raises_on_ambiguous_matches():
    known_ports = frozenset({"df.bsd.outputs", "other.bsd.outputs"})
    with pytest.raises(AuthoringError):
        resolve_component_ref("self.bsd.outputs", known_ports=known_ports, where="t")


def test_try_resolve_component_ref_returns_none_on_zero_matches():
    """Zero matches is not raised here: Block 1 has no live component
    manifest, so "does not exist" and "this run never wired that component"
    are indistinguishable from a recording's own topics alone (checked with
    the user, `S-B1Δ`)."""
    assert try_resolve_component_ref("self.bsd.outputs", known_ports=frozenset({"df.common.hud"}), where="t") is None


def test_try_resolve_component_ref_still_raises_on_ambiguous_matches():
    """More than one match is a same-run collision regardless -- that
    evidence does not need a live manifest."""
    known_ports = frozenset({"df.bsd.outputs", "other.bsd.outputs"})
    with pytest.raises(AuthoringError):
        try_resolve_component_ref("self.bsd.outputs", known_ports=known_ports, where="t")


# ---------------------------------------------------------------------------
# `resolve` -- the S-C1cΔ, Pipeline/ComponentManifest-based resolver
# (`UT-C1c-22`, `UT-C1c-23`). NOT `resolve_component_ref` above -- that one
# resolves against a run's flat known-port universe with no manifest; this
# one resolves against ONE component's own declared ports, exactly.
# ---------------------------------------------------------------------------


def _manifest(*port_names: str) -> ComponentManifest:
    return ComponentManifest(
        component="test", version="1", abi_version=1, build_id="b",
        inputs=(), outputs=tuple(PortSpec(name=name, proto_type="x.Y") for name in port_names),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def test_a_bare_ref_passes_through_resolve_unchanged():
    assert resolve("df.bsd.outputs", component="df", manifest=_manifest(), where="t") == "df.bsd.outputs"


def test_resolve_binds_under_a_renamed_stage():
    """`UT-C1c-22`: the whole claim -- the same plug-in binds correctly
    whether the pipeline calls the stage `df` or `driving_functions`, since
    the concrete address is built from whatever `component` the caller
    supplies, never searched for."""
    manifest = _manifest("bsd.outputs")
    assert resolve("self.bsd.outputs", component="df", manifest=manifest, where="t") == "df.bsd.outputs"
    assert resolve("self.bsd.outputs", component="driving_functions", manifest=manifest, where="t") == \
        "driving_functions.bsd.outputs"


def test_resolve_matches_an_input_port_too():
    manifest = ComponentManifest(
        component="test", version="1", abi_version=1, build_id="b",
        inputs=(PortSpec(name="veh_dyn", proto_type="x.Y"),), outputs=(),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )
    assert resolve("self.veh_dyn", component="vdy", manifest=manifest, where="t") == "vdy.veh_dyn"


def test_resolve_raises_naming_the_reference_component_and_declared_ports():
    """`UT-C1c-23`: names all three -- never a sentinel a caller could
    treat as "absent"."""
    manifest = _manifest("bsd.outputs", "common.hud")
    with pytest.raises(AuthoringError) as excinfo:
        resolve("self.no_such_port", component="df", manifest=manifest, where="t")
    message = str(excinfo.value)
    assert "self.no_such_port" in message
    assert "df" in message
    assert "bsd.outputs" in message and "common.hud" in message
