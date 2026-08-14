# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`FileKind` -- the four configuration concerns `SIM_System_Requirements_
v0.1.md` SS2.2 (`SYS-0117`) found independently arrived at, and requires
never be merged into one file: **composition** (which units load, from
which binaries, exposing which ports), **connections** (how exposed ports
are wired), **source binding** (which recorded signal satisfies which
port) and **layout** (tabs, views, layer visibility, scoped parameters).

This module states the boundary as data (`KIND_KEYS`) and enforces it as a
refusal, not a convention (`SW-0150`): a key belonging to one kind's
declared set appearing in a file of a different kind is an `AuthoringError`
naming both kinds. `schema.py` layers the full JSON-Schema per kind on top
of this; this module is what makes the four-way split checkable even
before a schema exists.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from adas_sim.diagnostics.errors import AuthoringError


class FileKind(StrEnum):
    """SW-0150 -- four, never merged."""

    COMPOSITION = "composition"
    CONNECTIONS = "connections"
    SOURCE_BINDING = "source_binding"
    LAYOUT = "layout"


#: Each kind's own top-level keys (`SYS-0117`'s four-way split, made
#: concrete). Disjoint by construction -- `test_a2_kinds.py`'s own
#: `INSP-SW-02` check asserts no two kinds share a key, since a shared key
#: would make `check_disjoint_keys` unable to tell which file it belongs to.
KIND_KEYS: Mapping[FileKind, frozenset[str]] = {
    FileKind.COMPOSITION: frozenset({"version", "units"}),
    FileKind.CONNECTIONS: frozenset({"version", "name", "wiring", "allow_mixed_projects"}),
    FileKind.SOURCE_BINDING: frozenset({"version", "provides", "absent"}),
    FileKind.LAYOUT: frozenset({"version", "tabs", "layers", "params"}),
}


def check_disjoint_keys(kind: FileKind, raw: Mapping[str, object], *, where: str) -> None:
    """A key from a DIFFERENT kind's declared set appearing in `raw` is a
    load error naming both kinds (`SW-0150`) -- `version` is exempt (every
    kind declares it, `check_version` owns it, `schema.py::IMP-0153`)."""
    own = KIND_KEYS[kind]
    for other_kind, other_keys in KIND_KEYS.items():
        if other_kind is kind:
            continue
        collision = (set(raw) & other_keys) - own - {"version"}
        if collision:
            raise AuthoringError(
                expected=f"only {kind.value} keys {sorted(own)} in a {kind.value} file",
                found=f"key(s) {sorted(collision)}, which belong to {other_kind.value}",
                where=where,
                hint=f"the four configuration concerns (SYS-0117) are never merged into one "
                     f"file -- move {sorted(collision)} to its own {other_kind.value} file",
            )


def _find_string_leaves(node: object) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, Mapping):
        return [s for v in node.values() for s in _find_string_leaves(v)]
    if isinstance(node, (list, tuple)):
        return [s for v in node for s in _find_string_leaves(v)]
    return []


def check_composition_no_cross_unit_reference(raw: Mapping[str, object], *, where: str) -> None:
    """`IMP-0398`: a `COMPOSITION` file declares one unit's own exposed
    ports and nothing about wiring -- a unit's declaration naming another
    declared unit anywhere in its own body is a wiring concern smuggled
    into composition, refused so a unit stays reusable regardless of which
    `CONNECTIONS` file wires it (`CN-0103`)."""
    units = raw.get("units") or []
    names = {unit["name"] for unit in units if isinstance(unit, Mapping) and "name" in unit}
    for unit in units:
        if not isinstance(unit, Mapping) or "name" not in unit:
            continue
        own_name = unit["name"]
        others = names - {own_name}
        body = {k: v for k, v in unit.items() if k != "name"}
        found = others & set(_find_string_leaves(body))
        if found:
            raise AuthoringError(
                expected="a composition entry naming no other declared unit",
                found=f"unit '{own_name}' names {sorted(found)}",
                where=f"{where} units[{own_name!r}]",
                hint="wiring belongs in a connections file, never composition -- "
                     "a unit that references another by name cannot be reused standalone (CN-0103)",
            )
