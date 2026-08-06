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
  messages:  (topic, log_time_ns, capture_time_ns, bytes) in log_time order
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
    #: A second, capture-time stamp distinct from reception (`OD-9`,
    #: `CR-SIM-4`). A codec without one declares it and degrades explicitly
    #: -- this is R-SIM-14's existing mechanism, so the field costs no new
    #: concept, only a new declaration.
    capture_time: bool
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
    #: `impl: pkg:<ref>`'s own addressing (`sim_resim_and_recording.md`
    #: "Pinning a resim to the build that produced it", `OQ-9`/`NR-SIM-24`).
    #: Empty when the library was built locally -- today, always, since no
    #: `pkg:` resolver exists yet. A real value alone would prove nothing
    #: (a package can be rebuilt and re-uploaded under the same reference);
    #: `library_sha256` above is the actual verification, `--pin-builds`'s
    #: own job. Kept as a field now so a recording written today already
    #: has a place for it, rather than retrofitting the schema later.
    package_ref: str = ""


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
    #: `OD-11` (`R-SIM-3a` §9.1): whether this run's pipeline declared
    #: `allow_mixed_projects: true` -- badges a deliberate cross-project
    #: experiment so a reader never mistakes it for an unnoticed mismatch.
    #: Independent of whether the components actually disagreed; recorded
    #: whenever the escape was requested, same as any other declared choice.
    allow_mixed_projects: bool = False
    #: `S-C6` (`R-SIM-24`): random per PROCESS (`core.manifest._PROCESS_NONCE`,
    #: generated once at import time), so two runs written by one process
    #: share it -- `sim determinism`'s same-process/fresh-process
    #: discriminator. Lives in `meta`, excluded from `new_run_id`'s hash
    #: (`core.ids.REQUIRED_KEYS` does not name it) so it cannot perturb what
    #: it measures.
    process_nonce: str = ""

    @property
    def known(self) -> bool:
        return self.manifest_version > 0

    def __repr__(self) -> str:
        return f"<RunManifest run_id={self.run_id!r} known={self.known}>"


#: The first `manifest_version` written by a capture-time-aware writer
#: (`OD-9`, `CR-SIM-4`, `S-A4Δ`). A recording whose manifest reports less than
#: this -- including `manifest_version=0` (no manifest at all) -- predates
#: the two-clock model: every message in it reports `capture_time_ns=None`
#: regardless of its bytes, because the writer that produced it set
#: `publish_time = log_time_ns` unconditionally, an equality that carries no
#: information. Existing recordings/tests pinned at `manifest_version=1` are
#: therefore left exactly as they are -- no existing manifest needs editing
#: for this delta to be correct.
CAPTURE_TIME_MANIFEST_VERSION = 2


class RecordingReader(Protocol):
    capabilities: ClassVar[Capabilities]

    def meta(self) -> RunManifest: ...

    def topics(self) -> Mapping[str, TopicInfo]: ...

    def messages(self, topics: Sequence[str] | None = None) -> Iterator[tuple[str, int, int | None, bytes]]: ...

    def close(self) -> None: ...


class RecordingWriter(Protocol):
    capabilities: ClassVar[Capabilities]

    def open(self, path: Path, meta: RunManifest, topics: Mapping[str, TopicInfo]) -> None: ...

    def write(self, topic: str, log_time_ns: int, payload: bytes, *, capture_time_ns: int | None = None) -> None: ...

    def close(self) -> None: ...


def group_by_log_time(
    messages: Iterable[tuple[str, int, int | None, bytes]], expected_topics: Collection[str]
) -> Iterator[tuple[int, dict[str, bytes], frozenset[str]]]:
    """Groups `(topic, log_time_ns, capture_time_ns, bytes)` messages by
    `log_time_ns` -- format-agnostic, over the model, not a file. Grouping is
    a *scheduling* question, so it keys on `log_time_ns` exactly as before
    (`OD-9`) and the yielded shape is unchanged: `(log_time_ns, {topic:
    payload}, missing_topics)`, `capture_time_ns` dropped after grouping. A
    tick missing one of its expected topics is **reported** via
    `missing_topics`, never silently dropped (`UT-A4-9`). A full grouped
    `Tick` object is `core/tick.py`'s job (`S-B2`); this is the
    format-independent piece of that idea usable now.
    """
    groups: dict[int, dict[str, bytes]] = {}
    for topic, log_time_ns, _capture_time_ns, payload in messages:
        groups.setdefault(log_time_ns, {})[topic] = payload
    expected = frozenset(expected_topics)
    for log_time_ns in sorted(groups):
        group = groups[log_time_ns]
        yield log_time_ns, group, expected - frozenset(group)
