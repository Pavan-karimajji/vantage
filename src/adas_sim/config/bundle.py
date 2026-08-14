# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""What may enter the config bundle, and the two cross-component agreement
checks (`R-SIM-3a`, `IMP-0159`/`IMP-0160`).

`may_enter_bundle` is `R-SIM-9`'s own line made a refusal: "the bundle and
`shared_config` hold real runtime configuration only... World-model
bindings, sensor **error** models and fault injection live with the
tooling." A file/category that is not runtime calibration a module's own
DLL reads at run time is refused, quoting the rule.

The two agreement checks are ported, unchanged in behaviour, from
`graph/build.py::_validate_cross_component_agreement` (`OD-11`): project-name
agreement is a **warning**, escapable via `allow_mixed_projects: true`; ego-
parameter agreement is a **hard error with no escape**, and the escape
widening beyond project-name is exactly what `R-SIM-3a` forbids. This module
takes plain data (project name / bundle directory per stage), never a
`SilComponent`, so `config/**` never imports `adas_sim.resolve` or anything
that itself touches `ctypes` (`ANL-SW-34`, `IMP-0164`).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from warnings import warn

import yaml

from adas_sim.diagnostics.errors import AuthoringError, ProvenanceWarning


class BundleCategory(StrEnum):
    """What kind of data a candidate bundle entry is (`R-SIM-9`). Only
    `RUNTIME_CALIBRATION` may enter -- the other three are simulation-only
    concerns that live with the tooling instead (per-scenario `world.*`/
    `run.faults`, or `modules/df/sim/sensor_models/`)."""

    RUNTIME_CALIBRATION = "runtime_calibration"
    WORLD_MODEL_BINDING = "world_model_binding"
    SENSOR_ERROR_MODEL = "sensor_error_model"
    FAULT_INJECTION = "fault_injection"


_MAY_ENTER = frozenset({BundleCategory.RUNTIME_CALIBRATION})

_R_SIM_9 = (
    "R-SIM-9: 'the bundle and shared_config hold real runtime configuration only... "
    "World-model bindings (map, spawn index, blueprints), sensor error models (noise, "
    "latency, dropout, occlusion, object_range_m, num_object_slots) and fault injection "
    "live with the tooling'"
)


def may_enter_bundle(category: BundleCategory, *, key: str) -> None:
    """A file/key enters the config bundle iff some module's DLL reads it
    at run time (`R-SIM-9`). Anything else is refused, quoting the rule --
    never silently dropped, since a silently dropped calibration key is
    indistinguishable from one nobody wrote yet."""
    if category in _MAY_ENTER:
        return
    raise AuthoringError(
        expected="runtime calibration a module's own DLL reads at run time",
        found=f"{category.value} key {key!r}",
        where="config bundle assembly",
        hint=_R_SIM_9,
    )


def _load_ego_params(bundle_dir: Path) -> Mapping[str, object]:
    """The shared-vehicle-facts half of a bundle (`R-SIM-3a`): `<bundle_dir>/
    vehicle/ego_params.yaml`, or empty if this bundle carries none -- a
    bundle packed with no ego copy contributes nothing to the comparison
    rather than erroring (there is nothing to disagree about yet)."""
    ego_path = bundle_dir / "vehicle" / "ego_params.yaml"
    if not ego_path.is_file():
        return {}
    return yaml.safe_load(ego_path.read_text(encoding="utf-8")) or {}


def check_cross_component_agreement(
    projects: Mapping[str, str | None], bundle_dirs: Mapping[str, Path | None], *, allow_mixed_projects: bool,
) -> bool:
    """`OD-11` (`sim_sil_contract.md` SS9.1): every real bundle resolved
    into one pipeline must agree on the vehicle facts it carries, or the
    picture and the SUT disagree about the wheelbase with no legitimate
    reading.

    **Project-name agreement is a warning, escapable** by the caller's own
    `allow_mixed_projects: true` -- a deliberate cross-project experiment is
    a real workflow.

    **Ego-parameter agreement is a hard load error, with NO escape** --
    `allow_mixed_projects` widens the project-name warning only; it must
    never also suppress this, since an escape hatch that widens beyond its
    stated scope is how a hard error becomes a warning.

    `projects`/`bundle_dirs` are keyed by stage/unit name; a name absent
    from `bundle_dirs` or mapped to `None` has nothing on disk to compare
    and is skipped. Returns whether the resolved projects actually
    differed, so a caller can record it -- `allow_mixed_projects:` is what
    was *requested*, the return value is what was *found*."""
    known = [(name, bundle_dir) for name, bundle_dir in bundle_dirs.items() if bundle_dir is not None]
    if len(known) < 2:
        return False

    named_projects = {name: projects[name] for name, _ in known if projects.get(name)}
    distinct_projects = set(named_projects.values())
    mixed = len(distinct_projects) > 1
    if mixed and not allow_mixed_projects:
        first_name, first_project = next(iter(named_projects.items()))
        for name, project in named_projects.items():
            if project != first_project:
                warn(
                    ProvenanceWarning(
                        f"stage '{name}' bundle is for project {project!r}, stage '{first_name}' bundle is "
                        f"for project {first_project!r} -- set allow_mixed_projects: true if this is deliberate"
                    )
                )
                break

    reference_name, reference_dir = known[0]
    reference_ego = _load_ego_params(reference_dir)
    for name, bundle_dir in known[1:]:
        ego = _load_ego_params(bundle_dir)
        for key, value in reference_ego.items():
            if key in ego and ego[key] != value:
                raise AuthoringError(
                    expected=f"stage '{name}' ego_params.yaml to agree with stage '{reference_name}' on '{key}'",
                    found=f"'{name}'={ego[key]!r} vs '{reference_name}'={value!r}",
                    where="pipeline cross-component ego-parameter agreement (OD-11)",
                    hint="every component's config bundle carries its own copy of shared_config's "
                         "vehicle/ego_params.yaml -- they must be identical. allow_mixed_projects "
                         "does not, and must not, suppress this",
                )
    return mixed
