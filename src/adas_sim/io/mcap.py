# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`io/mcap.py` -- the default codec; all capabilities true
(sim_implementation_plan.md S-A4, sim_resim_and_recording.md §3.1). Protobuf
message encoding, schemas embedded as a `FileDescriptorSet` per channel.

Three meta blocks ride as native mcap `Metadata` records, each a flat
`dict[str, str]` (`add_metadata`'s own shape, so no extra encoding is
invented for them): `manifest` (one YAML blob under key `"yaml"`),
`config_bundle` (ditto), `topic_provenance` (topic -> provenance value,
already flat -- no wrapping needed).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from types import MappingProxyType

import yaml
from mcap.reader import make_reader
from mcap.writer import Writer as _McapWriter

from adas_sim.io.base import (
    CAPTURE_TIME_MANIFEST_VERSION,
    Capabilities,
    ComponentBuildInfo,
    OverrideRecord,
    Provenance,
    RunManifest,
    TopicInfo,
)
from adas_sim.io.registry import register

CAPABILITIES = Capabilities(
    embedded_schemas=True, random_access=True, meta_blocks=True,
    arbitrary_topics=True, round_trips=True, capture_time=True, write_only=False,
)

_MANIFEST_META = "manifest"
_CONFIG_BUNDLE_META = "config_bundle"
_PLUGIN_BUNDLES_META = "plugin_bundles"
_TOPIC_PROVENANCE_META = "topic_provenance"
_PROVENANCE_VALUES = frozenset(p.value for p in Provenance)


def _manifest_to_dict(manifest: RunManifest) -> dict:
    return {
        "manifest_version": manifest.manifest_version,
        "run_id": manifest.run_id,
        "run_kind": manifest.run_kind,
        "created_utc": manifest.created_utc,
        "host": manifest.host,
        "source_kind": manifest.source_kind,
        "scenario": manifest.scenario,
        "scenario_sha256": manifest.scenario_sha256,
        "recording": manifest.recording,
        "recording_sha256": manifest.recording_sha256,
        "project": manifest.project,
        "pipeline": manifest.pipeline,
        "seed": manifest.seed,
        "allow_mixed_projects": manifest.allow_mixed_projects,
        "process_nonce": manifest.process_nonce,
        "components": [
            {
                "name": c.name,
                "library_sha256": c.library_sha256,
                "build_id": c.build_id,
                "abi_version": c.abi_version,
                "manifest_sha256": c.manifest_sha256,
                "config_bundle": c.config_bundle,
                "config_bundle_sha256": c.config_bundle_sha256,
                "config_bundle_embedded": c.config_bundle_embedded,
                "enabled_functions": list(c.enabled_functions),
                "package_ref": c.package_ref,
            }
            for c in manifest.components
        ],
        "overrides": [
            {"stage": o.stage, "address": o.address, "verb": o.verb, "value": o.value}
            for o in manifest.overrides
        ],
    }


def _manifest_from_dict(data: dict) -> RunManifest:
    components = tuple(
        ComponentBuildInfo(
            name=c["name"],
            library_sha256=c.get("library_sha256", ""),
            build_id=c.get("build_id", ""),
            abi_version=c.get("abi_version", 0),
            manifest_sha256=c.get("manifest_sha256", ""),
            config_bundle=c.get("config_bundle", ""),
            config_bundle_sha256=c.get("config_bundle_sha256", ""),
            config_bundle_embedded=c.get("config_bundle_embedded", False),
            enabled_functions=tuple(c.get("enabled_functions", ())),
            package_ref=c.get("package_ref", ""),
        )
        for c in data.get("components", ())
    )
    overrides = tuple(
        OverrideRecord(stage=o["stage"], address=o["address"], verb=o["verb"], value=o.get("value"))
        for o in data.get("overrides", ())
    )
    return RunManifest(
        manifest_version=data.get("manifest_version", 0),
        run_id=data.get("run_id", ""),
        run_kind=data.get("run_kind", ""),
        created_utc=data.get("created_utc", ""),
        host=data.get("host", ""),
        source_kind=data.get("source_kind", ""),
        scenario=data.get("scenario", ""),
        scenario_sha256=data.get("scenario_sha256", ""),
        recording=data.get("recording", ""),
        recording_sha256=data.get("recording_sha256", ""),
        project=data.get("project", ""),
        pipeline=data.get("pipeline", ""),
        seed=data.get("seed", 0),
        allow_mixed_projects=data.get("allow_mixed_projects", False),
        process_nonce=data.get("process_nonce", ""),
        components=components,
        overrides=overrides,
    )


class McapWriter:
    capabilities = CAPABILITIES

    def __init__(self) -> None:
        self._file = None
        self._writer: _McapWriter | None = None
        self._channel_ids: dict[str, int] = {}

    def open(
        self,
        path: Path,
        meta: RunManifest,
        topics: Mapping[str, TopicInfo],
        *,
        config_bundle_bytes: bytes = b"",
        plugin_bundles_meta: Mapping[str, Mapping[str, object]] = MappingProxyType({}),
    ) -> None:
        self._file = path.open("wb")
        self._writer = _McapWriter(self._file)
        self._writer.start(profile="", library="adas-sim")

        # Sorted topic order (P-8): deterministic channel numbering is part
        # of what makes two writes of the same messages byte-identical
        # (UT-A4-12) -- dict iteration order must never leak into the file.
        for topic in sorted(topics):
            info = topics[topic]
            schema_id = self._writer.register_schema(
                name=info.schema_name or topic,
                encoding="protobuf" if info.schema_bytes else "",
                data=info.schema_bytes,
            )
            channel_id = self._writer.register_channel(
                topic=topic, message_encoding="protobuf", schema_id=schema_id
            )
            self._channel_ids[topic] = channel_id

        if meta.known:
            self._writer.add_metadata(_MANIFEST_META, {"yaml": yaml.safe_dump(_manifest_to_dict(meta), sort_keys=True)})
        if config_bundle_bytes:
            self._writer.add_metadata(_CONFIG_BUNDLE_META, {"yaml": config_bundle_bytes.decode("utf-8")})
        if plugin_bundles_meta:
            # NR-SIM-44: identity + hash only, never bytes -- opening a
            # colleague's recording must never run their code.
            self._writer.add_metadata(_PLUGIN_BUNDLES_META, {"yaml": yaml.safe_dump(dict(plugin_bundles_meta), sort_keys=True)})
        self._writer.add_metadata(
            _TOPIC_PROVENANCE_META,
            {topic: topics[topic].provenance.value for topic in sorted(topics)},
        )

    def write(self, topic: str, log_time_ns: int, payload: bytes, *, capture_time_ns: int | None = None) -> None:
        # mcap already carries both stamps with exactly these semantics --
        # `publish_time` is when the producer published (our capture_time_ns),
        # `log_time` is when it was logged (S-A4Δ, OD-9). A caller that does
        # not know the capture time falls back to log_time_ns, unchanged from
        # before this delta.
        channel_id = self._channel_ids[topic]
        publish_time = log_time_ns if capture_time_ns is None else capture_time_ns
        self._writer.add_message(channel_id=channel_id, log_time=log_time_ns, data=payload, publish_time=publish_time)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.finish()
            self._writer = None
        if self._file is not None:
            self._file.close()
            self._file = None


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
        return _manifest_from_dict(yaml.safe_load(block["yaml"]))

    def config_bundle_bytes(self) -> bytes:
        """Extra, beyond the `RecordingReader` Protocol's minimum (api
        reference §11: "internal helpers ... are free") -- the writer-side
        twin of `open()`'s `config_bundle_bytes` keyword."""
        block = self._metadata_by_name.get(_CONFIG_BUNDLE_META)
        return block["yaml"].encode("utf-8") if block else b""

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

    def close(self) -> None:
        self._file.close()


def _new_writer() -> McapWriter:
    return McapWriter()


register(".mcap", reader=McapReader, writer=_new_writer)
