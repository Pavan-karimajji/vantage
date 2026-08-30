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
**Movement B** ✅ `B1` fully closed (2026-08-29), and both of its own named
exceptions closed 2026-08-30: `sync_check.py` deleted, `next.py` rewritten
"minus its gate table", `check_cross_module_trace.py`'s 60 findings triaged
(56 parser gap, fixed; 3 real, in df's design doc, left for df to fix). See
`MOVEMENT_B_PLAN.md`'s own updated B1 row and
`docs/v2/SIM_Test_Execution_2026-08-30_sync_check_retire.md`.
**Movement C** ← **the POC demo runs, all five clauses, watched. The freeze
ends by its own terms.**
`MOVEMENT_B_PLAN.md`'s `B2` was corrected 2026-08-30 — it would have deleted
`df`'s real CarMaker viz plug-in on a 2026-08-27 misreading — and then
**executed** the same day, re-scoped to its real content: 3 duplicate test
files (388 lines), removed from `modules/df` behind a real vs2026 build
(314/315 → 311/312 tests, exactly 3 fewer test binaries, one pre-existing
unrelated failure unchanged). `B3` was fully re-scoped the same day: all four
rows failed verification against the code — `tools/carla/` and `replay/viz.py`
are both active (not legacy), `df_sim_gui.py` is retired as a deletion target
(its CarMaker section is current, real work), `bsdviz/`'s "gate" doesn't hold
(8 files still import it). **Zero `B3` rows are ready to execute.** See
`docs/v2/SIM_Test_Execution_2026-08-30_movement_b_plan_audit.md` (the
correction) and
`docs/v2/SIM_Test_Execution_2026-08-30_b2_execute_b3_rescope.md` (execution +
re-scope). Not yet committed — `modules/df`'s change is staged only.

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

> **`B2` is done** (388 lines, executed 2026-08-30, staged not committed in
> `modules/df`) and **`B3` is re-scoped to empty** — all four of its rows
> turned out to name active or non-superseded code, not legacy; none are
> ready to execute, and it needs its targets re-identified before it can be
> planned again, not just re-gated. Neither commit has happened yet — ask
> before committing (`R-GIT-1`: `df` first, then this pointer). The Movement C
> scope conversation this file named before `B1` started (`DEMO_AND_SCOPE.md`
> §1's *"may begin. Not before"*) is still the standing open question and this
> session did not touch it. `B4` and item `#20` were explicitly withheld this
> pass.

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
- **2026-08-29** — `B1` (viz sync plan) fully closed: `SM-10`/`SM-05`/`SM-07`/
  `SM-12`/`SM-08` all done, the Python scene/render/player tree deleted,
  `ANL-SM-03`/`ANL-SM-02` both real and green. Sync plan retired its own §2/§3
  per §6.6. `E2E-VZ-01`'s `PASS` now means C++-vs-frozen-snapshot, not two
  live implementations — stated explicitly so it isn't over-read later.
  Record: `docs/v2/SIM_Test_Execution_2026-08-29_b1_close.md`.
- **2026-08-28** — Ingest map wired end to end (`#5` red → green): the emitter,
  the engine's spec parser, and a `Translator` that had no caller. A legacy
  recording went from 218 empty ticks to real data; `bsd_curve_r172_passby`
  stayed green but stopped being false. Record: `…_2026-08-28_ingest.md`.
