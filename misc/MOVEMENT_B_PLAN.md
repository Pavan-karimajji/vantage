# Movement B — finish what exists

**Written:** 2026-08-27 · **Status:** `B1` closed 2026-08-29. `B2` corrected
and executed 2026-08-30 (388 lines, three duplicate test files, in
`modules/df`). `B3` re-scoped the same day — zero of its four rows are ready
to execute; nothing deleted. `B4` re-measured 2026-08-30 — re-scoped to one
real item (`io`), not actionable yet (parity gap); nothing deleted.
**`B1`–`B4` are all now either closed or re-scoped to their real remaining
content — no row in this plan still rests on an unverified claim.**
**Corrected 2026-08-30:** `B2` was a misreading (deletion would have broken
CarMaker viz) — rewritten, re-scoped to 388 real duplicate lines, and executed
(gated on a real vs2026 build, 314/315 → 311/312 tests, exactly 3 fewer test
binaries, one pre-existing unrelated failure unchanged). `B3` re-scoped in
full: all four rows failed verification against the code (not legacy, not
orphaned, or not superseded by what the row claimed) — none executed. `B4`
re-measured per-item (not just re-sized): 4 of its 5 claimed overlaps were
never overlaps (asymmetric by design, or a producer/consumer pair, or
cross-module) — only `io` is real, and its own C++ code admits it isn't at
parity yet. See
`docs/v2/SIM_Test_Execution_2026-08-30_movement_b_plan_audit.md` (the `B2`
correction), `docs/v2/SIM_Test_Execution_2026-08-30_b2_execute_b3_rescope.md`
(`B2` execution + `B3` re-scope) and
`docs/v2/SIM_Test_Execution_2026-08-30_b4_remeasure.md` (`B4` re-measure).
**Reads with:** `memory.md` (why), `DEMO_AND_SCOPE.md` (the finite list),
`CONSOLIDATED_REQUIREMENTS.md` (the 25 lines).

Movement A is done. This is the plan for the movement that **all three previous
attempts died in**: deleting what was replaced. Every migration in this project
so far has been a copy, never a move, so nothing has ever been finished.

**The rule that governs every step below:**

> Nothing is done until the thing it replaced is gone.
> Delete only behind a gate that proves the replacement works.

---

## B0 — Preconditions

| | |
|---|---|
| Gate state | 1 known failure (Conan editable, parked WP-31) |
| Decisions in force | **A** C++ where possible · **B** player permanently in viz · **C** ~~ERG~~ **parked** · **D** vdy months away · **E** demo = done, as POC |
| Freeze | in force — corrections allowed, new scope goes to the parked list |

**The ERG blocker is answered: no such measurement exists and none can be
obtained (2026-08-27).** `B5` is therefore **parked in full**, and the demo was
rewritten around a recording the system produces itself (`DEMO_AND_SCOPE.md` §1).
The `.erg` codec stays built (`WP-06b`, 8/8) and unused until data appears.

**The new top risk** is step zero of the revised critical path: can a recording
containing df's *outputs* be produced, and does `mode: measured` consume it?
`R-SIM-6` says yes and is marked built — but built is not demonstrated. **Check
this before anything else in Movement C.** An hour's work, and it decides whether
the demo is close or blocked.

---

## B1 — Close the viz sync plan · **10 boxes, all closed 2026-08-29**

The whole remainder of a 43-item plan. All of it was deletion or truth-telling.

| Item | Work | Gate |
|---|---|---|
| `SM-10` — **done** | The real finding wasn't `modules/sim/CLAUDE.md` (already correct) but `modules/viz`'s own `CLAUDE.md`, still opening *"this module does not exist yet — there is no source here"* over 112 files / ~11,300 lines. Fixed. | The file describes what is actually on disk |
| `SM-05` — **done** | supersession bookkeeping, closed once `SM-12`'s dual-run window closed | trace check clean |
| `SM-07` — **done** | `MP-4` re-cut | trace check clean |
| `SM-08` — **done** | Qt out, headless in — turned out to already be true (`SM-12` deleted the last Python `PySide6` importer as a side effect). Real remaining work: `pyproject.toml`'s `viewer` extra dropped, two stale docstrings fixed, `sim-ci.yml`'s three install lines corrected (would have failed outright on the now-unknown `viewer` extra), `ANL-SM-02` built for real and wired into `ci_gate.py`. `figures`/`foxglove` extras also now dead in source — found, not touched, separate finding. | `ANL-SM-02` real and green: no CI image installs a graphical toolkit |
| `SM-12` — **done** | **Deleted the Python scene** — the `D-6` box. This *is* Decision B: `scene/`, `render/`, `player/shell/` gone, `player/panels/` down to `pipeline_panel.py` (`SI-22`'s own `KEEP`); ~20 dependent files individually triaged and fixed (`core/runner.py` split, `cli/render.py`/`cli/view.py` deleted, `plugins/registry.py`'s `EXTENSION_POINTS` amended, `scripts/vantage.py` deleted, `vantage.bat`/`gui.py`/`vantage_native.py` lost their `--legacy` fallback — a real, named capability loss, not silently dropped). `df`'s own `sim/layers/{bsd,common}.py` confirmed orphaned-but-harmless, not touched (separate submodule, separate finding). | `ANL-SM-03` real and green: exactly one layer-provider implementation remains |

**Exit:** the sync plan self-deleted, per its own §6.6 — §2/§3 removed,
2026-08-29. **Both honest exceptions named at the time are now closed
(2026-08-30):** `sync_check.py` is deleted — `scripts/next.py` was rewritten
to drop the hard import, per the sync plan's own "minus its gate table"
(§6.6), and now runs each of the three modules' own `trace_check.py` instead.
`scripts/check_cross_module_trace.py`'s 60 `BROKEN` findings were triaged:
56 (every `SIM:SW-*`/`SIM:SYS-*` one) were exactly the suspected parser gap
— a third disposition-table definition shape the checker didn't recognize —
fixed; the remaining 3 (`VIZ:IMP-0036`/`0064`/`0065`) are real dangling links
in `df_viz_Implementation_Design_v0.1.md`, left unfixed and named for whoever
owns df's design doc next. Full account:
`docs/v2/SIM_Test_Execution_2026-08-29_b1_close.md` (the original close) and
`docs/v2/SIM_Test_Execution_2026-08-30_sync_check_retire.md` (this pass).

**`E2E-VZ-01`'s `PASS`, from here on, means C++-vs-frozen-snapshot, not
two live implementations agreeing** — the Python side that used to be the
second half of that comparison no longer exists. Stated explicitly in the
closing Test Execution record so it is never over-read later.

## B2 — Corrected 2026-08-30: not a remnant, do not delete · **388 lines, not ~4,900**

**This row was wrong** (a 2026-08-27 misreading) and is corrected in place so no
future session repeats it, per this row's own `Do not` in `START_HERE.md`.

`modules/df/src/platform/df_viz/` is **not** a half-finished extraction. It is
`df`'s viz plug-in — real, load-bearing, and current:

- `df_viz_c.cpp`/`.h` (202 lines) — the `df_viz.dll` **composition root**
  (`R-SIM-20`'s "authored in the component, deployed beside its library").
- `layers/` (892 lines) — `df`'s own layer providers (`bsd.cpp`, `common.cpp`,
  `port_tree.cpp`) — component content that belongs in the component by
  `R-SIM-1`, never in `modules/viz`.
- `viz/theme/r1_theme_init.{cpp,hpp}` + `viz/viewport/r1_viewport_init.{cpp,hpp}`
  (211 lines) — `df`'s own R1 theme-token/viewport registration. **Not
  duplicated toolkit**: the shared toolkit (`modules/viz`) ships no component
  style tokens by design (`R-SIM-1`), so every component registers its own.
- The rest of the tree (scripts/, most of tests/, tools/) is component-scoped
  build-invariant checks and unit tests exercising `df`'s own generated data —
  see the audit below for the one place this is not true.

**Verified against the build, not just the plan's prose (2026-08-30):** both
`sil_viz` and `cm_viz` targets build `df_viz.dll` and deploy it beside
`df_sil.dll` (`modules/df/conf/build.yml`); `viz::host::PushHost`
(`modules/viz/cpp/viz/host/push_host.{cpp,hpp}`) loads it at run time from
`modules/df/src/platform/cm/src/user_hooks.cpp`. **Deleting this directory
would break CarMaker visualization outright.**

### Audit — is anything here genuinely duplicated in `modules/viz`?

Checked `tools/`, `scripts/`, `tests/` against their `modules/viz` counterparts
by diff, not by name-matching:

- **`scripts/check_dependency_graph.py`, `check_toolkit_isolation.py`** — same
  *pattern* as `modules/viz/scripts/`'s own copies, but genuinely different
  content (df's own `SI-01..10` item map vs. viz's `FS_DIRS`/`INCLUDE_DIRS`,
  different `ALLOWED_DIRS`). Each checks its own tree. Not duplicates — keep.
- **`tests/unit/test_theme.cpp`, `test_render_gl.cpp`, `test_render_svg.cpp`,
  `test_scene.cpp`, `test_scene_history.cpp`, `test_viewport.cpp`,
  `test_manifest_no_protobuf.cpp`** — same filenames as `modules/viz/tests/`,
  substantially different content. `test_theme.cpp` is the clearest case:
  `modules/viz`'s own copy tests generic `ThemeTable` machinery against a
  *synthetic* vocabulary, by design ("the toolkit's own tests carry no
  component name either" — its own comment); `df`'s copy is `df`'s **real
  coverage test** ("every R1 token resolves in every theme") using `df`'s
  real R1 vocabulary, which the toolkit test's own comment says belongs with
  the component. Not duplicates — keep.
- **`tests/unit/test_furniture.cpp`, `test_history.cpp`, `test_pick.cpp`
  (388 lines) — genuine duplicates.** Byte-identical to
  `modules/viz/tests/unit/`'s own copies except the `COMPONENT:` header line
  (`diff` confirms). Each is compiled and run as its own gtest binary in both
  `df_viz`'s `CMakeLists.txt` and `modules/viz`'s, testing the shared
  `AdasViz::toolkit` code (`furniture.hpp`, `history.hpp`, pick-testing via
  `SceneBuilder`) — not anything `df`-specific, despite using `bsd.*` token
  strings as test data (permitted under the `tests/` carve-out, `R-SIM-1`).
  This is real, scoped B2 content.
- `tests/combined_dll/`, `tests/scene_only_host/`, `tools/demo_viewer.cpp`,
  `scripts/check_layers_toolkit_boundary.py`, `check_no_intree_toolkit.py`,
  `gen_viz_shim.py` — no same-named counterpart in `modules/viz` at all. Not
  duplicates.

**Revised B2, scoped to what is actually redundant:**

1. **Gate:** confirm `df_viz_test_furniture`/`df_viz_test_history`/
   `df_viz_test_pick` assert nothing `df`-specific (re-read alongside
   `modules/viz`'s copies — done above) and that `modules/viz`'s own test
   suite already covers the same assertions (it does; it is the same file).
2. Delete `modules/df/src/platform/df_viz/tests/unit/test_furniture.cpp`,
   `test_history.cpp`, `test_pick.cpp` and their three `add_executable`/
   `add_test` blocks in `df_viz/CMakeLists.txt`.
3. **Verify:** `df_viz` still builds and its remaining tests pass; no
   coverage is lost (the deleted assertions still run under
   `modules/viz`'s own suite).

**Not executed this pass** — corrected and scoped only, per the ask.

## B3 — Delete legacy tooling · **re-scoped against code + git log, 2026-08-30. Nothing deleted this pass.**

The tooling the `R-SIM` rules were written to replace, still present — but
"still present" turned out to mean different things per row. Checked each
row's build and `git log`, not the plan's prose, the same way `B2` was
verified, per the standing instruction to never trust a size/staleness claim
in this file without re-measuring it.

| Target | Plan said | Found | Verdict |
|---|---|---|---|
| `modules/df/tools/carla/` | ~3,200 lines, legacy | 2,787 (excl. `__pycache__`); **last commit 2026-08-20** (`ff27fd0`) and, four days before that, real feature work (`56c87f3`, "`--step` gets a paced Play/Pause/Step/speed/fast-forward panel") | **Not legacy — active.** Caution stands as written (see below). Not deleted |
| `modules/df/tools/carla/replay/viz.py` | 561 lines, sibling target, gate: "the viz player renders the same recordings" | 561 confirmed, nested inside row 1 (unchanged finding). **Actively imported**: `df_dll_sim_mcap.py:450` does `import viz as viz_module`, and `df_dll_sim_mcap.py` is exactly what `df_sim_gui.py`'s REPLAY & FOXGLOVE section launches (`df_sim_gui.py:675`). Not orphaned by any measure | **Not orphaned — in active use through the current GUI.** Gate still unmet regardless (`vantage_app.exe` has no bare-replay mode, `START_HERE.md` open risk 4). Not deleted |
| ~~`scripts/df_sim_gui.py`~~ → **`modules/df/scripts/df_sim_gui.py`** | 658 lines, gate: `vantage.bat` covers what it did | 863 lines. Extended **2026-08-29** (`250be04`, one day after this plan was written) with a whole new CarMaker section; the file's own header states extending it — rather than adding a fourth `sim_gui`-shaped launcher — was a **deliberate call against R-SIM-1's "don't extend the old structure"**, because that section reuses `run_bsd_straight_suite.bat` as its one entry point and is not part of the CARLA/MCAP world R-SIM-1 targets. `vantage.bat` has no CarMaker capability and cannot cover that section, ever | **Row retired as written; re-scoped.** This file does not get deleted as a unit. Its CARLA + REPLAY sections (the two `_ProcessRunner` blocks launching `carla_bridge.py`/`df_dll_sim_mcap.py`) are the only part `vantage.bat` could ever supersede, and only once rows 1/2 above close their own gates — neither has. The CARMAKER section is current, real, load-bearing, and is **never** in scope for this row. Not deleted |
| `modules/df/docs/bsd/py/bsdviz/` | 1,878 lines, gate: "the layer plug-ins cover it" | 1,878 confirmed (excl. `__pycache__`). `bsdviz` itself dormant since 2026-07-29 — **but actively imported by 8 files that are not dormant**: every file under `docs/bsd/py/figures/` (`a_convention.py` through `v_vehicledynamics.py`) does `from bsdviz import ...`, driven by `df_bsd_image_creation.py`. These are documentation-figure generators (`df_bsd_image_creation.md`), a different purpose from the live C++ layer plug-ins entirely — one draws teaching diagrams for docs, the other draws the live BEV. "The layer plug-ins cover it" does not hold; nothing about live rendering supersedes a figure generator | **Gate does not hold — this was heading toward a third `B2`-shaped mistake.** Not orphaned, not superseded by anything named in this plan. Not deleted |

**Net effect of this pass: zero rows are ready to execute.** Every row's
premise (legacy, orphaned, or superseded by a named replacement) failed
verification against the code. `B3` is not close to done; it needs its
targets re-identified, not just its gates re-checked.

> ⚠ **Caution — unchanged, still binding.** `carla_bridge.py` inside
> `tools/carla/` is what **generates the recordings**. The parked scenario
> finding (only 4 of 18 recordings exist; the warning never fires in any that
> run) is entangled with it and is confirmed still parked as of this pass
> (`START_HERE.md`'s parked table, unpark condition: *"Before `B3` deletes
> `tools/carla/`"*). **Resolve the parked finding, or confirm ERG replaces
> this corpus entirely, before touching row 1 — which, independently, is not
> legacy tooling anyway per the finding above.**

## B4 — Resolve the Python/C++ overlap · Decision A · **re-measured 2026-08-30, re-scoped to one item, nothing deleted**

`adas_sim` is 18,560 lines today, not the original 26,272 (`B1`/`SM-12`
deleted the Python scene/render/player tree 2026-08-29, after this row was
written — drift, not a misreading). `simcore` is 31,406, close to the
original 31,064.

**Each of the five named overlaps checked individually — by reading the
code and its own header comments, not by re-running the earlier line-count
sweep** (the method `MOVEMENT_B_PLAN.md`'s own audit note above says this
file must stop trusting):

| Item | Python (`adas_sim`) | C++ (`simcore`) | Verdict |
|---|---|---|---|
| `io` | `io/` — 5 files, 1,266 lines. Format codecs (`base`/`csv`/`jsonl`/`mcap.py`) | `io/` — 10 files, 1,673 lines | **Genuine second implementation.** `simcore/io/registry.cpp`'s own header: *"Ports `io/registry.py`'s `register`/`reader_for`/`writer_for` behaviour."* `codecs/mcap.cpp`'s own header: *"the C++ twin of `io/mcap.py`... ported"* — and **honestly documents its own gap**: it does not yet replicate `io/mcap.py`'s `manifest_version >= CAPTURE_TIME_MANIFEST_VERSION` gate. Real overlap, but the C++ side's own comment says it is not yet at parity — not safe to act on this pass regardless |
| `runspec` | `runspec/` — 6 files, 1,614 lines. `emit.py`: *"the seam's own producer"* | `runspec/` — 1 file, `load.cpp`, 255 lines | **Not a duplicate.** `load.cpp`'s own header: *"parses the JSON text `emit_run_spec`/`write_run_spec` produced"* — a consumer of Python's output, never a competing builder. Producer and consumer sharing a folder name, exactly the documented `WP-05` seam. Nothing to resolve |
| `session` | `session/` — 4 files, 749 lines, actively imported by 11 real source files (`check/`, `cli/`, `config/`, `core/runner.py`, `diagnostics/`×3, `graph/build.py`, `pyapi/api.py`) + 14 test files | none in `simcore` | **Real duplicate — but not here.** `modules/viz/cpp/viz/session/session.hpp`'s own header: *"the C++ rewrite of `adas_sim.session.session.Session`, living in `adas-viz-player`."* Both sides are live and used today. This is a genuine cross-**module** overlap (`sim` vs `viz`), outside `B4`'s own stated scope (*"`modules/sim/src` carries two stacks"*) — a `sim`-internal deletion pass cannot resolve it. Its own initiative, not a `B4` line item |
| `abi` | none in `adas_sim` | `abi/simcore.cpp` — 514 lines. `simEngineCreate`/`Run`/`Destroy`, the engine's own generic ABI | **Not an overlap at all.** This is the per-tick engine's own entry point — C++-only by design, the whole point of Decision A. Python has no equivalent because Python no longer hosts a per-tick engine. Asymmetric on purpose, nothing missing |
| `diagnostics` | `diagnostics/` — 13 files, 1,724 lines: `determinism` (cross-run comparison), `explain`/`evidence` (`sim explain` CLI facts), `tolerance`, `suggest`, `console` — reporting/CLI, once-per-run | `diagnostics/` — 6 files, 470 lines: `breakpoints`, `reproducer` (crash-dump writer hooked into the engine's own crash detection), `trace` (per-cycle hook inside the execution loop) — runtime engine instrumentation | **Not a duplicate.** Different concerns sharing a directory name: Python is offline reporting/tooling, C++ is in-loop engine instrumentation. `evidence.py`'s own header even names the split explicitly: *"viz's own C++ evidence chain (`BuildEvidence`) is the live [formatter]"* for the runtime half; this file stays the headless `--at` half |

**Net: 1 of 5 rows is real** (`io`), and even that one is not actionable this
pass — the C++ side's own comment documents an unresolved capability gap, so
"prove parity, delete the loser" cannot run yet. `runspec`, `abi` and
`diagnostics` were never overlaps; `session` is a real overlap but belongs to
a `sim`/`viz` cross-module initiative `B4` was never scoped to reach.

**`B4` is re-scoped, not retired** — unlike `B3`, it is not empty: `io` is a
real, named, tracked gap. Retained as a single item (close the
`manifest_version`/capture-time parity gap in `simcore/io/codecs/mcap.cpp`,
then delete `adas_sim/io/`'s overlapping half) rather than the original
five-row table. `WP-16` (10/11 boxes, 1 left, unchanged — `sil_host`
retirement) and `WP-02`'s "seven duplications"/restructure claims were **not
independently re-verified this pass** — out of the five-overlap scope this
session was asked to re-measure; flagged so a future pass does not assume
they were.

**Do not over-delete.** Python still legitimately owns the once-per-run half
— resim, config resolution, the run spec. The engine split is a stated rule:
*per tick is C++, once per run is Python*, joined by the Resolved Run Spec
(`WP-05`, the seam). Python that has no C++ replacement is not dead code.
Full account: `docs/v2/SIM_Test_Execution_2026-08-30_b4_remeasure.md`.

## ~~B5 — Readers and writers~~ · **PARKED 2026-08-27**

`WP-17` (11 boxes) and `WP-18` (11) are parked with ERG. They were on the
critical path only because ERG needed them; `mcap` read and write already work
on both the Python and C++ sides, which is all the revised demo requires.

**Unpark when** a real measurement in a format sim cannot yet read arrives —
ERG, MDF4, rosbag. The `.erg` codec is already written, so that day starts from
`WP-17`, not from zero.

---

## Order, and why

```
B1 (viz, 10 boxes)  ──►  B2 (388-line test dedup)  ──►  B4 (io parity gap, 1 item)
                                │
          B3 (legacy tooling)  ◄┘   only after the parked scenario
                                    finding is resolved, or ruled irrelevant
```

B1 first: small, finishes a whole 43-item plan, and one of its boxes stops every
future session being misinformed on its first read. B4 last — **re-scoped
2026-08-30 from a five-row Python/C++ overlap sweep to one item** (`io`'s
`mcap.py`/`mcap.cpp` parity gap), smaller than originally thought and still not
urgent now that ERG is parked.

**Movement B no longer blocks the demo.** With ERG gone, the demo's critical path
(`DEMO_AND_SCOPE.md` §5) runs entirely through already-part-built packages —
chiefly `WP-28`, which has one design item left. **If the goal is to see the demo
soonest, do Movement C's step zero first and Movement B after.** Movement B is
the debt that makes the next six months cheap; it is not the gate on the POC.

## Definition of done for Movement B

1. The viz sync plan has deleted itself.
2. `modules/df/src/platform/df_viz/` **stays** — it is `df`'s real viz plug-in
   (corrected 2026-08-30). Its 3 duplicate toolkit tests (388 lines) are gone.
3. ~~Exactly one implementation of io, session, abi, runspec and diagnostics.~~
   **Corrected 2026-08-30** — only `io` is a genuine second implementation;
   `runspec`/`abi`/`diagnostics` are asymmetric by design (producer/consumer,
   engine-only, and different concerns sharing a name, respectively) and were
   never meant to converge. `session`'s real duplicate is cross-module
   (`sim` Python vs `viz` C++), outside this movement's own scope. Revised:
   `io`'s C++ codec reaches parity with `io/mcap.py` (the documented
   `manifest_version`/capture-time gap closes), then `adas_sim/io/`'s
   overlapping half is deleted.
4. The gate is green with no parked-failure exceptions other than WP-31 scope.
5. ~~`sim` can read a real ERG measurement end to end.~~ *Parked with ERG.*

---

## Two findings to decide on separately

**1. The parked scenario finding.** Only 4 of 18 scenarios can run; of those, the
single passing one asserts `warning == 'OFF' always` — it passes by asserting
nothing happens — while all three that assert a warning fires report *never
became*. Parked by decision on 2026-08-27. It is entangled with B3 (above) and
with the demo, which is *"see the BEV with objects and the warning zone."*

**2. ~~A company email domain appears in 419 files~~ — settled 2026-08-27.**
Writing the organisation as **L&T EPS** is approved, so the 419 files are not a
confidentiality problem and no scrub is required. If the spelling is ever
normalised, `docs/file_header_template.md` is the one file that matters — every
new file inherits from it, which is why the string spread this far.
