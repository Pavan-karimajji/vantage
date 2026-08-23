# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim resim <recording> --pipeline <p.yaml>` -- re-execute against a recording.

Runs the pipeline's stages over an existing recording, deterministically. This
is the mode CI uses. `--save` writes the result as a new recording.

`recording`, `--project` and `--config` each fall back to the pipeline file's
own key when omitted, so a run manifest resims with `--pipeline` alone. An
explicit flag always wins.
"""

# Design refs: `GT-9` · engine is `engine/bridge.py` -> `simengine` (`WP-15b`,
# `IMP-0422`; `core/resim.py` retired from this call site) · `R-SIM-5` resim
# is the deterministic mode · `UT-D3-4`, `NR-SIM-24`

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path

from adas_sim.graph.build import Pipeline
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.runspec.manifest import (
    check_library_provenance,
    load_run_spec,
    resolve_swept_config,
    verify_pinned_builds,
)
from adas_sim.engine.bridge import run_pipeline_via_engine
from adas_sim.io.base import group_by_log_time
from adas_sim.plugins.registry import reader_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim resim", description=__doc__)
    parser.add_argument(
        "recording", type=Path, nargs="?", default=None,
        help="a recording to resim against (falls back to --pipeline's own recording: key if omitted)",
    )
    parser.add_argument("--pipeline", type=Path, required=True, help="the pipeline YAML (or run manifest) to execute")
    parser.add_argument("--save", type=Path, help="write this resim's own freshly-computed tick outputs to a new recording")
    parser.add_argument(
        "--search", type=Path, action="append", default=[],
        help="a directory to search for a dll:/stubdll: stage's library "
            "(repeatable)",
    )
    parser.add_argument(
        "--project", default=None,
        help="falls back to --pipeline's own project: key, else 'base'",
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="config path forwarded to each stage's adasInit; falls back to the "
            "bundle beside the library, then to --pipeline's config: key",
    )
    parser.add_argument(
        "--pin-builds", action="store_true",
        help="refuse to start unless every simulate stage's resolved library "
            "byte-matches the library_sha256 the recording was made with "
            "(NR-SIM-24)",
    )
    return parser


def _count_ticks(output_path: Path) -> int:
    """Ticks are the resim's own unit of progress (`resim_pipeline`'s
    previous return value, one entry per input group) -- read back from
    the engine's own output recording rather than counted in Python, since
    `WP-15b` moved tick execution to `simengine` (`R-SIM-16`)."""
    reader = reader_for(output_path)
    try:
        topics = reader.topics()
        messages = list(reader.messages())
        return sum(1 for _ in group_by_log_time(messages, expected_topics=topics.keys()))
    finally:
        reader.close()


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    spec = load_run_spec(args.pipeline)
    recording = args.recording if args.recording is not None else spec.recording
    if recording is None:
        raise AuthoringError(
            expected="a recording (positional argument, or a recording: key in --pipeline's own file)",
            found="neither given", where=str(args.pipeline), hint="",
        )
    project = args.project if args.project is not None else spec.project
    config = args.config if args.config is not None else spec.config

    # NR-SIM-6, UT-C5-6/7: a declared run.overrides: (spec.overrides) derives
    # a swept bundle from `config` -- `resolved.effective_config` is what
    # actually reaches adasInit, `config` itself is unchanged when no sweep
    # was declared (resolve_swept_config's own passthrough).
    resolved = resolve_swept_config(config, spec.overrides, project=project)
    config = resolved.effective_config

    pipeline = Pipeline.load(args.pipeline, search=args.search)
    if args.pin_builds:
        verify_pinned_builds(pipeline, recording)
    else:
        # UT-C2-9's own default: a differing library hash is a WARNING,
        # not a refusal -- --pin-builds already covers the harder claim
        # above, so this only runs when that opt-in gate wasn't asked for.
        check_library_provenance(pipeline, recording)

    # WP-15b (IMP-0422): execution moved to `simengine`, out of process
    # (`engine.bridge` -- `simcore` is a STATIC library with no in-process
    # ABI artifact to bind, see that module's own docstring). `pipeline`
    # is still built above for provenance checks and `pipeline_to_run_spec`'s
    # own manifest/library-path reads; it is never `init_components`'d or
    # `exec()`'d in this process any more.
    output_path = args.save
    cleanup_output = False
    if output_path is None:
        fd, tmp_name = tempfile.mkstemp(suffix=".mcap", prefix="sim_resim_")
        os.close(fd)  # the writer (a separate simengine process) opens this path itself
        output_path = Path(tmp_name)
        cleanup_output = True
    try:
        run_id = f"resim-{args.pipeline.stem}-{recording.stem}"
        result = run_pipeline_via_engine(
            pipeline, recording, run_id=run_id, output_path=output_path, config_path=config,
        )
        if not result.ok:
            raise AuthoringError(
                expected="simengine to exit ok (SimExitCode kSimExitOk)",
                found=f"exit_code={result.exit_code}: {result.stderr or result.stdout}",
                where=f"simengine {args.pipeline} {recording}",
                hint="see stderr above for the failing stage/spec",
            )
        tick_count = _count_ticks(output_path)
        if args.save:
            print(f"wrote {args.save}")
    finally:
        if resolved.scratch_dir is not None:
            shutil.rmtree(resolved.scratch_dir, ignore_errors=True)
        if cleanup_output:
            output_path.unlink(missing_ok=True)
            output_path.with_suffix(output_path.suffix + ".spec.json").unlink(missing_ok=True)

    print(f"resim complete: {tick_count} tick(s)")
    return 0
