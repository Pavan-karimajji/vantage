# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`Pipeline` -- ordered stages, wired by name (sim_api_reference.md SS3.3,
sim_sil_contract.md SS4.2). Validated at LOAD, never at first tick (SS5.14):
every input reference resolves, `mode: measured` is checked against a
recording's topic index, a port-type mismatch and a forward reference are
both load errors naming both ends.

`Pipeline.exec` runs one tick, single-rate: every stage executes on every
call. Multi-rate scheduling (`period_ns`/GCD due-tick gating, held-port
`age_s`) and `contracts/override.py` are later slices' scope.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from adas_sim.contracts.component import CtypesSilComponent, PortSpec, SilComponent
from adas_sim.contracts.loader import resolve_library
from adas_sim.contracts.override import Override, parse_override_verb
from adas_sim.core.errors import AuthoringError
from adas_sim.io.base import RecordingReader

#: The only shape that has ever existed -- `_resolve_version`'s upgrade is a
#: no-op today; a real v2 would add a transform step there (`CR-SIM-23`).
CURRENT_PIPELINE_VERSION = 1

Mode = Literal["simulate", "measured", "off"]


@dataclass(frozen=True, slots=True)
class Stage:
    """One pipeline entry (`sim_api_reference.md` SS3.3). `inputs` maps this
    stage's own port name to a producer reference: `"source.<name>"` or
    `"<earlier-stage>.<port>"`. `overrides` is keyed by a port name or a
    field path (`"egoDyn.vx"`), from the closed four-verb list
    (`contracts/override.py`, `R-SIM-15`) -- declared and validated at load,
    not yet applied during `exec()` (a later slice wires that in)."""

    name: str
    mode: Mode
    impl: str | None
    inputs: Mapping[str, str]
    overrides: Mapping[str, Override] = field(default_factory=dict)


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


def _parse_overrides(raw: Mapping[str, Mapping[str, object]], *, stage_name: str) -> dict[str, Override]:
    """`overrides: {<port or port.field>: {verb: ..., value: ...}}` -- the
    verb is checked against the closed four (`R-SIM-15`); an unknown verb
    is a load error naming the offending key (`UT-C1c-17`)."""
    result: dict[str, Override] = {}
    for key, entry in raw.items():
        verb = parse_override_verb(entry["verb"], where=f"stage '{stage_name}' overrides '{key}'")
        result[key] = Override(verb=verb, value=entry.get("value"))
    return result


def _resolve_components(
    stages: Sequence[Stage], *, search: Sequence[Path], components: Mapping[str, SilComponent],
) -> dict[str, SilComponent]:
    """`impl: dll:<stem>` / `stubdll:<stem>` load for real, through
    `resolve_library` (`P-5`) + `CtypesSilComponent`. `impl: stub:<name>`
    has no registry yet (`S-C2`) -- it must be supplied via `components=`.
    A caller-supplied entry always wins, for any `impl:` kind."""
    resolved: dict[str, SilComponent] = {}
    for stage in stages:
        if stage.name in components:
            resolved[stage.name] = components[stage.name]
            continue
        if not stage.impl:
            raise AuthoringError(
                expected="impl: on the stage, or a pre-built component via components=",
                found="impl: absent", where=f"stage '{stage.name}'",
                hint="add impl: dll:<stem> / stubdll:<stem>, or pass components={...}",
            )
        kind, _, ref = stage.impl.partition(":")
        if kind in ("dll", "stubdll"):
            resolved[stage.name] = CtypesSilComponent(resolve_library(ref, search=search))
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
    return resolved


def _find_port(specs: Sequence[PortSpec], name: str) -> PortSpec | None:
    for spec in specs:
        if spec.name == name:
            return spec
    return None


def _validate_wiring(
    stages: Sequence[Stage], components: Mapping[str, SilComponent], recording: RecordingReader | None,
) -> None:
    """`Pipeline.load`'s validation, in api reference SS3.3's order: every
    input resolves, `measured` is checked against the recording, a
    port-type mismatch and a forward reference both raise naming both ends.
    (Severed-chain detection is `severed_chains()`, checked separately --
    it is returned, never raised: `sim_sil_contract.md` SS4.2.)"""
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
                continue  # S-C2 validates source.* against a real Source's emits()

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


class Pipeline:
    """Ordered stages, wired by name (`sim_api_reference.md` SS3.3)."""

    def __init__(
        self, *, name: str, stages: tuple[Stage, ...], version: int, components: Mapping[str, SilComponent],
    ) -> None:
        self.name = name
        self.stages = stages
        self.version = version
        self._components = dict(components)

    def __repr__(self) -> str:
        return f"<Pipeline name={self.name!r} stages={[s.name for s in self.stages]}>"

    @classmethod
    def load(
        cls, path: Path, *, search: Sequence[Path] = (),
        components: Mapping[str, SilComponent] | None = None,
        recording: RecordingReader | None = None,
    ) -> Pipeline:
        """Validates at LOAD, never at first tick (SS5.14). `search` is
        forwarded to `resolve_library` for `dll:`/`stubdll:` stages;
        `components` supplies already-built stages (the only way to satisfy
        `impl: stub:` until S-C2's registry exists, and how a test injects a
        fake component with no file on disk); `recording` is checked against
        every `mode: measured` stage's declared outputs."""
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        version = _resolve_version(raw)
        name = raw.get("name", path.stem)
        stages = tuple(
            Stage(
                name=spec["name"], mode=spec.get("mode", "simulate"), impl=spec.get("impl"),
                inputs=dict(spec.get("inputs", {})),
                overrides=_parse_overrides(spec.get("overrides", {}), stage_name=spec["name"]),
            )
            for spec in raw.get("stages", [])
        )
        resolved = _resolve_components(stages, search=search, components=components or {})
        _validate_wiring(stages, resolved, recording)
        return cls(name=name, stages=stages, version=version, components=resolved)

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
        Single-rate today: every stage executes every call (multi-rate
        due-tick gating is a later slice).
        """
        measured = measured or {}
        outputs_by_stage: dict[str, Mapping[str, bytes]] = {}
        for stage in self.stages:
            if stage.mode == "off":
                continue
            if stage.mode == "measured":
                outputs_by_stage[stage.name] = dict(measured.get(stage.name, {}))
                continue

            inputs: dict[str, bytes] = {}
            for port_name, ref in stage.inputs.items():
                producer_name, ref_port = _split_ref(ref)
                produced = stimulus if producer_name == "source" else outputs_by_stage.get(producer_name, {})
                if ref_port in produced:
                    inputs[port_name] = produced[ref_port]

            outputs_by_stage[stage.name] = self._components[stage.name].exec(dt_ns, inputs)
        return outputs_by_stage

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
        `simulate` too -- undoably, since the caller keeps the old object."""
        names = {s.name for s in self.stages}
        if stage not in names:
            raise AuthoringError(
                expected="a declared stage name", found=stage, where="Pipeline.with_mode",
                hint=f"declared stages: {', '.join(names)}",
            )
        new_stages = tuple(
            Stage(name=s.name, mode=mode, impl=s.impl, inputs=s.inputs, overrides=s.overrides) if s.name == stage else s
            for s in self.stages
        )
        result = Pipeline(name=self.name, stages=new_stages, version=self.version, components=self._components)
        if not close_gaps:
            return result
        to_close = {
            chain.measured for chain in result.severed_chains() if stage in (chain.upstream, chain.measured, chain.downstream)
        }
        if not to_close:
            return result
        closed_stages = tuple(
            Stage(name=s.name, mode="simulate", impl=s.impl, inputs=s.inputs, overrides=s.overrides) if s.name in to_close else s
            for s in new_stages
        )
        return Pipeline(name=self.name, stages=closed_stages, version=self.version, components=self._components)

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
                }
                for s in self.stages
            ],
        }
        return yaml.safe_dump(data, sort_keys=False)
