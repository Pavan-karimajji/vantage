# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""IMP-0113 / ANL-06 -- SYS-0104: the supervisor runs no component and writes nothing but the seal. A source scan
of the bodies of ``RunWithSupervision``, ``ClassifyWorkerEnd``, ``HoldLiveMeas``, ``SealAfterWorker`` and
``WriteCrashReproducer`` in ``src/simengine/main.cpp`` for a call of ``Component::Exec``, ``RunStage``,
``liveMeasStep`` or ``liveMeasClose``. Comments and string literals are not read.

    check_supervisor_boundary.py [--root <dir>] [--selftest]

One line per finding, ``<file>:<line>: <kind>: <source line>``; exit 1 on any. ``--selftest`` plants ANL-06 .c2 (a
``liveMeasStep`` call) and .c3 (a ``Component::Exec`` call) in ``RunWithSupervision`` of a temporary copy and exits
1 unless each is reported with its file and line.
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

SUPERVISOR_FILE = "src/simengine/main.cpp"
SUPERVISOR_FUNCTIONS = ("RunWithSupervision", "ClassifyWorkerEnd", "HoldLiveMeas", "SealAfterWorker", "WriteCrashReproducer")
_FORBIDDEN = re.compile(r"\b(?:Component\s*::\s*Exec|RunStage|liveMeasStep|liveMeasClose)\b")


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
        elif c == '"' or (c == "'" and not (i > 0 and text[i - 1].isalnum())):
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


def _body_span(blank: str, name: str) -> list[tuple[int, int]]:
    """The (start, end) offsets of every definition body of function ``name`` in the blanked text."""
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"\b" + re.escape(name) + r"\s*\(", blank):
        depth, i = 1, match.end()
        while i < len(blank) and depth:
            depth += {"(": 1, ")": -1}.get(blank[i], 0)
            i += 1
        tail = re.match(r"\s*(?:const\s*)?(?:noexcept\s*)?\{", blank[i:])
        if not tail:  # a call or a declaration, not a definition
            continue
        start = i + tail.end() - 1
        depth, j = 0, start
        while j < len(blank):
            depth += {"{": 1, "}": -1}.get(blank[j], 0)
            j += 1
            if depth == 0:
                break
        spans.append((start, j))
    return spans


def check_supervisor_boundary(root: Path = SIM_ROOT) -> list[str]:
    path = root / SUPERVISOR_FILE
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    original = text.splitlines()
    blank = _blank(text)
    findings: list[str] = []
    seen: set[int] = set()
    for name in SUPERVISOR_FUNCTIONS:
        for start, end in _body_span(blank, name):
            for hit in _FORBIDDEN.finditer(blank, start, end):
                lineno = blank.count("\n", 0, hit.start()) + 1
                if lineno in seen:
                    continue
                seen.add(lineno)
                kind = re.sub(r"\s+", "", hit.group(0))
                findings.append(f"{SUPERVISOR_FILE}:{lineno}: {kind} in {name}: {original[lineno - 1].strip()}")
    return findings


#: ANL-06 .c2 and .c3: (case, text planted at the top of RunWithSupervision's body).
PLANTS: tuple[tuple[str, str], ...] = (
    ("ANL-06 .c2 (a liveMeasStep call)", "  liveMeasStep(handle, 0, 0, nullptr, 0, nullptr, 0);\n"),
    ("ANL-06 .c3 (a Component::Exec call)", "  simcore::module_host::Component::Exec(component, 0);\n"),
)
_ANCHOR = re.compile(r"SimExitCode RunWithSupervision\(const Args& args\) \{\n")


def selftest(root: Path = SIM_ROOT) -> int:
    """Plants each violation at the top of ``RunWithSupervision`` in a temporary copy; each must be reported with its
    file and line."""
    failed = 0
    source = root / SUPERVISOR_FILE
    for case, planted in PLANTS:
        text = source.read_text(encoding="utf-8", errors="replace") if source.is_file() else ""
        anchor = _ANCHOR.search(text)
        if not anchor:
            print(f"selftest {case}: FAIL -- RunWithSupervision is not in {SUPERVISOR_FILE}")
            failed += 1
            continue
        planted_line = text.count("\n", 0, anchor.end()) + 1
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            (copy / SUPERVISOR_FILE).parent.mkdir(parents=True)
            (copy / SUPERVISOR_FILE).write_text(text[: anchor.end()] + planted + text[anchor.end() :], encoding="utf-8", newline="\n")
            hit = [f for f in check_supervisor_boundary(copy) if f.startswith(f"{SUPERVISOR_FILE}:{planted_line}:")]
        if hit:
            print(f"selftest {case}: PASS -- reported {hit[0]}")
        else:
            print(f"selftest {case}: FAIL -- the copy passes")
            failed += 1
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANL-06: the supervisor runs no component and writes only the seal.")
    parser.add_argument("--root", type=Path, default=SIM_ROOT, help="the vantage module root (default: this one)")
    parser.add_argument("--selftest", action="store_true", help="plant ANL-06 .c2 and .c3 in a copy and prove each is reported")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest(args.root)
    findings = check_supervisor_boundary(args.root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} forbidden call(s) in the supervisor")
        return 1
    print("check_supervisor_boundary: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
