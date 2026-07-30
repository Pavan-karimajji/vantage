# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Renders `view/plots.PlotState` (S-B3 slice 10, `sim_visualization_spec.md`
§7.4). `timeseries`/`state` panels reuse `render/timeline.render_timeline`
directly -- a plot's signal/state lanes are drawn exactly like the
timeline strip's, "one address space... timeline, plot panels..." (`NR-SIM-8`)
being one *rendering* path too, not just one resolver. `xy` and
`distribution` are genuinely new (neither has a time axis), so they get
their own functions here.

Same headless matplotlib/`Agg` pattern as `render/bev.py`/`render/timeline.py`
-- Qt enters only at `render/viewer.py`. `xy`/`distribution` do not support
click-to-seek (no `px_to_tick`-style inverse): their axes are scaled to the
*data*, not a fixed `[0, head_tick]`, so the same "one path" click precision
`render/timeline.py` has for `timeseries`/`state` does not carry over
without a second geometry to keep in sync -- `UT-B3-9` is satisfied by the
lane-based panel types, which already have it.
"""

from __future__ import annotations

import io as _io

import matplotlib

matplotlib.use("Agg")  # headless: must work with no display, must be set before pyplot import
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

_BG = "#1a1a19"
_FG = "#dddddd"
_POINT_COLOR = "#7fb0ff"
_PLAYHEAD_COLOR = "#ffffff"


def _figure(size_px: tuple[int, int], dpi: int = 100):
    fig = plt.figure(figsize=(size_px[0] / dpi, size_px[1] / dpi), dpi=dpi)
    fig.patch.set_facecolor(_BG)
    ax = fig.add_axes((0.08, 0.08, 0.90, 0.88))  # small margin: real axis ticks/labels, unlike render/timeline.py
    ax.set_facecolor(_BG)
    ax.tick_params(colors=_FG, labelsize=6)
    for spine in ax.spines.values():
        spine.set_color(_FG)
    return fig, ax


def _to_array(fig, dpi: int) -> np.ndarray:
    buffer = _io.BytesIO()
    fig.savefig(buffer, format="raw", dpi=dpi)
    buffer.seek(0)
    width, height = fig.canvas.get_width_height()
    array = np.frombuffer(buffer.getvalue(), dtype=np.uint8).reshape((height, width, 4))
    plt.close(fig)
    return array[:, :, :3]


def render_xy(
    x_series: tuple[tuple[int, float], ...],
    y_series: tuple[tuple[int, float], ...],
    color_series: tuple[tuple[int, float], ...] | None,
    current_tick: int,
    size_px: tuple[int, int],
) -> np.ndarray:
    """`xy` (§7.4): `y` vs `x`, paired by tick index (both resolved from
    the same session, so their tick indices match); optionally coloured by
    a third signal. The current tick's own point is highlighted, not
    click-seekable (this module's own docstring)."""
    fig, ax = _figure(size_px)
    x_by_tick = dict(x_series)
    y_by_tick = dict(y_series)
    color_by_tick = dict(color_series) if color_series is not None else None
    ticks = [t for t in x_by_tick if t in y_by_tick]
    xs = [x_by_tick[t] for t in ticks]
    ys = [y_by_tick[t] for t in ticks]
    if color_by_tick is not None:
        colors = [color_by_tick.get(t, 0.0) for t in ticks]
        scatter = ax.scatter(xs, ys, c=colors, cmap="viridis", s=10)
        fig.colorbar(scatter, ax=ax).ax.tick_params(colors=_FG, labelsize=6)
    else:
        ax.plot(xs, ys, color=_POINT_COLOR, linewidth=1.0, marker="o", markersize=2)
    if current_tick in y_by_tick and current_tick in x_by_tick:
        ax.scatter([x_by_tick[current_tick]], [y_by_tick[current_tick]],
                   color=_PLAYHEAD_COLOR, s=40, zorder=5, edgecolors="black")
    return _to_array(fig, dpi=100)


def render_distribution(
    values: tuple[float, ...],
    current_value: float | None,
    size_px: tuple[int, int],
    *,
    bins: int = 20,
) -> np.ndarray:
    """`distribution` (§7.4): a signal's spread over the whole session (the
    single-session reading of "over a whole run" -- a scenario-*set*
    distribution, e.g. onset time across many recordings, is `S-D`
    Campaign territory and needs more than one `Session` in scope, not
    built here)."""
    fig, ax = _figure(size_px)
    if values:
        ax.hist(values, bins=bins, color=_POINT_COLOR, edgecolor=_BG)
    if current_value is not None:
        ax.axvline(current_value, color=_PLAYHEAD_COLOR, linewidth=1.2)
    return _to_array(fig, dpi=100)
