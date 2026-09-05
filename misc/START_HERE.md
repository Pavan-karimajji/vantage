# START HERE

**Updated:** 2026-09-01 (Step 7 fully closed; next action reframed) · **Read this first, then run the status command below.**

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

**Movements A, B and C are complete and the demo works** — `DEMO_AND_SCOPE.md`
§1 runs end to end, all five clauses, watched and screenshotted (`WP-35`).
That is the baseline everything else is measured against: a working system with
named gaps in breadth, not a task list with a broken core.

**One item of Movement B remains** — `io`'s Python/C++ parity gap, not yet
actionable. Every other row in `MOVEMENT_B_PLAN.md` rests on verified code.

**The PARITY requirement set is written** (`docs/v2/parity/`) and the next thing
is code. See the next section.

**Where the history is.** Every campaign since 2026-08-27 has a dated record in
`docs/v2/SIM_Test_Execution_*.md`, and every change has a commit message that
explains itself. This section used to carry ~390 lines restating them; that was
execution narration, which belongs in `git log` (`R-REQ-14`), and it was cut on
2026-09-05. Nothing was lost — the records it cited are unchanged, and the two
items that were live only here moved to **Open risks** below.

## The next action — exactly one

> **Write `WP-01` of the PARITY set: the ingest map keyed by port, with an
> ordered address list.** Eight design rows, each naming a file and a symbol,
> blocked by nothing. **`docs/v2/parity/README.md` first**, then run its
> checker — that is what answers "where do I start", not a written-down list.
>
> That set is the requirement work for bringing this module and *Vantage* up to
> the behaviour of a production-grade developer bench. It **amends** the v2 set;
> it does not replace it, and there is no sim v3 here or proposed. Its reasoning
> lives in its change register, its build order and file-level design in one
> document beside it.
>
> **The next thing is code, not documents.**

---

## After `WP-01` — the standing list

Not a queue and not a priority order. Nothing here gates anything else, which
is what *"the demo works"* means. Pick one.

- **Six board items are amber, not red** (`CONSOLIDATED_REQUIREMENTS.md` —
  `#2`/`#3` the three-pillar and two-face architecture, `#12`/`#13` crash
  isolation and determinism, `#17` export one-way-ness, `#24` geometry from
  calibration). Each does its job for the case the demo exercises; each is
  amber because it does not yet do it for every case the concept promises.
- **Five work packages are at zero boxes** (`memory.md` §2 — `WP-17`, `WP-18`,
  `WP-19`, `WP-30`, `WP-31`: the io codecs and export, images, packaging).
  Named honestly as not started, never guessed at as partial.

`docs/v2/py/trace_check.py --status` names the lowest-numbered untouched
package if a default is wanted. That is a number, not a recommendation.

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

- **2026-09-05** — PARITY requirement set written, `docs/v2/parity/`. Four
  layers down to file-and-symbol design rows, landed by work packages whose
  contents are derived rather than listed. Restarted once at stage 1 on the
  author's finding that a two-layer set cannot be built from — correct, and the
  reason is dated in its `layers.yaml`. Three rules came out of it and now bind
  every module: `R-REQ-13`/`R-REQ-14` (cap the commentary, never the count or
  the length) and `R-REQ-6a`'s plan checks, mechanised in the shared checker.
  Two corrections to its own record are on the record rather than quietly
  fixed: `SYS-0004` retired the day it was written as a duplicate of
  `SYS-0022`, and the claim that `SW-0011`/`SW-0032` would become "actively
  wrong" was too strong — both survive.

- **2026-09-01** — Step 7 fully closed. `docs/v1/` all 10 files retired
  (9 to stubs + `sim_requirements.md`'s compact register, 17,681→2,078
  lines), including `sim_api_reference.md` — held back pending a
  conditional check, found to describe `scene`/`render`/`app` packages
  `7d4c626` deleted, three options presented, author accepted retiring it
  like its siblings, its stub naming both what was wrong and what merely
  moved. 85 essay checkbox rows compressed to closing-commit pointers.
  `.claude/rules/sim.md`'s two mechanical repoints applied and its stale
  "signature is a contract" clause removed outright. `misc/memory.md` §10
  closed against `sim_api_reference.md` too — only `§2`'s zero-progress
  packages and six amber board items remain open, reframed as remaining
  capability against a working demo, not unfinished work. **The next
  action** rewritten to match. Pushed across `sim`/`df`/`viz`/superproject,
  R-GIT-1 order. `trace_check.py`/`check_invariants.py` clean throughout.
  Record: `docs/v2/SIM_Test_Execution_2026-09-01_step7_execution.md`.
- **2026-08-31** — Everything pushed (sim, df, superproject). Two freshness-
  check findings resolved (`mathlib` rebuilt on real `vs2026`; `interfaces`'
  flagged artifact was a dead pre-`WP-33` leftover, deleted). `df`'s
  `.IPGControl.conf` gitignored. Step 7 document-set shrink plan written
  (not executed): `misc/STEP_7_SHRINK_PLAN.md`, target ~35,894 → ~4,000–4,500
  tracked lines, read-before-cut per file, `R-REQ-2` respected for
  `sim_requirements.md`'s 49 live trace citations.
- **2026-08-31** — Build-artifact freshness check built
  (`scripts/check_build_freshness.py`, superproject root, cross-submodule):
  for every Conan-editable package, its own `build*/` binaries vs. the
  newest file in what actually feeds its build (`src`/`include`/`conf`/
  recipe files). Run by hand, not wired into any gate. **A real bug found
  and fixed before shipping:** the first version scanned each package's
  whole tree as "source," producing 26 mostly-false findings (one build
  tree's own bookkeeping read as source, `CompilerIdC.exe` treated as a
  deliverable, a dev launcher `.bat` counted as C++ source) — narrowed;
  re-run, 2 real findings (`interfaces`/`mathlib`, both behind their own
  `conanfile.py`), neither rebuilt. 10/10 new unit tests. **Uncommitted —
  reported, awaiting go-ahead.** Record:
  `docs/v2/SIM_Test_Execution_2026-08-31_build_freshness_check.md`.
- **2026-08-31** — Cross-repo `Session` duplication disposition closed:
  re-measured from the build graph and git log (not carried over), both
  Python `adas_sim/session/` and C++ `viz::session::Session` are genuinely
  live for different consumers (every headless CLI verb; the real shipped
  `viz_player.exe`). Reframed as a cross-language twin (`io/mcap.py`↔
  `mcap.cpp`'s pattern), not copy-never-move debt — no deletion. Drift risk
  (already manifested once) named as a new open risk. No code touched.
  **Committed, not pushed** (`sim` `0a5732a`, superproject `6e6e7a2`).
  Record:
  `docs/v2/SIM_Test_Execution_2026-08-31_session_duplication_disposition.md`.
- **2026-08-31** — `mcap.cpp`'s own named `capture_time_ns` gap closed: a
  narrow scalar read of `manifest_version:` (not a full `RunManifest` port)
  gates `Pull()`'s `capture_time_ns`, mirroring `io/mcap.py`'s
  `CAPTURE_TIME_MANIFEST_VERSION` check — `nullopt` for no manifest or a
  pre-two-clock one, never defaulted. Dormant `MetaKind::kRunManifest`
  string-mismatch bug (`"run_manifest"` vs. Python's real `"manifest"`)
  found and fixed alongside it. Three new regression cases,
  `simcore_tests` 215/218 (1 pre-existing, unrelated Windows temp-dir
  flake). **Committed, not pushed** (`sim` `c5a095e`, superproject
  `f848ea5`). Record:
  `docs/v2/SIM_Test_Execution_2026-08-31_io_capture_time_gap.md`.
- **2026-08-31** — `A-15`'s config-bundle-hash fix proven on the real path:
  real `vs2026` `df_sil` build (Conan blocked by the known credential gap,
  worked around with a direct `cmake --build` against the already-resolved
  graph), demo's own `sim resim --save`, real `config_bundle_sha256`
  (`966f0e30...`) read back from both the recording's manifest and `sim
  explain`'s evidence chain. Board `#16` re-marked 🟢. Separate gap named,
  not fixed: the bundle's actual bytes still are not embedded in the
  recording. **Committed, not pushed** (`sim` `f81de52`, superproject
  `802801a`). Record:
  `docs/v2/SIM_Test_Execution_2026-08-31_a15_real_path_proof.md`.
- (older entries trimmed per this section's own "keep about five" rule —
  see git history on this file for anything earlier, including Board `#20`
  closing green 2026-08-31.)
