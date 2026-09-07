# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`RecordingReader`/`RecordingWriter` Protocols, `Capabilities`, `TopicInfo`,
`Provenance`, `RunManifest` (sim_api_reference.md §4, R-SIM-14). A recording
is a **model**, not a file format:

```
Recording
  meta:      manifest . config bundle . topic provenance
  topics:    name -> {schema, provenance tag}
  messages:  (topic, log_time_ns, capture_time_ns, bytes) in log_time order
```

Everything above `io/` is written against this model and never against a
format (`UT-A4-11`); a format is a codec of about four methods
(`io/mcap.py` is the first).

**Note on precedence.** `sim_resim_and_recording.md` §3.0 sketches an
earlier, rougher `RecordingReader`/`RecordingWriter` shape
(`read()`/`declare()`/`put_meta()`, a `meta(block: str) -> bytes | None`
accessor). This stage's own checklist item says "per api reference §4"
explicitly, and api reference's shape is what is implemented here -- the
recording doc's sketch is superseded, not contradicted; it is the "why", api
reference is the "what to type".
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, Protocol


class Provenance(StrEnum):
    """Per-topic origin tag (R-SIM-12, N-5): a manufactured recording and a
    real one share a format, never an evidence grade."""

    MEASURED = "measured"
    TRUTH = "truth"
    MOCKED = "mocked"
    SIMULATED = "simulated"
    OVERRIDDEN = "overridden"
    #: A recording with no meta at all (R-SIM-6) -- degrades visibly, never
    #: silently defaults to a "real" tag.
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Capabilities:
    embedded_schemas: bool
    random_access: bool
    meta_blocks: bool
    arbitrary_topics: bool
    #: False => cannot be a resim input (R-SIM-14).
    round_trips: bool
    #: A second, capture-time stamp distinct from reception (`OD-9`,
    #: `CR-SIM-4`). A codec without one declares it and degrades explicitly
    #: -- this is R-SIM-14's existing mechanism, so the field costs no new
    #: concept, only a new declaration.
    capture_time: bool
    write_only: bool = False

    def __repr__(self) -> str:
        return f"<Capabilities round_trips={self.round_trips} write_only={self.write_only}>"


@dataclass(frozen=True, slots=True)
class TopicInfo:
    """Schema + provenance for one topic (sim_api_reference.md §4)."""

    schema_name: str
    provenance: Provenance
    #: A serialized `FileDescriptorSet`, when the codec embeds one
    #: (`embedded_schemas`). Empty for a schema-less/degraded topic.
    schema_bytes: bytes = b""

    def __repr__(self) -> str:
        return f"<TopicInfo schema_name={self.schema_name!r} provenance={self.provenance.value}>"


@dataclass(frozen=True, slots=True)
class ComponentBuildInfo:
    """One `sut.components[]` entry (sim_resim_and_recording.md §2)."""

    name: str
    library_sha256: str = ""
    build_id: str = ""
    abi_version: int = 0
    manifest_sha256: str = ""
    config_bundle: str = ""
    config_bundle_sha256: str = ""
    config_bundle_embedded: bool = False
    enabled_functions: tuple[str, ...] = ()
    #: `impl: pkg:<ref>`'s own addressing (`sim_resim_and_recording.md`
    #: "Pinning a resim to the build that produced it", `OQ-9`/`NR-SIM-24`).
    #: Empty when the library was built locally -- today, always, since no
    #: `pkg:` resolver exists yet. A real value alone would prove nothing
    #: (a package can be rebuilt and re-uploaded under the same reference);
    #: `library_sha256` above is the actual verification, `--pin-builds`'s
    #: own job. Kept as a field now so a recording written today already
    #: has a place for it, rather than retrofitting the schema later.
    package_ref: str = ""
    #: `IMP-0226` (`R-SIM-24`, `S-C6`): this stage's own `modules/<name>/
    #: sim/tolerance.yaml`, hashed -- `diagnostics.tolerance.ToleranceSet.
    #: sha256`. `""` when the component declares no tolerance file (every
    #: field exact, the honest zero-configuration case, `load_tolerance`'s
    #: own default -- never an error).
    tolerance_sha256: str = ""
    #: `IMP-0215`'s own "timing model" half: this stage's own declared
    #: sample period in integer nanoseconds (`R-SIM-18`), `0` when the
    #: component declares none (runs every base-grid tick).
    period_ns: int = 0


@dataclass(frozen=True, slots=True)
class OverrideRecord:
    """One declared override, exactly as it appears in the run manifest --
    `R-SIM-15`'s own "declared, never smuggled," made legible rather than
    only hashed (`S-D6`, `UT-D6-2`). `stage`/`address`/`verb`/`value`
    mirror `contracts.pipeline.Stage.overrides`' own keys 1:1, never
    re-derived -- `core.manifest.build_manifest` is the one place a
    `Pipeline`'s overrides become this shape. `value` is `None` for a verb
    that carries none (`hold`/`select`/`drop`, `contracts/override.py`)."""

    stage: str
    address: str
    verb: str
    value: float | None = None


@dataclass(frozen=True, slots=True)
class BundleOverrideRecord:
    """One declared `run.overrides:` entry -- `NR-SIM-6`'s calibration
    sweep, exactly as it appears in the run manifest. A DIFFERENT
    mechanism from `OverrideRecord` above: that one is a per-STAGE PORT
    value (`R-SIM-15`, applied at `exec()` time); this one is a run-wide
    BUNDLE calibration key (`model.project.materialize_derived_bundle`,
    applied once at `adasInit` time, before any stage exists). No `stage`
    field -- one derived bundle is shared by every stage `init_components`
    initialises (`Pipeline.init_components`'s single `config_path`), and
    no `verb` -- a bundle override always sets the key to `value`, the
    sweep vocabulary arch §5.6 defines has no `hold`/`offset`/`scale`."""

    address: str
    value: object = None


@dataclass(frozen=True, slots=True)
class FaultRecord:
    """One declared `run.faults:` entry, exactly as it appears in the run
    manifest -- `R-SIM-15`'s "declared, never smuggled" extended from
    overrides to faults (`S-C3`'s own status note: "a fault is declared in
    `run.faults:`, lands in the run manifest"). Mirrors `contracts.fault.
    Fault`'s own fields 1:1; `verb` is the string value of `FaultVerb`.
    **No topic tag exists for this, by the same finding `UT-D6-2` made for
    overrides**: a fault mutates the STIMULUS right before a stage sees it
    (`Pipeline._apply_stimulus_faults`), but the recorded `source.*` topic
    is `Recorder.tick`'s own raw, pre-fault `stimulus` -- no recorded
    topic's bytes ever reflect a fault, so `origin: overridden` on a topic
    would state something false. This manifest field is the whole
    "declared, never smuggled" claim; there is no second, topic-level one."""

    verb: str
    address: str
    value: float | None = None
    from_s: float | None = None
    to_s: float | None = None
    after_tick: int | None = None


@dataclass(frozen=True, slots=True)
class DelayStepRecord:
    """`IMP-0402` (`SW-0402`, `CN-0154`): one wired edge's declared transport
    delay, exactly as `runspec/emit.py`'s own `stages[].inputs[].
    delay_steps` carries it in the Resolved Run Spec (`0` = same-tick, the
    universal default today -- `SW-0073`'s own execution-side consumption
    of this value is separate, later work; this record only states what
    was DECLARED, so a manifest reader can tell a same-tick result from a
    delayed one even before that execution support lands)."""

    edge: str  # "<consumer_stage>.<consumer_port>"
    delay_steps: int = 0


@dataclass(frozen=True, slots=True)
class PortResolutionRecord:
    """`IMP-0015` (`SW-0014`): one port's ingest resolution outcome, exactly
    as `ingest.resolve.Resolution` reported it -- `matched_address` is the
    candidate the resolver chose (`Resolution.chosen`), `None` when no
    candidate matched. Every resolved port appears once; nothing downstream
    re-derives which address a port actually used."""

    port: str
    matched_address: str | None = None


@dataclass(frozen=True, slots=True)
class RecordPolicyRecord:
    """One declared output port's resolved `record:` policy, exactly as it
    appears in the run manifest (`UT-C2-12`, `NR-SIM-42`). Written for
    **every** declared output port, not only the exceptions -- `full` is
    still a value, not an absence -- so a reader answers "was this
    recording complete?" from the file alone: `R-SIM-6` degrading
    *visibly* to "everything except these, by declaration" instead of
    silently becoming false. `decimate_n` is `0` unless `verb == "decimate"`
    (mirrors `contracts.pipeline.RecordPolicy.decimate_n`, `None` there)."""

    port: str
    verb: str
    decimate_n: int = 0


@dataclass(frozen=True, slots=True)
class RunManifest:
    """The run manifest (sim_resim_and_recording.md §2), written into the
    recording and every snapshot sidecar. `RunManifest()` (every field at its
    default) is what a recording with no meta at all decodes to --
    `manifest_version=0` marks it as such (`UT-A4-4`, `R-SIM-6`): it degrades
    and says so, it does not raise.
    """

    manifest_version: int = 0
    run_id: str = ""
    run_kind: str = ""  # "sim" | "resim"
    created_utc: str = ""
    host: str = ""
    source_kind: str = ""  # "mcap" | "carmaker" | "synthetic"
    scenario: str = ""
    scenario_sha256: str = ""
    recording: str = ""
    recording_sha256: str = ""
    project: str = ""
    pipeline: str = ""
    components: tuple[ComponentBuildInfo, ...] = field(default_factory=tuple)
    #: `IMP-0015` (`SW-0014`): every resolved port's chosen address, from
    #: `ingest.resolve.Resolution` -- empty when this run resolved no ports
    #: through the `WP-01` resolver (every caller predating it, or a run
    #: with no ingest map applicable).
    ports: tuple[PortResolutionRecord, ...] = field(default_factory=tuple)
    #: `R-SIM-15`'s "declared, never smuggled," made legible (`S-D6`,
    #: `UT-D6-2`) -- previously only hashed into `run_id` (`core.manifest.
    #: _overrides_repr`), never actually readable from a written manifest.
    overrides: tuple[OverrideRecord, ...] = field(default_factory=tuple)
    #: `UT-C2-12`: every declared output port's resolved `record:` policy,
    #: for every non-`off` stage -- see `RecordPolicyRecord`'s own
    #: docstring for why `full` is written too, not only the exceptions.
    record_policies: tuple[RecordPolicyRecord, ...] = field(default_factory=tuple)
    #: `S-C3`'s own "a fault is declared in run.faults:, lands in the run
    #: manifest" -- see `FaultRecord`'s own docstring for why there is no
    #: topic-level tag alongside it.
    faults: tuple[FaultRecord, ...] = field(default_factory=tuple)
    #: `NR-SIM-6`, `UT-C5-6/7`: this run's declared `run.overrides:` (the
    #: BUNDLE-calibration sweep set, `BundleOverrideRecord`'s own
    #: docstring on how this differs from `overrides` above). Empty for
    #: every run that declared none -- the common case, unchanged.
    bundle_overrides: tuple[BundleOverrideRecord, ...] = field(default_factory=tuple)
    #: The pre-override bundle's own `bundle.sha256`, recorded ALONGSIDE
    #: each stage's `ComponentBuildInfo.config_bundle_sha256` (which, for a
    #: swept run, reports the DERIVED bundle actually used) -- arch §5.6's
    #: "records both the base bundle's hash and the override set," so "a
    #: swept run is `bundle <hash> + 1 override`" is a statement a reader
    #: can make from this manifest alone. `""` whenever `bundle_overrides`
    #: is empty -- there is no second hash to distinguish from the first.
    base_config_bundle_sha256: str = ""
    seed: int = 0
    #: `OD-11` (`R-SIM-3a` §9.1): whether this run's pipeline declared
    #: `allow_mixed_projects: true` -- badges a deliberate cross-project
    #: experiment so a reader never mistakes it for an unnoticed mismatch.
    #: Independent of whether the components actually disagreed; recorded
    #: whenever the escape was requested, same as any other declared choice.
    allow_mixed_projects: bool = False
    #: `S-C6` (`R-SIM-24`): random per PROCESS (`core.manifest._PROCESS_NONCE`,
    #: generated once at import time), so two runs written by one process
    #: share it -- `sim determinism`'s same-process/fresh-process
    #: discriminator. Lives in `meta`, excluded from `new_run_id`'s hash
    #: (`core.ids.REQUIRED_KEYS` does not name it) so it cannot perturb what
    #: it measures.
    process_nonce: str = ""
    #: `IMP-0216` (`SW-0216`, `IT-16`): the Resolved Run Spec's own
    #: `spec_sha256` (`runspec/canon.py::compute_spec_sha256`) -- `""` when
    #: no spec was emitted for this run (every caller predating `WP-05`'s
    #: `emit.py`, or a `sim record` run with no pipeline at all). The spec
    #: bytes themselves travel as a sibling artifact (`write_run_spec`'s own
    #: `.spec.json`, `engine/bridge.py`'s convention); this field is the
    #: hash a reader checks the two agree on, never a second copy of the
    #: spec's own bytes.
    run_spec_sha256: str = ""
    #: `IMP-0224` (`SW-0224`, `CN-0114`): the whole pipeline's own
    #: `graph.coherence.classify()` outcome, aggregated to worst-of
    #: (`"broken"` if any finding is `BROKEN`, else `"orphan"` if any is
    #: `ORPHAN`, else `"normal"`) -- `"unknown"` when no pipeline was
    #: classified (a `sim record` run with no pipeline). `R-SIM-25`: an
    #: explicit non-answer, never a guessed `"normal"`.
    coherence_verdict: str = "unknown"
    #: One `graph.coherence.render_finding()` string per finding
    #: `classify()` returned -- empty when `coherence_verdict` is
    #: `"normal"` or `"unknown"`, never a placeholder for an unclassified
    #: run (`coherence_verdict` alone answers that).
    coherence_findings: tuple[str, ...] = ()
    #: `IMP-0224`: the first tick past which a `mode: simulate` stage's
    #: output diverged from the recording it was resimmed against, as
    #: `simcore::runner::divergence.cpp::DivergenceLatch` reports it --
    #: `"unknown"` when no divergence observer supplied a value (today,
    #: always: `simcore`'s divergence latch has no Python binding yet, so
    #: this field is a real, honest placeholder rather than a guess that
    #: the run never diverged).
    divergence: str = "unknown"
    #: `IMP-0222` (`SW-0222`): `"completed"` | `"failed"` | `"crashed"` |
    #: `"timeout"` -- always one of these four, never blank, so a manifest
    #: written from a `finally` states which of the four outcomes it is
    #: reporting on.
    outcome: str = "completed"
    #: `IMP-0222`: the last cycle this run actually completed, `-1` when
    #: unknown (a `completed` run's own `-1` means "not tracked per cycle
    #: by this caller," never "zero cycles ran" -- callers that DO track
    #: per-cycle progress pass the real count for every outcome, `completed`
    #: included).
    last_completed_cycle: int = -1
    #: `IMP-0235` (`SW-0235`): whether a caller-supplied `CancelToken`
    #: (`orchestrate/progress.py`) ended this run -- `outcome` stays
    #: `"failed"` for a cancelled run (never a fifth `outcome` value,
    #: `R-SIM-19`), distinguished here instead, same pattern
    #: `orchestrate/batch.py::RecordingOutcome.cancelled`/`limit_breach`
    #: already established at the batch-report layer; this is that same
    #: fact recorded in the manifest itself.
    cancelled: bool = False
    #: `IMP-0252`/`IMP-0253` (`SW-0252`/`SW-0253`): `""` (no read error) or
    #: one of `orchestrate.readerror.ReadError`'s own values -- the policy
    #: this run was launched with, when its own pre-flight recording read
    #: failed. `read_retry_attempts` is `0` when no read error occurred.
    read_error: str = ""
    read_retry_attempts: int = 0
    #: `IMP-0251` (`SW-0251`): the `orchestrate.reset.ResetPolicy` (mode x
    #: timing) this run was launched with -- `""` when no policy was
    #: recorded (a caller predating this field). Never the per-entry
    #: DECISION `should_reset_before` returned: under `orchestrate/batch.py`'s
    #: own one-fresh-subprocess-per-recording isolation invariant, that
    #: decision is trivially always-true and would misrepresent what
    #: actually happened -- the policy is the real, checkable fact.
    reset_mode: str = ""
    reset_when: str = ""
    #: `IMP-0252` (`SW-0252`): count of damaged packages (mcap chunks) this
    #: run's own pre-flight found and skipped under `ReadError.SKIP_PACKAGE`
    #: -- `0` for every run that found none, including every run launched
    #: under a different `read_error` policy (that policy's pre-flight
    #: never scans chunks at all, `orchestrate/worker.py::_open_and_probe`).
    #: A nonzero value is the flag `SW-0252`'s Accept clause asks for --
    #: "a run that skipped packages cannot be mistaken for a clean one" --
    #: same distinguish-by-field pattern as `cancelled`/`read_error`, never
    #: a fifth `outcome` value.
    skipped_packages: int = 0
    #: `IMP-0128` (`SW-0128`): this run's own caught `SimError.kind`
    #: (`""` for `ok`, or a failure the worker did not raise a `SimError`
    #: for) -- `orchestrate.severity.severity_for_kind` maps it to a
    #: `Severity` for `--exit-on`.
    error_kind: str = ""
    #: `IMP-0402` (`SW-0402`, `CN-0154`): every wired edge's declared
    #: transport delay, in force for this run -- see `DelayStepRecord`'s own
    #: docstring for what "in force" does and does not claim yet.
    delay_steps: tuple[DelayStepRecord, ...] = field(default_factory=tuple)
    #: `IMP-0215`'s own "timing model" half: `graph.grid.derive_step()` over
    #: every non-`off` stage's declared period (`R-SIM-18`) -- `0` when no
    #: stage declares a period (no pipeline, or every period `0`).
    grid_step_ns: int = 0

    @property
    def known(self) -> bool:
        return self.manifest_version > 0

    def __repr__(self) -> str:
        return f"<RunManifest run_id={self.run_id!r} known={self.known}>"


#: The first `manifest_version` written by a capture-time-aware writer
#: (`OD-9`, `CR-SIM-4`, `S-A4Δ`). A recording whose manifest reports less than
#: this -- including `manifest_version=0` (no manifest at all) -- predates
#: the two-clock model: every message in it reports `capture_time_ns=None`
#: regardless of its bytes, because the writer that produced it set
#: `publish_time = log_time_ns` unconditionally, an equality that carries no
#: information. Existing recordings/tests pinned at `manifest_version=1` are
#: therefore left exactly as they are -- no existing manifest needs editing
#: for this delta to be correct.
CAPTURE_TIME_MANIFEST_VERSION = 2


def manifest_to_dict(manifest: RunManifest) -> dict:
    """`RunManifest` <-> a plain, YAML/JSON-safe `dict` -- **shared by every
    codec that carries the manifest as text** (`io/mcap.py`'s metadata
    block, `io/jsonl.py`'s header line, S-C9's `ST-C9-3`: "format and depth
    are genuinely orthogonal"). Moved here from being `io/mcap.py`-private
    at `S-C9` specifically because a second codec needing the same ~15
    fields is the evidence for that claim -- two codecs hand-rolling the
    same (de)serialization would silently drift apart the next time a
    field is added to `RunManifest` (`UT-C5-6/7`'s own `bundle_overrides`/
    `base_config_bundle_sha256` already needed updating in exactly one
    place because of this)."""
    return {
        "manifest_version": manifest.manifest_version,
        "run_id": manifest.run_id,
        "run_kind": manifest.run_kind,
        "created_utc": manifest.created_utc,
        "host": manifest.host,
        "source_kind": manifest.source_kind,
        "scenario": manifest.scenario,
        "scenario_sha256": manifest.scenario_sha256,
        "recording": manifest.recording,
        "recording_sha256": manifest.recording_sha256,
        "project": manifest.project,
        "pipeline": manifest.pipeline,
        "seed": manifest.seed,
        "allow_mixed_projects": manifest.allow_mixed_projects,
        "process_nonce": manifest.process_nonce,
        "components": [
            {
                "name": c.name,
                "library_sha256": c.library_sha256,
                "build_id": c.build_id,
                "abi_version": c.abi_version,
                "manifest_sha256": c.manifest_sha256,
                "config_bundle": c.config_bundle,
                "config_bundle_sha256": c.config_bundle_sha256,
                "config_bundle_embedded": c.config_bundle_embedded,
                "enabled_functions": list(c.enabled_functions),
                "package_ref": c.package_ref,
                "tolerance_sha256": c.tolerance_sha256,
                "period_ns": c.period_ns,
            }
            for c in manifest.components
        ],
        "ports": [
            {"port": p.port, "matched_address": p.matched_address} for p in manifest.ports
        ],
        "overrides": [
            {"stage": o.stage, "address": o.address, "verb": o.verb, "value": o.value}
            for o in manifest.overrides
        ],
        "record_policies": [
            {"port": r.port, "verb": r.verb, "decimate_n": r.decimate_n}
            for r in manifest.record_policies
        ],
        "faults": [
            {
                "verb": f.verb, "address": f.address, "value": f.value,
                "from_s": f.from_s, "to_s": f.to_s, "after_tick": f.after_tick,
            }
            for f in manifest.faults
        ],
        "bundle_overrides": [
            {"address": o.address, "value": o.value} for o in manifest.bundle_overrides
        ],
        "base_config_bundle_sha256": manifest.base_config_bundle_sha256,
        "run_spec_sha256": manifest.run_spec_sha256,
        "coherence_verdict": manifest.coherence_verdict,
        "coherence_findings": list(manifest.coherence_findings),
        "divergence": manifest.divergence,
        "outcome": manifest.outcome,
        "last_completed_cycle": manifest.last_completed_cycle,
        "cancelled": manifest.cancelled,
        "read_error": manifest.read_error,
        "read_retry_attempts": manifest.read_retry_attempts,
        "reset_mode": manifest.reset_mode,
        "reset_when": manifest.reset_when,
        "error_kind": manifest.error_kind,
        "delay_steps": [
            {"edge": d.edge, "delay_steps": d.delay_steps} for d in manifest.delay_steps
        ],
        "grid_step_ns": manifest.grid_step_ns,
        "skipped_packages": manifest.skipped_packages,
    }


def manifest_from_dict(data: dict) -> RunManifest:
    """The inverse of `manifest_to_dict` -- every field defaulted the same
    "degrades and says so" way `RunManifest()`'s own defaults do, so a
    dict missing a key (an older recording, a hand-authored fixture)
    decodes to the same value a never-set field would."""
    components = tuple(
        ComponentBuildInfo(
            name=c["name"],
            library_sha256=c.get("library_sha256", ""),
            build_id=c.get("build_id", ""),
            abi_version=c.get("abi_version", 0),
            manifest_sha256=c.get("manifest_sha256", ""),
            config_bundle=c.get("config_bundle", ""),
            config_bundle_sha256=c.get("config_bundle_sha256", ""),
            config_bundle_embedded=c.get("config_bundle_embedded", False),
            enabled_functions=tuple(c.get("enabled_functions", ())),
            package_ref=c.get("package_ref", ""),
            tolerance_sha256=c.get("tolerance_sha256", ""),
            period_ns=c.get("period_ns", 0),
        )
        for c in data.get("components", ())
    )
    ports = tuple(
        PortResolutionRecord(port=p["port"], matched_address=p.get("matched_address"))
        for p in data.get("ports", ())
    )
    overrides = tuple(
        OverrideRecord(stage=o["stage"], address=o["address"], verb=o["verb"], value=o.get("value"))
        for o in data.get("overrides", ())
    )
    record_policies = tuple(
        RecordPolicyRecord(port=r["port"], verb=r["verb"], decimate_n=r.get("decimate_n", 0))
        for r in data.get("record_policies", ())
    )
    faults = tuple(
        FaultRecord(
            verb=f["verb"], address=f["address"], value=f.get("value"),
            from_s=f.get("from_s"), to_s=f.get("to_s"), after_tick=f.get("after_tick"),
        )
        for f in data.get("faults", ())
    )
    bundle_overrides = tuple(
        BundleOverrideRecord(address=o["address"], value=o.get("value"))
        for o in data.get("bundle_overrides", ())
    )
    delay_steps = tuple(
        DelayStepRecord(edge=d["edge"], delay_steps=d.get("delay_steps", 0))
        for d in data.get("delay_steps", ())
    )
    return RunManifest(
        manifest_version=data.get("manifest_version", 0),
        run_id=data.get("run_id", ""),
        run_kind=data.get("run_kind", ""),
        created_utc=data.get("created_utc", ""),
        host=data.get("host", ""),
        source_kind=data.get("source_kind", ""),
        scenario=data.get("scenario", ""),
        scenario_sha256=data.get("scenario_sha256", ""),
        recording=data.get("recording", ""),
        recording_sha256=data.get("recording_sha256", ""),
        project=data.get("project", ""),
        pipeline=data.get("pipeline", ""),
        seed=data.get("seed", 0),
        allow_mixed_projects=data.get("allow_mixed_projects", False),
        process_nonce=data.get("process_nonce", ""),
        components=components,
        ports=ports,
        overrides=overrides,
        record_policies=record_policies,
        faults=faults,
        bundle_overrides=bundle_overrides,
        base_config_bundle_sha256=data.get("base_config_bundle_sha256", ""),
        run_spec_sha256=data.get("run_spec_sha256", ""),
        coherence_verdict=data.get("coherence_verdict", "unknown"),
        coherence_findings=tuple(data.get("coherence_findings", ())),
        divergence=data.get("divergence", "unknown"),
        outcome=data.get("outcome", "completed"),
        last_completed_cycle=data.get("last_completed_cycle", -1),
        cancelled=data.get("cancelled", False),
        read_error=data.get("read_error", ""),
        read_retry_attempts=data.get("read_retry_attempts", 0),
        reset_mode=data.get("reset_mode", ""),
        reset_when=data.get("reset_when", ""),
        error_kind=data.get("error_kind", ""),
        delay_steps=delay_steps,
        grid_step_ns=data.get("grid_step_ns", 0),
        skipped_packages=data.get("skipped_packages", 0),
    )


class RecordingReader(Protocol):
    capabilities: ClassVar[Capabilities]

    def meta(self) -> RunManifest: ...

    def topics(self) -> Mapping[str, TopicInfo]: ...

    def messages(self, topics: Sequence[str] | None = None) -> Iterator[tuple[str, int, int | None, bytes]]: ...

    def close(self) -> None: ...


class RecordingWriter(Protocol):
    capabilities: ClassVar[Capabilities]

    def open(self, path: Path, meta: RunManifest, topics: Mapping[str, TopicInfo]) -> None: ...

    def write(self, topic: str, log_time_ns: int, payload: bytes, *, capture_time_ns: int | None = None) -> None: ...

    def close(self) -> None: ...


def group_by_log_time(
    messages: Iterable[tuple[str, int, int | None, bytes]], expected_topics: Collection[str]
) -> Iterator[tuple[int, dict[str, bytes], frozenset[str]]]:
    """Groups `(topic, log_time_ns, capture_time_ns, bytes)` messages by
    `log_time_ns` -- format-agnostic, over the model, not a file. Grouping is
    a *scheduling* question, so it keys on `log_time_ns` exactly as before
    (`OD-9`) and the yielded shape is unchanged: `(log_time_ns, {topic:
    payload}, missing_topics)`, `capture_time_ns` dropped after grouping. A
    tick missing one of its expected topics is **reported** via
    `missing_topics`, never silently dropped (`UT-A4-9`). A full grouped
    `Tick` object is `core/tick.py`'s job (`S-B2`); this is the
    format-independent piece of that idea usable now.
    """
    groups: dict[int, dict[str, bytes]] = {}
    for topic, log_time_ns, _capture_time_ns, payload in messages:
        groups.setdefault(log_time_ns, {})[topic] = payload
    expected = frozenset(expected_topics)
    for log_time_ns in sorted(groups):
        group = groups[log_time_ns]
        yield log_time_ns, group, expected - frozenset(group)
