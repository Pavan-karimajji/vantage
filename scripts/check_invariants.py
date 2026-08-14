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
#: WP-03: the enforced surface for R-SIM-1-derived checks is all of
#: `modules/sim/src/**` (adas_sim + simcore + simengine), not just the
#: Python package -- the rule's own text always said "src/**"; only
#: adas_sim existed to scan before simcore/simengine gained real content.
ALL_SRC_ROOT = SIM_ROOT / "src"

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

# IMP-0383 / ANL-SW-72 (WP-01, WP-06): no identifier under
# src/simcore/io/codecs/** names a driving function, and no module manifest
# names a codec. Extends GT-1's own grep rather than adding a second
# scanner. Neither directory exists yet -- src/simcore/io/codecs/ lands
# WP-06, a module manifest (conf/ports.yaml, IMP-0392) lands WP-10 -- so
# this reports zero files scanned today rather than a false PASS, exactly
# like WP-01's other new checks (Plan WP-01 Exit gate 3).
_CODEC_NAME_TOKENS = re.compile(r"(?<![A-Za-z0-9_])(mcap|csv|jsonl|mdf4|tdms)(?![A-Za-z0-9_])", re.IGNORECASE)

# UT-D8-9 (S-D8, sim_player.md's own naming rule): no workspace/product token
# outside app/. Case-SENSITIVE, unlike GT-1's tokens -- "Vantage"/"Bench"/
# "Campaign" are ordinary English words in lowercase ("a Bench" vs. "a test
# bench", "workbench"), so matching case-insensitively would flag legitimate
# prose; the actual product/workspace names are always capitalized at their
# point of use (sim_player.md itself: "Vantage", "Bench", "Campaign").
_WORKSPACE_TOKENS = re.compile(r"(?<![A-Za-z0-9])(Vantage|Bench|Campaign)(?![A-Za-z0-9])")

# WP-02(b) / DD-12: the live world-model client is removed from the system
# entirely -- no live stimulus of any kind, every input is a recording read
# through a codec. Deliberately narrower than GT-1's bare-token grep: `df`'s
# own real recordings are named `carla_scenarios`/`carla_testruns` (they
# were captured from CARLA) and that provenance naming is legitimate data,
# not a leak of the deleted client -- a blanket "carla" substring ban would
# flag `check/runner.py`'s real directory-naming convention. What must never
# come back is the deleted CLIENT: its class name and its import path.
_WORLD_MODEL_CLIENT_TOKENS = re.compile(
    r"(?<![A-Za-z0-9_])(CarlaSource|sources[./\\]carla)(?![A-Za-z0-9_])", re.IGNORECASE
)


def _iter_py_files(root: Path):
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.py"))


#: WP-03: simcore/simengine are C++, not Python -- GT-1's own concern (no
#: banned function-name string in framework code) applies to a .cpp/.hpp/.h
#: file exactly as much as a .py one.
_SOURCE_EXTENSIONS = (".py", ".cpp", ".hpp", ".h")


def _iter_source_files(root: Path):
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in _SOURCE_EXTENSIONS)


def check_gt1(src_root: Path = ALL_SRC_ROOT) -> list[str]:
    """GT-1 -- no function names in the framework (R-SIM-1), over all of
    `src/**` (`.py`/`.cpp`/`.hpp`/`.h`) -- `simcore`/`simengine` included
    since `WP-03`. `io/legacy.py`'s exemption is gone (`S-C9`): the one
    thing that needed it -- recognising real legacy topic names -- moved to
    `modules/df/sim/ingest/carla_legacy.yaml`, declared data outside
    `src/`, which `GT-1` never scanned in the first place."""
    findings = []
    for path in _iter_source_files(src_root):
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


def check_gt6(src_root: Path = ALL_SRC_ROOT) -> list[str]:
    """GT-6 -- the framework imports no component (R-SIM-11), over all of
    `src/**` -- Python-only concept (an `import`/`from` statement), so this
    stays on `_iter_py_files` even though the scanned root now also covers
    `simcore`/`simengine` (no `.py` lives there today; harmless to widen)."""
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


def check_ut_d8_9(src_root: Path = SRC_ROOT) -> list[str]:
    """`UT-D8-9` (`S-D8`) -- no `Vantage`/`Bench`/`Campaign` token anywhere
    in `adas_sim/` outside `player/shell/` (`sim_player.md`'s own naming
    rule: "no workspace name appears in `adas_sim/` outside `app/`" -- the
    engine must not know which workspace is open, same discipline `GT-1`
    applies to a driving function's name). `app/` became `player/shell/` at
    `WP-02`'s rename (Design §2.3); the exemption moved with it. Scoped
    exactly like `GT-2`/`GT-3` scope to their own subtrees -- everything
    under `src_root` except `player/shell/` itself, which is the one place
    these tokens are the whole point."""
    findings = []
    app_dir = (src_root / "player" / "shell").resolve()
    for path in _iter_py_files(src_root):
        if app_dir in path.resolve().parents or path.resolve() == app_dir:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _WORKSPACE_TOKENS.search(line):
                findings.append(f"UT-D8-9 {path}:{lineno}: workspace/product token outside app/: {line.strip()!r}")
    return findings


def check_codec_scope_no_function_name(sim_root: Path = SIM_ROOT) -> list[str]:
    """IMP-0383 half 1: no identifier under `src/simcore/io/codecs/**`
    names a driving function (GT-1's own tokens, R-SIM-1). `WP-06`'s job to
    populate; this is `WP-01`'s job to be watching before it does."""
    findings = []
    codecs_dir = sim_root / "src" / "simcore" / "io" / "codecs"
    if not codecs_dir.is_dir():
        return findings
    for path in sorted(p for p in codecs_dir.rglob("*") if p.is_file()):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _FUNCTION_TOKENS.search(line):
                findings.append(f"IMP-0383 {path}:{lineno}: function-name token in a codec: {line.strip()!r}")
    return findings


def check_no_world_model_client(sim_root: Path = SIM_ROOT) -> list[str]:
    """WP-02(b) / DD-12: no live world-model client survives -- the deleted
    `sources/carla/` directory and its `CarlaSource` class/import path must
    never reappear anywhere under `src/**` (all three roots: `adas_sim`,
    `simcore`, `simengine`)."""
    findings = []
    src_dir = sim_root / "src"
    carla_dir = src_dir / "adas_sim" / "sources" / "carla"
    if carla_dir.exists():
        findings.append(f"WP-02(b) {carla_dir}: the deleted world-model client's directory has reappeared")
    for path in _iter_py_files(src_dir):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _WORLD_MODEL_CLIENT_TOKENS.search(line):
                findings.append(f"WP-02(b) {path}:{lineno}: deleted world-model client reappeared: {line.strip()!r}")
    return findings


def check_no_manifest_names_codec(superproject_root: Path = SUPERPROJECT_ROOT) -> list[str]:
    """IMP-0383 half 2: no module manifest (`conf/ports.yaml`, IMP-0392,
    lands `WP-10`) names a codec format -- a component's port declaration
    must not know which codec `sim` happens to read it with."""
    findings = []
    for manifest in sorted(superproject_root.glob("modules/*/conf/ports.yaml")):
        for lineno, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), start=1):
            if _CODEC_NAME_TOKENS.search(line):
                findings.append(f"IMP-0383 {manifest}:{lineno}: module manifest names a codec: {line.strip()!r}")
    return findings


def run_all(
    src_root: Path = SRC_ROOT, superproject_root: Path = SUPERPROJECT_ROOT, all_src_root: Path = ALL_SRC_ROOT,
) -> list[str]:
    sim_root = all_src_root.parent
    return [
        *check_gt1(all_src_root),
        *check_gt2(superproject_root),
        *check_gt3(src_root, superproject_root),
        *check_gt6(all_src_root),
        *check_gt11(superproject_root),
        *check_ut_d8_9(src_root),
        *check_no_world_model_client(sim_root),
        *check_codec_scope_no_function_name(sim_root),
        *check_no_manifest_names_codec(superproject_root),
    ]


def main(argv: list[str] | None = None) -> int:
    findings = run_all()
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} invariant violation(s)")
        return 1
    print("GT-1, GT-2, GT-3, GT-6, GT-11, UT-D8-9, WP-02(b): clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
