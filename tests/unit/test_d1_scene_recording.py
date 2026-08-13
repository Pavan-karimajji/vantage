# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D1 checklist item 3 ("`/scene` topic written into a session recording,
so a recording opened cold shows the full spatial scene with no framework
present"): `write_scene_snapshot`'s round-trip through a REAL `.mcap` file
(`io/mcap.py`, no mocking) -- topics registered, schema names Foxglove
Studio recognizes natively, and both `log_time_ns`/`capture_time_ns` land
correctly (`R-SIM-14`'s two-clock model, `CAPTURE_TIME_MANIFEST_VERSION`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("foxglove")  # optional extra (pyproject `[foxglove]`); P-10 -- absent means skip, never a collection error

import adas_sim.io.mcap  # noqa: E402,F401 -- registers ".mcap"
from adas_sim.io.base import RunManifest  # noqa: E402
from adas_sim.plugins.registry import reader_for, writer_for  # noqa: E402
from adas_sim.render.foxglove import (  # noqa: E402
    FRAME_TRANSFORMS_TOPIC, SCENE_TOPIC, scene_recording_topics, write_scene_snapshot,
)
from adas_sim.scene.types import Layer, Prim, Scene  # noqa: E402

_SCENE = Scene(layers=(Layer(id="l1", group="g", prims=(
    Prim(kind="box", cx_m=1.0, cy_m=2.0, length_m=4.5, width_m=1.8, style="object.default"),
)),))


def test_scene_and_frame_transforms_round_trip_through_a_real_mcap(tmp_path):
    out = tmp_path / "scene.mcap"
    writer = writer_for(out)
    writer.open(out, RunManifest(manifest_version=2, run_id="test-d1"), scene_recording_topics())
    write_scene_snapshot(writer, _SCENE, 1_000_000)
    write_scene_snapshot(writer, _SCENE, 2_000_000)
    writer.close()

    reader = reader_for(out)
    try:
        topics = reader.topics()
        assert set(topics) == {SCENE_TOPIC, FRAME_TRANSFORMS_TOPIC}
        assert topics[SCENE_TOPIC].schema_name == "foxglove.SceneUpdate"
        assert topics[FRAME_TRANSFORMS_TOPIC].schema_name == "foxglove.FrameTransforms"
        assert topics[SCENE_TOPIC].schema_bytes  # a real embedded FileDescriptorSet, never empty

        messages = list(reader.messages())
        assert len(messages) == 4  # 2 ticks x (scene, tf)
        for topic, log_time_ns, capture_time_ns, payload in messages:
            assert topic in (SCENE_TOPIC, FRAME_TRANSFORMS_TOPIC)
            assert capture_time_ns == log_time_ns  # a Scene is a pure function of its own tick
            assert len(payload) > 0
    finally:
        reader.close()


def test_a_cold_recording_needs_no_framework_present_to_be_meaningful(tmp_path):
    """The stage's own claim, made concrete: the written bytes decode using
    ONLY the schema embedded in the recording (foxglove-sdk's own
    get_schema(), never adas_sim's scene/ types) -- so a reader with no
    adas_sim installed at all, only a protobuf runtime and the file, can
    still make sense of it. Simulated here by decoding through the embedded
    FileDescriptorSet exactly as a generic mcap tool would, never by
    importing adas_sim.scene."""
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

    out = tmp_path / "cold.mcap"
    writer = writer_for(out)
    writer.open(out, RunManifest(manifest_version=2, run_id="test-cold"), scene_recording_topics())
    write_scene_snapshot(writer, _SCENE, 0)
    writer.close()

    reader = reader_for(out)
    try:
        topics = reader.topics()
        fds = descriptor_pb2.FileDescriptorSet()
        fds.ParseFromString(topics[SCENE_TOPIC].schema_bytes)
        pool = descriptor_pool.DescriptorPool()
        for file_proto in fds.file:
            pool.Add(file_proto)
        msg_cls = message_factory.GetMessageClass(pool.FindMessageTypeByName(topics[SCENE_TOPIC].schema_name))

        scene_messages = [payload for topic, _t, _c, payload in reader.messages() if topic == SCENE_TOPIC]
        decoded = msg_cls()
        decoded.ParseFromString(scene_messages[0])
        assert len(decoded.entities) == 1
        assert decoded.entities[0].id == "l1"
    finally:
        reader.close()
