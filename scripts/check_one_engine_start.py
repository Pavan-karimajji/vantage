# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""IMP-0138 / ANL-07 -- SYS-0107, SYS-0108: one place starts ``simengine``, and only from a setup file just written. A source scan of
``src/adas_sim`` (the syntax tree, so comments and strings are not read) for

- a process start (``subprocess.run``/``Popen``/``call``/``check_call``/``check_output``, ``os.system``, ``os.spawn*``, ``os.exec*``)
  whose arguments name the engine -- ``simengine``, ``resolve_simengine_executable``, ``simengine_path`` -- anywhere but
  ``src/adas_sim/engine/bridge.py``; and
- a call of ``run_engine`` in a function that has not, on an earlier line, written its setup (``write_run_spec``, ``to_run_config``,
  ``emit_run_spec``, ``write_run_setup``, ``write_text``, ``write_bytes``, ``json.dump``).

    check_one_engine_start.py [--root <dir>] [--selftest]

One line per finding, ``<file>:<line>: <kind>``; exit 1 on any. ``--selftest`` plants ANL-07 .c2 (a start from a ``Selection`` argument)
and .c3 (a second process start naming ``simengine``) in a temporary copy and exits 1 unless each is reported with file and line.
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
SOURCE = "src/adas_sim"
BRIDGE = "src/adas_sim/engine/bridge.py"
_STARTS = {"run", "Popen", "call", "check_call", "check_output", "system", "startfile"}
_STARTS_PREFIX = ("spawn", "exec")
_ENGINE_WORDS = ("simengine", "resolve_simengine_executable")
_WRITES = {"write_run_spec", "write_run_setup", "to_run_config", "emit_run_spec", "write_text", "write_bytes", "dump"}


def _name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_process_start(call: ast.Call) -> bool:
    func = call.func
    if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
        return False
    owner = func.value.id
    return (owner == "subprocess" and func.attr in _STARTS) or (owner == "os" and (func.attr in _STARTS or func.attr.startswith(_STARTS_PREFIX)))


def _names_engine(call: ast.Call) -> bool:
    text = " ".join(ast.unparse(arg) for arg in [*call.args, *(k.value for k in call.keywords)]).lower()
    return any(word in text for word in _ENGINE_WORDS)


def check_one_engine_start(root: Path = SIM_ROOT) -> list[str]:
    findings: list[str] = []
    folder = root / SOURCE
    for path in sorted(folder.rglob("*.py")) if folder.is_dir() else []:
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and rel != BRIDGE and _is_process_start(node) and _names_engine(node):
                findings.append(f"{rel}:{node.lineno}: a process start naming the engine outside {BRIDGE}")
        for function in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)]
            for call in calls:
                if _name(call.func) != "run_engine":
                    continue
                if not any(_name(w.func) in _WRITES and w.lineno < call.lineno for w in calls if w is not call):
                    findings.append(f"{rel}:{call.lineno}: run_engine in {function.name} with no write of its setup before it")
    return findings


#: ANL-07 .c2 and .c3: (case, file, text appended to it).
PLANTS: tuple[tuple[str, str, str], ...] = (
    ("ANL-07 .c2 (a start from a Selection argument)", "src/adas_sim/launcher/write.py",
     "\n\ndef _planted(selection):\n    return run_engine(selection)\n"),
    ("ANL-07 .c3 (a second process start naming simengine)", "src/adas_sim/cli/resim.py",
     "\n\ndef _planted():\n    return subprocess.run([\"simengine\", \"x.json\"])\n"),
)


def selftest(root: Path = SIM_ROOT) -> int:
    failed = 0
    for case, relative, planted in PLANTS:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            shutil.copytree(root / SOURCE, copy / SOURCE, ignore=shutil.ignore_patterns("__pycache__"))
            target = copy / relative
            text = target.read_text(encoding="utf-8") + planted
            target.write_text(text, encoding="utf-8", newline="\n")
            line = text.count("\n", 0, text.rindex("def _planted")) + 2
            hit = [f for f in check_one_engine_start(copy) if f.startswith(f"{relative}:{line}:")]
        if hit:
            print(f"selftest {case}: PASS -- reported {hit[0]}")
        else:
            print(f"selftest {case}: FAIL -- the copy passes")
            failed += 1
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANL-07: one place starts simengine, from a file just written.")
    parser.add_argument("--root", type=Path, default=SIM_ROOT, help="the vantage module root (default: this one)")
    parser.add_argument("--selftest", action="store_true", help="plant ANL-07 .c2 and .c3 in a copy and prove each is reported")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest(args.root)
    findings = check_one_engine_start(args.root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} engine start(s) that break the rule")
        return 1
    print("check_one_engine_start: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
