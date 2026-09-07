# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Recording ingest maps (`R-SIM-23`, `S-C9`): the declared bridge from "what
topics are actually in this file" to "which port does this satisfy" for a
recording this framework did not produce -- today's legacy exports, and
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

**Two names, one declaration.** A `provides:` entry is keyed by **port**
(`WP-01`, `SW-0001`) -- the run-relative name a layer provider's
`self.<port>` resolves against (`contracts/binding.py`, `R-SIM-21`) -- for
an observation port this is still qualified by the recording's own
pipeline-stage name (a two-function component's own port, prefixed the way
that particular bridge happened to be run), because *that* is a fact about
how this recording came to exist, not a framework concept.
`ProvidedPort.manifest_port` is derived from it (the same
`name.partition(".")[2]` `_match_component_ref` already uses to strip a
stage prefix) -- the bare, pipeline-stage-agnostic name a component's own
manifest declares (`PortSpec.name`), which is what `Session.feasible_cuts`
needs: whether a *file* can satisfy a stage's declared outputs is a
question about the file and the manifest, never about what a particular
pipeline chose to call its stage. A `source.*` stimulus port has no stage
segment to strip (`"source"` is the framework's own reserved producer name,
`contracts/pipeline.py`'s grammar) and passes through unchanged.

**One port, several candidate addresses.** An entry's value carries an
ordered `from:` list of recorded topic names (`WP-01`) -- the same port may
have been published under different raw names across a family's own
history. `ingest/resolve.py::resolve_port` tries them in the declared
order against a recording's real topic index and reports which one
matched (`SW-0004`..`SW-0007`); `ProvidedPort.topic` keeps today's callers
working unchanged by carrying the *first* declared candidate, and
`ProvidedPort.candidates` carries the full ordered list for a caller that
resolves per recording. The topic-keyed shape this replaced (`port:` as a
sub-key of a topic-keyed entry) is rejected outright, never accepted
alongside the new one -- the two shapes cannot coexist in one file.

**Two discovery paths, one parser.** `discover_ingest_maps` scans `modules/
*/sim/ingest/*.yaml` under the superproject root directly -- a source-
checkout convenience for local development. `discover_ingest_maps_from_
library_dirs` (`WP-21`, `IMP-0194`) is the deployed-location counterpart:
`<library_dir>/sim/ingest/*.yaml` across a plug-in path, exactly the
directory `R-SIM-20`'s build already copies `sim/` into beside the config
bundle -- no source checkout reachable, `IT-14`'s own claim. Both call the
one real parser, `_parse_ingest_map`.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from adas_sim.config.paths import superproject_root as _superproject_root
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.ingest import family as _family
from adas_sim.ingest.header import HeaderBinding
from adas_sim.ingest.units import factor_offset as _factor_offset
from adas_sim.io.base import Provenance, RecordingReader, RunManifest, TopicInfo

_SUPERPROJECT_ROOT = _superproject_root()

#: `IMP-0188`: `unit:`/`shape:`/`header:` extend the closed `provides:`
#: vocabulary -- still renames and tags only (`unit:` resolves through
#: `units.py`'s closed table, never a raw factor/offset typed in the map).
#: `IMP-0001`: `port` left the entry (it is now the key); `from` is the
#: ordered address list that replaces it -- an entry still carrying `port`
#: is the old topic-keyed shape, and is rejected as an unknown key.
_ALLOWED_PROVIDES_KEYS = frozenset({"from", "proto_type", "origin", "unit", "shape", "header"})
_ALLOWED_HEADER_KEYS = frozenset({"t_source", "counter", "status"})
_ALLOWED_ABSENT_KEYS = frozenset({"reason"})
_VALID_ORIGINS = frozenset(p.value for p in Provenance)


@dataclass(frozen=True, slots=True)
class ProvidedPort:
    """One `provides:` entry, resolved -- `IMP-0188`'s nine-field
    `SignalBinding` (topic, port, proto_type, origin, factor, offset,
    shape, and the three header bindings, the last three carried as one
    `HeaderBinding` rather than three flat fields to avoid a second copy
    of `header.py`'s own shape). `factor`/`offset` default to the identity
    conversion (`1.0`/`0.0`) for a map declaring no `unit:` -- unchanged
    behaviour for every map written before `WP-12`.

    `topic` is the entry's first declared `from:` candidate -- every caller
    predating `WP-01` (`IngestRecordingReader`, `Session`) keeps reading one
    topic per port unchanged. `candidates` carries the full ordered list, for
    a caller that resolves per recording (`ingest.resolve.resolve_port`)."""

    topic: str
    port: str  # this run's Tick.ports / known_ports key (self.<port> resolution target)
    manifest_port: str  # bare, pipeline-stage-agnostic key -- Session.provides()/feasible_cuts
    proto_type: str
    origin: Provenance
    family: str
    factor: float = 1.0
    offset: float = 0.0
    shape: tuple[int, ...] | None = None
    header: HeaderBinding | None = None
    candidates: tuple[str, ...] = ()  # `WP-01`: the entry's full ordered `from:` list

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
    #: `IMP-0191`'s declared-rule axis (`family.match_family`) -- optional;
    #: a map with no `matches: path_glob:` participates only in the
    #: existing topic-based axis below.
    path_glob: str | None = None

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


def _require_from_list(entry: Mapping[str, object], *, where: str) -> list[str]:
    """`IMP-0002`: the one raise site for a `provides:` entry missing its
    required `from:` list -- distinct from `_require_reason_keys` above,
    which only ever catches an *extra* key. `where` already names the port
    (`SW-0002`), so this names only the field at fault, and no caller
    composes its own message."""
    candidates = entry.get("from")
    if not isinstance(candidates, list) or not candidates or not all(isinstance(c, str) for c in candidates):
        raise AuthoringError(
            expected="a 'from:' key naming a non-empty, ordered list of recorded addresses",
            found=repr(candidates), where=where,
            hint="a provides: entry is keyed by port and its value carries an ordered from: sequence (WP-01)",
        )
    return candidates


def _parse_ingest_map(path: Path) -> IngestMap:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    family = raw.get("family")
    if not family:
        raise AuthoringError(
            expected="a 'family:' key naming this ingest map", found=repr(raw.get("family")),
            where=str(path), hint="add family: <owning-component>.<name>",
        )

    matches_block = raw.get("matches") or {}
    any_topic = frozenset(matches_block.get("any_topic", ()))
    path_glob = matches_block.get("path_glob")
    if not any_topic and not path_glob:
        raise AuthoringError(
            expected="matches: any_topic: [<real topic>, ...] and/or matches: path_glob: '<pattern>'",
            found=repr(raw.get("matches")), where=str(path),
            hint="an ingest map with nothing to recognise a recording by can never apply",
        )

    provides = []
    for port, entry in (raw.get("provides") or {}).items():
        where = f"{path} provides '{port}'"
        _require_reason_keys(entry, allowed=_ALLOWED_PROVIDES_KEYS, where=where)
        candidates = _require_from_list(entry, where=where)
        origin_raw = entry.get("origin", Provenance.MEASURED.value)
        if origin_raw not in _VALID_ORIGINS:
            raise AuthoringError(
                expected=f"origin: one of {sorted(_VALID_ORIGINS)}", found=repr(origin_raw), where=where, hint="",
            )
        factor, offset = (1.0, 0.0)
        if "unit" in entry:
            factor, offset = _factor_offset(entry["unit"], where=where)
        shape_raw = entry.get("shape")
        shape = tuple(int(n) for n in shape_raw) if shape_raw is not None else None
        header_entry = entry.get("header")
        header = None
        if header_entry is not None:
            _require_reason_keys(header_entry, allowed=_ALLOWED_HEADER_KEYS, where=f"{where} header")
            header = HeaderBinding(
                t_source=header_entry.get("t_source"), counter=header_entry.get("counter"),
                status=header_entry.get("status"),
            )
        provides.append(ProvidedPort(
            topic=candidates[0], candidates=tuple(candidates), port=port, manifest_port=_manifest_port(port),
            proto_type=entry.get("proto_type", ""), origin=Provenance(origin_raw), family=family,
            factor=factor, offset=offset, shape=shape, header=header,
        ))

    absent = []
    for port, entry in (raw.get("absent") or {}).items():
        where = f"{path} absent '{port}'"
        _require_reason_keys(entry, allowed=_ALLOWED_ABSENT_KEYS, where=where)
        reason = entry.get("reason")
        if not reason:
            raise AuthoringError(expected="a 'reason:' explaining the hole", found=repr(reason), where=where, hint="")
        absent.append(AbsentPort(port=port, reason=reason, family=family))

    return IngestMap(
        family=family, match_any_topic=any_topic, provides=tuple(provides), absent=tuple(absent), path=path,
        path_glob=path_glob,
    )


def discover_ingest_maps(superproject_root: Path = _SUPERPROJECT_ROOT) -> tuple[IngestMap, ...]:
    """Every `modules/*/sim/ingest/*.yaml` under `superproject_root`,
    parsed. Order is deterministic (sorted by directory then filename) so a
    collision between two maps is reported the same way on every run."""
    maps = []
    for ingest_dir in sorted(superproject_root.glob("modules/*/sim/ingest")):
        for path in sorted(ingest_dir.glob("*.yaml")):
            maps.append(_parse_ingest_map(path))
    return tuple(maps)


def discover_ingest_maps_from_library_dirs(plugin_path: Sequence[Path]) -> tuple[IngestMap, ...]:
    """`IMP-0194`/`SW-0194`: the deployed-location counterpart to
    `discover_ingest_maps` above -- reads `<library_dir>/sim/ingest/*.yaml`
    for each library directory in `plugin_path`, the same plug-in path a
    player points at a folder of built libraries (`R-SIM-20`, `resolve/
    plugins.py::discover_plugins`'s own directory-of-directories shape).
    Never opens a source checkout: `IT-14` runs this with `modules/*/sim/
    ingest` deleted entirely. Reuses `_parse_ingest_map`, the one parser --
    the difference from `discover_ingest_maps` is only which directories
    are searched."""
    maps = []
    for library_dir in sorted(Path(d) for d in plugin_path):
        ingest_dir = library_dir / "sim" / "ingest"
        if not ingest_dir.is_dir():
            continue
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

        _family.check_no_double_claim(claims, where="adas_sim.ingest.map.IngestRecordingReader")
        by_raw_topic: dict[str, ProvidedPort] = {topic: claimers[0] for topic, claimers in claims.items()}

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
        calling it directly would report. No `lambda` default (`ANL-SW-36`,
        `IMP-0195`): a plain `hasattr` branch reads the same and keeps
        `adas_sim/ingest/**` free of any callable-construction syntax."""
        inner_method = getattr(self._inner, "config_bundle_bytes", None)
        return inner_method() if inner_method is not None else b""

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
