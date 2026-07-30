# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`Viewport` -- pan/zoom/rotate state for the BEV, and nothing else (no
pixels drawn here). Replaces `viz.py`'s module-level `CANVAS_WIDTH_PX`/
`PX_PER_METER`/`ORIGIN_PX` constants with real state a follow mode and a
zoom gesture can change (sim_visualization_spec.md §4).
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class Viewport:
    #: World point (in `frame`, metres) that sits at the centre of the canvas.
    centre_m: tuple[float, float] = (0.0, 0.0)
    scale_px_per_m: float = 10.0
    #: 0 = +x is screen-up (viz.py's own convention: forward is up, left is left).
    rotation_rad: float = 0.0
    #: "ego_forward" | "ego_heading" | "world" | "locked:<pick_id>" (§4.2).
    follow: str = "ego_forward"
    #: From the widget, never a constant (viz.py's own D6 mistake).
    size_px: tuple[int, int] = (900, 700)

    MIN_SCALE_PX_PER_M: ClassVar[float] = 1.0
    MAX_SCALE_PX_PER_M: ClassVar[float] = 200.0

    def __repr__(self) -> str:
        return f"<Viewport centre_m={self.centre_m} scale_px_per_m={self.scale_px_per_m:.1f} follow={self.follow!r}>"

    def to_px(self, x_m: float, y_m: float) -> tuple[float, float]:
        """A world-frame point -> canvas pixels."""
        dx, dy = x_m - self.centre_m[0], y_m - self.centre_m[1]
        cos_r, sin_r = math.cos(self.rotation_rad), math.sin(self.rotation_rad)
        forward = dx * cos_r - dy * sin_r
        left = dx * sin_r + dy * cos_r
        cx, cy = self.size_px[0] / 2.0, self.size_px[1] / 2.0
        return (cx - left * self.scale_px_per_m, cy - forward * self.scale_px_per_m)

    def to_m(self, px: float, py: float) -> tuple[float, float]:
        """Canvas pixels -> a world-frame point (the exact inverse of `to_px`)."""
        cx, cy = self.size_px[0] / 2.0, self.size_px[1] / 2.0
        left = (cx - px) / self.scale_px_per_m
        forward = (cy - py) / self.scale_px_per_m
        cos_r, sin_r = math.cos(self.rotation_rad), math.sin(self.rotation_rad)
        dx = forward * cos_r + left * sin_r
        dy = -forward * sin_r + left * cos_r
        return (dx + self.centre_m[0], dy + self.centre_m[1])

    def zoomed_about_cursor(self, factor: float, cursor_px: tuple[float, float]) -> Viewport:
        """Scale clamped at its declared bounds; the cursor's own world point
        stays fixed on screen (`UT-B1-9`)."""
        world_before = self.to_m(*cursor_px)
        new_scale = min(max(self.scale_px_per_m * factor, self.MIN_SCALE_PX_PER_M), self.MAX_SCALE_PX_PER_M)
        candidate = dataclasses.replace(self, scale_px_per_m=new_scale)
        world_after = candidate.to_m(*cursor_px)
        return dataclasses.replace(
            candidate,
            centre_m=(
                candidate.centre_m[0] + (world_before[0] - world_after[0]),
                candidate.centre_m[1] + (world_before[1] - world_after[1]),
            ),
        )

    def panned(self, start_px: tuple[float, float], end_px: tuple[float, float]) -> Viewport:
        """Drag-to-pan (`sim_visualization_spec.md` §4.4): the world point
        grabbed at `start_px` ends up under `end_px` -- the same "invariant
        point" reasoning as `zoomed_about_cursor`, so panning and zooming
        agree on what "the cursor's world point" means, rather than a
        second pixel-delta-to-world-delta derivation that could disagree
        with it."""
        world_grabbed = self.to_m(*start_px)
        world_at_end_before_pan = self.to_m(*end_px)
        return dataclasses.replace(self, centre_m=(
            self.centre_m[0] + (world_grabbed[0] - world_at_end_before_pan[0]),
            self.centre_m[1] + (world_grabbed[1] - world_at_end_before_pan[1]),
        ))

    def fitted_to(self, bounds_m: tuple[float, float, float, float], *, margin: float = 0.1) -> Viewport:
        """`F` (§4.4): the smallest scale that fits `bounds_m` (world
        `(x_min, y_min, x_max, y_max)`) inside `size_px`, centred on it.
        `x` (forward) spans canvas **height**, `y` (left) spans canvas
        **width** -- the same axis pairing `render/bev.py`'s
        `_x_axis_limits`/`_y_axis_limits` use, so a fitted viewport and a
        rendered frame agree on which axis is which. A degenerate (empty or
        single-point) `bounds_m` keeps this viewport's own scale rather than
        dividing by zero."""
        x_min, y_min, x_max, y_max = bounds_m
        x_span, y_span = x_max - x_min, y_max - y_min
        candidates = []
        if x_span > 0:
            candidates.append(self.size_px[1] / x_span)
        if y_span > 0:
            candidates.append(self.size_px[0] / y_span)
        # A degenerate (empty or single-point) span has nothing to fill, so
        # the margin -- which only means something relative to a fit -- does
        # not apply to the "keep this viewport's own scale" fallback.
        new_scale = min(candidates) * (1.0 - margin) if candidates else self.scale_px_per_m
        new_scale = min(max(new_scale, self.MIN_SCALE_PX_PER_M), self.MAX_SCALE_PX_PER_M)
        return dataclasses.replace(
            self, scale_px_per_m=new_scale, centre_m=((x_min + x_max) / 2.0, (y_min + y_max) / 2.0),
        )


#: Named viewpoints as data (S-B1 checklist; a component's own
#: `viewpoints.yaml` supplies the presets themselves -- these are the
#: framework-generic fallbacks every component can start from).
DEFAULT_PRESETS: dict[str, Viewport] = {
    "close": Viewport(scale_px_per_m=20.0),
    "wide": Viewport(scale_px_per_m=6.0),
}
