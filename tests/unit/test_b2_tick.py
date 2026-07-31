# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B2Δ `core/tick.py` tests: UT-B2-13, UT-B2-14
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

import pytest
from google.protobuf import descriptor_pb2 as _dpb
from google.protobuf.message import DecodeError

from adas_sim.core.runner import build_session_from_recording
from adas_sim.core.tick import PortValue
from adas_sim.io.base import Provenance, RunManifest, TopicInfo
from adas_sim.io.mcap import McapWriter


def test_age_s_is_capture_derived_when_capture_ns_is_known():
    """UT-B2-13."""
    pv = PortValue(name="p", message=b"x", origin="measured", capture_ns=80_000_000, t_ns=100_000_000)
    assert pv.age_s == pytest.approx(0.02)


def test_age_s_is_hold_derived_when_capture_is_unknown():
    """UT-B2-13: `hold_age_s` is `contracts/pipeline.Pipeline.step()`'s own
    schedule-tracked age (`R-SIM-18`) -- a live SIL stage has no capture
    stamp to derive from at all."""
    pv = PortValue(name="p", message=b"x", origin="simulated", hold_age_s=0.05)
    assert pv.age_s == pytest.approx(0.05)


def test_age_s_defaults_to_zero_with_neither_clock():
    pv = PortValue(name="p", message=b"x", origin="measured")
    assert pv.age_s == 0.0


def test_capture_derived_and_hold_derived_ages_are_distinguishable_even_when_equal():
    """UT-B2-13's core claim: two `PortValue`s can report the identical
    `age_s` float yet differ in *why* it is old -- `capture_ns` states
    which clock produced it, so the two are never confused as `age_s`
    alone would leave them (`OD-9`)."""
    capture_derived = PortValue(name="a", message=b"x", origin="measured", capture_ns=0, t_ns=50_000_000)
    hold_derived = PortValue(name="b", message=b"x", origin="simulated", hold_age_s=0.05)
    assert capture_derived.age_s == pytest.approx(0.05)
    assert hold_derived.age_s == pytest.approx(0.05)
    assert capture_derived.capture_ns is not None
    assert hold_derived.capture_ns is None


def _tiny_schema() -> tuple[str, bytes]:
    """A minimal real `Tiny { x: int32 }` schema, the same technique
    `core/tick.decode_message` itself resolves against (R-SIM-11)."""
    fdp = _dpb.FileDescriptorProto()
    fdp.name = "b2tick_tiny.proto"
    fdp.package = "adas_sim.test.b2tick"
    fdp.syntax = "proto3"
    msg = fdp.message_type.add()
    msg.name = "Tiny"
    f = msg.field.add()
    f.name, f.number, f.type = "x", 1, _dpb.FieldDescriptorProto.TYPE_INT32
    f.label = _dpb.FieldDescriptorProto.LABEL_OPTIONAL

    fds = _dpb.FileDescriptorSet()
    fds.file.append(fdp)
    return "adas_sim.test.b2tick.Tiny", fds.SerializeToString()


def test_the_resim_path_parses_nothing_until_message_is_read(tmp_path):
    """UT-B2-14: a port carrying a deliberately un-parseable payload builds
    into a `Session` without raising -- nothing is parsed at build time
    (`OD-13`). Reading that one port's `.message` then raises, which is the
    only way "parsing is deferred" is actually observable rather than just
    asserted.
    """
    schema_name, schema_bytes = _tiny_schema()
    topics = {
        "/df/outer": TopicInfo(schema_name=schema_name, provenance=Provenance.SIMULATED, schema_bytes=schema_bytes),
    }
    path = tmp_path / "unparseable.mcap"
    writer = McapWriter()
    writer.open(path, RunManifest(), topics)
    writer.write("/df/outer", 0, b"\xff\xff\xff\xff\xff")  # not valid protobuf for this schema
    writer.close()

    session = build_session_from_recording(path)  # must not raise: nothing was parsed
    assert len(session) == 1

    with pytest.raises(DecodeError):
        session.at(0).port("df.outer").message  # only now does the parse actually happen
