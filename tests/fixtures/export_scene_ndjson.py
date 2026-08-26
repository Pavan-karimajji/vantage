# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""E2E-07/E2E-VZ-01, step 2 of the sequenced plan in
`modules/viz/docs/VIZ_Sync_Plan_v0.1.md`'s `SM-12` row: exports every tick of
the phase-1 golden corpus, replayed through the real (retiring) Python scene
-- the same pipeline `make_bsd_golden.py` already proves -- to the shared
cross-language NDJSON schema `viz`'s own `--export-ndjson` sibling (C++,
`player_app.cpp`) writes. One line per prim per tick. Never hand-crafted --
regenerate with `python tests/fixtures/export_scene_ndjson.py` (needs
`modules/interfaces` built, same requirement `make_bsd_golden.py` has).

Point-encoding parity with the C++ ABI, confirmed by reading
`viz/cpp/viz/scene/scene_builder.cpp` directly (that ABI carries no semantic
per-kind fields at all -- everything is a resolved point list):
  * `box`   -- C++ stores the CENTRE ONLY (1 point), no width/length/yaw
              anywhere in the ABI. `objects_layer`'s real boxes (below) DO
              carry real `length_m`/`width_m`/`yaw_rad` -- a genuine,
              load-bearing cross-language gap, not solved here. The lost
              fields are still exported under `_py_extra` for a human
              comparing a divergence, never compared by the shared schema.
  * `circle` -- C++ stores 2 points: centre, then `(r_m, 0.0)`. Mirrored
              exactly.
  * `text`  -- C++ stores 1 point (the anchor); the string itself travels in
              `label`, not `points`. Mirrored exactly.
  * `polygon`/`polyline`/`points` -- `points_m` exported unchanged.
  * `arrow`/`grid` -- **never emitted by any of df's four real providers**
              (confirmed by grepping every `Prim(` call in
              `modules/df/sim/layers/{common,bsd}.py`), so their point
              encoding is not needed for the phase-1 corpus and is not
              guessed at here.
  * `ellipse`/`heatmap`/`image` -- Python-only kinds with no C++ ABI
              equivalent at all. Also never emitted by the four real
              providers -- moot for phase-1, a real gap if that ever
              changes.

Frame-to-space mapping: every real `Prim(` call above omits `frame=`
entirely, so every prim in the phase-1 corpus defaults to `frame="ego"`
(`adas_sim/scene/frames.py`). `viz`'s C++ space vocabulary is
`ego_bev`/`image:<cam>`/`world`/`chart` -- Python's is `ego`/`world`/
`sensor:<id>`/`image:<cam>`, not 1:1. Mapped here: `"ego"` -> `"ego_bev"`
(the only literal-name difference actually exercised), `"world"` and
`"image:<cam>"` pass through unchanged, `"sensor:<id>"` has no C++ target
and is passed through verbatim with no translation (untested by the
phase-1 corpus -- no real prim uses it).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SIM_ROOT = Path(__file__).resolve().parents[2]
_MODULES_ROOT = _SIM_ROOT.parent
_DF_ROOT = _MODULES_ROOT / "df"
_SRC = _SIM_ROOT / "src"
for _p in (_SRC, _DF_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from adas_sim.diagnostics.console import reconfigure_console_utf8  # noqa: E402
from adas_sim.session.history import FrameTree, HistoryView, LayerCtx  # noqa: E402
from adas_sim.core.runner import build_session_from_recording  # noqa: E402
from adas_sim.config.project import ProjectModel  # noqa: E402
from adas_sim.scene import default_layers  # noqa: E402
from adas_sim.scene.types import Prim, Scene  # noqa: E402
from sim.layers import bsd, common  # noqa: E402

_CARLA_TESTRUNS = _DF_ROOT / "tests" / "carla_testruns"
CORPUS = (
    _CARLA_TESTRUNS / "aeb" / "aeb_canonical_10mps_30m.mcap",
    _CARLA_TESTRUNS / "exports" / "bsd_curve_r172_passby_20260727_213847.mcap",
)
OUT_DIR = Path(__file__).resolve().parent / "golden" / "ndjson"

# Same providers `make_bsd_golden.py` uses -- the real, retiring `SI-19` scene.
_PROVIDERS = (
    default_layers.frame_layer, default_layers.ego_layer, common.objects_layer,
    default_layers.trail_layer, common.hud_layer, bsd.zone_layer, bsd.warning_layer,
)

_FRAME_TO_SPACE = {"ego": "ego_bev", "world": "world"}


def build_scene(session, tick_index: int, project: str = "base") -> Scene:
    ctx = LayerCtx(
        model=ProjectModel.resolve(project=project),
        history=HistoryView(_ticks=tuple(session.ticks[: tick_index + 1])),
        frames=FrameTree(session.at(tick_index).pose),
        known_ports=session.known_ports,
    )
    layers = [layer for provider in _PROVIDERS for layer in provider(ctx)]
    return Scene(t_s=session.at(tick_index).t_s, layers=tuple(layers))


def _space_of(frame: str) -> str:
    if frame in _FRAME_TO_SPACE:
        return _FRAME_TO_SPACE[frame]
    if frame.startswith("image:"):
        return frame  # already "image:<cam>", same shape both languages use
    return frame  # "sensor:<id>" or anything else -- no C++ target, passed through


def _space_camera_of(space: str) -> str | None:
    if space.startswith("image:") and len(space) > len("image:"):
        return space[len("image:") :]
    return None


def _round_point(x: float, y: float) -> list[float]:
    return [round(x, 6), round(y, 6)]


def _points_of(prim: Prim) -> list[list[float]] | None:
    if prim.kind == "box":
        if prim.cx_m is None or prim.cy_m is None:
            return None
        return [_round_point(prim.cx_m, prim.cy_m)]
    if prim.kind == "circle":
        if prim.cx_m is None or prim.cy_m is None or prim.r_m is None:
            return None
        return [_round_point(prim.cx_m, prim.cy_m), _round_point(prim.r_m, 0.0)]
    if prim.kind == "text":
        if prim.x_m is None or prim.y_m is None:
            return None
        return [_round_point(prim.x_m, prim.y_m)]
    if prim.points_m is not None:
        return [_round_point(x, y) for x, y in prim.points_m]
    # arrow/grid/ellipse/heatmap/image: never emitted by df's real four
    # providers (confirmed by grep) -- not encoded here, see module docstring.
    return None


def _py_extra_of(prim: Prim) -> dict | None:
    """Fields the shared NDJSON schema has nowhere to carry -- real box
    length/width/yaw, chiefly -- kept for a human reading a divergence,
    never read by the comparator."""
    extra: dict[str, float] = {}
    for name in ("length_m", "width_m", "yaw_rad"):
        value = getattr(prim, name, None)
        if value is not None:
            extra[name] = value
    return extra or None


def export_scene_row(tick_index: int, t_s: float, layer_id: str, prim: Prim) -> dict:
    space = _space_of(prim.frame)
    row = {
        "tick": tick_index,
        "scene_index": 0,
        "kind": prim.kind,
        "points": _points_of(prim),
        "style": prim.style,
        "label": prim.text if prim.kind == "text" else None,
        "pick_id": prim.pick_id,
        "layer": layer_id,
        "space": space,
        "space_camera": _space_camera_of(space),
        "reference_topic": prim.bulk.topic if prim.bulk is not None else None,
        "reference_log_time_ns": prim.bulk.log_time_ns if prim.bulk is not None else None,
        "reference_kind": None,  # BulkRef carries no kind field on the Python side; unused by phase-1 corpus
        "derived": prim.derived,
        "inspector_fields": dict(prim.fields) if prim.fields is not None else None,
    }
    if prim.points_m is None and prim.kind not in ("box", "circle", "text") and row["points"] is None:
        row["todo"] = "point encoding not confirmed cross-language for this kind"
    extra = _py_extra_of(prim)
    if extra is not None:
        row["_py_extra"] = extra
    return row


def export_recording(recording: Path, out_path: Path) -> int:
    session = build_session_from_recording(recording)
    row_count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for tick_index in range(len(session)):
            scene = build_scene(session, tick_index)
            for layer in scene.layers:
                for prim in layer.prims:
                    row = export_scene_row(tick_index, scene.t_s, layer.id, prim)
                    f.write(json.dumps(row, ensure_ascii=False))
                    f.write("\n")
                    row_count += 1
    return row_count


def main() -> int:
    reconfigure_console_utf8()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for recording in CORPUS:
        if not recording.is_file():
            print(f"skip: {recording} is absent (partial clone)")
            continue
        out_path = OUT_DIR / f"{recording.stem}.py.ndjson"
        row_count = export_recording(recording, out_path)
        print(f"wrote {out_path} ({row_count} prim-rows, {out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
