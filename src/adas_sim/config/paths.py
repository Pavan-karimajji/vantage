# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Path handling (SI-07, `WP-03`/`IMP-0364`) -- the one sanctioned place
`adas_sim`'s own ancestor directories are computed.

Before this module, `check/runner.py`, `config/ego.py` and `ingest/map.py`
each independently hardcoded `Path(__file__).resolve().parents[N]` with
their own `N` for their own file depth -- fragile against exactly the kind
of restructuring `WP-02` just did (a file moving one level changes every
`N` that assumed the old depth, silently). This module's own depth is
fixed once, here, and every caller asks by name instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from adas_sim.config.kinds import FileKind

#: modules/sim/src/adas_sim/config/paths.py -> config -> adas_sim -> src -> sim
_SIM_ROOT = Path(__file__).resolve().parents[3]


def sim_root() -> Path:
    """`modules/sim`, this component's own root."""
    return _SIM_ROOT


def modules_root() -> Path:
    """`modules/`, the superproject's component directory."""
    return _SIM_ROOT.parent


def superproject_root() -> Path:
    """The superproject root, one level above `modules/`."""
    return _SIM_ROOT.parent.parent


@dataclass(frozen=True, slots=True)
class ConfigPaths:
    """Where a project's own configuration files live -- `project_root` is
    ALWAYS a caller-supplied parameter, never derived from `adas_sim`'s own
    install location (`IMP-0158`, `CN-0014`): a customer's configuration
    lives in the customer's own repository, and this package must resolve
    it correctly whether it is a source checkout, a pip install, or a
    frozen build's read-only site-packages -- none of which have any say in
    where the CUSTOMER's files are (`IT-12` runs from exactly that: a
    checkout with the package installed read-only)."""

    project_root: Path

    def dir_for(self, kind: FileKind) -> Path:
        """One subdirectory per `FileKind`, named after the kind itself --
        the four-way split (`SW-0150`) carried into the filesystem layout."""
        return self.project_root / kind.value
