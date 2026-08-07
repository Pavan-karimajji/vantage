# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The **Qt-independent** Scene-to-raster core (S-B1 checklist) -- testable
headless and reusable by the image renderer. Qt enters at `S-B3` and never
below this line; this module uses matplotlib's `Agg` backend, which needs no
display (`P-7`-style headless discipline, though `P-7` itself is about Qt).

Draws every prim kind in `scene/types.py`'s closed catalogue via matplotlib
patches, resolving `style` tokens through `render/theme.py` -- the one place
outside `theme.py` itself allowed to turn a token into a colour.
"""

from __future__ import annotations

import io as _io
from collections.abc import Sequence

import matplotlib

matplotlib.use("Agg")  # headless: must work with no display, and must be set before pyplot import
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from adas_sim.render.theme import Theme, resolve  # noqa: E402
from adas_sim.scene.types import Layer, Prim, Scene  # noqa: E402
from adas_sim.view.viewport import Viewport  # noqa: E402


def _visible_prims(scene: Scene, layer_selection: frozenset[str] | None) -> list[tuple[Layer, Prim]]:
    pairs = []
    for layer in scene.layers:
        if layer_selection is not None and layer.id not in layer_selection:
            continue
        for prim in layer.prims:
            pairs.append((layer, prim))
    pairs.sort(key=lambda pair: (pair[1].z, pair[0].z))
    return pairs


#: `AR-56`: two text labels closer than this in SCREEN pixels
#: are a collision -- the second one is dropped rather than drawn on top of
#: the first. A rough footprint, not real text metrics (`ax.text`'s actual
#: rendered extent needs a draw pass to query); good enough to stop the
#: worst case -- two labels stacked unreadably on each other -- without a
#: second rendering pass. Tuned to roughly half an 8pt label's own width.
_LABEL_COLLISION_RADIUS_PX = 18.0


def _draw_text_avoiding_collisions(
    ax, x_m: float, y_m: float, text: str, *, color: str, fontsize: float, zorder: float,
    occupied_px: list[tuple[float, float]] | None, ha: str = "left", va: str = "baseline",
) -> None:
    """The one place any label reaches the canvas -- grid distance
    labels and ordinary `text` prims both go through this, so a grid label
    and an object label mutually avoid each other rather than each having
    its own, inconsistent notion of "too close". `occupied_px=None` (the
    overlay/HUD-text call sites, and any caller predating this) skips the
    check entirely -- opt-in, not a behaviour change for existing callers
    that never populate it."""
    if occupied_px is not None:
        # world (y_m, x_m) -> the SAME (horizontal, vertical) convention
        # every other call in this module plots with -- ax.transData is
        # already configured with this frame's xlim/ylim.
        px, py = ax.transData.transform((y_m, x_m))
        for ox, oy in occupied_px:
            if (px - ox) ** 2 + (py - oy) ** 2 < _LABEL_COLLISION_RADIUS_PX ** 2:
                return
        occupied_px.append((px, py))
    ax.text(y_m, x_m, text, color=color, fontsize=fontsize, zorder=zorder, ha=ha, va=va)


def _draw_prim(ax, prim: Prim, theme: Theme, selected: bool = False,
                occupied_px: list[tuple[float, float]] | None = None) -> None:
    style = resolve(prim.style, theme) if prim.style else None
    color = style.color if style else "#888888"
    if selected:
        # §7.1: "selected prims get object.selected styling plus a halo" --
        # the halo is generic (any kind, via _prim_bounds_m below), the same
        # one-path reasoning UT-B1-10's hit_test already relies on.
        color = resolve("object.selected", theme).color

    if prim.kind in ("polyline", "polygon", "points") and prim.points_m:
        xs = [p[0] for p in prim.points_m]
        ys = [p[1] for p in prim.points_m]
        if prim.kind == "points":
            ax.scatter(ys, xs, color=color, s=12, zorder=prim.z)
        elif prim.kind == "polygon":
            # facecolor="none" for an unfilled polygon -- ax.fill(alpha=0)
            # would zero the EDGE's alpha too, making the outline invisible
            # (found by looking at a render, not by reasoning about the code).
            ax.add_patch(mpatches.Polygon(
                list(zip(ys, xs)), closed=True,
                facecolor=color if prim.filled else "none",
                edgecolor=color, alpha=prim.alpha, linewidth=(prim.width_px or 1.5) / 1.5, zorder=prim.z,
            ))
        else:
            if prim.closed and xs:
                xs, ys = [*xs, xs[0]], [*ys, ys[0]]
            ax.plot(ys, xs, color=color, linewidth=(prim.width_px or 1.0) / 2, zorder=prim.z, alpha=prim.alpha)
    elif prim.kind == "box" and None not in (prim.cx_m, prim.cy_m, prim.length_m, prim.width_m):
        half_l, half_w = prim.length_m / 2.0, prim.width_m / 2.0
        corners_x = [-half_l, half_l, half_l, -half_l]
        corners_y = [-half_w, -half_w, half_w, half_w]
        yaw = prim.yaw_rad or 0.0
        cos_y, sin_y = np.cos(yaw), np.sin(yaw)
        world = [
            (prim.cx_m + cx * cos_y - cy * sin_y, prim.cy_m + cx * sin_y + cy * cos_y)
            for cx, cy in zip(corners_x, corners_y)
        ]
        ax.fill([w[1] for w in world], [w[0] for w in world], color=color, alpha=prim.alpha, zorder=prim.z,
                edgecolor=color)
    elif prim.kind == "circle" and None not in (prim.cx_m, prim.cy_m, prim.r_m):
        ax.add_patch(mpatches.Circle((prim.cy_m, prim.cx_m), prim.r_m, color=color, fill=False,
                                      linewidth=(prim.width_px or 1.5) / 1.5, zorder=prim.z, alpha=prim.alpha))
    elif prim.kind == "arrow" and None not in (prim.x_m, prim.y_m, prim.dx_m, prim.dy_m):
        ax.annotate("", xy=(prim.y_m + prim.dy_m, prim.x_m + prim.dx_m), xytext=(prim.y_m, prim.x_m),
                    arrowprops=dict(arrowstyle="->", color=color), zorder=prim.z)
    elif prim.kind == "text" and prim.text and None not in (prim.x_m, prim.y_m):
        _draw_text_avoiding_collisions(
            ax, prim.x_m, prim.y_m, prim.text, color=color, fontsize=8, zorder=prim.z, occupied_px=occupied_px,
        )
    elif prim.kind == "grid" and prim.spacing_m and prim.extent_m:
        n = int(prim.extent_m / prim.spacing_m)
        for i in range(-n, n + 1):
            d = i * prim.spacing_m
            ax.axhline(d, color=color, linewidth=0.4, alpha=0.5, zorder=prim.z)
        spacing_lateral_m = prim.spacing_lateral_m or prim.spacing_m
        n_lateral = int(prim.extent_m / spacing_lateral_m)
        for i in range(-n_lateral, n_lateral + 1):
            d = i * spacing_lateral_m
            ax.axvline(d, color=color, linewidth=0.4, alpha=0.5, zorder=prim.z)
        # `AR-56`: distance labels anchored near the frame
        # MARGIN, never the crosshair -- the whole point of the fix (used
        # to sit at a fixed small offset from the origin, directly on the
        # ego box). Legible at any pan/zoom because it is computed from
        # the CURRENT visible extent (`ax.get_xlim`/`get_ylim`), which only
        # the renderer -- never a layer provider, R-SIM-2 -- may read. A
        # label is only drawn for a grid line actually crossing the
        # visible frame on the other axis; an off-screen line's label
        # would render nowhere useful anyway.
        x_left, x_right = ax.get_xlim()   # world-y, screen-horizontal, inverted (left > right)
        y_bottom, y_top = ax.get_ylim()   # world-x, screen-vertical
        margin_frac = 0.04
        label_y_at_edge = x_right + margin_frac * (x_left - x_right)   # inset from the right screen edge
        label_x_at_edge = y_bottom + margin_frac * (y_top - y_bottom)  # inset from the bottom screen edge
        # A label whose own anchor sits too close to the FRAME edge (not
        # the margin line above -- the actual raster boundary) draws half
        # off-canvas, unreadable rather than merely tight. `ha="center"`
        # labels (the lateral row) are the ones this actually bites --
        # inset the visibility check itself by a small band, not just the
        # anchor position, so the outermost label is skipped rather than
        # clipped.
        clip_x_m = 0.03 * abs(x_left - x_right)
        clip_y_m = 0.03 * (y_top - y_bottom)
        for i in range(-n, n + 1):
            d = i * prim.spacing_m
            if y_bottom + clip_y_m <= d <= y_top - clip_y_m:
                _draw_text_avoiding_collisions(
                    ax, d, label_y_at_edge, f"{d:.0f}", color=color, fontsize=7, zorder=prim.z,
                    occupied_px=occupied_px, ha="right", va="center",
                )
        for i in range(-n_lateral, n_lateral + 1):
            d = i * spacing_lateral_m
            if min(x_left, x_right) + clip_x_m <= d <= max(x_left, x_right) - clip_x_m:
                _draw_text_avoiding_collisions(
                    ax, label_x_at_edge, d, f"{d:.0f}", color=color, fontsize=7, zorder=prim.z,
                    occupied_px=occupied_px, ha="center", va="bottom",
                )
    elif prim.kind == "heatmap" and prim.values:
        arr = np.array(prim.values)
        extent = (prim.y0_m, prim.y0_m + arr.shape[1] * prim.cell_dy_m,
                  prim.x0_m, prim.x0_m + arr.shape[0] * prim.cell_dx_m)
        ax.imshow(arr, extent=extent, origin="lower", alpha=prim.alpha, zorder=prim.z, cmap="viridis")

    if selected:
        bounds = _prim_bounds_m(prim)
        if bounds is not None:
            x_min, y_min, x_max, y_max = bounds
            margin_m = 0.15
            ax.add_patch(mpatches.Rectangle(
                (y_min - margin_m, x_min - margin_m),
                (y_max - y_min) + 2 * margin_m, (x_max - x_min) + 2 * margin_m,
                fill=False, edgecolor=color, linestyle="--", linewidth=1.5, zorder=prim.z + 0.5,
            ))


def _draw_scene_figure(scene: Scene, viewport: Viewport, theme: Theme,
                        layer_selection: frozenset[str] | None,
                        selection: frozenset[str],
                        overlay_prims: tuple[Prim, ...],
                        hud_lines: tuple[str, ...],
                        stale_banner: str | None, dpi: int) -> plt.Figure:
    """The one drawing path (`S-B4`'s `D5`: never two rendering stacks with
    no shared vocabulary) -- `render_scene` (raster) and `render_scene_vector`
    (`S-B4`'s print/vector capture) both call this and differ only in how
    the resulting `Figure` is written out."""
    fig = plt.figure(figsize=(viewport.size_px[0] / dpi, viewport.size_px[1] / dpi), dpi=dpi)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(*_x_axis_limits(viewport))
    ax.set_ylim(*_y_axis_limits(viewport))
    ax.axis("off")
    fig.patch.set_facecolor("#1a1a19" if theme == "dark" else "#fcfcfb")
    ax.set_facecolor(fig.patch.get_facecolor())

    # `AR-56`: one shared list for the whole frame, so a grid label and an
    # object label -- drawn from entirely different providers -- still
    # avoid each other (`_draw_text_avoiding_collisions`). Z-order already
    # decides paint order (`_visible_prims`' own sort); collision order
    # follows the same sequence, so a higher-`z` label wins a contested spot.
    occupied_px: list[tuple[float, float]] = []
    for _layer, prim in _visible_prims(scene, layer_selection):
        _draw_prim(ax, prim, theme, selected=prim.pick_id in selection, occupied_px=occupied_px)
    for prim in overlay_prims:
        _draw_prim(ax, prim, theme, occupied_px=occupied_px)

    hud_color = "#dddddd" if theme == "dark" else "#333333"
    for i, line in enumerate(hud_lines):
        ax.text(0.99, 0.99 - i * 0.045, line, transform=ax.transAxes, ha="right", va="top",
                fontsize=7, color=hud_color, zorder=1000)
    if stale_banner:
        ax.text(0.5, 0.98, stale_banner, transform=ax.transAxes, ha="center", va="top",
                fontsize=9, color="#ff5555", zorder=1001,
                bbox={"facecolor": "#1a1a19" if theme == "dark" else "#fcfcfb", "alpha": 0.75, "edgecolor": "none"})
    return fig


def render_scene(scene: Scene, viewport: Viewport, theme: Theme,
                  layer_selection: frozenset[str] | None = None,
                  selection: frozenset[str] = frozenset(),
                  overlay_prims: tuple[Prim, ...] = (),
                  hud_lines: tuple[str, ...] = (),
                  stale_banner: str | None = None) -> np.ndarray:
    """`Scene` + `Viewport` + `theme` -> an RGB raster array (H, W, 3),
    uint8. Pure function of its arguments -- no window, no state held
    between calls (headless, `ST-B1-3`). `selection` (`Interaction.selection`,
    `pick_id`s) drives §7.1's styling-plus-halo; defaults to none selected,
    so every caller predating `S-B3` slice 5 renders unchanged. `overlay_prims`
    (`view/measure.MeasureState.overlay_prims()`, §8) draw last, always on
    top, through the same `_draw_prim` every layer provider's own prims go
    through -- ruler/range-rings/annotations are ordinary `Prim`s, not a
    second drawing path; defaults to none, so every caller predating `S-B3`
    slice 11 renders unchanged.

    `hud_lines`/`stale_banner` (`view/hud.py`, §10) are drawn in **screen
    space** (`ax.transAxes`), not world metres -- HUD furniture must stay
    fixed top-right regardless of pan/zoom, which a `Prim` (always
    world-space) cannot do; this is why the HUD is not just more
    `overlay_prims`. Both default to nothing, so every caller predating
    `S-B3` slice 12 renders unchanged."""
    dpi = 100
    fig = _draw_scene_figure(
        scene, viewport, theme, layer_selection, selection, overlay_prims, hud_lines, stale_banner, dpi,
    )
    buffer = _io.BytesIO()
    fig.savefig(buffer, format="raw", dpi=dpi)
    buffer.seek(0)
    width, height = fig.canvas.get_width_height()
    array = np.frombuffer(buffer.getvalue(), dtype=np.uint8).reshape((height, width, 4))
    plt.close(fig)
    return array[:, :, :3]  # drop alpha


def render_scene_vector(scene: Scene, viewport: Viewport, theme: Theme,
                         layer_selection: frozenset[str] | None = None,
                         selection: frozenset[str] = frozenset(),
                         overlay_prims: tuple[Prim, ...] = (),
                         hud_lines: tuple[str, ...] = (),
                         stale_banner: str | None = None, *,
                         fmt: str = "svg") -> bytes:
    """`S-B4`'s print variant: the same `Scene` through the same drawing
    path as `render_scene` (`D5`), written out as a vector format instead of
    a raster -- `fmt` is any format matplotlib's own `Figure.savefig`
    accepts (`"svg"`, `"pdf"`); `render/capture.py` picks it from the
    output path's own suffix, never guessed here."""
    dpi = 100
    fig = _draw_scene_figure(
        scene, viewport, theme, layer_selection, selection, overlay_prims, hud_lines, stale_banner, dpi,
    )
    buffer = _io.BytesIO()
    fig.savefig(buffer, format=fmt, dpi=dpi)
    plt.close(fig)
    return buffer.getvalue()


def _x_axis_limits(viewport: Viewport) -> tuple[float, float]:
    """matplotlib's `ax.set_xlim` -- screen-horizontal, which shows **world
    Y** (every prim is plotted `ax.plot(ys, xs, ...)`), spanning canvas
    **width**. Inverted: `+y` is left (R-COORD-1), so a higher world-Y must
    land on the LEFT of the screen, i.e. the first limit is the larger
    value. (Found wrong the first time -- this function and
    `_y_axis_limits` had their spans and axes swapped, which silently
    flipped left/right in a rendered scene without raising anything.)
    """
    half_span_m = (viewport.size_px[0] / 2.0) / viewport.scale_px_per_m
    return (viewport.centre_m[1] + half_span_m, viewport.centre_m[1] - half_span_m)


def _y_axis_limits(viewport: Viewport) -> tuple[float, float]:
    """matplotlib's `ax.set_ylim` -- screen-vertical, which shows **world
    X** (forward), spanning canvas **height**. Not inverted: matplotlib's
    y-axis already increases upward, matching "forward is up"."""
    half_span_m = (viewport.size_px[1] / 2.0) / viewport.scale_px_per_m
    return (viewport.centre_m[0] - half_span_m, viewport.centre_m[0] + half_span_m)


def _prim_bounds_m(prim: Prim) -> tuple[float, float, float, float] | None:
    """A generic (not per-kind) bounding box in world metres, for hit
    testing -- the one thing every kind can produce, so `hit_test` below is
    one path, not one per prim type (`UT-B1-10`).

    **Known imprecision, deliberately not fixed here:** an axis-aligned
    bounding box over-approximates a diagonal `polyline`/`polygon` --
    a point well clear of the visible line can still fall inside its bbox
    and register a hit. Precise per-kind distance testing would remove
    this, at the cost of the one-path property this exists for; acceptable
    for a BEV of mostly axis-following boxes and circles, revisit if a real
    diagonal-heavy layer makes it a problem in practice.
    """
    if prim.kind == "box" and None not in (prim.cx_m, prim.cy_m, prim.length_m, prim.width_m):
        half_l, half_w = prim.length_m / 2.0, prim.width_m / 2.0
        return (prim.cx_m - half_l, prim.cy_m - half_w, prim.cx_m + half_l, prim.cy_m + half_w)
    if prim.kind == "circle" and None not in (prim.cx_m, prim.cy_m, prim.r_m):
        return (prim.cx_m - prim.r_m, prim.cy_m - prim.r_m, prim.cx_m + prim.r_m, prim.cy_m + prim.r_m)
    if prim.kind in ("polyline", "polygon", "points") and prim.points_m:
        xs = [p[0] for p in prim.points_m]
        ys = [p[1] for p in prim.points_m]
        return (min(xs), min(ys), max(xs), max(ys))
    if prim.kind == "text" and None not in (prim.x_m, prim.y_m):
        return (prim.x_m - 0.3, prim.y_m - 0.3, prim.x_m + 0.3, prim.y_m + 0.3)
    return None


def hit_test(scene: Scene, viewport: Viewport, cursor_px: tuple[float, float],
             layer_selection: frozenset[str] | None = None) -> str | None:
    """The `pick_id` of the topmost prim actually drawn under `cursor_px`,
    or `None`. One path for every prim kind (`UT-B1-10`): compute a bounding
    box in world metres, then a single in-pixel-space containment test."""
    cursor_m = viewport.to_m(*cursor_px)
    best: tuple[int, int, str] | None = None  # (layer.z, prim.z, pick_id) -- topmost wins
    for layer, prim in _visible_prims(scene, layer_selection):
        if prim.pick_id is None:
            continue
        bounds = _prim_bounds_m(prim)
        if bounds is None:
            continue
        x_min, y_min, x_max, y_max = bounds
        if x_min <= cursor_m[0] <= x_max and y_min <= cursor_m[1] <= y_max:
            candidate = (layer.z, prim.z, prim.pick_id)
            if best is None or candidate[:2] >= best[:2]:
                best = candidate
    return best[2] if best else None


def scene_bounds_m(scene: Scene, layer_selection: frozenset[str] | None = None) -> tuple[float, float, float, float] | None:
    """The union of every visible prim's bounds (`_prim_bounds_m`, the same
    generic one-path bbox `hit_test` uses) -- `None` for an empty scene, so
    `Viewport.fitted_to` (`§4.4`, "F to fit") has nothing to fit and a caller
    can decide what "fit an empty scene" means rather than this function
    guessing."""
    x_min = y_min = x_max = y_max = None
    for _layer, prim in _visible_prims(scene, layer_selection):
        bounds = _prim_bounds_m(prim)
        if bounds is None:
            continue
        bx_min, by_min, bx_max, by_max = bounds
        x_min = bx_min if x_min is None else min(x_min, bx_min)
        y_min = by_min if y_min is None else min(y_min, by_min)
        x_max = bx_max if x_max is None else max(x_max, bx_max)
        y_max = by_max if y_max is None else max(y_max, by_max)
    if x_min is None:
        return None
    return (x_min, y_min, x_max, y_max)


def anchor_points_m(
    scene: Scene, layer_selection: frozenset[str] | None = None,
) -> tuple[tuple[float, float], ...]:
    """Every selectable prim's bbox corners + centre (`_prim_bounds_m`, the
    same generic bbox `hit_test` uses) -- ruler snap targets (§8: "snaps to
    prim anchor points (box corners/centres)"). Only prims with a
    `pick_id` count, matching `hit_test`'s own "never a hit on decoration"
    rule -- a snap target should be a real entity, not the grid."""
    points: list[tuple[float, float]] = []
    for _layer, prim in _visible_prims(scene, layer_selection):
        if prim.pick_id is None:
            continue
        bounds = _prim_bounds_m(prim)
        if bounds is None:
            continue
        x_min, y_min, x_max, y_max = bounds
        points.extend([
            (x_min, y_min), (x_min, y_max), (x_max, y_min), (x_max, y_max),
            ((x_min + x_max) / 2.0, (y_min + y_max) / 2.0),
        ])
    return tuple(points)
