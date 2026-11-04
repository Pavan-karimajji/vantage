# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`dry_run` (`IMP-0147`, `SYS-0121`): the launcher's dry run. It resolves the configuration of a project (`config.load`) and prints each
resolved value with the layer, file and line it came from (`Provenanced`), calling no component and starting no engine run."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from adas_sim.config import load
from adas_sim.config.kinds import FileKind
from adas_sim.config.layers import Layer
from adas_sim.config.paths import ConfigPaths


def dry_run(paths: ConfigPaths, cli: Mapping[FileKind, Mapping[str, object]] | None = None,
            variables: Mapping[str, str] | None = None) -> list[str]:
    """One line per resolved value: `<kind>.<key> = <value>   [<layer>  <file>:<line>]`, kinds and keys in order."""
    resolved = load(paths, cli, variables=variables).resolved
    lines: list[str] = []
    for kind in FileKind:
        for key, leaf in sorted(resolved.get(kind, {}).items()):
            where = "cli" if leaf.layer is Layer.CLI else f"{leaf.file}:{leaf.line}"
            lines.append(f"{kind.value}.{key} = {leaf.value!r}   [{leaf.layer.value}  {where}]")
    return lines
