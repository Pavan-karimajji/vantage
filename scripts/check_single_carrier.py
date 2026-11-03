# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""IMP-0090 / ANL-04 -- SYS-0074: the live measurement writer's calls are the one carrier of step values out
of the engine. A source scan over ``include/simcore/``, ``src/simcore/`` and ``src/simengine/`` for the retired
player transport: its names (``TransportPublisher``, ``SetTransportPublisher``, ``simEngineAttachTransport``,
``InProcessTransport``, ``SharedMemoryTransport``, ``ITransport``) and an include of its headers
(``transport.hpp``, ``transport_publisher.hpp``, ``transport_shm.hpp``). Comments and string literals are not
read, except on an ``#include`` line, whose header name is.

    check_single_carrier.py [--root <dir>] [--selftest]

One line per finding, ``<file>:<line>: <kind>: <source line>``; exit 1 on any. ``--selftest`` plants ANL-04 .c2
(a ``SetTransportPublisher`` call in ``src/simcore/abi/simcore.cpp``) and .c3 (an
``#include "simcore/transport_shm.hpp"`` in ``src/simcore/runner/cycle_loop.cpp``) in a temporary copy and
exits 1 unless each is reported with its file and line.
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

#: Relative to the root; every file below is scanned.
SCANNED: tuple[str, ...] = ("include/simcore", "src/simcore", "src/simengine")

_SUFFIXES = (".hpp", ".h", ".cpp")

_NAME = re.compile(
    r"\b(?:TransportPublisher|SetTransportPublisher|transport_publisher_?|simEngineAttachTransport|"
    r"InProcessTransport|SharedMemoryTransport|ITransport)\b"
)
_INCLUDE_LINE = re.compile(r"^\s*#\s*include\b")
_TRANSPORT_HEADER = re.compile(r'[<"][^>"]*\btransport(?:_publisher|_shm)?\.hpp[>"]')


def _blank(text: str) -> str:
    """The text with comments and string/char literals replaced by spaces, newlines kept, so a word in a comment
    or a message never counts and line numbers still match."""
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
        source = original[lineno - 1]
        if _INCLUDE_LINE.match(line) and _TRANSPORT_HEADER.search(source):
            findings.append(f"{shown}:{lineno}: transport include: {source.strip()}")
        elif _NAME.search(line):
            findings.append(f"{shown}:{lineno}: transport name: {source.strip()}")
    return findings


def check_single_carrier(root: Path = SIM_ROOT) -> list[str]:
    findings: list[str] = []
    for entry in SCANNED:
        target = root / entry
        if not target.is_dir():
            continue
        for path in sorted(target.rglob("*")):
            if path.is_file() and path.suffix in _SUFFIXES:
                findings.extend(_scan_file(path, path.relative_to(root).as_posix()))
    return findings


#: ANL-04 .c2 and .c3: (case, file, text appended to a copy of it).
PLANTS: tuple[tuple[str, str, str], ...] = (
    (
        "ANL-04 .c2 (a SetTransportPublisher call)",
        "src/simcore/abi/simcore.cpp",
        "\nnamespace {\nvoid planted_attach(simcore::runner::Runner* runner) { runner->SetTransportPublisher(nullptr); }\n}\n",
    ),
    (
        "ANL-04 .c3 (an include of the transport header)",
        "src/simcore/runner/cycle_loop.cpp",
        '\n#include "simcore/transport_shm.hpp"\n',
    ),
)


def _planted_findings(root: Path, relative: str, planted: str) -> list[str] | None:
    """The findings the plant adds to a temporary copy of the scanned tree, at or after its first line; None when
    ``relative`` is not in the tree."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp)
        for entry in SCANNED:
            source = root / entry
            if source.is_dir():
                shutil.copytree(source, copy / entry)
        target = copy / relative
        if not target.is_file():
            return None
        before = set(check_single_carrier(copy))
        first_planted_line = len(target.read_text(encoding="utf-8", errors="replace").splitlines()) + 1
        with target.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(planted)
        new = [f for f in check_single_carrier(copy) if f not in before]
        return [f for f in new if f.startswith(f"{relative}:") and int(f.split(":")[1]) >= first_planted_line]


def selftest(root: Path = SIM_ROOT) -> int:
    """Plants each violation in a temporary copy of the scanned tree; every one must be reported with its file and
    line, over and above what the unplanted copy reports."""
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
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANL-04: the live measurement writer is the one carrier of step values.")
    parser.add_argument("--root", type=Path, default=SIM_ROOT, help="the vantage module root (default: this one)")
    parser.add_argument("--selftest", action="store_true", help="plant ANL-04 .c2 and .c3 in a copy and prove each is reported")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest(args.root)
    findings = check_single_carrier(args.root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} use(s) of the retired player transport")
        return 1
    print("check_single_carrier: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
