# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Pass 1 for the replay case; pass 2 is the renderer
(sim_implementation_plan.md S-B2). Phase B has no C++ and no DLL -- every
port is already in an exported recording, so pass 1 here is purely: group raw
`(topic, log_time_ns, bytes)` triples into `Tick`s (`UT-A4-9`'s
`group_by_log_time`), decoding each payload against its topic's embedded
schema when one exists.

`SceneCache` is pass 2's memo: toggling a layer or switching theme must not
re-run pass 1 (`UT-B2-3`), and it is bounded (`UT-B2-12`) because an
unbounded cache over a 36 000-tick session is `OQ-6` arriving early.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from adas_sim.core.session import Session
from adas_sim.core.tick import Pose2D, PortValue, Tick
from adas_sim.io.base import Provenance, group_by_log_time
from adas_sim.io.legacy import LegacyRecordingReader
from adas_sim.io.registry import reader_for

#: Provenance values (io/) map 1:1 onto Origin values (core/tick.py) -- both
#: carry "unknown" for the same reason (R-SIM-6).
_PROVENANCE_TO_ORIGIN = {p.value: p.value for p in Provenance}


def _topic_to_port_name(topic: str) -> str:
    """A slash-namespaced topic -> its dotted port/signal name (N-2's
    topic/port-name pairing: a topic and its signal name are the same path,
    spelled with `/` versus `.`) -- strip the leading slash, dot-join the
    remaining segments. `Tick.ports` is keyed by this, not the raw topic
    string, so a layer provider's `tick.port(name)` matches the name N-2
    documents rather than a codec-specific spelling.
    """
    return ".".join(topic.strip("/").split("/"))


def decode_message(schema_bytes: bytes, schema_name: str, payload: bytes) -> Any:
    """Builds the message class from an embedded `FileDescriptorSet` at run
    time (R-SIM-11: no generated bindings required) and parses `payload`.
    Returns `payload` unchanged if no schema is available to decode with --
    degrading, never raising, so a recording predating a component's
    embedded-schema support still replays (R-SIM-6).
    """
    if not schema_bytes:
        return payload
    # Deferred: importing adas_sim.core must not pull in protobuf as a side
    # effect (UT-A1-2) -- only decoding an actual schema needs it.
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

    file_descriptor_set = descriptor_pb2.FileDescriptorSet()
    file_descriptor_set.ParseFromString(schema_bytes)
    pool = descriptor_pool.DescriptorPool()
    by_name = {f.name: f for f in file_descriptor_set.file}
    added: set[str] = set()

    def add(file_proto: descriptor_pb2.FileDescriptorProto) -> None:
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
    message = message_cls()
    message.ParseFromString(payload)
    return message


def build_session_from_recording(
    path: Path,
    *,
    codec: str | None = None,
    deterministic: bool = True,
    pose_of: Callable[[dict[str, PortValue]], Pose2D] | None = None,
) -> Session:
    """Pass 1: read `path` (via `io.registry.reader_for`, `codec` unused
    today -- `reader_for` dispatches on extension already, kept for a future
    explicit override) and group its messages into `Tick`s.

    `pose_of` extracts `Tick.pose` from a tick's ports; no component's ego
    pose port is generic (R-SIM-1), so the default is the coordinate origin
    for every tick -- correct behaviour is supplied by whichever stage first
    needs a real trajectory (S-B1's own ego layer, or later).
    """
    del codec  # reserved, not yet a second resolution axis (see docstring)
    # Always wrapped: legacy topic remapping is a no-op on a modern recording
    # (io/legacy.py's own docstring), so every recording -- old or new --
    # presents namespaced names to the rest of the framework.
    reader = LegacyRecordingReader(reader_for(path))
    try:
        topics = reader.topics()
        manifest = reader.meta()
        groups = list(group_by_log_time(reader.messages(), expected_topics=topics.keys()))

        ticks: list[Tick] = []
        previous_t_ns: int | None = None
        for index, (t_ns, payloads, _missing) in enumerate(groups):
            dt_ns = 0 if previous_t_ns is None else t_ns - previous_t_ns
            previous_t_ns = t_ns

            ports: dict[str, PortValue] = {}
            for topic, payload in payloads.items():
                info = topics[topic]
                message = decode_message(info.schema_bytes, info.schema_name, payload)
                origin = _PROVENANCE_TO_ORIGIN.get(info.provenance.value, "unknown")
                port_name = _topic_to_port_name(topic)
                ports[port_name] = PortValue(name=port_name, message=message, origin=origin)

            pose = pose_of(ports) if pose_of is not None else Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)
            ticks.append(Tick(index=index, t_ns=t_ns, dt_ns=dt_ns, ports=ports, pose=pose))

        return Session(
            run_id=manifest.run_id or "unknown",
            name=path.stem,
            ticks=tuple(ticks),
            meta=manifest,
            deterministic=deterministic,
        )
    finally:
        reader.close()


class SceneCache:
    """Memoises pass 2's output, keyed by `(tick_index, layer_selection,
    theme)` -- **not** viewport (`UT-B2-5`: a viewport change must never
    invalidate it). Least-recently-used eviction once `max_size` is exceeded
    (`UT-B2-12`).
    """

    def __init__(self, build: Callable[[int, frozenset[str], str], object], *, max_size: int = 256) -> None:
        self._build = build
        self._max_size = max_size
        self._store: OrderedDict[tuple[int, frozenset[str], str], object] = OrderedDict()
        self.build_calls = 0

    def get(self, tick_index: int, layer_selection: frozenset[str], theme: str) -> object:
        key: tuple[int, frozenset[str], str] = (tick_index, layer_selection, theme)
        if key in self._store:
            self._store.move_to_end(key)
            return self._store[key]
        value = self._build(tick_index, layer_selection, theme)
        self.build_calls += 1
        self._store[key] = value
        if len(self._store) > self._max_size:
            self._store.popitem(last=False)
        return value

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return f"<SceneCache size={len(self._store)}/{self._max_size} build_calls={self.build_calls}>"
