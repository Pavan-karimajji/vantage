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
import uuid
from dataclasses import replace
from pathlib import Path

from adas_sim.graph.build import Pipeline
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.runspec.manifest import (
    build_manifest,
    check_library_provenance,
    load_run_spec,
    resolve_swept_config,
    verify_pinned_builds,
)
from adas_sim.engine.bridge import backfill_schema_bytes, count_ticks, overwrite_manifest_meta
from adas_sim.orchestrate.batch import read_checkpoint_divergence
from adas_sim.orchestrate.run import invoke_engine


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
    # `IMP-0224`: only `--save`'s own manifest reads this back
    # (`read_checkpoint_divergence` below) -- allocated only in that case,
    # same "an unsaved run pays for nothing extra" discipline `output_path`
    # itself already follows.
    checkpoint_path = None
    if args.save:
        checkpoint_fd, checkpoint_name = tempfile.mkstemp(suffix=".json", prefix="sim_resim_progress_")
        os.close(checkpoint_fd)  # simengine opens this path itself, same as output_path above
        checkpoint_path = Path(checkpoint_name)
    try:
        run_id = f"resim-{args.pipeline.stem}-{recording.stem}"
        result = invoke_engine(
            pipeline, recording, run_id=run_id, output_path=output_path, config_path=config,
            checkpoint_path=checkpoint_path,
        )
        if not result.ok:
            raise AuthoringError(
                expected="simengine to exit ok (SimExitCode kSimExitOk)",
                found=f"exit_code={result.exit_code}: {result.stderr or result.stdout}",
                where=f"simengine {args.pipeline} {recording}",
                hint="see stderr above for the failing stage/spec",
            )
        tick_count = count_ticks(output_path)
        if args.save:
            # NR-SIM-24, engine.bridge.overwrite_manifest_meta's own
            # docstring: simengine's own writer embeds no run manifest at
            # all -- a real one (component_build_shas included) is built
            # here exactly as core/resim.py's own caller used to, and
            # overwrites the recording's meta. Only a --save'd recording
            # is patched, matching the pre-WP-15b behavior (a temp/
            # cleanup-only output is never read again).
            divergence = read_checkpoint_divergence(checkpoint_path) if checkpoint_path is not None else None
            meta = build_manifest(
                pipeline=pipeline, pipeline_path=args.pipeline, run_kind="resim", source_kind="mcap",
                project=project, recording_path=recording, component_build_shas=pipeline.component_build_shas(),
                component_bundle_paths=pipeline.component_bundle_paths(),
                component_bundle_shas=pipeline.component_bundle_shas(),
                bundle_overrides=spec.overrides, base_bundle_sha=resolved.base_bundle_sha,
                run_spec_sha256=result.spec_sha256, divergence=divergence if divergence is not None else "unknown",
            )
            # build_manifest's own process_nonce is a module-level constant
            # (runspec/manifest.py::_PROCESS_NONCE) scoped to the PYTHON
            # CALLER's process -- correct pre-WP-15b, when that process
            # also did the computing. Now every call launches a genuinely
            # fresh simengine subprocess to compute the actual result
            # (R-SIM-24's own same_process/fresh_process axis is about
            # THAT), so two `sim resim` calls from one Python process (a
            # script driving several resims, or this same pytest process)
            # would otherwise share one nonce and read back as
            # same_process despite two independently-computing engine
            # processes -- overridden here, per call, to the subprocess
            # this specific run just launched.
            meta = replace(meta, process_nonce=uuid.uuid4().hex)
            overwrite_manifest_meta(output_path, meta)
            # E2E-07 item 8 (SM-12): simcore's own writer cannot embed a
            # topic's real FileDescriptorSet (BuildOutputTopics's own
            # comment -- Writer::Open runs before any component loads);
            # backfill it now from pipeline's own already-loaded
            # component manifests, the same "engine writes what it can,
            # Python patches what it couldn't reach yet" shape this row's
            # own manifest-meta patch above already uses.
            backfill_schema_bytes(output_path, pipeline)
            print(f"wrote {args.save}")
    finally:
        if resolved.scratch_dir is not None:
            shutil.rmtree(resolved.scratch_dir, ignore_errors=True)
        if cleanup_output:
            output_path.unlink(missing_ok=True)
            output_path.with_suffix(output_path.suffix + ".spec.json").unlink(missing_ok=True)
        if checkpoint_path is not None:
            checkpoint_path.unlink(missing_ok=True)
            capture_dir = checkpoint_path.parent / (checkpoint_path.name + "_input_capture")
            shutil.rmtree(capture_dir, ignore_errors=True)

    print(f"resim complete: {tick_count} tick(s)")
    return 0
