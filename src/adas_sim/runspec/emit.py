# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`emit_run_spec` (`SW-0001`, design §3.5) -- the seam's own producer.
Takes `config.ResolvedConfig` (`WP-04`) plus whatever a caller has already
PROBED as plain data (`ComponentManifest` per unit, a content hash per
source, design §3.3a) and returns a `RunSpec` with every reference
resolved, every path absolute, every port carrying a concrete `record`/
`sampling`/`on_missing` -- **"if the engine has to decide something the
configuration layer could have decided, the spec is missing a field"**
(design §3.3, the one rule this module exists to keep).

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
never guessed. `coherence` needs `SI-12`, also not built -- it emits
`{"verdict": "unknown", ...}`, an explicit non-answer (`R-SIM-25`,
`NR-SIM-4`), never a plausible `"normal"`.
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

#: `SW-0005` -- the one schema string `LoadRunSpec` accepts today.
RUN_SPEC_SCHEMA = "adas.sim.runspec/1.0"

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

#: `IMP-0010`'s own fallback when a proto_type has no declared default --
#: hold-last-value is this framework's own convention everywhere else
#: (`R-SIM-18`'s "held" semantics), so it is not an arbitrary guess.
_DEFAULT_SAMPLING = "latest_at_or_before"
_DEFAULT_ON_MISSING = "hold"


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
    """`IMP-0006`: the GCD over every stage's declared (nonzero)
    `period_ns` -- computed here, once, so `simcore` never derives it
    (`ANL-SW-02` greps the engine for `gcd`). A period not an integer
    multiple of the result is an emit-time error naming both, same
    discipline `graph/build.py::_compute_base_grid_ns` already established
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


def _topological_order(stage_names: Sequence[str], depends_on: Mapping[str, set[str]]) -> tuple[str, ...]:
    """`SW-0072`: precomputed once at emit, never re-derived by the engine.
    Kahn's algorithm; a cycle is an emit-time error naming every stage
    still blocked (never a silent partial order)."""
    remaining = {name: set(depends_on.get(name, ())) for name in stage_names}
    ordered: list[str] = []
    while remaining:
        ready = sorted(name for name, deps in remaining.items() if not deps)
        if not ready:
            raise AuthoringError(
                expected="a wiring graph with no cycle", found=f"still blocked: {sorted(remaining)}",
                where="emit_run_spec order (SW-0072)", hint="a stage cannot (directly or transitively) depend on itself",
            )
        for name in ready:
            del remaining[name]
        for deps in remaining.values():
            deps.difference_update(ready)
        ordered.extend(ready)
    return tuple(ordered)


def _port_dict(
    spec: PortSpec, *, direction: str, record: str, sampling_defaults: Mapping[str, str],
    on_missing_defaults: Mapping[str, str],
) -> dict:
    return {
        "name": spec.name, "dir": direction, "kind": "data", "proto_type": spec.proto_type,
        "record": record,
        "sampling": sampling_defaults.get(spec.proto_type, _DEFAULT_SAMPLING),  # IMP-0010
        "on_missing": on_missing_defaults.get(spec.proto_type, _DEFAULT_ON_MISSING),  # IMP-0010
        "fixed_slots": spec.fixed_slots,
    }


def _record_verb_for(stage: str, port_name: str, record_policy: Mapping[str, Mapping[str, str]]) -> str:
    """`IMP-0009`: every port carries a concrete `record` value at emit time
    -- an exact entry wins, else `"*"`, else the closed default `full`,
    same precedence `graph/build.py::record_policy_for` already
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
                    if not Path(value).is_absolute():
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
    modes: Mapping[str, str] | None = None,
    search: Sequence[Path] = (),
    record_policy: Mapping[str, Mapping[str, str]] | None = None,
    sampling_defaults: Mapping[str, str] | None = None,
    on_missing_defaults: Mapping[str, str] | None = None,
    overrides: Mapping[str, Mapping[str, Override]] | None = None,
    sources: Sequence[SourceSpec] = (),
    outputs: Mapping[str, object] | None = None,
    limits: Mapping[str, object] | None = None,
    diagnostics: Mapping[str, object] | None = None,
) -> RunSpec:
    """Builds the Resolved Run Spec from `resolved`'s `COMPOSITION` (units)
    and `CONNECTIONS` (wiring) layers plus every already-probed
    `manifests[unit_name]`. Raises `InternalError` unless `unresolved()`
    returns empty on the built spec -- an emitter that produces something
    unresolved is this module's own bug, never the caller's (`IMP-0001`)."""
    modes = modes or {}
    record_policy = record_policy or {}
    sampling_defaults = sampling_defaults or {}
    on_missing_defaults = on_missing_defaults or {}
    overrides = overrides or {}
    outputs = dict(outputs or {})
    limits = {"exec_timeout_ms": 250, "severity_exit": "error", **(limits or {})}
    diagnostics = {"cycle_trace": False, "graph_dump": False, **(diagnostics or {})}

    units = resolved.resolved.get(FileKind.COMPOSITION, {}).get("units")
    units_list = list(units.value) if units is not None else []
    wiring = resolved.resolved.get(FileKind.CONNECTIONS, {}).get("wiring")
    wiring_list = list(wiring.value) if wiring is not None else []

    depends_on: dict[str, set[str]] = {u["name"]: set() for u in units_list}
    inputs_by_stage: dict[str, list[dict]] = {u["name"]: [] for u in units_list}
    for edge in wiring_list:
        stage, port, producer_ref = edge["stage"], edge["port"], edge["from"]
        producer, _, producer_port = producer_ref.partition(".")
        depends_on.setdefault(stage, set()).add(producer)
        inputs_by_stage.setdefault(stage, []).append({
            "port": port, "producer": producer, "producer_port": producer_port,  # IMP-0007
            "delay_steps": int(edge.get("delay_steps", 0)),
        })

    stages: list[dict] = []
    period_ns_by_stage: dict[str, int] = {}
    for unit in units_list:
        name = unit["name"]
        manifest = manifests[name]
        period_ns_by_stage[name] = manifest.period_ns
        ports = [
            _port_dict(
                p, direction="pro", record=_record_verb_for(name, p.name, record_policy),
                sampling_defaults=sampling_defaults, on_missing_defaults=on_missing_defaults,
            )
            for p in manifest.outputs
        ] + [
            _port_dict(
                p, direction="req", record=_record_verb_for(name, p.name, record_policy),
                sampling_defaults=sampling_defaults, on_missing_defaults=on_missing_defaults,
            )
            for p in manifest.inputs
        ]
        stages.append({
            "name": name, "mode": modes.get(name, "simulate"),
            "impl": _resolve_impl(unit["impl"], stage=name, search=search),  # IMP-0003
            "period_ns": manifest.period_ns, "abi_version": manifest.abi_version,
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
                    "path": list(resolved_address.path), "index": resolved_address.index,
                },
                "operands": [override.value] if override.value is not None else [],
                "window_ns": [0, None],
            })

    data: dict[str, object] = {
        "schema": RUN_SPEC_SCHEMA,
        "run_id": run_id,
        "spec_sha256": "",  # filled by canon.write_run_spec
        "grid": {"step_ns": _compute_grid_step_ns(period_ns_by_stage)},  # IMP-0006
        "sources": [
            {
                "path": _require_absolute(s.path, where="sources[].path"), "sha256": s.sha256,  # IMP-0412
                "codec": s.codec, "ingest": [], "absent": [],  # IMP-0011 -- WP-12 not landed yet
            }
            for s in sources
        ],
        "stages": stages,
        "mutations": mutations,  # IMP-0008's payoff
        "order": list(_topological_order([u["name"] for u in units_list], depends_on)),
        "coherence": {"verdict": "unknown", "stale": [], "waiver": None},  # SI-12 not landed yet
        "outputs": outputs,
        "limits": limits,
        "diagnostics": diagnostics,
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
