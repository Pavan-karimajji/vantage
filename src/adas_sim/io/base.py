# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`RecordingReader`/`RecordingWriter` Protocols, `Capabilities`, `TopicInfo`,
`Provenance`, `RunManifest` (sim_api_reference.md §4, R-SIM-14). A recording
is a **model**, not a file format:

```
Recording
  meta:      manifest . config bundle . topic provenance
  topics:    name -> {schema, provenance tag}
  messages:  (topic, log_time_ns, bytes) in log_time order
```

Everything above `io/` is written against this model and never against a
format (`UT-A4-11`); a format is a codec of about four methods
(`io/mcap.py` is the first).

**Note on precedence.** `sim_resim_and_recording.md` §3.0 sketches an
earlier, rougher `RecordingReader`/`RecordingWriter` shape
(`read()`/`declare()`/`put_meta()`, a `meta(block: str) -> bytes | None`
accessor). This stage's own checklist item says "per api reference §4"
explicitly, and api reference's shape is what is implemented here -- the
recording doc's sketch is superseded, not contradicted; it is the "why", api
reference is the "what to type".
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, Protocol


class Provenance(StrEnum):
    """Per-topic origin tag (R-SIM-12, N-5): a manufactured recording and a
    real one share a format, never an evidence grade."""

    MEASURED = "measured"
    TRUTH = "truth"
    MOCKED = "mocked"
    SIMULATED = "simulated"
    OVERRIDDEN = "overridden"
    #: A recording with no meta at all (R-SIM-6) -- degrades visibly, never
    #: silently defaults to a "real" tag.
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Capabilities:
    embedded_schemas: bool
    random_access: bool
    meta_blocks: bool
    arbitrary_topics: bool
    #: False => cannot be a resim input (R-SIM-14).
    round_trips: bool
    write_only: bool = False

    def __repr__(self) -> str:
        return f"<Capabilities round_trips={self.round_trips} write_only={self.write_only}>"


@dataclass(frozen=True, slots=True)
class TopicInfo:
    """Schema + provenance for one topic (sim_api_reference.md §4)."""

    schema_name: str
    provenance: Provenance
    #: A serialized `FileDescriptorSet`, when the codec embeds one
    #: (`embedded_schemas`). Empty for a schema-less/degraded topic.
    schema_bytes: bytes = b""

    def __repr__(self) -> str:
        return f"<TopicInfo schema_name={self.schema_name!r} provenance={self.provenance.value}>"


@dataclass(frozen=True, slots=True)
class ComponentBuildInfo:
    """One `sut.components[]` entry (sim_resim_and_recording.md §2)."""

    name: str
    library_sha256: str = ""
    build_id: str = ""
    abi_version: int = 0
    manifest_sha256: str = ""
    config_bundle: str = ""
    config_bundle_sha256: str = ""
    config_bundle_embedded: bool = False
    enabled_functions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RunManifest:
    """The run manifest (sim_resim_and_recording.md §2), written into the
    recording and every snapshot sidecar. `RunManifest()` (every field at its
    default) is what a recording with no meta at all decodes to --
    `manifest_version=0` marks it as such (`UT-A4-4`, `R-SIM-6`): it degrades
    and says so, it does not raise.
    """

    manifest_version: int = 0
    run_id: str = ""
    run_kind: str = ""  # "sim" | "resim"
    created_utc: str = ""
    host: str = ""
    source_kind: str = ""  # "carla" | "mcap" | "carmaker" | "synthetic"
    scenario: str = ""
    scenario_sha256: str = ""
    recording: str = ""
    recording_sha256: str = ""
    project: str = ""
    pipeline: str = ""
    components: tuple[ComponentBuildInfo, ...] = field(default_factory=tuple)
    seed: int = 0

    @property
    def known(self) -> bool:
        return self.manifest_version > 0

    def __repr__(self) -> str:
        return f"<RunManifest run_id={self.run_id!r} known={self.known}>"


class RecordingReader(Protocol):
    capabilities: ClassVar[Capabilities]

    def meta(self) -> RunManifest: ...

    def topics(self) -> Mapping[str, TopicInfo]: ...

    def messages(self, topics: Sequence[str] | None = None) -> Iterator[tuple[str, int, bytes]]: ...

    def close(self) -> None: ...


class RecordingWriter(Protocol):
    capabilities: ClassVar[Capabilities]

    def open(self, path: Path, meta: RunManifest, topics: Mapping[str, TopicInfo]) -> None: ...

    def write(self, topic: str, log_time_ns: int, payload: bytes) -> None: ...

    def close(self) -> None: ...


def group_by_log_time(
    messages: Iterable[tuple[str, int, bytes]], expected_topics: Collection[str]
) -> Iterator[tuple[int, dict[str, bytes], frozenset[str]]]:
    """Groups `(topic, log_time_ns, bytes)` triples by `log_time_ns` --
    format-agnostic, over the model, not a file. Yields `(log_time_ns,
    {topic: payload}, missing_topics)`: a tick missing one of its expected
    topics is **reported** via `missing_topics`, never silently dropped
    (`UT-A4-9`). A full grouped `Tick` object is `core/tick.py`'s job
    (`S-B2`); this is the format-independent piece of that idea usable now.
    """
    groups: dict[int, dict[str, bytes]] = {}
    for topic, log_time_ns, payload in messages:
        groups.setdefault(log_time_ns, {})[topic] = payload
    expected = frozenset(expected_topics)
    for log_time_ns in sorted(groups):
        group = groups[log_time_ns]
        yield log_time_ns, group, expected - frozenset(group)
