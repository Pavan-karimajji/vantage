# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-22 launcher` -- `to_run_config` + `launch` (`WP-28`, `IMP-0343`/
`IMP-0347`): the one seam between the launcher's in-memory `Selection` and
an actual run.

**No invented schema.** `to_run_config` writes exactly the field set
`graph.pipeline.Pipeline.to_yaml`/`Pipeline.load` already read, plus the
`recording:`/`project:`/`config:` top-level keys `runspec.manifest.
RunSpec`/`cli.resim` already read (`WP-15b`'s own real engine bridge) --
never a launcher-only format (`SW-0347`). `launch` takes a **path**, never
a `Selection`: there is no code path from in-memory state to a run
(`CN-0175`), and it re-loads and re-classifies the file it is given rather
than trusting whatever the caller's `Selection` claimed."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from adas_sim.config.roundtrip import dump
from adas_sim.graph.pipeline import Pipeline, stage_setup_doc
from adas_sim.graph.waiver import Waiver
from adas_sim.diagnostics.errors import AuthoringError, exit_code_meaning
from adas_sim.engine.bridge import _ingest_for, pipeline_to_run_spec, resolve_simengine_executable, run_engine
from adas_sim.launcher.command import command_line, command_text
from adas_sim.launcher.classify import LaunchBlocked, classify, warn_orphans
from adas_sim.runspec.canon import write_run_spec
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
                **stage_setup_doc(s),
            }
            for s in pipeline.stages
        ],
        "project": selection.project,
    }
    if pipeline.run_setup:
        data["run_setup"] = dict(pipeline.run_setup)
    if selection.selected_recording is not None:
        data["recording"] = _relative(selection.selected_recording, to=path.parent)
    if selection.config is not None:
        data["config"] = _relative(selection.config, to=path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dump(data))
    return path


def reproduce_line(selection: Selection) -> str:
    """`SW-0021`/`IMP-0022`: the reproducing invocation, rendered directly
    from `selection` -- never composed by reading back previously displayed
    text. Every field `to_run_config` would write (stage mode/impl/inputs,
    project, recording, config) feeds the digest naming the file it would
    write; `Selection.layout` is display-only (its own docstring's "no
    headless reader consumes a layout: key") and is excluded on purpose, so
    changing only a label leaves this line unchanged (`SW-0021` Accept)."""
    pipeline = selection.working_pipeline
    fingerprint_src = "|".join([
        *(f"{s.name}:{s.mode}:{s.impl or ''}:{sorted(s.inputs.items())}" for s in pipeline.stages),
        f"project={selection.project}",
        f"recording={selection.selected_recording}",
        f"config={selection.config}",
    ])
    digest = hashlib.sha256(fingerprint_src.encode("utf-8")).hexdigest()[:8]
    line = f"sim resim --pipeline run_{digest}.yaml"
    for directory in selection.search:
        line += f" --search {directory}"
    return line


def _verdict(findings, waivers) -> str:
    """The setup's `coherence_verdict`: `clean` with no finding that blocks, else `waived:` and every reason, in the order given."""
    if not waivers:
        return "clean"
    return "waived: " + "; ".join(w.reason for w in waivers)


def write_run_setup(
    selection: Selection, path: Path, *, run_id: str | None = None, output_path: Path | None = None,
    exec_timeout_ms: int = 250, waivers: tuple[Waiver, ...] = (),
) -> Path:
    """`IMP-0140` (`SYS-0106`, `SYS-0116`, `SYS-0119`, `SYS-0193`): the engine's run setup for `selection`, written to `path`. The
    selection is classified first and a broken chain no waiver covers raises `LaunchBlocked` before any file is written; a waiver puts
    its reason into `coherence_verdict`. Each simulated stage's `impl.path` is an absolute library path, `sources[0].sha256` the SHA-256
    of the recording's bytes. `selection` keeps nothing the file does not hold (`SYS-0106`)."""
    pipeline = selection.working_pipeline
    result = classify(pipeline, waivers)
    if not result.can_launch:
        raise LaunchBlocked(result.blocking)
    if selection.selected_recording is None:
        raise AuthoringError(expected="a selected recording", found="none", where="launcher.write.write_run_setup",
                             hint="add_recording then select_recording before a setup is written")
    warn_orphans(result)
    recording = Path(selection.selected_recording).resolve()
    out = output_path if output_path is not None else path.with_suffix(".out.mcap")
    spec = pipeline_to_run_spec(
        pipeline, run_id=run_id or f"launch-{path.stem}", recording_path=recording, setup_values=pipeline.setup_values(),
        recording_sha256=hashlib.sha256(recording.read_bytes()).hexdigest(), output_path=out, exec_timeout_ms=exec_timeout_ms,
        coherence_verdict=_verdict(result.findings, waivers),
    )
    # The files added are the files of the one recording (`ARCH §2.3`, `sources[]`), the selected one first (`SYS-0126`).
    for other in (Path(p).resolve() for p in selection.recordings):
        if other != recording:
            spec.data["sources"].append({"path": str(other), "sha256": hashlib.sha256(other.read_bytes()).hexdigest(),
                                         "codec": "mcap", **_ingest_for(other)})
    path.parent.mkdir(parents=True, exist_ok=True)
    write_run_spec(spec, path)
    return path


def launch(
    path: Path, *, search: tuple[Path, ...] = (), waivers: tuple[Waiver, ...] = (), setup_path: Path | None = None,
    supervise: bool = False, attempt_timeout_ms: int | None = None, restart_on_crash: int = 0, threads: int = 1,
    exec_timeout_ms: int = 250,
) -> int:
    """`IMP-0140`: the ONE function a "Launch" action may call. Reloads the run configuration at `path` (`Selection.from_spec`, never
    the `Selection` that wrote it), writes the engine's run setup beside it (`write_run_setup`, which classifies again and raises
    `LaunchBlocked` on an unwaived broken chain, because the file about to run is the only thing that counts), starts the engine on
    that file through `run_engine` and prints the exit code's meaning. A supervised start needs `attempt_timeout_ms` (`SYS-0109`).
    Returns the engine's exit code."""
    selection = Selection.from_spec(path, search=search)
    setup = write_run_setup(selection, setup_path or path.with_suffix(".run.json"), exec_timeout_ms=exec_timeout_ms, waivers=waivers)
    result = run_engine(setup, supervise=supervise, attempt_timeout_ms=attempt_timeout_ms, restart_on_crash=restart_on_crash,
                        threads=threads, search=search, output_path=setup.with_suffix(".out.mcap"))
    print(exit_code_meaning(result.exit_code))
    return result.exit_code


def command_for(
    selection: Selection, setup_path: Path, *, face: str = "developer", deadline_ms: int | None = None, threads: int = 1,
    restart_on_crash: int = 0, engine: Path | None = None, waivers: tuple[Waiver, ...] = (), exec_timeout_ms: int = 250,
) -> list[str]:
    """`IMP-0151` (`SYS-0123`): writes the run setup for `selection` and returns the engine's command line for it, built by
    `command.command_line`: what the window copies, and what `launch_selection` starts."""
    setup = write_run_setup(selection, setup_path, waivers=waivers, exec_timeout_ms=exec_timeout_ms)
    return command_line(engine or resolve_simengine_executable(selection.search), setup, face, deadline_ms=deadline_ms, threads=threads,
                        restart_on_crash=restart_on_crash)


def command_text_for(selection: Selection, setup_path: Path, **kwargs) -> str:
    """`command_for` as the text a shell runs."""
    return command_text(command_for(selection, setup_path, **kwargs))


def launch_selection(
    selection: Selection, setup_path: Path, *, face: str = "developer", deadline_ms: int | None = None, threads: int = 1,
    restart_on_crash: int = 0, engine: Path | None = None, waivers: tuple[Waiver, ...] = (), exec_timeout_ms: int = 250,
) -> int:
    """`IMP-0149` (`SYS-0123`, `SYS-0126`): the window's *start*. Writes the run setup (`write_run_setup`) and starts the engine on that
    file, the face and deadline of `command_for`, so the command run is the command `command_text_for` gave. Returns the exit code."""
    setup = write_run_setup(selection, setup_path, waivers=waivers, exec_timeout_ms=exec_timeout_ms)
    result = run_engine(setup, supervise=face == "batch", attempt_timeout_ms=deadline_ms, restart_on_crash=restart_on_crash, threads=threads,
                        simengine_path=engine, search=selection.search, output_path=setup.with_suffix(".out.mcap"))
    print(exit_code_meaning(result.exit_code))
    return result.exit_code

