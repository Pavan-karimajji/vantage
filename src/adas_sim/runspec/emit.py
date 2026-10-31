# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`emit_run_spec` (`SW-0001`, design §3.5) -- the seam's own producer.
Takes `config.ResolvedConfig` (`WP-04`) plus whatever a caller has already
PROBED as plain data (`ComponentManifest` per unit, a content hash per
source, design §3.3a) and returns a `RunSpec` with every reference
resolved, every path absolute, every port carrying a concrete `record`,
`bulk` and `buffer_depth` -- **"if the engine has to decide something the
configuration layer could have decided, the spec is missing a field"**
(design §3.3, the one rule this module exists to keep).

**Schema `adas.sim.runspec/2.0`** (`VANTAGE_Architecture.md` §2.3, `IMP-0051`):
the writer emits `trigger`, `clock_period_ns`, `previous_cycle`, `bulk`,
`buffer_depth`, `outputs.livemeas`, `readiness_limit_steps` and
`fallback_max_gap`, and no longer writes `grid`, `order`, `delay_steps`,
`sampling` or `on_missing`. The values nobody supplied are `⊘`
(`ARCH §4`): they arrive in a `RunSetupValues` the caller must pass, this
module holds no default for any of them, and a missing one is an
`AuthoringError` naming the key.

**Why this module never opens a recording or loads a binary itself**
(`ANL-SW-34`, `runspec/` is one of the four restricted directories): the
probe (`RecordingIndex`/`ComponentManifest`) happens through the SAME
interfaces a real run uses, in a caller this module does not own -- passed
in here as plain data, never a handle (design §3.3a's own rule, `SW-0411`).
`resolve.library.resolve_library` is the one exception already established
by `IMP-0003`'s own design note ("exactly as it uses today's
`resolve_library`"): it searches directories for a file, never opens one.

**Scoped, honestly, for this pass** (`WP-05`): `sources[].ingest` needs
`IMP-0187`'s ingest-map parser, which is `WP-12`'s own work package and
does not exist yet -- every source's `ingest`/`absent` emit as empty lists,
never guessed. `coherence_verdict` needs `SI-12`, also not built -- it emits
`"unknown"`, an explicit non-answer (`R-SIM-25`, `NR-SIM-4`), never a
plausible `"normal"`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache, reduce
from math import gcd
from pathlib import Path

import jsonschema

from adas_sim.config import ResolvedConfig
from adas_sim.config.kinds import FileKind
from adas_sim.config.override import Override
from adas_sim.diagnostics.errors import AuthoringError, InternalError
from adas_sim.resolve.component import ComponentManifest, PortSpec
from adas_sim.resolve.library import resolve_library
from adas_sim.runspec.address import resolve_address
from adas_sim.runspec.canon import RunSpec

#: `SW-0005`, `SYS-0004` -- the one schema string `LoadRunSpec` accepts.
RUN_SPEC_SCHEMA = "adas.sim.runspec/2.0"

_SCHEMA_PATH = Path(__file__).parent / "schema" / "run_spec.schema.json"


@lru_cache(maxsize=None)
def _run_spec_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_run_spec(spec: RunSpec) -> None:
    """`IF-13`-adjacent: the published schema (`runspec/schema/run_spec.
    schema.json`) is what an external tool (or `simcore`'s own C++ reader)
    validates a spec against; this is the Python-side self-check
    `emit_run_spec` and its tests both use, so the emitter and the schema
    can never silently drift apart from each other."""
    jsonschema.validate(instance=spec.data, schema=_run_spec_schema())

@dataclass(frozen=True, slots=True)
class LiveMeasSpec:
    """`outputs.livemeas` (`ARCH §2.3`): the name and geometry of the live
    measurement. The four geometry values are `⊘` -- no default exists."""

    name: str
    cycle_slot_count: int
    cycle_slot_size: int
    bulk_slot_count: int
    bulk_slot_size: int


@dataclass(frozen=True, slots=True)
class RunSetupValues:
    """What a run setup needs that no component manifest or configuration
    file carries (`IMP-0051`, `ARCH §2.3`, `§4`). The caller supplies every
    one; this module has no default for any (`⊘`). A value that is missing
    or not of its type is an `AuthoringError` naming the key.

    - `readiness_limit_steps`, `fallback_max_gap`: integers (`⊘`).
    - `trigger`: stage name -> `control`, an input port name, or `""` when
      a clock starts the stage. Required for every `simulate` stage; a
      `measured` or `off` stage is never run and is written with `""`.
    - `buffer_depth`: `"<stage>.<port>"` or `"*"` -> integer (`⊘`); an exact
      entry wins over `"*"`. Required for every port.
    - `previous_cycle`: the `"<stage>.<port>"` inputs that are
      previous-cycle inputs (the rest are not).
    - `bulk`: the `"<stage>.<port>"` ports whose values go to `MeasBulk`.
    - `livemeas`: the live measurement, or `None` for no live measurement.
    """

    readiness_limit_steps: int | None
    fallback_max_gap: int | None
    trigger: Mapping[str, str]
    buffer_depth: Mapping[str, int]
    previous_cycle: frozenset[str] = frozenset()
    bulk: frozenset[str] = frozenset()
    livemeas: LiveMeasSpec | None = None


def _require_setup_integer(value: object, *, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuthoringError(
            expected=f"an integer value for '{key}' (a ⊘ value: no default exists)", found=repr(value),
            where="adas_sim.runspec.emit.RunSetupValues", hint=f"supply '{key}' in the RunSetupValues",
        )
    return value


def _buffer_depth_for(values: RunSetupValues, stage: str, port: str) -> int:
    key = f"{stage}.{port}"
    where = f"stages[{stage}].ports[{port}].buffer_depth"
    for candidate in (key, "*"):
        if candidate in values.buffer_depth:
            return _require_setup_integer(values.buffer_depth[candidate], key=where)
    raise AuthoringError(
        expected=f"an integer value for '{where}' (a ⊘ value: no default exists)", found="absent",
        where="adas_sim.runspec.emit.RunSetupValues.buffer_depth",
        hint=f"add '{key}' (or '*') to RunSetupValues.buffer_depth",
    )


def _trigger_for(values: RunSetupValues, stage: str, mode: str) -> str:
    if mode != "simulate":
        return ""
    if stage not in values.trigger:
        raise AuthoringError(
            expected=f"a trigger for the simulated stage '{stage}' (control, an input port name, or '')",
            found="absent", where=f"stages[{stage}].trigger",
            hint=f"add '{stage}' to RunSetupValues.trigger -- the engine never picks a trigger",
        )
    return values.trigger[stage]


def _livemeas_dict(livemeas: LiveMeasSpec) -> dict:
    where = "outputs.livemeas"
    return {
        "name": livemeas.name,
        "cycle_slot_count": _require_setup_integer(livemeas.cycle_slot_count, key=f"{where}.cycle_slot_count"),
        "cycle_slot_size": _require_setup_integer(livemeas.cycle_slot_size, key=f"{where}.cycle_slot_size"),
        "bulk_slot_count": _require_setup_integer(livemeas.bulk_slot_count, key=f"{where}.bulk_slot_count"),
        "bulk_slot_size": _require_setup_integer(livemeas.bulk_slot_size, key=f"{where}.bulk_slot_size"),
    }



@dataclass(frozen=True, slots=True)
class SourceSpec:
    """One probed recording, plain data (design §3.3a) -- `sha256` is what
    the caller's probe pass actually read from the file (`SW-0412`),
    never recomputed here."""

    path: Path
    sha256: str
    codec: str = "mcap"


def _require_absolute(path: Path, *, where: str) -> str:
    if not path.is_absolute():
        raise InternalError(
            expected="an absolute path (ANL-SW-01 -- the engine expands nothing)",
            found=str(path), where=where,
            hint="resolve to an absolute path before calling emit_run_spec",
        )
    return str(path)


def _resolve_impl(impl_raw: str, *, stage: str, search: Sequence[Path]) -> dict:
    """`IMP-0003`: `stages[].impl` carries a resolved `{kind, path, pattern,
    search}` -- never a bare stem the engine would have to expand
    (`IMP-0079`). Bridges through today's `resolve_library`, exactly as
    `IMP-0003`'s own design note names, until `WP-21` re-homes probing to
    `resolve/probe.py` and this call is replaced by `IMP-0204`'s
    `Resolution`."""
    kind, _, stem = impl_raw.partition(":")
    if kind not in ("dll", "stubdll"):
        raise AuthoringError(
            expected="impl: dll:<stem> or stubdll:<stem> (stub: has no file to resolve)",
            found=impl_raw, where=f"stage '{stage}' impl",
            hint="only a real library has a path for the spec to carry",
        )
    lib_path = resolve_library(stem, search=search)
    return {
        "kind": kind, "path": _require_absolute(lib_path, where=f"stage '{stage}' impl.path"),
        "pattern": "{stem}.dll" if lib_path.suffix == ".dll" else f"{{stem}}{lib_path.suffix}",
        "search": [str(p) for p in search],
    }


def _compute_grid_step_ns(period_ns_by_stage: Mapping[str, int]) -> int:
    """Converts a fault's `after_tick` into a time window (`engine/bridge.py`,
    `_fault_mutations`) -- **never written into a run setup** (schema 2.0 has
    no grid). The GCD over every stage's declared (nonzero)
    `period_ns` -- computed here, so `simcore` never derives it
    (`ANL-SW-02` greps the engine for `gcd`). A period not an integer
    multiple of the result is an emit-time error naming both, same
    discipline `graph/pipeline.py::_compute_base_grid_ns` already established
    (ported, not shared, since `runspec/` must not import `graph/`)."""
    periods = [p for p in period_ns_by_stage.values() if p > 0]
    if not periods:
        return 0
    step_ns = reduce(gcd, periods)
    for stage, period in period_ns_by_stage.items():
        if period > 0 and period % step_ns != 0:
            raise InternalError(
                expected=f"period_ns to be an integer multiple of the grid step ({step_ns} ns)",
                found=f"stage '{stage}' period_ns={period}", where="emit_run_spec grid (R-SIM-18)",
                hint=f"grid step {step_ns} ns is the GCD of every stage's declared period_ns",
            )
    return step_ns


def _port_dict(
    spec: PortSpec, *, stage: str, direction: str, record: str, values: RunSetupValues,
) -> dict:
    return {
        "name": spec.name, "dir": direction, "kind": "data", "proto_type": spec.proto_type,
        "record": record,
        "fixed_slots": spec.fixed_slots,
        "bulk": f"{stage}.{spec.name}" in values.bulk,
        "buffer_depth": _buffer_depth_for(values, stage, spec.name),
    }


def _record_verb_for(stage: str, port_name: str, record_policy: Mapping[str, Mapping[str, str]]) -> str:
    """`IMP-0009`: every port carries a concrete `record` value at emit time
    -- an exact entry wins, else `"*"`, else the closed default `full`,
    same precedence `graph/pipeline.py::record_policy_for` already
    establishes (ported here so the ENGINE never holds this table)."""
    stage_policy = record_policy.get(stage, {})
    if port_name in stage_policy:
        return stage_policy[port_name]
    if "*" in stage_policy:
        return stage_policy["*"]
    return "full"


def unresolved(spec: RunSpec) -> list[str]:
    """`ANL-SW-01`'s mechanical form, run over an already-built spec: any
    string that is a reference (`self.`/`source.` prefix -- design §3.2,
    no reference grammar survives to the engine) or a relative `path`-named
    field. Returns every finding, dotted-key-path-prefixed; empty means the
    spec is clean. There is no "expression" case to check for -- the closed
    six-verb override vocabulary (`R-SIM-15`) cannot *produce* an
    expression, so nothing here can ever construct one to catch."""
    findings: list[str] = []

    def _walk(node: object, where: str) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                child_where = f"{where}.{key}"
                if key in ("path", "search") and isinstance(value, str):
                    # An empty path is the closed-vocabulary sentinel for
                    # "no file" (a measured/off stage's `ImplRef`, same
                    # literal shape `BuildAbi02RunSpecJson`'s own `meas`
                    # stage fixture uses in
                    # tests/integration/test_ut_abi_writer_and_resolver.cpp)
                    # -- never a relative-path authoring mistake.
                    if value and not Path(value).is_absolute():
                        findings.append(f"{child_where}: relative path {value!r}")
                if isinstance(value, str) and (value.startswith("self.") or value.startswith("source.")):
                    findings.append(f"{child_where}: unresolved reference {value!r}")
                _walk(value, child_where)
        elif isinstance(node, (list, tuple)):
            for i, value in enumerate(node):
                _walk(value, f"{where}[{i}]")

    _walk(spec.data, "spec")
    return findings


def emit_run_spec(
    resolved: ResolvedConfig,
    *,
    run_id: str,
    manifests: Mapping[str, ComponentManifest],
    setup_values: RunSetupValues,
    modes: Mapping[str, str] | None = None,
    search: Sequence[Path] = (),
    record_policy: Mapping[str, Mapping[str, str]] | None = None,
    overrides: Mapping[str, Mapping[str, Override]] | None = None,
    sources: Sequence[SourceSpec] = (),
    outputs: Mapping[str, object] | None = None,
    checkpoint: Mapping[str, object] | None = None,
    limits: Mapping[str, object] | None = None,
) -> RunSpec:
    """Builds the Resolved Run Spec from `resolved`'s `COMPOSITION` (units)
    and `CONNECTIONS` (wiring) layers plus every already-probed
    `manifests[unit_name]`. Raises `InternalError` unless `unresolved()`
    returns empty on the built spec -- an emitter that produces something
    unresolved is this module's own bug, never the caller's (`IMP-0001`).

    `setup_values` carries the `⊘` values and the per-stage and per-port
    choices no manifest holds (`RunSetupValues`); there is no default for
    any of them, and a missing one is an `AuthoringError` naming the key."""
    modes = modes or {}
    record_policy = record_policy or {}
    overrides = overrides or {}
    outputs = dict(outputs or {})
    if setup_values.livemeas is not None:
        outputs["livemeas"] = _livemeas_dict(setup_values.livemeas)
    checkpoint = dict(checkpoint or {})
    limits = {"exec_timeout_ms": 250, "severity_exit": "error", **(limits or {})}
    readiness_limit_steps = _require_setup_integer(setup_values.readiness_limit_steps, key="readiness_limit_steps")
    fallback_max_gap = _require_setup_integer(setup_values.fallback_max_gap, key="fallback_max_gap")

    units = resolved.resolved.get(FileKind.COMPOSITION, {}).get("units")
    units_list = list(units.value) if units is not None else []
    wiring = resolved.resolved.get(FileKind.CONNECTIONS, {}).get("wiring")
    wiring_list = list(wiring.value) if wiring is not None else []

    inputs_by_stage: dict[str, list[dict]] = {u["name"]: [] for u in units_list}
    for edge in wiring_list:
        stage, port, producer_ref = edge["stage"], edge["port"], edge["from"]
        producer, _, producer_port = producer_ref.partition(".")
        inputs_by_stage.setdefault(stage, []).append({
            "port": port, "producer": producer, "producer_port": producer_port,  # IMP-0007
            "previous_cycle": f"{stage}.{port}" in setup_values.previous_cycle,
        })

    stages: list[dict] = []
    for unit in units_list:
        name = unit["name"]
        manifest = manifests[name]
        mode = modes.get(name, "simulate")
        ports = [
            _port_dict(
                p, stage=name, direction="pro", record=_record_verb_for(name, p.name, record_policy),
                values=setup_values,
            )
            for p in manifest.outputs
        ] + [
            _port_dict(
                p, stage=name, direction="req", record=_record_verb_for(name, p.name, record_policy),
                values=setup_values,
            )
            for p in manifest.inputs
        ]
        stages.append({
            "name": name, "mode": mode,
            "impl": _resolve_impl(unit["impl"], stage=name, search=search),  # IMP-0003
            "trigger": _trigger_for(setup_values, name, mode),
            "clock_period_ns": manifest.period_ns, "abi_version": manifest.abi_version,
            "config_bundle_sha256": manifest.config_bundle_sha256,
            "ports": ports, "inputs": inputs_by_stage.get(name, []),
        })

    mutations: list[dict] = []
    for stage, entries in overrides.items():
        for raw_address, override in entries.items():
            resolved_address = resolve_address(raw_address, stage=stage, where=f"stage '{stage}' overrides")
            mutations.append({
                "verb": override.verb.value,
                "address": {
                    "stage": resolved_address.stage, "port": resolved_address.port,
                    "path": list(resolved_address.path),
                    # `resolve_address` has carried `all_elements` in its own
                    # `ResolvedAddress` since IMP-0008 (WP-05) -- this dict
                    # never spelled it out to the wire until now (WP-11's own
                    # found gap, closed here rather than left a second time,
                    # `simcore::MutationAddress`'s twin field).
                    "index": "*" if resolved_address.all_elements else resolved_address.index,
                },
                "operands": [override.value] if override.value is not None else [],
                "window_ns": [0, None],
            })

    data: dict[str, object] = {
        "schema": RUN_SPEC_SCHEMA,
        "run_id": run_id,
        "spec_sha256": "",  # filled by canon.write_run_spec
        "sources": [
            {
                "path": _require_absolute(s.path, where="sources[].path"), "sha256": s.sha256,  # IMP-0412
                "codec": s.codec, "ingest": [], "absent": [],  # IMP-0011 -- WP-12 not landed yet
            }
            for s in sources
        ],
        "stages": stages,
        "mutations": mutations,  # IMP-0008's payoff
        "coherence_verdict": "unknown",  # SI-12 not landed yet
        "outputs": outputs,
        "checkpoint": checkpoint,
        "limits": limits,
        "readiness_limit_steps": readiness_limit_steps,
        "fallback_max_gap": fallback_max_gap,
    }

    spec = RunSpec(data=data)
    validate_run_spec(spec)
    findings = unresolved(spec)
    if findings:
        raise InternalError(
            expected="unresolved(spec) == [] (IMP-0001)", found=f"{len(findings)} unresolved: {findings[:5]}",
            where="adas_sim.runspec.emit.emit_run_spec",
            hint="this is an emitter bug -- every reference/relative path must be resolved before emit returns",
        )
    return spec
