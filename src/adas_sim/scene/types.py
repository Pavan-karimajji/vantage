# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`Prim`, `Layer`, `Scene` -- the central IR (R-SIM-2, sim_api_reference.md
§5, sim_visualization_spec.md §2, sim_architecture.md §5.3). Everything
upstream produces a `Scene`; everything downstream consumes it. A `Prim`
never carries a colour, a pixel coordinate or a viewport reference -- only
metres, a named frame and a semantic style token.

**Design note.** `sim_api_reference.md` §5 shows a narrower, 7-kind `Prim`
with a generic `coords: tuple[float, ...]` and no `pick_id`/`z`/`alpha` --
which cannot represent a `Heatmap` (a 2D array) or `Image` (bytes) at all.
`sim_visualization_spec.md` §2 and `sim_architecture.md` §5.3 (the master
design doc) both specify the richer 11-kind catalogue below instead; that
catalogue is what is implemented here, and api reference §5 is corrected in
the same commit (`GT-7`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from adas_sim.core.errors import AuthoringError
from adas_sim.scene.frames import is_known_frame, known_frame_kinds

#: Closed set (sim_visualization_spec.md §2). Adding a kind is a framework
#: change and needs a reason; a layer provider composes something new from
#: these rather than inventing a twelfth.
PrimKind = Literal[
    "polyline", "polygon", "box", "circle", "ellipse",
    "points", "arrow", "text", "grid", "heatmap", "image",
]
_KNOWN_KINDS = frozenset(PrimKind.__args__)  # type: ignore[attr-defined]

#: A style token is never a colour (R-SIM-2). This catches the mechanical,
#: unambiguous case -- a literal "#rrggbb"/"#rgb"/"#rrggbbaa" -- at
#: construction time, with no dependency on render/ (UT-A3-11). A token that
#: is merely *unregistered* (e.g. "bogus.token") is a different, later check:
#: render/theme.py's resolver owns the registered-token-table lookup, because
#: scene/ must not import render/ (this module's own "Must not").
_HEX_STYLE = re.compile(r"^#[0-9a-fA-F]{3}$|^#[0-9a-fA-F]{6}$|^#[0-9a-fA-F]{8}$")

SCENE_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class Prim:
    """One drawable primitive. Every field beyond `kind` and the five
    universal ones is `None` unless `kind` uses it -- there is no dataclass
    subclass per kind (`sim_architecture.md` §5.3's own sketch: "one of:
    Polyline Polygon Box Circle Points Text Arrow Grid Heatmap Image"), which
    is also what lets `UT-B1-10` hit-test through one path rather than one
    per prim type.
    """

    kind: PrimKind

    # -- universal (every kind) --------------------------------------------
    frame: str = "ego"
    style: str = ""
    pick_id: str | None = None
    z: int = 0
    alpha: float = 1.0
    #: The only two pixel fields that exist at all -- legibility (line
    #: weight, label offset) is not physical (R-SIM-2).
    width_px: float | None = None
    offset_px: tuple[float, float] | None = None

    # -- polyline / polygon / points -----------------------------------------
    points_m: tuple[tuple[float, float], ...] | None = None
    closed: bool = False                    # polyline
    filled: bool = True                     # polygon
    hatch: str | None = None                # polygon
    marker: str | None = None               # points

    # -- box / circle / ellipse (a centre-based shape) -----------------------
    cx_m: float | None = None
    cy_m: float | None = None
    length_m: float | None = None           # box
    width_m: float | None = None            # box
    yaw_rad: float | None = None            # box, ellipse
    height_m: float | None = None           # box (optional; image renderer only)
    r_m: float | None = None                # circle
    a_m: float | None = None                # ellipse semi-major
    b_m: float | None = None                # ellipse semi-minor

    # -- arrow / text (an origin-based shape) --------------------------------
    x_m: float | None = None
    y_m: float | None = None
    dx_m: float | None = None               # arrow
    dy_m: float | None = None               # arrow
    text: str | None = None                 # text
    anchor: str | None = None               # text

    # -- grid -----------------------------------------------------------------
    spacing_m: float | None = None
    extent_m: float | None = None

    # -- heatmap ----------------------------------------------------------------
    x0_m: float | None = None
    y0_m: float | None = None
    cell_dx_m: float | None = None
    cell_dy_m: float | None = None
    values: tuple[tuple[float, ...], ...] | None = None

    # -- image (renderer-specific payload) --------------------------------------
    data: bytes | None = None
    format: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _KNOWN_KINDS:
            raise AuthoringError(
                expected=f"one of {sorted(_KNOWN_KINDS)}", found=repr(self.kind),
                where="Prim.kind", hint="the prim catalogue is closed (sim_visualization_spec.md §2)",
            )
        if not is_known_frame(self.frame):
            raise AuthoringError(
                expected=f"a known frame: {', '.join(known_frame_kinds())}", found=repr(self.frame),
                where="Prim.frame", hint="R-COORD-1: default is 'ego'",
            )
        if _HEX_STYLE.match(self.style):
            raise AuthoringError(
                expected="a semantic style token, e.g. 'zone.entry'", found=repr(self.style),
                where="Prim.style",
                hint="style is never a colour (R-SIM-2) -- register or use a semantic token instead",
            )

    def __repr__(self) -> str:
        return f"<Prim kind={self.kind!r} frame={self.frame!r} style={self.style!r}>"


@dataclass(frozen=True, slots=True)
class Layer:
    """One named, independently toggleable group of prims."""

    id: str
    group: str
    prims: tuple[Prim, ...] = ()
    label: str = ""
    z: int = 0
    #: 1 always-on .. 3 internal debug (sim_api_reference.md §5).
    level: int = 1
    default_on: bool = True
    #: R-SIM-7's stopgap marker: reconstructed from calibration rather than a
    #: real debug port, never a silent one.
    derived: bool = False

    def __repr__(self) -> str:
        return f"<Layer {self.id!r} group={self.group!r} prims={len(self.prims)}>"


@dataclass(frozen=True, slots=True)
class Scene:
    """What to draw for one tick (sim_architecture.md §5.3). `version` is
    `major.minor`; additive is minor (`scene/codec.py`)."""

    version: str = SCENE_VERSION
    t_s: float = 0.0
    layers: tuple[Layer, ...] = ()

    def __repr__(self) -> str:
        return f"<Scene v{self.version} t_s={self.t_s:.3f} layers={len(self.layers)}>"
