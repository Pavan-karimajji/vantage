# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""IMP-0130 / ANL-09 -- SYS-0130: the scenario script writes a recording only through the one Python writer. A source scan of
``src/adas_sim/scenario`` for a call of any recording writer but ``McapRecorder``: ``McapWriter`` or the ``mcap`` library's
``Writer``. Comments and string literals are not read (the scan walks the syntax tree).

    check_one_recording_writer.py [--root <dir>] [--selftest]

One line per finding, ``<file>:<line>: <call>``; exit 1 on any. ``--selftest`` plants ANL-09 .c2 (an ``mcap.McapWriter(``
call) in a temporary copy and exits 1 unless it is reported with file and line.
"""

from __future__ import annotations

import argparse
import ast
import shutil
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
SCENARIO_DIR = "src/adas_sim/scenario"
FORBIDDEN = {"McapWriter", "Writer"}


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def check_one_recording_writer(root: Path = SIM_ROOT) -> list[str]:
    folder = root / SCENARIO_DIR
    findings: list[str] = []
    for path in sorted(folder.glob("*.py")) if folder.is_dir() else []:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node) in FORBIDDEN:
                findings.append(f"{SCENARIO_DIR}/{path.name}:{node.lineno}: {_call_name(node)}(")
    return findings


def selftest(root: Path = SIM_ROOT) -> int:
    """ANL-09 .c2: a planted ``mcap.McapWriter(`` call in a temporary copy of the scenario folder is reported with its line."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp)
        target = copy / SCENARIO_DIR
        shutil.copytree(root / SCENARIO_DIR, target, ignore=shutil.ignore_patterns("__pycache__"))
        planted = target / "write.py"
        text = planted.read_text(encoding="utf-8") + "\n\ndef _planted():\n    return mcap.McapWriter(None)\n"
        planted.write_text(text, encoding="utf-8", newline="\n")
        line = text.count("\n", 0, text.index("mcap.McapWriter(")) + 1
        hit = [f for f in check_one_recording_writer(copy) if f.startswith(f"{SCENARIO_DIR}/write.py:{line}:")]
    if hit:
        print(f"selftest ANL-09 .c2: PASS -- reported {hit[0]}")
        return 0
    print("selftest ANL-09 .c2: FAIL -- the copy passes")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANL-09: one recording writer in the scenario script.")
    parser.add_argument("--root", type=Path, default=SIM_ROOT, help="the vantage module root (default: this one)")
    parser.add_argument("--selftest", action="store_true", help="plant ANL-09 .c2 in a copy and prove it is reported")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest(args.root)
    findings = check_one_recording_writer(args.root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} recording writer call(s) besides McapRecorder")
        return 1
    print("check_one_recording_writer: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
