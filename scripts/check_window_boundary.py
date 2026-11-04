# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""IMP-0152 / ANL-08 -- SYS-0122: the launcher window holds no logic of its own. A scan of the syntax tree of
``src/adas_sim/launcher/window.py`` (comments and strings are not read) for

- a file access: ``open``, ``read_text``, ``write_text``, ``read_bytes``, ``write_bytes``, ``unlink``, ``mkdir``, ``copyfile``, ``rename``;
- a process start: any call on ``subprocess``, ``os.system``, ``os.spawn*``, ``os.exec*``, or an import of ``subprocess``;
- a rule of its own: a comparison with a mode name (``simulate``, ``measured``, ``off``, ``mixed``).

    check_window_boundary.py [--root <dir>] [--selftest]

One line per finding, ``<file>:<line>: <kind>``; exit 1 on any. ``--selftest`` plants ANL-08 .c2 -- a file read, a process start and a
mode comparison -- in a temporary copy and exits 1 unless each is reported with file and line.
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
WINDOW = "src/adas_sim/launcher/window.py"
_FILE_CALLS = {"open", "read_text", "write_text", "read_bytes", "write_bytes", "unlink", "mkdir", "copyfile", "rename"}
_MODES = {"simulate", "measured", "off", "mixed"}


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def check_window_boundary(root: Path = SIM_ROOT) -> list[str]:
    path = root / WINDOW
    if not path.is_file():
        return []
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            owner = node.func.value.id if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) else None
            if name in _FILE_CALLS:
                findings.append(f"{WINDOW}:{node.lineno}: a file access ({name})")
            if owner == "subprocess" or (owner == "os" and (name == "system" or name.startswith(("spawn", "exec")))):
                findings.append(f"{WINDOW}:{node.lineno}: a process start ({owner}.{name})")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(m.split(".")[0] == "subprocess" for m in modules):
                findings.append(f"{WINDOW}:{node.lineno}: a process start (import subprocess)")
        elif isinstance(node, ast.Compare):
            constants = [c.value for c in [node.left, *node.comparators] if isinstance(c, ast.Constant) and isinstance(c.value, str)]
            if any(value in _MODES for value in constants):
                findings.append(f"{WINDOW}:{node.lineno}: a rule of its own (a comparison with a mode name)")
    return findings


#: ANL-08 .c2: (what is planted, the text appended to window.py, the finding's kind).
PLANTS: tuple[tuple[str, str, str], ...] = (
    ("a file read", "\n\ndef _planted():\n    return open('x')\n", "a file access"),
    ("a process start", "\n\ndef _planted():\n    return subprocess.run(['x'])\n", "a process start"),
    ("a mode comparison", "\n\ndef _planted(mode):\n    return mode == 'measured'\n", "a rule of its own"),
)


def selftest(root: Path = SIM_ROOT) -> int:
    failed = 0
    for what, planted, kind in PLANTS:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            (copy / WINDOW).parent.mkdir(parents=True)
            shutil.copyfile(root / WINDOW, copy / WINDOW)
            text = (copy / WINDOW).read_text(encoding="utf-8") + planted
            (copy / WINDOW).write_text(text, encoding="utf-8", newline="\n")
            line = text.count("\n", 0, text.rindex("def _planted")) + 2
            hit = [f for f in check_window_boundary(copy) if f.startswith(f"{WINDOW}:{line}:") and kind in f]
        if hit:
            print(f"selftest ANL-08 .c2 ({what}): PASS -- reported {hit[0]}")
        else:
            print(f"selftest ANL-08 .c2 ({what}): FAIL -- the copy passes")
            failed += 1
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANL-08: the launcher window holds no logic of its own.")
    parser.add_argument("--root", type=Path, default=SIM_ROOT, help="the vantage module root (default: this one)")
    parser.add_argument("--selftest", action="store_true", help="plant ANL-08 .c2 in a copy and prove each is reported")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest(args.root)
    findings = check_window_boundary(args.root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} piece(s) of logic in the window")
        return 1
    print("check_window_boundary: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
