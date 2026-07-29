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


class ObjectModel:
    """Resolves a class name to a `Footprint`, in the order R-SIM-3 requires:
    a per-object `geometry` argument wins outright; failing that, the
    project's class table; failing that, the declared fallback, which always
    carries `assumed_geometry=True` regardless of how it was constructed."""

    def __init__(self, *, class_table: Mapping[str, Footprint], fallback: Footprint) -> None:
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
