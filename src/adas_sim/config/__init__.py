# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`load`/`validate_only` (`SW-0154`/`SW-0165`) -- the config layer's own
entry point. Locates every declared file per `FileKind`, expands `!include`
+ `${var}` (`config/include.py`), validates EACH LAYER against its kind's
schema (`config/kinds.py` + `config/schema.py`) before merging, then merges
the layers (`config/layers.py`) into one `Provenanced` value per leaf.

**Everything here runs once per run, with no recording and no binary**
(`ANL-SW-34`, `Part C`'s own boundary): the "every reference resolves"
discipline `R-SIM-*`/`CN-0346` states is checked here only as far as
config-layer text can check it (a `wiring:` reference must name a unit this
run's own `COMPOSITION` layer declares); the recording-index and DLL-type-
matching half of that same discipline needs a real manifest/recording and is
`WP-05`'s own seam (`IF-09`), not this module's.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from adas_sim.config import include, schema
from adas_sim.config.kinds import FileKind, check_composition_no_cross_unit_reference, check_disjoint_keys
from adas_sim.config.layers import Layer, Provenanced, merge
from adas_sim.config.paths import ConfigPaths

#: Where each layer's file lives within a kind's own directory
#: (`ConfigPaths.dir_for`) -- `Layer.CLI` has no file; it is supplied
#: programmatically (see `load`'s `cli` parameter).
_LAYER_FILENAMES: Mapping[Layer, str] = {
    Layer.PACKAGE: "package.yaml",
    Layer.PROJECT: "project.yaml",
    Layer.RUN: "run.yaml",
}


@dataclass(frozen=True, slots=True)
class RawConfig:
    """One layer of one kind, `!include`/`${var}`-expanded but not yet
    merged with any other layer -- what `validate` checks."""

    kind: FileKind
    path: Path
    data: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    """Every kind's merged, per-leaf-provenanced configuration -- `load`'s
    return value."""

    resolved: Mapping[FileKind, Mapping[str, Provenanced[object]]]


def validate(cfg: RawConfig) -> None:
    """Every load-time check the config layer can run with no recording and
    no binary (`ANL-SW-34`): declared keys belong to this kind
    (`kinds.check_disjoint_keys`), `version:` in range (`schema.
    check_version`), the full published schema (`schema.validate`), and --
    `COMPOSITION` only -- no cross-unit reference (`IMP-0398`). Raises
    `AuthoringError` naming the file."""
    check_disjoint_keys(cfg.kind, cfg.data, where=str(cfg.path))
    schema.check_version(cfg.kind, cfg.data, where=str(cfg.path))
    schema.validate(cfg.kind, cfg.data, path=cfg.path)
    if cfg.kind is FileKind.COMPOSITION:
        check_composition_no_cross_unit_reference(cfg.data, where=str(cfg.path))


def load(
    paths: ConfigPaths,
    cli: Mapping[FileKind, Mapping[str, object]] | None = None,
    *,
    variables: Mapping[str, str] | None = None,
) -> ResolvedConfig:
    """For every `FileKind`, reads whichever of `package.yaml`/`project.
    yaml`/`run.yaml` exist under `paths.dir_for(kind)`, expands includes and
    variables, validates each one (`validate`, before any merge -- a bad
    file fails naming itself, never after being silently absorbed into a
    merged result), then merges the layers present plus `cli[kind]` if
    given (`Layer.CLI`, always last, always wins). `cli` is supplied data,
    not a file someone could typo -- it is merged but not schema-validated;
    a caller assembling it programmatically owns its correctness the same
    way any other Python caller owns its own arguments."""
    variables = variables or {}
    cli = cli or {}
    resolved: dict[FileKind, Mapping[str, Provenanced[object]]] = {}

    for kind in FileKind:
        kind_dir = paths.dir_for(kind)
        entries: list[tuple[Layer, Path, Mapping[str, object]]] = []
        for layer, filename in _LAYER_FILENAMES.items():
            file_path = kind_dir / filename
            if not file_path.is_file():
                continue
            expanded = include.expand(file_path)
            substituted, _used = include.resolve_vars(expanded, variables, source=file_path, layer=layer)
            cfg = RawConfig(kind=kind, path=file_path, data=substituted)
            validate(cfg)
            entries.append((layer, file_path, cfg.data))
        if kind in cli:
            entries.append((Layer.CLI, Path("<cli>"), cli[kind]))
        resolved[kind] = merge(entries) if entries else {}

    return ResolvedConfig(resolved=resolved)


def validate_only(
    paths: ConfigPaths,
    cli: Mapping[FileKind, Mapping[str, object]] | None = None,
    *,
    variables: Mapping[str, str] | None = None,
) -> ResolvedConfig:
    """`CN-0128`, `IMP-0165`: the fast-lint path -- identical to `load`,
    since this module never opens a recording or a binary regardless
    (`ANL-SW-34`). Named separately so a caller's intent ("just check,
    don't run") is explicit at the call site; `sim validate` (not yet
    wired to a CLI -- outside this `WP`'s own `adas_sim/config/**` scope)
    will call this."""
    return load(paths, cli, variables=variables)
