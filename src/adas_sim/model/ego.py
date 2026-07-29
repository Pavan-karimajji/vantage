# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`EgoModel` -- x_front/x_rear/half_width from resolved YAML, never a module
constant (R-SIM-3, sim_api_reference.md §6). Formulas mirror a driving
function's own existing zone-drawing reference module exactly (the generic
half only -- that module's own zone-geometry functions are function-specific
and do not belong here, R-SIM-1).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from adas_sim.core.errors import AuthoringError

#: `shared_config` is cross-component calibration, not a "function" (R-MATH-2
#: reasoning): the one path this framework may hardcode, because every
#: project's ego geometry genuinely lives only here (docs/shared_config_plan.md).
MODULES_ROOT = Path(__file__).resolve().parents[4]
SHARED_CONFIG_PROJECTS = MODULES_ROOT / "shared_config" / "projects"

#: field name -> the ego_params.yaml key it comes from (R-NAME-3 ALL_CAPS keys).
_REQUIRED_KEYS = {
    "length_m": "EGO_LENGTH_M",
    "width_m": "EGO_WIDTH_M",
    "wheelbase_m": "EGO_WHEELBASE_M",
    "overhang_front_m": "EGO_OVERHANG_FRONT_M",
}


@dataclass(frozen=True, slots=True)
class EgoModel:
    """Ego body geometry, frame per R-COORD-1 (origin at rear-axle centre,
    +x forward, +y left)."""

    project: str
    length_m: float
    width_m: float
    wheelbase_m: float
    overhang_front_m: float

    @property
    def x_front_m(self) -> float:
        """wheelbase + front overhang."""
        return self.wheelbase_m + self.overhang_front_m

    @property
    def x_rear_m(self) -> float:
        """x_front - length."""
        return self.x_front_m - self.length_m

    @property
    def half_width_m(self) -> float:
        """Body half-width, mirrors excluded."""
        return self.width_m / 2.0

    def __repr__(self) -> str:
        return f"<EgoModel {self.project!r} x_front_m={self.x_front_m:.3f} x_rear_m={self.x_rear_m:.3f}>"

    @classmethod
    def load(cls, project: str) -> EgoModel:
        """Load `shared_config/projects/<project>/vehicle/ego_params.yaml` --
        the standard, non-bundle location (R-VAR-4). Bundle-shaped tiers
        (explicit/embedded/library, `model/project.py`) go through
        `from_yaml_file` instead."""
        path = SHARED_CONFIG_PROJECTS / project / "vehicle" / "ego_params.yaml"
        if not path.is_file():
            raise AuthoringError(
                expected="a project with vehicle/ego_params.yaml",
                found="no such file",
                where=str(path),
                hint=f"check the project name against {SHARED_CONFIG_PROJECTS}",
            )
        return cls.from_yaml_file(path, project=project)

    @classmethod
    def from_yaml_file(cls, path: Path, *, project: str) -> EgoModel:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        values: dict[str, float] = {}
        for field, key in _REQUIRED_KEYS.items():
            if key not in data:
                raise AuthoringError(
                    expected=f"key {key!r}",
                    found="missing",
                    where=str(path),
                    hint=f"add {key} to {path.name} (a case-differing key does not resolve, P-3)",
                )
            values[field] = float(data[key])
        return cls(project=project, **values)
