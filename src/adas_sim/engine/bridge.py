# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-15b` (`IMP-0422`, `SW-0013`) -- the ONE bridge every live Python
caller of the retiring `core/resim.py`/`resolve/component.py` execution
path rewires onto: builds a Resolved Run Spec (`IF-09`) from an already-
loaded `Pipeline`, then drives `simcore`/`simengine`'s engine to execute it
(`R-SIM-4`/`R-SIM-11`/`R-SIM-16`).

**Integration shape, decided here (WP-15b's own open call):** subprocess
against the `simengine` executable, for every call site -- not a per-call-
site choice. `simcore` (`src/simcore/CMakeLists.txt`) is built as a STATIC
library only; no CMake target anywhere in this module produces a shared
object/DLL exporting `simcore/abi/simcore.h`'s C ABI (`simEngineCreate` et
al.), so an in-process `ctypes` binding against it has no artifact to load
-- unlike `resolve/component.py::CtypesSilComponent`, which binds a
per-COMPONENT `.dll`/`.so` that genuinely is built shared. Adding a new
shared-library CMake target would be a build-machinery change (`R-BUILD-6`)
outside this package's own declared `Files:` scope (the four call sites
plus one shared bridge module) -- if that target is added later, only
`run_engine` below needs a second implementation; every call site stays
unchanged, since none of them ever touch `simengine`.exe`/`ctypes` directly.

`orchestrate/worker.py` already subprocesses one `simengine`/child per
recording (`R-SIM-19`), so this shape costs it nothing new. For the other
three call sites this is one more process per resim -- accepted, since
`simengine`'s own startup is the same `simEngineCreate` cost either shape
would pay, and there is no shared-library artifact to bind in-process to
avoid it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from adas_sim.diagnostics.errors import EnvironmentError_, InternalError
from adas_sim.graph.build import Pipeline, _split_ref
from adas_sim.resolve.component import ComponentManifest
from adas_sim.runspec.address import resolve_address
from adas_sim.runspec.canon import RunSpec, write_run_spec
from adas_sim.runspec.emit import (
    RUN_SPEC_SCHEMA,
    _compute_grid_step_ns,
    _port_dict,
    _record_verb_for,
    _topological_order,
    unresolved,
    validate_run_spec,
)

#: `simcore::ExitCode` (`errors.hpp`/`docs/v2/errors.yaml`)/`SimExitCode`
#: (`abi/simcore.h`) mirrored on the Python side -- the taxonomy this
#: bridge's own `EngineRunResult.exit_code` is always a member of, same
#: reasoning `CtypesSilComponent`'s own `ADAS_SIL_ABI_VERSION` constant
#: gives for not re-deriving a published contract.
SIM_EXIT_OK = 0
SIM_EXIT_CONFIG = 2
SIM_EXIT_COHERENCE = 3
SIM_EXIT_MODULE = 4
SIM_EXIT_INPUT = 5
SIM_EXIT_INFRA = 6
SIM_EXIT_TIMEOUT = 7
SIM_EXIT_CRASH = 8

_MODULE_ROOT = Path(__file__).resolve().parents[3]  # modules/sim/

#: Candidate build directories for the `simengine` executable, most
#: specific platform first -- same shape `scripts/prove_equal.py`'s own
#: `SIMCORE_TESTS_CANDIDATES` uses for the gtest binary, applied here to
#: the product binary this bridge actually drives.
_SIMENGINE_CANDIDATES = (
    _MODULE_ROOT / "build-gtest-vs2026" / "src" / "simengine" / "Release" / "simengine.exe",
    _MODULE_ROOT / "build-gtest-vs2026" / "src" / "simengine" / "Debug" / "simengine.exe",
    _MODULE_ROOT / "build-gtest-ubuntu_gcc" / "src" / "simengine" / "simengine",
)


def resolve_simengine_executable(search: Sequence[Path] = ()) -> Path:
    """The one place a `simengine` binary path is discovered (mirrors
    `resolve.library.resolve_library`'s own single-discovery-point
    discipline, `P-5`). `search` is checked first (repeatable, most
    specific caller-supplied directories), then the module's own known
    build directories."""
    for directory in search:
        for name in ("simengine.exe", "simengine"):
            candidate = directory / name
            if candidate.is_file():
                return candidate
    for candidate in _SIMENGINE_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise EnvironmentError_(
        expected="a built simengine executable",
        found="none of the known build directories contain one",
        where=", ".join(str(c) for c in _SIMENGINE_CANDIDATES),
        hint="build the simengine target for this platform "
             "(scripts/build.py -t sil -p <platform>), or pass search=[...] "
             "naming the directory that holds it",
    )


def _run_subprocess(cmd: list[str]) -> subprocess.CompletedProcess:
    """A Windows `.exe` is runnable directly under WSL2 interop; if that
    fails (exec format), retry through `cmd.exe` -- the same proven,
    headless-binary-only channel `scripts/prove_equal.py::_run` already
    uses (project memory: WSL2 interop via cmd.exe/powershell.exe is safe
    for a non-GUI binary; `simengine` opens no window)."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    except OSError:
        win_cmd = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        return subprocess.run(["cmd.exe", "/c", win_cmd], capture_output=True, text=True, encoding="utf-8")


@dataclass(frozen=True, slots=True)
class EngineRunResult:
    """One `simengine` invocation's outcome -- `exit_code` is always a
    `SIM_EXIT_*` value (parsed from the process's own return code, which
    `main.cpp` documents as `simEngineRun`'s `SimExitCode`, `SW-0148`,
    never a raw platform code). `stdout`/`stderr` are kept for a caller
    that wants to surface `simengine`'s own diagnostics on failure."""

    exit_code: int
    ok: bool
    stdout: str
    stderr: str
    output_path: Path | None


def run_engine(
    spec_path: Path, *, config_path: Path | None = None, exec_timeout_ms: int = 0,
    simengine_path: Path | None = None, search: Sequence[Path] = (), output_path: Path | None = None,
) -> EngineRunResult:
    """Runs an already-written Run Spec JSON to completion through the real
    `simengine` executable (`simEngineCreate`/`simEngineRun`/
    `simEngineDestroy`, `IMP-0144`) -- the ONE place any Python call site
    invokes the engine (`R-SIM-16`'s "one engine" applied at the process
    boundary: a GUI Run, `sim resim`, `sim batch`'s worker and `check`'s
    `expect:` evaluation must never silently diverge on how they drive the
    same spec)."""
    binary = simengine_path if simengine_path is not None else resolve_simengine_executable(search)
    cmd = [str(binary), str(spec_path)]
    if config_path is not None:
        cmd += ["--config", str(config_path)]
    if exec_timeout_ms > 0:
        cmd += ["--timeout-ms", str(exec_timeout_ms)]
    proc = _run_subprocess(cmd)
    return EngineRunResult(
        exit_code=proc.returncode, ok=proc.returncode == SIM_EXIT_OK,
        stdout=proc.stdout or "", stderr=proc.stderr or "", output_path=output_path,
    )


def _stage_impl_dict(pipeline: Pipeline, stage) -> dict:
    """`SpecStage.impl` (`runspec.hpp`'s `ImplRef`) from a stage already
    resolved by `Pipeline.load` -- unlike `runspec.emit._resolve_impl`,
    the library path is already known (`pipeline.library_paths`), so this
    never calls `resolve_library` a second time. `measured`/`off` stages
    (and any `components=`-injected test stage with no file on disk) carry
    an empty `ImplRef`, mirroring `BuildAbi02RunSpecJson`'s own `meas`
    stage in `tests/integration/test_ut_abi_writer_and_resolver.cpp`."""
    if stage.impl is None:
        return {"kind": "", "path": "", "pattern": "", "search": []}
    kind, _, _stem = stage.impl.partition(":")
    lib_path = pipeline.library_paths.get(stage.name)
    if kind not in ("dll", "stubdll") or lib_path is None:
        return {"kind": "", "path": "", "pattern": "", "search": []}
    return {
        "kind": kind, "path": str(lib_path),
        "pattern": "{stem}.dll" if lib_path.suffix == ".dll" else f"{{stem}}{lib_path.suffix}",
        "search": [],
    }


def pipeline_to_run_spec(
    pipeline: Pipeline, *, run_id: str, recording_path: Path, recording_sha256: str = "",
    output_path: Path | None = None, exec_timeout_ms: int = 250,
) -> RunSpec:
    """Builds a Resolved Run Spec (`IF-09`) directly from an already-loaded
    `Pipeline` -- the Python-object twin of `runspec.emit.emit_run_spec`,
    which instead builds one from `config.ResolvedConfig`'s COMPOSITION/
    CONNECTIONS layers (`WP-05`'s own scope, never wired to a live
    `Pipeline`). Reuses `emit.py`'s already-proven per-port/grid/order
    helpers rather than a second implementation of them (`R-BUILD`'s
    no-second-implementation principle applied at function granularity).

    `output_path=None` means no recording output declared -- the engine
    still runs, but nothing downstream can read results back (`SW-0013`'s
    callers always pass one; see each call site for why)."""
    manifests: dict[str, ComponentManifest] = {stage.name: pipeline.manifest_for(stage.name) for stage in pipeline.stages}
    period_ns_by_stage = {name: m.period_ns for name, m in manifests.items()}

    depends_on: dict[str, set[str]] = {stage.name: set() for stage in pipeline.stages}
    stages: list[dict] = []
    for stage in pipeline.stages:
        manifest = manifests[stage.name]
        inputs: list[dict] = []
        for port, ref in stage.inputs.items():
            producer, producer_port = _split_ref(ref)
            if producer != "source":
                depends_on[stage.name].add(producer)
            inputs.append({"port": port, "producer": producer, "producer_port": producer_port, "delay_steps": 0})
        ports = [
            _port_dict(p, direction="pro", record=_record_verb_for(stage.name, p.name, {}),
                       sampling_defaults={}, on_missing_defaults={})
            for p in manifest.outputs
        ] + [
            _port_dict(p, direction="req", record=_record_verb_for(stage.name, p.name, {}),
                       sampling_defaults={}, on_missing_defaults={})
            for p in manifest.inputs
        ]
        stages.append({
            "name": stage.name, "mode": stage.mode,
            "impl": _stage_impl_dict(pipeline, stage),
            "period_ns": manifest.period_ns, "abi_version": manifest.abi_version,
            "config_bundle_sha256": manifest.config_bundle_sha256,
            "ports": ports, "inputs": inputs,
        })

    mutations: list[dict] = []
    for stage in pipeline.stages:
        for raw_address, override in stage.overrides.items():
            resolved_address = resolve_address(raw_address, stage=stage.name, where=f"stage '{stage.name}' overrides")
            mutations.append({
                "verb": override.verb.value,
                "address": {
                    "stage": resolved_address.stage, "port": resolved_address.port,
                    "path": list(resolved_address.path),
                    "index": "*" if resolved_address.all_elements else resolved_address.index,
                },
                "operands": [override.value] if override.value is not None else [],
                "window_ns": [0, None],
            })

    outputs = {"path": str(output_path), "codec": "mcap"} if output_path is not None else {}

    data: dict[str, object] = {
        "schema": RUN_SPEC_SCHEMA,
        "run_id": run_id,
        "spec_sha256": "",
        "grid": {"step_ns": _compute_grid_step_ns(period_ns_by_stage)},
        "sources": [{
            "path": str(recording_path), "sha256": recording_sha256, "codec": "mcap",
            "ingest": [], "absent": [],  # WP-12's ingest-map parser not landed yet, same as emit_run_spec's own
        }],
        "stages": stages,
        "mutations": mutations,
        "order": list(_topological_order([s.name for s in pipeline.stages], depends_on)),
        "coherence": {"verdict": "unknown", "stale": [], "waiver": None},
        "outputs": outputs,
        "limits": {"exec_timeout_ms": exec_timeout_ms, "severity_exit": "error"},
        "diagnostics": {"cycle_trace": False, "graph_dump": False},
    }

    spec = RunSpec(data=data)
    validate_run_spec(spec)
    findings = unresolved(spec)
    if findings:
        raise InternalError(
            expected="unresolved(spec) == [] (mirrors emit_run_spec's own IMP-0001 check)",
            found=f"{len(findings)} unresolved: {findings[:5]}",
            where="adas_sim.engine.bridge.pipeline_to_run_spec",
            hint="a Pipeline field is not yet absolute/resolved before this call",
        )
    return spec


def run_pipeline_via_engine(
    pipeline: Pipeline, recording_path: Path, *, run_id: str, output_path: Path,
    config_path: Path | None = None, exec_timeout_ms: int = 250,
    spec_json_path: Path | None = None, simengine_path: Path | None = None, search: Sequence[Path] = (),
) -> EngineRunResult:
    """The one call every rewired call site makes: build the spec, write it
    (`runspec.canon.write_run_spec`, the same canonical form
    `runspec/manifest.py` already uses), run it through `simengine`, return
    the outcome. `spec_json_path` defaults to a sibling of `output_path`
    (`<output_path>.spec.json`) so a caller inspecting a failed run finds
    the exact spec that failed next to the (possibly partial) recording."""
    spec = pipeline_to_run_spec(
        pipeline, run_id=run_id, recording_path=recording_path, output_path=output_path,
        exec_timeout_ms=exec_timeout_ms,
    )
    spec_path = spec_json_path if spec_json_path is not None else output_path.with_suffix(output_path.suffix + ".spec.json")
    write_run_spec(spec, spec_path)
    return run_engine(
        spec_path, config_path=config_path, exec_timeout_ms=exec_timeout_ms,
        simengine_path=simengine_path, search=search, output_path=output_path,
    )
