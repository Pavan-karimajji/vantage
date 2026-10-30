# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""IMP-0374 / ANL-SW-68 (docs/v2/SIM_Implementation_Plan_v0.1.md WP-01) --
R-STYLE-1's file header block, mechanised. Every `.cpp`/`.hpp`/`.h`/`.py`
under this module's own tree carries `Copyright / Proprietary /
COMPONENT: VANTAGE / @author` (Python, `#`-style) or `Copyright / Proprietary /
COMPONENT: VANTAGE / @file / @brief / @author` (C++, `//`+`///`-style), per
`docs/file_header_template.md`; a file already present at the `seed-from-sim`
tag may still carry `COMPONENT: SIM` (inherited files are not mass re-headed). `src/simcore/**` and `src/simengine/**`
gained real content at `WP-03`/`WP-14`; a scan that finds none reports
`SKIPPED` rather than a false PASS (Plan WP-01's third Exit gate).
`scripts/build.py`, `build_gui.py` and `setup.py` are exempt (`R-BUILD-2`/`4`/`6`): byte-identical
across every component, so they cannot carry a per-component `COMPONENT:` token.
"""

from __future__ import annotations

import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Collection, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
SEED_TAG = "seed-from-sim"

# Excluded: generated/vendored/build trees, never authored here.
_EXCLUDE_DIR_NAMES = {
    "__pycache__", ".venv", "build", "dist", ".pytest_cache", ".git",
    "egg-info",
    # WP-05, DD-02: src/simcore/third_party/ -- a vendored single-header
    # library (nlohmann/json) carries its own upstream copyright/license,
    # never this project's header block.
    "third_party",
}

# R-BUILD-2: scripts/build.py is byte-identical across every component --
# it cannot carry a COMPONENT: VANTAGE token, because the same file also sits
# in df/vdy/sil_host/etc. with no per-component token at all. Not this
# check's exemption to invent: the file's own docstring already states
# "Physically identical across every component ... no component name or
# kind may appear in it."
#
# The same holds for the other two copy-distributed launchers, `scripts/build_gui.py` (R-BUILD-4) and
# `scripts/setup.py` (modules/toolchain/copy_files/scripts/): held identical by CPY-1, so a header with this
# module's COMPONENT token would make sim's copy differ from every other component's and fail CPY-1.
_EXCLUDE_FILES = {"scripts/build.py", "scripts/build_gui.py", "scripts/setup.py"}

_PY_HEADER = re.compile(
    r"^# Copyright \(c\) .+\. All Rights Reserved\.\n"
    r"# Proprietary and Confidential\.\n"
    r"# COMPONENT: (?P<token>VANTAGE|SIM)\n"
    r"# @author .+\n"
)

_CPP_HEADER = re.compile(
    r"^// Copyright \(c\) .+\. All Rights Reserved\.\n"
    r"// Proprietary and Confidential\.\n"
    r"// COMPONENT: (?P<token>VANTAGE|SIM)\n"
    r"/// @file\n"
    r"/// @brief\n"
)


@lru_cache(maxsize=None)
def read_seed_tree(root: Path = SIM_ROOT) -> frozenset[str]:
    """Paths of the tree at the seed tag, read once per run; empty (with one
    printed line) when the tag is missing, so `COMPONENT: SIM` is accepted nowhere."""
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", "--name-only", SEED_TAG],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        print(f"check_headers: {SEED_TAG} tag not found; COMPONENT: SIM accepted nowhere")
        return frozenset()
    return frozenset(done.stdout.splitlines())


def _header_ok(match: Optional[re.Match], path: Path, sim_root: Path, seed_files: Collection[str]) -> bool:
    if match is None:
        return False
    return match.group("token") == "VANTAGE" or path.relative_to(sim_root).as_posix() in seed_files


def _excluded(path: Path, sim_root: Path) -> bool:
    if any(part in _EXCLUDE_DIR_NAMES or part.endswith(".egg-info") or part.startswith(".venv-") for part in path.parts):
        return True
    return path.relative_to(sim_root).as_posix() in _EXCLUDE_FILES


def _iter_files(root: Path, suffixes: tuple[str, ...], sim_root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.rglob("*") if p.suffix in suffixes and p.is_file() and not _excluded(p, sim_root)
    )


def check_python_headers(
    sim_root: Path = SIM_ROOT, seed_files: Optional[Collection[str]] = None
) -> tuple[list[str], int]:
    """Return (findings, files scanned)."""
    if seed_files is None:
        seed_files = read_seed_tree(sim_root)
    findings: list[str] = []
    files = [
        p for root in ("src", "scripts", "tests", "docs/v2/py")
        for p in _iter_files(sim_root / root, (".py",), sim_root)
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not _header_ok(_PY_HEADER.match(text), path, sim_root, seed_files):
            findings.append(f"{path}: missing/malformed R-STYLE-1 header block")
    return findings, len(files)


def check_cpp_headers(
    sim_root: Path = SIM_ROOT, seed_files: Optional[Collection[str]] = None
) -> tuple[list[str], int]:
    """Return (findings, files scanned). `src/simcore/`, `src/simengine/`
    and `include/simcore/` do not exist until WP-03/WP-06 -- an empty scan
    is reported as such by the caller, never silently as PASS."""
    if seed_files is None:
        seed_files = read_seed_tree(sim_root)
    findings: list[str] = []
    files = [
        p for root in ("src/simcore", "src/simengine", "include/simcore")
        for p in _iter_files(sim_root / root, (".cpp", ".hpp", ".h"), sim_root)
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not _header_ok(_CPP_HEADER.match(text), path, sim_root, seed_files):
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
