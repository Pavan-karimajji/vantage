# START HERE

**Updated:** 2026-08-27 · **Read this first, then run the status command below.**

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
**Movement B** ⏸ planned, deliberately **not** started — it is no longer the gate.
**Movement C** ← **we are here. The demo runs, watched; one clause of it is
still answered `unknown`.**

The 2026-08-27 reset re-scoped this module around one watchable demo instead of a
completion percentage. Read `memory.md` for why, `DEMO_AND_SCOPE.md` for the
demo and the finite list, `MOVEMENT_B_PLAN.md` for the deletion work.

**The demo runs.** `WP-35` was opened for it (authorised 2026-08-28, scoped
verbatim to `DEMO_AND_SCOPE.md` §1) and the launcher now carries the
measured/simulated control. Four of §1's five clauses are demonstrated and
screenshotted; the fifth is three-quarters answered. Records:
**`…_2026-08-28.md`** (the fixes), **`…_2026-08-28_wp28.md`** (`F-7`),
**`…_2026-08-28_wp35.md`** (the demo, its screenshots and `F-8`).

## The next action — exactly one

> **`F-8` — make `sim explain` join `run_id` → the manifest's `components[]`,
> so a port's **build** is answered instead of read `unknown`.**

It is the only clause of §1 the demo cannot yet satisfy, and the last box of
`WP-35`. The data is already in the recording
(`ComponentBuildInfo(name='df', library_sha256='b3524ca8…')`); `R-SIM-25` says
this join needs no new capture and no new index. It lives in `diagnostics`, not
the launcher — which is why `WP-35` recorded it rather than absorbing it.

When that closes, the POC demo is complete and the freeze ends by its own
terms.

## Do not

- **Do not propose a sim v3.** Two rewrites already happened. A third would repeat
  a failure this module has documented twice.
- **The specification freeze is in force.** No new requirements, no new work
  packages, no new design documents until the demo runs. Corrections are allowed;
  new scope goes to the parked list in `DEMO_AND_SCOPE.md` §4.2.
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
| `WP-19` `WP-30` `WP-31` | No demo dependency | The demo runs — **`F-8` is the last clause**; unpark then |
| The scenario finding — **now only its corpus half** (4 of 18 runnable, one vacuous pass). The three *"never became"* failures were `F-1` and are fixed | Author's call, 2026-08-27 | Before `B3` deletes `tools/carla/`, or when coverage rather than the warning path matters |
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
3. **The scenario corpus is thin, and one green is false.** Only 4 of 18
   scenarios can run. Three now assert real firing behaviour; the fourth
   (`bsd_curve_r172_passby`) passes only because nothing reaches the component —
   it needs `WP-12`'s ingest map. Do not mistake a green `sim check` for coverage.

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

- **2026-08-28** — `WP-35` opened (the demo, §1 verbatim) and the launcher wired
  to `adas_sim.launcher`. Demo run for real: both modes, both pictures agree,
  screenshotted. `F-8` found — build reads `unknown` though the recording
  carries it. Record: `…_2026-08-28_wp35.md`. **Not committed.**
- **2026-08-28** — `WP-28` driven against the real demo through its own API:
  both toggle directions launch. Found and fixed `F-7` (every cut reported
  infeasible against a real recording — an untested join). The visible half has
  no box; that is the open decision. Record: `…_2026-08-28_wp28.md`.
- **2026-08-28** — `F-1`/`F-2`/`F-3` fixed in `simcore`, `F-4` corrected in the
  plan; rebuilt and verified on both platforms. `sim check` 3 failed → 0, no
  regressions, one new finding (`F-6`). Record:
  `docs/v2/SIM_Test_Execution_2026-08-28.md`.
- **2026-08-27** — Findings from the step-zero run verified and written up as a
  Test Execution Record (`_step_zero`); this file trimmed back and its no-counts
  rule sharpened to *no derived progress state* (dated evidence is fine).
- **2026-08-27** — Step zero run for real. Toggle confirmed byte-identical on
  firing AEB data; five findings, `F-3` blocks the demo's shape.
