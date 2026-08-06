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

`RunSpec`/`load_run_spec`/`write_run_manifest` (S-D3): a DIFFERENT
"manifest" from `RunManifest` above -- that one is post-run PROVENANCE,
embedded in a recording after the fact, with no per-stage mode/impl
fields at all. This one is a pre-run CONFIGURATION: which recording,
project and config to run a pipeline against, plus this session's
mode: overrides -- what `sim resim <manifest>` would otherwise need five
flags for, and what `PipelinePanelState`'s toggles need a file to land in.
Deliberately **not** a new schema (agreed with the user before building):
a run manifest IS a pipeline YAML file, with three optional extra
top-level keys (`recording:`/`project:`/`config:`) `Pipeline.load()`
itself never reads. `stages:` stays the identical shape, so the SAME
parser reads a plain pipeline file and a run manifest -- there is no
second format to keep in sync.
"""

from __future__ import annotations

import hashlib
import os
import socket
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from warnings import warn

import yaml

from adas_sim.contracts.pipeline import Pipeline, record_policy_for
from adas_sim.core.errors import AuthoringError, ContractError, ProvenanceWarning
from adas_sim.core.ids import new_run_id
from adas_sim.io.base import (
    CAPTURE_TIME_MANIFEST_VERSION,
    ComponentBuildInfo,
    OverrideRecord,
    RecordPolicyRecord,
    RunManifest,
)
from adas_sim.io.registry import reader_for

#: `S-C6` (`R-SIM-24`): generated ONCE per process, at import time -- every
#: `RunManifest` this process builds carries the same value, which is exactly
#: `sim determinism`'s same-process signal. A per-call `uuid4()` would make
#: two runs in one process look like two different processes.
_PROCESS_NONCE = uuid.uuid4().hex


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


def _override_records(pipeline: Pipeline) -> tuple[OverrideRecord, ...]:
    """The same declared overrides `_overrides_repr` hashes, as the
    structured, actually-readable form `RunManifest.overrides` carries
    (`S-D6`, `UT-D6-2`) -- same sort order, so the two never disagree
    about which override came first."""
    return tuple(
        OverrideRecord(stage=stage.name, address=key, verb=override.verb.value, value=override.value)
        for stage in pipeline.stages for key, override in sorted(stage.overrides.items())
    )


def _record_policy_records(pipeline: Pipeline) -> tuple[RecordPolicyRecord, ...]:
    """Every non-`off` stage's own declared output ports, each with its
    resolved `record:` policy (`UT-C2-12`, `NR-SIM-42`) -- written for
    `full` ports too, not only `excluded`/`decimated` ones, so a reader
    answers "was this recording complete?" from the manifest alone.
    `sources/recorder.py` is a DIFFERENT concern (it decides what to
    physically WRITE for a port, honouring the same policy) -- this is the
    declaration, always complete regardless of what got written."""
    records: list[RecordPolicyRecord] = []
    for stage in pipeline.stages:
        if stage.mode == "off":
            continue
        manifest = pipeline.manifest_for(stage.name)
        for port_spec in manifest.outputs:
            policy = record_policy_for(stage, port_spec.name)
            records.append(RecordPolicyRecord(
                port=f"{stage.name}.{port_spec.name}", verb=policy.verb.value,
                decimate_n=policy.decimate_n or 0,
            ))
    return records


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
    component_bundle_paths: Mapping[str, str] | None = None,
    component_bundle_shas: Mapping[str, str] | None = None,
    config_bundle_embedded: bool = False,
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

    `component_bundle_paths`/`component_bundle_shas` (`S-C5`, `sim_resim_
    and_recording.md` §2's `sut.components[]`): the resolved bundle
    directory's path and its `bundle.sha256`, per stage -- `config_bundle`
    is a display string (the path a reader would check), never bundle
    bytes; the bytes themselves go on the separate `/meta/config_bundle`
    topic (`Recorder.open`'s `config_bundle_bytes`), embedded once per
    recording, not per component. `config_bundle_embedded` states whether
    THIS recording actually carries those bytes -- a run with a resolved
    bundle but no recording in progress (e.g. `sim resim`'s own SUT) leaves
    it `False`, honestly.

    `pipeline`/`pipeline_path` are both optional: `sim record`
    (`sim_resim_and_recording.md` §9's own "executes a SUT: no") has no
    pipeline at all, only a `Source` -- `pipeline_sha`/`overrides_repr`
    then fall back to `""`, real honest values for a run this framework
    genuinely did not wire through a pipeline file, not placeholders for
    one it forgot to pass."""
    component_build_shas = component_build_shas or {}
    component_bundle_paths = component_bundle_paths or {}
    component_bundle_shas = component_bundle_shas or {}
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
        ComponentBuildInfo(
            name=stage.name,
            library_sha256=component_build_shas.get(stage.name, ""),
            config_bundle=component_bundle_paths.get(stage.name, ""),
            config_bundle_sha256=component_bundle_shas.get(stage.name, ""),
            config_bundle_embedded=config_bundle_embedded,
        )
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
        overrides=_override_records(pipeline) if pipeline is not None else (),
        record_policies=tuple(_record_policy_records(pipeline)) if pipeline is not None else (),
        seed=seed,
        allow_mixed_projects=pipeline.allow_mixed_projects if pipeline is not None else False,
        process_nonce=_PROCESS_NONCE,
    )


def verify_pinned_builds(pipeline: Pipeline, recording_path: Path) -> None:
    """`sim resim --pin-builds` (`UT-D7-9`, `OQ-9`/`NR-SIM-24`,
    `sim_resim_and_recording.md` "Pinning a resim to the build that
    produced it"): refuses to start rather than silently resim against a
    different build than the one that produced `recording_path`.

    Reads `recording_path`'s OWN embedded run manifest (`RecordingReader.
    meta()`, `R-SIM-6`) for each `mode: simulate` stage's previously
    recorded `library_sha256`, and compares it against `pipeline`'s
    CURRENTLY resolved library (`Pipeline.component_build_shas`) for that
    same stage. A `components=`-supplied stage (no file on disk, e.g. a
    test's `InProcessSilComponent`) has nothing to verify and is skipped --
    same reasoning `_validate_cross_component_agreement` already uses for
    the bundle-directory check.

    Verification, not addressing (`impl: pkg:` still does not exist) -- a
    package reference alone would prove nothing anyway (`ComponentBuildInfo.
    package_ref`'s own docstring); the byte hash is the actual claim. **The
    honest limit is a refusal, not a silent pass**: a stage the recording
    carries no `library_sha256` for (an older recording, or one whose
    library was never resim'd for real) is reported as **unpinnable**
    rather than treated as a match -- the entire point of this flag is a
    hard guarantee, and treating "unknown" as "fine" would defeat it
    (`R-SIM-25`/`NR-SIM-4`)."""
    reader = reader_for(recording_path)
    try:
        recorded_shas = {c.name: c.library_sha256 for c in reader.meta().components}
    finally:
        reader.close()
    current_shas = pipeline.component_build_shas()

    for stage in pipeline.stages:
        if stage.mode != "simulate" or stage.name not in current_shas:
            continue
        current_sha = current_shas[stage.name]
        recorded_sha = recorded_shas.get(stage.name, "")
        if not recorded_sha:
            raise ContractError(
                expected="a library_sha256 this recording was pinned against",
                found="none -- this recording carries no verifiable build hash for this stage",
                where=f"stage '{stage.name}' ({recording_path})",
                hint="unpinnable: record a new baseline with a real dll:/stubdll: build, or drop --pin-builds",
            )
        if recorded_sha != current_sha:
            raise ContractError(
                expected=f"library_sha256={recorded_sha} (the build that produced this recording)",
                found=f"library_sha256={current_sha} (the build currently resolved)",
                where=f"stage '{stage.name}' ({recording_path})",
                hint="rebuild to match, or point --search at the matching artifact",
            )


def check_library_provenance(pipeline: Pipeline, recording_path: Path) -> None:
    """`UT-C2-9`'s own warning half: "a differing library hash is a
    **warning**" -- the default, unconditional check every resim gets,
    unlike `verify_pinned_builds` above (`--pin-builds`'s own opt-in HARD
    refusal). Same comparison, deliberately different severity: detection
    is always on; escalating a mismatch into a gate is a choice the caller
    makes, not this function's.

    **Never warns on "unknown."** A recording with no recorded
    `library_sha256` for a stage (the overwhelming majority of recordings
    made before `UT-D7-9` started populating it for real) is silent here --
    `verify_pinned_builds` is where "unknown" gets treated as a refusal;
    warning on it by default would make every ordinary resim noisy for a
    fact nobody withheld, only never recorded (`R-SIM-25`/`NR-SIM-4`: a
    missing fact and a contradicting one are different statements).

    **No file opened at all when there is nothing to check** -- a pipeline
    with no `mode: simulate` stage (every stage `measured`/`off`, or a
    pure-mock/test double) has no library to compare, so this returns
    before touching `recording_path`, not after opening it and finding
    nothing."""
    if not any(stage.mode == "simulate" for stage in pipeline.stages):
        return
    reader = reader_for(recording_path)
    try:
        recorded_shas = {c.name: c.library_sha256 for c in reader.meta().components}
    finally:
        reader.close()
    current_shas = pipeline.component_build_shas()

    for stage in pipeline.stages:
        if stage.mode != "simulate" or stage.name not in current_shas:
            continue
        current_sha = current_shas[stage.name]
        recorded_sha = recorded_shas.get(stage.name, "")
        if recorded_sha and recorded_sha != current_sha:
            warn(ProvenanceWarning(
                f"stage '{stage.name}': library_sha256 differs from the recording that produced it "
                f"(recorded {recorded_sha}, resolved {current_sha}) -- results may not reproduce it exactly "
                f"({recording_path})"
            ))


@dataclass(frozen=True, slots=True)
class RunSpec:
    """A pipeline file's own optional `recording:`/`project:`/`config:`
    keys, resolved. `RunSpec()` (every field absent/default) is what a
    plain pipeline file with none of these keys decodes to -- unchanged
    from being just a pipeline definition, same "degrades and says so"
    shape `RunManifest`'s own `manifest_version=0` uses."""

    recording: Path | None = None
    project: str = "base"
    config: Path | None = None


def _relative_or_raise(raw: object, *, key: str, path: Path) -> Path | None:
    """UT-D3-6: a run manifest contains no absolute path, so it can be
    committed, shared and replayed on another machine. Resolved relative
    to the manifest FILE's own directory -- the manifest is what travels,
    not the machine that wrote it."""
    if raw is None:
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        raise AuthoringError(
            expected=f"{key}: as a path relative to this file", found=str(candidate), where=str(path),
            hint="run manifests are portable (P-2, UT-D3-6) -- write a path relative to the manifest's own directory",
        )
    return (path.resolve().parent / candidate).resolve()


def load_run_spec(pipeline_path: Path) -> RunSpec:
    """Reads `recording:`/`project:`/`config:` from `pipeline_path`'s own
    top-level YAML keys, if present. Raises `AuthoringError` naming the
    file for an absolute path in either field (`UT-D3-6`) -- never
    silently accepted and never silently made relative."""
    raw = yaml.safe_load(pipeline_path.read_text(encoding="utf-8")) or {}
    return RunSpec(
        recording=_relative_or_raise(raw.get("recording"), key="recording", path=pipeline_path),
        project=raw.get("project", "base"),
        config=_relative_or_raise(raw.get("config"), key="config", path=pipeline_path),
    )


def write_run_manifest(
    path: Path, *, pipeline: Pipeline, mode_overrides: Mapping[str, str] | None = None,
    recording: Path | None = None, project: str = "base", config: Path | None = None,
) -> None:
    """Writes `pipeline`'s stages (mode overridden per `mode_overrides`,
    `impl:`/`inputs:` unchanged) plus `recording:`/`project:`/`config:` as
    one pipeline YAML at `path` -- `Pipeline.load(path)` reads it back
    unchanged (`UT-D3-5`), and `load_run_spec(path)` recovers the other
    three (`UT-D3-4`). Paths are written relative to `path`'s own
    directory (`UT-D3-6`) -- `os.path.relpath`, never `str(path)`.

    Raises `AuthoringError` naming the stage for a non-empty `overrides:`/
    `record:` -- this pass's `PipelinePanelState` never sets either, and
    silently dropping an existing pipeline's own `overrides:`/`record:` on
    round-trip would be real, silent data loss (`R-SIM-15`'s own "declared,
    never smuggled" applies here too). Real support is separate, later work.
    """
    mode_overrides = mode_overrides or {}
    stage_docs = []
    for stage in pipeline.stages:
        if stage.overrides or stage.record:
            raise AuthoringError(
                expected="a stage with no overrides:/record: (not yet supported by write_run_manifest)",
                found=f"stage {stage.name!r} has overrides={bool(stage.overrides)} record={bool(stage.record)}",
                where=str(path), hint="round-tripping overrides:/record: is separate, later work",
            )
        doc: dict[str, object] = {"name": stage.name, "mode": mode_overrides.get(stage.name, stage.mode)}
        if stage.impl:
            doc["impl"] = stage.impl
        if stage.inputs:
            doc["inputs"] = dict(stage.inputs)
        stage_docs.append(doc)

    base_dir = path.resolve().parent
    manifest: dict[str, object] = {"version": 1, "name": pipeline.name, "stages": stage_docs}
    if recording is not None:
        manifest["recording"] = os.path.relpath(recording.resolve(), base_dir)
    manifest["project"] = project
    if config is not None:
        manifest["config"] = os.path.relpath(config.resolve(), base_dir)

    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
