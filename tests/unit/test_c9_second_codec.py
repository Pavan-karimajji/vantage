# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`ST-C9-3` (`docs/sim_implementation_plan.md`, `R-SIM-14`, `R-SIM-23`):
"dimension 1 costs nothing here" -- the SAME ingest map, applied over a
SECOND registered recording format (`io/jsonl.py`, added at this same
stage), yields an IDENTICAL resolved port set to the `.mcap` recording of
equivalent content. `io/ingest.py`'s own docstring already claims this
("format-agnostic by construction: it operates on the recording *model*,
so it works identically for mcap, MF4 or a CarMaker codec") -- until now
nothing proved it against a second real codec; `.jsonl` is that codec.
"""

from __future__ import annotations

from pathlib import Path

from adas_sim.io.base import Provenance, RunManifest, TopicInfo
from adas_sim.ingest.map import IngestMap, IngestRecordingReader, ProvidedPort
from adas_sim.plugins.registry import reader_for, writer_for

import adas_sim.io.jsonl  # noqa: E402,F401 -- registers the ".jsonl" codec
import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec

_PROTO_TYPE = "test.st_c9_3.Objects"
_RAW_TOPIC = "legacy_family/raw_objects"
_MESSAGES = [(_RAW_TOPIC, 1_000, b"\x01"), (_RAW_TOPIC, 2_000, b"\x02"), (_RAW_TOPIC, 3_000, b"\x03")]


def _write_equivalent_recording(path: Path) -> None:
    writer = writer_for(path)
    writer.open(path, RunManifest(manifest_version=2, run_id="st-c9-3"), {
        _RAW_TOPIC: TopicInfo(schema_name=_PROTO_TYPE, provenance=Provenance.UNKNOWN),
    })
    for topic, t_ns, payload in _MESSAGES:
        writer.write(topic, t_ns, payload)
    writer.close()


def _ingest_map() -> IngestMap:
    return IngestMap(
        family="test.st_c9_3",
        match_any_topic=frozenset({_RAW_TOPIC}),
        provides=(
            ProvidedPort(
                topic=_RAW_TOPIC, port="legacy.objects", manifest_port="objects",
                proto_type=_PROTO_TYPE, origin=Provenance.MEASURED, family="test.st_c9_3",
            ),
        ),
        absent=(),
        path=Path("<synthetic, in-memory -- ST-C9-3 test fixture>"),
    )


def _ingested_view(path: Path) -> tuple[dict, list]:
    reader = IngestRecordingReader(reader_for(path), [_ingest_map()])
    try:
        topics = dict(reader.topics())
        messages = list(reader.messages())
    finally:
        reader.close()
    return topics, messages


def test_the_same_ingest_map_yields_an_identical_port_set_over_two_codecs(tmp_path):
    mcap_path = tmp_path / "equivalent.mcap"
    jsonl_path = tmp_path / "equivalent.jsonl"
    _write_equivalent_recording(mcap_path)
    _write_equivalent_recording(jsonl_path)

    mcap_topics, mcap_messages = _ingested_view(mcap_path)
    jsonl_topics, jsonl_messages = _ingested_view(jsonl_path)

    # Both raw topics resolved to the SAME final port name, "legacy.objects"
    # -- the ingest map's own translation, unaware which codec is behind it.
    assert set(mcap_topics) == set(jsonl_topics) == {"legacy.objects"}
    assert mcap_topics["legacy.objects"].provenance == jsonl_topics["legacy.objects"].provenance == Provenance.MEASURED

    # Same final topic name and same bytes, same log_time_ns, for every
    # message -- the depth-of-ingest result is identical regardless of
    # which format carried it (capture_time_ns is intentionally excluded:
    # not asserted equal here, since it is a per-codec/per-write concern
    # this test never populates, R-SIM-14's own two-clock model).
    mcap_shape = [(topic, log_time_ns, payload) for topic, log_time_ns, _capture, payload in mcap_messages]
    jsonl_shape = [(topic, log_time_ns, payload) for topic, log_time_ns, _capture, payload in jsonl_messages]
    assert mcap_shape == jsonl_shape == [("legacy.objects", t_ns, payload) for _raw, t_ns, payload in _MESSAGES]


def test_a_raw_topic_the_ingest_map_does_not_claim_passes_through_unchanged_on_both_codecs(tmp_path):
    """`IngestRecordingReader`'s own "a topic no applicable map declares
    passes through unchanged" -- proven on both codecs, not just the
    default one, since a codec-specific bug in `topics()`/`messages()`
    would otherwise only ever surface on whichever codec someone happened
    to test with."""
    mcap_path = tmp_path / "unclaimed.mcap"
    jsonl_path = tmp_path / "unclaimed.jsonl"
    for path in (mcap_path, jsonl_path):
        writer = writer_for(path)
        writer.open(path, RunManifest(), {
            "totally/unrelated": TopicInfo(schema_name="test.Other", provenance=Provenance.UNKNOWN),
        })
        writer.write("totally/unrelated", 1_000, b"\xff")
        writer.close()

    mcap_topics, mcap_messages = _ingested_view(mcap_path)
    jsonl_topics, jsonl_messages = _ingested_view(jsonl_path)

    assert set(mcap_topics) == set(jsonl_topics) == {"totally/unrelated"}
    assert [m[:2] for m in mcap_messages] == [m[:2] for m in jsonl_messages] == [("totally/unrelated", 1_000)]
