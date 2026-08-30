# SIM — Test Execution Record — 2026-08-30 · `B2` executed (real `modules/df` build), `B3` fully re-scoped

**This record is evidence, not a specification.** Exempt from the freeze on
that basis, never edited after the fact. A later campaign is a **new file**.
**Reads with:** `SIM_Test_Execution_2026-08-30_movement_b_plan_audit.md` (the
correction pass this one executes and extends).

## Campaign

| | |
|---|---|
| Question | Execute the re-scoped `B2` (388 lines, three duplicate test files) in `modules/df` for real, gated on a real vs2026 build — not an assumption. Then re-scope `B3` properly: check each of its four rows against the build and `git log`, the same way `B2` was verified, and correct or retire each row on what is actually found. |
| Method | `A` (analysis) for `B3`'s re-scope; a real build + `T` (ctest) for `B2`'s gate and verification |
| Platform | native Windows (`vs2026`, this session's shell), `modules/df/build-gtest-vs2026` |
| Scope | `modules/df` (execution) and `modules/sim/misc/MOVEMENT_B_PLAN.md`/`START_HERE.md` (bookkeeping). `R-GIT-1` applies: this is a change inside the `df` submodule, staged there, not yet committed in either repo |
| Committed | Not yet — review-first, per the user's ask |

## Result — `B2` executed

### Gate (before deletion)

`modules/df/build-gtest-vs2026` had drifted since it was last configured:
`TARGET_TYPE` had reverted to the preset default `sil` (no `df_viz` targets
present at all — the exact failure mode
`reference_df_viz_gtest_build_recovery` warns about), and `conan install`
failed twice before a clean build was even possible:

1. `adas-mathlib` — `Library 'adas-mathlib' not found in package`. Root
   cause: the `adas-mathlib` Conan editable was registered against
   `C:\ws\repo\lt\1v-superproject\modules\mathlib` — a **different checkout on
   this machine**, not this one. Fixed: `conan editable add .` from
   `modules/mathlib` in *this* checkout. (`adas-df`, `adas-shared-config`,
   `adas-perception-core`, `adas-vdy` are still editable against the `lt`
   checkout — untouched, out of scope; only the one blocking `df`'s own
   `AdasMathlib::AdasMathlib` dependency was fixed.)
2. `protobuf/3.21.12: EOF when reading a line. [Remote: adas-local]` — the
   known `adas-local` auth gap (`reference_conan_remote_auth`). Fixed:
   `conan remote login adas-local demo -p demo`.

Recovered per `reference_df_viz_gtest_build_recovery`'s documented recipe (no
`cmake --fresh`, explicit `-DTARGET_TYPE=sil_viz -DBUILD_TESTING=ON` reconfigure
after a `conan install` into the existing output folder):
```
conan install . --output-folder build-gtest-vs2026 --update --build=missing -o project=base -s build_type=Release
cmake -S . -B build-gtest-vs2026 -G "Visual Studio 18 2026" -A x64 -T v145 -DCMAKE_TOOLCHAIN_FILE=build-gtest-vs2026/conan_toolchain.cmake -DCMAKE_POLICY_DEFAULT_CMP0091=NEW -DBUILD_TESTING=ON -DTARGET_TYPE=sil_viz -DADAS_PROJECT=base
cmake --build build-gtest-vs2026 --config Release
ctest --test-dir build-gtest-vs2026 -C Release --output-on-failure
```

**Baseline, before deletion:** build green. `315` ctest entries (`21` of them
`df_viz_test_*`), **314 passed, 1 failed**:
`df_viz_test_render_svg` — `RenderSvg.UT_render_svg_02_AllEightKindsProduceOneElementEach`
fails on `unresolved style token "bsd.zone" in theme "dark"` (a real,
pre-existing gap in `df`'s R1 theme registration, unrelated to any of the
three files this pass touches). Gate satisfied: build is real and green modulo
this one pre-existing, unrelated failure, which is left untouched per
instruction ("do not touch anything else in `df_viz/`").

### Execution

Removed `tests/unit/test_furniture.cpp`, `test_history.cpp`, `test_pick.cpp`
(`git rm`) and their three `add_executable`/`target_link_libraries`/
`add_test` blocks in `CMakeLists.txt` (29 lines net). Nothing else in
`df_viz/` touched.

Reconfigured (same explicit `-DTARGET_TYPE=sil_viz` command, required after
any `CMakeLists.txt` edit) and rebuilt clean — no new warnings, no errors.

### Verification

```
ctest --test-dir build-gtest-vs2026 -C Release -N | grep -c df_viz   # 21 -> 18
ctest --test-dir build-gtest-vs2026 -C Release --output-on-failure   # 312 total (was 315)
```
**312 ctest entries (was 315, exactly 3 fewer), 311 passed / 1 failed (was
314/1)** — the same pre-existing `df_viz_test_render_svg` failure, unchanged,
confirming the deletion touched nothing it shouldn't have. `df_viz`-specific
ctest entries: **18 (was 21)**. `grep` for the deleted filenames/target names
across the tree (excluding build directories) finds only historical dated
entries in `docs/viz/df_viz_Implementation_Plan_v0.1.md` (`UT-pick-01..03`,
`UT-history-01/02` — the R-REQ-6a implementation-progress record of when
these were originally verified) and one still-accurate design-rationale
comment in `CMakeLists.txt` referring to the now-deleted `df_viz_test_history`
by name in `df_viz_test_scene_history`'s own comment block. Left untouched —
outside this pass's scope (`docs/viz/` is a requirements doc, not `df_viz/`
source; the comment is prose, not a broken reference) and named here so a
future pass knows they exist and are not build breakage.

## Result — `B3` re-scoped: all four rows fail verification, zero executed

Checked each row against the build and `git log`, not the plan's prose —
findings below, full detail in the rewritten `B3` table in
`MOVEMENT_B_PLAN.md`.

| Row | Plan's premise | What broke it |
|---|---|---|
| `tools/carla/` | Legacy tooling `R-SIM` replaces | `git log`: last commit **2026-08-20**, four days earlier a real feature landed (`56c87f3`, paced Play/Pause/Step panel). Active, not legacy |
| `replay/viz.py` | Sibling deletion target, superseded once the viz player covers replay | `df_dll_sim_mcap.py:450` does `import viz as viz_module`; that file is exactly what `df_sim_gui.py`'s REPLAY & FOXGLOVE section launches (`df_sim_gui.py:675`, `cmd = ["py", "-3.12", "df_dll_sim_mcap.py", rel_path]`). In active use through the current GUI, not orphaned |
| `df_sim_gui.py` | `vantage.bat` covers what it did | Confirmed from the previous pass: extended 2026-08-29 with a real CarMaker section the file's own header says was deliberately kept here rather than split out. `vantage.bat` cannot cover CarMaker launching under any reading |
| `docs/bsd/py/bsdviz/` | "the layer plug-ins cover it" | 8 files under `docs/bsd/py/figures/` (`a_convention.py` … `v_vehicledynamics.py`) do `from bsdviz import ...`, driven by `df_bsd_image_creation.py` — a documentation-figure generator, a different purpose from the live C++ layer plug-ins entirely. Not superseded by anything named |

**None of the four rows is ready to execute.** `tools/carla/` and
`replay/viz.py` are both active, current tooling (not legacy at all, contrary
to the row heading). `df_sim_gui.py` is retired as a deletion target and
re-scoped to "at most its CARLA+REPLAY sections, once rows 1/2 close" —
which they have not. `bsdviz/`'s gate does not hold against any code found
this pass. **Nothing deleted from `modules/df` this pass beyond `B2`'s three
files.**

## What this does not close

`B3` needs its targets re-identified before it can be planned again, not
just its gates re-checked — this pass found the row descriptions themselves
(legacy/orphaned/superseded) false for three of four rows, not merely their
gates unmet. `B4` and item `#20` were explicitly out of scope and untouched.
The pre-existing `df_viz_test_render_svg` failure and the two stale-editable
Conan registrations (`adas-df`, `adas-shared-config`, `adas-perception-core`,
`adas-vdy` still pointing at the `lt` checkout) are both real, both
unaddressed, and both outside this pass's scope — named here so they are not
mistaken for new breakage next time this build tree is touched.

## Files changed

| Repo | Scope |
|---|---|
| `modules/df` | 3 files deleted (`tests/unit/test_furniture.cpp`, `test_history.cpp`, `test_pick.cpp`), `src/platform/df_viz/CMakeLists.txt` (29 lines removed). Staged, not committed |
| `modules/sim` | `misc/MOVEMENT_B_PLAN.md` (`B3` table rewritten, header updated), `misc/START_HERE.md` (three fields updated), this record |
| (machine-local, not a repo change) | Conan editable `adas-mathlib` re-registered to this checkout; `adas-local` remote re-authenticated |

## Re-run commands

```
cd modules/df
conan install . --output-folder build-gtest-vs2026 --update --build=missing -o project=base -s build_type=Release
cmake -S . -B build-gtest-vs2026 -G "Visual Studio 18 2026" -A x64 -T v145 -DCMAKE_TOOLCHAIN_FILE=build-gtest-vs2026/conan_toolchain.cmake -DCMAKE_POLICY_DEFAULT_CMP0091=NEW -DBUILD_TESTING=ON -DTARGET_TYPE=sil_viz -DADAS_PROJECT=base
cmake --build build-gtest-vs2026 --config Release
ctest --test-dir build-gtest-vs2026 -C Release --output-on-failure
```

A later campaign is a **new file**, never an edit to this one (`R-REQ-6`).
