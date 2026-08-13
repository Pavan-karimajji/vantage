# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""IMP-0415 / ANL-SW-76 (docs/v2/SIM_Implementation_Plan_v0.1.md WP-01) --
walks every writer `conf/artifact_kinds.yaml` names and diffs it against
the file: a writer function that has been renamed or deleted orphans its
kind's declaration, and (the case this exists for) a new writer added
without a declared kind is caught at the commit that adds it, not at
`WP-31` when `USE_CONSTRAINTS.md` is generated from whatever the file
happens to say by then.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
ARTIFACT_KINDS_YAML = SIM_ROOT / "conf" / "artifact_kinds.yaml"


def _function_exists(sim_root: Path, rel_path: str, func_name: str) -> bool:
    path = sim_root / rel_path
    if not path.is_file():
        return False
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == func_name:
            return True
    return False


def check_artifact_kinds(
    sim_root: Path = SIM_ROOT, kinds_yaml: Path = ARTIFACT_KINDS_YAML
) -> tuple[list[str], int]:
    """Return (findings, kinds checked)."""
    if not kinds_yaml.is_file():
        return [f"{kinds_yaml}: does not exist"], 0

    data = yaml.safe_load(kinds_yaml.read_text(encoding="utf-8")) or {}
    kinds = data.get("kinds", [])
    findings: list[str] = []

    for row in kinds:
        name = row.get("name", "<unnamed>")
        writers = row.get("writers", [])
        if not writers:
            findings.append(f"{name}: declared with no writers -- a kind nothing produces should not be listed")
            continue
        for writer in writers:
            if "::" not in writer:
                findings.append(f"{name}: writer '{writer}' is not 'path::function'")
                continue
            rel_path, func_name = writer.split("::", 1)
            if not _function_exists(sim_root, rel_path, func_name):
                findings.append(f"{name}: writer '{writer}' does not exist -- orphaned declaration")

    return findings, len(kinds)


def main(argv: list[str] | None = None) -> int:
    findings, checked = check_artifact_kinds()
    for f in findings:
        print(f)
    print(f"\n{checked} artifact kind(s) checked")
    if findings:
        print(f"{len(findings)} artifact-kind violation(s)")
        return 1
    print("check_artifact_kinds: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
