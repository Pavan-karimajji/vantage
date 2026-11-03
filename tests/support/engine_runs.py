# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""What the `RUN` and `ORC` system tests share (`IMP-0044`, `IMP-0045`): running `simengine` or `step_tap` on a lab
case (`F-ENGINE`, `F-TAP`), reading a recording as decoded messages, and comparing two recordings with the lab's
comparator (`F-COMPARE`, `lab_tools.compare.equal_outputs`, taken from the `vantage-lab` checkout the way
`lab_cases.py` finds it).

Nothing here decides a pass: a helper returns what it saw and the test states the assertion with the FAIL side of
the case it serves. A tool or library that is not built makes the test skip with the reason printed.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import pytest
import yaml

from adas_sim.diagnostics.errors import EnvironmentError_
from adas_sim.engine.bridge import resolve_simengine_executable
from tests.support.lab_cases import LabCase, Message, VANTAGE_ROOT, edit_setup, lab_root, read_recording

_TOOL_DIRS = (
    VANTAGE_ROOT / "conan_workarea" / "build-gtest-vs2026" / "tests" / "Release",
    VANTAGE_ROOT / "conan_workarea" / "build-gtest-ubuntu_gcc" / "tests",
)
_LAB_SRC = lab_root() / "src"
if _LAB_SRC.is_dir() and str(_LAB_SRC) not in sys.path:
    sys.path.insert(0, str(_LAB_SRC))

CONTROL_TYPE = "adas.common.CycleControl"
RUN_TIMEOUT_S = 300


def skip(reason: str) -> None:
    print(reason, file=sys.stderr)
    pytest.skip(reason)


def engine_exe() -> Path:
    try:
        return resolve_simengine_executable()
    except EnvironmentError_ as exc:
        skip(f"no built simengine found: {exc}")


def tool_path(name: str) -> Path:
    """A test executable of the gtest build (`step_tap`, `control_tick`); the library `exec_probe` is looked for the
    same way with its platform suffix."""
    names = (f"{name}.exe", name, f"{name}.dll", f"lib{name}.so")
    for directory in _TOOL_DIRS:
        for candidate in names:
            if (directory / candidate).is_file():
                return directory / candidate
    skip(f"{name} is not built (build.bat -t gtest); looked in {[str(d) for d in _TOOL_DIRS]}")


def lab_compare():
    """`lab_tools.compare` and `lab_tools.messages`, or skip when the lab checkout is not beside this one."""
    try:
        from lab_tools import compare, messages
    except ImportError as exc:
        skip(f"the lab's comparator cannot be imported (no vantage-lab/src at {_LAB_SRC}): {exc}")
    return compare, messages


# ---- running the engine ------------------------------------------------------------------------------------------

@dataclass
class EngineRun:
    """One `simengine` process: its exit code, its streams, the setup it ran and the files beside `outputs.path`."""

    returncode: int
    stdout: str
    stderr: str
    setup: Path
    recording: Path | None
    events: list[str] = field(default_factory=list)

    @property
    def started(self) -> bool:
        """True when the engine got past load: the plan was printed or an output file exists."""
        return "stage: " in self.stderr or (self.recording is not None and self.recording.exists())

    def error_text(self) -> str:
        return self.stderr.split("[simengine] error:", 1)[1] if "[simengine] error:" in self.stderr else ""


def _outputs_path(setup: Path) -> Path | None:
    declared = json.loads(setup.read_text(encoding="utf-8")).get("outputs", {}).get("path")
    return Path(declared) if declared else None


def _finish(done: subprocess.CompletedProcess, setup: Path) -> EngineRun:
    recording = _outputs_path(setup)
    events: list[str] = []
    if recording is not None:
        log = recording.with_suffix(".events.log")
        if log.is_file():
            events = log.read_text(encoding="utf-8").splitlines()
    return EngineRun(done.returncode, done.stdout, done.stderr, setup, recording, events)


def run_engine(setup: Path, *, cwd: Path | None = None, env: dict | None = None, threads: int | None = None) -> EngineRun:
    """`simengine <setup> [--threads N]` as a process; `env` replaces the whole environment when given."""
    command = [str(engine_exe()), str(setup)]
    if threads is not None:
        command += ["--threads", str(threads)]
    done = subprocess.run(command, capture_output=True, text=True, timeout=RUN_TIMEOUT_S, cwd=cwd, env=env)
    return _finish(done, setup)


def bare_environment() -> dict:
    """An environment with no Python, no YAML tool and no library search path reachable: the system directories
    only, and every variable the loader or an interpreter would read removed."""
    system = os.environ.get("SystemRoot", r"C:\Windows")
    env = {"SystemRoot": system, "PATH": os.pathsep.join([str(Path(system) / "System32"), system])} if os.name == "nt" \
        else {"PATH": "/usr/bin:/bin"}
    return env


def case_change(label: str, change: Callable[[dict], None] | None):
    """The setup change of a run: the test's own, then a livemeas name made unique for this run."""
    def apply(setup: dict) -> None:
        if change is not None:
            change(setup)
        livemeas = setup.get("outputs", {}).get("livemeas")
        if isinstance(livemeas, dict) and "name" in livemeas:
            livemeas["name"] = f"{livemeas['name']}_{label}"
    return apply


def run_case(case: LabCase, directory: Path, label: str, *, change: Callable[[dict], None] | None = None,
             threads: int | None = None, cwd: Path | None = None, env: dict | None = None) -> EngineRun:
    """The case's setup with `change` applied and `outputs.path` in `directory`, run on `simengine`."""
    recording = Path(directory) / f"{label}.mcap"
    setup = edit_setup(case, directory, case_change(label, change), name=label, outputs=recording)
    return run_engine(setup, cwd=cwd if cwd is not None else Path(directory), env=env, threads=threads)


@dataclass
class TapRun:
    returncode: int
    stderr: str
    steps: list[dict]
    setup: Path
    recording: Path | None
    events: list[str] = field(default_factory=list)

    def badge_count(self, kind: str, subject: str | None = None, *, step_index: int | None = None) -> int:
        """The cumulative count of a badge as of the step at `step_index` (default: the last step); 0 when it has
        not appeared."""
        steps = self.steps if step_index is None else self.steps[: step_index + 1]
        total = 0
        if steps:
            for badge in steps[-1]["badges"]:
                if badge["kind"] == kind and (subject is None or badge["subject"] == subject):
                    total += badge["count"]
        return total

    def badges(self, kind: str) -> dict[str, int]:
        """`{subject: count}` of a kind at the end of the run."""
        found: dict[str, int] = {}
        if self.steps:
            for badge in self.steps[-1]["badges"]:
                if badge["kind"] == kind:
                    found[badge["subject"]] = found.get(badge["subject"], 0) + badge["count"]
        return found


def run_tap(setup: Path, *, threads: int | None = None, jump: tuple[int, int] | None = None) -> TapRun:
    """`step_tap <setup>`: one JSON line per engine step. `jump` is `(at_ms, to_ms)`."""
    command = [str(tool_path("step_tap")), str(setup)]
    if threads is not None:
        command += ["--threads", str(threads)]
    if jump is not None:
        command += ["--jump-at-ms", str(jump[0]), "--jump-to-ms", str(jump[1])]
    done = subprocess.run(command, capture_output=True, text=True, timeout=RUN_TIMEOUT_S)
    steps = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
    recording = _outputs_path(setup)
    events: list[str] = []
    if recording is not None and recording.with_suffix(".events.log").is_file():
        events = recording.with_suffix(".events.log").read_text(encoding="utf-8").splitlines()
    return TapRun(done.returncode, done.stderr, steps, setup, recording, events)


def tap_case(case: LabCase, directory: Path, label: str, *, change: Callable[[dict], None] | None = None,
             threads: int | None = None, jump: tuple[int, int] | None = None) -> TapRun:
    recording = Path(directory) / f"{label}.mcap"
    setup = edit_setup(case, directory, case_change(label, change), name=label, outputs=recording)
    return run_tap(setup, threads=threads, jump=jump)


# ---- reading recordings ------------------------------------------------------------------------------------------

class Recording:
    """A recording read once: its messages in file order, decoded on demand with the schema it carries."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.messages, self.manifest, self.provenance, self.schemas = read_recording(self.path)
        _compare, messages = lab_compare()
        self._factories: dict[bytes, object] = {}
        self._messages_module = messages

    def topics(self) -> list[str]:
        return sorted({topic for topic, _t, _p in self.messages})

    def of(self, topic: str) -> list[tuple[int, int, bytes]]:
        """`(file index, log time ns, payload)` of every message of `topic`, in file order."""
        return [(i, t, p) for i, (name, t, p) in enumerate(self.messages) if name == topic]

    def decode(self, topic: str, payload: bytes):
        schema_name, descriptor_set = self.schemas[topic]
        factory = self._factories.get(descriptor_set)
        if factory is None:
            factory = self._factories[descriptor_set] = self._messages_module.MessageFactory(descriptor_set)
        return factory.parse(schema_name, payload)

    def decoded(self, topic: str) -> list[tuple[int, int, object]]:
        return [(i, t, self.decode(topic, p)) for i, t, p in self.of(topic)]

    def counters(self, topic: str) -> list[int]:
        return [m.sig_header.measurement_counter for _i, _t, m in self.decoded(topic)]


def compare_recordings(first: Recording, second: Recording, topics: Iterable[str] | None = None) -> list[str]:
    """Every difference of two recordings as `topic: reason`, by the lab's `equal_outputs` over each topic's
    messages; a topic only one of them holds is a difference. Empty when equal."""
    compare, _messages = lab_compare()
    names = sorted(set(topics) if topics is not None else set(first.topics()) | set(second.topics()))
    found: list[str] = []
    for topic in names:
        mine, theirs = first.of(topic), second.of(topic)
        if not mine and not theirs:
            continue
        schema_name, descriptor_set = (first.schemas.get(topic) or second.schemas[topic])
        factory = first._factories.get(descriptor_set) or first._messages_module.MessageFactory(descriptor_set)
        result = compare.equal_outputs([p for _i, _t, p in mine], [p for _i, _t, p in theirs], factory, schema_name)
        if not result.equal:
            found.append(f"{topic}: {result.reason}")
    return found


# ---- setup and recording edits the tests share -------------------------------------------------------------------

def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point_at_recording(setup: dict, *paths: Path) -> None:
    """`sources[]` of a setup made to list exactly `paths` (one recording, or the files of one), with their hashes."""
    setup["sources"] = [{"absent": [], "codec": "mcap", "ingest": [], "path": Path(path).as_posix(), "sha256": sha256_of(path)}
                        for path in paths]


def stage_of(setup: dict, name: str) -> dict:
    return next(stage for stage in setup["stages"] if stage["name"] == name)


def port_of(stage: dict, name: str) -> dict:
    return next(port for port in stage["ports"] if port["name"] == name)


def simulated_stages(setup: dict) -> list[str]:
    return [stage["name"] for stage in setup["stages"] if stage["mode"] == "simulate"]


def copy_tree_files(source: Path, dest: Path) -> None:
    """The files of a folder, copied with their relative layout (a bundle folder or a library's own `config/`)."""
    for item in sorted(Path(source).rglob("*")):
        if item.is_file():
            target = Path(dest) / item.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, target)


def library_with_bundle(case: LabCase, stage: str, directory: Path, bundle: Path | None = None) -> Path:
    """The stage's library copied into `directory/<stage>/` with a `config/` beside it: the stage's own bundle, or the
    folder `bundle` names (a case's `<scenario>.<case>.bundles/<stage>/` variant). The engine reads the bundle beside
    the library it loads, so this is how a test runs a stage on a bundle other than the build's. Returns the path to
    set as the stage's `impl.path`."""
    library = case.libraries[stage]
    folder = Path(directory) / stage
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / library.name
    shutil.copyfile(library, target)
    copy_tree_files(bundle if bundle is not None else library.parent / "config", folder / "config")
    return target


# ---- the cases of the lab ----------------------------------------------------------------------------------------

def catalogue() -> dict[str, dict]:
    """`{topology: declared catalogue file}` of every topology of the lab catalogue."""
    found = {}
    for path in sorted((lab_root() / "catalogue").glob("*.yaml")):
        if path.name != "provisional.yaml":
            found[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return found


def exact_cases() -> list[tuple[str, str, str]]:
    """`(topology, scenario, case)` of every exact case: the scenario expects `exact` and the case is not `hang` or
    `crash`, which need the supervisor (`F-CAT`)."""
    return [(topology, scenario["name"], case["name"])
            for topology, declared in catalogue().items()
            for scenario in declared.get("scenarios", []) if scenario.get("expect", "exact") == "exact"
            for case in scenario.get("resim", []) if case["name"] not in ("hang", "crash")]


def lab_setups() -> list[tuple[str, str, str]]:
    """`(topology, scenario, case)` of every run setup the lab wrote."""
    found = []
    for path in sorted((lab_root() / "lab").glob("*/*.run.json")):
        scenario, _dot, case = path.name[: -len(".run.json")].partition(".")
        found.append((path.parent.name, scenario, case))
    return found


def case_params(cases: list[tuple[str, str, str]]):
    """`pytest.param`s for a test over lab cases, each parameter one case; one skipped parameter, with its reason,
    when the lab has none."""
    if not cases:
        return [pytest.param(None, None, None, id="no-lab-catalogue",
                             marks=pytest.mark.skip(reason=f"lab not built: no catalogue under {lab_root() / 'catalogue'}"))]
    return [pytest.param(*case, id="/".join(case)) for case in cases]


def simulated_names(case: LabCase) -> list[str]:
    setup = json.loads(case.setup.read_text(encoding="utf-8"))
    return [stage["name"] for stage in setup["stages"] if stage["mode"] == "simulate"]


def ran(case: LabCase, directory: Path, label: str, **kwargs) -> tuple[EngineRun, Recording]:
    """`run_case`, asserted to exit 0, with its recording read."""
    run = run_case(case, directory, label, **kwargs)
    assert run.returncode == 0, f"{case.topology}/{case.scenario}/{case.case}: the engine run failed: {run.stderr[-400:]}"
    return run, Recording(run.recording)


def rerun_entries(recording: Recording, stage: str, port: str) -> list[tuple[int, int]]:
    """`(measurement_counter, source_timestamp_us)` of the refSync entry for `port` of every run of `stage`, in file
    order."""
    found = []
    for _i, _t, ref_sync in recording.decoded(f"{stage}.refSync"):
        entry = next((e for e in ref_sync.inputs if e.port == port), None)
        found.append((entry.measurement_counter, entry.source_timestamp_us) if entry is not None else (0, 0))
    return found


def event_entries(lines: list[str], kind: str) -> list[dict[str, str]]:
    """The event log lines of one entry kind as `{key: value}` (`step`, `stage`, `port`, ...)."""
    found = []
    for line in lines:
        fields = dict(part.split("=", 1) for part in line.split() if "=" in part)
        if fields.get("entry") == kind:
            found.append(fields)
    return found


def instants(recording: Recording) -> list[int]:
    """The distinct logging times of a recording, in order."""
    return sorted({t for _topic, t, _payload in recording.messages})


@dataclass(frozen=True)
class StepStarters:
    """The topics whose messages start a step, and the engine steps those and the clocks make (`ARCH §7`)."""

    topics: frozenset[str]
    times: list[int]


def step_starting_instants(setup: dict, recording: Recording) -> StepStarters:
    """The engine steps of a run setup on a recording, from the closed list of step-starting messages (`ARCH §7`,
    `D28 (2)`): a `source` sample some non-`off` stage's input reads; each output of a `measured` stage (its `pro`
    ports: data outputs, `refSync`, `compState`); the `control` of a `simulate` stage, whatever its trigger. A
    `simulate` stage's outputs and `refSync`, a topic the setup does not declare and a `measured` or `off` stage's
    `control` start nothing. A `simulate` stage with a clock adds a tick at the recording's first reception time
    plus whole periods, up to its last. Only topics the recording holds are chosen."""
    chosen: set[str] = set()
    for stage in setup["stages"]:
        if stage["mode"] == "off":
            continue
        for wired in stage.get("inputs", []):
            if wired["producer"] == "source":
                chosen.add(f"source.{wired['producer_port']}")
        if stage["mode"] == "measured":
            chosen.update(f"{stage['name']}.{port['name']}" for port in stage["ports"] if port["dir"] == "pro")
        elif stage["mode"] == "simulate":
            chosen.add(f"{stage['name']}.control")
    held = set(recording.topics())
    chosen &= held
    times = {t for topic, t, _payload in recording.messages if topic in chosen}
    everything = instants(recording)
    for stage in setup["stages"]:
        period = stage.get("clock_period_ns", 0)
        if stage["mode"] == "simulate" and period > 0:
            times.update(range(everything[0], everything[-1] + 1, period))
    return StepStarters(frozenset(chosen), sorted(times))


def edited_payload(recording: Recording, topic: str, payload: bytes, mutate: Callable[[object], None]) -> bytes:
    """`payload` of `topic` decoded with the schema `recording` carries, changed by `mutate(message)`, encoded again."""
    message = recording.decode(topic, payload)
    mutate(message)
    return message.SerializeToString(deterministic=True)


def probe_copy(directory: Path, stage: str, log: Path, spin_ms: int = 0) -> Path:
    """The exec probe's library copied to `directory/probe_<stage>/` with its own `config/` naming the stage, the call
    log and how long each call spins (the probe reads no other input)."""
    source = tool_path("exec_probe")
    folder = Path(directory) / f"probe_{stage}"
    (folder / "config").mkdir(parents=True)
    library = folder / source.name
    shutil.copyfile(source, library)
    (folder / "config" / "default.yaml").write_text(
        f"PROBE_STAGE_NAME: {stage}\nPROBE_LOG_FILE: {Path(log).as_posix()}\nPROBE_SPIN_MS: {spin_ms}\n", encoding="utf-8")
    return library


def split_by_topic(case: LabCase, directory: Path, keep_first: Callable[[str], bool]) -> tuple[Path, Path]:
    """The case's recording written as two files through `edit_recording`: the messages whose topic
    `keep_first` accepts in the first, all others in the second."""
    from tests.support.lab_cases import edit_recording

    first = edit_recording(case, Path(directory) / "part_one.mcap", lambda ms: [m for m in ms if keep_first(m[0])])
    second = edit_recording(case, Path(directory) / "part_two.mcap", lambda ms: [m for m in ms if not keep_first(m[0])])
    return first, second


__all__ = [
    "CONTROL_TYPE", "EngineRun", "Message", "Recording", "TapRun", "bare_environment", "compare_recordings",
    "case_params", "catalogue", "copy_tree_files", "edited_payload", "engine_exe", "event_entries", "exact_cases",
    "instants", "lab_compare", "lab_setups", "library_with_bundle", "point_at_recording", "port_of", "probe_copy",
    "ran", "rerun_entries", "run_case", "run_engine", "run_tap", "sha256_of", "simulated_names", "simulated_stages",
    "skip", "split_by_topic", "stage_of", "StepStarters", "step_starting_instants", "tap_case", "tool_path",
]
