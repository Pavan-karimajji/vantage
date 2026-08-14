# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""One published JSON-Schema per `FileKind`, under `schemas/*.schema.json`,
shipped in the package (`IF-13`, `IMP-0151`). `additionalProperties: false`
everywhere -- an unknown key is an error, never a warning (`CN-0183`,
`IMP-0152`), and the error carries `near_matches` (`IMP-0124`) so a typo
points at the real key instead of a bare "not allowed."

`check_version` (`IMP-0153`) ports `graph/build.py::_resolve_version`'s
gate -- version required, integer, `>= 1`, never newer than this reader
understands -- to every file kind, not just the pipeline. `graph/build.py`
keeps its own copy for now (`R-STYLE-2`: that module's version handling is
not itself a WP-04 artifact); this is the one every NEW kind uses.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import jsonschema

from adas_sim.config.kinds import FileKind
from adas_sim.config.layers import line_index
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.diagnostics.suggest import near_matches

_SCHEMAS_DIR = Path(__file__).parent / "schemas"

#: The newest version THIS reader understands, per kind -- same "reject
#: anything newer, naming both" discipline as `CURRENT_PIPELINE_VERSION`.
CURRENT_VERSIONS: Mapping[FileKind, int] = {
    FileKind.COMPOSITION: 1,
    FileKind.CONNECTIONS: 1,
    FileKind.SOURCE_BINDING: 1,
    FileKind.LAYOUT: 1,
}


@lru_cache(maxsize=None)
def _schema_for(kind: FileKind) -> dict:
    path = _SCHEMAS_DIR / f"{kind.value}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def check_version(kind: FileKind, raw: Mapping[str, object], *, where: str) -> int:
    """`version:` is required going forward; a file with none is refused
    (every WP-04 kind is new -- there is no pre-version file to upgrade,
    unlike `graph/build.py`'s pipeline reader, `IMP-0153`'s own `MOVE` note).
    A version newer than `CURRENT_VERSIONS[kind]` is a load error naming
    both."""
    current = CURRENT_VERSIONS[kind]
    version = raw.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise AuthoringError(
            expected="an integer version >= 1", found=repr(version), where=where,
            hint=f"use version: {current}",
        )
    if version > current:
        raise AuthoringError(
            expected=f"version <= {current} (this reader)", found=f"version {version}", where=where,
            hint=f"this {kind.value} file was written by a newer adas-sim; upgrade the framework",
        )
    return version


def _line_for(path: Path, key: str) -> int:
    for key_path, line in line_index(path).items():
        if key_path and key_path[-1] == key:
            return line
    return 0


def validate(kind: FileKind, raw: Mapping[str, object], *, path: Path) -> None:
    """Validates `raw` (already `!include`-expanded, `IMP-0156`) against
    `kind`'s published schema. The FIRST error (schema-declaration order,
    stable) is raised as an `AuthoringError` naming the file, the line (best
    effort, via `layers.line_index`), the wrong value and the allowed keys
    -- an unknown key additionally carries `near_matches` against the
    schema's own declared property names."""
    schema = _schema_for(kind)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    errors = sorted(validator_cls(schema).iter_errors(raw), key=lambda e: (list(e.path), e.validator))
    if not errors:
        return
    error = errors[0]
    key = str(error.path[-1]) if error.path else ""
    where = f"{path}:{_line_for(path, key)}" if key else str(path)

    if error.validator == "additionalProperties" and isinstance(error.instance, Mapping):
        allowed = sorted(error.schema.get("properties", {}))
        unknown = sorted(set(error.instance) - set(allowed))
        suggestions = {k: near_matches(k, allowed) for k in unknown}
        raise AuthoringError(
            expected=f"one of {allowed}", found=f"unknown key(s) {unknown}",
            where=where if key else str(path),
            hint=f"did you mean: {suggestions}" if any(suggestions.values()) else f"allowed keys: {allowed}",
        )
    raise AuthoringError(
        expected=error.schema.get("description", str(error.validator)),
        found=repr(error.instance), where=where, hint=error.message,
    )
