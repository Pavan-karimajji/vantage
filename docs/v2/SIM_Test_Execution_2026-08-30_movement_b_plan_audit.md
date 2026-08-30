# SIM — Test Execution Record — 2026-08-30 · `MOVEMENT_B_PLAN.md` audit — `B2` corrected, `B3`/`B4` sanity-checked

**This record is evidence, not a specification.** Exempt from the freeze on
that basis, never edited after the fact. A later campaign is a **new file**.

## Campaign

| | |
|---|---|
| Question | `B2` said to delete `modules/df/src/platform/df_viz/` as a "half-finished extraction, ~4,900 lines." Is that true? If not, correct it — do not execute it. Then: does `B2` have any real duplicate content once corrected, and do `B3`/`B4`, measured the same day by the same method, carry the same kind of error? |
| Method | `A` (analysis — read the code and build config directly; no test suite invoked). `diff` for duplication claims, `wc -l` for size claims, `git log` for staleness/activity claims |
| Platform | native Windows (this session's shell) |
| Scope | `modules/sim/misc/MOVEMENT_B_PLAN.md` and `misc/START_HERE.md` only. **No deletion executed in `modules/df` this pass**, per instruction |
| Committed | Not yet — review-first, per the user's ask |

## Result — `B2`: real, load-bearing, do not delete

`modules/df/src/platform/df_viz/` is `df`'s viz plug-in, not a remnant:

- `df_viz_c.cpp`/`.h` (202 lines) — the `df_viz.dll` composition root.
- `layers/` (892 lines) — `df`'s own layer providers (`bsd.cpp`, `common.cpp`,
  `port_tree.cpp`).
- `viz/theme/r1_theme_init.*` + `viz/viewport/r1_viewport_init.*` (211 lines,
  exact) — `df`'s own theme-token/viewport registration, not duplicated
  toolkit (the shared toolkit ships no component style tokens, `R-SIM-1`).

Verified against the build directly:
```
modules/df/conf/build.yml   -- sil_viz, cm_viz targets both build+deploy df_viz.dll
modules/viz/cpp/viz/host/push_host.{cpp,hpp}   -- PushHost, the loader
modules/df/src/platform/cm/src/user_hooks.cpp  -- calls PushHost at run time
```
Deleting the directory would have removed CarMaker visualization outright.

**Total tree size is 4,909 lines** (`wc -l` over `*.cpp/*.hpp/*.h`), matching
the plan's "~4,900" — the size estimate was right, the *characterization*
("half-finished extraction... everything else was copied to `modules/viz` and
the original left standing") was wrong. 4,462 of the 4,909 lines are
`tests/`, `scripts/`, `tools/` — audited below.

### Audit — genuine duplication in `modules/viz`?

| Checked | Verdict | Evidence |
|---|---|---|
| `scripts/check_dependency_graph.py`, `check_toolkit_isolation.py` | Not duplicates | `diff` against `modules/viz/scripts/`'s same-named files: different `ITEM_DIRS`/`FS_DIRS`/`INCLUDE_DIRS` maps, different `ALLOWED_DIRS`. Same pattern, own content, each scoped to its own tree. |
| `tests/unit/test_theme.cpp` | Not a duplicate | `diff`: `modules/viz`'s copy tests generic `ThemeTable` machinery against a *synthetic* vocabulary "by design... the toolkit's own tests carry no component name either" (its own comment); `df`'s copy is `df`'s real R1-vocabulary coverage test, which that same comment says belongs with the component. |
| `tests/unit/test_render_gl.cpp`, `test_render_svg.cpp`, `test_scene.cpp`, `test_scene_history.cpp`, `test_viewport.cpp`, `test_manifest_no_protobuf.cpp` | Not duplicates | `diff` line counts: 78–321 differing lines each (of 69–733 total) — substantially different content, not a stale copy. |
| `tests/unit/test_furniture.cpp`, `test_history.cpp`, `test_pick.cpp` | **Genuine duplicates — 388 lines** | `diff` against `modules/viz/tests/unit/`: identical except the `COMPONENT:` header line. Each is built and run as its own `add_executable`/`add_test` in both `df_viz/CMakeLists.txt` (confirmed present, lines 343–348, 474–490) and `modules/viz`'s, exercising the shared `AdasViz::toolkit` code — not `df`-specific, despite `bsd.*` token strings used as test data (permitted under the `tests/` carve-out, `R-SIM-1`). |
| `tests/combined_dll/`, `tests/scene_only_host/`, `tools/demo_viewer.cpp`, `scripts/check_layers_toolkit_boundary.py`, `check_no_intree_toolkit.py`, `gen_viz_shim.py` | Not duplicates | No same-named counterpart exists in `modules/viz` at all. |

**`B2` re-scoped to 388 lines** (three test files + their CMake blocks), not
~4,900. Corrected in `MOVEMENT_B_PLAN.md`; not executed this pass.

## Result — `B3`: one row corrected, one structural note, two confirmed

Sanity-checked the same way (`wc -l`, `git log`, actual paths) rather than
trusting the plan's prose:

| Row | Plan said | Found | Verdict |
|---|---|---|---|
| `modules/df/tools/carla/` | ~3,200 | 2,787 (excl. `__pycache__`) | Close enough — unchanged |
| `replay/viz.py` | 561, sibling target | 561 confirmed, but it is `modules/df/tools/carla/replay/viz.py` — **nested inside row 1's own tree**, not a sibling | Structural note, not a size error — deleting row 1 deletes it too |
| `scripts/df_sim_gui.py` | 658; gate: `vantage.bat` covers it | Wrong path (`modules/df/scripts/df_sim_gui.py`), 863 lines, and **extended one day after this plan was written** (commit `250be04`, 2026-08-29, adds a CarMaker launcher section) | **Corrected — this was heading toward a second `B2`-shaped mistake.** The file's own header now documents a deliberate decision to extend it rather than add a fourth launcher; `vantage.bat` has no CarMaker capability and cannot cover that section. Row flagged, not re-scoped, so it isn't deleted on the stale gate |
| `docs/bsd/py/bsdviz/` | 1,878 | 1,878 confirmed; last real commit 2026-07-29, dormant since (no post-plan growth) | Confirmed as-is, gate not independently re-verified |

## Result — `B4`: sizes stale from `B1` closing, not a misreading

`adas_sim` is 18,560 lines today, not 26,272 — `B1`/`SM-12` deleted the Python
scene/render/player tree on 2026-08-29, two days after this row's count was
written. `simcore` is 31,406, close to the original 31,064. Of the five named
overlapping sub-packages, `io`/`runspec`/`diagnostics` still exist on both
sides; **`session` is Python-only today (no `simcore/session`) and `abi` is
C++-only (no `adas_sim/abi`)** — 3 of 5 are a live overlap now, not 5. Read as
`B1`'s execution having partly resolved the overlap already, not as the
original row misreading the code — flagged for a fresh look before `B4`
starts rather than rewritten prescriptively.

## What this does not close

Nothing was deleted or re-scoped to completion. `B2` is corrected and its real
content (388 lines) identified but not removed. `B3` row 3 is flagged, not
re-scoped — what of `df_sim_gui.py` (if anything) is still superseded by
`vantage.bat` is an open question. `B4`'s overlap list needs re-deriving
before that movement starts. None of this blocks Movement C.

## Files changed

| Repo | Scope |
|---|---|
| `modules/sim` | `misc/MOVEMENT_B_PLAN.md` (`B2` rewritten and re-scoped, `B3`/`B4` rows annotated), `misc/START_HERE.md` (three fields updated), this record |

## Re-run commands

```
find modules/df/src/platform/df_viz -name '*.cpp' -o -name '*.hpp' -o -name '*.h' | xargs wc -l
diff modules/df/src/platform/df_viz/tests/unit/test_pick.cpp modules/viz/tests/unit/test_pick.cpp
git -C modules/df log -3 --format='%ad %h %s' -- scripts/df_sim_gui.py
```

A later campaign is a **new file**, never an edit to this one (`R-REQ-6`).
