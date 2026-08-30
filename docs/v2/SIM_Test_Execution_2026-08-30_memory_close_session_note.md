# SIM — Test Execution Record — 2026-08-30 · `memory.md`'s self-contradiction fixed; cross-repo Session duplication recorded

**This record is evidence, not a specification.** Exempt from the freeze on
that basis, never edited after the fact. A later campaign is a **new file**.
**Reads with:** `..._b4_remeasure.md` (the session-duplication finding this
record's second half makes findable, not new evidence of its own).

## Campaign

| | |
|---|---|
| Question | `misc/memory.md` §3's closing paragraph ("deletion has never once been executed") was left standing directly under a correction saying `B1` deleted the Python scene/render/player stack on 2026-08-29 — a same-section contradiction. Fix it without losing the warning. Separately: `B4`'s re-measure correctly ruled the cross-repo `adas_sim.session`/`viz::session` duplication out of `B4`'s own scope, but scoping it out doesn't make it stop being real — record it somewhere findable, as a known item with no owner, not a `B4` row, and don't act on it. |
| Method | `A` (analysis/documentation only — no code touched, no build run) |
| Scope | `modules/sim/misc/memory.md`, `misc/MOVEMENT_B_PLAN.md` only |
| Committed | Not yet — review-first, per the user's ask |

## Result — `memory.md` §3's contradiction fixed

The closing paragraph asserted, in the present tense, *"deletion has never
once been executed"* — directly beneath this same session's own correction
(added earlier 2026-08-30) stating the opposite: sim's Python scene/render/
player stack really was deleted, 2026-08-29 (`B1`/`SM-12`). Rewritten to say
what actually happened: the copy-never-move pattern was real and held for
three attempts (v1's stalled retirement, v2's still-coexisting stacks, and
sim's own Python player stack before `B1`) — **and `B1` broke it**, the first
executed deletion in this project's history. The warning is kept, pointed at
what is genuinely still undeleted (v1's private tooling, `B4`'s one real item,
the Session duplication below) — reframed as *"one deletion is a proof of
capability, not yet a habit,"* not as a claim that is now simply false.

## Result — cross-repo `Session` duplication recorded, not acted on

Added as item 3 of `MOVEMENT_B_PLAN.md`'s *"findings to decide on
separately"* section (now three items) — the established home in this file
for a real, verified finding that has no clean owner among `B1`–`B4`:

- `modules/sim/src/adas_sim/session/` — Python, 4 files, 749 lines, imported
  by 11 real source files and 14 tests today (verified in the `B4`
  re-measure, unchanged since).
- `modules/viz/cpp/viz/session/session.hpp` — C++, whose own header states
  it is *"the C++ rewrite of `adas_sim.session.session.Session`, living in
  `adas-viz-player`."*

Both are live and used. This is a direct, unaddressed consequence of
Decision B (the player moved permanently into `viz`, as C++, 2026-08-27) —
the Python `Session` was never retired once its C++ replacement existed,
because no plan in either module tracks a cross-module deletion. **Not
acted on** — no code touched, no deletion proposed. Recorded so a future
session finds it instead of rediscovering it from a fresh `B4`-style sweep.

## What this does not close

The Session duplication itself is unresolved and has no owner — that is the
whole point of recording it as a known item rather than pretending `B4`'s
"out of scope" verdict made it go away. Resolving it needs its own
initiative (which module owns `Session` going forward, and what a
cross-module deletion process even looks like in this project) — not
attempted this pass.

## Files changed

| Repo | Scope |
|---|---|
| `modules/sim` | `misc/memory.md` (§3 closing paragraph rewritten), `misc/MOVEMENT_B_PLAN.md` ("Two findings" → "Three findings," item 3 added), this record |

A later campaign is a **new file**, never an edit to this one (`R-REQ-6`).
