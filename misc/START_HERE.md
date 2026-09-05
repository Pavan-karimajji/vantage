# START HERE

**Updated:** 2026-09-05 · **Read this first, then run the status command below.**

> **This file holds only what no tool can derive** — decisions, open risks,
> parked triggers, and the things not to do. No counts, no progress, no
> "N of M": that is `trace_check.py`'s answer, and a second copy goes stale.
> It lost twelve stages once to a hand-kept table reading `frozen` while the
> work shipped.
>
> **Dated evidence is fine** — `t=2.300 s`, a file, a line number — because a
> measurement from a named run is history, not state.

```
cd modules/sim && python docs/v2/py/trace_check.py --status          # the v2 set
cd modules/sim/docs/v2/parity && python py/trace_check.py --status   # the PARITY set
```

**Division of labour, so the two never drift.** `trace_check.py` is the
authority for *what is built*. This file is the authority for *what we are
doing and why*, and **contains no counts at all**.

---

## Where we are

**Movements A, B and C are complete and the demo works** — `DEMO_AND_SCOPE.md`
§1 runs end to end, all five clauses, watched and screenshotted (`WP-35`). A
working system with named gaps in breadth, not a task list with a broken core.

**One item of Movement B remains** — `io`'s Python/C++ parity gap, not yet
actionable. Every other row in `MOVEMENT_B_PLAN.md` rests on verified code.

**The PARITY requirement set is written** — `docs/v2/parity/`, four layers down
to file-and-symbol design rows. It **amends** the v2 set; there is no sim v3
here or proposed.

**History lives in `git log` and in `docs/v2/SIM_Test_Execution_*.md`** — one
dated record per campaign since 2026-08-27. This file used to restate them; that
was execution narration (`R-REQ-14`) and it was cut on 2026-09-05.

## The next action — exactly one

> **Write `WP-01` of the PARITY set: the ingest map keyed by port, with an
> ordered address list.** Eight design rows, each naming a file and a symbol,
> blocked by nothing.
>
> **Read `docs/v2/parity/README.md` first**, then run its checker. That answers
> *"where do I start"* — not a list written down here.
>
> **The next thing is code, not documents.**

**When PARITY is not the work:** the v2 board has six amber items
(`CONSOLIDATED_REQUIREMENTS.md`) and five work packages at zero boxes. Nothing
gates anything else — that is what *"the demo works"* means. `--status` names
the lowest-numbered untouched package if a default is wanted; that is a number,
not a recommendation.

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
| **F** | Hosted CI is out of scope. `scripts/ci_gate.py` (run by hand, both platforms) is the real gate; `.github/workflows/sim-ci.yml` stays as an explicitly unobserved, unmaintained artifact. `WP-01`'s two items that were waiting on this (the stale `R-REQ-9` test-id citations, the Conan-editable-install system test) are **not-doing**, not pending — recorded, not silently dropped | 2026-08-31 |
| **G** | **No driver view.** The chase camera (`#20`, `WP-22`) is sufficient; a driver-view camera feed is not wanted. Board `#20` closes green with nothing left open in it — stated explicitly so it cannot quietly reopen as a "gap" | 2026-08-31 |

## Open — PARITY's three, none blocking

Raised by writing the set, and none of them stops the first seven work
packages. Each is a decision no tool can make.

| # | Question | Blocks |
|---|---|---|
| 1 | **The absent-port convention.** `SYS-0084` says an unused stage's ports *shall simply be absent*. The bench study's `C-04` wants them *bound to a typed, inert sink* so an upstream producer keeps writing somewhere legal. Both keep the graph whole; only one can be the convention. | Nothing — `WP-02` proceeds either way |
| 2 | **Does the resolved run spec carry which candidate address matched**, or does the run manifest alone carry it? | Nothing — the manifest already does |
| 3 | **Who writes `IF-06`** (`Source`/`Feed`) in `modules/viz`, and when? It is unwritten, and every transport control is a call on it. | `WP-08` and `WP-09` only |

## Parked — and what unparks each

| Parked | Why | Unpark when |
|---|---|---|
| ERG · `WP-17` · `WP-18` | No ERG measurement exists or can be obtained | Real data arrives in a format sim cannot read |
| `WP-19` `WP-30` `WP-31` | No demo dependency | **Condition met 2026-08-28 — the demo runs.** Unparking them is now a scope decision, not a wait |
| The scenario finding — **now only its corpus half** (4 of 18 runnable, and those four under-asserted). Every *"never became"* and every vacuous pass is fixed | Author's call, 2026-08-27 | Before `B3` deletes `tools/carla/`, or when coverage rather than the warning path matters |

**Removed 2026-08-31, not unparked:** the 155 `R-REQ-9` citations and the Conan
editable-install system test are **not-doing** (Decision F) — they no longer
wait on `WP-31` or anything else. See the log entry below and
`docs/v2/SIM_Test_Execution_2026-08-31_ci_descope.md`.

## Open risks

1. **A recording carrying no provenance grade still computes nothing** (`F-6`,
   2026-08-28 record). Validity is inferred from evidence grade, so a foreign or
   supplier file has every input flagged invalid — `F-1`'s symptom by a second
   route. Not on the demo path; does not report itself.
2. **The scenario corpus is thin and under-asserted.** Only 4 of 18 scenarios
   can run. All four now assert real computed behaviour (`bsd_curve_r172_passby`
   stopped being a false green 2026-08-28) — but its BSD warning fires at
   t≈7.4–9.6 s with no expectation covering it. Green is not coverage.
3. **A real capability loss, not silently dropped** (`SM-12`, 2026-08-29):
   `vantage_app.exe` has no bare-replay mode (no `--pipeline`) and no
   `--preset`/`--at`/`--workspace`/`--version` — the Python viewer that used
   to serve them is deleted, and there is no native equivalent yet.
4. **The Python and C++ `Session` twins can drift, and already have once**
   (2026-08-31 disposition, `docs/v2/SIM_Test_Execution_2026-08-31_session_
   duplication_disposition.md`). No test asserts the two agree on anything
   across the language boundary — each side's unit tests cover only its own
   implementation. Unparks with a cross-language parity/invariant check,
   not a deletion (the two are not redundant, see the disposition record).

5. **`bsd.warning` renders nothing against a legacy-vocabulary recording**
   (2026-08-30). `objects`/`hud` were fixed by applying the ingest map in the
   player; `bsd.warning` was not fixable there, because
   `bsd_curve_r172_passby.mcap` carries no `bsd.compState`/`bsd.outputs` topic
   at all. Genuinely absent data, confirmed against the file — named, not
   fixed, and not a defect in the layer.

6. **An editable dependency's build artifact can sit stale across a
   behaviour-changing commit** and nothing in the ordinary build/test loop
   notices. It shipped two real regressions unnoticed in one week, both found
   by accident. `scripts/check_build_freshness.py` at the superproject root
   answers it, run by hand; it is deliberately not wired into any automated
   gate (hosted CI is out of scope, Decision F) or into any component's
   byte-identical `build.py` (`R-BUILD-6`).

## Ending a session

Leave this file true. That means: a **decision** you took, an **open risk** you
found, a **trigger** for something you parked. Nothing else — what you built is
in `--status`, and what you did is in the commit message.

## Log — newest first, one line each, keep five

- **2026-09-05** — PARITY requirement set written (`docs/v2/parity/`); three rules came out of it and now bind every module (`R-REQ-13`, `R-REQ-14`, `R-REQ-6a`'s plan checks).
- **2026-09-05** — `START_HERE.md` cut from 635 lines to this; the 390-line narrative was already held in dated Test Execution records.
- **2026-09-01** — Step 7 closed. `docs/v1/` retired (17,681 → 2,078 lines), implementation plan's essay rows compressed to commit pointers.
- **2026-08-31** — Hosted CI descoped (Decision F); board `#20` closed green (Decision G); config-bundle hash proven on the real path.
- **2026-08-28** — The demo runs, all five clauses, watched. `WP-35` closed and the freeze ended by its own terms.
