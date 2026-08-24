# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-22 launcher` -- `to_run_config` + `launch` (`WP-28`, `IMP-0343`/
`IMP-0347`): the one seam between the launcher's in-memory `Selection` and
an actual run.

**No invented schema.** `to_run_config` writes exactly the field set
`graph.build.Pipeline.to_yaml`/`Pipeline.load` already read, plus the
`recording:`/`project:`/`config:` top-level keys `runspec.manifest.
RunSpec`/`cli.resim` already read (`WP-15b`'s own real engine bridge) --
never a launcher-only format (`SW-0347`). `launch` takes a **path**, never
a `Selection`: there is no code path from in-memory state to a run
(`CN-0175`), and it re-loads and re-classifies the file it is given rather
than trusting whatever the caller's `Selection` claimed."""

from __future__ import annotations

import os
from pathlib import Path

from adas_sim.config.roundtrip import dump
from adas_sim.graph.build import Pipeline
from adas_sim.graph.waiver import Waiver
from adas_sim.launcher.classify import LaunchBlocked, classify
from adas_sim.launcher.model import Selection


def _relative(target: Path, *, to: Path) -> str:
    """`runspec.manifest._relative_or_raise`'s own requirement, satisfied
    at write time rather than caught at load time: `recording:`/`config:`
    travel as paths relative to the file that names them (`UT-D3-6`)."""
    return os.path.relpath(target.resolve(), start=to.resolve())


def to_run_config(selection: Selection, path: Path) -> Path:
    """`IMP-0343`/`IMP-0347`: builds the pipeline-YAML dict `Pipeline.
    to_yaml` itself would emit for `selection.working_pipeline` (`impl:`
    overlaid per stage, since `working_pipeline`'s own copy keeps the
    BASE `impl:` for a stage whose manifest was never re-resolved -- see
    `launcher/model.py::_with_impl`'s own note), overlays the top-level
    `recording:`/`project:`/`config:` keys, and writes it through `config.
    roundtrip.dump` -- the one YAML writer this package owns (`SW-0155`).
    Returns `path` unchanged, for chaining into `launch`."""
    pipeline = selection.working_pipeline
    data: dict[str, object] = {
        "version": pipeline.version,
        "name": pipeline.name,
        "stages": [
            {
                "name": s.name, "mode": s.mode,
                **({"impl": s.impl} if s.impl is not None else {}),
                "inputs": dict(s.inputs),
            }
            for s in pipeline.stages
        ],
        "project": selection.project,
    }
    if selection.selected_recording is not None:
        data["recording"] = _relative(selection.selected_recording, to=path.parent)
    if selection.config is not None:
        data["config"] = _relative(selection.config, to=path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dump(data))
    return path


def launch(path: Path, *, search: tuple[Path, ...] = (), waivers: tuple[Waiver, ...] = ()) -> int:
    """`IMP-0343`: the ONE function a "Launch" action may call. Reloads
    `path` with `Pipeline.load` (never the `Selection` that wrote it),
    classifies the RELOADED pipeline (`launcher.classify.classify`) and
    raises `LaunchBlocked` on an unwaived `BROKEN` chain -- coherence is
    checked again here, not only at selection time, because the file on
    disk is the only thing about to run (`SW-0342`'s block belongs to the
    artifact, not to a UI state that may since have drifted from it).
    Delegates to `cli.resim.run(["--pipeline", str(path)])`, the SAME
    function `sim resim --pipeline <path>` invokes from the command line --
    so a run started here and a headless re-run of the same file are
    identical by construction (`IT-21`)."""
    pipeline = Pipeline.load(path, search=search)
    result = classify(pipeline, waivers)
    if not result.can_launch:
        raise LaunchBlocked(result.blocking)

    from adas_sim.cli.resim import run as _resim_run

    argv = ["--pipeline", str(path)]
    for directory in search:
        argv += ["--search", str(directory)]
    return _resim_run(argv)
