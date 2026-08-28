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
**Movement C** ← **we are here. Step zero is done; it found one real defect.**

The 2026-08-27 reset re-scoped this module around one watchable demo instead of a
completion percentage. Read `memory.md` for why, `DEMO_AND_SCOPE.md` for the
demo and the finite list, `MOVEMENT_B_PLAN.md` for the deletion work.

**Step zero is answered: the mechanism works, the demo's shape does not.**
`mode: measured` injects a self-produced recording's outputs byte-identically on
real data — `R-SIM-10` holds. But a self-produced recording **cannot be
re-simulated**, so one file cannot be toggled both ways, and three other defects
sit in front of the demo. Five findings, four independently re-verified:
**`docs/v2/SIM_Test_Execution_2026-08-27_step_zero.md`** — read it before fixing
anything.

## The next action — exactly one

> **Work the fix order in
> `docs/v2/SIM_Test_Execution_2026-08-27_step_zero.md`, starting with `F-1`.**

`F-1` first because nothing else can be judged until resim actually computes:
topic lookup is strict on one side and tolerant on the other, so every resim of a
pre-2026-08-23 recording flags all inputs invalid and publishes neutral output,
exits 0, and warns about nothing.

Then `F-3` — **a design decision before any code.** A self-produced recording
names its input topics after the consuming stage, so it can be replayed but not
re-simulated, and the demo's "one recording, both directions" shape is not
expressible. Choose: record `req` topics under their producing identity, or
rewrite the demo around two recordings. The record recommends the first.

All three of `F-1`/`F-2`/`F-3` are in `simcore` and need a `vs2026` rebuild.
Afterwards `WP-28` (the launcher toggle) is the remaining demo work.

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
| `WP-19` `WP-30` `WP-31` | No demo dependency | The demo runs |
| The scenario finding | Author's call, 2026-08-27 | Before `B3` deletes `tools/carla/`, or when the warning path matters to the demo |
| 155 `R-REQ-9` citations | Bookkeeping, not code | `WP-31` |
| Conan editable test | `WP-31` scope | `WP-31` |

## Open risks

1. **The demo's shape is not expressible today** (`F-3`), and every resim of a
   pre-2026-08-23 recording is silently neutral (`F-1`). Both in the step-zero
   record. Top risks, because neither reports itself.
2. **`WP-01` cannot close** until a real GitHub Actions run is observed passing.
   The workflow trigger was fixed on 2026-08-27; it needs a push. `gh` is not
   installed on this machine.
3. **The scenario corpus is thin and mostly negative.** Only 4 of 18 scenarios can
   run; the one that passes asserts a warning *never* fires. Parked, but do not
   mistake a green `sim check` for coverage.

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

- **2026-08-27** — Findings from the step-zero run verified and written up as a
  Test Execution Record (`_step_zero`); this file trimmed back and its no-counts
  rule sharpened to *no derived progress state* (dated evidence is fine).
- **2026-08-27** — Step zero run for real. Toggle confirmed byte-identical on
  firing AEB data; five findings, `F-3` blocks the demo's shape.
- **2026-08-27** — Reset session. Diagnosed why the work felt endless (resume
  pointer always said `WP-01`; nothing ever deleted after replacement;
  specification outgrew the product). Movement A: pointer fixed, CI trigger found
  dead and repointed, first Test Execution Record written. Gate went 12 failures →
  1 (parked). ERG found unobtainable → demo rewritten around a self-produced
  recording. **26 files uncommitted in `modules/sim` — reviewed, green, not
  committed.**
