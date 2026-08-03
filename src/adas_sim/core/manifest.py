# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`build_manifest` -- assembles a `RunManifest` (`io.base.RunManifest`,
already built at `S-A4Δ`) for a run about to happen (`S-C2`,
`sim_resim_and_recording.md` §2). Thin on purpose: the run id itself is
`core.ids.new_run_id`'s job, already built and already enforcing its
`REQUIRED_KEYS`; this module's only work is gathering those keys from a
`Pipeline` and its inputs.
"""

from __future__ import annotations

import hashlib
import socket
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.ids import new_run_id
from adas_sim.io.base import CAPTURE_TIME_MANIFEST_VERSION, ComponentBuildInfo, RunManifest


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _overrides_repr(pipeline: Pipeline) -> str:
    """A stable, sorted text form of every stage's overrides -- part of
    `new_run_id`'s hashed input set (`R-SIM-15`'s "declared, never
    smuggled" extended to the run id: two runs differing only in their
    overrides must never collide on one id)."""
    parts = [
        f"{stage.name}.{key}={override.verb.value}:{override.value}"
        for stage in pipeline.stages for key, override in sorted(stage.overrides.items())
    ]
    return "|".join(parts)


def build_manifest(
    *,
    pipeline: Pipeline | None = None,
    pipeline_path: Path | None = None,
    run_kind: str,
    source_kind: str,
    project: str = "base",
    scenario_name: str = "",
    scenario_path: Path | None = None,
    recording_path: Path | None = None,
    component_build_shas: Mapping[str, str] | None = None,
    bundle_sha: str = "",
    seed: int = 0,
    host: str = "",
    clock: datetime | None = None,
) -> RunManifest:
    """`run_kind` is `"sim"` or `"resim"` (`RunManifest.run_kind`);
    `source_kind` is `"carla"` / `"synthetic"` / ... (`Source.name`).
    `recording_path` is the INPUT recording for a resim, absent for a fresh
    `sim record` (there is nothing yet to hash) -- `recording_sha256` is
    then `""`, a real, honest value for `new_run_id`'s hash, not a
    placeholder. `component_build_shas` defaults to empty: no per-library
    hash exists yet at `S-C2` (that's `S-C5`'s packed config bundle); a
    caller that has one (a real `dll:` stage) supplies it keyed by stage
    name.

    `pipeline`/`pipeline_path` are both optional: `sim record`
    (`sim_resim_and_recording.md` §9's own "executes a SUT: no") has no
    pipeline at all, only a `Source` -- `pipeline_sha`/`overrides_repr`
    then fall back to `""`, real honest values for a run this framework
    genuinely did not wire through a pipeline file, not placeholders for
    one it forgot to pass."""
    component_build_shas = component_build_shas or {}
    pipeline_sha = _sha256_file(pipeline_path) if pipeline_path is not None and pipeline_path.exists() else ""
    recording_sha = _sha256_file(recording_path) if recording_path is not None and recording_path.exists() else ""
    scenario_sha = _sha256_file(scenario_path) if scenario_path is not None and scenario_path.exists() else ""
    overrides_repr = _overrides_repr(pipeline) if pipeline is not None else ""

    run_id = new_run_id(
        inputs={
            "pipeline_sha": pipeline_sha,
            "recording_sha": recording_sha,
            "project": project,
            "component_build_shas": "|".join(f"{k}={v}" for k, v in sorted(component_build_shas.items())),
            "bundle_sha": bundle_sha,
            "overrides_repr": overrides_repr,
            "seed": str(seed),
        },
        clock=clock,
    )

    components = tuple(
        ComponentBuildInfo(name=stage.name, library_sha256=component_build_shas.get(stage.name, ""))
        for stage in pipeline.stages if stage.mode != "off"
    ) if pipeline is not None else ()

    when = clock if clock is not None else datetime.now(timezone.utc)
    return RunManifest(
        manifest_version=CAPTURE_TIME_MANIFEST_VERSION,
        run_id=run_id,
        run_kind=run_kind,
        created_utc=when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        host=host or socket.gethostname(),
        source_kind=source_kind,
        scenario=scenario_name,
        scenario_sha256=scenario_sha,
        recording=str(recording_path) if recording_path is not None else "",
        recording_sha256=recording_sha,
        project=project,
        pipeline=pipeline.name if pipeline is not None else "",
        components=components,
        seed=seed,
    )
