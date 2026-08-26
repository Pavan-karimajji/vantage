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
from dataclasses import dataclass, field, replace
from pathlib import Path

from adas_sim.config.fault import FaultVerb
from adas_sim.config.paths import sim_root
from adas_sim.diagnostics.errors import EnvironmentError_, InternalError
from adas_sim.graph.build import Pipeline, _split_ref
from adas_sim.io.base import Provenance, RunManifest, TopicInfo, group_by_log_time
from adas_sim.plugins.registry import reader_for, writer_for
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
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout_s)
    except OSError:
        win_cmd = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        return subprocess.run(
            ["cmd.exe", "/c", win_cmd], capture_output=True, text=True, encoding="utf-8", timeout=timeout_s
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
    spec_path: Path, *, config_path: Path | None = None, exec_timeout_ms: int = 0,
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
    hanging the caller forever."""
    binary = simengine_path if simengine_path is not None else resolve_simengine_executable(search)
    cmd = [str(binary), str(spec_path)]
    if config_path is not None:
        cmd += ["--config", str(config_path)]
    if exec_timeout_ms > 0:
        cmd += ["--timeout-ms", str(exec_timeout_ms)]
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
    empty = {"kind": "dll", "path": "", "pattern": "", "search": []}
    if stage.impl is None:
        return empty
    kind, _, _stem = stage.impl.partition(":")
    lib_path = pipeline.library_paths.get(stage.name)
    if kind not in ("dll", "stubdll") or lib_path is None:
        return empty
    return {
        "kind": kind, "path": str(lib_path),
        "pattern": "{stem}.dll" if lib_path.suffix == ".dll" else f"{{stem}}{lib_path.suffix}",
        "search": [],
    }


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
    once for this same spec's own `grid.step_ns`, never re-derived."""
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


def pipeline_to_run_spec(
    pipeline: Pipeline, *, run_id: str, recording_path: Path, recording_sha256: str = "",
    output_path: Path | None = None, exec_timeout_ms: int = 250, checkpoint_path: Path | None = None,
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

    grid_step_ns = _compute_grid_step_ns(period_ns_by_stage)
    mutations.extend(_fault_mutations(pipeline.faults, grid_step_ns=grid_step_ns))

    outputs = {"path": str(output_path), "codec": "mcap"} if output_path is not None else {}

    data: dict[str, object] = {
        "schema": RUN_SPEC_SCHEMA,
        "run_id": run_id,
        "spec_sha256": "",
        "grid": {"step_ns": grid_step_ns},
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


def run_pipeline_via_engine(
    pipeline: Pipeline, recording_path: Path, *, run_id: str, output_path: Path,
    config_path: Path | None = None, exec_timeout_ms: int = 250,
    spec_json_path: Path | None = None, simengine_path: Path | None = None, search: Sequence[Path] = (),
    checkpoint_path: Path | None = None,
) -> EngineRunResult:
    """The one call every rewired call site makes: build the spec, write it
    (`runspec.canon.write_run_spec`, the same canonical form
    `runspec/manifest.py` already uses), run it through `simengine`, return
    the outcome. `spec_json_path` defaults to a sibling of `output_path`
    (`<output_path>.spec.json`) so a caller inspecting a failed run finds
    the exact spec that failed next to the (possibly partial) recording.
    `checkpoint_path` is forwarded to `pipeline_to_run_spec` unchanged --
    `None` means no checkpointing, matching that function's own default."""
    spec = pipeline_to_run_spec(
        pipeline, run_id=run_id, recording_path=recording_path, output_path=output_path,
        exec_timeout_ms=exec_timeout_ms, checkpoint_path=checkpoint_path,
    )
    spec_path = spec_json_path if spec_json_path is not None else output_path.with_suffix(output_path.suffix + ".spec.json")
    spec_sha256 = write_run_spec(spec, spec_path)
    result = run_engine(
        spec_path, config_path=config_path, exec_timeout_ms=exec_timeout_ms,
        simengine_path=simengine_path, search=search, output_path=output_path,
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
    """Matches `sources.recorder.topic_for`'s convention (`WP-15b` follow-on:
    leading slash, only the first dot turned into a slash) -- this function's
    output is compared for exact equality against `Recorder`-written topics
    in `merge_engine_output_with_recording` below, so the two must agree."""
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


def merge_engine_output_with_recording(
    pipeline: Pipeline, recording_path: Path, engine_output_path: Path, out_path: Path, *, meta: RunManifest,
) -> None:
    """The Python-object twin of `core.resim.resim_pipeline_merged`
    (`S-D3`, `ST-D3-1`): a full, directly-viewable recording at `out_path`
    -- every topic `recording_path` originally carried, passed through
    unchanged, except each `mode: simulate` stage's own declared output
    ports, overwritten with `engine_output_path`'s freshly-computed bytes
    (`R-SIM-13` -- the viewer's only input is a `Session`, built from a
    complete recording, never assembled from two files at load time).

    Unlike `resim_pipeline_merged`, TICK EXECUTION already happened
    (`simengine`, via `run_pipeline_via_engine`) -- this function only
    merges two already-written recordings, so no Python frame runs per
    message the engine already produced (`ANL-SW-05`)."""
    simulate_stages = [stage for stage in pipeline.stages if stage.mode == "simulate"]
    simulate_topics: dict[str, TopicInfo] = {}
    for stage in simulate_stages:
        manifest = pipeline.manifest_for(stage.name)
        for port_spec in manifest.outputs:
            topic = _port_name_to_topic(f"{stage.name}.{port_spec.name}")
            simulate_topics[topic] = TopicInfo(
                schema_name=port_spec.proto_type or f"{stage.name}.{port_spec.name}",
                schema_bytes=manifest.descriptor_set, provenance=Provenance.SIMULATED,
            )

    src_reader = reader_for(recording_path)
    try:
        src_topics = src_reader.topics()
        merged_topics = {topic: info for topic, info in src_topics.items() if topic not in simulate_topics}
        merged_topics.update(simulate_topics)

        src_messages = list(src_reader.messages())
        capture_by_topic_time = {
            (topic, log_time_ns): capture_time_ns for topic, log_time_ns, capture_time_ns, _payload in src_messages
        }
        src_groups = list(group_by_log_time(src_messages, expected_topics=src_topics.keys()))
    finally:
        src_reader.close()

    engine_ticks = dict(decode_ticks(engine_output_path))  # t_ns -> {stage: {port: bytes}}

    writer = writer_for(out_path)
    writer.open(out_path, meta, merged_topics)
    try:
        for t_ns, payloads, _missing in src_groups:
            for topic, payload in payloads.items():
                if topic in simulate_topics:
                    continue
                writer.write(topic, t_ns, payload, capture_time_ns=capture_by_topic_time.get((topic, t_ns)))

            outputs_by_stage = engine_ticks.get(t_ns, {})
            for stage in simulate_stages:
                for port_name, payload in outputs_by_stage.get(stage.name, {}).items():
                    # Freshly computed this tick by simengine -- reception
                    # and validity coincide, same reasoning
                    # `resim_pipeline_merged`'s own comment gives.
                    writer.write(_port_name_to_topic(f"{stage.name}.{port_name}"), t_ns, payload, capture_time_ns=t_ns)
    finally:
        writer.close()


def run_pipeline_merged_via_engine(
    pipeline: Pipeline, recording_path: Path, out_path: Path, *, meta: RunManifest, run_id: str,
    config_path: Path | None = None, exec_timeout_ms: int = 250, simengine_path: Path | None = None,
    search: Sequence[Path] = (),
) -> EngineRunResult:
    """`player/shell/qt_window.py`'s GUI "Run" button rewired onto this
    (`WP-15b`): runs `pipeline` through `simengine`, then merges the fresh
    output back into a full copy of `recording_path` at `out_path` --
    the out-of-process twin of `core.resim.resim_pipeline_merged`, same
    contract, same caller-visible result (a complete `out_path` recording,
    `build_session_from_recording`-loadable with no other input)."""
    engine_output_path = out_path.with_suffix(out_path.suffix + ".engine.mcap")
    result = run_pipeline_via_engine(
        pipeline, recording_path, run_id=run_id, output_path=engine_output_path, config_path=config_path,
        exec_timeout_ms=exec_timeout_ms, simengine_path=simengine_path, search=search,
    )
    if not result.ok:
        return result
    merge_engine_output_with_recording(pipeline, recording_path, engine_output_path, out_path, meta=meta)
    return result


def overwrite_manifest_meta(output_path: Path, meta: RunManifest) -> None:
    """**Found live, fixed live (`WP-15b`):** `simengine`'s own writer
    (`simcore::abi::simcore.cpp`) embeds NO `_MANIFEST_META` metadata
    record at all today (`io.mcap.McapWriter.open`'s own `if meta.known`
    guard never fires against anything the engine wrote) — every field
    `runspec.manifest.build_manifest` used to populate in Python,
    in-process, before `core/resim.py`'s own writer ran (`run_id`, host,
    timestamps, and — `NR-SIM-24`'s own guarantee —
    `component_build_shas`) is simply absent from a recording produced
    through the new bridge. `verify_pinned_builds` then reports every
    stage **unpinnable** (a real regression from the pre-`WP-15b`
    behaviour `test_d7_pin_builds_cli.py`'s own round trip depends on,
    not a wrong hash — the field is missing outright). Closing this
    inside `simcore` itself (a real `MetaKind::run_manifest` writer,
    `IMP-0038`'s own note) is `simcore`'s job, out of this Python-wiring
    package's own scope — this function is the caller-side answer until
    then: build a real `RunManifest` (`runspec.manifest.build_manifest`,
    unchanged, same call `core/resim.py`'s own caller used to make) and
    overwrite the recording's ENTIRE meta block with it, read-everything/
    rewrite (`sim convert`'s own pattern, the same one
    `test_d7_pin_builds_cli.py::_with_tampered_library_sha` already uses
    for the opposite direction — writing a WRONG hash to prove refusal).
    A targeted single-field patch was tried first and found insufficient
    live: `RunManifest.known` gates the whole write on `manifest_version
    > 0`, so patching only `components` into an otherwise-still-default
    (`manifest_version=0`) meta silently wrote nothing at all — the caller
    must supply a genuinely complete, real manifest."""
    reader = reader_for(output_path)
    try:
        topics = reader.topics()
        messages = list(reader.messages())
    finally:
        reader.close()
    tmp_path = output_path.with_name(output_path.stem + ".manifesttmp" + output_path.suffix)
    writer = writer_for(tmp_path)
    writer.open(tmp_path, meta, topics)
    try:
        for topic, log_time_ns, capture_time_ns, payload in messages:
            writer.write(topic, log_time_ns, payload, capture_time_ns=capture_time_ns)
    finally:
        writer.close()
    tmp_path.replace(output_path)


def backfill_schema_bytes(output_path: Path, pipeline: Pipeline) -> None:
    """**Found live, fixed live, 2026-08-26 (`SM-12`'s own `E2E-07` item
    8):** `simcore::abi::BuildOutputTopics` (`simcore.cpp`) sets every
    topic's `schema_name` from `RunSpec`'s own `proto_type` but never its
    `schema_bytes` — a real `FileDescriptorSet` is only available AFTER a
    component loads, and `Writer::Open` must run before that (that
    function's own comment states this explicitly; not an oversight).
    `.mcap`'s `arbitrary_topics` capability degrades this to a
    schema-less registration, so the recording is still fully readable —
    but `PortValue.message`'s own lazy decode (`session/tick.py`) then
    degrades too (`decode_message`'s documented `if not schema_bytes:
    return payload`), and nothing downstream expected raw bytes back: a
    real component's own layer providers (`warning_layer`, found live
    against `bsd.outputs`) call `.message` assuming a parsed protobuf
    object always comes back.

    Same read-everything/rewrite pattern `overwrite_manifest_meta`
    (immediately above) already uses, run as its own separate pass
    (kept independent rather than folded into that function's own
    signature, since it needs `pipeline` — a different input, for a
    different, unrelated field): for every topic whose `TopicInfo`
    carries a `schema_name` but empty `schema_bytes`, find which stage
    produced it (`topic_to_port_name`'s own qualified form, split on the
    first `.`) and patch in that stage's own already-loaded
    `ComponentManifest.descriptor_set` — the real bytes `simcore` could
    not reach at write time but `pipeline` (built for provenance checks,
    never `init_components`'d or `exec()`'d, `cli/resim.py`'s own note)
    already has, cheaply, with no engine re-run. A topic naming a stage
    this pipeline does not declare (should not occur for anything
    `simengine` itself wrote) is left unpatched rather than raising —
    this function only ever adds information, never required to
    succeed for every topic to be worth running once."""
    reader = reader_for(output_path)
    try:
        meta = reader.meta()
        topics = dict(reader.topics())
        messages = list(reader.messages())
    finally:
        reader.close()

    stage_names = {stage.name for stage in pipeline.stages}
    patched = False
    for topic, info in list(topics.items()):
        if info.schema_bytes or not info.schema_name:
            continue
        stage_name, sep, _port = topic_to_port_name(topic).partition(".")
        if not sep or stage_name not in stage_names:
            continue
        descriptor_set = pipeline.manifest_for(stage_name).descriptor_set
        if not descriptor_set:
            continue
        topics[topic] = replace(info, schema_bytes=descriptor_set)
        patched = True
    if not patched:
        return  # nothing to do -- every topic already had real bytes or none to source

    tmp_path = output_path.with_name(output_path.stem + ".schematmp" + output_path.suffix)
    writer = writer_for(tmp_path)
    writer.open(tmp_path, meta, topics)
    try:
        for topic, log_time_ns, capture_time_ns, payload in messages:
            writer.write(topic, log_time_ns, payload, capture_time_ns=capture_time_ns)
    finally:
        writer.close()
    tmp_path.replace(output_path)
