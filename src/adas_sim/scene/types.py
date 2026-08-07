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

from adas_sim.core.errors import AuthoringError, ContractError
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

#: Small geometry only (`NR-SIM-43`, arch §5.3, `OD-7`). Above this many
#: inline elements -- points in `points_m`, cells in `values`, bytes in
#: `data` -- a provider must carry a `BulkRef` instead of inlining, checked
#: in `Layer.__post_init__` because a `Prim` does not know its layer. Fixed
#: here, as a stated figure, so `NR-SIM-5` is falsifiable rather than a magic
#: literal (`sim_implementation_plan.md` S-A3Δ, `GT-13`).
MAX_INLINE_PRIM_ELEMENTS = 2000


@dataclass(frozen=True, slots=True)
class BulkRef:
    """A coordinate into the recording, never a second storage mechanism
    (`NR-SIM-43`, arch §5.3). A `Prim` carrying this is a *reference* --
    resolved by the renderer from the recording at draw time -- not a second
    copy of the payload, so a `Scene` stays serializable.
    """

    topic: str
    log_time_ns: int
    field: str = ""
    count: int = 0
    encoding: str = ""


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
    #: `AR-56` (2026-08-07): the lateral (world-y) grid line spacing, when it
    #: legitimately differs from `spacing_m` (world-x) -- `None` means "same
    #: as `spacing_m`". Not a new kind (the closed catalogue above is
    #: unchanged): a grid with denser cross-lines at close range is still
    #: one grid, the same way `width_px`/`offset_px` are optional per-kind
    #: legibility fields already. The renderer, not the provider, decides
    #: WHERE a grid's coordinate labels are drawn (R-SIM-2) -- this field is
    #: only the physical fact of a second spacing for it to read.
    spacing_lateral_m: float | None = None

    # -- heatmap ----------------------------------------------------------------
    x0_m: float | None = None
    y0_m: float | None = None
    cell_dx_m: float | None = None
    cell_dy_m: float | None = None
    values: tuple[tuple[float, ...], ...] | None = None

    # -- image (renderer-specific payload) --------------------------------------
    data: bytes | None = None
    format: str | None = None

    #: A coordinate into the recording for bulk geometry too large to inline
    #: (`NR-SIM-43`) -- the renderer resolves it at draw time instead.
    bulk: BulkRef | None = None

    #: R-SIM-7's stopgap marker at prim granularity: this prim was
    #: reconstructed from calibration rather than published by the SUT. A
    #: layer legitimately mixes real and derived prims, which is why this
    #: exists alongside (not instead of) `Layer.derived` (`OD-6`, arch §5.19).
    derived: bool = False

    #: Ordered (name, formatted value) pairs for the inspector panel
    #: (`sim_visualization_spec.md` §7.2) -- **declared, not dumped**: the
    #: provider that built this prim already had the raw entity in hand, so
    #: it computes these inline, the same pass, rather than a separate
    #: registry resolving a `pick_id` back to a value later (`S-A3`'s
    #: `@inspector_fields` tried the latter and was never wired up -- "the
    #: renderer hit-tests the prims it actually drew, so the two cannot
    #: disagree" (§7.1), extended here: the prim that carries the values is
    #: the prim that was drawn). Only meaningful alongside `pick_id`.
    fields: tuple[tuple[str, str], ...] | None = None

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
        if self.fields is not None and self.pick_id is None:
            raise AuthoringError(
                expected="pick_id set whenever fields is (fields with nothing to attach it to is dead data)",
                found="fields set, pick_id is None",
                where="Prim.fields", hint="give the prim a pick_id, or drop fields",
            )
        if _HEX_STYLE.match(self.style):
            raise AuthoringError(
                expected="a semantic style token, e.g. 'zone.entry'", found=repr(self.style),
                where="Prim.style",
                hint="style is never a colour (R-SIM-2) -- register or use a semantic token instead",
            )

    def __repr__(self) -> str:
        return f"<Prim kind={self.kind!r} frame={self.frame!r} style={self.style!r}>"


def _inline_element_count(prim: Prim) -> int:
    """Elements actually inlined in `prim` -- points, heatmap cells, or image
    bytes -- the quantity `MAX_INLINE_PRIM_ELEMENTS` budgets (`NR-SIM-43`). A
    prim referencing its payload via `bulk` instead carries none of these.
    """

    if prim.points_m is not None:
        return len(prim.points_m)
    if prim.values is not None:
        return sum(len(row) for row in prim.values)
    if prim.data is not None:
        return len(prim.data)
    return 0


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

    #: `AR-53`: set (to the unresolved `self.<port>` reference, human-
    #: readable) when a `requires=` entry never binds to any port this run
    #: -- never a value any single ProPort published, so this layer carries
    #: NO prims (`__post_init__` enforces it) and exists only to be named
    #: and greyed in the layer list, instead of vanishing (`scene/
    #: registry.py`'s own `gated()`, the one place this is set). Distinct
    #: from the ordinary "no port yet this tick" case, which stays silently
    #: absent on purpose (`view/layers.py`'s own `LayerTreeState.sync`
    #: docstring) -- that one is transient and will populate; this one is
    #: structural and will not, until the recording or the pipeline changes.
    unavailable: str | None = None

    #: `S-D4`'s ground_truth/perception/perception.error group convention --
    #: framework-generic, not any one component's; R-SIM-1's banned-string
    #: grep names specific function ids, never a role vocabulary this general.
    #: An `.error` group's own layer is, by construction, a comparison
    #: between two SEPARATE sources (a truth and an estimate) -- never a
    #: value any single ProPort published -- so it is always a
    #: reconstruction (R-SIM-7). Generalised to the suffix, not the one
    #: literal `"perception.error"`, because the reasoning already was: a
    #: `perception-core` split into computer-vision + fusion would move the
    #: real error group to `"fusion.error"` (`FR-SIM-71`), and a rule keyed
    #: to today's one name would silently stop applying at exactly the
    #: moment the decomposition it exists to survive actually happens.
    _DERIVED_GROUP_SUFFIX = ".error"

    def __post_init__(self) -> None:
        if self.unavailable is not None and self.prims:
            raise AuthoringError(
                expected="a Layer(unavailable=...) to carry no prims -- nothing was published to draw",
                found=f"{len(self.prims)} prim(s) alongside unavailable={self.unavailable!r}",
                where=f"Layer.__post_init__ (layer={self.id!r})",
                hint="an unavailable layer names its own absence; it never also draws something (R-SIM-7)",
            )
        if self.group.endswith(self._DERIVED_GROUP_SUFFIX) and not self.derived:
            raise AuthoringError(
                expected=f"a Layer(group={self.group!r}) ending {self._DERIVED_GROUP_SUFFIX!r} to be derived=True",
                found=f"Layer(group={self.group!r}, derived=False)",
                where=f"Layer.__post_init__ (layer={self.id!r})",
                hint="an *.error group's own layer is always a reconstructed "
                     "comparison, never a value any single port published (R-SIM-7)",
            )
        for prim in self.prims:
            if prim.derived and not self.derived:
                raise AuthoringError(
                    expected="a Layer(derived=False) contains only derived=False prims",
                    found=f"a {prim.kind!r} prim with derived=True",
                    where=f"Layer.__post_init__ (layer={self.id!r})",
                    hint="mark the layer derived=True, or stop reconstructing this prim (R-SIM-7, OD-6)",
                )
            count = _inline_element_count(prim)
            if count > MAX_INLINE_PRIM_ELEMENTS:
                raise ContractError(
                    expected=f"inline geometry <= {MAX_INLINE_PRIM_ELEMENTS} elements (NR-SIM-43)",
                    found=f"{count} elements in a {prim.kind!r} prim",
                    where=f"Layer.__post_init__ (layer={self.id!r})",
                    hint="reference bulk data with Prim.bulk (a BulkRef) instead of inlining it",
                )

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
