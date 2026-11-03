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


def split_by_topic(case: LabCase, directory: Path, keep_first: Callable[[str], bool]) -> tuple[Path, Path]:
    """The case's recording written as two files through `edit_recording`: the messages whose topic
    `keep_first` accepts in the first, all others in the second."""
    from tests.support.lab_cases import edit_recording

    first = edit_recording(case, Path(directory) / "part_one.mcap", lambda ms: [m for m in ms if keep_first(m[0])])
    second = edit_recording(case, Path(directory) / "part_two.mcap", lambda ms: [m for m in ms if not keep_first(m[0])])
    return first, second


__all__ = [
    "CONTROL_TYPE", "EngineRun", "Message", "Recording", "TapRun", "bare_environment", "compare_recordings",
    "copy_tree_files", "engine_exe", "library_with_bundle", "lab_compare", "point_at_recording", "port_of", "run_case", "run_engine",
    "run_tap", "sha256_of", "simulated_stages", "skip", "split_by_topic", "stage_of", "tap_case", "tool_path",
]
