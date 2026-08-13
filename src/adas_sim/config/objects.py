# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`ObjectModel.footprint(class_name)` -- the three-step precedence
(per-object `geometry` -> class table -> declared fallback), R-SIM-3."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class Footprint:
    length_m: float
    width_m: float
    #: True only for the declared fallback -- never a measurement (R-SIM-3),
    #: drawn in a style that makes it visibly a guess.
    assumed_geometry: bool = False

    def __repr__(self) -> str:
        tag = " assumed" if self.assumed_geometry else ""
        return f"<Footprint length_m={self.length_m:.2f} width_m={self.width_m:.2f}{tag}>"


#: The one generic "unknown object" size every caller falls back to when a
#: project's own calibration has no entry for a class (`GT-3`: this literal
#: lives in `config/`, the one place a physical constant may, precisely so a
#: layer provider never has to invent its own). Matches the long-standing
#: cosmetic default `tools/carla/replay/viz.py`'s `OBJECT_LENGTH_M`/
#: `OBJECT_WIDTH_M` already used, since no project's calibration has ever
#: covered every object class.
DEFAULT_FALLBACK_FOOTPRINT = Footprint(length_m=4.5, width_m=1.8, assumed_geometry=True)

#: Cross-function generic class sizes -- **not** project-calibrated (no
#: project's YAML covers car/truck/pedestrian today, only a driving
#: function's own class-specific subset, e.g. a two-wheeler size). Every
#: entry carries `assumed_geometry=True` for exactly that reason. A
#: component with real per-class calibration passes its own `class_table`
#: to `ObjectModel` instead of this one; this exists so a component-generic
#: layer (no function name allowed, `R-SIM-1`) still distinguishes "this is
#: clearly a pedestrian" from "this is clearly a car" out of the box,
#: without inventing its own literal dimensions (`GT-3`).
DEFAULT_CLASS_FOOTPRINTS: dict[str, Footprint] = {
    "car": Footprint(length_m=4.5, width_m=1.8, assumed_geometry=True),
    "truck": Footprint(length_m=8.0, width_m=2.5, assumed_geometry=True),
    "two_wheeler": Footprint(length_m=2.0, width_m=0.8, assumed_geometry=True),
    "pedestrian": Footprint(length_m=0.6, width_m=0.6, assumed_geometry=True),
}


class ObjectModel:
    """Resolves a class name to a `Footprint`, in the order R-SIM-3 requires:
    a per-object `geometry` argument wins outright; failing that, the
    project's class table; failing that, the declared fallback, which always
    carries `assumed_geometry=True` regardless of how it was constructed."""

    def __init__(self, *, class_table: Mapping[str, Footprint], fallback: Footprint = DEFAULT_FALLBACK_FOOTPRINT) -> None:
        self._class_table = dict(class_table)
        self._fallback = fallback if fallback.assumed_geometry else replace(fallback, assumed_geometry=True)

    def __repr__(self) -> str:
        return f"<ObjectModel classes={sorted(self._class_table)} fallback={self._fallback!r}>"

    def footprint(self, class_name: str, *, geometry: Footprint | None = None) -> Footprint:
        if geometry is not None:
            return geometry
        if class_name in self._class_table:
            return self._class_table[class_name]
        return self._fallback
