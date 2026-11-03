# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""IMP-0037 / ANL-01 -- SYS-0017: the orchestrator and input selection decide
only from the run setup, ``sig_header``s and the two contract messages that
drive them: the recorded ``refSync`` (``adas::common::RefSync``) for selection
and the recorded control (``adas::common::CycleControl``) for RESTART. A source
scan over ``src/simcore/orchestrator/``, ``src/simcore/runner/select_inputs.cpp``
and ``src/simcore/runner/read_ahead.cpp`` for a clock, thread-id or timer call
and for a parse of any other message type (``ReadSignalHeader``, which lives in
``bus/``, is outside the scan).

A parse (``ParseFrom*``, ``ParsePartialFrom*``, ``MergeFrom*``, ``MergePartialFrom*``)
is allowed exactly when the object it is called on is declared, in the same file,
as one of those two types. Any other type, or a call whose object the scan cannot
name or find declared, is a finding. There is no per-line marker.

    check_engine_decisions.py [--root <dir>] [--selftest]

One line per finding, ``<file>:<line>: <kind>: <source line>``; exit 1 on any.
``--selftest`` plants ANL-01 .c2 (a ``std::chrono::steady_clock::now()`` in
``src/simcore/orchestrator/orchestrator.cpp``) and .c3 (an
``adas::common::VehDyn`` parsed with ``ParseFromArray`` in
``src/simcore/runner/select_inputs.cpp``) in a temporary copy and exits 1 unless
each is reported with its file and line; it also plants a parse of an allowed
type and exits 1 if that is reported.
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
)

#: A parse of a payload, and the same call on a plain name (`ego.ParseFromArray(`, `ego->ParseFromArray(`).
_PARSE = re.compile(r"\b(?:ParseFrom|ParsePartialFrom|MergeFrom|MergePartialFrom)\w*\s*\(")
_PARSE_ON = re.compile(
    r"(?<![\w.>)\]])(\w+)\s*(?:\.|->)\s*(?:ParseFrom|ParsePartialFrom|MergeFrom|MergePartialFrom)\w*\s*\("
)

#: The two messages a decision may parse (SYS-0017).
ALLOWED_TYPES: tuple[str, ...] = ("adas::common::RefSync", "adas::common::CycleControl")


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


def _declared_allowed(blanked: str, name: str) -> bool:
    """True when ``name`` is declared in this file as one of ``ALLOWED_TYPES`` (a variable, a reference or a pointer)."""
    types = "|".join(re.escape(t) for t in ALLOWED_TYPES)
    return re.search(rf"\b(?:{types})\b[\s&*]*(?:const\b\s*)?{re.escape(name)}\b", blanked) is not None


def _unallowed_parse(blanked: str, line: str) -> bool:
    """True when ``line`` holds a parse that is not on an object declared as an allowed type."""
    calls = _PARSE.findall(line)
    if not calls:
        return False
    on = _PARSE_ON.findall(line)
    return len(on) != len(calls) or not all(_declared_allowed(blanked, name) for name in on)


def _scan_file(path: Path, shown: str) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    original = text.splitlines()
    blanked = _blank(text)
    findings: list[str] = []
    for lineno, line in enumerate(blanked.splitlines(), start=1):
        for kind, pattern in _RULES:
            if pattern.search(line):
                findings.append(f"{shown}:{lineno}: {kind}: {original[lineno - 1].strip()}")
        if _unallowed_parse(blanked, line):
            findings.append(f"{shown}:{lineno}: payload parse: {original[lineno - 1].strip()}")
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
        "ANL-01 .c3 (payload parse of another type)",
        "src/simcore/runner/select_inputs.cpp",
        "\nnamespace {\nbool planted_parse(const unsigned char* p, int n) {\n"
        "  adas::common::VehDyn ego;\n  return ego.ParseFromArray(p, n);\n}\n}\n",
    ),
)

#: A parse of an allowed type, which must NOT be reported (the refSync is parsed for selection).
ALLOWED_PLANT: tuple[str, str, str] = (
    "ANL-01 (allowed parse of RefSync is not reported)",
    "src/simcore/runner/select_inputs.cpp",
    "\nnamespace {\nbool planted_allowed_parse(const unsigned char* p, int n) {\n"
    "  adas::common::RefSync ref_sync;\n  return ref_sync.ParseFromArray(p, n);\n}\n}\n",
)


def _planted_findings(root: Path, relative: str, planted: str) -> list[str] | None:
    """The findings the plant adds to a temporary copy of the scanned tree (at or after its first line); None when
    ``relative`` is not in the tree."""
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
            return None
        before = set(check_engine_decisions(copy))
        first_planted_line = len(target.read_text(encoding="utf-8", errors="replace").splitlines()) + 2
        with target.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(planted)
        new = [f for f in check_engine_decisions(copy) if f not in before]
        return [f for f in new if f.startswith(f"{relative}:") and int(f.split(":")[1]) >= first_planted_line]


def selftest(root: Path = SIM_ROOT) -> int:
    """Plants each violation in a temporary copy of the scanned tree; every one must be reported with its file and
    line, over and above what the unplanted copy reports. A parse of an allowed type must not be."""
    failed = 0
    for case, relative, planted in PLANTS:
        hit = _planted_findings(root, relative, planted)
        if hit is None:
            print(f"selftest {case}: FAIL -- {relative} is not in the tree")
            failed += 1
        elif hit:
            print(f"selftest {case}: PASS -- reported {hit[0]}")
        else:
            print(f"selftest {case}: FAIL -- the copy passes")
            failed += 1
    case, relative, planted = ALLOWED_PLANT
    hit = _planted_findings(root, relative, planted)
    if hit is None:
        print(f"selftest {case}: FAIL -- {relative} is not in the tree")
        failed += 1
    elif hit:
        print(f"selftest {case}: FAIL -- reported {hit[0]}")
        failed += 1
    else:
        print(f"selftest {case}: PASS -- not reported")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANL-01: the engine's decisions read no clock and no payload but RefSync and CycleControl.")
    parser.add_argument("--root", type=Path, default=SIM_ROOT, help="the vantage module root (default: this one)")
    parser.add_argument("--selftest", action="store_true", help="plant ANL-01 .c2 and .c3 in a copy and prove each is reported, and an allowed parse is not")
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
