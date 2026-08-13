# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B4: a picture that leaves the tool must carry enough to be believed
(`FR-SIM-13`). `snapshot()` writes an image **and** its provenance sidecar
-- both, or neither (`UT-B4-1`): each is built in memory first, then moved
into place with `os.replace` (atomic on both platforms, `P-7`); any failure
along the way removes every temp/final file this call touched, so a
half-written pair is never observable.

Raster (`.png`) vs. vector (`.pdf`/`.svg`) is chosen from `out`'s own
suffix -- `render/bev.py`'s `render_scene`/`render_scene_vector` share one
drawing path (`D5`), this module only picks which one to call.
"""

from __future__ import annotations

import io as _io
import json
import os
from dataclasses import asdict
from pathlib import Path

import matplotlib.image

from adas_sim import __version__ as TOOL_VERSION
from adas_sim.core.runner import build_scene
from adas_sim.session.session import Session
from adas_sim.config.project import ProjectModel
from adas_sim.render.bev import render_scene, render_scene_vector
from adas_sim.render.theme import Theme
from adas_sim.scene.types import Prim, Scene
from adas_sim.player.panels.layers import LayerTreeState
from adas_sim.player.panels.viewport import Viewport


def resolve_layer_selection(layer_selection: frozenset[str] | None, scene: Scene) -> frozenset[str]:
    """`AR-58`: `None` (no explicit `--layer` selection) used
    to mean "draw literally every layer the Scene carries" all the way
    into the rendered pixels -- which let a layer the live window hides by
    default (`Layer.default_on=False`, a debug overlay a component marked
    off by default per `AR-56`) dominate a headless `sim render`/`sim
    clip` output instead, breaking
    `NR-SIM-2`'s "one picture, many media" and `FR-SIM-13`'s "a snapshot
    is reproducible evidence of what you saw" -- the live window and its
    own PNG disagreed about what was on screen. `None` now resolves to
    what a fresh `LayersPanel` shows with nothing clicked: reuses
    `LayerTreeState` directly (the GUI's own class, `sync()` + `visible_
    layer_ids()`) so there is exactly one implementation of "which layers
    are on by default" -- a caller wanting literally everything passes an
    explicit selection built from every layer id instead, never `None` as
    a synonym for it. Both `snapshot()` and `export_clip()` call this
    (`clip.py`'s own `S-B4` sibling), so the two exporters cannot drift
    into two different notions of "default"."""
    if layer_selection is not None:
        return layer_selection
    state = LayerTreeState()
    state.sync(scene.layers)
    return state.visible_layer_ids()

#: matplotlib's own vector formats this module knows how to route to
#: `render_scene_vector` -- anything else falls back to raster (`.png`).
_VECTOR_SUFFIXES = frozenset({".svg", ".pdf"})


def sidecar_dict(
    session: Session, tick_index: int, scene: Scene, viewport: Viewport,
    layer_selection: frozenset[str] | None, theme: str, project: str,
    model: ProjectModel | None = None,
) -> dict:
    tick = session.at(tick_index)
    model = model if model is not None else ProjectModel.resolve(project=project)
    manifest = session.meta
    return {
        "run_id": session.run_id,
        "tick": tick_index,
        "t_ns": tick.t_ns,
        "project": project,
        "bundle_sha256": model.bundle_sha256,
        "bundle_origin": model.bundle_origin,
        "scenario": manifest.scenario,
        # No real pipeline hash exists yet -- pipelines aren't built/hashed
        # until S-C1c. The name is what the manifest actually carries today.
        "pipeline": manifest.pipeline,
        "components": [
            {
                "name": c.name, "library_sha256": c.library_sha256, "build_id": c.build_id,
                "abi_version": c.abi_version, "manifest_sha256": c.manifest_sha256,
            }
            for c in manifest.components
        ],
        "viewport": asdict(viewport),
        "layers": sorted(layer_selection) if layer_selection is not None else None,
        "theme": theme,
        "scene_version": scene.version,
        "tool_version": TOOL_VERSION,
    }


def write_pair(image_bytes: bytes, sidecar: dict, out: Path) -> None:
    """The atomic write mechanism (`UT-B4-1`: both files or neither) --
    takes already-rendered bytes and a plain sidecar dict, never builds a
    `Scene` itself. `snapshot()` below is the BEV caller; a plot panel's
    own capture (`UT-B4-3`) goes through this exact same function, so there
    is one write routine, not one per panel type."""
    out.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path = out.with_suffix(".json")
    image_tmp = out.with_name(out.name + ".tmp")
    sidecar_tmp = sidecar_path.with_name(sidecar_path.name + ".tmp")
    try:
        image_tmp.write_bytes(image_bytes)
        sidecar_tmp.write_text(json.dumps(sidecar, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(image_tmp, out)
        os.replace(sidecar_tmp, sidecar_path)
    except Exception:
        for tmp in (image_tmp, sidecar_tmp):
            tmp.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
        sidecar_path.unlink(missing_ok=True)
        raise


def snapshot(
    session: Session, tick_index: int, viewport: Viewport,
    layer_selection: frozenset[str] | None, out: Path, *,
    theme: Theme = "dark", project: str | None = None,
    selection: frozenset[str] = frozenset(),
    overlay_prims: tuple[Prim, ...] = (),
    hud_lines: tuple[str, ...] = (),
    stale_banner: str | None = None,
    model: ProjectModel | None = None,
) -> None:
    """Writes `out` (raster `.png`, or vector `.svg`/`.pdf`) and a `.json`
    sidecar beside it carrying enough provenance to believe the picture
    (`UT-B4-2`): `run_id`, tick, `t_ns`, project, config-bundle hash +
    origin, scenario, pipeline, every component build hash, viewport,
    active layers, theme, Scene version, tool version.

    `project` defaults to the session's own recorded project
    (`session.meta.project`), falling back to `"base"` (`R-VAR-4`) only if
    the recording carries no meta at all (`R-SIM-6`).

    `model`, when given, is used as-is instead of re-resolving `project`
    (`ST-C5-2`'s discipline, extended here): a caller that already
    resolved a plug-in root's own `ProjectModel` (`cli/render.py`
    `--plugin-root`) must pass it through, or a component's layer code
    reading calibration relative to a DEPLOYED copy's own path falls back
    to a source-checkout path that does not exist there and crashes
    (`sim_implementation_plan.md` S-C8's gate, the same bug class
    `render/viewer.py`'s `_resolve_project_model` fixed for the
    interactive window)."""
    resolved_project = project or session.meta.project or "base"
    scene = build_scene(session, tick_index, project=resolved_project, model=model)
    layer_selection = resolve_layer_selection(layer_selection, scene)
    sidecar = sidecar_dict(session, tick_index, scene, viewport, layer_selection, theme, resolved_project, model)

    if out.suffix.lower() in _VECTOR_SUFFIXES:
        image_bytes = render_scene_vector(
            scene, viewport, theme, layer_selection, selection, overlay_prims, hud_lines, stale_banner,
            fmt=out.suffix.lower().lstrip("."),
        )
    else:
        frame = render_scene(
            scene, viewport, theme, layer_selection, selection, overlay_prims, hud_lines, stale_banner,
        )
        buffer = _io.BytesIO()
        # `format=` explicit: imsave would otherwise sniff it from `out`'s
        # own suffix, which is correct here too, but this keeps the choice
        # in one place rather than duplicating `out.suffix` parsing.
        matplotlib.image.imsave(buffer, frame, format=out.suffix.lstrip(".") or "png")
        image_bytes = buffer.getvalue()

    write_pair(image_bytes, sidecar, out)
