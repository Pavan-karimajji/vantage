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

# Design refs: `GT-9` · engine is `core/resim.py` (`check/` needs it and may not import
# `cli/`) · `R-SIM-5` resim is the deterministic mode · `UT-D3-4`, `NR-SIM-24`

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.errors import AuthoringError
from adas_sim.core.manifest import (
    build_manifest,
    check_library_provenance,
    load_run_spec,
    resolve_swept_config,
    verify_pinned_builds,
)
from adas_sim.core.resim import resim_pipeline
from adas_sim.io.base import Provenance, TopicInfo
from adas_sim.io.registry import writer_for
from adas_sim.sources.recorder import topic_for


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


def _save_outputs(pipeline: Pipeline, outputs: list[tuple[int, dict]], path: Path, meta) -> None:
    """`--save`: only the freshly-computed (`mode: simulate`) stages' own
    outputs -- a `measured` stage contributed nothing new this resim, and
    the original recording already carries its bytes (`R-SIM-6`), so
    re-writing them here would be a second, redundant copy, not new
    evidence."""
    simulate_stages = [stage for stage in pipeline.stages if stage.mode == "simulate"]
    topics = {}
    for stage in simulate_stages:
        manifest = pipeline.manifest_for(stage.name)
        for port_spec in manifest.outputs:
            name = f"{stage.name}.{port_spec.name}"
            # R-SIM-11: descriptor_set, so this file decodes on replay
            # instead of staying raw bytes (previously never wired in here).
            topics[topic_for(name)] = TopicInfo(
                schema_name=port_spec.proto_type or name, provenance=Provenance.SIMULATED,
                schema_bytes=manifest.descriptor_set,
            )

    writer = writer_for(path)
    writer.open(path, meta, topics)
    for t_ns, tick_outputs in outputs:
        for stage in simulate_stages:
            for port_name, payload in tick_outputs.get(stage.name, {}).items():
                writer.write(topic_for(f"{stage.name}.{port_name}"), t_ns, payload, capture_time_ns=t_ns)
    writer.close()


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
    pipeline.init_components(config)
    try:
        outputs = resim_pipeline(pipeline, recording)
    finally:
        pipeline.shutdown_components()
        if resolved.scratch_dir is not None:
            shutil.rmtree(resolved.scratch_dir, ignore_errors=True)

    if args.save:
        meta = build_manifest(
            pipeline=pipeline, pipeline_path=args.pipeline, run_kind="resim", source_kind="mcap",
            project=project, recording_path=recording, component_build_shas=pipeline.component_build_shas(),
            bundle_overrides=spec.overrides, base_bundle_sha=resolved.base_bundle_sha,
        )
        _save_outputs(pipeline, outputs, args.save, meta)
        print(f"wrote {args.save}")

    print(f"resim complete: {len(outputs)} tick(s)")
    return 0
