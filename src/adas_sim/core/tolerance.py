# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""`ToleranceSet` -- `S-C6` (`R-SIM-24`): per-component field tolerance for
the two MEASURED determinism axes (rebuilt binary, different machine).
`default: exact`; every widening row carries a mandatory `why:` or the file
is an `AuthoringError` at load, not a silently-accepted gap (`OD-10`) --
integers and enums are exact everywhere and this file offers no way to
widen them (`abs_tol` only ever applies to a float family; an integer/enum
divergence is always reported, regardless of what this file says).

Axes A (same-process) and B (fresh-process) never consult this module --
they have no tolerance *field*, not a tolerance of zero, so there is nothing
here to widen for them (`core.determinism`'s own discipline)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from adas_sim.core.errors import AuthoringError


@dataclass(frozen=True, slots=True)
class ToleranceRow:
    #: A dotted field path (`"aebOutputs.ttc_s"`) or `"*"` for the family
    #: default within a component.
    field: str
    abs_tol: float
    why: str


@dataclass(frozen=True, slots=True)
class ToleranceSet:
    component: str
    rows: tuple[ToleranceRow, ...]
    #: `""` when no `tolerance.yaml` exists for this component (every field
    #: is exact) -- joins `config_bundle_sha256` in the run manifest when
    #: this axis's report is attached to one (`S-C6`'s own wording).
    sha256: str

    def bound_for(self, field_path: str) -> ToleranceRow | None:
        for row in self.rows:
            if row.field == field_path:
                return row
        for row in self.rows:
            if row.field == "*":
                return row
        return None


def load_tolerance(path: Path, *, component: str) -> ToleranceSet:
    """`path` is `modules/<name>/sim/tolerance.yaml`. Absent entirely ->
    `default: exact` for every field, the honest zero-configuration case,
    never an error."""
    if not path.is_file():
        return ToleranceSet(component=component, rows=(), sha256="")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows: list[ToleranceRow] = []
    for field, spec in raw.get("fields", {}).items():
        if not isinstance(spec, dict) or "why" not in spec:
            raise AuthoringError(
                expected=f"tolerance row '{field}' to carry a mandatory 'why:'",
                found=repr(spec), where=str(path),
                hint="a tolerance widening with no stated reason is exactly the silent "
                     "spiral this file exists to prevent (OD-10)",
            )
        if "abs_tol" not in spec:
            raise AuthoringError(
                expected=f"tolerance row '{field}' to carry 'abs_tol:'",
                found=repr(spec), where=str(path), hint="the only two keys a row takes are abs_tol: and why:",
            )
        abs_tol = float(spec["abs_tol"])
        if abs_tol < 0:
            raise AuthoringError(
                expected=f"tolerance row '{field}' abs_tol >= 0", found=str(abs_tol), where=str(path),
            )
        rows.append(ToleranceRow(field=field, abs_tol=abs_tol, why=str(spec["why"])))

    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return ToleranceSet(component=component, rows=tuple(rows), sha256=sha256)
