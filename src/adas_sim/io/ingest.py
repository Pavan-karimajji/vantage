# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Recording ingest maps (`R-SIM-23`, `S-C9`): the declared bridge from "what
topics are actually in this file" to "which port does this satisfy" for a
recording this framework did not produce -- today's legacy CARLA exports, and
the shape any other team's/format's recordings will need tomorrow. Owned by
whoever owns the recordings (`modules/<name>/sim/ingest/<family>.yaml`), never
by this framework: a topic named `df/gen_object_list` is `df`'s own fact, the
same placement rule `R-SIM-1` already applies to layer providers.

**Renames and tags only** -- the closed vocabulary this module enforces at
load (`provides:` accepts only `port:`/`proto_type:`/`origin:`; `absent:`
only `reason:`). No expression, no unit conversion, no field arithmetic: a
step that computes is an unversioned algorithm sitting between the recording
and the SUT, which would make a resim reproduce the recording *plus whatever
that step did* (`R-SIM-5`, `R-SIM-7`).

**Two names, one declaration.** A `provides:` entry's `port:` is the
run-relative name a layer provider's `self.<port>` resolves against
(`contracts/binding.py`, `R-SIM-21`) -- for an observation port this is
still qualified by the recording's own pipeline-stage name (a two-function
component's own port, prefixed the way that particular bridge happened to
be run), because *that* is a fact about how this recording came to exist,
not a framework concept. `ProvidedPort.manifest_port` is derived from it
(the same `name.partition(".")[2]` `_match_component_ref` already uses to
strip a stage prefix) -- the bare, pipeline-stage-agnostic name a
component's own manifest declares (`PortSpec.name`), which is what
`Session.feasible_cuts` needs: whether a *file* can satisfy a stage's
declared outputs is a question about the file and the manifest, never about
what a particular pipeline chose to call its stage. A `source.*` stimulus
port has no stage segment to strip (`"source"` is the framework's own
reserved producer name, `contracts/pipeline.py`'s grammar) and passes
through unchanged.

**Loaded from the source checkout, not a plug-in path.** `S-C8` (the
plug-in path, build order #14) does not exist yet -- the same scoped gap a
component's own calibration-reading layer providers already document
(`S-C4`): `discover_ingest_maps` scans `modules/*/sim/ingest/*.yaml` under
the superproject root directly. Revisit when `S-C8` lands.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from adas_sim.core.errors import AuthoringError
from adas_sim.io.base import Provenance, RecordingReader, RunManifest, TopicInfo

#: `io/ingest.py` -> `io` -> `adas_sim` -> `src` -> `sim` -> `modules` -> superproject root.
_SUPERPROJECT_ROOT = Path(__file__).resolve().parents[5]

_ALLOWED_PROVIDES_KEYS = frozenset({"port", "proto_type", "origin"})
_ALLOWED_ABSENT_KEYS = frozenset({"reason"})
_VALID_ORIGINS = frozenset(p.value for p in Provenance)


@dataclass(frozen=True, slots=True)
class ProvidedPort:
    """One `provides:` entry, resolved."""

    topic: str
    port: str  # this run's Tick.ports / known_ports key (self.<port> resolution target)
    manifest_port: str  # bare, pipeline-stage-agnostic key -- Session.provides()/feasible_cuts
    proto_type: str
    origin: Provenance
    family: str

    def __repr__(self) -> str:
        return f"<ProvidedPort {self.topic!r} -> {self.port!r} ({self.family!r})>"


@dataclass(frozen=True, slots=True)
class AbsentPort:
    """One `absent:` entry -- a port this family's recordings never
    capture, named at load rather than discovered as a tick-0 failure."""

    port: str
    reason: str
    family: str

    def __repr__(self) -> str:
        return f"<AbsentPort {self.port!r} ({self.family!r})>"


def _manifest_port(port: str) -> str:
    if port.startswith("source."):
        return port
    stripped = port.partition(".")[2]
    return stripped or port


@dataclass(frozen=True, slots=True)
class IngestMap:
    """One `modules/<name>/sim/ingest/<family>.yaml`, parsed."""

    family: str
    match_any_topic: frozenset[str]
    provides: tuple[ProvidedPort, ...]
    absent: tuple[AbsentPort, ...]
    path: Path

    def matches(self, topics: Collection[str]) -> bool:
        return bool(self.match_any_topic & frozenset(topics))

    def __repr__(self) -> str:
        return f"<IngestMap {self.family!r} provides={len(self.provides)} absent={len(self.absent)}>"


def _require_reason_keys(entry: Mapping[str, object], *, allowed: frozenset[str], where: str) -> None:
    extra = set(entry) - allowed
    if extra:
        raise AuthoringError(
            expected=f"only {sorted(allowed)}", found=f"also has: {sorted(extra)}", where=where,
            hint="an ingest map renames and tags only -- no expression, unit conversion or "
                 "field arithmetic (R-SIM-23)",
        )


def _parse_ingest_map(path: Path) -> IngestMap:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    family = raw.get("family")
    if not family:
        raise AuthoringError(
            expected="a 'family:' key naming this ingest map", found=repr(raw.get("family")),
            where=str(path), hint="add family: <owning-component>.<name>",
        )

    any_topic = frozenset((raw.get("matches") or {}).get("any_topic", ()))
    if not any_topic:
        raise AuthoringError(
            expected="matches: any_topic: [<real topic>, ...] naming at least one topic",
            found=repr(raw.get("matches")), where=str(path),
            hint="an ingest map with nothing to recognise a recording by can never apply",
        )

    provides = []
    for topic, entry in (raw.get("provides") or {}).items():
        where = f"{path} provides '{topic}'"
        _require_reason_keys(entry, allowed=_ALLOWED_PROVIDES_KEYS, where=where)
        port = entry.get("port")
        if not port:
            raise AuthoringError(expected="a 'port:' name", found=repr(port), where=where, hint="")
        origin_raw = entry.get("origin", Provenance.MEASURED.value)
        if origin_raw not in _VALID_ORIGINS:
            raise AuthoringError(
                expected=f"origin: one of {sorted(_VALID_ORIGINS)}", found=repr(origin_raw), where=where, hint="",
            )
        provides.append(ProvidedPort(
            topic=topic, port=port, manifest_port=_manifest_port(port),
            proto_type=entry.get("proto_type", ""), origin=Provenance(origin_raw), family=family,
        ))

    absent = []
    for port, entry in (raw.get("absent") or {}).items():
        where = f"{path} absent '{port}'"
        _require_reason_keys(entry, allowed=_ALLOWED_ABSENT_KEYS, where=where)
        reason = entry.get("reason")
        if not reason:
            raise AuthoringError(expected="a 'reason:' explaining the hole", found=repr(reason), where=where, hint="")
        absent.append(AbsentPort(port=port, reason=reason, family=family))

    return IngestMap(family=family, match_any_topic=any_topic, provides=tuple(provides), absent=tuple(absent), path=path)


def discover_ingest_maps(superproject_root: Path = _SUPERPROJECT_ROOT) -> tuple[IngestMap, ...]:
    """Every `modules/*/sim/ingest/*.yaml` under `superproject_root`,
    parsed. Order is deterministic (sorted by directory then filename) so a
    collision between two maps is reported the same way on every run."""
    maps = []
    for ingest_dir in sorted(superproject_root.glob("modules/*/sim/ingest")):
        for path in sorted(ingest_dir.glob("*.yaml")):
            maps.append(_parse_ingest_map(path))
    return tuple(maps)


class IngestRecordingReader:
    """Wraps any `RecordingReader`, remapping every topic a loaded,
    *matching* ingest map declares to its final port name -- a topic no
    applicable map declares passes through unchanged (safe to wrap a modern
    recording that needs no translation at all, or none matching any
    family). A topic claimed by more than one applicable map is an
    `AuthoringError` naming both families (`UT-C9-5`) -- `matches:` exists
    precisely so two components' recording families do not have to agree on
    a shared topic vocabulary to coexist on one plug-in path.
    """

    def __init__(self, inner: RecordingReader, ingest_maps: Sequence[IngestMap] = ()) -> None:
        self._inner = inner
        self.capabilities = inner.capabilities
        raw_topics = frozenset(inner.topics())
        applicable = [m for m in ingest_maps if m.matches(raw_topics)]

        claims: dict[str, list[ProvidedPort]] = {}
        for ingest_map in applicable:
            for provided in ingest_map.provides:
                claims.setdefault(provided.topic, []).append(provided)

        by_raw_topic: dict[str, ProvidedPort] = {}
        for topic, claimers in claims.items():
            if len(claimers) > 1:
                families = sorted({c.family for c in claimers})
                raise AuthoringError(
                    expected="at most one ingest map to claim a given topic",
                    found=f"topic {topic!r} claimed by {families}",
                    where="adas_sim.io.ingest.IngestRecordingReader",
                    hint="narrow one map's matches: any_topic:, or fold the two families",
                )
            by_raw_topic[topic] = claimers[0]

        self._by_raw_topic = by_raw_topic
        #: This recording's declared provides/absent, file-level and
        #: pipeline-agnostic (`Session.provides`/`Session.absent` read these
        #: directly) -- computed once here, never re-derived per tick.
        self.provides: tuple[ProvidedPort, ...] = tuple(by_raw_topic.values())
        self.absent: tuple[AbsentPort, ...] = tuple(a for m in applicable for a in m.absent)

    def __repr__(self) -> str:
        return f"<IngestRecordingReader wrapping {self._inner!r}>"

    def meta(self) -> RunManifest:
        return self._inner.meta()

    def config_bundle_bytes(self) -> bytes:
        """Forwards to the wrapped reader's own extra (`io/mcap.py`'s own
        docstring: "beyond the `RecordingReader` Protocol's minimum") --
        `b""` for a codec that never implemented it (`io/csv.py`), same as
        calling it directly would report."""
        return getattr(self._inner, "config_bundle_bytes", lambda: b"")()

    def topics(self) -> Mapping[str, TopicInfo]:
        remapped: dict[str, TopicInfo] = {}
        for name, info in self._inner.topics().items():
            provided = self._by_raw_topic.get(name)
            if provided is None:
                remapped[name] = info
            else:
                remapped[provided.port] = TopicInfo(
                    schema_name=info.schema_name, provenance=provided.origin, schema_bytes=info.schema_bytes,
                )
        return remapped

    def messages(self, topics: Sequence[str] | None = None) -> Iterator[tuple[str, int, int | None, bytes]]:
        # `topics` (if given) is expressed in the new, remapped names; ask
        # the inner reader for its own (possibly raw) names.
        reverse = {provided.port: raw for raw, provided in self._by_raw_topic.items()}
        inner_topics = [reverse.get(t, t) for t in topics] if topics is not None else None
        for topic, log_time_ns, capture_time_ns, payload in self._inner.messages(inner_topics):
            provided = self._by_raw_topic.get(topic)
            final = provided.port if provided is not None else topic
            yield final, log_time_ns, capture_time_ns, payload

    def close(self) -> None:
        self._inner.close()
