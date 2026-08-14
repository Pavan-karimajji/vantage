# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`Pipeline` -- ordered stages, wired by name (api reference §3.3, contract
§4.2).

**Validated at load, never at first tick** (§5.14): every input reference
resolves, `mode: measured` is checked against the recording's topic index, and
a port-type mismatch or forward reference is a load error naming both ends.

`Pipeline.exec` runs one tick single-rate -- every stage every call.
`Pipeline.step` is the multi-rate entry point (`R-SIM-18`): it advances the
pipeline's own clock and runs a stage only on its due ticks, holding the rest
with `updated=False` and `age_s` from integer nanoseconds.

**Overrides** (`contracts/override.py`, `contracts/binding.py`) are declared,
load-validated, and applied to a stage's input bytes immediately before
`exec()` sees them (`OD-8`). `Stage.overrides` is the "declared, never
smuggled" record (`R-SIM-15`); tagging a recorded topic `origin: overridden` is
the recorder reading this same field, not a second mechanism.

**Faults** (`contracts/fault.py`) are scenario-scoped, declared at
construction, and applied to the **stimulus** before any stage's own override
runs. Stage-to-stage and per-stage faults are out of scope (scenarios §9.2's
rejected bus-level models): only the world model's output can be faulted.

`InputMeta` carries the real `valid`/`age_s` that a fault or `step()`'s
multi-rate holding produces through to `SilComponent.exec` -- the fields the
ctypes input builder once hardcoded.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from functools import reduce
from math import gcd
from pathlib import Path
from typing import Literal
from warnings import warn

import yaml

from adas_sim.runspec.address import Address, apply_override, parse_address
from adas_sim.resolve.component import (
    ComponentManifest, CtypesSilComponent, InputMeta, PortSpec, SilComponent, resolve_message_classes,
)
from adas_sim.config.bundle import check_cross_component_agreement
from adas_sim.config.fault import Fault, FaultVerb, apply_fault
from adas_sim.resolve.library import resolve_library
from adas_sim.config.override import Override, OverrideVerb, parse_override_verb
from adas_sim.diagnostics.errors import AuthoringError, ContractError, ProvenanceWarning
from adas_sim.session.tick import PortValue
from adas_sim.io.base import RecordingReader
from adas_sim.sources.base import Source

#: The only shape that has ever existed -- `_resolve_version`'s upgrade is a
#: no-op today; a real v2 would add a transform step there (`CR-SIM-23`).
CURRENT_PIPELINE_VERSION = 1

Mode = Literal["simulate", "measured", "off"]


class RecordVerb(StrEnum):
    """The closed per-port record vocabulary (`NR-SIM-42`): `full` is the
    stated default, `excluded` drops the port entirely, `decimate` keeps
    every Nth tick. No fourth verb -- same "closed list, stated reason"
    discipline as `OverrideVerb` (`R-SIM-15`)."""

    FULL = "full"
    EXCLUDED = "excluded"
    DECIMATE = "decimate"


@dataclass(frozen=True, slots=True)
class RecordPolicy:
    """One port's resolved `record:` policy. `decimate_n` is required for,
    and only meaningful with, `verb is DECIMATE`."""

    verb: RecordVerb
    decimate_n: int | None = None


def record_policy_for(stage: Stage, port_name: str) -> RecordPolicy:
    """`stage`'s resolved policy for one of its own declared output ports
    (`NR-SIM-42`): an exact port entry wins, else the `"*"` wildcard entry,
    else the closed default `full` -- `record:` entirely absent means every
    port is `full`, stated rather than merely assumed."""
    if port_name in stage.record:
        return stage.record[port_name]
    if "*" in stage.record:
        return stage.record["*"]
    return RecordPolicy(RecordVerb.FULL)


@dataclass(frozen=True, slots=True)
class Stage:
    """One pipeline entry (`sim_api_reference.md` SS3.3). `inputs` maps this
    stage's own port name to a producer reference: `"source.<name>"` or
    `"<earlier-stage>.<port>"`. `overrides` is keyed by a port name or a
    field path (`"egoDyn.vx"`), from the closed four-verb list
    (`contracts/override.py`, `R-SIM-15`) -- declared and validated at load,
    not yet applied during `exec()` (a later slice wires that in).
    `record` is keyed by this stage's own OUTPUT port name (or `"*"`), the
    per-port capture policy the recorder honours (`NR-SIM-42`, `S-C2`) --
    unrelated to `overrides`, which governs this stage's INPUT side."""

    name: str
    mode: Mode
    impl: str | None
    inputs: Mapping[str, str]
    overrides: Mapping[str, Override] = field(default_factory=dict)
    record: Mapping[str, RecordPolicy] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SeveredChain:
    """A `measured` stage sitting between two `simulate` stages on one data
    path (`R-SIM-10`): `upstream` computes `upstream_port` into nothing,
    `downstream` reads `downstream_port` from the recording instead of from
    `upstream`'s live computation."""

    upstream: str
    upstream_port: str
    measured: str
    downstream: str
    downstream_port: str


@dataclass(frozen=True, slots=True)
class ScheduleDisagreement:
    """`R-SIM-18`'s own closing line: "the DLL's own `updated` flag is
    authoritative over the predicted schedule ... a disagreement is
    reported, never hidden." One port, one due tick, one mismatch --
    `Pipeline.step` predicted `predicted_due` from that port's own
    declared `PortSpec.period_us` (never the component-level GCD, which
    only gates whether `exec()` is called at all); `actual_updated` is
    whether the real ABI actually reported that port as refreshed this
    call (`CtypesSilComponent._collect_outputs`'s own `port.updated`,
    surviving as simple presence in `exec()`'s returned mapping). A
    component whose rate gating has drifted from its declared period
    otherwise surfaces months later as an unexplained stale value --
    this is the mechanism that instead surfaces it the tick it happens."""

    tick_index: int
    stage: str
    port: str
    predicted_due: bool
    actual_updated: bool


def _split_ref(ref: str) -> tuple[str, str]:
    """`"perception-core.gen_object_list"` -> `("perception-core",
    "gen_object_list")`. Splits on the FIRST dot only: a port name may itself
    contain a dot (`<function>.<port>`, e.g. `"widget.outputs"`), a stage
    name never does."""
    stage_name, _, port_name = ref.partition(".")
    return stage_name, port_name


def _resolve_version(raw: Mapping[str, object]) -> int:
    """`version:` is a required top-level key going forward; a file with
    none predates it and is read as v1 (`CR-SIM-23`). A version newer than
    this reader understands is a load error naming both."""
    version = raw.get("version", 1)
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise AuthoringError(
            expected="an integer pipeline version >= 1", found=repr(version),
            where="pipeline file 'version:' key", hint="use version: 1",
        )
    if version > CURRENT_PIPELINE_VERSION:
        raise AuthoringError(
            expected=f"pipeline version <= {CURRENT_PIPELINE_VERSION} (this reader)",
            found=f"version {version}", where="pipeline file 'version:' key",
            hint="this pipeline was written by a newer adas-sim; upgrade the framework",
        )
    return version


#: An override entry's only allowed keys (`S-C1cΔ`) -- anything else is
#: someone reaching for a time-varying or conditional override, which does
#: not exist (`R-SIM-15`).
_ALLOWED_OVERRIDE_KEYS = frozenset({"verb", "value"})


def _parse_overrides(raw: Mapping[str, Mapping[str, object]], *, stage_name: str) -> dict[str, Override]:
    """`overrides: {<address>: {verb: ..., value: ...}}` -- the verb is
    checked against the closed six (`R-SIM-15`, `UT-C1c-17`), the address
    against the closed grammar (`S-C1cΔ`, `UT-C1c-24`), both load errors
    naming the offending key. **Refuses a time-varying or conditional
    override, naming the alternative** (`S-C1cΔ`): an entry key beyond
    `verb:`/`value:`, or a `value:` that is not a plain number, is exactly
    the shape someone reaches for first -- refused pointing at *edit the
    scenario* or *write a `stub:` stage*, because a refusal that does not
    say where to go instead is how a closed list gets reopened.
    """
    result: dict[str, Override] = {}
    for key, entry in raw.items():
        where = f"stage '{stage_name}' overrides '{key}'"
        extra = set(entry) - _ALLOWED_OVERRIDE_KEYS
        if extra:
            raise AuthoringError(
                expected=f"only {sorted(_ALLOWED_OVERRIDE_KEYS)} in an override entry",
                found=f"also has: {sorted(extra)}", where=where,
                hint="no time-varying or conditional override exists -- "
                     "edit the scenario itself, or write a stub: stage",
            )
        value = entry.get("value")
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise AuthoringError(
                expected="a plain number for value:", found=repr(value), where=where,
                hint="no time-varying or conditional value exists -- "
                     "edit the scenario itself, or write a stub: stage",
            )
        verb = parse_override_verb(entry["verb"], where=where)
        parse_address(key, where=where)  # grammar validated now (UT-C1c-24); re-resolved when actually applied
        result[key] = Override(verb=verb, value=float(value) if value is not None else None)
    return result


def _parse_record_policy(raw: object, *, where: str) -> RecordPolicy:
    """One `record:` entry's value -- a bare string (`full`/`excluded`) or
    `{decimate: <n>}` (`NR-SIM-42`'s own example shape). Anything else,
    including a bare `"decimate"` string with no count, is a load error
    naming the closed vocabulary."""
    if isinstance(raw, str) and raw != RecordVerb.DECIMATE.value:
        try:
            return RecordPolicy(RecordVerb(raw))
        except ValueError as exc:
            raise AuthoringError(
                expected="one of: full, excluded, or {decimate: <n>}", found=repr(raw), where=where,
                hint="the record: policy vocabulary is closed (NR-SIM-42)",
            ) from exc
    if isinstance(raw, Mapping) and set(raw) == {"decimate"}:
        n = raw["decimate"]
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise AuthoringError(
                expected="a positive integer for decimate:", found=repr(n), where=where,
                hint="e.g. {decimate: 10} keeps every 10th tick",
            )
        return RecordPolicy(RecordVerb.DECIMATE, decimate_n=n)
    raise AuthoringError(
        expected="one of: full, excluded, or {decimate: <n>}", found=repr(raw), where=where,
        hint="the record: policy vocabulary is closed (NR-SIM-42)",
    )


def _parse_record(raw: Mapping[str, object], *, stage_name: str) -> dict[str, RecordPolicy]:
    """`record: {<port or "*">: <policy>}` (`NR-SIM-42`) -- keyed by this
    stage's own output ports, resolved per-port by `record_policy_for`."""
    return {
        key: _parse_record_policy(value, where=f"stage '{stage_name}' record '{key}'")
        for key, value in raw.items()
    }


def validate_recordable(stages: Sequence[Stage], components: Mapping[str, SilComponent]) -> None:
    """Recording-time-only check (`NR-SIM-42`'s "two different times, two
    different answers"): the recorder calls this before starting, never
    `Pipeline.load` itself -- the very same pipeline loads fine for resim,
    where an excluded/decimated port is merely a cut `sim probe` reports as
    infeasible, not an error. A `mode: simulate` stage consuming a
    producing stage's output that is `excluded`/`decimate`d is a load error
    naming both ends: you would be recording a run whose own inputs you are
    not keeping, which can never be resimmed. `source.*`-fed inputs are
    exempt -- stimulus has no `record:` policy of its own in this model,
    the recorder always keeps it in full."""
    by_name = {stage.name: stage for stage in stages}
    for stage in stages:
        if stage.mode != "simulate":
            continue
        for port_name, ref in stage.inputs.items():
            producer_name, ref_port = _split_ref(ref)
            if producer_name == "source":
                continue
            producer_stage = by_name.get(producer_name)
            if producer_stage is None:
                continue  # an undeclared producer is already _validate_wiring's error
            policy = record_policy_for(producer_stage, ref_port)
            if policy.verb is RecordVerb.FULL:
                continue
            detail = f"decimate={policy.decimate_n}" if policy.verb is RecordVerb.DECIMATE else policy.verb.value
            raise AuthoringError(
                expected=f"'{producer_name}.{ref_port}' to be recorded 'full' while "
                         f"stage '{stage.name}' (mode: simulate) consumes it as '{port_name}'",
                found=f"record: {detail}", where=f"stage '{producer_name}' record '{ref_port}'",
                hint="set record: full for this port, or set the consuming stage to mode: measured/off",
            )


def _resolve_components(
    stages: Sequence[Stage], *, search: Sequence[Path], components: Mapping[str, SilComponent],
) -> tuple[dict[str, SilComponent], dict[str, Path | None], dict[str, Path | None]]:
    """`impl: dll:<stem>` / `stubdll:<stem>` load for real, through
    `resolve_library` (`P-5`) + `CtypesSilComponent`. `impl: stub:<name>`
    has no registry yet (`S-C2`) -- it must be supplied via `components=`.
    A caller-supplied entry always wins, for any `impl:` kind.

    Also returns each stage's resolved **bundle directory** (`<library_dir>/
    config`, `R-SIM-3a`) and the raw **library file path** itself, both
    `None` for a `components=`-supplied stage, since this function never
    sees a file path for those. `OD-11`'s cross-component agreement check
    (`_validate_cross_component_agreement`) is the bundle directory's only
    consumer; the library path is `Pipeline.component_build_shas`'s
    (`UT-D7-9`, `NR-SIM-24`)."""
    resolved: dict[str, SilComponent] = {}
    bundle_dirs: dict[str, Path | None] = {}
    library_paths: dict[str, Path | None] = {}
    for stage in stages:
        if stage.name in components:
            resolved[stage.name] = components[stage.name]
            bundle_dirs[stage.name] = None
            library_paths[stage.name] = None
            continue
        if not stage.impl:
            raise AuthoringError(
                expected="impl: on the stage, or a pre-built component via components=",
                found="impl: absent", where=f"stage '{stage.name}'",
                hint="add impl: dll:<stem> / stubdll:<stem>, or pass components={...}",
            )
        kind, _, ref = stage.impl.partition(":")
        if kind in ("dll", "stubdll"):
            lib_path = resolve_library(ref, search=search)
            resolved[stage.name] = CtypesSilComponent(lib_path)
            bundle_dirs[stage.name] = lib_path.parent / "config"
            library_paths[stage.name] = lib_path
        elif kind == "stub":
            raise AuthoringError(
                expected=f"stage '{stage.name}' supplied via components=",
                found="no stub registry exists yet (S-C2)", where=f"stage '{stage.name}' impl: {stage.impl!r}",
                hint="pass components={...} with a pre-built InProcessSilComponent",
            )
        else:
            raise AuthoringError(
                expected="impl: one of dll:<stem> | stubdll:<stem> | stub:<name> (with components=)",
                found=stage.impl, where=f"stage '{stage.name}'",
                hint="'legacy:' stages are not yet supported",
            )
    return resolved, bundle_dirs, library_paths


def _validate_cross_component_agreement(
    bundle_dirs: Mapping[str, Path | None], components: Mapping[str, SilComponent], *, allow_mixed_projects: bool,
) -> bool:
    """Thin wrapper -- the real check moved to `config/bundle.py::
    check_cross_component_agreement` (`WP-04`, `IMP-0160`), which takes
    plain project names rather than `SilComponent` so `config/**` stays free
    of any import that itself touches `ctypes` (`ANL-SW-34`). Behaviour is
    unchanged; this is the call site."""
    projects = {name: component.manifest.project for name, component in components.items()}
    return check_cross_component_agreement(
        projects, bundle_dirs, allow_mixed_projects=allow_mixed_projects,
    )


def _require_multiple(period_ns: int, base_grid_ns: int, *, stage_name: str) -> None:
    """The guard `_compute_base_grid_ns` calls for every declared period.
    Kept as its own function, independently unit-tested with adversarial
    numbers (`test_c1c_pipeline.py`): a `base_grid_ns` that is genuinely the
    GCD of every period in the set makes this tautologically always pass
    (GCD divides every member of the set it was computed from, by
    definition) -- there is no set of real, correctly-derived periods that
    can ever fail it. The check stays anyway, because `R-SIM-18` states the
    invariant explicitly and a future change to how periods are supplied
    (e.g. a per-pipeline override) could make it reachable; a guard that is
    unreachable today is cheap, and finding out it is unreachable is what
    this comment records -- not a reason to delete it."""
    if period_ns % base_grid_ns != 0:
        raise AuthoringError(
            expected=f"period_ns to be an integer multiple of the base grid ({base_grid_ns} ns)",
            found=f"stage '{stage_name}' period_ns={period_ns}",
            where="Pipeline base grid (R-SIM-18)",
            hint=f"base grid {base_grid_ns} ns is the GCD of every stage's declared period_ns",
        )


def _compute_base_grid_ns(stages: Sequence[Stage], components: Mapping[str, SilComponent]) -> int:
    """`R-SIM-18`: the base grid is the GCD of every declared (nonzero)
    `period_ns` -- derived, never configured, never rounded. `0` means
    undeclared: that stage is due every call and does not participate in
    the GCD. No declared periods at all -> no grid (`0`)."""
    periods = [
        components[stage.name].manifest.period_ns for stage in stages
        if components[stage.name].manifest.period_ns > 0
    ]
    if not periods:
        return 0
    base_grid_ns = reduce(gcd, periods)
    for stage in stages:
        period_ns = components[stage.name].manifest.period_ns
        if period_ns > 0:
            _require_multiple(period_ns, base_grid_ns, stage_name=stage.name)
    return base_grid_ns


def _find_port(specs: Sequence[PortSpec], name: str) -> PortSpec | None:
    for spec in specs:
        if spec.name == name:
            return spec
    return None


def _validate_wiring(
    stages: Sequence[Stage], components: Mapping[str, SilComponent], recording: RecordingReader | None,
    source: Source | None = None,
) -> None:
    """`Pipeline.load`'s validation, in api reference SS3.3's order: every
    input resolves, `measured` is checked against the recording, a
    port-type mismatch and a forward reference both raise naming both ends.
    (Severed-chain detection is `severed_chains()`, checked separately --
    it is returned, never raised: `sim_sil_contract.md` SS4.2.) `source`
    is optional (`S-C2`): omitted, a `source.*` reference is left
    unchecked here, same as before this stage -- a test with no real
    `Source` still loads. Supplied, a `source.<name>` reference to a port
    outside `source.emits()` is a load error naming both (`R-SIM-10`)."""
    index_by_name: dict[str, int] = {}
    for i, stage in enumerate(stages):
        if stage.name in index_by_name:
            raise AuthoringError(
                expected="every stage name unique", found=f"'{stage.name}' declared more than once",
                where="pipeline stages", hint="rename one of the two",
            )
        index_by_name[stage.name] = i

    for i, stage in enumerate(stages):
        manifest = components[stage.name].manifest

        for input_spec in manifest.inputs:
            ref = stage.inputs.get(input_spec.name)
            if ref is None:
                if not input_spec.optional and stage.mode == "simulate":
                    raise AuthoringError(
                        expected=f"stage '{stage.name}' input '{input_spec.name}' to be wired",
                        found="no entry in inputs:", where=f"stage '{stage.name}'",
                        hint=f"add inputs: {{{input_spec.name}: source.<name> | <earlier-stage>.<port>}}",
                    )
                continue

            producer_name, port_name = _split_ref(ref)
            if producer_name == "source":
                if source is not None and port_name not in source.emits():
                    emitted = ", ".join(sorted(source.emits())) or "(none)"
                    raise AuthoringError(
                        expected=f"source '{source.name}' to emit port '{port_name}'",
                        found=f"source '{source.name}' emits: {emitted}",
                        where=f"stage '{stage.name}' input '{input_spec.name}' references '{ref}'",
                        hint="check the port name against the source's emits(), or wire a different source",
                    )
                continue

            if producer_name not in index_by_name:
                raise AuthoringError(
                    expected="a declared stage name or 'source' before the first dot",
                    found=f"'{ref}'", where=f"stage '{stage.name}' input '{input_spec.name}'",
                    hint=f"declared stages: {', '.join(index_by_name)}",
                )
            if index_by_name[producer_name] >= i:
                raise AuthoringError(
                    expected=f"'{producer_name}' to be declared before '{stage.name}'",
                    found=f"'{producer_name}' is declared at or after '{stage.name}' (index {index_by_name[producer_name]} >= {i})",
                    where=f"stage '{stage.name}' input '{input_spec.name}' references '{ref}'",
                    hint="stages execute in declaration order; a later stage cannot feed an earlier one, and there is no last-tick fallback",
                )

            producer_manifest = components[producer_name].manifest
            producer_port = _find_port(producer_manifest.outputs, port_name)
            if producer_port is None:
                produced = ", ".join(p.name for p in producer_manifest.outputs) or "(none)"
                raise AuthoringError(
                    expected=f"'{producer_name}' to produce output port '{port_name}'",
                    found=f"'{producer_name}' outputs: {produced}",
                    where=f"stage '{stage.name}' input '{input_spec.name}' references '{ref}'",
                    hint="check the port name against the producer's manifest",
                )
            if producer_port.proto_type != input_spec.proto_type:
                raise AuthoringError(
                    expected=f"'{ref}' to carry {input_spec.proto_type!r}",
                    found=f"'{ref}' carries {producer_port.proto_type!r}",
                    where=f"stage '{stage.name}' input '{input_spec.name}'",
                    hint="the producer and consumer manifests disagree on this port's proto_type",
                )

        if stage.mode == "measured" and recording is not None:
            topics = set(recording.topics())
            missing = [spec.name for spec in manifest.outputs if spec.name not in topics]
            if missing:
                raise AuthoringError(
                    expected=f"the recording to contain stage '{stage.name}''s output topics",
                    found=f"missing: {', '.join(missing)}", where=f"stage '{stage.name}' (mode: measured)",
                    hint="record this stage's outputs, or set mode: simulate or off",
                )


def _validate_overrides(stages: Sequence[Stage], components: Mapping[str, SilComponent]) -> None:
    """`S-C1cΔ`: two checks beyond `_parse_overrides`' own grammar gate. An
    override addresses one of *this stage's own* declared input ports
    (never an arbitrary string); and a `select`/`drop` override needs
    `fixed_slots` on that port's spec. `PortSpec.fixed_slots` exists as of
    `S-C1aΔ2`, but no real component yet POPULATES it -- that is `S-C1d`'s
    own job (build order #12, generating it from `conf/ports.yaml`), still
    pending -- so today every real `select`/`drop` still raises here,
    naming the port and the undeclared field (`UT-C1c-25`'s documented,
    honest, only-reachable path until `S-C1d` lands). Never a guessed
    default (`NR-SIM-4`): `False` would mean "safe to compact", `True`
    would mean "safe to zero".
    """
    for stage in stages:
        manifest = components[stage.name].manifest
        for key, override in stage.overrides.items():
            address = parse_address(key, where=f"stage '{stage.name}' overrides '{key}'")
            port_spec = _find_port(manifest.inputs, address.port)
            if port_spec is None:
                declared = ", ".join(p.name for p in manifest.inputs) or "(none)"
                raise AuthoringError(
                    expected=f"stage '{stage.name}' to declare input port '{address.port}'",
                    found=f"declared inputs: {declared}", where=f"stage '{stage.name}' overrides '{key}'",
                    hint="an override addresses one of this stage's own input ports",
                )
            if override.verb in (OverrideVerb.SELECT, OverrideVerb.DROP) and port_spec.fixed_slots is None:
                raise ContractError(
                    expected=f"port '{address.port}' to declare fixed_slots for a {override.verb.value} override",
                    found="fixed_slots absent from the manifest", where=f"stage '{stage.name}' overrides '{key}'",
                    hint="drop/select on a repeated field needs fixed_slots declared true or false "
                         "(NR-SIM-4); arrives at S-C1d",
                )


class Pipeline:
    """Ordered stages, wired by name (`sim_api_reference.md` SS3.3)."""

    def __init__(
        self, *, name: str, stages: tuple[Stage, ...], version: int, components: Mapping[str, SilComponent],
        faults: Sequence[Fault] = (), allow_mixed_projects: bool = False, mixed_projects: bool = False,
        library_paths: Mapping[str, Path | None] | None = None,
    ) -> None:
        self.name = name
        self.stages = stages
        self.version = version
        self._components = dict(components)
        #: `dll:`/`stubdll:` stages' resolved library file, keyed by stage
        #: name -- `None` (absent from a `components=`-supplied stage) same
        #: as `bundle_dirs` in `_resolve_components`. `component_build_shas`
        #: is the only consumer (`UT-D7-9`, `NR-SIM-24`).
        self.library_paths: dict[str, Path | None] = dict(library_paths or {})
        #: `OD-11`: `allow_mixed_projects` is what the pipeline file
        #: *requested*; `mixed_projects` is what `_validate_cross_component_
        #: agreement` actually *found*. Independent facts -- a pipeline can
        #: request the escape and still resolve a single-project run.
        self.allow_mixed_projects = allow_mixed_projects
        self.mixed_projects = mixed_projects
        self.base_grid_ns = _compute_base_grid_ns(stages, self._components)
        #: `step()`'s own clock and held-value cache (`R-SIM-18`) -- reset on
        #: every `Pipeline` construction, including the copies `with_mode`
        #: returns: a mode change is a configuration edit, not a tick.
        self._elapsed_ns = 0
        self._last_output: dict[str, Mapping[str, bytes]] = {}
        self._last_due_ns: dict[str, int] = {}
        #: `S-C1cΔ`: `hold`'s own memory, one entry per (stage, address) --
        #: also reset on every construction, same reasoning as the clock
        #: above. Lazily populated per stage on first override application.
        self._override_first_seen: dict[tuple[str, str], float] = {}
        self._message_classes: dict[str, Mapping[str, type]] = {}
        #: `run.faults:` (`sim_scenarios_and_expectations.md` SS9.2) --
        #: applied to the STIMULUS every `exec()`/`step()` call, before any
        #: stage sees it ("a failure of the sensor or the transport", the
        #: world model's own output). `_fault_first_active` is `stale`'s own
        #: cross-tick memory, `apply_fault`'s `first_active_t_s`, keyed by
        #: the fault's own address -- same reasoning as
        #: `_override_first_seen`, reset on every construction.
        self._faults = tuple(faults)
        self._fault_first_active: dict[str, float | None] = {}
        #: `R-SIM-18`'s own closing line, `ScheduleDisagreement`'s own
        #: docstring -- every due-tick mismatch between a port's declared
        #: `period_us` and the real ABI's own `updated` flag, accumulated
        #: for this `Pipeline` instance's whole life. Reset on every
        #: construction, same reasoning as `_last_output`/`_last_due_ns`.
        self._schedule_disagreements: list[ScheduleDisagreement] = []
        #: One shared tick counter for `Fault.active_at`'s `after_tick` --
        #: `step()` already tracks elapsed time in `_elapsed_ns`; `exec()`
        #: gains the same accumulation here so both entry points can time
        #: a fault's window identically. A `Pipeline` instance is driven by
        #: exactly one of `exec()`/`step()` for its whole life (never both),
        #: so sharing the counter is safe.
        self._tick_index = 0

    def __repr__(self) -> str:
        return f"<Pipeline name={self.name!r} stages={[s.name for s in self.stages]}>"

    def manifest_for(self, stage_name: str) -> ComponentManifest:
        """A declared stage's own component manifest (`S-C9`,
        `Session.feasible_cuts`'s one dependency on `Pipeline` beyond its
        `stages`) -- the manifest a recording's `provides:` is checked
        against, never a name this class invents."""
        return self._components[stage_name].manifest

    def init_components(self, config_path: Path | None = None) -> None:
        """Calls `.init()` on every resolved stage's own component
        (`SilComponent.init`, `sim_sil_contract.md` SS4.1) -- required
        once before the first `exec()`/`step()` for a real `dll:`/
        `stubdll:` stage (`CtypesSilComponent.exec` raises otherwise).
        Every test to date injects a pre-initialised `InProcessSilComponent`
        via `components=` and so never needed this; a live resim or run
        against a real library does."""
        for component in self._components.values():
            component.init(config_path)

    def shutdown_components(self) -> None:
        """The paired teardown (`SilComponent.shutdown`) -- always call
        after a real run, even if `exec()`/`step()` raised."""
        for component in self._components.values():
            component.shutdown()

    def component_build_shas(self) -> dict[str, str]:
        """`sha256` of each `dll:`/`stubdll:` stage's resolved library file,
        keyed by stage name -- the real value `core.manifest.build_manifest`'s
        `component_build_shas` kwarg needs (`UT-D7-9`, `NR-SIM-24`), closing
        the gap `S-D7`'s own status note named: "nothing computes a real
        hash from a resolved library path". A `components=`-supplied stage
        has no file on disk and is simply absent from the result -- there is
        nothing to hash, not an empty string standing in for a real one."""
        return {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in self.library_paths.items() if path is not None
        }

    @property
    def faults(self) -> tuple[Fault, ...]:
        """This run's own `run.faults:` (`S-C3`, `sim_scenarios_and_
        expectations.md` SS9.2), read-only. Public so `core.manifest.
        build_manifest` can make `R-SIM-15`'s "declared, never smuggled"
        claim legible for faults the same way it already does for
        overrides (`UT-D6-2`) -- `_faults` itself stays private, this is
        the one sanctioned read."""
        return self._faults

    @property
    def schedule_disagreements(self) -> tuple[ScheduleDisagreement, ...]:
        """Every `ScheduleDisagreement` `step()` has found so far, in the
        order found -- read-only, same "the one sanctioned read" reasoning
        `faults` states above; `_schedule_disagreements` itself stays
        private and append-only."""
        return tuple(self._schedule_disagreements)

    @classmethod
    def parse_stages(cls, path: Path) -> tuple[Stage, ...]:
        """The stage-declaration half of `load()` -- no component
        resolution, so no `dll:`/`stubdll:` lookup and nothing here can
        raise on a missing library. `sim doctor`'s own need (`UT-D6-8`):
        report EVERY stage's `impl:` resolution, even when one of them is
        broken, rather than the whole pipeline failing to load before any
        diagnosis happens (`_resolve_components` is the part that raises)."""
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return tuple(
            Stage(
                name=spec["name"], mode=spec.get("mode", "simulate"), impl=spec.get("impl"),
                inputs=dict(spec.get("inputs", {})),
                overrides=_parse_overrides(spec.get("overrides", {}), stage_name=spec["name"]),
                record=_parse_record(spec.get("record", {}), stage_name=spec["name"]),
            )
            for spec in raw.get("stages", [])
        )

    @classmethod
    def load(
        cls, path: Path, *, search: Sequence[Path] = (),
        components: Mapping[str, SilComponent] | None = None,
        recording: RecordingReader | None = None,
        source: Source | None = None,
        faults: Sequence[Fault] = (),
    ) -> Pipeline:
        """Validates at LOAD, never at first tick (SS5.14). `search` is
        forwarded to `resolve_library` for `dll:`/`stubdll:` stages;
        `components` supplies already-built stages (the only way to satisfy
        `impl: stub:` until S-C2's registry exists, and how a test injects a
        fake component with no file on disk); `recording` is checked against
        every `mode: measured` stage's declared outputs; `source` (`S-C2`)
        is checked against every `source.*` reference's `emits()` -- both
        optional, so a test wiring neither still loads exactly as before
        either stage existed. `faults` is a scenario's own `run.faults:`
        (`contracts/scenario.py`) -- the pipeline file itself never declares
        them (SS9.2's vocabulary lives with the run, not the wiring)."""
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        version = _resolve_version(raw)
        name = raw.get("name", path.stem)
        allow_mixed_projects = bool(raw.get("allow_mixed_projects", False))
        stages = cls.parse_stages(path)
        resolved, bundle_dirs, library_paths = _resolve_components(stages, search=search, components=components or {})
        _validate_wiring(stages, resolved, recording, source)
        _validate_overrides(stages, resolved)
        mixed_projects = _validate_cross_component_agreement(
            bundle_dirs, resolved, allow_mixed_projects=allow_mixed_projects,
        )
        return cls(
            name=name, stages=stages, version=version, components=resolved, faults=faults,
            allow_mixed_projects=allow_mixed_projects, mixed_projects=mixed_projects, library_paths=library_paths,
        )

    def _message_classes_for(self, stage_name: str) -> Mapping[str, type]:
        if stage_name not in self._message_classes:
            self._message_classes[stage_name] = resolve_message_classes(self._components[stage_name].manifest)
        return self._message_classes[stage_name]

    def _apply_input_overrides(self, stage: Stage, inputs: dict[str, bytes]) -> None:
        """Overrides apply to a stage's OWN input ports, right before
        `exec()`/`step()` hand them to the component (`S-C1cΔ`, `R-SIM-15`)
        -- declared and load-validated since `S-C1c`, now real. Several
        overrides addressing the same port (a bare-port `hold` and a
        `field` `const`, say) apply to one decode/re-encode, not one each.
        """
        if not stage.overrides:
            return
        manifest = self._components[stage.name].manifest
        classes = self._message_classes_for(stage.name)
        by_port: dict[str, list[tuple[Address, Override]]] = {}
        for key, override in stage.overrides.items():
            address = parse_address(key, where=f"stage '{stage.name}' overrides '{key}'")
            by_port.setdefault(address.port, []).append((address, override))

        for port_name, entries in by_port.items():
            if port_name not in inputs:
                continue  # nothing wired this tick (an absent optional input) -- nothing to override
            port_spec = _find_port(manifest.inputs, port_name)
            message_cls = classes[port_spec.proto_type]
            payload = inputs[port_name]
            for address, override in entries:
                state_key = (stage.name, address.raw)
                payload, first_seen = apply_override(
                    payload, message_cls, address, override,
                    first_seen=self._override_first_seen.get(state_key),
                    fixed_slots=port_spec.fixed_slots,
                )
                self._override_first_seen[state_key] = first_seen
            inputs[port_name] = payload

    def _message_cls_for_source_port(self, port_name: str) -> type | None:
        """Resolves a STIMULUS port's message class for `corrupt`
        (`apply_fault`'s only verb that needs one) by finding the first
        stage wired to `source.<port_name>` and reusing its own input
        `PortSpec`/manifest -- the stimulus itself carries no schema of its
        own (`Source.poll()` returns bare bytes), so this borrows the
        schema from whichever stage already declared it. `None` when no
        stage references this port (a `corrupt` fault the pipeline cannot
        resolve raises `apply_fault`'s own `message_cls` error, naming the
        gap rather than silently no-opping)."""
        for stage in self.stages:
            for local_port, ref in stage.inputs.items():
                producer_name, ref_port = _split_ref(ref)
                if producer_name == "source" and ref_port == port_name:
                    port_spec = _find_port(self._components[stage.name].manifest.inputs, local_port)
                    if port_spec is not None:
                        return self._message_classes_for(stage.name).get(port_spec.proto_type)
        return None

    def _apply_stimulus_faults(
        self, stimulus: Mapping[str, bytes], *, t_ns: int, t_s: float, tick_index: int,
    ) -> tuple[dict[str, bytes], dict[str, InputMeta]]:
        """`run.faults:` (`sim_scenarios_and_expectations.md` SS9.2) target
        the STIMULUS -- "a failure of the sensor or the transport" is the
        world model's own output, before any stage sees it, addressed by
        the override grammar's bare port name (matching `stimulus`'s own
        keys, the same "no stage qualifier needed" reasoning
        `_apply_input_overrides` gets for free by living on one `Stage`).
        An inter-stage "bus" fault is out of scope here (SS9.2's own
        rejected bus-level fault models). `drop` removes the stimulus key
        entirely -- `R-SIM`'s "absent port" convention, `UT-C1c-12` --
        rather than carrying a `valid=False` `InputMeta` entry, which is
        indistinguishable from the port never having existed this tick,
        exactly what `drop` means."""
        if not self._faults:
            return dict(stimulus), {}
        stimulus = dict(stimulus)
        meta: dict[str, InputMeta] = {}
        for fault in self._faults:
            address = parse_address(fault.address, where=f"run.faults address {fault.address!r}")
            port_name = address.port
            if port_name not in stimulus:
                continue
            port_value = PortValue(
                name=port_name, origin="simulated", message=stimulus[port_name],
                valid=True, updated=True, t_ns=t_ns,
            )
            message_cls = self._message_cls_for_source_port(port_name) if fault.verb is FaultVerb.CORRUPT else None
            result, first_active = apply_fault(
                port_value, fault, t_s=t_s, tick_index=tick_index,
                first_active_t_s=self._fault_first_active.get(fault.address), message_cls=message_cls,
            )
            self._fault_first_active[fault.address] = first_active
            if first_active is None:
                continue  # not active this tick
            if result.message is None:
                stimulus.pop(port_name, None)
                meta.pop(port_name, None)
                continue
            stimulus[port_name] = result.raw_bytes
            meta[port_name] = InputMeta(valid=result.valid, age_s=result.age_s)
        return stimulus, meta

    def exec(
        self, dt_ns: int, stimulus: Mapping[str, bytes], *,
        measured: Mapping[str, Mapping[str, bytes]] | None = None,
    ) -> Mapping[str, Mapping[str, bytes]]:
        """Runs one tick, stages in declaration order, single-threaded
        (`sim_sil_contract.md` SS4.2's ordering rule; `FunctionRunner`'s own
        choice, mirrored). `stimulus` supplies `source.*` values keyed by
        source port name; `measured` supplies each `mode: measured` stage's
        recorded outputs for this tick, keyed by stage name then port --
        `Pipeline` does no I/O itself, so reading those bytes from a
        recording is the caller's job.

        `mode: off` is neither run nor injected: a reference to an `off`
        stage's port is simply absent from whatever consumes it, which is
        `valid=0` downstream by the same "absent port" convention
        `SilComponent` already uses (`UT-C1c-12`) -- no special-casing
        needed here.

        Returns every stage's output ports this tick, keyed by stage name --
        both actually-computed and injected, so a caller (a future
        recorder) sees the whole tick without re-deriving which stages ran.
        Single-rate: every declared stage executes every call, unconditionally
        -- the primitive `step()` (multi-rate, due-tick gating) is built on.
        """
        # Accumulate BEFORE reading, matching step()'s own convention (its
        # first line is this same `+=`) -- `resim_pipeline` passes dt_ns=0
        # for the very first tick, so this still lands `t_s == 0.0` there;
        # accumulating after would leave every tick reading the PREVIOUS
        # tick's elapsed time instead of its own.
        self._elapsed_ns += dt_ns
        t_s = self._elapsed_ns / 1_000_000_000.0
        stimulus, stimulus_meta = self._apply_stimulus_faults(
            stimulus, t_ns=self._elapsed_ns, t_s=t_s, tick_index=self._tick_index,
        )
        self._tick_index += 1

        measured = measured or {}
        outputs_by_stage: dict[str, Mapping[str, bytes]] = {}
        for stage in self.stages:
            if stage.mode == "off":
                continue
            if stage.mode == "measured":
                outputs_by_stage[stage.name] = dict(measured.get(stage.name, {}))
                continue

            inputs: dict[str, bytes] = {}
            input_meta: dict[str, InputMeta] = {}
            for port_name, ref in stage.inputs.items():
                producer_name, ref_port = _split_ref(ref)
                produced = stimulus if producer_name == "source" else outputs_by_stage.get(producer_name, {})
                if ref_port in produced:
                    inputs[port_name] = produced[ref_port]
                    if producer_name == "source" and ref_port in stimulus_meta:
                        input_meta[port_name] = stimulus_meta[ref_port]

            self._apply_input_overrides(stage, inputs)
            outputs_by_stage[stage.name] = self._components[stage.name].exec(dt_ns, inputs, input_meta)
        return outputs_by_stage

    def step(
        self, dt_ns: int, stimulus: Mapping[str, bytes], *,
        measured: Mapping[str, Mapping[str, bytes]] | None = None,
    ) -> Mapping[str, PortValue]:
        """The multi-rate-aware entry point (`R-SIM-18`). Advances this
        `Pipeline`'s own clock by `dt_ns` and runs (or injects) a stage only
        on its due ticks -- a stage with no declared `period_ns` (`0`,
        undeclared) is due every call. A stage that is not due HOLDS its
        last output rather than re-running: `updated=False`, `age_s` the
        exact elapsed time since it was last actually due, from integer
        nanoseconds (`P-8`) -- never accumulated as float seconds.

        Returns one `PortValue` per declared output port, keyed by fully
        qualified name (`"<stage>.<port>"`, matching `core.tick.Tick.ports`
        directly) -- the FULL declared port set every call, held or fresh,
        which is `R-SIM-10`'s invariant carried into multi-rate (`UT-C1c-21`):
        a downstream stage wired to a not-due producer still sees that
        producer's last real value, not a gap.
        """
        self._elapsed_ns += dt_ns
        t_s = self._elapsed_ns / 1_000_000_000.0
        stimulus, stimulus_meta = self._apply_stimulus_faults(
            stimulus, t_ns=self._elapsed_ns, t_s=t_s, tick_index=self._tick_index,
        )
        self._tick_index += 1
        measured = measured or {}
        fresh: dict[str, Mapping[str, bytes]] = {}
        result: dict[str, PortValue] = {}

        for stage in self.stages:
            if stage.mode == "off":
                continue
            manifest = self._components[stage.name].manifest
            due = manifest.period_ns == 0 or self._elapsed_ns % manifest.period_ns == 0

            if due:
                if stage.mode == "measured":
                    computed = dict(measured.get(stage.name, {}))
                else:
                    inputs: dict[str, bytes] = {}
                    input_meta: dict[str, InputMeta] = {}
                    for port_name, ref in stage.inputs.items():
                        producer_name, ref_port = _split_ref(ref)
                        source_map = stimulus if producer_name == "source" else (
                            fresh.get(producer_name) or self._last_output.get(producer_name, {})
                        )
                        if ref_port in source_map:
                            inputs[port_name] = source_map[ref_port]
                            if producer_name == "source":
                                if ref_port in stimulus_meta:
                                    input_meta[port_name] = stimulus_meta[ref_port]
                            else:
                                # The producer's own held-value staleness
                                # (`R-SIM-18`) -- the real gap this pass
                                # closes: a half-rate producer's stale
                                # output now reaches the real DLL's own
                                # ageS gate instead of always reading 0.0.
                                producer_hold_age_s = (
                                    self._elapsed_ns - self._last_due_ns.get(producer_name, self._elapsed_ns)
                                ) / 1_000_000_000.0
                                input_meta[port_name] = InputMeta(valid=True, age_s=producer_hold_age_s)
                    self._apply_input_overrides(stage, inputs)
                    computed = self._components[stage.name].exec(dt_ns, inputs, input_meta)
                    self._check_schedule_disagreements(stage.name, manifest, computed)
                fresh[stage.name] = computed
                self._last_output[stage.name] = computed
                self._last_due_ns[stage.name] = self._elapsed_ns

            produced = self._last_output.get(stage.name, {})
            # Schedule-derived, never capture-derived (`S-B2Δ`, `R-SIM-18`):
            # a live SIL stage has no recording capture stamp, only its own
            # due/held bookkeeping -- `hold_age_s` says so explicitly rather
            # than the two sources sharing one bare float (`UT-B2-13`).
            hold_age_s = (self._elapsed_ns - self._last_due_ns.get(stage.name, self._elapsed_ns)) / 1_000_000_000.0
            origin = "measured" if stage.mode == "measured" else "simulated"
            for port_spec in manifest.outputs:
                qualified = f"{stage.name}.{port_spec.name}"
                if port_spec.name in produced:
                    result[qualified] = PortValue(
                        name=qualified, message=produced[port_spec.name], origin=origin,
                        valid=True, updated=due, hold_age_s=hold_age_s,
                    )
                else:
                    result[qualified] = PortValue(
                        name=qualified, message=None, origin="unknown", valid=False, updated=False,
                    )
        return result

    def _check_schedule_disagreements(
        self, stage_name: str, manifest: ComponentManifest, computed: Mapping[str, bytes],
    ) -> None:
        """`R-SIM-18`'s closing line, `ScheduleDisagreement`'s own
        docstring on why this checks each port's own `period_us` rather
        than `manifest.period_ns` (the component-level GCD that already
        decided whether `exec()` ran at all this tick -- gating multiple
        functions at different real rates through one call is normal and
        NOT itself a disagreement). `period_us == 0` (undeclared) predicts
        "always due," the same convention `PortSpec.period_us`'s own
        docstring states, so an undeclared port can never disagree.
        `computed` already lost the ABI's raw `updated` int
        (`CtypesSilComponent._collect_outputs`'s own docstring) -- but
        never the fact, since a port that came back `updated=0` is simply
        absent from `computed`, so presence IS the actual flag here.
        `ProvenanceWarning`, immediately -- "reported, never hidden" means
        visible the tick it happens, not only queryable after the fact
        (`schedule_disagreements` is the queryable half, for a caller that
        wants the full list rather than a live warning stream)."""
        for port_spec in manifest.outputs:
            if port_spec.period_us == 0:
                continue
            port_period_ns = port_spec.period_us * 1000
            predicted_due = self._elapsed_ns % port_period_ns == 0
            actual_updated = port_spec.name in computed
            if predicted_due == actual_updated:
                continue
            self._schedule_disagreements.append(ScheduleDisagreement(
                tick_index=self._tick_index - 1, stage=stage_name, port=port_spec.name,
                predicted_due=predicted_due, actual_updated=actual_updated,
            ))
            warn(ProvenanceWarning(
                f"stage '{stage_name}' port '{port_spec.name}': declared period_us={port_spec.period_us} "
                f"predicted due={predicted_due} at tick {self._tick_index - 1}, but the ABI's own updated "
                f"flag reported {actual_updated} -- rate gating has drifted from the declared period"
            ))

    def severed_chains(self) -> tuple[SeveredChain, ...]:
        """A `measured` stage between two `simulate` stages on one data path
        (`R-SIM-10`). Returned, not raised -- a future GUI auto-closes by
        default (`S-D6`), a future CLI warns; `off -> measured -> simulate`
        is deliberately not flagged, since nothing computed into the gap."""
        index_by_name = {s.name: i for i, s in enumerate(self.stages)}
        chains: list[SeveredChain] = []
        for stage in self.stages:
            if stage.mode != "measured":
                continue
            upstream_links = []
            for port_name, ref in stage.inputs.items():
                ref_stage, ref_port = _split_ref(ref)
                if ref_stage in index_by_name and self.stages[index_by_name[ref_stage]].mode == "simulate":
                    upstream_links.append((ref_stage, ref_port, port_name))
            if not upstream_links:
                continue
            for later in self.stages[index_by_name[stage.name] + 1 :]:
                if later.mode != "simulate":
                    continue
                for port_name, ref in later.inputs.items():
                    ref_stage, _ref_port = _split_ref(ref)
                    if ref_stage != stage.name:
                        continue
                    for upstream_name, upstream_port, _ in upstream_links:
                        chains.append(SeveredChain(
                            upstream=upstream_name, upstream_port=upstream_port,
                            measured=stage.name, downstream=later.name, downstream_port=port_name,
                        ))
        return tuple(chains)

    def with_mode(self, stage: str, mode: Mode, *, close_gaps: bool = True) -> Pipeline:
        """Returns a NEW pipeline; `impl:`/`inputs:` are retained on the
        changed stage so the toggle is reversible (`R-SIM-10`). With
        `close_gaps` (default), any severed chain the change just created
        that involves `stage` is closed by flipping its `measured` member to
        `simulate` too -- undoably, since the caller keeps the old object.

        `close_gaps=False` forces the gap open deliberately (watching one
        stage's divergence while a downstream stage stays on known-good
        input, `R-SIM-10`'s own example) -- never silent: exactly ONE
        `ProvenanceWarning` names every stage `close_gaps=True` would have
        flipped, badged *"computed, not consumed"* wherever a GUI renders it
        (`S-D6`, `UT-D6-6`). The run itself is never blocked -- this is a
        warning a headless caller sees in the log, not an error."""
        names = {s.name for s in self.stages}
        if stage not in names:
            raise AuthoringError(
                expected="a declared stage name", found=stage, where="Pipeline.with_mode",
                hint=f"declared stages: {', '.join(names)}",
            )
        new_stages = tuple(
            Stage(name=s.name, mode=mode, impl=s.impl, inputs=s.inputs, overrides=s.overrides, record=s.record)
            if s.name == stage else s
            for s in self.stages
        )
        result = Pipeline(
            name=self.name, stages=new_stages, version=self.version, components=self._components,
            faults=self._faults, library_paths=self.library_paths,
        )
        to_close = {
            chain.measured for chain in result.severed_chains() if stage in (chain.upstream, chain.measured, chain.downstream)
        }
        if not to_close:
            return result
        if not close_gaps:
            warn(ProvenanceWarning(
                f"stage(s) {', '.join(sorted(to_close))} computed, not consumed -- "
                f"setting '{stage}' to {mode!r} severed the chain to it and close_gaps=False left the gap open"
            ))
            return result
        closed_stages = tuple(
            Stage(name=s.name, mode="simulate", impl=s.impl, inputs=s.inputs, overrides=s.overrides, record=s.record)
            if s.name in to_close else s
            for s in new_stages
        )
        return Pipeline(
            name=self.name, stages=closed_stages, version=self.version, components=self._components,
            library_paths=self.library_paths,
        )

    def to_yaml(self) -> str:
        data = {
            "version": self.version,
            "name": self.name,
            "stages": [
                {
                    "name": s.name, "mode": s.mode,
                    **({"impl": s.impl} if s.impl is not None else {}),
                    "inputs": dict(s.inputs),
                    **(
                        {"overrides": {k: {"verb": o.verb.value, **({"value": o.value} if o.value is not None else {})}
                                       for k, o in s.overrides.items()}}
                        if s.overrides else {}
                    ),
                    **(
                        {"record": {
                            k: ({"decimate": p.decimate_n} if p.verb is RecordVerb.DECIMATE else p.verb.value)
                            for k, p in s.record.items()
                        }}
                        if s.record else {}
                    ),
                }
                for s in self.stages
            ],
        }
        return yaml.safe_dump(data, sort_keys=False)
