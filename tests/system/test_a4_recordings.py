# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A4 system tests: ST-A4-1, ST-A4-2 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.io.ingest import IngestRecordingReader, discover_ingest_maps
from adas_sim.io.mcap import McapReader, McapWriter

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_TESTRUNS = MODULES_ROOT / "df" / "tests" / "carla_testruns"
TINY_MCAP = SIM_ROOT / "tests" / "fixtures" / "tiny.mcap"


def _existing_recordings() -> list[Path]:
    if not DF_TESTRUNS.is_dir():
        return []
    return sorted(DF_TESTRUNS.rglob("*.mcap"))


def test_every_existing_recording_loads_with_a_positive_tick_count():
    """ST-A4-1."""
    recordings = _existing_recordings()
    if not recordings:
        pytest.skip("modules/df/tests/carla_testruns is absent (partial clone)")

    ingest_maps = discover_ingest_maps()
    for path in recordings:
        reader = IngestRecordingReader(McapReader(path), ingest_maps)
        try:
            tick_count = sum(1 for _ in reader.messages())
            assert tick_count > 0, f"{path}: no messages"
            reader.topics()  # must not raise
            reader.meta()  # must not raise, even with no manifest
        finally:
            reader.close()


def test_read_write_read_yields_an_identical_topic_and_message_set(tmp_path):
    """ST-A4-2."""
    source = TINY_MCAP if TINY_MCAP.is_file() else None
    if source is None:
        pytest.skip("tests/fixtures/tiny.mcap is missing -- run make_tiny_mcap.py")

    first = McapReader(source)
    first_topics = dict(first.topics())
    first_messages = list(first.messages())
    first_manifest = first.meta()
    first_bundle = first.config_bundle_bytes()
    first.close()

    round_tripped = tmp_path / "round_tripped.mcap"
    writer = McapWriter()
    writer.open(round_tripped, first_manifest, first_topics, config_bundle_bytes=first_bundle)
    for topic, log_time_ns, capture_time_ns, payload in first_messages:
        writer.write(topic, log_time_ns, payload, capture_time_ns=capture_time_ns)
    writer.close()

    second = McapReader(round_tripped)
    second_topics = dict(second.topics())
    second_messages = list(second.messages())
    second.close()

    assert set(second_topics) == set(first_topics)
    assert sorted(second_messages) == sorted(first_messages)
