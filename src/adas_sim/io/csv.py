# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D7: `io/csv.py` -- a write-only export codec (`R-SIM-14`: an export is
lossy and terminal, never a resim input; `CAPABILITIES.round_trips=False`
is what `io/registry.py`'s `reader_for` refuses on). One row per tick
(grouped by `log_time_ns`, `io/base.group_by_log_time`), one column per
leaf field of each selected port, `#`-prefixed provenance preamble.

Works directly on raw `(topic, log_time_ns, capture_time_ns, bytes)`
messages -- **not** `core/tick.Tick`/`PortValue` -- so `io/` never depends
upward on `core/` (`R-SIM-14`: keep `io/` self-contained). That turns out to
buy real multi-rate semantics for free: a topic absent from a row it has
already appeared in at least once before is **held** (`UT-D7-3`) -- last
known value, `age_s` growing -- computed here from the row sequence itself,
not borrowed from `Tick.age_s` (which `core/runner.py`'s pass 1 does not yet
populate meaningfully; a `core/`-level gap this module does not depend on).
`on_missing` governs only a port with **no prior value to hold**: never
appeared at all, or a leading gap before its first occurrence.

**`<port>.age_s` is capture-derived when capture is known** (`S-A4Δ`,
`OD-9`): `(log_time_ns - capture_time_ns)` when the message declared a
capture time, else the pre-delta reception-based convention (`0.0` fresh,
growing from the last log time while held) -- `group_by_log_time` itself
drops `capture_time_ns` after grouping (it is a scheduling primitive shared
with `core/runner.py`), so this module keeps its own small
`(topic, log_time_ns) -> capture_time_ns` side table instead of changing
that shared contract.
"""

from __future__ import annotations

import csv as _csv
import io as _io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.io.base import Capabilities, RunManifest, TopicInfo, group_by_log_time
from adas_sim.plugins.registry import register

CAPABILITIES = Capabilities(
    embedded_schemas=False, random_access=False, meta_blocks=True,
    arbitrary_topics=True, round_trips=False, capture_time=False, write_only=True,
)

OnMissing = Literal["error", "blank", "omit-column"]


def _port_name(topic: str) -> str:
    """Topic -> dotted port name (`N-2`) -- the exact one-line conversion
    `core/runner.py`'s own `_topic_to_port_name` uses, duplicated rather
    than imported so `io/` never depends on `core/`."""
    return ".".join(topic.strip("/").split("/"))


def _decode(schema_bytes: bytes, schema_name: str, payload: bytes):
    """Mirrors `core/runner.decode_message` -- builds the message class from
    an embedded `FileDescriptorSet` at run time (`R-SIM-11`), degrading to
    the raw payload when no schema is available. Duplicated for the same
    layering reason as `_port_name` above."""
    if not schema_bytes:
        return payload
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

    file_descriptor_set = descriptor_pb2.FileDescriptorSet()
    file_descriptor_set.ParseFromString(schema_bytes)
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

    descriptor = pool.FindMessageTypeByName(schema_name)
    message_cls = message_factory.GetMessageClass(descriptor)
    if payload:
        message = message_cls()
        message.ParseFromString(payload)
        return message
    return message_cls()  # default-constructed: leaf-column discovery needs no real message (UT-D7-*)


def _leaf_values(value, prefix: str) -> list[tuple[str, object]]:
    """`(dotted.leaf.name, value)` pairs -- recurses through singular
    message/mapping fields; a **repeated** field (scalar or message) is one
    column, `;`-joined (`R-SIM-14`: an export is lossy by design, not a
    second recording format). Walked off the message's own **static**
    schema (`DESCRIPTOR`/`keys()`), never `ListFields()`/instance presence,
    so the column set is identical on every row regardless of what any one
    row happens to have set."""
    message_module = _protobuf_message_module()
    if message_module is not None and isinstance(value, message_module.Message):
        leaves: list[tuple[str, object]] = []
        for field in value.DESCRIPTOR.fields:
            name = f"{prefix}.{field.name}"
            field_value = getattr(value, field.name)
            if field.is_repeated:
                leaves.append((name, _join_repeated(field_value)))
            else:
                leaves.extend(_leaf_values(field_value, name))
        return leaves
    if isinstance(value, Mapping):
        leaves = []
        for key in sorted(value):
            leaves.extend(_leaf_values(value[key], f"{prefix}.{key}"))
        return leaves
    return [(prefix, value)]


def _join_repeated(items) -> str:
    message_module = _protobuf_message_module()
    parts = []
    for item in items:
        if message_module is not None and isinstance(item, message_module.Message):
            fields = _leaf_values(item, "")  # prefix="" -> names come back "."-prefixed, stripped below
            parts.append("{" + ",".join(f"{name.lstrip('.')}={val}" for name, val in fields) + "}")
        else:
            parts.append(str(item))
    return ";".join(parts)


def _protobuf_message_module():
    try:
        from google.protobuf import message as _message
    except ImportError:  # protobuf is already a hard dependency (pyproject.toml); defensive only
        return None
    return _message


class CsvWriter:
    """`sim export`'s codec (`cli/export.py` constructs this directly, with
    `ports`/`on_missing` -- **not** through `io.registry.writer_for`, which
    only knows the zero-arg `RecordingWriter` shape). Still registered
    write-only (below) so `reader_for` can refuse a `.csv` path as a resim
    input **by capability** (`R-SIM-14`)."""

    capabilities = CAPABILITIES

    def __init__(self, *, ports: Sequence[str] | None = None, on_missing: OnMissing = "error") -> None:
        #: `None` = every port the recording declares.
        self._requested_ports = tuple(ports) if ports is not None else None
        self._on_missing = on_missing
        self._path: Path | None = None
        self._meta: RunManifest = RunManifest()
        self._topics: dict[str, TopicInfo] = {}
        self._messages: list[tuple[str, int, int | None, bytes]] = []

    def open(self, path: Path, meta: RunManifest, topics: Mapping[str, TopicInfo]) -> None:
        self._path = path
        self._meta = meta
        self._topics = dict(topics)
        self._messages = []

    def write(self, topic: str, log_time_ns: int, payload: bytes, *, capture_time_ns: int | None = None) -> None:
        self._messages.append((topic, log_time_ns, capture_time_ns, payload))

    def close(self) -> None:
        assert self._path is not None, "CsvWriter.close() called before open()"
        topics_by_port = {_port_name(topic): topic for topic in self._topics}

        if self._requested_ports is None:
            selected_topics = sorted(self._topics)  # P-8: deterministic column order, not dict insertion order
        else:
            selected_topics = []
            for port in self._requested_ports:
                if port not in topics_by_port:
                    raise AuthoringError(
                        expected=f"one of the recording's own ports: {sorted(topics_by_port)}",
                        found=repr(port), where=str(self._path),
                        hint="a requested port must match a topic actually declared by this recording",
                    )
                selected_topics.append(topics_by_port[port])

        groups = list(group_by_log_time(self._messages, expected_topics=selected_topics))
        never_seen = {
            topic for topic in selected_topics
            if all(topic in missing for _, _, missing in groups)
        }
        if self._on_missing == "error" and never_seen:
            # The per-row check below never fires for a totally empty
            # export (zero rows to iterate) -- this is the only case that
            # needs catching here rather than there.
            raise AuthoringError(
                expected="a value for every selected port", found=f"{sorted(never_seen)} never appear at all",
                where=str(self._path), hint='pass on_missing="blank" or "omit-column" to allow this',
            )
        # `omit-column` only drops a port with **no data anywhere** in the
        # export; a port with a mere leading gap (missing before its first
        # occurrence, held after) keeps its columns -- that gap is handled
        # per-row below, same as any other "no value to hold yet" case.
        included_topics = [t for t in selected_topics if not (self._on_missing == "omit-column" and t in never_seen)]

        leaf_names = {
            topic: [name for name, _ in _leaf_values(
                _decode(self._topics[topic].schema_bytes, self._topics[topic].schema_name, b""), _port_name(topic),
            )]
            for topic in included_topics
        }

        header = ["log_time_ns", "tick_index", "scenario_time_s"]
        for topic in included_topics:
            header.extend(leaf_names[topic])
        for topic in included_topics:
            header.append(f"{_port_name(topic)}.age_s")

        # A side table, not a change to `group_by_log_time`'s shared contract
        # (that stays payload-only, `core/runner.py`'s own consumer): capture
        # time per (topic, log_time_ns), used only for this module's own
        # age_s column (S-A4Δ).
        capture_by_topic_time: dict[tuple[str, int], int | None] = {
            (topic, log_time_ns): capture_time_ns
            for topic, log_time_ns, capture_time_ns, _payload in self._messages
        }

        first_log_time_ns = groups[0][0] if groups else 0
        #: topic -> (last_seen_log_time_ns, its capture_time_ns, decoded value)
        held: dict[str, tuple[int, int | None, object]] = {}
        rows: list[list[object]] = []
        for tick_index, (log_time_ns, payloads, missing) in enumerate(groups):
            row: list[object] = [log_time_ns, tick_index, (log_time_ns - first_log_time_ns) / 1e9]
            ages: list[object] = []
            for topic in included_topics:
                info = self._topics[topic]
                if topic not in missing:
                    value = _decode(info.schema_bytes, info.schema_name, payloads[topic])
                    capture_time_ns = capture_by_topic_time.get((topic, log_time_ns))
                    held[topic] = (log_time_ns, capture_time_ns, value)
                    row.extend(v for _, v in _leaf_values(value, _port_name(topic)))
                    ages.append(0.0 if capture_time_ns is None else (log_time_ns - capture_time_ns) / 1e9)
                elif topic in held:
                    last_seen_ns, held_capture_ns, value = held[topic]
                    row.extend(v for _, v in _leaf_values(value, _port_name(topic)))
                    reference_ns = last_seen_ns if held_capture_ns is None else held_capture_ns
                    ages.append((log_time_ns - reference_ns) / 1e9)
                else:  # no prior value to hold: never seen yet, or never at all -- on_missing governs
                    if self._on_missing == "error":
                        raise AuthoringError(
                            expected=f"a value for {_port_name(topic)!r} by tick {tick_index}",
                            found="no value yet (and none held from an earlier tick)",
                            where=str(self._path),
                            hint='pass on_missing="blank" or "omit-column" to allow this',
                        )
                    row.extend([""] * len(leaf_names[topic]))
                    ages.append("")
            row.extend(ages)
            rows.append(row)

        buffer = _io.StringIO(newline="")
        buffer.write(f"# run_id={self._meta.run_id}\n")
        buffer.write(f"# scenario={self._meta.scenario}\n")
        buffer.write(f"# project={self._meta.project}\n")
        for component in self._meta.components:
            buffer.write(f"# bundle_sha256[{component.name}]={component.config_bundle_sha256}\n")
        origins = ", ".join(f"{_port_name(t)}={self._topics[t].provenance.value}" for t in included_topics)
        buffer.write(f"# origin: {origins}\n")

        writer = _csv.writer(buffer, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(buffer.getvalue(), encoding="utf-8", newline="\n")


def _new_writer() -> CsvWriter:
    return CsvWriter()  # every port, on_missing="error" -- cli/export.py constructs its own directly


register(".csv", writer=_new_writer)
