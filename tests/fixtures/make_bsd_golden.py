# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Generates the S-B1 golden: the `Scene` (encoded via `scene/codec.py`, the
same protobuf codec `S-A3` built) for a fixed sample of ticks from a real
recording, replayed through every `modules/df/sim/layers/{common,bsd}.py`
provider. Never hand-crafted -- regenerate with
`python tests/fixtures/make_bsd_golden.py` (needs `modules/interfaces`
built, for the generated bindings used to construct/decode messages).
"""

from __future__ import annotations

import sys
from pathlib import Path

_SIM_ROOT = Path(__file__).resolve().parents[2]
_MODULES_ROOT = _SIM_ROOT.parent
_DF_ROOT = _MODULES_ROOT / "df"
_SRC = _SIM_ROOT / "src"
for _p in (_SRC, _DF_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from adas_sim.core.console import reconfigure_console_utf8  # noqa: E402
from adas_sim.core.history import FrameTree, HistoryView, LayerCtx  # noqa: E402
from adas_sim.core.runner import build_session_from_recording  # noqa: E402
from adas_sim.model.project import ProjectModel  # noqa: E402
from adas_sim.scene import default_layers  # noqa: E402
from adas_sim.scene.codec import encode_scene  # noqa: E402
from adas_sim.scene.types import Scene  # noqa: E402
from sim.layers import bsd, common  # noqa: E402

RECORDING = _DF_ROOT / "tests" / "carla_testruns" / "exports" / "bsd_curve_r172_passby_20260727_213847.mcap"
OUT_DIR = Path(__file__).resolve().parent / "golden"
SAMPLE_TICKS = (0, 50, 100, 162, -1)  # -1: the last tick

# `frame`/`ego`/`trail` moved to the framework's own default layer set
# (`AR-52`, 2026-08-07, `adas_sim.scene.default_layers`) -- `df` only
# contributes `objects`/`hud` now.
_PROVIDERS = (
    default_layers.frame_layer, default_layers.ego_layer, common.objects_layer,
    default_layers.trail_layer, common.hud_layer, bsd.zone_layer, bsd.warning_layer,
)


def build_scene(session, tick_index: int, project: str = "base") -> Scene:
    index = tick_index if tick_index >= 0 else len(session) + tick_index
    ctx = LayerCtx(
        model=ProjectModel.resolve(project=project),
        history=HistoryView(_ticks=tuple(session.ticks[: index + 1])),
        frames=FrameTree(session.at(index).pose),
        known_ports=session.known_ports,
    )
    layers = [layer for provider in _PROVIDERS for layer in provider(ctx)]
    return Scene(t_s=session.at(index).t_s, layers=tuple(layers))


def main() -> int:
    reconfigure_console_utf8()
    if not RECORDING.is_file():
        print(f"skip: {RECORDING} is absent (partial clone)")
        return 0
    session = build_session_from_recording(RECORDING)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for tick_index in SAMPLE_TICKS:
        scene = build_scene(session, tick_index)
        index = tick_index if tick_index >= 0 else len(session) + tick_index
        out_path = OUT_DIR / f"bsd_tick{index}.scene.bin"
        out_path.write_bytes(encode_scene(scene))
        print(f"wrote {out_path} ({out_path.stat().st_size} bytes, tick {index})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
