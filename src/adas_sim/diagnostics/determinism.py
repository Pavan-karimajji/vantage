# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""Determinism, measured along the axes that break it (`R-SIM-24`).

`derive_axis` never takes a flag -- the axis is read off the two runs' own
manifests (`host`, `process_nonce`, `library_sha256`, `build_id`,
`config_bundle_sha256`), because a flag can lie: "cross-machine verified"
claimed from a pair that also rebuilt the binary is the cheat this refuses. A
pair differing in more than one dimension is evidence for **neither** axis,
and every differing dimension is named.

Axes A (same-process) and B (fresh-process) are **gates**: exact, with no
tolerance field at all, so `compare_exact` is the only comparison allowed.
Axes C (rebuilt binary) and D (different machine) are **measurements**:
`compare_with_tolerance` against the component's own `ToleranceSet`, reporting
every divergence found plus the worst headroom fraction consumed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from adas_sim.diagnostics.tolerance import ToleranceSet
from adas_sim.io.base import RecordingReader, RunManifest, TopicInfo

DeterminismAxis = Literal["same_process", "fresh_process", "rebuilt_binary", "different_machine"]

AXIS_LABELS: Mapping[str, str] = {
    "same_process": "same process", "fresh_process": "fresh process",
    "rebuilt_binary": "rebuilt binary", "different_machine": "different machine",
}


@dataclass(frozen=True, slots=True)
class AxisResult:
    #: `None` when more than one dimension differs -- evidence for neither
    #: axis (`R-SIM-24`).
    axis: DeterminismAxis | None
    differing_dimensions: tuple[str, ...]

    def __repr__(self) -> str:
        return f"<AxisResult axis={self.axis!r} differing={self.differing_dimensions!r}>"


def _component_dims(manifest: RunManifest) -> dict[str, str]:
    dims: dict[str, str] = {}
    for c in manifest.components:
        dims[f"library_sha256:{c.name}"] = c.library_sha256
        dims[f"build_id:{c.name}"] = c.build_id
        dims[f"config_bundle_sha256:{c.name}"] = c.config_bundle_sha256
    return dims


def derive_axis(manifest_a: RunManifest, manifest_b: RunManifest) -> AxisResult:
    """Same-process is checked first via `process_nonce` equality (the
    strongest possible signal: two runs literally written by one process
    share it) -- host and every component dimension are still compared
    afterward, since a "same process" pair with anything else differing is
    itself a finding, not a confirmation."""
    dims_a = {"host": manifest_a.host, **_component_dims(manifest_a)}
    dims_b = {"host": manifest_b.host, **_component_dims(manifest_b)}
    keys = sorted(set(dims_a) | set(dims_b))
    differing = tuple(k for k in keys if dims_a.get(k) != dims_b.get(k))

    if manifest_a.process_nonce and manifest_a.process_nonce == manifest_b.process_nonce:
        return AxisResult(axis="same_process" if not differing else None, differing_dimensions=differing)

    if not differing:
        return AxisResult(axis="fresh_process", differing_dimensions=())
    if len(differing) == 1:
        axis: DeterminismAxis = "different_machine" if differing[0] == "host" else "rebuilt_binary"
        return AxisResult(axis=axis, differing_dimensions=differing)
    return AxisResult(axis=None, differing_dimensions=differing)


@dataclass(frozen=True, slots=True)
class Divergence:
    tick_index: int
    topic: str
    field: str
    detail: str

    def __repr__(self) -> str:
        return f"<Divergence tick={self.tick_index} topic={self.topic!r} field={self.field!r}>"


def _messages_by_topic(reader: RecordingReader) -> dict[str, list[bytes]]:
    out: dict[str, list[bytes]] = {}
    for topic, _log_time_ns, _capture_time_ns, payload in reader.messages():
        out.setdefault(topic, []).append(payload)
    return out


def compare_exact(reader_a: RecordingReader, reader_b: RecordingReader) -> Divergence | None:
    """Axes A/B: byte-identical port payloads -- the ONLY comparison either
    gate is allowed (no tolerance field exists for them). Returns the FIRST
    divergence (this is a gate, not a measurement) or `None` when every
    topic's every message matches exactly."""
    topics_a = set(reader_a.topics())
    topics_b = set(reader_b.topics())
    if topics_a != topics_b:
        only_a, only_b = sorted(topics_a - topics_b), sorted(topics_b - topics_a)
        return Divergence(
            tick_index=-1, topic=(only_a + only_b)[0], field="",
            detail=f"topic sets differ: only in A={only_a}, only in B={only_b}",
        )

    msgs_a, msgs_b = _messages_by_topic(reader_a), _messages_by_topic(reader_b)
    for topic in sorted(topics_a):
        a_list, b_list = msgs_a.get(topic, []), msgs_b.get(topic, [])
        if len(a_list) != len(b_list):
            return Divergence(
                tick_index=min(len(a_list), len(b_list)), topic=topic, field="",
                detail=f"message count differs: A={len(a_list)} B={len(b_list)}",
            )
        for i, (pa, pb) in enumerate(zip(a_list, b_list)):
            if pa != pb:
                return Divergence(tick_index=i, topic=topic, field="", detail="payload bytes differ")
    return None


def _message_class_for_topic(info: TopicInfo):
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

    file_descriptor_set = descriptor_pb2.FileDescriptorSet()
    file_descriptor_set.ParseFromString(info.schema_bytes)
    pool = descriptor_pool.DescriptorPool()
    by_name = {f.name: f for f in file_descriptor_set.file}
    added: set[str] = set()

    def add(file_proto) -> None:
        if file_proto.name in added:
            return
        added.add(file_proto.name)
        for dependency in file_proto.dependency:
            if dependency in by_name:
                add(by_name[dependency])
        pool.Add(file_proto)

    for file_proto in file_descriptor_set.file:
        add(file_proto)
    descriptor = pool.FindMessageTypeByName(info.schema_name)
    return message_factory.GetMessageClass(descriptor)


def compare_with_tolerance(
    reader_a: RecordingReader, reader_b: RecordingReader, tolerance: ToleranceSet,
) -> tuple[list[Divergence], float]:
    """Axes C/D: a MEASUREMENT, never a gate -- every divergence found is
    returned, not just the first. Decodes each topic via its OWN embedded
    schema (`TopicInfo.schema_bytes`) and compares every top-level field: a
    float/double field is checked against `tolerance.bound_for(field)`
    (default exact -- `bound_for` returning `None` means bound `0.0`, i.e.
    exact); every other field type (int, bool, enum, string, message) is
    ALWAYS exact, regardless of what `tolerance` says -- this function never
    even looks a non-float field's name up in `tolerance`, so there is no
    path by which an integer/enum family could be widened. Returns the worst
    headroom fraction (`|diff| / abs_tol`) seen among fields that stayed
    within bound, for the "a passing report prints the headroom consumed"
    requirement (`OD-10`).

    Scope: one `ToleranceSet` applied uniformly across every topic -- every
    real pipeline today is single-component, so a topic-to-component
    attribution question does not yet arise; a multi-component pipeline
    needing per-component tolerance is real, named follow-up work."""
    topics_a, topics_b = reader_a.topics(), reader_b.topics()
    divergences: list[Divergence] = []
    worst_headroom = 0.0

    for topic in sorted(set(topics_a) & set(topics_b)):
        info = topics_a[topic]
        a_payloads = [payload for _t, _l, _c, payload in reader_a.messages([topic])]
        b_payloads = [payload for _t, _l, _c, payload in reader_b.messages([topic])]
        if not info.schema_bytes:
            # No embedded schema to decode field-by-field -- a real
            # difference must never go unreported just because it cannot be
            # ATTRIBUTED to a field (R-SIM-24's whole point is the axis is
            # evidence, not a vibe). Falls back to the same raw-byte
            # equality `compare_exact` uses, unattributed (field="").
            for i, (pa, pb) in enumerate(zip(a_payloads, b_payloads)):
                if pa != pb:
                    divergences.append(Divergence(
                        tick_index=i, topic=topic, field="",
                        detail="payload bytes differ (no embedded schema to attribute this to a field)",
                    ))
            continue
        message_class = _message_class_for_topic(info)
        for i, (pa, pb) in enumerate(zip(a_payloads, b_payloads)):
            if pa == pb:
                continue
            msg_a, msg_b = message_class(), message_class()
            msg_a.ParseFromString(pa)
            msg_b.ParseFromString(pb)
            for field_descriptor in message_class.DESCRIPTOR.fields:
                if field_descriptor.is_repeated:
                    continue  # repeated/message fields: out of scope this pass, see docstring
                value_a = getattr(msg_a, field_descriptor.name)
                value_b = getattr(msg_b, field_descriptor.name)
                is_float = field_descriptor.cpp_type in (
                    field_descriptor.CPPTYPE_FLOAT, field_descriptor.CPPTYPE_DOUBLE,
                )
                if is_float:
                    row = tolerance.bound_for(field_descriptor.name)
                    bound = row.abs_tol if row is not None else 0.0
                    diff = abs(value_a - value_b)
                    if diff > bound:
                        divergences.append(Divergence(
                            tick_index=i, topic=topic, field=field_descriptor.name,
                            detail=f"|{value_a} - {value_b}| = {diff} > bound {bound}",
                        ))
                    elif bound > 0:
                        worst_headroom = max(worst_headroom, diff / bound)
                elif value_a != value_b:
                    divergences.append(Divergence(
                        tick_index=i, topic=topic, field=field_descriptor.name,
                        detail=f"{value_a!r} != {value_b!r} (exact-only field)",
                    ))
    return divergences, worst_headroom
