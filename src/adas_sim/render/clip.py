# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B4: interval capture to `.mp4`, the video counterpart of
`render/capture.py`'s single-frame `snapshot()` -- a customer with no
GUI install still needs to *see* a run, not just a still (deferred:
`imageio[ffmpeg]`, `pyproject.toml`'s `video` extra, pulls a portable
ffmpeg with no system install).

Same drawing path as everything else in `render/` (`D5`): every frame comes
from `render/bev.py`'s `render_scene`, and the finished file gets the same
provenance sidecar shape `capture.write_pair` already writes for a
snapshot -- one write mechanism, keyed to the clip's first tick.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from adas_sim.core.runner import build_scene
from adas_sim.session.session import Session
from adas_sim.config.project import ProjectModel
from adas_sim.render import capture
from adas_sim.render.bev import render_scene
from adas_sim.render.theme import Theme
from adas_sim.scene.types import Prim
from adas_sim.player.panels.viewport import Viewport

_DEFAULT_FPS = 10.0


def _clip_fps(session: Session, tick_indices: range) -> float:
    """Real-time playback by default: the average tick spacing over the
    interval, not an arbitrary constant -- a customer watching this needs
    it to match how fast the scenario actually happened. Falls back to
    `_DEFAULT_FPS` for a single-tick interval, where no spacing exists."""
    if len(tick_indices) < 2:
        return _DEFAULT_FPS
    span_s = (session.at(tick_indices[-1]).t_ns - session.at(tick_indices[0]).t_ns) / 1e9
    if span_s <= 0:
        return _DEFAULT_FPS
    return (len(tick_indices) - 1) / span_s


def export_clip(
    session: Session, t_start_s: float, t_end_s: float, viewport: Viewport,
    layer_selection: frozenset[str] | None, out: Path, *,
    theme: Theme = "dark", project: str | None = None, fps: float | None = None,
    selection: frozenset[str] = frozenset(),
    overlay_prims: tuple[Prim, ...] = (),
    hud_lines: tuple[str, ...] = (),
    stale_banner: str | None = None,
    model: ProjectModel | None = None,
) -> None:
    """One clip per call, `[t_start_s, t_end_s]` inclusive (boundary-exact
    via `Session.seek_ns`, same as `snapshot`). `out` must end `.mp4`.

    `model`, when given, is resolved once and reused for every frame --
    same discipline `ST-C5-2` states for `render/viewer.py`'s own cache,
    and the same fix `snapshot()` needed (`sim_implementation_plan.md`
    S-C8's gate: a plug-in root's `ProjectModel` must be threaded through
    or a component's layer code falls back to a source-checkout path a
    deployed copy does not have). `None` resolves once here rather than
    once per tick, which the previous per-tick `build_scene(...)` call
    (implicitly re-resolving on every frame) did not."""
    if out.suffix.lower() != ".mp4":
        raise ValueError(f"clip output must end .mp4, got {out.suffix!r}")
    # Deferred: only an actual clip export needs a video encoder -- every
    # other `render/` module must stay importable with `video` not
    # installed (same discipline `cli/render.py` applies to Qt).
    import imageio.v3 as iio

    resolved_project = project or session.meta.project or "base"
    resolved_model = model if model is not None else ProjectModel.resolve(project=resolved_project)
    start_tick = session.seek_ns(int(t_start_s * 1e9))
    end_tick = session.seek_ns(int(t_end_s * 1e9))
    tick_indices = range(min(start_tick, end_tick), max(start_tick, end_tick) + 1)

    frames = []
    first_scene = None
    for tick_index in tick_indices:
        scene = build_scene(session, tick_index, project=resolved_project, model=resolved_model)
        if first_scene is None:
            first_scene = scene
            # `AR-58`: resolved once, off the first tick, and reused for
            # every frame -- the same reason the sidecar below uses
            # `first_scene` rather than re-deriving anything per tick.
            layer_selection = capture.resolve_layer_selection(layer_selection, scene)
        frames.append(render_scene(
            scene, viewport, theme, layer_selection, selection, overlay_prims, hud_lines, stale_banner,
        ))

    sidecar = capture.sidecar_dict(
        session, tick_indices[0], first_scene, viewport, layer_selection, theme, resolved_project, resolved_model,
    )
    sidecar["clip_t_start_s"] = session.at(tick_indices[0]).t_s
    sidecar["clip_t_end_s"] = session.at(tick_indices[-1]).t_s
    sidecar["clip_tick_count"] = len(tick_indices)
    sidecar["clip_fps"] = fps if fps is not None else _clip_fps(session, tick_indices)

    # imageio's ffmpeg plugin muxes to a real file (it pipes frames to an
    # ffmpeg subprocess) -- no in-memory path the way `snapshot`'s PNG has,
    # so the encode happens in a scratch temp file and the resulting bytes
    # are handed to `write_pair`, keeping the one write/atomicity mechanism
    # (`UT-B4-1`) for every capture kind.
    with tempfile.TemporaryDirectory() as scratch:
        scratch_path = Path(scratch) / "clip.mp4"
        iio.imwrite(scratch_path, frames, fps=sidecar["clip_fps"], codec="libx264", plugin="FFMPEG")
        video_bytes = scratch_path.read_bytes()

    capture.write_pair(video_bytes, sidecar, out)
