# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A4 `io/mcap.py` tests: UT-A4-1, UT-A4-2, UT-A4-3, UT-A4-4, UT-A4-6,
UT-A4-8, UT-A4-9, UT-A4-12, UT-A4-13, UT-A4-14 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

import pytest
from mcap.writer import Writer as RawMcapWriter

from adas_sim.io.base import (
    CAPTURE_TIME_MANIFEST_VERSION,
    ComponentBuildInfo,
    Provenance,
    RunManifest,
    TopicInfo,
    group_by_log_time,
)
from adas_sim.io.mcap import CAPABILITIES, McapReader, McapWriter

_TOPICS = {
    "/source/veh_dyn": TopicInfo(schema_name="adas_sim.test.VehDyn", provenance=Provenance.MEASURED),
    "/df/aeb.outputs": TopicInfo(schema_name="adas_sim.test.AebOutputs", provenance=Provenance.SIMULATED),
}


def _write_sample(path, *, manifest=None, config_bundle_bytes=b"", messages=None):
    writer = McapWriter()
    writer.open(path, manifest or RunManifest(), _TOPICS, config_bundle_bytes=config_bundle_bytes)
    for topic, t_ns, payload in (messages or []):
        writer.write(topic, t_ns, payload)
    writer.close()


def test_write_then_read_back_identical_topic_log_time_bytes(tmp_path):
    """UT-A4-1. `manifest_version` defaults to 0 (no manifest) here, so
    `capture_time_ns` reads back `None` (S-A4Δ) -- unrelated to this test's
    own subject, topic/log_time/bytes identity."""
    path = tmp_path / "sample.mcap"
    written = [
        ("/source/veh_dyn", 0, b"\x01\x02"),
        ("/df/aeb.outputs", 0, b"\x03"),
        ("/source/veh_dyn", 50_000_000, b"\x04\x05"),
    ]
    expected = [(topic, t_ns, None, payload) for topic, t_ns, payload in written]
    _write_sample(path, messages=written)

    reader = McapReader(path)
    actual = list(reader.messages())
    reader.close()
    assert actual == expected


def test_topics_returns_schema_and_provenance_for_each(tmp_path):
    """UT-A4-2."""
    path = tmp_path / "sample.mcap"
    _write_sample(path, messages=[("/source/veh_dyn", 0, b"\x00")])

    reader = McapReader(path)
    topics = reader.topics()
    reader.close()
    assert topics["/source/veh_dyn"].schema_name == "adas_sim.test.VehDyn"
    assert topics["/source/veh_dyn"].provenance == Provenance.MEASURED
    assert topics["/df/aeb.outputs"].provenance == Provenance.SIMULATED


def test_meta_blocks_round_trip(tmp_path):
    """UT-A4-3: manifest, config_bundle, topic_provenance."""
    path = tmp_path / "sample.mcap"
    manifest = RunManifest(
        manifest_version=1, run_id="20260729T000000Z-abc12345", run_kind="resim",
        project="base", seed=7, components=(ComponentBuildInfo(name="df", library_sha256="ab" * 32),),
    )
    _write_sample(path, manifest=manifest, config_bundle_bytes=b"EGO_LENGTH_M: 4.5\n", messages=[("/source/veh_dyn", 0, b"\x00")])

    reader = McapReader(path)
    read_manifest = reader.meta()
    read_bundle = reader.config_bundle_bytes()
    read_topics = reader.topics()
    reader.close()

    assert read_manifest == manifest
    assert read_bundle == b"EGO_LENGTH_M: 4.5\n"
    assert read_topics["/source/veh_dyn"].provenance == Provenance.MEASURED


def test_a_recording_with_no_meta_degrades_to_unknown_without_raising(tmp_path):
    """UT-A4-4: R-SIM-6 -- it degrades and says so, it does not raise."""
    path = tmp_path / "no_meta.mcap"
    # Bypass McapWriter deliberately: a foreign/legacy writer never calls
    # add_metadata at all.
    with path.open("wb") as f:
        raw = RawMcapWriter(f)
        raw.start(profile="", library="test")
        schema_id = raw.register_schema(name="adas_sim.test.VehDyn", encoding="", data=b"")
        channel_id = raw.register_channel(topic="/source/veh_dyn", message_encoding="protobuf", schema_id=schema_id)
        raw.add_message(channel_id=channel_id, log_time=0, data=b"\x00", publish_time=0)
        raw.finish()

    reader = McapReader(path)
    manifest = reader.meta()
    topics = reader.topics()
    messages = list(reader.messages())
    reader.close()

    assert manifest.known is False
    assert topics["/source/veh_dyn"].provenance == Provenance.UNKNOWN
    assert messages == [("/source/veh_dyn", 0, None, b"\x00")]


def test_capabilities_are_declared_and_reported():
    """UT-A4-6."""
    assert CAPABILITIES.embedded_schemas is True
    assert CAPABILITIES.round_trips is True
    assert CAPABILITIES.write_only is False
    assert CAPABILITIES.capture_time is True
    assert McapWriter().capabilities is CAPABILITIES


def test_dt_s_reconstruction_from_log_time_gaps(tmp_path):
    """UT-A4-8: tick 0 measured from 0; gaps come from consecutive log_time
    values, exactly as recorded."""
    path = tmp_path / "sample.mcap"
    ticks_ns = [0, 48_000_000, 121_000_000, 200_000_000]  # deliberately non-uniform
    _write_sample(path, messages=[("/source/veh_dyn", t_ns, b"\x00") for t_ns in ticks_ns])

    reader = McapReader(path)
    log_times = [t_ns for _topic, t_ns, _capture_ns, _payload in reader.messages()]
    reader.close()

    assert log_times == ticks_ns
    assert log_times[0] == 0
    dt_s = [(b - a) / 1e9 for a, b in zip(log_times, log_times[1:])]
    assert dt_s == [pytest.approx(0.048), pytest.approx(0.073), pytest.approx(0.079)]


def test_a_tick_missing_an_expected_topic_is_reported_not_dropped(tmp_path):
    """UT-A4-9."""
    path = tmp_path / "sample.mcap"
    # Tick 0: both topics. Tick 1: only veh_dyn -- aeb.outputs is missing.
    _write_sample(path, messages=[
        ("/source/veh_dyn", 0, b"\x00"),
        ("/df/aeb.outputs", 0, b"\x00"),
        ("/source/veh_dyn", 50_000_000, b"\x01"),
    ])

    reader = McapReader(path)
    groups = list(group_by_log_time(reader.messages(), expected_topics=_TOPICS.keys()))
    reader.close()

    assert groups[0] == (0, {"/source/veh_dyn": b"\x00", "/df/aeb.outputs": b"\x00"}, frozenset())
    assert groups[1][0] == 50_000_000
    assert groups[1][2] == frozenset({"/df/aeb.outputs"})


def test_two_writes_of_the_same_messages_are_byte_identical(tmp_path):
    """UT-A4-12: topic order sorted, no wall-clock in the payload."""
    messages = [
        ("/source/veh_dyn", 0, b"\x01\x02"),
        ("/df/aeb.outputs", 0, b"\x03"),
        ("/source/veh_dyn", 50_000_000, b"\x04\x05"),
    ]
    path_a = tmp_path / "a.mcap"
    path_b = tmp_path / "b.mcap"
    _write_sample(path_a, messages=messages)
    _write_sample(path_b, messages=messages)
    assert path_a.read_bytes() == path_b.read_bytes()


def test_capture_time_round_trips_as_a_separate_stamp_from_reception(tmp_path):
    """UT-A4-13: a message's capture time and reception time round-trip as
    two distinct integer-ns stamps (S-A4Δ, OD-9) -- an injected latency
    (captured before it was received) survives, which the pre-delta
    behaviour (`publish_time = log_time_ns` unconditionally) could not
    represent at all."""
    path = tmp_path / "sample.mcap"
    manifest = RunManifest(manifest_version=CAPTURE_TIME_MANIFEST_VERSION, run_id="capture-aware")
    writer = McapWriter()
    writer.open(path, manifest, _TOPICS)
    # Received at t=100ms but describing the world 20ms earlier.
    writer.write("/source/veh_dyn", 100_000_000, b"\x01", capture_time_ns=80_000_000)
    writer.close()

    reader = McapReader(path)
    _topic, log_time_ns, capture_time_ns, _payload = next(iter(reader.messages()))
    reader.close()

    assert log_time_ns == 100_000_000
    assert capture_time_ns == 80_000_000


def test_none_capture_time_is_distinguishable_from_a_genuine_equal_stamp(tmp_path):
    """UT-A4-14: a pre-delta recording (manifest_version below
    `CAPTURE_TIME_MANIFEST_VERSION`, including no manifest at all) reports
    `capture_time_ns=None` for every message regardless of its bytes; a
    post-delta recording whose two stamps genuinely coincide reports two
    *equal integers* instead. The two must not be confused -- shown by
    round-tripping one file of each kind (`OD-9`)."""
    old_path = tmp_path / "old.mcap"
    new_path = tmp_path / "new.mcap"

    _write_sample(old_path, messages=[("/source/veh_dyn", 5_000_000, b"\x00")])  # RunManifest() default: version 0

    new_manifest = RunManifest(manifest_version=CAPTURE_TIME_MANIFEST_VERSION, run_id="capture-aware")
    writer = McapWriter()
    writer.open(new_path, new_manifest, _TOPICS)
    writer.write("/source/veh_dyn", 5_000_000, b"\x00", capture_time_ns=5_000_000)  # genuinely simultaneous
    writer.close()

    old_reader = McapReader(old_path)
    old_message = next(iter(old_reader.messages()))
    old_reader.close()

    new_reader = McapReader(new_path)
    new_message = next(iter(new_reader.messages()))
    new_reader.close()

    assert old_message[2] is None
    assert new_message[2] == 5_000_000
    assert new_message[1] == new_message[2]  # genuinely coincide: a real equality, not a fabricated one
