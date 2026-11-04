# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""What the live measurement, inspector and supervisor system tests share (`IMP-0118`; fixtures `F-LM-HELD`,
`F-INSPECT`, `F-READER`): `held_run` starts a lab case on `F-LM-HELD` -- the case's setup with one more simulated
stage, `held_probe`, whose first call returns only once the test writes its gate file -- and waits until the live
measurement exists; the test then attaches what it wants, calls `release`, and `finish`es the run. `inspect` runs
`vantage-inspect <verb>` and returns its output and exit code. `LiveRegion` reads the named shared memory directly,
byte for byte, independently of every C++ reader.

On Windows a named region lives while a handle is open, so a reader must be attached before the end (`D31 (5)`):
every test here either follows the run with `dump --follow` / `check` started while it is held, or keeps an
`F-READER --stall` attached.

Nothing here decides a pass. A tool or library that is not built makes the test skip with the reason printed.
"""
from __future__ import annotations

import json
import mmap
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from tests.support.engine_runs import (
    EngineRun, Recording, case_change, engine_exe, port_of, skip, tap_case, tool_path,
)
from tests.support.lab_cases import LabCase, VANTAGE_ROOT, edit_setup

PROBE_STAGE = "H"  # the held stage's name in a setup `held_run` makes
NAME_WAIT_S = 90.0

_INSPECTOR_DIRS = tuple(sorted((VANTAGE_ROOT / "conan_workarea").glob("build-*/src/inspector/Release"))) + \
    tuple(sorted((VANTAGE_ROOT / "conan_workarea").glob("build-*/src/inspector")))


def inspector_exe() -> Path:
    for directory in _INSPECTOR_DIRS:
        for name in ("vantage-inspect.exe", "vantage-inspect"):
            if (directory / name).is_file():
                return directory / name
    skip(f"vantage-inspect is not built (build.bat -t gtest or -t sil); looked in {[str(d) for d in _INSPECTOR_DIRS]}")


# ---- vantage-inspect ---------------------------------------------------------------------------------------------

@dataclass
class Inspected:
    code: int
    out: str
    err: str


def inspect(verb: str, *args: str, cwd: Path | None = None, env: dict | None = None, timeout: float = 300,
            exe: Path | None = None) -> Inspected:
    """`vantage-inspect <verb> <args>` as a process, to its end."""
    done = subprocess.run([str(exe or inspector_exe()), verb, *args], capture_output=True, text=True, timeout=timeout,
                          cwd=cwd, env=env)
    return Inspected(done.returncode, done.stdout, done.stderr)


class Following:
    """A `vantage-inspect` process started while the run is held; its output goes to files so it never blocks."""

    def __init__(self, command: list[str], directory: Path, label: str, *, env: dict | None = None):
        self.out_path = Path(directory) / f"{label}.inspect.out.txt"
        self.err_path = Path(directory) / f"{label}.inspect.err.txt"
        self._out = open(self.out_path, "w", encoding="utf-8")
        self._err = open(self.err_path, "w", encoding="utf-8")
        self.process = subprocess.Popen(command, stdout=self._out, stderr=self._err, env=env)

    def finish(self, timeout: float = 300) -> Inspected:
        try:
            code = self.process.wait(timeout=timeout)
        finally:
            self._out.close()
            self._err.close()
        return Inspected(code, self.out_path.read_text(encoding="utf-8"), self.err_path.read_text(encoding="utf-8"))

    def kill(self) -> None:
        self.process.kill()
        self.process.wait()
        self._out.close()
        self._err.close()


def start_inspect(directory: Path, label: str, verb: str, *args: str, env: dict | None = None) -> Following:
    return Following([str(inspector_exe()), verb, *args], directory, label, env=env)


# ---- dump lines --------------------------------------------------------------------------------------------------

_DUMP_LINE = re.compile(r"^step (\d+) port (\S+) run (\d+) origin (\w+) age_ns (\d+) (.*)$")


@dataclass(frozen=True)
class DumpLine:
    step: int
    port: str
    run: int
    origin: str
    age_ns: int
    body: str


def parse_dump(text: str) -> list[DumpLine]:
    """The value lines of `dump` output, in the order printed (`skipped` lines and others left out)."""
    found = []
    for line in text.splitlines():
        match = _DUMP_LINE.match(line)
        if match:
            found.append(DumpLine(int(match[1]), match[2], int(match[3]), match[4], int(match[5]), match[6]))
    return found


def decode_body(recording: Recording, topic: str, body: str):
    """A dump line's text-format body parsed back into a message of the type `recording` carries for `topic`."""
    from google.protobuf import text_format

    schema_name, descriptor_set = recording.schemas[topic]
    factory = recording._factories.get(descriptor_set)
    if factory is None:
        factory = recording._factories[descriptor_set] = recording._messages_module.MessageFactory(descriptor_set)
    message = factory.parse(schema_name, b"")
    text_format.Parse(body, message)
    return message


def counter_in(body: str) -> int | None:
    """`sig_header.measurement_counter` of a decoded body, or None."""
    match = re.search(r"measurement_counter:\s*(\d+)", body)
    return int(match[1]) if match else None


def status_fields(attach_output: str) -> dict[str, str]:
    """`{key: value}` of `vantage-inspect attach` output."""
    fields = {}
    for line in attach_output.splitlines():
        key, sep, value = line.partition(": ")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


# ---- processes -----------------------------------------------------------------------------------------------------

def process_table() -> dict[int, tuple[int, str]]:
    """`{pid: (parent pid, image name)}` of the machine's processes, from the platform's own tool."""
    if os.name == "nt":
        done = subprocess.run(["powershell", "-NoProfile", "-Command",
                               "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name | ConvertTo-Json"],
                              capture_output=True, text=True, timeout=60)
        return {int(p["ProcessId"]): (int(p["ParentProcessId"]), p["Name"]) for p in json.loads(done.stdout)}
    done = subprocess.run(["ps", "-e", "-o", "pid=,ppid=,comm="], capture_output=True, text=True, timeout=60)
    table = {}
    for line in done.stdout.splitlines():
        pid, ppid, name = line.split(None, 2)
        table[int(pid)] = (int(ppid), name.strip())
    return table


def descendants(pid: int, table: dict[int, tuple[int, str]] | None = None) -> list[int]:
    """The children of `pid`, then theirs, from `table` (default: the process table now)."""
    table = table if table is not None else process_table()
    found: list[int] = []
    frontier = [pid]
    while frontier:
        parent = frontier.pop()
        for child, (ppid, _name) in table.items():
            if ppid == parent and child not in found and child != parent:
                found.append(child)
                frontier.append(child)
    return found


def case_bundles(case: LabCase, directory: Path) -> Callable[[dict], None]:
    """The setup change that runs each stage a case gives its own bundle (`<scenario>.<case>.bundles/<stage>/`: the
    `hang` and `crash` cases' `LAB_B_HANG_AFTER_RUNS`, `LAB_B_CRASH_AFTER_RUNS`) on that bundle: the stage's library
    copied beside a `config/` of it (`library_with_bundle`)."""
    from tests.support.engine_runs import library_with_bundle, stage_of

    folder = case.setup.parent / f"{case.scenario}.{case.case}.bundles"

    def apply(setup: dict) -> None:
        if not folder.is_dir():
            return
        for stage_dir in sorted(p for p in folder.iterdir() if p.is_dir()):
            stage_of(setup, stage_dir.name)["impl"]["path"] = library_with_bundle(
                case, stage_dir.name, Path(directory) / case.case, stage_dir).as_posix()

    return apply


def pair_controls(messages: list, stage: str = "B") -> list:
    """`F-REC-EDIT` of `F-LM-TWICE`: `stage`'s controls taken in pairs, the first of each pair logged at the
    instant of the second, so a step holds two runs of the stage (the edit `SYT-ORC-13` uses)."""
    later = [t for topic, t, _p in messages if topic == f"{stage}.control"]
    seen = 0
    paired = []
    for index, (topic, time_ns, payload) in enumerate(messages):
        if topic == f"{stage}.control":
            if seen % 2 == 0 and seen + 1 < len(later):
                time_ns = later[seen + 1]
            seen += 1
        paired.append((index, topic, time_ns, payload))
    return [(topic, time_ns, payload) for _i, topic, time_ns, payload in sorted(paired, key=lambda m: (m[2], m[0]))]


# ---- the held stage ----------------------------------------------------------------------------------------------

def held_library(directory: Path, label: str, gate: Path, fail_at_call: int | None = None) -> Path:
    """`held_probe`'s library copied to `directory/<label>_held/` with a `config/` naming the gate file, and
    `PROBE_FAIL_AT_CALL` when `fail_at_call` is given."""
    source = tool_path("held_probe")
    folder = Path(directory) / f"{label}_held"
    (folder / "config").mkdir(parents=True, exist_ok=True)
    library = folder / source.name
    shutil.copyfile(source, library)
    bundle = f"PROBE_GATE_FILE: {Path(gate).as_posix()}\n"
    if fail_at_call is not None:
        bundle += f"PROBE_FAIL_AT_CALL: {fail_at_call}\n"
    (folder / "config" / "default.yaml").write_text(bundle, encoding="utf-8")
    return library


def add_held_stage(setup: dict, library: Path, *, source: str | None = None, source_type: str | None = None,
                   bulk: bool = False) -> None:
    """One more simulated stage `H` (`held_probe`) reading and triggered by a source port that already triggers a
    stage of the case, read by no stage: it adds no step and changes no other stage's outputs. `source` (with its
    message type, and `bulk`) names another source port for it to read instead: a topology in which no stage reads the
    source a test needs (the `camera` topology's `Cam`) -- that stage then adds the steps its source triggers."""
    template = None
    for stage in setup["stages"]:
        if stage["mode"] == "off":
            continue
        for wired in stage.get("inputs", []):
            if wired["producer"] != "source":
                continue
            wired_port = port_of(stage, wired["port"])
            if wired_port["proto_type"] == "adas.lab.LabSample":
                template = (wired["producer_port"], stage, wired_port)
                break
        if template:
            break
    assert template is not None, "no source port of LabSample type triggers a stage of this case"
    source_port, donor, in_port = template
    if source is not None:
        source_port, in_port = source, dict(in_port, proto_type=source_type or in_port["proto_type"])

    def port(name: str, direction: str, proto_type: str, like: dict) -> dict:
        made = dict(like)
        made.update({"name": name, "dir": direction, "proto_type": proto_type})
        return made

    like = port_of(donor, "control")
    setup["stages"].append({
        "name": PROBE_STAGE, "mode": "simulate", "impl": {"kind": "dll", "path": Path(library).as_posix()},
        "trigger": "in", "clock_period_ns": 0, "abi_version": donor["abi_version"], "config_bundle_sha256": "",
        "ports": [port("control", "req", "adas.common.CycleControl", like), dict(port("in", "req", in_port["proto_type"], in_port), bulk=bulk),
                  port("refSync", "pro", "adas.common.RefSync", port_of(donor, "refSync")),
                  port("compState", "pro", "adas.df.CompState", port_of(donor, "compState"))],
        "inputs": [{"port": "in", "producer": "source", "producer_port": source_port, "previous_cycle": False}],
    })
    setup["limits"]["exec_timeout_ms"] = 0  # the probe's first call is held far longer than a lab stage's call


@dataclass
class Finished:
    returncode: int
    stdout: str
    stderr: str
    recording: Path | None
    events: list[str] = field(default_factory=list)


class HeldRun:
    """A `simengine` process held in its first `held_probe` call, its live measurement existing."""

    def __init__(self, case: LabCase, setup: Path, name: str, gate: Path, process: subprocess.Popen,
                 out_path: Path, err_path: Path, directory: Path, label: str):
        self.case, self.setup, self.name, self.gate = case, setup, name, gate
        self.process, self.directory, self.label = process, Path(directory), label
        self._out_path, self._err_path = out_path, err_path
        declared = json.loads(Path(setup).read_text(encoding="utf-8"))["outputs"].get("path")
        self.recording = Path(declared) if declared else None

    @property
    def pid(self) -> int:
        return self.process.pid

    def release(self) -> None:
        self.gate.write_text("go\n", encoding="utf-8")

    def follow(self, verb: str, *args: str, tag: str | None = None) -> Following:
        """A `vantage-inspect <verb> <name> <args>` started now, attached while held."""
        return start_inspect(self.directory, f"{self.label}_{tag or verb}", verb, self.name, *args)

    def hold_open(self) -> subprocess.Popen:
        """An `F-READER --stall` attached to the name: it keeps the region alive after the run on Windows."""
        process = subprocess.Popen([str(tool_path("lm_reader")), self.name, "--stall", "--timeout-ms", "30000"],
                                   stdout=subprocess.PIPE, text=True)
        assert process.stdout.readline().strip() == "attached", "the stalled reader did not attach"
        return process

    def finish(self, timeout: float = 300) -> Finished:
        try:
            self.process.wait(timeout=timeout)
        finally:
            pass
        stdout = self._out_path.read_text(encoding="utf-8", errors="replace")
        stderr = self._err_path.read_text(encoding="utf-8", errors="replace")
        events: list[str] = []
        if self.recording is not None and self.recording.with_suffix(".events.log").is_file():
            events = self.recording.with_suffix(".events.log").read_text(encoding="utf-8").splitlines()
        return Finished(self.process.returncode, stdout, stderr, self.recording, events)

    def kill(self) -> None:
        """Ends the engine process by its pid, through the platform API."""
        self.process.kill()
        self.process.wait()

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()


def attach_ready(name: str, distinct_from: int | None = None) -> bool:
    attached = inspect("attach", name)
    if attached.code != 0 or "status: running" not in attached.out:
        return False
    return distinct_from is None or status_fields(attached.out).get("run id") != f"{distinct_from:x}"


def run_directory(directory: Path, label: str) -> Path:
    path = Path(directory) / label
    path.mkdir(parents=True, exist_ok=True)
    return path


def held_run(case: LabCase, directory: Path, label: str, *, change: Callable[[dict], None] | None = None,
             ring: int | None = None, threads: int | None = None, wait_s: float = NAME_WAIT_S,
             held_source: dict | None = None, livemeas: bool = True, supervise_ms: int | None = None,
             restart_on_crash: int = 0, distinct_from: int | None = None, env: dict | None = None,
             fail_at_call: int | None = None) -> HeldRun:
    """`case` on `F-LM-HELD`: started, held in `held_probe`'s first call, its live measurement attached-to-able.
    `ring` sets `cycle_slot_count`; unset it is the case's step count (from `F-TAP` on the same setup) plus 8, so
    the ring holds the whole run. `held_source` is `add_held_stage`'s `source`/`source_type`/`bulk`. `livemeas=False`
    removes `outputs.livemeas`: there is no name to wait for, so the run is simply given time to reach its held call.
    `supervise_ms` starts it under `--supervise --attempt-timeout-ms N`; `distinct_from` (a run id) makes the wait
    for the name skip a measurement that still has that run id (a killed run's). The caller must `release` and
    `finish` (or `close`) it. `fail_at_call` makes the held stage's n-th call return an error."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    gate = directory / f"{label}.gate"
    gate.unlink(missing_ok=True)
    if ring is None:
        tapped = tap_case(case, directory, f"{label}_steps", change=change if livemeas else None)
        assert tapped.returncode == 0, f"{case.topology}/{case.scenario}/{case.case}: the step count run failed: {tapped.stderr[-300:]}"
        ring = len(tapped.steps) + 8
    library = held_library(directory, label, gate, fail_at_call)

    def held_change(setup: dict) -> None:
        if change is not None:
            change(setup)
        if livemeas:
            setup["outputs"]["livemeas"]["cycle_slot_count"] = ring
        else:
            setup["outputs"].pop("livemeas", None)
        add_held_stage(setup, library, **(held_source or {}))

    recording = directory / f"{label}.mcap"
    setup = edit_setup(case, directory, case_change(label, held_change), name=label, outputs=recording)
    name = json.loads(case.setup.read_text(encoding="utf-8"))["outputs"]["livemeas"]["name"] + f"_{label}"
    out_path, err_path = directory / f"{label}.engine.out.txt", directory / f"{label}.engine.err.txt"
    command = [str(engine_exe()), str(setup)] + (["--threads", str(threads)] if threads is not None else [])
    if supervise_ms is not None:
        command += ["--supervise", "--attempt-timeout-ms", str(supervise_ms)]
        if restart_on_crash:
            command += ["--restart-on-crash", str(restart_on_crash)]
    process = subprocess.Popen(command, stdout=open(out_path, "w"), stderr=open(err_path, "w"), cwd=directory, env=env)
    held = HeldRun(case, setup, name, gate, process, out_path, err_path, directory, label)
    if not livemeas:
        time.sleep(2.0)  # no name to wait for: the run is given time to reach its held call
        assert process.poll() is None, f"{label}: the engine ended before its held call: {err_path.read_text(encoding='utf-8')[-400:]}"
        return held
    until = time.monotonic() + wait_s
    while time.monotonic() < until:
        if process.poll() is not None:
            stderr = err_path.read_text(encoding="utf-8", errors="replace")
            raise AssertionError(f"{label}: the engine ended (exit {process.returncode}) before its live measurement "
                                 f"'{name}' appeared: {stderr[-500:]}")
        if attach_ready(name, distinct_from):
            return held
        time.sleep(0.05)
    held.close()
    raise AssertionError(f"{label}: no live measurement '{name}' within {wait_s} s")


def release_and_follow(held: HeldRun, *verbs_args: tuple) -> list[Inspected]:
    """Attaches one `vantage-inspect` per `(verb, *args)` while held, releases the run, and returns what each said
    once the measurement was finished."""
    followers = [held.follow(verb, *args, tag=f"{verb}{i}") for i, (verb, *args) in enumerate(verbs_args)]
    time.sleep(0.3)  # each attached before the release
    held.release()
    return [f.finish() for f in followers]


@dataclass
class Flawed:
    """What `make_flawed` saw: the inspector's result, the target's name and the lines the tool printed before it
    was ready (`flaw step=N`)."""

    result: Inspected
    target: str
    notes: list[str]


def make_flawed(held: HeldRun, label: str, *flaw: str, check_args: tuple = (), outcome: int | None = None,
                verb: str = "check") -> Flawed:
    """`F-FLAWED-LM` made from the held run `held` with the flaw `flaw` (its options, `lm_flawed`'s own), and
    `vantage-inspect <verb> <target> <check_args>` attached to it before it ends: returns what the inspector said and
    the target's name. Releases `held`."""
    target = f"{held.name}_{label}"
    gate = held.directory / f"{target}.gate"
    gate.unlink(missing_ok=True)
    err_path = held.directory / f"{target}.flawed.err.txt"
    command = [str(tool_path("lm_flawed")), "--source", held.name, "--target", target, "--gate", str(gate), *flaw]
    if outcome is not None:
        command += ["--outcome", str(outcome)]
    writer = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=open(err_path, "w"), text=True)
    time.sleep(0.4)  # attached to the source before it ends
    held.release()
    notes: list[str] = []
    while True:
        line = writer.stdout.readline().strip()
        if line == "ready":
            break
        assert line, f"lm_flawed did not get ready ({flaw}): {err_path.read_text(encoding='utf-8')[-400:]}"
        notes.append(line)
    checker = start_inspect(held.directory, f"{held.label}_{label}", verb, target, *check_args)
    time.sleep(0.3)
    gate.write_text("go\n", encoding="utf-8")
    writer.wait(timeout=60)
    return Flawed(checker.finish(), target, notes)


# ---- reading the shared memory directly ---------------------------------------------------------------------------

_STATUS = struct.Struct("<IIQIIIIIIIIIxxxxQQQ")  # MeasStatus, 80 bytes (`livemeas_layout.hpp`)
assert _STATUS.size == 80


@dataclass(frozen=True)
class Status:
    magic: int
    layout_version: int
    run_id: int
    writer_pid: int
    status: int
    outcome: int
    description_capacity: int
    description_length: int
    cycle_slot_count: int
    cycle_slot_size: int
    bulk_slot_count: int
    bulk_slot_size: int
    heartbeat: int
    write_sequence: int
    dropped_cycles: int


class _WindowsView:
    """An existing named file mapping opened read-only (`OpenFileMapping`, never created: `mmap`'s `tagname` would
    create a missing one, and so race the engine that is about to)."""

    def __init__(self, name: str, length: int):
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenFileMappingA.restype = wintypes.HANDLE
        kernel.OpenFileMappingA.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCSTR]
        kernel.MapViewOfFile.restype = ctypes.c_void_p
        kernel.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
        kernel.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel = kernel
        self._handle = kernel.OpenFileMappingA(0x0004, False, name.encode())  # FILE_MAP_READ
        if not self._handle:
            raise OSError(f"no mapping named {name!r}")
        self._base = kernel.MapViewOfFile(self._handle, 0x0004, 0, 0, length)
        if not self._base:
            kernel.CloseHandle(self._handle)
            raise OSError(f"mapping {name!r} cannot be viewed")
        self._array = (ctypes.c_char * length).from_address(self._base)

    def __getitem__(self, key):
        return self._array[key]

    def __len__(self) -> int:
        return len(self._array)

    def __buffer__(self, flags):  # Python 3.12: the buffer protocol of the underlying array
        return memoryview(self._array)

    def buffer(self):
        return self._array

    def close(self) -> None:
        if self._base:
            self._kernel.UnmapViewOfFile(self._base)
            self._kernel.CloseHandle(self._handle)
            self._base = None


def _map(name: str, length: int):
    try:
        if os.name == "nt":
            return _WindowsView(name, length)
        with open(f"/dev/shm/{name}", "rb") as handle:
            return mmap.mmap(handle.fileno(), length, access=mmap.ACCESS_READ)
    except (OSError, ValueError):
        return None


def _buf(view):
    """The object `struct.unpack_from` can read: the view's array on Windows, the mmap itself elsewhere."""
    return view.buffer() if isinstance(view, _WindowsView) else view


class LiveRegion:
    """A live measurement's two segments mapped read-only by name, read with `struct` and nothing of Vantage's."""

    def __init__(self, name: str):
        self.name = name
        head = _map(name, _STATUS.size)
        if head is None:
            raise LookupError(f"no live measurement named {name!r}")
        status = self._status_of(head)
        head.close()
        if status.magic != 0x534D564C:  # created, not yet initialised by the writer
            raise LookupError(f"{name!r} is not ready")
        self.data_size = 80 + status.description_capacity + status.cycle_slot_count * status.cycle_slot_size
        self.bulk_size = status.bulk_slot_count * status.bulk_slot_size
        self.data = _map(name, self.data_size)
        self.bulk = _map(name + "_bulk", self.bulk_size)
        if self.data is None or self.bulk is None:
            for view in (self.data, self.bulk):
                if view is not None:
                    view.close()
            raise LookupError(f"the segments of {name!r} cannot be mapped")

    @staticmethod
    def _status_of(view) -> Status:
        fields = _STATUS.unpack_from(_buf(view), 0)
        return Status(*fields)

    def status(self) -> Status:
        return self._status_of(self.data)

    def copy(self) -> tuple[bytes, bytes]:
        """Both segments, copied now."""
        return bytes(self.data[: self.data_size]), bytes(self.bulk[: self.bulk_size])

    def description(self) -> Description:
        status = self.status()
        return parse_description(bytes(self.data[80:80 + status.description_length]))

    def cycles(self) -> list[Cycle]:
        """Every complete cycle slot, in step order (a slot read between two writes is skipped)."""
        status = self.status()
        found = []
        for index in range(status.cycle_slot_count):
            offset = 80 + status.description_capacity + index * status.cycle_slot_size
            sequence, step, sim_time, length = struct.unpack_from("<QQQI", _buf(self.data), offset)
            if sequence == 0 or sequence & 1:
                continue
            body = bytes(self.data[offset + 32:offset + 32 + length])
            if struct.unpack_from("<Q", _buf(self.data), offset)[0] != sequence:
                continue
            found.append(parse_cycle(step, sim_time, body))
        return sorted(found, key=lambda c: c.step)

    def bulk_slot(self, slot: int) -> tuple[int, int, int, bytes]:
        """`(sequence, step, port, payload)` of bulk slot `slot`."""
        status = self.status()
        offset = slot * status.bulk_slot_size
        sequence, step, length, port = struct.unpack_from("<QQII", _buf(self.bulk), offset)
        return sequence, step, port, bytes(self.bulk[offset + 24:offset + 24 + length])

    def newest_step(self) -> int | None:
        """The step of the newest completed cycle slot, or None when no cycle was written."""
        status = self.status()
        if status.write_sequence == 0:
            return None
        index = (status.write_sequence - 1) % status.cycle_slot_count
        offset = 80 + status.description_capacity + index * status.cycle_slot_size
        return struct.unpack_from("<Q", _buf(self.data), offset + 8)[0]

    def close(self) -> None:
        self.data.close()
        self.bulk.close()


# ---- protobuf wire parsing: the live measurement's own messages, with no generated class --------------------------

def _varint(buf: bytes, pos: int) -> tuple[int, int]:
    shift = result = 0
    while True:
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7


def wire_fields(buf: bytes) -> dict[int, list]:
    """`{field number: [values]}` of one serialized message: a varint is an int, a length-delimited field its bytes."""
    found: dict[int, list] = {}
    pos = 0
    while pos < len(buf):
        key, pos = _varint(buf, pos)
        number, kind = key >> 3, key & 7
        if kind == 0:
            value, pos = _varint(buf, pos)
        elif kind == 2:
            length, pos = _varint(buf, pos)
            value, pos = bytes(buf[pos:pos + length]), pos + length
        elif kind == 1:
            value, pos = struct.unpack_from("<Q", buf, pos)[0], pos + 8
        elif kind == 5:
            value, pos = struct.unpack_from("<I", buf, pos)[0], pos + 4
        else:
            raise ValueError(f"wire type {kind}")
        found.setdefault(number, []).append(value)
    return found


ORIGINS = ["UNKNOWN", "MEASURED", "TRUTH", "MOCKED", "SIMULATED", "OVERRIDDEN"]
BADGE_KINDS = ["KIND_UNKNOWN", "KIND_FALLBACK", "KIND_WARMING_UP", "KIND_READINESS_TIMEOUT",
               "KIND_COMPUTED_NOT_CONSUMED", "KIND_IDENTITY_BROKEN"]


@dataclass(frozen=True)
class CycleValue:
    port: int
    payload: bytes
    origin: str
    age_ns: int
    omitted: bool
    bulk: tuple[int, int] | None  # (slot, sequence)


@dataclass(frozen=True)
class Cycle:
    step: int
    sim_time_ns: int
    values: list[CycleValue]
    badges: list[tuple[str, str, int]]  # (kind, subject, count)


def parse_cycle(step: int, sim_time_ns: int, buf: bytes) -> Cycle:
    fields = wire_fields(buf)
    values = []
    for raw in fields.get(1, []):
        v = wire_fields(raw)
        bulk = wire_fields(v[6][0]) if 6 in v else None
        values.append(CycleValue(v.get(1, [0])[0], v.get(2, [b""])[0], ORIGINS[v.get(3, [0])[0]], v.get(4, [0])[0],
                                 bool(v.get(5, [0])[0]), (bulk.get(1, [0])[0], bulk.get(2, [0])[0]) if bulk is not None else None))
    badges = []
    for raw in fields.get(2, []):
        b = wire_fields(raw)
        badges.append((BADGE_KINDS[b.get(1, [0])[0]], b.get(2, [b""])[0].decode(), b.get(3, [0])[0]))
    return Cycle(step, sim_time_ns, values, badges)


@dataclass(frozen=True)
class Description:
    """`MeasDescription` read by field number: stages `{name, mode, impl, build_id, trigger, clock_period_ns,
    previous_cycle_inputs}`, ports `{name, proto_type, bulk}`, overrides' addresses, bundles, readiness limit."""

    recording: str
    stages: list[dict]
    ports: list[dict]
    bundles: list[dict]
    overrides: list[dict]
    readiness_limit_steps: int


_MODES = ["MODE_UNKNOWN", "MODE_SIMULATE", "MODE_MEASURED", "MODE_OFF"]


def parse_description(buf: bytes) -> Description:
    top = wire_fields(buf)
    stages = []
    for raw in top.get(2, []):
        s = wire_fields(raw)
        stages.append({"name": s.get(1, [b""])[0].decode(), "mode": _MODES[s.get(2, [0])[0]],
                       "impl": s.get(3, [b""])[0].decode(), "build_id": s.get(4, [b""])[0].decode(),
                       "trigger": s.get(5, [b""])[0].decode(), "clock_period_ns": s.get(6, [0])[0],
                       "previous_cycle_inputs": [x.decode() for x in s.get(7, [])]})
    ports = []
    for raw in top.get(3, []):
        p = wire_fields(raw)
        ports.append({"name": p.get(1, [b""])[0].decode(), "proto_type": p.get(2, [b""])[0].decode(),
                      "bulk": bool(p.get(3, [0])[0])})
    bundles = []
    for raw in top.get(5, []):
        b = wire_fields(raw)
        bundles.append({"stage": b.get(1, [b""])[0].decode(), "kind": b.get(2, [0])[0],
                        "path": b.get(3, [b""])[0].decode(), "sha256": b.get(4, [b""])[0].decode()})
    overrides = []
    for raw in top.get(6, []):
        o = wire_fields(raw)
        overrides.append({"address": o.get(1, [b""])[0].decode(), "verb": o.get(2, [0])[0],
                          "argument": o.get(3, [b""])[0].decode()})
    return Description(top.get(1, [b""])[0].decode(), stages, ports, bundles, overrides, top.get(7, [0])[0])


def pid_alive(pid: int) -> bool:
    """Whether a process of that id is running, from the platform's own call."""
    if os.name == "nt":
        import ctypes

        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def kill_as_crash(pid: int) -> None:
    """Ends a process by its pid as an abnormal termination: `TerminateProcess` with an unhandled-exception status on
    Windows (a plain kill gives exit code 1, which no one can tell from a clean failure), `SIGKILL` elsewhere."""
    if os.name == "nt":
        import ctypes

        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
        assert handle, f"cannot open process {pid} to end it"
        kernel.TerminateProcess(handle, 0xC0000005)
        kernel.CloseHandle(handle)
    else:
        import signal

        os.kill(pid, signal.SIGKILL)


def suspend(process: subprocess.Popen) -> None:
    """Stops `process` where it is, through the platform API (a paused reader)."""
    if os.name == "nt":
        import ctypes

        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x0800, False, process.pid)  # PROCESS_SUSPEND_RESUME
        ctypes.windll.ntdll.NtSuspendProcess(handle)
        kernel.CloseHandle(handle)
    else:
        import signal

        os.kill(process.pid, signal.SIGSTOP)


def resume(process: subprocess.Popen) -> None:
    if os.name == "nt":
        import ctypes

        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x0800, False, process.pid)
        ctypes.windll.ntdll.NtResumeProcess(handle)
        kernel.CloseHandle(handle)
    else:
        import signal

        os.kill(process.pid, signal.SIGCONT)


@dataclass
class TapWithRegion:
    """A `step_tap` run with a reader (`LiveRegion`) attached while it ran: the tap's lines and the region."""

    returncode: int
    stderr: str
    steps: list[dict]
    region: LiveRegion | None
    setup: Path
    recording: Path


def tap_with_region(case: LabCase, directory: Path, label: str, *, change: Callable[[dict], None] | None = None,
                    jump: tuple[int, int] | None = None, ring: int = 2000, wait_s: float = 60.0) -> TapWithRegion:
    """`step_tap` on the case with `outputs.livemeas` and a reader attached as soon as the name appears (the ring
    set to `ring` cycles so it holds the run)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    def with_ring(setup: dict) -> None:
        if change is not None:
            change(setup)
        setup["outputs"]["livemeas"]["cycle_slot_count"] = ring

    recording = directory / f"{label}.mcap"
    setup = edit_setup(case, directory, case_change(label, with_ring), name=label, outputs=recording)
    name = json.loads(setup.read_text(encoding="utf-8"))["outputs"]["livemeas"]["name"]
    command = [str(tool_path("step_tap")), str(setup)]
    if jump is not None:
        command += ["--jump-at-ms", str(jump[0]), "--jump-to-ms", str(jump[1])]
    out_path, err_path = directory / f"{label}.tap.out.txt", directory / f"{label}.tap.err.txt"
    process = subprocess.Popen(command, stdout=open(out_path, "w"), stderr=open(err_path, "w"), cwd=directory)
    region = None
    until = time.monotonic() + wait_s
    while region is None and process.poll() is None and time.monotonic() < until:
        try:
            region = LiveRegion(name)
        except LookupError:
            time.sleep(0.001)
    process.wait(timeout=300)
    steps = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line.startswith("{")]
    return TapWithRegion(process.returncode, err_path.read_text(encoding="utf-8", errors="replace"), steps, region,
                         setup, recording)


def wait_until(predicate: Callable[[], bool], timeout: float, interval: float = 0.01) -> bool:
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


__all__ = [
    "BADGE_KINDS",
    "Cycle",
    "CycleValue",
    "Description",
    "DumpLine",
    "Finished",
    "Flawed",
    "Following",
    "HeldRun",
    "Inspected",
    "LiveRegion",
    "NAME_WAIT_S",
    "ORIGINS",
    "PROBE_STAGE",
    "Status",
    "TapWithRegion",
    "add_held_stage",
    "attach_ready",
    "case_bundles",
    "counter_in",
    "decode_body",
    "descendants",
    "held_library",
    "held_run",
    "inspect",
    "inspector_exe",
    "kill_as_crash",
    "make_flawed",
    "pair_controls",
    "parse_cycle",
    "parse_description",
    "parse_dump",
    "pid_alive",
    "process_table",
    "release_and_follow",
    "resume",
    "run_directory",
    "start_inspect",
    "status_fields",
    "suspend",
    "tap_with_region",
    "wait_until",
    "wire_fields",
]
