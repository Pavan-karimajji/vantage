# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`io/jsonl.py` -- a second registered recording codec (`R-SIM-14`: "a new
format is one reader/writer of ~4 methods each"), added at `S-C9` as the
real evidence `ST-C9-3` needs: the same ingest map, applied over a second
format, yields an identical port set -- proof format and depth are
genuinely orthogonal, not just an architectural claim. Human-readable
(one JSON object per line: a `meta` header, then one line per message) --
deliberately simple for small synthetic fixtures and debugging, not a
competitor to `.mcap`'s indexed binary format.

Same model as every other codec (`io/base.py`'s own docstring): `meta` +
`topics` + `(topic, log_time_ns, capture_time_ns, bytes)`, reusing
`manifest_to_dict`/`manifest_from_dict` (moved to `io/base.py` at this
same stage, for exactly this reason -- two codecs hand-rolling the same
`RunManifest` (de)serialization would silently drift apart). Message
bytes are hex-encoded (JSON has no binary type); everything else is
line-oriented and sorted the same way `io/mcap.py` already is (`P-8`):
deterministic channel/topic order is part of what makes two writes of the
same messages byte-identical.

**Capabilities, and why each is what it is:** no embedded schemas (JSON
carries no protobuf `FileDescriptorSet` concept without inventing one, and
nothing here needs it -- `topics()` still reports `schema_name`); no
random access (a reader loads and indexes the whole file up front, same
as `McapReader`'s own `iter_metadata`/`get_summary` eager reads, so this
is not a NEW limitation, just an honest one); `capture_time=True` (both
clocks round-trip, same two-clock model `io/mcap.py` uses)."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

from adas_sim.io.base import (
    CAPTURE_TIME_MANIFEST_VERSION,
    Capabilities,
    Provenance,
    RunManifest,
    TopicInfo,
    manifest_from_dict,
    manifest_to_dict,
)
from adas_sim.io.registry import register

CAPABILITIES = Capabilities(
    embedded_schemas=False, random_access=False, meta_blocks=True,
    arbitrary_topics=True, round_trips=True, capture_time=True, write_only=False,
)

_PROVENANCE_VALUES = frozenset(p.value for p in Provenance)


class JsonlWriter:
    capabilities = CAPABILITIES

    def __init__(self) -> None:
        self._file = None

    def open(
        self, path: Path, meta: RunManifest, topics: Mapping[str, TopicInfo], *, config_bundle_bytes: bytes = b"",
    ) -> None:
        self._file = path.open("w", encoding="utf-8", newline="\n")
        header = {
            "kind": "header",
            # `meta.known` mirrors io/mcap.py's own "nothing to write when
            # there is no real manifest yet" (RunManifest() sentinel).
            "meta": manifest_to_dict(meta) if meta.known else None,
            "topics": {
                topic: {
                    "schema_name": info.schema_name,
                    "provenance": info.provenance.value,
                }
                for topic in sorted(topics)
                for info in [topics[topic]]
            },
            "config_bundle": config_bundle_bytes.decode("utf-8") if config_bundle_bytes else None,
        }
        self._file.write(json.dumps(header, sort_keys=True) + "\n")

    def write(self, topic: str, log_time_ns: int, payload: bytes, *, capture_time_ns: int | None = None) -> None:
        record = {
            "kind": "message",
            "topic": topic,
            "log_time_ns": log_time_ns,
            "capture_time_ns": capture_time_ns,
            "data_hex": payload.hex(),
        }
        self._file.write(json.dumps(record, sort_keys=True) + "\n")

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


class JsonlReader:
    capabilities = CAPABILITIES

    def __init__(self, path: Path) -> None:
        self._meta = RunManifest()
        self._topics: dict[str, TopicInfo] = {}
        self._config_bundle_bytes = b""
        self._messages: list[tuple[str, int, int | None, bytes]] = []

        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle):
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                kind = record.get("kind")
                if kind == "header":
                    if record.get("meta") is not None:
                        self._meta = manifest_from_dict(record["meta"])
                    for topic, info in (record.get("topics") or {}).items():
                        raw_provenance = info.get("provenance", Provenance.UNKNOWN.value)
                        provenance = (
                            Provenance(raw_provenance) if raw_provenance in _PROVENANCE_VALUES else Provenance.UNKNOWN
                        )
                        self._topics[topic] = TopicInfo(schema_name=info.get("schema_name", ""), provenance=provenance)
                    config_bundle = record.get("config_bundle")
                    if config_bundle:
                        self._config_bundle_bytes = config_bundle.encode("utf-8")
                elif kind == "message":
                    self._messages.append((
                        record["topic"], record["log_time_ns"], record.get("capture_time_ns"),
                        bytes.fromhex(record["data_hex"]),
                    ))
                else:
                    raise ValueError(f"{path}:{line_no + 1}: unknown jsonl record kind {kind!r}")

    def __repr__(self) -> str:
        return f"<JsonlReader topics={len(self._topics)}>"

    def meta(self) -> RunManifest:
        return self._meta

    def config_bundle_bytes(self) -> bytes:
        """Extra, beyond the `RecordingReader` Protocol's minimum -- same
        as `McapReader.config_bundle_bytes`' own docstring."""
        return self._config_bundle_bytes

    def topics(self) -> Mapping[str, TopicInfo]:
        return dict(self._topics)

    def messages(self, topics: Sequence[str] | None = None) -> Iterator[tuple[str, int, int | None, bytes]]:
        capture_aware = self._meta.manifest_version >= CAPTURE_TIME_MANIFEST_VERSION
        wanted = set(topics) if topics is not None else None
        for topic, log_time_ns, capture_time_ns, payload in self._messages:
            if wanted is not None and topic not in wanted:
                continue
            yield topic, log_time_ns, (capture_time_ns if capture_aware else None), payload

    def close(self) -> None:
        pass


register(".jsonl", reader=JsonlReader, writer=JsonlWriter)
