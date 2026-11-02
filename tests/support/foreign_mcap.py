# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`ForeignMcapWriter`: test data for the READ side only -- `.mcap` files shaped the way the retired
`adas_sim.io.mcap.McapWriter` wrote them, which a reader must still open: no `source_kind`, an unknown origin, a
capture time apart from the logging time, a `config_bundle` as one `yaml` entry, a manifest with a `library_sha256`
and no `build_id`. The one Python recording writer (`adas_recording`, `RCT:IMP-0048`) refuses to make such a file,
so tests of the reader and of the ingest, pin and doctor paths build theirs here. Nothing under `src/` uses it, and
it is not a recording writer for anything that runs; a test that needs a conforming recording uses
`tests/support/recordings.py::write_recording`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml
from mcap.writer import Writer

from adas_sim.io.base import RunManifest, TopicInfo, manifest_to_dict


class ForeignMcapWriter:
    """The `open` / `write` / `close` of the retired writer, over the mcap package's own writer."""

    def __init__(self) -> None:
        self._file = None
        self._writer: Writer | None = None
        self._channel_ids: dict[str, int] = {}

    def open(
        self, path: Path, meta: RunManifest, topics: Mapping[str, TopicInfo], *, config_bundle_bytes: bytes = b"",
        plugin_bundles_meta: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        self._file = Path(path).open("wb")
        self._writer = Writer(self._file)
        self._writer.start(profile="", library="foreign-test-data")
        for topic in sorted(topics):
            info = topics[topic]
            schema_id = self._writer.register_schema(
                name=info.schema_name or topic, encoding="protobuf" if info.schema_bytes else "", data=info.schema_bytes)
            self._channel_ids[topic] = self._writer.register_channel(
                topic=topic, message_encoding="protobuf", schema_id=schema_id)
        if meta.known:
            self._writer.add_metadata("manifest", {"yaml": yaml.safe_dump(manifest_to_dict(meta), sort_keys=True)})
        if config_bundle_bytes:
            self._writer.add_metadata("config_bundle", {"yaml": config_bundle_bytes.decode("utf-8")})
        if plugin_bundles_meta:
            self._writer.add_metadata("plugin_bundles", {"yaml": yaml.safe_dump(dict(plugin_bundles_meta), sort_keys=True)})
        self._writer.add_metadata("topic_provenance", {topic: topics[topic].provenance.value for topic in sorted(topics)})

    def write(self, topic: str, log_time_ns: int, payload: bytes, *, capture_time_ns: int | None = None) -> None:
        publish_time = log_time_ns if capture_time_ns is None else capture_time_ns
        self._writer.add_message(
            channel_id=self._channel_ids[topic], log_time=log_time_ns, data=payload, publish_time=publish_time)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.finish()
            self._writer = None
        if self._file is not None:
            self._file.close()
            self._file = None
