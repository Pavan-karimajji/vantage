# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`io/jsonl.py` unit tests -- the second registered codec `ST-C9-3` needs
(`docs/sim_implementation_plan.md`, `R-SIM-14`). Round-trip coverage
mirrors `test_a4_mcap.py`'s own shape: capabilities, meta, topics,
messages, the two-clock (`log_time_ns`/`capture_time_ns`) contract."""

from __future__ import annotations

import pytest

from adas_sim.io.base import CAPTURE_TIME_MANIFEST_VERSION, Provenance, RunManifest, TopicInfo
from adas_sim.io.jsonl import CAPABILITIES, JsonlReader, JsonlWriter
from adas_sim.plugins.registry import reader_for, registered_extensions, writer_for

_TOPICS = {
    "source/veh_dyn": TopicInfo(schema_name="adas_sim.test.VehDyn", provenance=Provenance.MEASURED),
    "df/aeb.outputs": TopicInfo(schema_name="adas_sim.test.AebOutputs", provenance=Provenance.SIMULATED),
}


def _write_sample(path, *, manifest=None, config_bundle_bytes=b"", messages=None):
    writer = JsonlWriter()
    writer.open(path, manifest or RunManifest(), _TOPICS, config_bundle_bytes=config_bundle_bytes)
    for topic, t_ns, payload in (messages or []):
        writer.write(topic, t_ns, payload)
    writer.close()


def test_jsonl_is_registered_and_readable_and_writable():
    assert ".jsonl" in registered_extensions()
    info_reader = JsonlReader
    assert info_reader.capabilities is CAPABILITIES
    assert CAPABILITIES.round_trips is True
    assert CAPABILITIES.write_only is False


def test_writer_for_and_reader_for_resolve_the_jsonl_extension(tmp_path):
    path = tmp_path / "rec.jsonl"
    assert isinstance(writer_for(path), JsonlWriter)
    _write_sample(path)
    assert isinstance(reader_for(path), JsonlReader)


def test_round_trips_topics_and_messages(tmp_path):
    path = tmp_path / "rec.jsonl"
    _write_sample(path, messages=[("source/veh_dyn", 1000, b"\x01\x02"), ("df/aeb.outputs", 2000, b"\x03")])

    reader = JsonlReader(path)
    assert dict(reader.topics()) == _TOPICS
    messages = list(reader.messages())
    assert ("source/veh_dyn", 1000, None, b"\x01\x02") in messages
    assert ("df/aeb.outputs", 2000, None, b"\x03") in messages
    reader.close()


def test_messages_filters_by_the_given_topic_list(tmp_path):
    path = tmp_path / "rec.jsonl"
    _write_sample(path, messages=[("source/veh_dyn", 1000, b"\x01"), ("df/aeb.outputs", 2000, b"\x02")])

    reader = JsonlReader(path)
    only_one = list(reader.messages(["source/veh_dyn"]))
    assert [m[0] for m in only_one] == ["source/veh_dyn"]
    reader.close()


def test_round_trips_a_known_manifest(tmp_path):
    path = tmp_path / "rec.jsonl"
    manifest = RunManifest(manifest_version=CAPTURE_TIME_MANIFEST_VERSION, run_id="run-jsonl", project="base")
    _write_sample(path, manifest=manifest)

    reader = JsonlReader(path)
    assert reader.meta().run_id == "run-jsonl"
    assert reader.meta().known is True
    reader.close()


def test_unknown_manifest_when_none_was_ever_written(tmp_path):
    path = tmp_path / "rec.jsonl"
    _write_sample(path)  # RunManifest() default -- not known

    reader = JsonlReader(path)
    assert reader.meta().known is False
    reader.close()


def test_config_bundle_bytes_round_trips(tmp_path):
    path = tmp_path / "rec.jsonl"
    _write_sample(path, config_bundle_bytes=b"vehicle:\n  EGO_WHEELBASE_M: 2.7\n")

    reader = JsonlReader(path)
    assert reader.config_bundle_bytes() == b"vehicle:\n  EGO_WHEELBASE_M: 2.7\n"
    reader.close()


def test_config_bundle_bytes_empty_when_never_written(tmp_path):
    path = tmp_path / "rec.jsonl"
    _write_sample(path)

    reader = JsonlReader(path)
    assert reader.config_bundle_bytes() == b""
    reader.close()


def test_capture_time_reported_only_for_a_capture_time_aware_manifest(tmp_path):
    """`OD-9`/`CR-SIM-4`'s own discipline, over a second codec: a
    pre-two-clock manifest (`manifest_version` below `CAPTURE_TIME_MANIFEST_
    VERSION`) never reports a fabricated `capture_time_ns`, even when one
    was written -- mirrors `test_a4_mcap.py`'s own capture-time test."""
    path = tmp_path / "rec.jsonl"
    writer = JsonlWriter()
    writer.open(path, RunManifest(manifest_version=1, run_id="old"), _TOPICS)
    writer.write("source/veh_dyn", 1000, b"\x01", capture_time_ns=900)
    writer.close()

    reader = JsonlReader(path)
    ((_topic, _log_time_ns, capture_time_ns, _payload),) = list(reader.messages())
    assert capture_time_ns is None  # never fabricated from a pre-two-clock manifest
    reader.close()

    path2 = tmp_path / "rec2.jsonl"
    writer2 = JsonlWriter()
    writer2.open(path2, RunManifest(manifest_version=CAPTURE_TIME_MANIFEST_VERSION, run_id="new"), _TOPICS)
    writer2.write("source/veh_dyn", 1000, b"\x01", capture_time_ns=900)
    writer2.close()

    reader2 = JsonlReader(path2)
    ((_topic2, _log_time_ns2, capture_time_ns2, _payload2),) = list(reader2.messages())
    assert capture_time_ns2 == 900
    reader2.close()


def test_a_malformed_line_raises_naming_the_line_number(tmp_path):
    path = tmp_path / "rec.jsonl"
    _write_sample(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"kind": "nonsense"}\n')

    with pytest.raises(ValueError, match="nonsense"):
        JsonlReader(path)
