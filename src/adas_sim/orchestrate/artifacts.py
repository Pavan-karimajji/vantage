# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SW-0236`/`SW-0237`: every run writes to its own artifact directory, and
that directory is self-contained -- a downloaded copy opens in the player
with no access to the originating machine (`R-SIM-3a`'s config-bundle
discipline, applied at the per-run granularity every face shares).

`run_dir(out, run_id)` is the one place this layout is decided:

    <out>/<run_id>/
        spec/          the resolved Run Spec / pipeline this run executed
        manifest/       the run manifest (`runspec/manifest.py::write_manifest`)
        exports/        `--save`d recordings, CSV exports, reports
        logs/           captured stdout/stderr excerpts
        checkpoints/    per-recording checkpoint files (`orchestrate/batch.py`)
        config/         the config bundle this run resolved (`R-SIM-3a`),
                        copied in -- never a path reference -- so the
                        directory answers `SW-0237`'s "no source checkout"
                        test standalone.

Two concurrent runs never collide because `run_id` is already unique per run
(`runspec/manifest.py::new_run_id`, content-derived) -- `run_dir` itself does
not invent uniqueness, it only lays out one run's own directory once a caller
has a `run_id`."""

from __future__ import annotations

import shutil
from pathlib import Path

#: The layout every run directory carries -- fixed, not per-caller, so a
#: downloaded directory is navigable without reading this module's source.
_SUBDIRS = ("spec", "manifest", "exports", "logs", "checkpoints", "config")


def run_dir(out: Path, run_id: str) -> Path:
    """Creates (idempotently) `<out>/<run_id>/` with every declared
    subdirectory and returns it. Never removes an existing directory -- a
    caller resuming a run (`SW-0249`) reopens the same path."""
    directory = out / run_id
    for name in _SUBDIRS:
        (directory / name).mkdir(parents=True, exist_ok=True)
    return directory


def embed_config_bundle(directory: Path, bundle_dir: Path) -> Path:
    """Copies `bundle_dir`'s contents (byte-for-byte, `bundle.sha256`
    included) into `directory / "config"` -- never a symlink and never a
    path reference -- so `SW-0237`'s self-containment holds for the config
    half the same way `R-SIM-6` already holds for the recorded bytes half.
    Returns the destination directory."""
    dest = directory / "config"
    dest.mkdir(parents=True, exist_ok=True)
    for item in bundle_dir.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
    return dest


def is_self_contained(directory: Path) -> tuple[bool, tuple[str, ...]]:
    """`SW-0237`'s own check, machine-runnable: every declared subdirectory
    exists under `directory`, and `config/` -- when present at all -- carries
    its own `bundle.sha256` rather than being empty. Returns `(ok, reasons)`;
    `reasons` names exactly what is missing, never a bare `False`
    (`R-SIM-25`/`NR-SIM-4`)."""
    reasons: list[str] = []
    for name in _SUBDIRS:
        if not (directory / name).is_dir():
            reasons.append(f"missing subdirectory: {name}")
    config_dir = directory / "config"
    if config_dir.is_dir() and any(config_dir.iterdir()) and not (config_dir / "bundle.sha256").exists():
        reasons.append("config/ is non-empty but carries no bundle.sha256")
    return (not reasons, tuple(reasons))
