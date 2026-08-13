# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Run manifests -- two different things that share a word, kept distinct.

`build_manifest` assembles a `RunManifest` (`io.base.RunManifest`) for a run
about to happen: post-run **provenance** (`R-SIM-6`, recording spec §2), embedded in the recording after the
fact, with no per-stage mode/impl fields. Thin on purpose -- the run id is
`core.ids.new_run_id`'s job and already enforces its `REQUIRED_KEYS`; this
only gathers those keys from a `Pipeline` and its inputs.

`RunSpec`/`load_run_spec`/`write_run_manifest` are a pre-run
**configuration**: which recording, project and config to run a pipeline
against, plus this session's `mode:` overrides -- what `sim resim` would
otherwise need five flags for.

Deliberately **not** a second schema: a run manifest *is* a pipeline YAML
with three optional extra top-level keys (`recording:`/`project:`/`config:`)
that `Pipeline.load()` ignores. `stages:` keeps its identical shape, so one
parser reads both and there is no second format to keep in sync.
"""

from __future__ import annotations

import hashlib
import os
import socket
import tempfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from warnings import warn

import yaml

from adas_sim.graph.build import Pipeline, record_policy_for
from adas_sim.diagnostics.errors import AuthoringError, ContractError, ProvenanceWarning
from adas_sim.runspec.ids import new_run_id
from adas_sim.io.base import (
    CAPTURE_TIME_MANIFEST_VERSION,
    BundleOverrideRecord,
    ComponentBuildInfo,
    FaultRecord,
    OverrideRecord,
    RecordPolicyRecord,
    RunManifest,
)
from adas_sim.plugins.registry import reader_for
from adas_sim.config.project import ProjectModel, materialize_derived_bundle

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


def _faults_repr(pipeline: Pipeline) -> str:
    """A stable text form of every declared `run.faults:` entry -- part of
    `new_run_id`'s hashed input set, same reasoning `_overrides_repr` gives:
    two runs differing only in which faults were injected must never
    collide on one run id. Not added to `core.ids.REQUIRED_KEYS` (unlike
    `overrides_repr`) -- `new_run_id` hashes every key it is given, required
    or not, and `build_manifest` is its only caller, so there is no second
    call site that could forget to pass this one."""
    parts = [
        f"{fault.verb.value}:{fault.address}:{fault.value}:{fault.from_s}:{fault.to_s}:{fault.after_tick}"
        for fault in pipeline.faults
    ]
    return "|".join(parts)


def _fault_records(pipeline: Pipeline) -> tuple[FaultRecord, ...]:
    """The same declared faults `_faults_repr` hashes, as the structured,
    actually-readable form `RunManifest.faults` carries (`S-C3`)."""
    return tuple(
        FaultRecord(
            verb=fault.verb.value, address=fault.address, value=fault.value,
            from_s=fault.from_s, to_s=fault.to_s, after_tick=fault.after_tick,
        )
        for fault in pipeline.faults
    )


def _bundle_overrides_repr(bundle_overrides: Mapping[str, object]) -> str:
    """A stable text form of a declared `run.overrides:` set -- part of
    `new_run_id`'s hashed input set, same reasoning `_faults_repr` gives:
    two runs differing only in which calibration keys were swept must
    never collide on one run id (`NR-SIM-6`)."""
    return "|".join(f"{key}={value}" for key, value in sorted(bundle_overrides.items()))


def _bundle_override_records(bundle_overrides: Mapping[str, object]) -> tuple[BundleOverrideRecord, ...]:
    """The same declared overrides `_bundle_overrides_repr` hashes, as the
    structured, actually-readable form `RunManifest.bundle_overrides`
    carries (`UT-C5-6/7`)."""
    return tuple(BundleOverrideRecord(address=key, value=value) for key, value in sorted(bundle_overrides.items()))


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
    bundle_overrides: Mapping[str, object] | None = None,
    base_bundle_sha: str = "",
    seed: int = 0,
    host: str = "",
    clock: datetime | None = None,
) -> RunManifest:
    """`run_kind` is `"sim"` or `"resim"`; `source_kind` is the `Source.name`.

        Several fields are optional and **degrade honestly rather than with a
        placeholder** -- an empty value here is a real answer, not a forgotten one:

        - `recording_path` is the input recording for a resim, absent for a fresh
          `sim record` (nothing exists yet to hash), so `recording_sha256` is `""`.
        - `pipeline`/`pipeline_path` are absent for `sim record`, which has a
          `Source` and no pipeline at all.
        - `component_build_shas` is keyed by stage name, supplied by a caller that
          has a real library.
        - `component_bundle_paths`/`component_bundle_shas` are the resolved bundle
          directory and its `bundle.sha256` per stage. `config_bundle` is a
          **display string** -- the path a reader would check -- never bundle
          bytes; the bytes go once per recording on the `/meta/config_bundle`
          topic. `config_bundle_embedded` states whether *this* recording actually
          carries them.
        - `bundle_overrides`/`base_bundle_sha` describe a calibration sweep
          (`NR-SIM-6`): the declared override set and the hash of the bundle it was
          derived from. Distinct from `bundle_sha`, which reports whatever bundle
          was actually resolved -- the derived one, for a swept run.

    """
    component_build_shas = component_build_shas or {}
    component_bundle_paths = component_bundle_paths or {}
    component_bundle_shas = component_bundle_shas or {}
    bundle_overrides = bundle_overrides or {}
    pipeline_sha = _sha256_file(pipeline_path) if pipeline_path is not None and pipeline_path.exists() else ""
    recording_sha = _sha256_file(recording_path) if recording_path is not None and recording_path.exists() else ""
    scenario_sha = _sha256_file(scenario_path) if scenario_path is not None and scenario_path.exists() else ""
    overrides_repr = _overrides_repr(pipeline) if pipeline is not None else ""
    faults_repr = _faults_repr(pipeline) if pipeline is not None else ""
    bundle_overrides_repr = _bundle_overrides_repr(bundle_overrides)

    run_id = new_run_id(
        inputs={
            "pipeline_sha": pipeline_sha,
            "recording_sha": recording_sha,
            "project": project,
            "component_build_shas": "|".join(f"{k}={v}" for k, v in sorted(component_build_shas.items())),
            "bundle_sha": bundle_sha,
            "overrides_repr": overrides_repr,
            "faults_repr": faults_repr,
            "bundle_overrides_repr": bundle_overrides_repr,
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
        faults=_fault_records(pipeline) if pipeline is not None else (),
        bundle_overrides=_bundle_override_records(bundle_overrides),
        base_config_bundle_sha256=base_bundle_sha if bundle_overrides else "",
        seed=seed,
        allow_mixed_projects=pipeline.allow_mixed_projects if pipeline is not None else False,
        process_nonce=_PROCESS_NONCE,
    )


def verify_pinned_builds(pipeline: Pipeline, recording_path: Path) -> None:
    """`sim resim --pin-builds` (`NR-SIM-24`): refuse to start rather than
        silently resim against a different build than the one that produced the
        recording.

        Reads the recording's own embedded run manifest for each `mode: simulate`
        stage's recorded `library_sha256` and compares it against the currently
        resolved library for that stage. A `components=`-supplied stage has no file
        on disk and is skipped.

        Verification, not addressing: a package reference would prove nothing, the
        byte hash is the claim.

        **The limit is a refusal, not a silent pass.** A stage the recording
        carries no `library_sha256` for is reported as **unpinnable**, never
        treated as a match -- the point of the flag is a hard guarantee, and
        reading "unknown" as "fine" would defeat it (`NR-SIM-4`).

    """
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
    #: `NR-SIM-6`, `UT-C5-6/7`: this run manifest's own top-level
    #: `overrides:` key -- the BUNDLE calibration sweep (arch §5.6),
    #: distinct from a pipeline stage's `overrides:` (`Stage.overrides`,
    #: a port value). Empty for every plain pipeline file, unchanged.
    overrides: Mapping[str, object] = field(default_factory=dict)


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
        overrides=dict(raw.get("overrides") or {}),
    )


@dataclass(frozen=True, slots=True)
class ResolvedRunConfig:
    """`resolve_swept_config`'s own result. `effective_config` is what a
    caller must forward to `Pipeline.init_components` -- unchanged from
    the `config` it was given when no sweep was declared.
    `scratch_dir`, when not `None`, is a directory the CALLER now owns and
    must remove after the run (same lifetime discipline `render/
    viewer.py`'s own `_resim_scratch_dir` uses) -- this function only ever
    creates it, never cleans it up."""

    effective_config: Path | None
    base_bundle_sha: str = ""
    scratch_dir: Path | None = None


def resolve_swept_config(config: Path | None, overrides: Mapping[str, object], *, project: str) -> ResolvedRunConfig:
    """`NR-SIM-6`'s wiring: a caller that resolved `config`/`overrides`
    from a `RunSpec` (`cli/resim.py`) calls this ONCE, before
    `init_components`, turning a declared `run.overrides:` sweep into the
    real derived-bundle mechanism (`model.project.
    materialize_derived_bundle`).

    `overrides` empty (the overwhelming common case): passthrough --
    `effective_config is config`, no scratch directory created, a plain
    run pays nothing for a feature it never asked for.

    `overrides` non-empty: `config` MUST already name a real base bundle
    directory -- there is no tier-resolution here (`ProjectModel.
    resolve`'s embedded/library/checkout tiers answer "what would the SUT
    read with no override at all", a different question); sweeping
    "whatever `adasInit(NULL)` would have found" would derive from a
    directory this process never actually inspected. A missing `config` is
    therefore an `AuthoringError`, never a silent fall-through to some
    other tier."""
    if not overrides:
        return ResolvedRunConfig(effective_config=config)
    if config is None:
        raise AuthoringError(
            expected="a base config bundle directory to sweep (--config, or the run manifest's own config: key)",
            found="no config given",
            where="run.overrides:",
            hint="run.overrides: derives a swept bundle FROM a real one -- point --config at the bundle "
                 "adasInit would otherwise read, then declare the sweep on top of it",
        )
    base_model = ProjectModel.resolve(explicit=config, project=project)
    scratch_dir = Path(tempfile.mkdtemp(prefix="adas_sim_derived_bundle_"))
    materialize_derived_bundle(config, overrides, scratch_dir)
    return ResolvedRunConfig(
        effective_config=scratch_dir, base_bundle_sha=base_model.bundle_sha256, scratch_dir=scratch_dir,
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
