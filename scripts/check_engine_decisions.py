# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""IMP-0037 / ANL-01 -- SYS-0017: the orchestrator and input selection decide
from the run setup and the samples' ``sig_header`` only. A source scan over
``src/simcore/orchestrator/``, ``src/simcore/runner/select_inputs.cpp`` and
``src/simcore/runner/read_ahead.cpp`` for a clock, thread-id or timer call and
for a payload parse (the only payload read is ``ReadSignalHeader``, which lives
in ``bus/`` and is outside the scan).

    check_engine_decisions.py [--root <dir>] [--selftest]

One line per finding, ``<file>:<line>: <kind>: <source line>``; exit 1 on any.
``--selftest`` plants ANL-01 .c2 (a ``std::chrono::steady_clock::now()`` in
``src/simcore/orchestrator/orchestrator.cpp``) and .c3 (a ``ParseFromArray`` in
``src/simcore/runner/select_inputs.cpp``) in a temporary copy and exits 1 unless
each is reported with its file and line.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent

#: Relative to the root; a directory is scanned whole, a file alone.
SCANNED: tuple[str, ...] = (
    "src/simcore/orchestrator",
    "src/simcore/runner/select_inputs.cpp",
    "src/simcore/runner/read_ahead.cpp",
)

_SUFFIXES = (".hpp", ".h", ".cpp")

_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "clock call",
        re.compile(
            r"\b(?:steady_clock|system_clock|high_resolution_clock|utc_clock|file_clock)\b"
            r"|::now\s*\("
            r"|\b(?:clock_gettime|gettimeofday|QueryPerformanceCounter|GetTickCount|GetTickCount64|timespec_get)\b"
            r"|\bstd::(?:clock|time)\s*\("
        ),
    ),
    (
        "thread-id call",
        re.compile(r"\bthis_thread\s*::\s*get_id\b|\bthread::id\b|\bget_id\s*\(|\bGetCurrentThreadId\b|\bpthread_self\b|\bgettid\b"),
    ),
    (
        "timer call",
        re.compile(
            r"\b(?:sleep_for|sleep_until|wait_for|wait_until|nanosleep|usleep|setitimer|timer_create|"
            r"timeSetEvent|SetTimer|CreateTimerQueueTimer)\b"
        ),
    ),
    (
        "payload parse",
        re.compile(r"\b(?:ParseFrom|ParsePartialFrom|MergeFrom|MergePartialFrom)\w*\s*\("),
    ),
)


def _blank(text: str) -> str:
    """The text with comments and string/char literals replaced by spaces, newlines kept, so a word in a
    comment or a message never counts and line numbers still match."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        two = text[i : i + 2]
        c = text[i]
        if two == "//":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif two == "/*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j]))
            i = j
        elif c == '"' or (c == "'" and not (i > 0 and text[i - 1].isalnum())):  # 100'000 is a number, not a char
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(c + " " * (j - i - 2) + c if j - i >= 2 else text[i:j])
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _scan_file(path: Path, shown: str) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    original = text.splitlines()
    findings: list[str] = []
    for lineno, line in enumerate(_blank(text).splitlines(), start=1):
        for kind, pattern in _RULES:
            if pattern.search(line):
                findings.append(f"{shown}:{lineno}: {kind}: {original[lineno - 1].strip()}")
    return findings


def check_engine_decisions(root: Path = SIM_ROOT) -> list[str]:
    findings: list[str] = []
    for entry in SCANNED:
        target = root / entry
        if target.is_dir():
            files = [p for p in sorted(target.rglob("*")) if p.is_file() and p.suffix in _SUFFIXES]
        elif target.is_file():
            files = [target]
        else:
            continue
        for path in files:
            findings.extend(_scan_file(path, path.relative_to(root).as_posix()))
    return findings


#: ANL-01 .c2 and .c3: (case, file, text appended to a copy of it).
PLANTS: tuple[tuple[str, str, str], ...] = (
    (
        "ANL-01 .c2 (clock call)",
        "src/simcore/orchestrator/orchestrator.cpp",
        "\nnamespace {\nauto planted_clock = std::chrono::steady_clock::now();\n}\n",
    ),
    (
        "ANL-01 .c3 (payload parse)",
        "src/simcore/runner/select_inputs.cpp",
        "\nnamespace {\nbool planted_parse(adas::common::CycleControl& m, const unsigned char* p, int n) {\n"
        "  return m.ParseFromArray(p, n);\n}\n}\n",
    ),
)


def selftest(root: Path = SIM_ROOT) -> int:
    """Plants each violation in a temporary copy of the scanned tree; every one must be reported with its file and
    line, over and above what the unplanted copy reports."""
    failed = 0
    for case, relative, planted in PLANTS:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            for entry in SCANNED:
                source = root / entry
                if source.is_dir():
                    shutil.copytree(source, copy / entry)
                elif source.is_file():
                    (copy / entry).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, copy / entry)
            target = copy / relative
            if not target.is_file():
                print(f"selftest {case}: FAIL -- {relative} is not in the tree")
                failed += 1
                continue
            before = set(check_engine_decisions(copy))
            first_planted_line = len(target.read_text(encoding="utf-8", errors="replace").splitlines()) + 2
            with target.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(planted)
            new = [f for f in check_engine_decisions(copy) if f not in before]
            hit = [f for f in new if f.startswith(f"{relative}:") and int(f.split(":")[1]) >= first_planted_line]
            if hit:
                print(f"selftest {case}: PASS -- reported {hit[0]}")
            else:
                print(f"selftest {case}: FAIL -- the copy passes")
                failed += 1
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANL-01: the engine's decisions read no clock and no payload.")
    parser.add_argument("--root", type=Path, default=SIM_ROOT, help="the vantage module root (default: this one)")
    parser.add_argument("--selftest", action="store_true", help="plant ANL-01 .c2 and .c3 in a copy and prove each is reported")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest(args.root)
    findings = check_engine_decisions(args.root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} decision(s) read a clock, a thread id, a timer or a payload")
        return 1
    print("check_engine_decisions: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
