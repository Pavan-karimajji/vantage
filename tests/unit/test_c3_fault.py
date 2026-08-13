# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C3 fault vocabulary tests (docs/sim_implementation_plan.md UT-C3-8):
each of the five faults produces its stated effect on `PortValue`
metadata, not only on bytes. `corrupt`'s payload case reuses
`test_c1c_pipeline.py`'s own `_scalar_message_cls` pattern -- a real
`Scalar { x: float }` schema, no function name anywhere (`R-SIM-1`).
"""

from __future__ import annotations

import pytest
from google.protobuf import descriptor_pb2 as _dpb
from google.protobuf import descriptor_pool as _dpool
from google.protobuf import message_factory as _mfactory

from adas_sim.config.fault import Fault, FaultVerb, apply_fault, parse_fault, parse_fault_verb
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.session.tick import PortValue


def _scalar_message_cls():
    fdp = _dpb.FileDescriptorProto()
    fdp.name = "c3_fault_scalar.proto"
    fdp.package = "adas_sim.test.c3fault"
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
    cls = _mfactory.GetMessageClass(pool.FindMessageTypeByName("adas_sim.test.c3fault.Scalar"))
    return cls, fds.SerializeToString()


# ---------------------------------------------------------------------------
# parse_fault_verb / Fault -- the closed list, and the window discipline
# ---------------------------------------------------------------------------


def test_parse_fault_verb_accepts_every_closed_member():
    for verb in FaultVerb:
        assert parse_fault_verb(verb.value, where="test") == verb


def test_a_sixth_fault_name_is_a_schema_error():
    with pytest.raises(AuthoringError, match="drop"):
        parse_fault_verb("reorder", where="test")


@pytest.mark.parametrize("verb", [FaultVerb.CORRUPT, FaultVerb.DELAY])
def test_a_value_requiring_verb_without_a_value_raises(verb):
    with pytest.raises(AuthoringError):
        Fault(verb=verb, address="widget.outputs.x", from_s=0.0, to_s=1.0)


@pytest.mark.parametrize("verb", [FaultVerb.DROP, FaultVerb.STALE, FaultVerb.INVALIDATE])
def test_a_no_value_verb_needs_no_value(verb):
    Fault(verb=verb, address="widget.outputs.x", from_s=0.0, to_s=1.0)  # must not raise


def test_neither_window_form_raises():
    with pytest.raises(AuthoringError, match="window"):
        Fault(verb=FaultVerb.DROP, address="widget.outputs.x")


def test_both_window_forms_raises():
    with pytest.raises(AuthoringError, match="window"):
        Fault(verb=FaultVerb.DROP, address="widget.outputs.x", from_s=0.0, to_s=1.0, after_tick=5)


def test_from_s_without_to_s_raises():
    with pytest.raises(AuthoringError, match="from_s"):
        Fault(verb=FaultVerb.DROP, address="widget.outputs.x", from_s=0.0)


def test_active_at_honours_from_s_to_s_window():
    fault = Fault(verb=FaultVerb.DROP, address="widget.outputs.x", from_s=2.0, to_s=4.0)
    assert fault.active_at(t_s=1.0, tick_index=0) is False
    assert fault.active_at(t_s=3.0, tick_index=0) is True
    assert fault.active_at(t_s=5.0, tick_index=0) is False


def test_active_at_honours_after_tick_window():
    fault = Fault(verb=FaultVerb.DROP, address="widget.outputs.x", after_tick=10)
    assert fault.active_at(t_s=0.0, tick_index=9) is False
    assert fault.active_at(t_s=0.0, tick_index=10) is True


def test_parse_fault_rejects_an_unknown_key():
    with pytest.raises(AuthoringError, match="also has"):
        parse_fault({"verb": "drop", "address": "widget.outputs.x", "from_s": 0.0, "to_s": 1.0, "bogus": 1}, where="t")


def test_parse_fault_round_trips_a_corrupt_entry():
    fault = parse_fault(
        {"verb": "corrupt", "address": "widget.outputs.x", "value": 99.0, "after_tick": 3}, where="t",
    )
    assert fault == Fault(verb=FaultVerb.CORRUPT, address="widget.outputs.x", value=99.0, after_tick=3)


# ---------------------------------------------------------------------------
# apply_fault -- each verb's stated PortValue-metadata effect (UT-C3-8)
# ---------------------------------------------------------------------------


def _port_value(*, t_ns: int, valid: bool = True, updated: bool = True, message=b"payload") -> PortValue:
    return PortValue(name="widget.outputs", origin="simulated", message=message, valid=valid, updated=updated, t_ns=t_ns)


def test_fault_not_active_outside_its_window_returns_the_value_unchanged():
    port_value = _port_value(t_ns=0)
    fault = Fault(verb=FaultVerb.DROP, address="widget.outputs", from_s=5.0, to_s=6.0)
    result, first_active = apply_fault(port_value, fault, t_s=0.0, tick_index=0)
    assert result is port_value
    assert first_active is None


def test_drop_yields_invalid_with_no_message():
    port_value = _port_value(t_ns=100)
    fault = Fault(verb=FaultVerb.DROP, address="widget.outputs", from_s=0.0, to_s=1.0)
    result, _ = apply_fault(port_value, fault, t_s=0.5, tick_index=0)
    assert result.valid is False
    assert result.message is None


def test_stale_yields_updated_false_with_growing_age_s():
    fault = Fault(verb=FaultVerb.STALE, address="widget.outputs", from_s=0.0, to_s=10.0)
    tick1 = _port_value(t_ns=1_000_000_000)
    result1, first_active = apply_fault(tick1, fault, t_s=1.0, tick_index=1)
    assert result1.updated is False
    assert result1.age_s == pytest.approx(0.0)  # just went stale -- no time has passed yet

    tick2 = _port_value(t_ns=2_000_000_000)
    result2, _ = apply_fault(tick2, fault, t_s=2.0, tick_index=2, first_active_t_s=first_active)
    assert result2.updated is False
    assert result2.age_s == pytest.approx(1.0)  # a full second stale now -- age_s grew


def test_delay_yields_a_capture_stamp_earlier_than_reception():
    fault = Fault(verb=FaultVerb.DELAY, address="widget.outputs", value=0.2, from_s=0.0, to_s=10.0)
    port_value = _port_value(t_ns=5_000_000_000)
    result, _ = apply_fault(port_value, fault, t_s=5.0, tick_index=5)
    assert result.capture_ns == 5_000_000_000 - 200_000_000
    assert result.age_s == pytest.approx(0.2)


def test_invalidate_yields_invalid_with_bytes_still_present():
    port_value = _port_value(t_ns=0, message=b"still-here")
    fault = Fault(verb=FaultVerb.INVALIDATE, address="widget.outputs", from_s=0.0, to_s=1.0)
    result, _ = apply_fault(port_value, fault, t_s=0.5, tick_index=0)
    assert result.valid is False
    assert result.message == b"still-here"


def test_corrupt_mutates_the_payload_and_stays_valid():
    scalar_cls, _descriptor_set = _scalar_message_cls()
    original = scalar_cls(x=1.0).SerializeToString()
    port_value = _port_value(t_ns=0, message=original)
    fault = Fault(verb=FaultVerb.CORRUPT, address="outputs.x", value=42.0, from_s=0.0, to_s=1.0)

    result, _ = apply_fault(port_value, fault, t_s=0.5, tick_index=0, message_cls=scalar_cls)

    assert result.valid is True
    decoded = scalar_cls()
    decoded.ParseFromString(result.raw_bytes)
    assert decoded.x == 42.0


def test_corrupt_without_message_cls_raises():
    port_value = _port_value(t_ns=0, message=b"x")
    fault = Fault(verb=FaultVerb.CORRUPT, address="outputs.x", value=1.0, from_s=0.0, to_s=1.0)
    with pytest.raises(AuthoringError, match="message_cls"):
        apply_fault(port_value, fault, t_s=0.5, tick_index=0)
