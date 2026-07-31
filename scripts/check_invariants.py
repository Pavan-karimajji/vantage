# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""GT-1, GT-2, GT-3, GT-6, GT-11 (docs/sim_implementation_plan.md §2), as one
script run by hand at the end of every stage and exercised by UT-A1-3 -- the
check is tested, not trusted. Every finding names the file, the line and the
gate.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_ROOT = SCRIPT_DIR.parent
SUPERPROJECT_ROOT = SIM_ROOT.parent.parent
SRC_ROOT = SIM_ROOT / "src" / "adas_sim"

# GT-1: R-SIM-1's grep, `\b(aeb|bsd|lca|acc|ldw|lka)\b`, run over modules/sim/src.
#
# Finding: a plain `\b...\b` word-boundary treats `_` as a word character, so
# it does NOT match a banned token embedded in a snake_case/ALL_CAPS
# identifier -- e.g. `BSD_SENSOR_0_RANGE_MAX_CAR_M` (exactly R-NAME-3's own
# calibration-key shape) or `bsd_zone_width_m` would slip through undetected,
# which is precisely the shape a leaked function name would take. Verified:
# `grep -niE '\b(bsd)\b'` does not match a file containing only
# `BSD_ZONE_WIDTH_M = 2.0`. Lookaround on alnum (not \w) makes `_` a boundary
# too, so the token is still isolated from an unrelated longer word ("access"
# does not match "acc") while catching the underscore-prefixed case R-SIM-1
# exists to prevent.
_FUNCTION_TOKENS = re.compile(
    r"(?<![A-Za-z0-9])(aeb|bsd|lca|acc|ldw|lka)(?![A-Za-z0-9])", re.IGNORECASE
)

# GT-2: a layer provider (modules/*/sim/layers/) may not import a renderer.
_RENDERER_IMPORTS = ("cv2", "matplotlib", "PySide6", "foxglove")

# GT-3: a literal vehicle/sensor dimension, outside model/. Heuristic: a float
# literal assigned to a name carrying a dimension word -- real geometry always
# comes from resolved YAML (R-SIM-3), never a module constant. Two refinements,
# both found as false positives against modules/df/sim/layers/common.py:
#   - `(?!\w*_px)` excludes width_px/offset_px -- R-SIM-2's one sanctioned
#     pixel exception (legibility, not physics; never meant to come from YAML).
#   - the trailing `(?!\s*[*+\-/%])\s*[,)\n]` excludes a number that is itself
#     an operand of an expression (`width_m=2.0 * ego.half_width_m`), where
#     the "2.0" is a coefficient on a calibration-derived value, not a literal
#     dimension standing alone.
_DIMENSION_ASSIGNMENT = re.compile(
    r"\b(width|length|height|wheelbase|overhang|half_width|range_m|fov)(?!\w*_px)\w*\s*[:=]\s*-?\d+\.\d+"
    r"(?!\s*[*+\-/%])\s*[,)\n]"
)

# GT-6: the framework may not import a component or generated protobuf bindings.
_COMPONENT_IMPORT = re.compile(r"^\s*(?:from|import)\s+modules\.\w+\b")

# GT-11: a plug-in's own `requires=` entry or `.port(...)` call naming a
# dotted, three-plus-segment string is a spelled stage name (R-SIM-21) --
# `self.<port>` (component-relative) and `source.<name>` (the reserved
# world-model prefix, contracts/pipeline.py's own grammar) are exempt.
# Only the `requires=(...)`/`.port(...)` ARGUMENT is scanned, never the
# whole line -- `@layer_provider("df.common.objects", ..., requires=(...))`
# has its own three-segment layer id on the same line, which is not a port
# reference at all.
_QUOTED_DOTTED_REF = re.compile(r'''["']([A-Za-z_]\w*(?:\.[A-Za-z_]\w*){2,})["']''')
_REQUIRES_ARG = re.compile(r"requires\s*=\s*[\(\[]([^)\]]*)[\)\]]")
_PORT_CALL_ARG = re.compile(r"\.port\(([^)]*)\)")
_GT11_EXEMPT_PREFIXES = ("self.", "source.")

# GT-1's one sanctioned exception: io/legacy.py's job is to recognise real
# legacy topic names on disk (df/aeb_outputs, df/bsd_outputs), which are
# function-prefixed by construction -- not framework prose repeating a
# function's name. N-6 already calls this file "the one sanctioned name
# translation"; this is the same narrow exception applied to GT-1. Named
# here, specifically, rather than a general carve-out.
_GT1_EXEMPT_FILENAMES = frozenset({"legacy.py"})


def _iter_py_files(root: Path):
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.py"))


def check_gt1(src_root: Path = SRC_ROOT) -> list[str]:
    """GT-1 -- no function names in the framework (R-SIM-1)."""
    findings = []
    for path in _iter_py_files(src_root):
        if path.name in _GT1_EXEMPT_FILENAMES:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _FUNCTION_TOKENS.search(line):
                findings.append(f"GT-1 {path}:{lineno}: function-name token in framework code: {line.strip()!r}")
    return findings


def check_gt2(superproject_root: Path = SUPERPROJECT_ROOT) -> list[str]:
    """GT-2 -- no renderer import in a layer provider (R-SIM-2)."""
    findings = []
    for layers_dir in sorted(superproject_root.glob("modules/*/sim/layers")):
        for path in _iter_py_files(layers_dir):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")) and any(tok in stripped for tok in _RENDERER_IMPORTS):
                    findings.append(f"GT-2 {path}:{lineno}: renderer import in a layer provider: {stripped!r}")
    return findings


def check_gt3(src_root: Path = SRC_ROOT, superproject_root: Path = SUPERPROJECT_ROOT) -> list[str]:
    """GT-3 -- no physical constant in a layer provider or renderer, outside model/ (R-SIM-3)."""
    findings = []
    candidates = list(_iter_py_files(src_root / "render"))
    for layers_dir in sorted(superproject_root.glob("modules/*/sim/layers")):
        candidates.extend(_iter_py_files(layers_dir))
    for path in candidates:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _DIMENSION_ASSIGNMENT.search(line):
                findings.append(f"GT-3 {path}:{lineno}: literal vehicle/sensor dimension outside model/: {line.strip()!r}")
    return findings


def check_gt6(src_root: Path = SRC_ROOT) -> list[str]:
    """GT-6 -- the framework imports no component (R-SIM-11)."""
    findings = []
    for path in _iter_py_files(src_root):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _COMPONENT_IMPORT.match(line) or "generated_py" in line:
                findings.append(f"GT-6 {path}:{lineno}: framework imports a component: {line.strip()!r}")
    return findings


def check_gt11(superproject_root: Path = SUPERPROJECT_ROOT) -> list[str]:
    """GT-11 -- no port address is a literal outside the component that
    declares it (R-SIM-21, arch `D13`, `S-B1Δ`). Extends `GT-1`, which stops
    exactly at the boundary where a component's own plug-in begins."""
    findings = []
    for sim_dir in sorted(superproject_root.glob("modules/*/sim")):
        for path in _iter_py_files(sim_dir):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                args = [m.group(1) for m in _REQUIRES_ARG.finditer(line)]
                args += [m.group(1) for m in _PORT_CALL_ARG.finditer(line)]
                for arg in args:
                    for match in _QUOTED_DOTTED_REF.finditer(arg):
                        ref = match.group(1)
                        if ref.startswith(_GT11_EXEMPT_PREFIXES):
                            continue
                        findings.append(f"GT-11 {path}:{lineno}: spelled port address outside its component: {line.strip()!r}")
    return findings


def run_all(src_root: Path = SRC_ROOT, superproject_root: Path = SUPERPROJECT_ROOT) -> list[str]:
    return [
        *check_gt1(src_root),
        *check_gt2(superproject_root),
        *check_gt3(src_root, superproject_root),
        *check_gt6(src_root),
        *check_gt11(superproject_root),
    ]


def main(argv: list[str] | None = None) -> int:
    findings = run_all()
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} invariant violation(s)")
        return 1
    print("GT-1, GT-2, GT-3, GT-6, GT-11: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
