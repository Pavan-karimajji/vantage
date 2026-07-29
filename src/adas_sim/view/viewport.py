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


#: Named viewpoints as data (S-B1 checklist; a component's own
#: `viewpoints.yaml` supplies the presets themselves -- these are the
#: framework-generic fallbacks every component can start from).
DEFAULT_PRESETS: dict[str, Viewport] = {
    "close": Viewport(scale_px_per_m=20.0),
    "wide": Viewport(scale_px_per_m=6.0),
}
