# START HERE

**Updated:** 2026-08-27 · **Read this first, then run the status command below.**

> **This file contains no counts, and must never contain any.** Numbers go stale
> the day after they are typed; this module already lost twelve stages to a
> hand-kept status table that read `frozen` on most rows while the work shipped.
> **Anything countable is computed:**
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
**Movement C** ← **we are here, at step zero.**

The 2026-08-27 reset re-scoped this module around one watchable demo instead of a
completion percentage. Read `memory.md` for why, `DEMO_AND_SCOPE.md` for the
demo and the finite list, `MOVEMENT_B_PLAN.md` for the deletion work.

## The next action — exactly one

> **Produce one recording containing df's *outputs*, then confirm
> `mode: measured` consumes it.**

About an hour. `R-SIM-6` (record every port, in *and* out) says this works and is
marked **built** — but built is not demonstrated, and every recording today is
stimulus-only with no computed outputs. **This one check decides whether the demo
is close or blocked**, and finding out costs an hour instead of 22 boxes of io
work.

If it works → `WP-28` (the launcher toggle, red item #8) is the rest of the demo.
If it fails → that is the first real defect, and it outranks everything else.

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

1. **Step zero is unverified** (see *next action*). Replaced ERG as the top risk.
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

Before you finish, update exactly three things in this file: **Where we are**,
**The next action**, and one line in the log. Nothing else. If this file grew, it
has failed.

## Log — newest first, one line each, keep about five

- **2026-08-27** — Reset session. Diagnosed why the work felt endless (resume
  pointer always said `WP-01`; nothing ever deleted after replacement;
  specification outgrew the product). Movement A: pointer fixed, CI trigger found
  dead and repointed, first Test Execution Record written. Gate went 12 failures →
  1 (parked). ERG found unobtainable → demo rewritten around a self-produced
  recording. **26 files uncommitted in `modules/sim` — reviewed, green, not
  committed.**
