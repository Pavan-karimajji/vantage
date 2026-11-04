# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""Runs the Python suites (``--python <paths>``) and/or the gtest binary (``--gtest``) in ``--workers N`` processes
(default: logical cores, at most 16) and aggregates them as one run.

Python: the node ids are collected once (``pytest --collect-only -q``), dealt longest first to the workers from
``conan_workarea/test_durations.json`` (written after each run; ids it has no time for are dealt in collection order),
and each worker is one ``pytest`` process with its own ``--basetemp``, ``--junitxml`` and ``VANTAGE_TEST_WORKER=<n>``
(``tests/support/lab_cases.py`` gives each worker its own copy of a lab setup, with its own live measurement name).
gtest: ``simcore_tests.exe`` as N shards (``GTEST_TOTAL_SHARDS``, ``GTEST_SHARD_INDEX``).

Exit 1 on any failure or error, or when the collected and the run counts differ. A test that cannot be isolated is listed
in ``SERIAL`` with its reason: it runs after the parallel part, alone; none is ever skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DURATIONS = ROOT / "conan_workarea" / "test_durations.json"
GTEST_EXE = ROOT / "conan_workarea" / "build-gtest-vs2026" / "tests" / "Release" / "simcore_tests.exe"
GTEST_CWD = ROOT / "conan_workarea" / "build-gtest-vs2026" / "tests"  # where ctest runs each discovered test

#: Tests that cannot be isolated, node id prefix -> the reason.
SERIAL: dict[str, str] = {
    "tests/system/test_vnt_window.py": "tkinter initialisation fails now and then while 16 workers load the machine; four short tests in one quiet process",
}


def _key(classname: str, name: str) -> str:
    return f"{classname}::{name}"


def _collected_key(node_id: str) -> str:
    """The junit key (`classname::name`) of a collected node id."""
    head = node_id.split("[", 1)[0]
    parts = head.split("::")
    module = parts[0][: -len(".py")].replace("/", ".").replace("\\", ".")
    name = parts[-1] + node_id[len(head):]
    return _key(".".join([module] + parts[1:-1]), name)


def collect(paths: list[str]) -> list[str]:
    done = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *paths],
                          capture_output=True, text=True, cwd=ROOT)
    ids = [line.strip() for line in done.stdout.splitlines() if "::" in line and not line.startswith(" ")]
    if done.returncode not in (0, 5) and not ids:
        sys.exit(f"run_tests: collection failed:\n{done.stdout[-1500:]}\n{done.stderr[-1500:]}")
    return ids


def load_durations() -> dict[str, float]:
    try:
        return json.loads(DURATIONS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def deal(ids: list[str], workers: int, durations: dict[str, float]) -> list[list[str]]:
    """Longest first onto the least loaded worker; an id with no recorded time takes the median (1 s with none)."""
    known = [durations[_collected_key(i)] for i in ids if _collected_key(i) in durations]
    default = statistics.median(known) if known else 1.0
    timed = [(durations.get(_collected_key(i), default), n, i) for n, i in enumerate(ids)]
    timed.sort(key=lambda item: (-item[0], item[1]))
    load = [0.0] * workers
    bins: list[list[str]] = [[] for _ in range(workers)]
    for seconds, _n, node in timed:
        target = load.index(min(load))
        bins[target].append(node)
        load[target] += seconds
    return bins


def _read_junit(path: Path) -> dict:
    """passed / failed / skipped / errors, the failing ids, the skip reasons and each test's seconds."""
    result = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "failures": [], "skips": Counter(), "times": {}}
    if not path.is_file():
        return result
    for case in ET.parse(path).getroot().iter("testcase"):
        key = _key(case.get("classname", ""), case.get("name", ""))
        result["times"][key] = float(case.get("time", 0))
        if case.find("failure") is not None:
            result["failed"] += 1
            result["failures"].append(key)
        elif case.find("error") is not None:
            result["errors"] += 1
            result["failures"].append(key)
        elif case.find("skipped") is not None:
            result["skipped"] += 1
            result["skips"][(case.find("skipped").get("message") or "").strip()[:200]] += 1
        else:
            result["passed"] += 1
    return result


def _worker_env(index: int, scratch: Path, **more: str) -> dict:
    """The worker's environment: its number and its own temporary directory (`TMP`/`TEMP`, which `tempfile` and
    `std::filesystem::temp_directory_path` read), so no test meets another worker on a fixed temporary name."""
    temp = scratch / f"tmp{index}"
    temp.mkdir(parents=True, exist_ok=True)
    return dict(os.environ, VANTAGE_TEST_WORKER=str(index), TMP=str(temp), TEMP=str(temp), **more)


def _python_worker(index: int, ids: list[str], scratch: Path, extra_env: dict | None = None) -> tuple[subprocess.Popen, Path, Path]:
    args_file = scratch / f"w{index}.args"
    args_file.write_text("\n".join(ids) + "\n", encoding="utf-8")
    junit = scratch / f"w{index}.xml"
    env = _worker_env(index, scratch, **(extra_env or {}))
    log = scratch / f"w{index}.log"
    process = subprocess.Popen(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--basetemp", str(scratch / f"base{index}"),
         "--junitxml", str(junit), f"@{args_file}"],
        stdout=open(log, "w", encoding="utf-8"), stderr=subprocess.STDOUT, cwd=ROOT, env=env)
    return process, junit, log


def run_python(paths: list[str], workers: int) -> int:
    started = time.monotonic()
    ids = collect(paths)
    if not ids:
        print("run_tests: no test collected")
        return 1
    serial = [i for i in ids if any(i.startswith(prefix) for prefix in SERIAL)]
    parallel = [i for i in ids if i not in set(serial)]
    scratch = Path(tempfile.mkdtemp(prefix="vantage_run_tests_"))
    bins = [b for b in deal(parallel, workers, load_durations()) if b]
    runs = [_python_worker(n + 1, b, scratch) for n, b in enumerate(bins)]
    worker_seconds, totals = [], {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    failures: list[str] = []
    skips: Counter = Counter()
    times: dict[str, float] = {}
    logs: list[tuple[int, Path]] = []
    for n, (process, junit, log) in enumerate(runs, start=1):
        process.wait()
        worker_seconds.append(time.monotonic() - started)
        part = _read_junit(junit)
        for field in totals:
            totals[field] += part[field]
        failures += part["failures"]
        skips.update(part["skips"])
        times.update(part["times"])
        if process.returncode not in (0, 1) or part["failed"] + part["errors"] or not junit.is_file():
            logs.append((n, log))
    if serial:  # the serial tail: one process, after the parallel part
        for node in serial:
            reason = next(why for prefix, why in SERIAL.items() if node.startswith(prefix))
            print(f"serial tail: {node} ({reason})")
        process, junit, log = _python_worker(0, serial, scratch)
        process.wait()
        part = _read_junit(junit)
        for field in totals:
            totals[field] += part[field]
        failures += part["failures"]
        skips.update(part["skips"])
        times.update(part["times"])
        if part["failed"] + part["errors"] or not junit.is_file():
            logs.append((0, log))
    wall = time.monotonic() - started
    total_run = sum(totals.values())
    for key in failures:
        print(f"FAILED  {key}")
    for n, log in logs:
        print(f"--- worker {n} log tail ({log}) ---")
        print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]))
    for reason, count in skips.most_common():
        print(f"SKIPPED [{count}] {reason}")
    print(f"python: {totals['passed']} passed, {totals['failed']} failed, {totals['errors']} errors, "
          f"{totals['skipped']} skipped; collected {len(ids)}, run {total_run}")
    print(f"python: wall {wall:.1f} s; sum of per-worker seconds {sum(sum(p['times'].values()) for p in [{'times': times}]):.1f} "
          f"(workers {len(bins)})")
    if times:
        merged = load_durations()
        merged.update(times)
        DURATIONS.parent.mkdir(parents=True, exist_ok=True)
        DURATIONS.write_text(json.dumps(merged, indent=0, sort_keys=True), encoding="utf-8")
    shutil.rmtree(scratch, ignore_errors=True)
    bad = totals["failed"] + totals["errors"] > 0 or total_run != len(ids)
    if total_run != len(ids):
        print(f"run_tests: {len(ids)} collected but {total_run} run")
    return 1 if bad else 0


def run_gtest(workers: int) -> int:
    started = time.monotonic()
    if not GTEST_EXE.is_file():
        print(f"run_tests: {GTEST_EXE} is not built (build.bat -t gtest -p vs2026)")
        return 1
    listed = subprocess.run([str(GTEST_EXE), "--gtest_list_tests"], capture_output=True, text=True, cwd=GTEST_CWD)
    suite, count = "", 0
    for line in listed.stdout.splitlines():
        if line and not line.startswith(" "):
            suite = line
        elif line.strip():
            count += 1
    scratch = Path(tempfile.mkdtemp(prefix="vantage_run_gtest_"))
    processes = []
    for n in range(workers):
        env = _worker_env(n + 1, scratch, GTEST_TOTAL_SHARDS=str(workers), GTEST_SHARD_INDEX=str(n))
        log = scratch / f"g{n}.log"
        processes.append((subprocess.Popen([str(GTEST_EXE), f"--gtest_output=xml:{scratch / f'g{n}.xml'}"],
                                           stdout=open(log, "w", encoding="utf-8"), stderr=subprocess.STDOUT,
                                           cwd=GTEST_CWD, env=env), log, scratch / f"g{n}.xml"))
    totals = {"run": 0, "failed": 0, "skipped": 0}
    failures: list[str] = []
    for process, log, xml in processes:
        process.wait()
        if process.returncode != 0 and xml.is_file():
            print(f"--- gtest worker log tail, exit {process.returncode} ({log}) ---")
            print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]))
        if not xml.is_file():
            print(f"gtest worker produced no result (exit {process.returncode}):\n"
                  + "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]))
            totals["failed"] += 1
            continue
        root = ET.parse(xml).getroot()
        for case in root.iter("testcase"):
            totals["run"] += 1
            if case.find("failure") is not None:
                totals["failed"] += 1
                failures.append(f"{case.get('classname')}.{case.get('name')}")
            elif case.find("skipped") is not None or case.get("status") == "notrun":
                totals["skipped"] += 1
    wall = time.monotonic() - started
    for name in failures:
        print(f"FAILED  {name}")
    print(f"gtest: {totals['run'] - totals['failed'] - totals['skipped']} passed, {totals['failed']} failed, "
          f"{totals['skipped']} skipped; listed {count}, run {totals['run']}")
    print(f"gtest: wall {wall:.1f} s (shards {workers})")
    if totals["failed"] == 0 and totals["run"] == count:
        shutil.rmtree(scratch, ignore_errors=True)
    if totals["run"] != count:
        print(f"run_tests: {count} listed but {totals['run']} run")
    return 1 if totals["failed"] or totals["run"] != count else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 16))
    parser.add_argument("--python", nargs="+", metavar="PATH", help="pytest paths to run in parallel")
    parser.add_argument("--gtest", action="store_true", help="run simcore_tests.exe as N shards")
    args = parser.parse_args(argv)
    if not args.python and not args.gtest:
        parser.error("name --python <paths> and/or --gtest")
    code = 0
    if args.gtest:
        code |= run_gtest(args.workers)
    if args.python:
        code |= run_python(args.python, args.workers)
    return code


if __name__ == "__main__":
    sys.exit(main())
