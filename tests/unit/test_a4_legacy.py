# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A4 `io/legacy.py` tests: UT-A4-5, UT-A4-10 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

import sys
from pathlib import Path

from mcap.writer import Writer as RawMcapWriter

from adas_sim.io.base import Provenance, RunManifest, TopicInfo
from adas_sim.io.legacy import LEGACY_TOPIC_MAP, SYNTHESIZED_VEH_SIG_TOPIC, LegacyRecordingReader
from adas_sim.io.mcap import McapReader, McapWriter

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


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
    """UT-A4-5."""
    path = tmp_path / "legacy.mcap"
    _write_legacy_shaped_recording(path)

    inner = McapReader(path)
    reader = LegacyRecordingReader(inner)
    topics = reader.topics()
    messages = list(reader.messages())
    manifest = reader.meta()
    reader.close()

    assert "/source/veh_dyn" in topics
    assert "/source/gen_object_list" in topics
    assert "df/veh_dyn" not in topics
    assert SYNTHESIZED_VEH_SIG_TOPIC in topics
    assert topics[SYNTHESIZED_VEH_SIG_TOPIC].provenance == Provenance.MOCKED
    assert manifest.known is False

    mapped_topics = {topic for topic, _t, _c, _p in messages}
    assert mapped_topics == {"/source/veh_dyn", "/source/gen_object_list"}


def test_no_name_is_translated_outside_legacy_py(tmp_path):
    """UT-A4-10: a round-trip through the mcap codec (not legacy.py) leaves
    every topic name exactly as declared -- io/legacy.py is the one declared
    exception, readable as data (LEGACY_TOPIC_MAP)."""
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

    # The mapping itself is plain data -- printable, not hidden logic.
    assert LEGACY_TOPIC_MAP["df/veh_dyn"] == "/source/veh_dyn"
    assert isinstance(LEGACY_TOPIC_MAP, dict)


def test_the_gt1_exemption_is_narrow_and_legacy_py_genuinely_needs_it():
    """`check_invariants.py`'s `_GT1_EXEMPT_FILENAMES` exempts `legacy.py`
    specifically. This confirms that exemption is doing real work (the file
    genuinely contains the tokens) rather than being a no-op, and that
    `check_gt1` itself still exempts only this one file by name, not a
    pattern that could accidentally swallow something else."""
    from check_invariants import _FUNCTION_TOKENS, _GT1_EXEMPT_FILENAMES

    assert _GT1_EXEMPT_FILENAMES == frozenset({"legacy.py"})
    legacy_path = Path(__file__).resolve().parent.parent.parent / "src" / "adas_sim" / "io" / "legacy.py"
    text = legacy_path.read_text(encoding="utf-8")
    assert _FUNCTION_TOKENS.search(text), "legacy.py no longer needs the GT-1 exemption -- consider removing it"
