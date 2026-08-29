# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Pass 1 for the replay case (`sim_implementation_plan.md` S-B2). Phase B
has no C++ and no DLL -- every port is already in an exported recording, so
pass 1 here is purely: group raw `(topic, log_time_ns, bytes)` triples into
`Tick`s (`UT-A4-9`'s `group_by_log_time`), building a lazily-parsed
`PortValue` per port (`S-B2Δ`, `core/tick.py` -- nothing is decoded until a
reader actually touches `.message`).

**Pass 2 (Scene build + render + `SceneCache`) retired with the rest of the
Python scene/render/player tree** (`SM-12`, `docs/VIZ_Sync_Plan_v0.1.md`,
Decision B: the player lives permanently in `viz`, as C++). This module now
carries pass 1 only.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick
from adas_sim.session.tick import decode_message  # noqa: F401 -- re-exported, see below
from adas_sim.io.base import Provenance, group_by_log_time
from adas_sim.ingest.map import IngestRecordingReader, discover_ingest_maps
from adas_sim.plugins.registry import reader_for


class LoadCancelled(Exception):
    """Raised by `build_session_from_recording` when `is_cancelled()` turns
    true mid-load -- cooperative cancellation for `S-B3`'s worker thread
    (`UT-B3-16`). Deliberately not part of `core/errors.py`'s closed
    `SimError` taxonomy: a user-requested cancel is normal control flow, not
    a diagnostic."""

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


#: `decode_message` moved to `core/tick.py` at `S-B2Δ` -- `PortValue.message`'s
#: own lazy parse is its one real caller now, so it lives beside the type it
#: serves. Imported (above), not redefined, so it stays importable from here
#: too: every docstring in this codebase that cites it still says
#: "core/runner.decode_message".


def build_session_from_recording(
    path: Path,
    *,
    codec: str | None = None,
    deterministic: bool = True,
    pose_of: Callable[[dict[str, PortValue]], Pose2D] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> Session:
    """Pass 1: read `path` (via `io.registry.reader_for`, `codec` unused
    today -- `reader_for` dispatches on extension already, kept for a future
    explicit override) and group its messages into `Tick`s.

    `pose_of` extracts `Tick.pose` from a tick's ports; no component's ego
    pose port is generic (R-SIM-1), so the default is the coordinate origin
    for every tick -- correct behaviour is supplied by whichever stage first
    needs a real trajectory (S-B1's own ego layer, or later).

    `on_progress`/`is_cancelled` are `S-B3`'s worker-thread hooks (`UT-B3-15`,
    `UT-B3-16`): called once per tick, from whatever thread this function
    runs on. Raising `LoadCancelled` mid-loop -- rather than returning a
    partial `Session` -- is deliberate: a half-built session rendered as if
    complete is a silent wrong picture (`UT-B3-16`'s own reasoning).
    """
    del codec  # reserved, not yet a second resolution axis (see docstring)
    # Always wrapped: ingest remapping is a no-op when no loaded map matches
    # this recording's topics (`io/ingest.py`'s own docstring, `S-C9`), so
    # every recording -- legacy or modern, this framework's own or someone
    # else's -- presents namespaced names to the rest of the framework.
    reader = IngestRecordingReader(reader_for(path), discover_ingest_maps())
    try:
        topics = reader.topics()
        manifest = reader.meta()
        config_bundle_bytes = reader.config_bundle_bytes()
        # Materialised once (`S-A4Δ`'s 4-tuple): `group_by_log_time` groups
        # on `log_time_ns` and drops `capture_time_ns` after (it is a
        # scheduling primitive shared with the resim path), so capture time
        # is recovered here from the raw messages instead -- same small
        # side-table `io/csv.py` already uses for its own age_s column.
        messages = list(reader.messages())
        capture_by_topic_time = {
            (topic, log_time_ns): capture_time_ns for topic, log_time_ns, capture_time_ns, _payload in messages
        }
        groups = list(group_by_log_time(messages, expected_topics=topics.keys()))

        ticks: list[Tick] = []
        previous_t_ns: int | None = None
        for index, (t_ns, payloads, _missing) in enumerate(groups):
            if is_cancelled is not None and is_cancelled():
                raise LoadCancelled()

            dt_ns = 0 if previous_t_ns is None else t_ns - previous_t_ns
            previous_t_ns = t_ns

            ports: dict[str, PortValue] = {}
            for topic, payload in payloads.items():
                info = topics[topic]
                origin = _PROVENANCE_TO_ORIGIN.get(info.provenance.value, "unknown")
                port_name = _topic_to_port_name(topic)
                # Retained as raw bytes plus a schema handle -- `.message`
                # parses lazily on first access, never here (`S-B2Δ`,
                # `UT-B2-14`, `OD-13`: the resim path parses nothing).
                ports[port_name] = PortValue(
                    name=port_name, message=payload, origin=origin,
                    capture_ns=capture_by_topic_time.get((topic, t_ns)), t_ns=t_ns,
                    schema_bytes=info.schema_bytes, schema_name=info.schema_name,
                )

            pose = pose_of(ports) if pose_of is not None else Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)
            ticks.append(Tick(index=index, t_ns=t_ns, dt_ns=dt_ns, ports=ports, pose=pose))
            if on_progress is not None:
                on_progress(index + 1, len(groups))

        return Session(
            run_id=manifest.run_id or "unknown",
            name=path.stem,
            ticks=tuple(ticks),
            meta=manifest,
            deterministic=deterministic,
            known_ports=frozenset(_topic_to_port_name(topic) for topic in topics),
            provides={p.manifest_port: p for p in reader.provides},
            absent={a.port: a for a in reader.absent},
            config_bundle_bytes=config_bundle_bytes,
        )
    finally:
        reader.close()

