# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A4 `io/legacy.py` tests: UT-A4-5, UT-A4-10 (docs/sim_implementation_plan.md).

**`S-C9`:** `io/legacy.py` (the framework's own hand-maintained
`LEGACY_TOPIC_MAP`, and its narrow `GT-1` exemption) is deleted -- the
mapping moved to `modules/df/sim/ingest/carla_legacy.yaml`, declared data
owned by `df` (`R-SIM-23`). `UT-A4-5` is kept, rewritten against the real
ingest map through `io/ingest.py`'s `IngestRecordingReader` instead of the
deleted reader -- stronger than before, since it now exercises `df`'s actual
declared file rather than a hardcoded dict duplicating it. The old
GT-1-exemption test is gone with the exemption it tested (`test_a1_check_
invariants.py`'s `test_run_all_is_clean_on_the_current_skeleton` is the
proof the exemption is no longer needed at all)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcap.writer import Writer as RawMcapWriter

from adas_sim.io.base import Provenance, RunManifest, TopicInfo
from adas_sim.ingest.map import IngestRecordingReader, discover_ingest_maps
from adas_sim.io.mcap import McapReader, McapWriter


def _write_legacy_shaped_recording(path):
    """A raw mcap file shaped exactly like the real legacy recordings under
    modules/df/tests/carla_testruns/ -- old topic names, no meta blocks."""
    with path.open("wb") as f:
        raw = RawMcapWriter(f)
        raw.start(profile="", library="test")
        channels = {}
        for topic in ("df/gen_object_list", "df/veh_dyn", "carla/chase_camera"):
            schema_id = raw.register_schema(name=topic, encoding="", data=b"")
            channels[topic] = raw.register_channel(topic=topic, message_encoding="protobuf", schema_id=schema_id)
        raw.add_message(channel_id=channels["df/veh_dyn"], log_time=0, data=b"\x01", publish_time=0)
        raw.add_message(channel_id=channels["df/gen_object_list"], log_time=0, data=b"\x02", publish_time=0)
        raw.finish()


def test_legacy_topic_names_map_correctly_and_manifest_is_unknown(tmp_path):
    """UT-A4-5, rewritten for `S-C9`: `df`'s real ingest map, not a
    framework-internal dict."""
    if not (Path(__file__).resolve().parents[3] / "df" / "sim" / "ingest" / "carla_legacy.yaml").is_file():
        pytest.skip("modules/df is not part of this checkout (df owns the legacy ingest map)")
    path = tmp_path / "legacy.mcap"
    _write_legacy_shaped_recording(path)

    inner = McapReader(path)
    reader = IngestRecordingReader(inner, discover_ingest_maps())
    topics = reader.topics()
    messages = list(reader.messages())
    manifest = reader.meta()
    reader.close()

    assert "source.veh_dyn" in topics
    assert "source.gen_object_list" in topics
    assert "df/veh_dyn" not in topics
    assert manifest.known is False

    mapped_topics = {topic for topic, _t, _c, _p in messages}
    assert mapped_topics == {"source.veh_dyn", "source.gen_object_list"}

    # source.veh_sig is declared absent, not synthesised as a topic nobody
    # ever publishes to (S-C9: "named at load", never a dead placeholder).
    assert "source.veh_sig" not in topics
    assert any(a.port == "source.veh_sig" for a in reader.absent)


def test_a_recording_that_matches_no_ingest_map_passes_through_unchanged(tmp_path):
    """`IngestRecordingReader` is a no-op when no loaded map's `matches:`
    fires -- a modern recording that already names its own topics correctly
    needs no translation (`io/ingest.py`'s own docstring)."""
    path = tmp_path / "modern.mcap"
    writer = McapWriter()
    writer.open(path, RunManifest(), {
        "/source/veh_dyn": TopicInfo(schema_name="adas_sim.test.VehDyn", provenance=Provenance.MEASURED),
    })
    writer.write("/source/veh_dyn", 0, b"\x00")
    writer.close()

    reader = IngestRecordingReader(McapReader(path), discover_ingest_maps())
    topics = reader.topics()
    reader.close()
    assert "/source/veh_dyn" in topics
    assert reader.provides == ()


def test_no_name_is_translated_outside_a_declared_ingest_map(tmp_path):
    """UT-A4-10: a round-trip through the mcap codec (not an ingest map)
    leaves every topic name exactly as declared."""
    path = tmp_path / "sample.mcap"
    topics = {
        "/source/veh_dyn": TopicInfo(schema_name="adas_sim.test.VehDyn", provenance=Provenance.MEASURED),
        "/df/aeb.outputs": TopicInfo(schema_name="adas_sim.test.AebOutputs", provenance=Provenance.SIMULATED),
    }
    writer = McapWriter()
    writer.open(path, RunManifest(), topics)
    writer.write("/source/veh_dyn", 0, b"\x00")
    writer.close()

    reader = McapReader(path)
    read_topics = set(reader.topics())
    reader.close()
    assert read_topics == set(topics)
