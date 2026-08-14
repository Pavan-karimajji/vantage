# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`Layer` + `Provenanced[T]` + `merge` (`SW-0149`) -- the four-layer
resolution order (package default -> project -> run -> CLI override, later
wins) with the winning layer, file and line carried on every resolved leaf
rather than reconstructed after the fact. `explain` (`IMP-0166`) prints this
directly; today's `contracts/pipeline.py`-descended code merges but keeps no
origin, which is `SW-0166`'s own `PARTIAL` this pairing closes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml


class Layer(StrEnum):
    """Resolution order, later wins (`SW-0149`) -- the ORDER a caller
    passes layers to `merge` in, not an intrinsic enum ordering (`StrEnum`
    carries none): a package default, overridden per project, overridden
    per run, overridden from the CLI."""

    PACKAGE = "package"
    PROJECT = "project"
    RUN = "run"
    CLI = "cli"


@dataclass(frozen=True, slots=True)
class Provenanced[T]:
    """One resolved leaf: its value, and which layer/file/line it came
    from (`SW-0149`, `SW-0166`). `line` is `0` when the value did not come
    from a real file on disk (e.g. a CLI-supplied override)."""

    value: T
    layer: Layer
    file: Path
    line: int


def _flatten(data: Mapping[str, object], prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], object]:
    result: dict[tuple[str, ...], object] = {}
    for key, value in data.items():
        path = prefix + (str(key),)
        if isinstance(value, Mapping):
            result.update(_flatten(value, path))
        else:
            result[path] = value
    return result


def _flatten_lines(node: yaml.Node, prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], int]:
    lines: dict[tuple[str, ...], int] = {}
    if not isinstance(node, yaml.MappingNode):
        return lines
    for key_node, value_node in node.value:
        path = prefix + (str(key_node.value),)
        if isinstance(value_node, yaml.MappingNode):
            lines.update(_flatten_lines(value_node, path))
        else:
            lines[path] = value_node.start_mark.line + 1  # 1-based, matching editors
    return lines


def line_index(path: Path) -> dict[tuple[str, ...], int]:
    """Every leaf's dotted key path -> its 1-based source line, from the
    raw YAML nodes (`yaml.compose`) rather than the already-parsed value --
    a parsed `dict` has no line numbers left to read."""
    text = path.read_text(encoding="utf-8")
    node = yaml.compose(text)
    if node is None:
        return {}
    return _flatten_lines(node)


def merge(
    layers: Sequence[tuple[Layer, Path, Mapping[str, object]]],
) -> dict[str, Provenanced[object]]:
    """Flattens every layer's mapping to dotted leaf paths (`"a.b.c"`) and,
    per leaf, keeps the value from the LAST entry in `layers` that declares
    it -- a per-LEAF merge (`SW-0149`), never a per-file replace: a layer
    that is silent on a leaf simply does not win it, and an earlier layer's
    value for that leaf survives untouched. Each resolved leaf is wrapped in
    `Provenanced` naming which layer, file and line it came from."""
    resolved: dict[tuple[str, ...], Provenanced[object]] = {}
    line_cache: dict[Path, dict[tuple[str, ...], int]] = {}
    for layer, path, data in layers:
        if path not in line_cache:
            line_cache[path] = line_index(path) if path.is_file() else {}
        lines = line_cache[path]
        for key_path, value in _flatten(data).items():
            resolved[key_path] = Provenanced(value=value, layer=layer, file=path, line=lines.get(key_path, 0))
    return {".".join(key_path): prov for key_path, prov in resolved.items()}
