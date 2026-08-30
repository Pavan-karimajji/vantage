# START HERE

**Updated:** 2026-08-30 · **Read this first, then run the status command below.**

> **No derived progress state in this file, ever** — no "N of M done", no
> per-item status, no checklist. That is what goes stale: this module already
> lost twelve stages to a hand-kept table reading `frozen` on most rows while the
> work shipped. *Dated evidence is fine* — `t=2.300 s`, a file, a line number —
> because a measurement from a named run is history, not state.
> **Anything derived is computed:**
>
> ```
> cd modules/sim && python docs/v2/py/trace_check.py --status
> ```
>
> That is the authority for *what is built*. This file is the authority for
> *what we are doing and why* — the part no tool can derive.

---

## Where we are

**Movement A** ✅ done, except one item blocked on the author (a push).
**Movement B** — `B1` closed 2026-08-29. `B2` corrected, re-scoped and
executed 2026-08-30 (388 lines, `modules/df`, committed/pushed). `B3`
re-scoped 2026-08-30 to empty — none of its four rows were real (see
`MOVEMENT_B_PLAN.md`). `B4` re-measured 2026-08-30 to one real item (`io`'s
Python/C++ parity gap, not yet actionable) — the other four claimed overlaps
were never overlaps. **Movement B is therefore not fully done** (that one
`io` item remains), but every row in `MOVEMENT_B_PLAN.md` now rests on
verified code, not a stale claim. `misc/memory.md` §3 corrected to match
(it was written from a day-one line-count/directory sweep, never the build
or `git log`). Records: `docs/v2/SIM_Test_Execution_2026-08-30_movement_b_plan_audit.md`,
`..._b2_execute_b3_rescope.md`, `..._b4_remeasure.md`.
**Movement C** ← **the POC demo runs, all five clauses, watched. The freeze
ends by its own terms.**

**CarMaker viz pipeline de-risked for a near-term demo, 2026-08-30 — no risk
found.** Clean `cm_viz` rebuild, both DLLs confirmed freshly deployed, a real
BSD TestRun run headless and live with the `df_viz` window screenshotted
showing `bsd.zone`/`bsd.warning`/`bsd.sensor_fov` registered and rendering.
`df_viz_test_render_svg`'s failure is root-caused, recorded as a known,
understood, author-decided-not-to-fix issue (SVG-test-only, zero live-picture
impact — `df_viz_Software_Test_Spec_v0.1.md` §8's own disposition note now
carries the one-line fix, so nobody re-investigates it), **not open.** Filed
on the `df` side: `modules/df/docs/viz/df_viz_Test_Execution_2026-08-30.md`.

The 2026-08-27 reset re-scoped this module around one watchable demo instead of a
completion percentage. Read `memory.md` for why, `DEMO_AND_SCOPE.md` for the
demo and the finite list, `MOVEMENT_B_PLAN.md` for the deletion work.
**To actually run the demo: `RUN_THE_DEMO.md` in this folder.**

**`DEMO_AND_SCOPE.md` §1 runs, end to end, all five clauses** — launcher,
self-produced recording, both modes, both pictures agreeing, and an object's
provenance answered down to the build. `WP-35` closed. Records, newest first:
**`…_2026-08-28_f8.md`** (the fifth clause), **`…_wp35.md`** (the demo and its
screenshots), **`…_wp28.md`** (`F-7`), **`…_2026-08-28.md`** (the step-zero
fixes).

## The next action — exactly one

> **`B1`/`B2`/`B3` are settled** (`B1` closed, `B2` done and pushed, `B3`
> empty). **`B4` is re-scoped to one real, named, not-yet-actionable item**
> (`io`'s `mcap.py`/`mcap.cpp` parity gap) — `Movement B` is not fully done,
> but nothing in it rests on an unverified claim any more. The CarMaker viz
> pipeline is de-risked for the demo, and `df_viz_test_render_svg` is now a
> closed, understood, deliberately-not-fixed question — neither needs
> re-investigating. The Movement C scope conversation this file named before
> `B1` started (`DEMO_AND_SCOPE.md` §1's *"may begin. Not before"*) is still
> the standing open question and this session did not touch it. Item `#20`
> was explicitly withheld again this pass.

## Do not

- **Do not propose a sim v3.** Two rewrites already happened. A third would repeat
  a failure this module has documented twice.
- **The specification freeze has ended by its own terms** (2026-08-28 — it ran
  *"until the demo runs"*, and it does). That is not licence to resume writing:
  what it outgrew the product by is in `memory.md` §4. New scope is now the
  author's call, from `DEMO_AND_SCOPE.md` §4.2's parked list.
- **Do not start Movement B to feel productive.** It is real debt, but it does not
  gate the POC.
- **Do not resume `docs/v1/`.** It is evidence, never a build order.

## Decisions in force

| | Decision | Taken |
|---|---|---|
| **A** | C++ wherever there is scope; the Python run path is legacy | 2026-08-27 |
| **B** | The player lives permanently in viz, as C++; Python player/scene deleted | 2026-08-27 |
| **C** | ~~ERG is the format~~ → **parked**, no measurement exists. POC runs on `mcap` | 2026-08-27 |
| **D** | vdy is the second module, but months away — nothing may depend on it | 2026-08-27 |
| **E** | The demo *is* the definition of done, explicitly as a POC | 2026-08-27 |

## Parked — and what unparks each

| Parked | Why | Unpark when |
|---|---|---|
| ERG · `WP-17` · `WP-18` | No ERG measurement exists or can be obtained | Real data arrives in a format sim cannot read |
| `WP-19` `WP-30` `WP-31` | No demo dependency | **Condition met 2026-08-28 — the demo runs.** Unparking them is now a scope decision, not a wait |
| The scenario finding — **now only its corpus half** (4 of 18 runnable, and those four under-asserted). Every *"never became"* and every vacuous pass is fixed | Author's call, 2026-08-27 | Before `B3` deletes `tools/carla/`, or when coverage rather than the warning path matters |
| 155 `R-REQ-9` citations | Bookkeeping, not code | `WP-31` |
| Conan editable test | `WP-31` scope | `WP-31` |

## Open risks

1. **A recording carrying no provenance grade still computes nothing** (`F-6`,
   2026-08-28 record). Validity is inferred from evidence grade, so a foreign or
   supplier file has every input flagged invalid — `F-1`'s symptom by a second
   route. Not on the demo path; does not report itself.
2. **`WP-01` cannot close** until a real GitHub Actions run is observed passing.
   The trigger was fixed 2026-08-27 and the push it was waiting on happened
   **2026-08-28** — so a run may now exist, unobserved: `gh` is not installed
   here. Someone must look. The gate itself still exits 1 on two parked items.
3. **The scenario corpus is thin and under-asserted.** Only 4 of 18 scenarios
   can run. All four now assert real computed behaviour (`bsd_curve_r172_passby`
   stopped being a false green 2026-08-28) — but its BSD warning fires at
   t≈7.4–9.6 s with no expectation covering it. Green is not coverage.
4. **A real capability loss, not silently dropped** (`SM-12`, 2026-08-29):
   `vantage_app.exe` has no bare-replay mode (no `--pipeline`) and no
   `--preset`/`--at`/`--workspace`/`--version` — the Python viewer that used
   to serve them is deleted, and there is no native equivalent yet.

## How Movement C gets tracked when it grows

Movement C will be done in pieces. **Those pieces are `WP` boxes in
`docs/v2/SIM_Implementation_Plan_v0.1.md`, tracked by `trace_check.py` like
everything else** — not a list in this file. This file only ever names the
*current* piece, in *The next action* above.

If you find yourself adding a checklist here, stop: that is a second copy of the
plan's state, and it will drift from it.

## Ending a session

Always update these three: **Where we are**, **The next action**, and one line in
the log.

Also update **Decisions**, **Parked** or **Open risks** — but *only* when the
underlying fact actually changed (a decision taken, an item unparked, a risk
retired), and by **replacing** a row, never appending one. Everything else stays
untouched.

**Analysis does not go here.** A campaign's findings and evidence go in a
`docs/v2/SIM_Test_Execution_<date>[_<campaign>].md`; this file links to it in one
line. That is what keeps this file one screen — **if it grew, it has failed.**

## Log — newest first, one line each, keep about five

- **2026-08-30** — Prior pass's `B2`/CarMaker work committed/pushed
  (R-GIT-1: `df` `b980fd9`, `sim` `a551d37`, superproject `a63ee3a`). Then:
  (1) `df_viz_test_render_svg` recorded as a **known, understood, not-open**
  failure in `df_viz_Software_Test_Spec_v0.1.md` §8 (the one-line fix named,
  test left unchanged, per instruction). (2) `misc/memory.md` §3 corrected —
  its "~6,300 lines of superseded tooling, all still present" claim (and the
  adjacent df_viz-as-old-toolkit claim) were both wrong, disproved by this
  week's `B2`/`B3` audits; replaced with what was actually found plus why
  (a day-one line-count sweep, never the build or `git log`). (3) `B4`
  re-measured per-item, not just re-sized: only `io` is a genuine overlap
  (and its own C++ code admits it isn't at parity); `runspec` is a
  producer/consumer pair, `abi` is C++-only by design, `diagnostics` is two
  different concerns, `session`'s real duplicate is cross-module
  (`sim` Python vs `viz` C++, outside `B4`'s scope). `B4` rewritten to one
  item; Movement B is not fully done. Nothing deleted. Record:
  `docs/v2/SIM_Test_Execution_2026-08-30_b4_remeasure.md`.
- **2026-08-30** — Author priority: de-risk CarMaker viz for a near-term demo.
  `B2`/`B3` work from earlier today committed/pushed first, R-GIT-1 order
  (`df` `6be858e`, `sim` `bc49152`, superproject `19211b2`). Then a clean
  `cm_viz` rebuild on vs2026 (two pre-existing env breaks fixed: stale
  `adas-mathlib` Conan editable, `adas-local` auth), `df_sil.dll`/`df_viz.dll`
  confirmed freshly deployed, a real BSD TestRun run both headless (clean) and
  live with the `df_viz` window screenshotted showing `bsd.zone`/
  `bsd.warning`/`bsd.sensor_fov` registered and rendering. No risk found.
  Separately root-caused `df_viz_test_render_svg`'s failure via `git log`: a
  stale token in one test file, missed by a 2026-08-26 rename sweep that fixed
  its two sibling tests — confirmed SVG-only, zero live-picture impact, not
  fixed per instruction. Filed on the `df` side (nothing here touched
  `modules/sim`): `modules/df/docs/viz/df_viz_Test_Execution_2026-08-30.md`.
- **2026-08-30** — `B2` executed for real in `modules/df`: gated on a live
  vs2026 build (recovered two pre-existing environment breaks first — a
  stale `adas-mathlib` Conan editable pointing at a different checkout on
  this machine, and the known `adas-local` auth gap), baseline 314/315 tests
  green, deleted the 3 duplicate test files + their CMake blocks, rebuilt
  green at 311/312 (exactly 3 fewer test binaries, same 1 pre-existing
  unrelated failure). Then `B3` fully re-scoped against the build and `git
  log`: all four rows turned out to name active or non-superseded code, not
  legacy — `tools/carla/` and `replay/viz.py` both have recent real activity
  and `replay/viz.py` is actively imported through the current GUI;
  `df_sim_gui.py` retired as a deletion target; `bsdviz/`'s gate fails
  (8 figure-generator files still import it). Zero `B3` rows ready to
  execute. Staged in `modules/df`, not committed. Record:
  `docs/v2/SIM_Test_Execution_2026-08-30_b2_execute_b3_rescope.md`.
- **2026-08-30** — `MOVEMENT_B_PLAN.md` audited against the code, not its own
  prose. `B2`'s "delete `df_viz`, ~4,900-line half-finished extraction" was
  wrong — it is `df`'s real CarMaker viz plug-in (`sil_viz`/`cm_viz` build it,
  `PushHost` loads it); deleting it would have broken CarMaker visualization.
  Rewritten and re-scoped to the 388 lines of genuine duplicate toolkit tests
  it actually has (`test_furniture`/`test_history`/`test_pick.cpp`, byte-
  identical to `modules/viz`'s own copies). `B3` row 3 (`df_sim_gui.py`) was
  heading the same way — extended with real CarMaker functionality one day
  after the plan was written — flagged, not yet re-scoped. `B4`'s sizes were
  stale from `B1` closing, not a misreading. Nothing executed. Record:
  `docs/v2/SIM_Test_Execution_2026-08-30_movement_b_plan_audit.md`.
- **2026-08-30** — Both exceptions `B1`'s closing record named are closed:
  `sync_check.py` deleted, `scripts/next.py` rewritten "minus its gate table"
  (runs each module's own `trace_check.py` instead of parsing the retired
  sync plan §2/§3). `check_cross_module_trace.py`'s 60 `BROKEN` findings
  triaged: 56 were a real parser gap (a third disposition-table definition
  shape sim uses, now recognized — also fixed sim showing 0 defined `IMP`
  UIDs), fixed; 3 (`VIZ:IMP-0036`/`0064`/`0065`, in df's design doc) are real
  dangling links, left for df. Record:
  `docs/v2/SIM_Test_Execution_2026-08-30_sync_check_retire.md`.
