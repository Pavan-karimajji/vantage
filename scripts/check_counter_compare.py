# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""IMP-0038 / ANL-02 -- SYS-0031: the engine compares ``measurement_counter`` and
``cycle_counter`` values only through a distance. A source scan over
``include/simcore/`` and ``src/simcore/`` for ``==``, ``!=``, ``<``, ``>``, ``<=``
or ``>=`` with an operand that names either counter.

An operand that is the result of ``counterDistance(...)`` or
``MeasurementCounterDistance(...)`` is a distance, not a counter: those calls (and
the counters inside their arguments) are taken out of the operand before it is
looked at, so comparing a distance is allowed.

    check_counter_compare.py [--root <dir>] [--selftest]

One line per finding, ``<file>:<line>: <operator> on <counter>: <source line>``;
exit 1 on any. ``--selftest`` plants ANL-02 .c2 (a ``<`` in
``src/simcore/bus/sample_buffer.cpp``) and .c3 (a ``==`` in
``src/simcore/orchestrator/orchestrator.cpp``) in a temporary copy and exits 1
unless each is reported with its file and line.

A comparison operator is read as one with whitespace on both sides (the shared
``.clang-format`` writes every comparison so and every template bracket without),
which keeps ``std::vector<T>`` and ``static_cast<T>(x)`` out of the scan.
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

DEFAULT_ROOTS: tuple[str, ...] = ("include/simcore", "src/simcore")

_SUFFIXES = (".hpp", ".h", ".cpp")

_COUNTER = re.compile(r"\b(measurement_counter|cycle_counter)\b")
_COMPARE = re.compile(r"(?<=\s)(==|!=|<=|>=|<|>)(?=\s)")
_DISTANCE_CALL = re.compile(r"\b(?:[A-Za-z_]\w*::)*(?:counterDistance|MeasurementCounterDistance)\s*\(")

# Where an operand ends: at depth 0, one of these.
_STOPS = ";{},?"


def _blank(text: str) -> str:
    """The text with comments and string/char literals replaced by spaces, newlines kept."""
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


def _left_operand(text: str, end: int) -> str:
    """The operand ending just before ``end``: back to an unmatched opening bracket, a ``;{},?``, ``&&``, ``||``,
    a single ``=`` or a ``return``."""
    depth = 0
    i = end - 1
    while i >= 0:
        c = text[i]
        if c in ")]":
            depth += 1
        elif c in "([":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0:
            if c in _STOPS:
                break
            if c in "&|" and i > 0 and text[i - 1] == c:
                break
            if c == "=" and text[i - 1 : i] not in ("=", "!", "<", ">") and text[i + 1 : i + 2] != "=":
                break
        i -= 1
    operand = text[i + 1 : end]
    return re.sub(r"^\s*(?:return|case|else)\b", "", operand)


def _right_operand(text: str, start: int) -> str:
    """The operand starting at ``start``: forward to an unmatched closing bracket, a ``;{},?``, ``&&``, ``||``, a
    single ``=`` or another comparison."""
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c in "([":
            depth += 1
        elif c in ")]":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0:
            if c in _STOPS:
                break
            if c in "&|" and text[i + 1 : i + 2] == c:
                break
            if c == "=" and text[i - 1 : i] not in ("=", "!", "<", ">") and text[i + 1 : i + 2] != "=":
                break
            if _COMPARE.match(text, i):
                break
        i += 1
    return text[start:i]


def _without_distances(operand: str) -> str:
    """The operand with every ``counterDistance(...)`` / ``MeasurementCounterDistance(...)`` call removed."""
    while True:
        match = _DISTANCE_CALL.search(operand)
        if match is None:
            return operand
        depth = 1
        i = match.end()
        while i < len(operand) and depth:
            depth += {"(": 1, ")": -1}.get(operand[i], 0)
            i += 1
        operand = operand[: match.start()] + " " + operand[i:]


def _scan_file(path: Path, shown: str) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    original = text.splitlines()
    blanked = _blank(text)
    findings: list[str] = []
    for match in _COMPARE.finditer(blanked):
        left = _without_distances(_left_operand(blanked, match.start()))
        right = _without_distances(_right_operand(blanked, match.end()))
        named = _COUNTER.search(left) or _COUNTER.search(right)
        if named:
            lineno = blanked.count("\n", 0, match.start()) + 1
            findings.append(f"{shown}:{lineno}: {match.group(1)} on {named.group(1)}: {original[lineno - 1].strip()}")
    return findings


def check_counter_compare(root: Path = SIM_ROOT, roots: tuple[str, ...] = DEFAULT_ROOTS) -> list[str]:
    findings: list[str] = []
    for entry in roots:
        target = root / entry
        if not target.is_dir():
            continue
        for path in sorted(target.rglob("*")):
            if path.is_file() and path.suffix in _SUFFIXES:
                findings.extend(_scan_file(path, path.relative_to(root).as_posix()))
    return findings


#: ANL-02 .c2 and .c3: (case, file, text appended to a copy of it).
PLANTS: tuple[tuple[str, str, str], ...] = (
    (
        "ANL-02 .c2 (<)",
        "src/simcore/bus/sample_buffer.cpp",
        "\nstatic bool PlantedBefore(const Sample& a, const Sample& b) {\n"
        "  return a.measurement_counter < b.measurement_counter;\n}\n",
    ),
    (
        "ANL-02 .c3 (==)",
        "src/simcore/orchestrator/orchestrator.cpp",
        "\nstatic bool PlantedSame(const Sample& a, const Sample& b) {\n"
        "  return a.measurement_counter == b.measurement_counter;\n}\n",
    ),
)


def selftest(root: Path = SIM_ROOT) -> int:
    """Plants each violation in a temporary copy of the scanned tree; every one must be reported with its file and
    line, over and above what the unplanted copy reports."""
    failed = 0
    for case, relative, planted in PLANTS:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            for entry in DEFAULT_ROOTS:
                if (root / entry).is_dir():
                    shutil.copytree(root / entry, copy / entry)
            target = copy / relative
            if not target.is_file():
                print(f"selftest {case}: FAIL -- {relative} is not in the tree")
                failed += 1
                continue
            before = set(check_counter_compare(copy))
            first_planted_line = len(target.read_text(encoding="utf-8", errors="replace").splitlines()) + 2
            with target.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(planted)
            new = [f for f in check_counter_compare(copy) if f not in before]
            hit = [f for f in new if f.startswith(f"{relative}:") and int(f.split(":")[1]) >= first_planted_line]
            if hit:
                print(f"selftest {case}: PASS -- reported {hit[0]}")
            else:
                print(f"selftest {case}: FAIL -- the copy passes")
                failed += 1
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANL-02: counters are compared only through a distance.")
    parser.add_argument("--root", type=Path, default=SIM_ROOT, help="the vantage module root (default: this one)")
    parser.add_argument("--selftest", action="store_true", help="plant ANL-02 .c2 and .c3 in a copy and prove each is reported")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest(args.root)
    findings = check_counter_compare(args.root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} comparison(s) applied to a counter")
        return 1
    print("check_counter_compare: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
