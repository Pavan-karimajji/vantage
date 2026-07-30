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
from adas_sim.core.session import Session
from adas_sim.model.project import ProjectModel
from adas_sim.render.bev import render_scene, render_scene_vector
from adas_sim.render.theme import Theme
from adas_sim.scene.types import Prim, Scene
from adas_sim.view.viewport import Viewport

#: matplotlib's own vector formats this module knows how to route to
#: `render_scene_vector` -- anything else falls back to raster (`.png`).
_VECTOR_SUFFIXES = frozenset({".svg", ".pdf"})


def sidecar_dict(
    session: Session, tick_index: int, scene: Scene, viewport: Viewport,
    layer_selection: frozenset[str] | None, theme: str, project: str,
) -> dict:
    tick = session.at(tick_index)
    model = ProjectModel.resolve(project=project)
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
) -> None:
    """Writes `out` (raster `.png`, or vector `.svg`/`.pdf`) and a `.json`
    sidecar beside it carrying enough provenance to believe the picture
    (`UT-B4-2`): `run_id`, tick, `t_ns`, project, config-bundle hash +
    origin, scenario, pipeline, every component build hash, viewport,
    active layers, theme, Scene version, tool version.

    `project` defaults to the session's own recorded project
    (`session.meta.project`), falling back to `"base"` (`R-VAR-4`) only if
    the recording carries no meta at all (`R-SIM-6`).
    """
    resolved_project = project or session.meta.project or "base"
    scene = build_scene(session, tick_index, project=resolved_project)
    sidecar = sidecar_dict(session, tick_index, scene, viewport, layer_selection, theme, resolved_project)

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
