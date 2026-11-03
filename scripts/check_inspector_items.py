# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""IMP-0102 / ANL-05 -- SYS-0087: the inspector holds no stage name and no port name of its own, so it finds an
item a topology adds without a source change. A scan of ``src/inspector/`` for a string literal that names one:
a dotted ``<stage>.<port>`` (two identifiers joined by one dot) or a name of the lab's catalogue (a source or a
component of ``vantage-lab/catalogue/*.yaml``). ``#include`` lines are not read, nor are comments.

    check_inspector_items.py [--root <dir>] [--catalogue <dir>] [--selftest]

One line per finding, ``<file>:<line>: <kind>: <source line>``; exit 1 on any. The catalogue defaults to
``../vantage-lab/catalogue`` beside the module; when it is not there a line says so and only the dotted form is
checked. ``--selftest`` plants ANL-05 .c2 (a ``"B.refSync"`` literal in ``src/inspector/check.cpp``) in a
temporary copy and exits 1 unless it is reported with its file and line.
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
DEFAULT_CATALOGUE = SIM_ROOT.parent / "vantage-lab" / "catalogue"

SCANNED = "src/inspector"
_SUFFIXES = (".hpp", ".h", ".cpp")
_DOTTED = re.compile(r"^[A-Za-z_]\w*\.[A-Za-z_]\w*$")
_INCLUDE_LINE = re.compile(r"^\s*#\s*include\b")
_SECTION = re.compile(r"^(\w+):")
_ENTRY = re.compile(r"^\s*-\s*(?:\{\s*)?name:\s*([A-Za-z_]\w*)")


def catalogue_names(catalogue: Path) -> set[str]:
    """The names of the sources and components of every topology file in ``catalogue``."""
    names: set[str] = set()
    for path in sorted(catalogue.glob("*.yaml")):
        section = ""
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            head = _SECTION.match(line)
            if head:
                section = head.group(1)
                continue
            entry = _ENTRY.match(line)
            if entry and section in ("sources", "components"):
                names.add(entry.group(1))
    return names


def string_literals(text: str) -> list[tuple[int, str]]:
    """Every string literal of the C++ text as (line, contents), comments skipped."""
    found: list[tuple[int, str]] = []
    i, n, line = 0, len(text), 1
    while i < n:
        two = text[i : i + 2]
        c = text[i]
        if two == "//":
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif two == "/*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += text.count("\n", i, j)
            i = j
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"' and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            found.append((line, text[i + 1 : j]))
            i = min(j + 1, n)
        elif c == "'" and not (i > 0 and text[i - 1].isalnum()):
            j = i + 1
            while j < n and text[j] != "'" and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            i = min(j + 1, n)
        else:
            if c == "\n":
                line += 1
            i += 1
    return found


def check_inspector_items(root: Path = SIM_ROOT, names: set[str] | None = None) -> list[str]:
    names = names or set()
    findings: list[str] = []
    target = root / SCANNED
    if not target.is_dir():
        return findings
    for path in sorted(target.rglob("*")):
        if not (path.is_file() and path.suffix in _SUFFIXES):
            continue
        shown = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for lineno, literal in string_literals(text):
            source = lines[lineno - 1] if lineno <= len(lines) else ""
            if _INCLUDE_LINE.match(source):
                continue
            if _DOTTED.match(literal):
                findings.append(f"{shown}:{lineno}: stage.port literal: {source.strip()}")
            elif literal in names:
                findings.append(f"{shown}:{lineno}: catalogue name literal: {source.strip()}")
    return findings


#: ANL-05 .c2: (case, file, text appended to a copy of it).
PLANTS: tuple[tuple[str, str, str], ...] = (
    (
        "ANL-05 .c2 (a \"B.refSync\" literal in check.cpp)",
        "src/inspector/check.cpp",
        '\nnamespace {\nconst char* const kPlanted = "B.refSync";\n}\n',
    ),
)


def selftest(root: Path = SIM_ROOT, names: set[str] | None = None) -> int:
    """Plants each violation in a temporary copy of ``src/inspector``; each must be reported with file and line, over
    and above what the unplanted copy reports."""
    failed = 0
    for case, relative, planted in PLANTS:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            if not (root / SCANNED).is_dir():
                print(f"selftest {case}: FAIL -- {SCANNED} is not in the tree")
                failed += 1
                continue
            shutil.copytree(root / SCANNED, copy / SCANNED)
            target = copy / relative
            before = set(check_inspector_items(copy, names))
            first_planted_line = len(target.read_text(encoding="utf-8", errors="replace").splitlines()) + 1
            with target.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(planted)
            new = [
                f
                for f in check_inspector_items(copy, names)
                if f not in before and f.startswith(f"{relative}:") and int(f.split(":")[1]) >= first_planted_line
            ]
        if new:
            print(f"selftest {case}: PASS -- reported {new[0]}")
        else:
            print(f"selftest {case}: FAIL -- the copy passes")
            failed += 1
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANL-05: the inspector holds no stage or port name.")
    parser.add_argument("--root", type=Path, default=SIM_ROOT, help="the vantage module root (default: this one)")
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE, help="the lab's catalogue folder")
    parser.add_argument("--selftest", action="store_true", help="plant ANL-05 .c2 in a copy and prove it is reported")
    args = parser.parse_args(argv)
    names: set[str] = set()
    if args.catalogue.is_dir():
        names = catalogue_names(args.catalogue)
    else:
        print(f"check_inspector_items: no catalogue at {args.catalogue}; only the dotted form is checked")
    if args.selftest:
        return selftest(args.root, names)
    findings = check_inspector_items(args.root, names)
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} stage or port name(s) in src/inspector")
        return 1
    print("check_inspector_items: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
