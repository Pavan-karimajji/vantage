# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`IMP-0196`/`SW-0196` -- the source-identity tuple resolved *before* any
description is selected (`description.py::resolve_descriptions` takes one
as input): `family` (the owning component/team's own name, `IngestMap`'s
own `family:` string), `model` (the physical/simulated sensor or ECU
model), `name` (this particular instance's label) and `instance` (an
integer disambiguating two identical sensors on one vehicle). **Unparented
in `SYS`** (`SwReq` §32.3) -- `trace_check.py` reports this as a known gap,
not a defect to close.

An incomplete identity is reported, never guessed: there is no default
`instance`, no "assume model X", because a wrong identity silently picks
the wrong `description.py` tier and the wrong static-data sidecar
(`static.py`) with no visible symptom until the numbers are already wrong.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from adas_sim.diagnostics.errors import AuthoringError

_REQUIRED_FIELDS = ("family", "model", "name", "instance")


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    family: str
    model: str
    name: str
    instance: int

    def __repr__(self) -> str:
        return f"<SourceIdentity {self.family}/{self.model}/{self.name}#{self.instance}>"


def resolve_identity(raw: Mapping[str, object] | None, *, where: str) -> SourceIdentity:
    missing = [f for f in _REQUIRED_FIELDS if raw is None or raw.get(f) in (None, "")]
    if missing:
        raise AuthoringError(
            expected=f"identity fields {_REQUIRED_FIELDS} all present", found=f"missing {missing}", where=where,
            hint="an incomplete source identity is never guessed (IMP-0196) -- declare every field",
        )
    assert raw is not None
    try:
        instance = int(raw["instance"])  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise AuthoringError(
            expected="instance: an integer", found=repr(raw["instance"]), where=where, hint="",
        ) from None
    return SourceIdentity(family=str(raw["family"]), model=str(raw["model"]), name=str(raw["name"]), instance=instance)
