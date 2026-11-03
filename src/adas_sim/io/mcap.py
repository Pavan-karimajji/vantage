# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`io/mcap.py` -- the default codec, READ side only; all capabilities true
(sim_implementation_plan.md S-A4, sim_resim_and_recording.md §3.1). Protobuf
message encoding, schemas embedded as a `FileDescriptorSet` per channel.

This package's Python code writes a recording only through the one Python writer,
`adas_recording` of the `adas-interfaces` package (`io/recording_writer.py`,
`RCT:IMP-0048`); this module reads what that writer and the engine's writer
make. Meta blocks ride as native mcap `Metadata` records, each a flat
`dict[str, str]`: `manifest` (one YAML blob under key `"yaml"`),
`config_bundle` (read here only in its older single-`"yaml"` shape),
`topic_provenance` (topic -> provenance value).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from mcap.data_stream import ReadDataStream
from mcap.reader import make_reader
from mcap.records import Chunk
from mcap.stream_reader import breakup_chunk

from adas_sim.io.base import (
    CAPTURE_TIME_MANIFEST_VERSION,
    Capabilities,
    Provenance,
    RunManifest,
    TopicInfo,
    manifest_from_dict,
)
from adas_sim.plugins.registry import register

CAPABILITIES = Capabilities(
    embedded_schemas=True, random_access=True, meta_blocks=True,
    arbitrary_topics=True, round_trips=True, capture_time=True, write_only=False,
)

@dataclass(frozen=True, slots=True)
class ChunkFaultResult:
    """`IMP-0252`/`IMP-0253` (`SW-0252`): one mcap chunk is one "package" for
    `ReadError.SKIP_PACKAGE` -- the file's own summary/schema/channel index
    (`McapReader.topics()`) can be fully intact while an individual chunk's
    compressed bytes are corrupted; `topics()` alone never reads chunk data,
    so it cannot see this. `total` is `0` for a file with no chunk index
    (an unindexed or empty recording) -- a real, honest "nothing to check,"
    never conflated with `corrupted`."""

    total: int
    corrupted: int


_MANIFEST_META = "manifest"
_CONFIG_BUNDLE_META = "config_bundle"
_PLUGIN_BUNDLES_META = "plugin_bundles"
_TOPIC_PROVENANCE_META = "topic_provenance"
_PROVENANCE_VALUES = frozenset(p.value for p in Provenance)


class McapReader:
    capabilities = CAPABILITIES

    def __init__(self, path: Path) -> None:
        self._file = path.open("rb")
        self._reader = make_reader(self._file)
        self._metadata_by_name: dict[str, dict[str, str]] = {
            record.name: dict(record.metadata) for record in self._reader.iter_metadata()
        }

    def __repr__(self) -> str:
        return f"<McapReader topics={len(self.topics())}>"

    def meta(self) -> RunManifest:
        block = self._metadata_by_name.get(_MANIFEST_META)
        if block is None:
            return RunManifest()
        manifest = manifest_from_dict(yaml.safe_load(block["yaml"]))
        # `IMP-0068` (`D29 (1)`): an engine run keeps each stage's bundle hash in the `config_bundle` block
        # (`<stage>/bundle.sha256`), never in `manifest`; a manifest entry that states one is kept.
        bundle = self._metadata_by_name.get(_CONFIG_BUNDLE_META)
        if not bundle:
            return manifest
        filled = tuple(
            dataclasses.replace(c, config_bundle_sha256=bundle[f"{c.name}/bundle.sha256"].strip())
            if not c.config_bundle_sha256 and f"{c.name}/bundle.sha256" in bundle
            else c
            for c in manifest.components
        )
        return dataclasses.replace(manifest, components=filled)

    def config_bundle_bytes(self) -> bytes:
        """Extra, beyond the `RecordingReader` Protocol's minimum (api
        reference §11: "internal helpers ... are free") -- the writer-side
        twin of `open()`'s `config_bundle_bytes` keyword."""
        block = self._metadata_by_name.get(_CONFIG_BUNDLE_META)
        # An engine run's block holds one entry per file (`RCT_Architecture.md` section 6a), not one `yaml` entry.
        return block["yaml"].encode("utf-8") if block and "yaml" in block else b""

    def plugin_bundles_meta(self) -> Mapping[str, Mapping[str, object]]:
        """S-C8: the writer-side twin of `open()`'s `plugin_bundles_meta`
        keyword -- `{component: {"api": int, "sha256": str}}`, identity and
        hash only (`NR-SIM-44`). Empty when the recording predates `S-C8` or
        embedded none."""
        block = self._metadata_by_name.get(_PLUGIN_BUNDLES_META)
        return yaml.safe_load(block["yaml"]) if block else {}

    def topics(self) -> Mapping[str, TopicInfo]:
        provenance_by_topic = self._metadata_by_name.get(_TOPIC_PROVENANCE_META, {})
        summary = self._reader.get_summary()
        result: dict[str, TopicInfo] = {}
        if summary is None:
            return result
        for channel in summary.channels.values():
            schema = summary.schemas.get(channel.schema_id)
            raw_provenance = provenance_by_topic.get(channel.topic, Provenance.UNKNOWN.value)
            provenance = Provenance(raw_provenance) if raw_provenance in _PROVENANCE_VALUES else Provenance.UNKNOWN
            result[channel.topic] = TopicInfo(
                schema_name=schema.name if schema else "",
                provenance=provenance,
                schema_bytes=schema.data if schema else b"",
            )
        return result

    def messages(self, topics: Sequence[str] | None = None) -> Iterator[tuple[str, int, int | None, bytes]]:
        # Whether `publish_time` means anything is a property of the FILE
        # (which writer produced it), not of any one message -- a file whose
        # manifest predates the two-clock model wrote `publish_time =
        # log_time` unconditionally, so reading that back as a real capture
        # stamp would fabricate information the writer never had (OD-9).
        capture_aware = self.meta().manifest_version >= CAPTURE_TIME_MANIFEST_VERSION
        for _schema, channel, message in self._reader.iter_messages(topics=topics):
            capture_time_ns = message.publish_time if capture_aware else None
            yield channel.topic, message.log_time, capture_time_ns, message.data

    def check_faults(self) -> ChunkFaultResult:
        """Extra, beyond the `RecordingReader` Protocol's minimum (same
        "internal helpers ... are free" allowance `config_bundle_bytes`/
        `plugin_bundles_meta` already use above) -- eagerly decodes every
        indexed chunk (CRC-validated, `R-SIM-25`: a bit flip inside a
        compressed chunk must be CAUGHT, not silently returned as
        different-but-valid bytes) and counts how many fail. A caller that
        wants `skip_package` to mean something beyond whole-file damage
        calls this explicitly, since it is real I/O over the whole file
        (unlike `topics()`, which reads only the summary section) -- never
        run implicitly by `topics()` or `messages()` themselves."""
        summary = self._reader.get_summary()
        if summary is None or not summary.chunk_indexes:
            return ChunkFaultResult(total=0, corrupted=0)
        corrupted = 0
        for chunk_index in summary.chunk_indexes:
            self._file.seek(chunk_index.chunk_start_offset + 1 + 8)
            try:
                chunk = Chunk.read(ReadDataStream(self._file))
                list(breakup_chunk(chunk, validate_crc=True))
            except Exception:  # noqa: BLE001 -- any decode/CRC failure marks this chunk corrupted
                corrupted += 1
        return ChunkFaultResult(total=len(summary.chunk_indexes), corrupted=corrupted)

    def close(self) -> None:
        self._file.close()


register(".mcap", reader=McapReader)
