# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""IMP-0374 / ANL-SW-68 (docs/v2/SIM_Implementation_Plan_v0.1.md WP-01) --
R-STYLE-1's file header block, mechanised. Every `.cpp`/`.hpp`/`.h`/`.py`
under this module's own tree carries `Copyright / Proprietary /
COMPONENT: SIM / @author` (Python, `#`-style) or `Copyright / Proprietary /
COMPONENT: SIM / @file / @brief / @author` (C++, `//`+`///`-style), per
`docs/file_header_template.md`. Extended in WP-03 to cover
`src/simcore/**` and `src/simengine/**` once they exist -- today they do
not, and this check says so rather than reporting a false PASS (Plan
WP-01's third Exit gate: a check that scanned zero must report SKIPPED).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent

# Excluded: generated/vendored/build trees, never authored here.
_EXCLUDE_DIR_NAMES = {
    "__pycache__", ".venv", "build", "dist", ".pytest_cache", ".git",
    "egg-info",
}

_PY_HEADER = re.compile(
    r"^# Copyright \(c\) .+\. All Rights Reserved\.\n"
    r"# Proprietary and Confidential\.\n"
    r"# COMPONENT: SIM\n"
    r"# @author .+\n"
)

_CPP_HEADER = re.compile(
    r"^// Copyright \(c\) .+\. All Rights Reserved\.\n"
    r"// Proprietary and Confidential\.\n"
    r"// COMPONENT: SIM\n"
    r"/// @file\n"
    r"/// @brief\n"
)


def _excluded(path: Path) -> bool:
    return any(part in _EXCLUDE_DIR_NAMES or part.endswith(".egg-info") for part in path.parts)


def _iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.suffix in suffixes and p.is_file() and not _excluded(p))


def check_python_headers(sim_root: Path = SIM_ROOT) -> tuple[list[str], int]:
    """Return (findings, files scanned)."""
    findings: list[str] = []
    files = [
        p for root in ("src", "scripts", "tests", "docs/v2/py")
        for p in _iter_files(sim_root / root, (".py",))
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not _PY_HEADER.match(text):
            findings.append(f"{path}: missing/malformed R-STYLE-1 header block")
    return findings, len(files)


def check_cpp_headers(sim_root: Path = SIM_ROOT) -> tuple[list[str], int]:
    """Return (findings, files scanned). `src/simcore/`, `src/simengine/`
    and `include/simcore/` do not exist until WP-03/WP-06 -- an empty scan
    is reported as such by the caller, never silently as PASS."""
    findings: list[str] = []
    files = [
        p for root in ("src/simcore", "src/simengine", "include/simcore")
        for p in _iter_files(sim_root / root, (".cpp", ".hpp", ".h"))
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not _CPP_HEADER.match(text):
            findings.append(f"{path}: missing/malformed R-STYLE-1 header block")
    return findings, len(files)


def main(argv: list[str] | None = None) -> int:
    py_findings, py_scanned = check_python_headers()
    cpp_findings, cpp_scanned = check_cpp_headers()

    for f in py_findings + cpp_findings:
        print(f)

    print(f"\npython: {'SKIPPED (0 files)' if py_scanned == 0 else f'{py_scanned} file(s) scanned'}")
    print(f"cpp:    {'SKIPPED (0 files -- src/simcore, src/simengine, include/simcore do not exist until WP-03/WP-06)' if cpp_scanned == 0 else f'{cpp_scanned} file(s) scanned'}")

    findings = py_findings + cpp_findings
    if findings:
        print(f"\n{len(findings)} header violation(s)")
        return 1
    print("check_headers: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
