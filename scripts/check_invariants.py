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
#: WP-05: the engine-only surface `ANL-SW-02`/`ANL-SW-03`/`ANL-SW-04` scan --
#: design §3.2's own enforcement table, mechanised.
SIMCORE_ROOT = SIM_ROOT / "src" / "simcore"
#: WP-21: `ANL-SW-08`'s own C++ surface -- both engine-side trees, not just
#: `simcore`, since a duplicate resolver could just as easily land in the
#: `simengine` executable itself.
SIMENGINE_ROOT = SIM_ROOT / "src" / "simengine"

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
    # WP-05, DD-02: src/simcore/third_party/ is vendored (nlohmann/json) --
    # GT-1's "no banned token" rule is about code THIS framework authored;
    # a third-party library's own source is not scanned, same reasoning
    # check_headers.py's own third_party exclusion states.
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix in _SOURCE_EXTENSIONS and "third_party" not in p.parts
    )


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


# ANL-SW-34 (WP-04, IMP-0164): `config/`, `graph/`, `ingest/`, `runspec/` run
# once per run and may not open a recording payload or load a module binary
# (Part C's own boundary) -- a direct `adas_sim.io`/`ctypes` import is the
# mechanised proxy for that. `resolve/` is deliberately excluded (its
# obligation is *not executing*, covered by `ANL-SW-07` instead -- a folder
# check states that wrongly).
_ANL_SW_34_DIRS = ("config", "graph", "ingest", "runspec")
_IO_OR_CTYPES_IMPORT = re.compile(r"^\s*(?:from\s+adas_sim\.io(?:\.\w+)*\s+import|import\s+adas_sim\.io\b|import\s+ctypes\b|from\s+ctypes\s+import)")


# ANL-SW-61 (WP-03, IMP-0364): "path handling and dynamic loading are
# abstracted at one place each" (SW-0364). Two independent, narrow
# invariants under one check ID, matching the design test spec's own
# pairing: a real OS dynamic-load call belongs only in `dso.cpp`
# (`simcore::module_host`, C++); the specific fragile-relative-path
# anti-pattern IMP-0364's own text names -- `Path(__file__).resolve().
# parents[N]`, hardcoded against this checkout's own directory depth --
# belongs only in `config/paths.py` (`ConfigPaths`). Deliberately not a
# blanket "no path-separator arithmetic anywhere" scan: that would be
# broad enough to false-positive on unrelated string formatting with no
# real fragility to it, which is not what either the Shall or the
# violation this check exists to catch actually names.
_DYNAMIC_LOAD_CALL = re.compile(r"\b(LoadLibrary[AW]?|dlopen)\s*\(")
_RESOLVE_PARENTS_WALK = re.compile(r"\.resolve\(\)\.parents\[")


def check_anl_sw61(all_src_root: Path = ALL_SRC_ROOT) -> list[str]:
    """`ANL-SW-61`: a `LoadLibrary`/`dlopen` call outside `dso.cpp`, or a
    `Path(...).resolve().parents[N]` relative-walk outside `config/
    paths.py`."""
    findings = []
    for path in _iter_source_files(all_src_root):
        if path.name == "dso.cpp":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _DYNAMIC_LOAD_CALL.search(line):
                findings.append(f"ANL-SW-61 {path}:{lineno}: dynamic-load call outside dso.cpp: {line.strip()!r}")
    for path in _iter_py_files(all_src_root / "adas_sim"):
        if path.name == "paths.py" and path.parent.name == "config":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _RESOLVE_PARENTS_WALK.search(line):
                findings.append(
                    f"ANL-SW-61 {path}:{lineno}: fragile relative-path walk outside config/paths.py: {line.strip()!r}"
                )
    return findings


def check_anl_sw34(src_root: Path = SRC_ROOT) -> list[str]:
    """`ANL-SW-34`: a direct `adas_sim.io`/`ctypes` import in `config/`,
    `graph/`, `ingest/` or `runspec/`. **Not yet in `run_all()`** -- `graph/
    build.py` (formerly `contracts/pipeline.py`) already imports `adas_sim.
    io.base.RecordingReader` for `Pipeline.load`'s `recording:` parameter,
    predating this `WP`; untangling that is `WP-05`'s own seam work
    (`IF-09`), not `WP-04`'s (`IMP-0164`'s own design note: "Today
    `contracts/pipeline.py` reaches into the component loader, which is why
    this is PARTIAL"). This function is real and tested (`UT-A2-*`
    planted-violation case) so the day that migration lands, wiring it into
    `run_all()` is a one-line change with an already-working check behind
    it -- not a check invented under pressure."""
    findings = []
    for subdir in _ANL_SW_34_DIRS:
        for path in _iter_py_files(src_root / subdir):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if _IO_OR_CTYPES_IMPORT.match(line):
                    findings.append(f"ANL-SW-34 {path}:{lineno}: io/ctypes import outside the boundary: {line.strip()!r}")
    return findings


# ANL-SW-07 (WP-21, IMP-0409): "SI-13 is the only Python item that binds
# the C interface for this, and is bounded by symbol" (SW-0409). A literal
# scan for the three execute-path symbol names, permitted only under
# `pyapi/`, `transport/`, `resolve/` -- `resolve/component.py`'s own
# `CtypesSilComponent` legitimately carries them (it is IN `resolve/`,
# `SI-13`); the boundary this check enforces is the SYMBOL BINDING site,
# never appearing outside those three folders, matching the design's own
# "stricter than forbidding the binding by folder, and the only form that
# survives the probe pass existing" (SwReq SWQ-14). **Scope, stated
# honestly:** this cannot decide arbitrary call-graph reachability (e.g.
# `graph/build.py` importing `CtypesSilComponent` by class name and calling
# its `.exec()` — a real, permanent behaviour, `WP-16`'s own "not a
# duplicate; stays" note) -- only whether the literal ctypes symbol tokens
# are bound outside the three permitted folders, which is what "bounded by
# symbol" cashes out to as something a static grep can mechanically check.
#
# Matched as an ATTRIBUTE ACCESS (`.adasInit`), not a bare token: this
# codebase's own docstrings/CLI help text/comments cite these three names
# in prose constantly (e.g. "config path forwarded to each stage's
# adasInit", "`` `adasInit(NULL)` will fail``") -- a bare-token scan finds
# a false positive on nearly every such mention. A real ctypes binding is
# always an attribute of a loaded `CDLL` (`dll.adasInit`, `self._dll.
# adasExec`); prose never spells the name with a leading dot.
_EXEC_SYMBOL_TOKENS = re.compile(r"\.(adasInit|adasExec|adasShutdown)\b")
_ANL_SW_07_ALLOWED_DIRS = ("pyapi", "transport", "resolve")


def check_anl_sw07(src_root: Path = SRC_ROOT) -> list[str]:
    """`ANL-SW-07`: an `adasInit`/`adasExec`/`adasShutdown` symbol token
    outside `pyapi/`, `transport/`, `resolve/`."""
    findings = []
    for path in _iter_py_files(src_root):
        relative_parts = path.relative_to(src_root).parts
        if relative_parts and relative_parts[0] in _ANL_SW_07_ALLOWED_DIRS:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _EXEC_SYMBOL_TOKENS.search(line):
                findings.append(f"ANL-SW-07 {path}:{lineno}: execute-path symbol outside pyapi/transport/resolve: {line.strip()!r}")
    return findings


# ANL-SW-08 (WP-21, IMP-0203): `resolve_library` implemented exactly once
# across the whole tree -- today that's Python's `resolve/library.py`
# alone (`library_loader.cpp`'s own resolve half died at `WP-16`). A
# second, C++-side stem-to-path resolver reappearing in `simcore`/
# `simengine` would silently reintroduce the duplication `WP-16` closed.
#: Requires an immediately-following `(` -- a real call or definition, not
#: a backtick-quoted prose mention (`dso.cpp`'s own doc comment cites the
#: deleted `ResolveLibrary` by name as history, `` `ResolveLibrary` ``,
#: which this must not flag).
_LIBRARY_RESOLVER_TOKENS = re.compile(
    r"(?<![A-Za-z0-9_])(ResolveLibrary|resolve_library|LibraryResolver)\s*\("
)


def check_anl_sw08(simcore_root: Path = SIMCORE_ROOT, simengine_root: Path = SIMENGINE_ROOT) -> list[str]:
    """`ANL-SW-08`: no C++ stem-to-path library resolver under `src/simcore/**`
    or `src/simengine/**` -- `resolve_library` (Python) is the one
    implementation."""
    findings = []
    for root in (simcore_root, simengine_root):
        for path in _iter_source_files(root):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if _LIBRARY_RESOLVER_TOKENS.search(line):
                    findings.append(f"ANL-SW-08 {path}:{lineno}: a second library resolver outside Python: {line.strip()!r}")
    return findings


# ANL-SW-37 (WP-21, IMP-0212): `resolve_library` called from exactly one
# place, plus two named, decided exceptions (2026-08-25) rather than a
# blanket "under resolve/ or graph/" carve-out -- an unlisted new call site
# anywhere else still fails the check.
#
# - `resolve/probe.py` is PERMANENT: it resolves a bare stem the user typed
#   for `sim probe <lib>`, with no `RunSpec`/pipeline stage in the picture --
#   a different operation from resolving a stage's `impl:`, not an instance
#   of the thing this check guards against.
# - `graph/build.py` is TEMPORARY, pending Bench building a `RunSpec` first
#   and constructing its `Pipeline` from that (so `_resolve_components`
#   reads `IMP-0003`'s already-resolved `stages[].impl` instead of calling
#   `resolve_library` itself). That refactor is a separate work package, not
#   this pass's `Files:` scope -- see the plan's `IMP-0212` row for the
#   `closed by` condition. Removing this entry is how that row closes.
_RESOLVE_LIBRARY_CALL = re.compile(r"(?<![A-Za-z0-9_.])resolve_library\s*\(")
_RESOLVE_LIBRARY_DEF = re.compile(r"^\s*def\s+resolve_library\s*\(")
_ANL_SW_37_ALLOWED_CALLERS = (
    Path("resolve") / "probe.py",       # permanent -- no RunSpec exists yet at this call
    Path("graph") / "build.py",         # temporary -- closed by the Bench-through-RunSpec refactor
)


def check_anl_sw37(src_root: Path = SRC_ROOT) -> list[str]:
    """`ANL-SW-37`: every call site of `resolve_library(...)` in the tree,
    excluding its own definition and the two named exceptions above. A
    finding lists every unexpected call site found."""
    call_sites: list[str] = []
    for path in _iter_py_files(src_root):
        relative = path.relative_to(src_root)
        if relative in _ANL_SW_37_ALLOWED_CALLERS:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _RESOLVE_LIBRARY_DEF.match(line):
                continue
            if _RESOLVE_LIBRARY_CALL.search(line):
                call_sites.append(f"{path}:{lineno}")
    if len(call_sites) > 1:
        return [f"ANL-SW-37 resolve_library called from {len(call_sites)} unexpected places, expected exactly 1: {call_sites}"]
    return []


# ANL-SW-38 (WP-21, IMP-0214): the three resolvers (`library.py`,
# `bundle.py`, `plugins.py`) each return the shared `Resolution[...]` shape
# through `order.py`'s one helper (`ordered_tiers`) -- checked mechanically
# by requiring each file to both import from `resolve.order` and declare a
# function returning `Resolution[...]`.
_RESOLVERS_FOR_ANL_SW_38 = ("library.py", "bundle.py", "plugins.py")
_ORDER_IMPORT = re.compile(r"^\s*from\s+adas_sim\.resolve\.order\s+import\b")
_RETURNS_RESOLUTION = re.compile(r"->\s*Resolution\[")


def check_anl_sw38(src_root: Path = SRC_ROOT) -> list[str]:
    """`ANL-SW-38`: each of `resolve/{library,bundle,plugins}.py` imports
    `resolve.order` and declares a function returning `Resolution[...]`."""
    findings = []
    resolve_dir = src_root / "resolve"
    for filename in _RESOLVERS_FOR_ANL_SW_38:
        path = resolve_dir / filename
        if not path.is_file():
            findings.append(f"ANL-SW-38 {path}: file does not exist")
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        imports_order = any(_ORDER_IMPORT.match(line) for line in lines)
        returns_resolution = bool(_RETURNS_RESOLUTION.search(text))
        if not imports_order:
            findings.append(f"ANL-SW-38 {path}: does not import adas_sim.resolve.order")
        if not returns_resolution:
            findings.append(f"ANL-SW-38 {path}: no function returns Resolution[...]")
    return findings


# ANL-SW-35 (WP-20, IMP-0167): the graph is built from module manifests plus
# the project's active module list, and no file enumerates a specific
# processing chain (SW-0167). `Pipeline.load` already reads `stages` purely
# from the pipeline YAML's own `parse_stages` -- this is a regression guard,
# not a fix: a hard-coded stage-name SEQUENCE assigned to a `stages`-named
# variable (`stages = ["perception", "fusion", "aeb"]`) is the shape a
# reintroduced literal chain would take. Deliberately narrow -- an empty
# list/tuple, a `Stage(...)` object literal, or a call like
# `cls.parse_stages(path)` never matches (no leading quoted string), so a
# real dynamic build stays invisible to this check the way `check_gt1`'s own
# banned-token grep stays invisible to ordinary prose.
_HARDCODED_STAGE_CHAIN = re.compile(r"""\b\w*stages?\w*\s*[:=]\s*[\[(]\s*["'][\w.]+["']\s*,""")


def check_anl_sw35(src_root: Path = SRC_ROOT) -> list[str]:
    """`ANL-SW-35`: `graph/build.py` never assigns a `stages`-named variable
    a literal list/tuple of quoted stage names."""
    findings = []
    path = src_root / "graph" / "build.py"
    if not path.is_file():
        return findings
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if _HARDCODED_STAGE_CHAIN.search(line):
            findings.append(f"ANL-SW-35 {path}:{lineno}: hard-coded stage chain: {line.strip()!r}")
    return findings


# WP-05, design §3.2's enforcement table -- three engine-only greps over
# `src/simcore/**`, excluding the vendored `third_party/` (not our own code,
# same reasoning `_iter_source_files` already applies to GT-1).
#: `gcd` is word-bounded (a common-enough substring to false-positive
#: otherwise); `snap` is a plain substring match -- it names a naming
#: PATTERN ("SnapToGrid", "snap_grid", "GridSnap"), not a standalone
#: identifier, so a word boundary would miss the PascalCase/prefix shapes
#: this token actually takes in practice.
_GCD_TOKENS = re.compile(r"(?<![A-Za-z0-9_])(gcd)(?![A-Za-z0-9_])", re.IGNORECASE)
_SNAP_TOKENS = re.compile(r"snap", re.IGNORECASE)
_ADDRESS_GRAMMAR_TOKENS = re.compile(r'"self\.|"source\.')
#: A quoted string literal ending `.yaml`, or a YAML library token -- never
#: a bare comment mention. This codebase's own established comment style
#: cites `docs/v2/*.yaml` as documentation provenance everywhere (e.g.
#: `errors.hpp`'s own "Ported from docs/v2/errors.yaml") -- a check that
#: flagged prose would be permanently red, which is worse than not checking.
_YAML_TOKENS = re.compile(r'"[^"]*\.yaml"|yaml-cpp|YAML::', re.IGNORECASE)


def check_anl_sw02(simcore_root: Path = SIMCORE_ROOT) -> list[str]:
    """`ANL-SW-02` (`IMP-0006`): no GCD/`snap`/base-grid computation in the
    engine -- `emit.py::_compute_grid_step_ns` (Python) is the ONE place
    the grid step is derived; `simcore` only ever reads `grid.step_ns` and
    `stages[].period_ns` already resolved."""
    findings = []
    for path in _iter_source_files(simcore_root):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _GCD_TOKENS.search(line) or _SNAP_TOKENS.search(line):
                findings.append(f"ANL-SW-02 {path}:{lineno}: grid/GCD computation in the engine: {line.strip()!r}")
    return findings


def check_anl_sw03(simcore_root: Path = SIMCORE_ROOT) -> list[str]:
    """`ANL-SW-03` (`IMP-0007`): no dotted-address splitting or `self.`/
    `source.` reference prefix in the engine -- `runspec/address.py`
    (Python) is the one place that grammar lives; `stages[].inputs[]`
    already carries `{producer, producer_port}` split, never a string to
    re-parse."""
    findings = []
    for path in _iter_source_files(simcore_root):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _ADDRESS_GRAMMAR_TOKENS.search(line):
                findings.append(f"ANL-SW-03 {path}:{lineno}: reference-grammar literal in the engine: {line.strip()!r}")
    return findings


def check_anl_sw04(simcore_root: Path = SIMCORE_ROOT) -> list[str]:
    """`ANL-SW-04` (`IMP-0011`): `simcore` opens no `.yaml` -- the ingest
    map (once `WP-12` lands) is parsed in Python and arrives pre-resolved
    in `sources[].ingest`; no YAML library or `.yaml` path literal may
    appear in the engine."""
    findings = []
    for path in _iter_source_files(simcore_root):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _YAML_TOKENS.search(line):
                findings.append(f"ANL-SW-04 {path}:{lineno}: YAML reference in the engine: {line.strip()!r}")
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
        *check_anl_sw07(src_root),
        *check_anl_sw08(),
        *check_anl_sw37(src_root),
        *check_anl_sw38(src_root),
        *check_anl_sw35(src_root),
        *check_anl_sw02(),
        *check_anl_sw03(),
        *check_anl_sw04(),
        *check_anl_sw61(all_src_root),
    ]


def main(argv: list[str] | None = None) -> int:
    findings = run_all()
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} invariant violation(s)")
        return 1
    print("GT-1, GT-2, GT-3, GT-6, GT-11, UT-D8-9, WP-02(b), ANL-SW-02/03/04/07/08/35/37/38/61: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
