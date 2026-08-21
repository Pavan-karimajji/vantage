# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`IMP-0197`/`SW-0197`, `IMP-0198`/`SW-0198`, `IMP-0201`/`SW-0201` --
ordered, reported, version-checked description resolution (`DD-06`).

A "description" is a schema/format document *about* a source's data
(a DBC file, a CARLA blueprint's field layout, a units-and-ranges sheet) --
distinct from the ingest map (which says which *port* a topic feeds) and
distinct from `static.py`'s static *parameter* payload. `DD-06` makes
`Description` **typed**: `type` names which kind of document this is
(`"ars540_can_dbc"`, `"carla_object_list"`, ...), and each type carries its
own closed set of accepted versions -- one artifact kind cannot carry
per-type version sets without a type field inside it, which is the same
design with an extra indirection (`DD-06`'s own reasoning).

`TIER_ORDER` is a **module constant**, printed by `explain`, never
discovered by probing the filesystem (`IMP-0201`) -- a precedence nobody
can read is a precedence nobody can predict.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.ingest.identity import SourceIdentity


class Tier(StrEnum):
    EMBEDDED = "embedded"
    CONFIGURED = "configured"
    CONVENTION = "convention"


#: Best first. `resolve_descriptions` walks this order and, per `type`,
#: keeps the first (highest-precedence) candidate offered -- a lower-tier
#: candidate for a type already chosen is not an error, just shadowed.
TIER_ORDER: tuple[Tier, ...] = (Tier.EMBEDDED, Tier.CONFIGURED, Tier.CONVENTION)


@dataclass(frozen=True, slots=True)
class Description:
    type: str
    version: str
    path: Path
    tier: Tier

    def __repr__(self) -> str:
        return f"<Description {self.type}@{self.version} tier={self.tier.value}>"


#: `DD-06`: each type's own accepted-version set. Adding a type or widening
#: an accepted set is a real, reviewed change to this table -- never an
#: inline `if version >= "1.0"` at a call site.
_ACCEPTED_VERSIONS: dict[str, frozenset[str]] = {
    "carla_object_list": frozenset({"0.9", "0.9.10"}),
    "ars540_can_dbc": frozenset({"1.0", "1.1"}),
    "df_sil_ports": frozenset({"1"}),
}


def _check_accepted(description: Description, *, where: str) -> None:
    accepted = _ACCEPTED_VERSIONS.get(description.type)
    if accepted is None:
        raise AuthoringError(
            expected=f"a known description type (one of {sorted(_ACCEPTED_VERSIONS)})",
            found=repr(description.type), where=where, hint="",
        )
    if description.version not in accepted:
        raise AuthoringError(
            expected=f"{description.type} version in {sorted(accepted)}", found=repr(description.version),
            where=where, hint="a version outside its type's accepted set is refused, never coerced (IMP-0198)",
        )


def resolve_descriptions(identity: SourceIdentity, candidates: Sequence[Description]) -> tuple[Description, ...]:
    """Per `type`, the highest-tier candidate in `candidates` wins
    (`TIER_ORDER`); every candidate actually chosen is checked against its
    type's accepted-version set (`IMP-0198`) before being returned. Which
    tier won, per source, is exactly `Description.tier` on the result --
    the caller reports it, this function does not print anything itself.
    """
    chosen: dict[str, Description] = {}
    for tier in TIER_ORDER:
        for candidate in candidates:
            if candidate.tier is tier and candidate.type not in chosen:
                _check_accepted(candidate, where=f"{identity!r} description {candidate.type}@{candidate.version}")
                chosen[candidate.type] = candidate
    return tuple(chosen.values())
