# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Renders `view/timeline.TimelineState`'s lanes to a raster (S-B3 slice 8,
`sim_visualization_spec.md` §7.3). Same headless matplotlib/`Agg` pattern as
`render/bev.py` -- Qt enters only at `render/viewer.py`.

Every lane is a **zero-margin** axes stacked to fill the canvas exactly
(`fig.add_axes`, the same trick `render/bev.py`'s single axes uses) rather
than `plt.subplots`' default margins or `tight_layout()` -- those are
data-dependent (a longer label shifts them), which would make a pixel-to-
tick inverse only approximately right. With zero margins the x-axis
(`[0, head_tick]`, fixed for every lane) maps to `[0, size_px[0]]` exactly,
so `px_to_tick` -- click-to-seek's other half in `render/viewer.py`'s
`TimelineStrip` -- is an exact inverse, not a documented imprecision (the
same "one path" reasoning `render/bev.py`'s `hit_test` uses for the BEV,
applied to what "drawn" and "clickable" mean here). Lane names are drawn as
a text overlay (axes-fraction coordinates), not `set_ylabel`, since a real
axis label lives in the margin this module does not have.
"""

from __future__ import annotations

import io as _io

import matplotlib

matplotlib.use("Agg")  # headless: must work with no display, must be set before pyplot import
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from adas_sim.view.timeline import EventMarker  # noqa: E402

_BG = "#1a1a19"
_FG = "#dddddd"
_SIGNAL_COLOR = "#7fb0ff"
_MARKER_COLOR = "#ffb000"
_PLAYHEAD_COLOR = "#ffffff"
_BOOKMARK_COLOR = "#66ff99"
_STATE_BAND_COLOR = "#3c5a80"
_EXPECTATION_PASS_COLOR = "#2ecc71"
_EXPECTATION_FAIL_COLOR = "#e74c3c"


def render_timeline(
    *,
    signal_series: dict[str, tuple[tuple[int, float], ...]],
    state_series: dict[str, tuple[tuple[int, object], ...]],
    markers: dict[str, tuple[EventMarker, ...]],
    bookmark_ticks: tuple[int, ...],
    current_tick: int,
    head_tick: int,
    size_px: tuple[int, int],
    expectation_windows: dict[str, tuple[tuple[int, int, bool], ...]] | None = None,
) -> np.ndarray:
    """One row per lane (signal lanes first, then state lanes), all
    sharing the same fixed `[0, head_tick]` x-axis (`§7.3`'s "synced
    strip"). Pure function of its arguments -- no window, no state held
    between calls, matching `render/bev.render_scene`'s own discipline.

    `expectation_windows`, keyed by the same lane address, is a
    `(start_tick, end_tick, passed)` triple per expectation with a
    drawable span (`check.expect.ExpectationResult.window_s`, already
    converted from seconds by the caller -- this module draws pixels, it
    does not own a `Session` to do that conversion itself, `R-SIM-13`).
    Drawn first, low-alpha, full lane height, so the lane's own signal
    line / state bands / markers sit visibly on top -- "expected windows
    drawn as translucent spans, so a pass/fail is visible rather than
    computed" (`sim_visualization_spec.md` §7.3), green if that
    expectation passed, red if it failed. Several expectations can name
    one signal (a `during:` and a `becomes:` on the same warning port),
    so this is a tuple per address, not a single window.
    """
    expectation_windows = expectation_windows or {}
    lane_names = [*signal_series, *state_series]
    n_lanes = max(1, len(lane_names))
    dpi = 100
    fig = plt.figure(figsize=(size_px[0] / dpi, size_px[1] / dpi), dpi=dpi)
    fig.patch.set_facecolor(_BG)
    x_max = max(head_tick, 1)

    def _new_lane_axes(row: int):
        lane_h = 1.0 / n_lanes
        ax = fig.add_axes((0.0, 1.0 - (row + 1) * lane_h, 1.0, lane_h))
        ax.set_facecolor(_BG)
        ax.set_xlim(0, x_max)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        return ax

    def _draw_expectation_windows(ax, name: str) -> None:
        for start_tick, end_tick, passed in expectation_windows.get(name, ()):
            color = _EXPECTATION_PASS_COLOR if passed else _EXPECTATION_FAIL_COLOR
            ax.axvspan(start_tick, end_tick, color=color, alpha=0.22, zorder=0)

    axes = []
    row = 0
    for name, series in signal_series.items():
        ax = _new_lane_axes(row)
        row += 1
        _draw_expectation_windows(ax, name)
        xs = [t for t, _ in series]
        ys = [v for _, v in series]
        ax.plot(xs, ys, color=_SIGNAL_COLOR, linewidth=1.2)
        ax.text(0.01, 0.85, name, transform=ax.transAxes, fontsize=7, color=_FG, va="top")
        for marker in markers.get(name, ()):
            ax.axvline(marker.tick_index, color=_MARKER_COLOR, linewidth=0.8, alpha=0.6)
        axes.append(ax)

    for name, series in state_series.items():
        ax = _new_lane_axes(row)
        row += 1
        _draw_expectation_windows(ax, name)
        for i, (tick_index, value) in enumerate(series):
            end = series[i + 1][0] if i + 1 < len(series) else head_tick + 1
            ax.axvspan(tick_index, end, color=_STATE_BAND_COLOR, alpha=0.5)
            ax.text((tick_index + end) / 2.0, 0.5, str(value), fontsize=6, color=_FG,
                     ha="center", va="center", transform=ax.get_xaxis_transform())
        ax.text(0.01, 0.85, name, transform=ax.transAxes, fontsize=7, color=_FG, va="top")
        for marker in markers.get(name, ()):
            ax.axvline(marker.tick_index, color=_MARKER_COLOR, linewidth=0.8, alpha=0.6)
        axes.append(ax)

    if not axes:
        axes = [_new_lane_axes(0)]

    for ax in axes:
        ax.axvline(current_tick, color=_PLAYHEAD_COLOR, linewidth=1.0)
        for bookmark_tick in bookmark_ticks:
            ax.axvline(bookmark_tick, color=_BOOKMARK_COLOR, linewidth=0.8, linestyle="--", alpha=0.7)

    buffer = _io.BytesIO()
    fig.savefig(buffer, format="raw", dpi=dpi)
    buffer.seek(0)
    width, height = fig.canvas.get_width_height()
    array = np.frombuffer(buffer.getvalue(), dtype=np.uint8).reshape((height, width, 4))
    plt.close(fig)
    return array[:, :, :3]


def px_to_tick(x_px: float, size_px: tuple[int, int], head_tick: int) -> int:
    """The exact inverse of `render_timeline`'s fixed `[0, head_tick]`
    zero-margin x-axis -- click-to-seek's other half."""
    span = max(head_tick, 1)
    tick = round((x_px / size_px[0]) * span)
    return max(0, min(tick, head_tick))
