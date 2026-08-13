# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Pass 1 for the replay case; pass 2 is the renderer
(sim_implementation_plan.md S-B2). Phase B has no C++ and no DLL -- every
port is already in an exported recording, so pass 1 here is purely: group raw
`(topic, log_time_ns, bytes)` triples into `Tick`s (`UT-A4-9`'s
`group_by_log_time`), building a lazily-parsed `PortValue` per port
(`S-B2Δ`, `core/tick.py` -- nothing is decoded until a reader actually
touches `.message`).

`SceneCache` is pass 2's memo: toggling a layer or switching theme must not
re-run pass 1 (`UT-B2-3`), and it is bounded both by entry count and by
bytes (`UT-B2-12`, `UT-B2-15`, `S-B2Δ`) because an unbounded cache over a
36 000-tick session is `OQ-6` arriving early.
"""

from __future__ import annotations

import sys
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from adas_sim.session.history import FrameTree, HistoryView, Interaction, LayerCtx, interaction_cache_key
from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick
from adas_sim.session.tick import decode_message  # noqa: F401 -- re-exported, see below
from adas_sim.io.base import Provenance, group_by_log_time
from adas_sim.ingest.map import IngestRecordingReader, discover_ingest_maps
from adas_sim.plugins.registry import reader_for
from adas_sim.config.project import ProjectModel
from adas_sim.scene.registry import registered_providers
from adas_sim.scene.types import Layer, Scene

#: The no-op default (`sim_visualization_spec.md` §7.5) -- every caller that
#: predates interaction-aware layers gets exactly the old behaviour.
_NO_INTERACTION = Interaction()

#: `SceneCache`'s byte ceiling (`NR-SIM-43`, `S-B2Δ`): a stated figure, not a
#: magic literal, so "stays responsive" (`NR-SIM-5`) is falsifiable. 256 MiB
#: comfortably holds hundreds of object-level Scenes; a session of
#: perception-scale Scenes referencing bulk data by `BulkRef` (`S-A3Δ`)
#: stays small regardless, since the bytes live in the recording, not here.
DEFAULT_SCENE_CACHE_MAX_BYTES = 256 * 1024 * 1024


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


def _resolve_tick_index(session: Session, tick_index: int) -> int:
    return tick_index if tick_index >= 0 else len(session) + tick_index


def _build_layer_ctx(
    session: Session, tick_index: int, *, project: str, interaction: Interaction,
    model: ProjectModel | None = None,
) -> LayerCtx:
    index = _resolve_tick_index(session, tick_index)
    return LayerCtx(
        model=model if model is not None else ProjectModel.resolve(project=project),
        history=HistoryView(_ticks=tuple(session.ticks[: index + 1])),
        frames=FrameTree(session.at(index).pose),
        interaction=interaction,
        known_ports=session.known_ports,
    )


def _static_layers(ctx: LayerCtx) -> tuple[Layer, ...]:
    """Providers that declared no `reacts_to` -- `SceneCache`'s cheap tier,
    unaffected by interaction (`sim_visualization_spec.md` §7.5)."""
    return tuple(
        layer for entry in registered_providers().values() if not entry.reacts_to
        for layer in entry.func(ctx)
    )


def _reactive_layers(ctx: LayerCtx) -> tuple[Layer, ...]:
    """Providers that declared `reacts_to` -- recomputed whenever the
    interaction state changes (`sim_visualization_spec.md` §7.5)."""
    return tuple(
        layer for entry in registered_providers().values() if entry.reacts_to
        for layer in entry.func(ctx)
    )


def build_scene(
    session: Session, tick_index: int, *, project: str = "base", interaction: Interaction = _NO_INTERACTION,
    model: ProjectModel | None = None,
) -> Scene:
    """Pass 2a: assemble one tick's `Scene` from every registered layer provider
        -- discovery by import, never a hardcoded list (`R-SIM-1`). Whoever
        composes the running app is responsible for importing the component layer
        modules that should contribute; this calls whatever is registered.

        Independent of theme and layer selection, both applied later at render
        time, which is why `SceneCache` can key on them without this needing
        either.

        `model`, when given, is used as-is instead of re-resolving `project`
    (`ST-C5-2`): a
        caller rendering many ticks off one session resolves its `ProjectModel`
        once, from the session's embedded bundle if it has one, rather than paying
        a full resolve per tick.

    """
    index = _resolve_tick_index(session, tick_index)
    ctx = _build_layer_ctx(session, tick_index, project=project, interaction=interaction, model=model)
    layers = _static_layers(ctx) + _reactive_layers(ctx)
    return Scene(t_s=session.at(index).t_s, layers=layers)


def build_static_scene(
    session: Session, tick_index: int, *, project: str = "base", model: ProjectModel | None = None,
) -> Scene:
    """`SceneCache`'s base tier: only providers that declared no
    `reacts_to`, so an interaction change never has to re-run them."""
    ctx = _build_layer_ctx(session, tick_index, project=project, interaction=_NO_INTERACTION, model=model)
    index = _resolve_tick_index(session, tick_index)
    return Scene(t_s=session.at(index).t_s, layers=_static_layers(ctx))


def build_reactive_layers(
    session: Session, tick_index: int, *, project: str = "base", interaction: Interaction = _NO_INTERACTION,
    model: ProjectModel | None = None,
) -> tuple[Layer, ...]:
    """`SceneCache`'s interaction-keyed tier: only providers that declared
    `reacts_to` (`sim_visualization_spec.md` §7.5)."""
    ctx = _build_layer_ctx(session, tick_index, project=project, interaction=interaction, model=model)
    return _reactive_layers(ctx)


class SceneCache:
    """Memoises pass 2's output, keyed by `(tick_index, layer_selection,
    theme)` -- **not** viewport (`UT-B2-5`: a viewport change must never
    invalidate it). Least-recently-used eviction once `max_size` is exceeded
    (`UT-B2-12`).

    **Interaction-aware tier (`S-B3` slice 3, §7.5), opt-in via
    `build_reactive`.** When given, `.get()` also fetches a second value
    from `build_reactive` keyed additionally on `interaction` (through
    `interaction_cache_key`, since `Interaction.toggles` is not hashable on
    its own) and returns `value` with those layers appended -- `value` must
    then be a `Scene` (`build_static_scene`'s return type). Omitting
    `build_reactive` (the default) reproduces `S-B2`'s exact original
    behaviour: `interaction` is never looked at, and `value` may be
    anything, which is what lets `UT-B2-3/5/12`'s plain test doubles keep
    working unchanged.
    """

    def __init__(
        self,
        build: Callable[[int, frozenset[str], str], object],
        *,
        build_reactive: Callable[[int, frozenset[str], str, Interaction], tuple[Layer, ...]] | None = None,
        max_size: int = 256,
        max_bytes: int = DEFAULT_SCENE_CACHE_MAX_BYTES,
    ) -> None:
        self._build = build
        self._build_reactive = build_reactive
        self._max_size = max_size
        self._max_bytes = max_bytes
        #: key -> (value, its estimated bytes) -- bytes ride alongside the
        #: value so eviction never re-measures (`S-B2Δ`, `NR-SIM-43`).
        self._store: OrderedDict[tuple[int, frozenset[str], str], tuple[object, int]] = OrderedDict()
        self._reactive_store: OrderedDict[tuple, tuple[Layer, ...]] = OrderedDict()
        self._total_bytes = 0
        self.build_calls = 0
        self.reactive_build_calls = 0

    def get(
        self, tick_index: int, layer_selection: frozenset[str], theme: str,
        interaction: Interaction = _NO_INTERACTION,
    ) -> object:
        key: tuple[int, frozenset[str], str] = (tick_index, layer_selection, theme)
        if key in self._store:
            self._store.move_to_end(key)
            value, _nbytes = self._store[key]
        else:
            value = self._build(tick_index, layer_selection, theme)
            self.build_calls += 1
            nbytes = _estimate_bytes(value)
            self._store[key] = (value, nbytes)
            self._total_bytes += nbytes
            # Bytes first (`NR-SIM-43`'s own ceiling), entry count second
            # (`UT-B2-12`) -- either can fire; both are checked every insert.
            # Never evict down to zero: a single oversized Scene must still
            # be returned once, not evicted before its own `get()` sees it.
            while len(self._store) > 1 and (len(self._store) > self._max_size or self._total_bytes > self._max_bytes):
                _evicted_key, (_evicted_value, evicted_bytes) = self._store.popitem(last=False)
                self._total_bytes -= evicted_bytes

        if self._build_reactive is None:
            return value

        reactive_key = key + (interaction_cache_key(interaction),)
        if reactive_key in self._reactive_store:
            self._reactive_store.move_to_end(reactive_key)
            reactive_layers = self._reactive_store[reactive_key]
        else:
            reactive_layers = self._build_reactive(tick_index, layer_selection, theme, interaction)
            self.reactive_build_calls += 1
            self._reactive_store[reactive_key] = reactive_layers
            if len(self._reactive_store) > self._max_size:
                self._reactive_store.popitem(last=False)
        return replace(value, layers=value.layers + reactive_layers)

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return (
            f"<SceneCache size={len(self._store)}/{self._max_size} "
            f"bytes={self._total_bytes}/{self._max_bytes} build_calls={self.build_calls}>"
        )


def _estimate_bytes(value: object) -> int:
    """A cheap-enough size estimate for `SceneCache`'s byte bound
    (`NR-SIM-43`, `S-B2Δ`). A real `Scene` is measured by its own encoded
    size -- the exact quantity a recording or golden would carry, and small
    regardless of how large the *referenced* bulk data is (`BulkRef`,
    `S-A3Δ`). Anything else (a plain test double) falls back to
    `sys.getsizeof`, which keeps `UT-B2-3/5/12`'s tiny values from ever
    approaching `DEFAULT_SCENE_CACHE_MAX_BYTES`.
    """
    if isinstance(value, Scene):
        # Deferred: importing adas_sim.core must not pull in protobuf as a
        # side effect (UT-A1-2) -- same discipline as `decode_message`.
        from adas_sim.scene.codec import encode_scene

        return len(encode_scene(value))
    return sys.getsizeof(value)
