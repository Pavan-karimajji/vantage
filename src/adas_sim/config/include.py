# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`expand` (`IMP-0156`) resolves `!include <relpath>` tags -- relative to
the INCLUDING file, cycle-detected, and the returned form is what is
validated: an included fragment goes through the same key/schema checks as
inline content, so it cannot smuggle an unknown key past `schema.py`'s
`additionalProperties: false` (`IMP-0152`).

`resolve_vars` (`IMP-0157`) substitutes `${name}` from a declared variable
set only -- no environment lookup, ever (`R-SIM-15`'s "no expression
language, no scripting hook" reasoning applied to configuration itself).
Every resolution is recorded as a `Provenanced` entry so `explain` can print
where each one came from.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

import yaml

from adas_sim.config.layers import Layer, Provenanced
from adas_sim.diagnostics.errors import AuthoringError

_INCLUDE_TAG = "!include"


def _load_expanded(path: Path, *, stack: tuple[Path, ...]) -> object:
    resolved_path = path.resolve()
    if resolved_path in stack:
        cycle = " -> ".join(str(p) for p in (*stack, resolved_path))
        raise AuthoringError(
            expected="no !include cycle", found=cycle, where=str(resolved_path),
            hint="break the cycle -- an included fragment may not (directly or "
                 "transitively) include the file that included it",
        )
    text = resolved_path.read_text(encoding="utf-8")
    new_stack = (*stack, resolved_path)

    def _include_constructor(loader: yaml.SafeLoader, node: yaml.Node) -> object:
        rel = loader.construct_scalar(node)
        return _load_expanded(resolved_path.parent / rel, stack=new_stack)

    loader_cls = type("_ExpandingLoader", (yaml.SafeLoader,), {})
    loader_cls.add_constructor(_INCLUDE_TAG, _include_constructor)
    return yaml.load(text, Loader=loader_cls) or {}


def expand(path: Path) -> dict:
    """Loads `path`, recursively resolving every `!include` tag (nested
    includes resolve relative to THEIR OWN file, not the root) into the
    returned document -- the form `schema.py`/`kinds.py` validate against,
    so an included fragment's unknown key is caught exactly as if it had
    been written inline (`IMP-0156`)."""
    result = _load_expanded(path, stack=())
    return result if isinstance(result, dict) else {}


_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def resolve_vars(
    raw: object, variables: Mapping[str, str], *, source: Path, layer: Layer,
) -> tuple[object, dict[str, Provenanced[str]]]:
    """Substitutes every `${name}` in every string leaf of `raw` from
    `variables` -- an undeclared name is a load error naming it and the
    declared set; there is no environment-variable fallback (`IMP-0157`).
    Returns the substituted document and one `Provenanced` entry per
    variable actually referenced (value = the substituted string, `layer`/
    `file` = where the *reference* was resolved -- the caller's own layer
    and source file, since that is what a reader debugging an unexpected
    value needs to find)."""
    used: dict[str, Provenanced[str]] = {}

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            raise AuthoringError(
                expected=f"variable '{name}' to be declared", found="undeclared",
                where=str(source),
                hint=f"no environment lookup is performed -- declared variables: {sorted(variables)}",
            )
        used[name] = Provenanced(value=variables[name], layer=layer, file=source, line=0)
        return variables[name]

    def _sub(node: object) -> object:
        if isinstance(node, str):
            return _VAR_RE.sub(_replace, node)
        if isinstance(node, Mapping):
            return {k: _sub(v) for k, v in node.items()}
        if isinstance(node, (list, tuple)):
            return [_sub(v) for v in node]
        return node

    return _sub(raw), used
