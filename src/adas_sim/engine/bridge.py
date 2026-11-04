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
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from adas_sim.config.fault import FaultVerb
from adas_sim.config.paths import sim_root
from adas_sim.diagnostics.errors import EnvironmentError_, InternalError
from adas_sim.graph.pipeline import Pipeline, _split_ref
from adas_sim.io.base import TopicInfo, group_by_log_time
from adas_sim.launcher.command import command_line
from adas_sim.plugins.registry import reader_for
from adas_sim.resolve.component import ComponentManifest
from adas_sim.runspec.address import resolve_address
from adas_sim.runspec.canon import RunSpec, write_run_spec
from adas_sim.runspec.emit import (
    RUN_SPEC_SCHEMA,
    RunSetupValues,
    _compute_grid_step_ns,
    _livemeas_dict,
    _port_dict,
    _record_verb_for,
    _require_setup_integer,
    _trigger_for,
    unresolved,
    validate_run_spec,
)

#: `simcore::ExitCode` (`errors.hpp`/`docs/v2/errors.yaml`)/`SimExitCode`
#: (`abi/simcore.h`) mirrored on the Python side -- the taxonomy this
#: bridge's own `EngineRunResult.exit_code` is always a member of, same
#: reasoning `CtypesSilComponent`'s own `ADAS_SIL_ABI_VERSION` constant
#: gives for not re-deriving a published contract.
#: The recording format `engine.bridge`'s own callers write to when they
#: have no other preference (a scratch/intermediate output, never a
#: user-facing artifact) -- named here, not in `check/runner.py`
#: (`UT-A4-11`/`R-SIM-14`: `check` is one of `test_a4_boundaries.py`'s own
#: `_NO_FORMAT_PACKAGES`, so no format token may appear in that module's
#: own source text; `engine/` is not restricted).
DEFAULT_RECORDING_EXT = ".mcap"

SIM_EXIT_OK = 0
SIM_EXIT_CONFIG = 2
SIM_EXIT_COHERENCE = 3
SIM_EXIT_MODULE = 4
SIM_EXIT_INPUT = 5
SIM_EXIT_INFRA = 6
SIM_EXIT_TIMEOUT = 7
SIM_EXIT_CRASH = 8

_MODULE_ROOT = sim_root()

#: Candidate build directories for the `simengine` executable, most
#: specific platform first -- same shape `scripts/prove_equal.py`'s own
#: `SIMCORE_TESTS_CANDIDATES` uses for the gtest binary, applied here to
#: the product binary this bridge actually drives.
_SIMENGINE_CANDIDATES = (
    _MODULE_ROOT / "conan_workarea" / "build-sil-vs2026" / "src" / "simengine" / "Release" / "simengine.exe",
    _MODULE_ROOT / "conan_workarea" / "build-gtest-vs2026" / "src" / "simengine" / "Release" / "simengine.exe",
    _MODULE_ROOT / "conan_workarea" / "build-gtest-vs2026" / "src" / "simengine" / "Debug" / "simengine.exe",
    _MODULE_ROOT / "conan_workarea" / "build-sil-ubuntu_gcc" / "src" / "simengine" / "simengine",
    _MODULE_ROOT / "conan_workarea" / "build-gtest-ubuntu_gcc" / "src" / "simengine" / "simengine",
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


#: Wall-clock ceiling on a whole `simengine` invocation, independent of
#: `exec_timeout_ms` (which bounds a single `exec()` cycle *inside* the
#: engine, R-SIM-19). Without this, anything that blocks the process
#: before/after the engine's own per-cycle watchdog can see it --
#: a Windows WER dialog on a bad image, a `cmd.exe` fallback that never
#: returns, an OS-level deadlock on startup -- hangs `subprocess.run`
#: forever with nothing to kill it (found live, 2026-08-23: a full test
#: run stalled 600s+ with no engine process left running afterward,
#: i.e. unrelated to any single test's own assertions). `fail`/`crash`/
#: `timeout` stay three distinct outcomes (R-SIM-19): this path reports
#: `SIM_EXIT_TIMEOUT`, never `SIM_EXIT_CRASH`.
_DEFAULT_PROCESS_TIMEOUT_S = 120


def _run_subprocess(cmd: list[str], *, timeout_s: float = _DEFAULT_PROCESS_TIMEOUT_S) -> subprocess.CompletedProcess:
    """A Windows `.exe` is runnable directly under WSL2 interop; if that
    fails (exec format), retry through `cmd.exe` -- the same proven,
    headless-binary-only channel `scripts/prove_equal.py::_run` already
    uses (project memory: WSL2 interop via cmd.exe/powershell.exe is safe
    for a non-GUI binary; `simengine` opens no window). `timeout_s` bounds
    both attempts -- a `TimeoutExpired` propagates to `run_engine`, which
    turns it into a real `SIM_EXIT_TIMEOUT` result instead of an indefinite
    hang."""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_s
        )
    except OSError:
        win_cmd = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        return subprocess.run(
            ["cmd.exe", "/c", win_cmd], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout_s
        )


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
    #: `IMP-0216` (`SW-0216`, `IT-16`): `runspec/canon.py::write_run_spec`'s
    #: own returned hash, attached by `run_pipeline_via_engine` -- the one
    #: caller that both writes a spec and returns a result. `""` for a
    #: caller of `run_engine` directly against an already-written spec
    #: path, which has no spec object to hash from.
    spec_sha256: str = ""


def run_engine(
    spec_path: Path, *, supervise: bool = False, attempt_timeout_ms: int | None = None, restart_on_crash: int = 0,
    threads: int = 1, wait_for_attach: bool = False,
    simengine_path: Path | None = None, search: Sequence[Path] = (), output_path: Path | None = None,
    process_timeout_s: float = _DEFAULT_PROCESS_TIMEOUT_S,
) -> EngineRunResult:
    """Runs an already-written Run Spec JSON to completion through the real
    `simengine` executable (`simEngineCreate`/`simEngineRun`/
    `simEngineDestroy`, `IMP-0144`) -- the ONE place any Python call site
    invokes the engine (`R-SIM-16`'s "one engine" applied at the process
    boundary: a GUI Run, `sim resim`, `sim batch`'s worker and `check`'s
    `expect:` evaluation must never silently diverge on how they drive the
    same spec). `process_timeout_s` is the whole-process wall clock
    (distinct from `exec_timeout_ms`'s per-cycle bound inside the engine,
    R-SIM-19) -- a process that never returns at all (never a plausible
    `fail`/`crash` result) reports `SIM_EXIT_TIMEOUT` here instead of
    hanging the caller forever.

    `supervise` starts the batch face (`--supervise`), which needs `attempt_timeout_ms`, the deadline of one attempt: a supervised
    start without it raises naming it, before any process starts (`SYS-0090`, `SYS-0109`; no default exists). The command line is
    `launcher.command.command_line`'s. The engine takes no configuration path and no call timeout: the setup carries the bundle
    beside each library and `limits.exec_timeout_ms` (`D31 (1)`)."""
    binary = simengine_path if simengine_path is not None else resolve_simengine_executable(search)
    cmd = command_line(
        binary, spec_path, "batch" if supervise else "developer", deadline_ms=attempt_timeout_ms, threads=threads,
        restart_on_crash=restart_on_crash, wait_for_attach=wait_for_attach,
    )
    try:
        proc = _run_subprocess(cmd, timeout_s=process_timeout_s)
    except subprocess.TimeoutExpired as exc:
        return EngineRunResult(
            exit_code=SIM_EXIT_TIMEOUT, ok=False,
            stdout=(exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=f"simengine did not return within process_timeout_s={process_timeout_s}s -- "
                   f"never a plausible fail/crash result (R-SIM-19): {' '.join(cmd)}",
            output_path=output_path,
        )
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
    a `kind: "dll"`, `path: ""` `ImplRef` -- the schema's `kind` enum is
    `["dll", "stubdll"]` with no empty-string member, so an empty `path`
    (never an empty `kind`) is what "no real file" means, exactly the
    literal fixture `BuildAbi02RunSpecJson`'s own `meas` stage in
    `tests/integration/test_ut_abi_writer_and_resolver.cpp` uses
    (`"impl": {"kind": "dll", "path": "", ...}`)."""
    empty = {"kind": "dll", "path": ""}
    if stage.impl is None:
        return empty
    kind, _, _stem = stage.impl.partition(":")
    lib_path = pipeline.library_paths.get(stage.name)
    if kind not in ("dll", "stubdll") or lib_path is None:
        return empty
    return {"kind": kind, "path": str(lib_path)}


def _fault_mutations(faults: Sequence, *, grid_step_ns: int) -> list[dict]:
    """`WP-15b` follow-on (found attempting the package, closed here):
    `scenario.run.faults` (`config/fault.py::Fault`) has no RunSpec array of
    its own -- `simcore`'s own `mutate::FaultSpec`/`ApplyFault` exist
    (`mutate/faults.cpp`) but nothing wires a `faults[]` key into the wire
    format or the engine's cycle loop yet, a real design decision named as
    a follow-on rather than guessed at during `WP-15b` itself.

    **What actually closes the found gap today:** `FaultVerb.CORRUPT` is
    exactly `OverrideVerb.CONST` applied to the STIMULUS (`config/fault.py`'s
    own docstring: "corrupt reuses the override CONST verb's own byte-level
    mutation") -- and the mutation vocabulary, its `window_ns` scoping and
    its consumer-side application against a `source.<port>`-addressed value
    (`cycle_loop.cpp`'s own `producer`/`bare` match, `R-SIM-21`'s reserved
    `source.<port>` keyword) already exist and are already wired. So a
    `corrupt` fault is translated into an equivalent `const` mutation here,
    address `{stage: "source", port: <fault's own port>}` -- reusing tested
    infrastructure end to end rather than adding a second, unwired
    mechanism. `drop`/`stale`/`delay`/`invalidate` have no equivalent verb
    in the closed six (`R-SIM-15`) -- each is a metadata flip `simcore`'s
    `ApplyFault` already knows how to do, but with no wire format to reach
    it yet -- so a fault of one of those verbs is a named, loud
    `InternalError` rather than a silent no-op (`R-SIM-25`), until a real
    `faults[]` RunSpec array + cycle-loop wiring lands as its own follow-on.

    **Window translation:** `from_s`/`to_s` (inclusive both ends, `Fault.
    active_at`) become `window_ns = [round(from_s*1e9), round(to_s*1e9)+1]`
    -- `+1` because `simcore::mutate::InWindow` is half-open
    (`[start_ns, end_ns)`, `IMP-0108`), so without it a fault active exactly
    AT `to_s` would stop one nanosecond early. `after_tick` (open-ended)
    becomes `[after_tick * grid_step_ns, None]` -- the same base grid
    `Pipeline._tick_index` counts against (`R-SIM-18`), already computed
    from the stages' own periods and used only for this window -- schema 2.0
    has no grid, so it is never written into the setup."""
    mutations: list[dict] = []
    for fault in faults:
        if fault.verb is not FaultVerb.CORRUPT:
            raise InternalError(
                expected="a run.faults verb this bridge can translate into a RunSpec mutation (today: corrupt only)",
                found=f"verb={fault.verb.value!r} address={fault.address!r}",
                where="adas_sim.engine.bridge._fault_mutations",
                hint="drop/stale/delay/invalidate have no equivalent in the closed six-verb mutation "
                     "vocabulary yet (WP-15b's own named follow-on, simcore::mutate::FaultSpec exists "
                     "but no RunSpec faults[] array reaches it) -- only corrupt maps onto const",
            )
        resolved_address = resolve_address(fault.address, stage="source", where=f"run.faults address {fault.address!r}")
        if fault.after_tick is not None:
            if grid_step_ns <= 0:
                raise InternalError(
                    expected="a positive grid.step_ns to convert run.faults[].after_tick into a window_ns",
                    found=f"grid_step_ns={grid_step_ns}", where="adas_sim.engine.bridge._fault_mutations",
                    hint="no stage declares a period_ns > 0 for this pipeline",
                )
            window_ns = [fault.after_tick * grid_step_ns, None]
        else:
            window_ns = [round(fault.from_s * 1_000_000_000), round(fault.to_s * 1_000_000_000) + 1]
        mutations.append({
            "verb": "const",
            "address": {
                "stage": resolved_address.stage, "port": resolved_address.port,
                "path": list(resolved_address.path),
                "index": "*" if resolved_address.all_elements else resolved_address.index,
            },
            "operands": [fault.value],
            "window_ns": window_ns,
        })
    return mutations


def _ingest_for(recording_path: Path) -> dict[str, list]:
    """The `ingest`/`absent` half of a `sources[]` entry, resolved for THIS
    recording (`R-SIM-23`, `WP-12`).

    **This function is the join `WP-12` was missing.** `ingest/map.py`'s
    parser has been real and tested since that package landed, and
    `simcore/io/translate.cpp`'s apply half since `IMP-0032` — but nothing
    connected them: this dict was hard-coded to `{"ingest": [], "absent": []}`
    with a comment saying the parser had not landed, long after it had. The
    consequence was not a missing feature but a wrong answer: a recording in
    a foreign topic vocabulary resimmed to completion, exit 0, feeding its
    module an empty payload on every tick, silently (`F-4`, measured
    2026-08-27 at 218 ticks).

    Which map applies is decided the way `IngestMap.matches` decides it —
    by the recording's own topics — never by filename or convention. A
    recording this framework produced matches no map and gets two empty
    lists, i.e. exactly the previous behaviour.

    Discovery failing is **not** this run's failure: a checkout with no
    `modules/*/sim/ingest` at all is the ordinary case for a deployed
    install, so it degrades to "no map" rather than raising. A map that
    exists but is malformed still raises out of `_parse_ingest_map`, which
    is where that error belongs.
    """
    from adas_sim.ingest.map import discover_ingest_maps

    try:
        reader = reader_for(recording_path)
    except Exception:  # noqa: BLE001 -- an unreadable recording fails later, with a better message
        return {"ingest": [], "absent": []}
    try:
        topics = list(reader.topics())
    finally:
        reader.close()

    applicable = [m for m in discover_ingest_maps() if m.matches(topics)]
    ingest: list[dict] = []
    absent: list[dict] = []
    for ingest_map in applicable:
        for provided in ingest_map.provides:
            ingest.append({
                # BOTH sides are topics, and that is the point. An ingest map
                # is authored in port-reference form (`source.gen_object_list`)
                # because that is what a pipeline wires; but a Resolved Run
                # Spec carries **no reference grammar** (`ANL-SW-01`,
                # design §3.2) and `unresolved()` refuses a `source.`-prefixed
                # string outright -- correctly, and it caught this on the
                # first real run. So the row is emitted topic -> topic, and
                # the engine derives the port name with the one transform it
                # already uses for every other topic (`TopicToPortName`).
                # Nothing new learns the reference grammar.
                "raw_topic": _port_name_to_topic(provided.topic),
                "port": _port_name_to_topic(provided.port),
                "origin": provided.origin.value,
                "proto_type": provided.proto_type,
                "factor": provided.factor,
                "offset": provided.offset,
            })
        for missing in ingest_map.absent:
            absent.append({"port": _port_name_to_topic(missing.port), "reason": missing.reason})
    return {"ingest": ingest, "absent": absent}


def pipeline_to_run_spec(
    pipeline: Pipeline, *, run_id: str, recording_path: Path, setup_values: RunSetupValues,
    recording_sha256: str = "", output_path: Path | None = None, exec_timeout_ms: int = 250,
    checkpoint_path: Path | None = None, coherence_verdict: str = "unknown",
) -> RunSpec:
    """Builds a Resolved Run Spec (`IF-09`) directly from an already-loaded
    `Pipeline` -- the Python-object twin of `runspec.emit.emit_run_spec`,
    which instead builds one from `config.ResolvedConfig`'s COMPOSITION/
    CONNECTIONS layers (`WP-05`'s own scope, never wired to a live
    `Pipeline`). Reuses `emit.py`'s already-proven per-port/grid/order
    helpers rather than a second implementation of them (`R-BUILD`'s
    no-second-implementation principle applied at function granularity).

    `setup_values` carries the `⊘` values and the per-stage triggers no
    pipeline file holds yet (`emit.RunSetupValues`); nothing here defaults
    any of them (`IMP-0051`).

    `output_path=None` means no recording output declared -- the engine
    still runs, but nothing downstream can read results back (`SW-0013`'s
    callers always pass one; see each call site for why).

    `checkpoint_path=None` (the default) omits the `checkpoint` key
    entirely, matching `load.cpp`'s own "absent key leaves `checkpoint.path`
    empty" -- checkpointing stays off unless a caller asks for it. When
    given, `simEngineCreate` writes a real `progress.json` there after every
    completed cycle (`SW-0119`, `src/simcore/runner/checkpoint.cpp`), which
    is what lets a crashed/timed-out run still report its last completed
    tick (`orchestrate/batch.py::read_checkpoint_tick`)."""
    manifests: dict[str, ComponentManifest] = {stage.name: pipeline.manifest_for(stage.name) for stage in pipeline.stages}
    period_ns_by_stage = {name: m.period_ns for name, m in manifests.items()}

    stages: list[dict] = []
    for stage in pipeline.stages:
        manifest = manifests[stage.name]
        inputs: list[dict] = []
        for port, ref in stage.inputs.items():
            producer, producer_port = _split_ref(ref)
            inputs.append({
                "port": port, "producer": producer, "producer_port": producer_port,
                "previous_cycle": f"{stage.name}.{port}" in setup_values.previous_cycle,
            })
        ports = [
            _port_dict(p, stage=stage.name, direction="pro", record=_record_verb_for(stage.name, p.name, {}),
                       values=setup_values)
            for p in manifest.outputs
        ] + [
            _port_dict(p, stage=stage.name, direction="req", record=_record_verb_for(stage.name, p.name, {}),
                       values=setup_values)
            for p in manifest.inputs
        ]
        stages.append({
            "name": stage.name, "mode": stage.mode,
            "impl": _stage_impl_dict(pipeline, stage),
            "trigger": _trigger_for(setup_values, stage.name, stage.mode),
            "clock_period_ns": manifest.period_ns, "abi_version": manifest.abi_version,
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

    grid_step_ns = _compute_grid_step_ns(period_ns_by_stage)
    mutations.extend(_fault_mutations(pipeline.faults, grid_step_ns=grid_step_ns))

    outputs = {"path": str(output_path), "codec": "mcap"} if output_path is not None else {}
    if setup_values.livemeas is not None:
        outputs["livemeas"] = _livemeas_dict(setup_values.livemeas)

    data: dict[str, object] = {
        "schema": RUN_SPEC_SCHEMA,
        "run_id": run_id,
        "spec_sha256": "",
        "sources": [{
            "path": str(recording_path), "sha256": recording_sha256, "codec": "mcap",
            **_ingest_for(recording_path),
        }],
        "stages": stages,
        "mutations": mutations,
        "coherence_verdict": coherence_verdict,
        "outputs": outputs,
        "limits": {"exec_timeout_ms": exec_timeout_ms, "severity_exit": "error"},
        "readiness_limit_steps": _require_setup_integer(setup_values.readiness_limit_steps, key="readiness_limit_steps"),
        "fallback_max_gap": _require_setup_integer(setup_values.fallback_max_gap, key="fallback_max_gap"),
    }
    if checkpoint_path is not None:
        data["checkpoint"] = {"path": str(checkpoint_path)}

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


def _stage_bundles(spec: RunSpec, bundle_dir: Path, scratch: Path) -> None:
    """The setup, not an engine option, carries an explicit bundle (`D31 (1)`): each simulated stage's library is copied, with
    the files beside it, into `scratch/<stage>/` and `bundle_dir` becomes the `config/` beside the copy, where the engine looks
    for it; the stage's `impl.path` names the copy and its `config_bundle_sha256` the bundle's own `bundle.sha256` when it has one."""
    hash_file = bundle_dir / "bundle.sha256"
    for stage in spec.data["stages"]:
        if stage["mode"] != "simulate" or not stage["impl"].get("path"):
            continue
        library = Path(stage["impl"]["path"])
        target = scratch / stage["name"]
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(library.parent, target, ignore=shutil.ignore_patterns("config", "__pycache__"))
        shutil.copytree(bundle_dir, target / "config")
        stage["impl"]["path"] = (target / library.name).as_posix()
        if hash_file.is_file():
            stage["config_bundle_sha256"] = hash_file.read_text(encoding="utf-8").strip()


def run_pipeline_via_engine(
    pipeline: Pipeline, recording_path: Path, *, run_id: str, output_path: Path, setup_values: RunSetupValues,
    bundle_dir: Path | None = None, exec_timeout_ms: int = 250,
    spec_json_path: Path | None = None, simengine_path: Path | None = None, search: Sequence[Path] = (),
    checkpoint_path: Path | None = None, supervise: bool = False, attempt_timeout_ms: int | None = None,
    restart_on_crash: int = 0, threads: int = 1,
) -> EngineRunResult:
    """The one call every rewired call site makes: build the spec, write it
    (`runspec.canon.write_run_spec`, the same canonical form
    `runspec/manifest.py` already uses), run it through `simengine`, return
    the outcome. `spec_json_path` defaults to a sibling of `output_path`
    (`<output_path>.spec.json`) so a caller inspecting a failed run finds
    the exact spec that failed next to the (possibly partial) recording.
    `checkpoint_path` is forwarded to `pipeline_to_run_spec` unchanged --
    `None` means no checkpointing, matching that function's own default.
    `setup_values` is forwarded unchanged too (`IMP-0051`). `exec_timeout_ms` is the setup's `limits.exec_timeout_ms` and
    `bundle_dir`, when given, is staged beside each simulated stage's library (`_stage_bundles`): neither is an engine option
    (`D31 (1)`). `supervise`, `attempt_timeout_ms` and `restart_on_crash` are `run_engine`'s."""
    spec = pipeline_to_run_spec(
        pipeline, run_id=run_id, recording_path=recording_path, output_path=output_path,
        exec_timeout_ms=exec_timeout_ms, checkpoint_path=checkpoint_path, setup_values=setup_values,
    )
    spec_path = spec_json_path if spec_json_path is not None else output_path.with_suffix(output_path.suffix + ".spec.json")
    if bundle_dir is not None:
        _stage_bundles(spec, Path(bundle_dir), spec_path.parent / (spec_path.name + ".bundles"))
    spec_sha256 = write_run_spec(spec, spec_path)
    result = run_engine(
        spec_path, supervise=supervise, attempt_timeout_ms=attempt_timeout_ms, restart_on_crash=restart_on_crash,
        threads=threads, simengine_path=simengine_path, search=search, output_path=output_path,
    )
    return replace(result, spec_sha256=spec_sha256)


def topic_to_port_name(topic: str) -> str:
    """One-line copy of `core.resim`'s own private helper -- neither
    module imports the other for a one-liner, same discipline that
    module's docstring states for its own copy. Public here (unlike
    `core.resim`'s `_topic_to_port_name`) since `check/runner.py` needs it
    too, and `WP-15b`'s own exit grep (`core\\.resim|core import resim|
    resim_pipeline`) must find no import of the retiring module outside
    itself."""
    return ".".join(topic.strip("/").split("/"))


def _port_name_to_topic(name: str) -> str:
    """The canonical topic spelling (`simcore`'s `PortNameToTopic`: leading slash,
    only the first dot turned into a slash) -- the form `simcore`'s reader
    gives every topic of a recording, whichever way the file spells it."""
    stage, sep, rest = name.partition(".")
    return f"/{stage}/{rest}" if sep else f"/{name}"


def validate_measured_stages_against_recording(
    pipeline: Pipeline, topics: Mapping[str, TopicInfo], port_name_of: Mapping[str, str],
) -> None:
    """`UT-C2-9`'s own hard-error half, moved here from `core.resim`'s
    private `_validate_measured_stages_against_recording` (same reasoning
    as `topic_to_port_name` above): a run against a recording whose port
    manifest differs from a `mode: measured` stage's own declared outputs
    -- missing entirely, or a schema/`proto_type` mismatch -- refuses to
    start, naming both, rather than silently letting a `measured` stage's
    ports read back `updated=False` with no other symptom."""
    available = {port: topics[topic] for topic, port in port_name_of.items()}
    for stage in pipeline.stages:
        if stage.mode != "measured":
            continue
        manifest = pipeline.manifest_for(stage.name)
        for port_spec in manifest.outputs:
            qualified = f"{stage.name}.{port_spec.name}"
            info = available.get(qualified)
            if info is None:
                raise InternalError(
                    expected=f"the recording to contain stage '{stage.name}''s output '{port_spec.name}'",
                    found="missing", where=f"stage '{stage.name}' (mode: measured)",
                    hint="record this stage's outputs, or set mode: simulate or off",
                )
            if info.schema_name and port_spec.proto_type and info.schema_name != port_spec.proto_type:
                raise InternalError(
                    expected=f"'{qualified}' to carry {port_spec.proto_type!r}",
                    found=f"the recording carries {info.schema_name!r}",
                    where=f"stage '{stage.name}' (mode: measured)",
                    hint="this recording was produced by a different component manifest -- "
                         "resim against a matching recording",
                )


def count_ticks(output_path: Path) -> int:
    """Ticks are a resim's own unit of progress -- read back from the
    engine's own output recording (`R-SIM-6`: every declared port is
    recorded) rather than counted in Python, since `WP-15b` moved tick
    execution to `simengine` (`R-SIM-16`). The one place every rewired
    call site that needs a tick count reads it (`cli/resim.py`,
    `orchestrate/worker.py`)."""
    reader = reader_for(output_path)
    try:
        topics = reader.topics()
        messages = list(reader.messages())
        return sum(1 for _ in group_by_log_time(messages, expected_topics=topics.keys()))
    finally:
        reader.close()


def decode_ticks(output_path: Path) -> list[tuple[int, dict[str, dict[str, bytes]]]]:
    """Reads `simengine`'s own output recording back into `(t_ns, outputs)`
    per tick, `outputs` keyed by stage then port -- the exact shape
    `core.resim.resim_pipeline` used to return directly from its in-process
    loop (`check.runner._ticks_from_resim`'s own contract), now
    reconstructed from the recording `R-SIM-6` guarantees carries every
    declared port of every non-`off` stage (`simcore/abi/simcore.cpp::
    BuildOutputTopics`) -- so this needs no ingest map and no second read
    of the input recording, unlike `core.resim.resim_pipeline`, which had
    to merge live-computed and recorded-measured bytes itself."""
    reader = reader_for(output_path)
    try:
        topics = reader.topics()
        messages = list(reader.messages())
        groups = group_by_log_time(messages, expected_topics=topics.keys())
        results: list[tuple[int, dict[str, dict[str, bytes]]]] = []
        for t_ns, payloads, _missing in groups:
            outputs: dict[str, dict[str, bytes]] = {}
            for topic, payload in payloads.items():
                stage, _, port = topic_to_port_name(topic).partition(".")
                outputs.setdefault(stage, {})[port] = payload
            results.append((t_ns, outputs))
        return results
    finally:
        reader.close()
