# The POC demo, and what is in scope to reach it

**Written:** 2026-08-27 · **Status:** the finite list. Supersedes checkbox
percentage as the measure of progress.

**Read `memory.md` in this folder first** if you don't know why this document
exists.

---

## 1. The demo — this is what "done" means

> **Open the launcher. Pick a recording the system itself produced. Set df to
> MEASURED — the picture comes from the file. Set df to SIMULATED — the same
> picture is computed live by the real DLL. The two match. Click an object and
> see which signal, tick, file and build produced it.**

That paragraph is the definition of done for the POC. Nothing else is.

> **Revised 2026-08-27 (same day).** The first version read *"pick an ERG
> measurement, set perception-core to MEASURED and df to SIMULATED."* **No real
> ERG measurement containing perception outputs is available**, and vdy — the
> second module — is months away, so nothing can feed a `measured` upstream
> stage. The original demo was therefore unreachable, not merely unfinished.
>
> The replacement rests on a capability that is already **built**: every
> module's inputs *and* outputs are recorded (`R-SIM-6`, requirement 15). So the
> system can produce its own `measured` source, and the toggle is demonstrated
> against a real recording with the real DLL.
>
> **What this proves:** `R-SIM-10`'s invariant — *executed and injected produce
> the same port set; a consumer cannot tell which it got* — which is the
> strongest idea in the design.
>
> **What it does not prove, stated so nobody claims otherwise:** with one module
> you demonstrate the **mechanism**, not the **chain**. Real upstream-measured →
> downstream-simulated needs a second module with real code, and waits for vdy.

**It is explicitly a POC.** It does not have to be fast, packaged, installable,
multi-format, or pretty. It has to be **real** — a real measurement, the real df
DLL, real geometry from project calibration, and a provenance answer that is
true.

When this runs, the simulation platform is delivered as a POC and the next
scope conversation may begin. Not before.

---

## 2. Decisions taken 2026-08-27

| | Decision | Consequence |
|---|---|---|
| **A** | **C++ wherever there is scope.** | The Python run path is legacy. Every fork resolves toward `simcore`/`simengine`. |
| **B** | **The player lives permanently in viz, as C++.** | The Python player and Python scene are deleted, not maintained. |
| **C** | ~~ERG is the format.~~ **Revised same day: ERG is PARKED — no measurement exists.** | The POC runs on `mcap`, which the system already reads and writes. The `.erg` codec stays built (`WP-06b`, 8/8) and unused until data exists. |
| **D** | **vdy is the second module — but months away.** | The demo must NOT depend on a second module existing. See §3. |
| **E** | **The demo above is the definition of done — as a POC.** | Scope is judged by "does this serve the demo", nothing else. |

---

## 3. What the revised demo unlocks

**The system produces its own `measured` source.**
`measured` means *replayed from the file*, so it needs a recording containing a
module's **outputs**. Today's recordings are stimulus-only (`provenance: mocked`,
no computed outputs), which is why ERG was reached for. But recording every
port — inputs *and* outputs — is `R-SIM-6`, and it is **built**. Run df once
with `mode: simulate` and record; that file is then a legitimate `measured`
source for the same stage. No external data, no second module, no ERG.

**The critical path collapses to one nearly-finished package.**
`WP-28` — the launcher, and the measured/simulated toggle that is red item #8 —
has **one design item left**. `WP-17`/`WP-18` (22 untouched boxes, the io index
and codec read coverage) were only on the path because ERG needed them; with ERG
parked they are parked too.

**Decision A still stands and still matters**, just not urgently for the demo:
the Python and C++ stacks both being live is the standing cost (`B4`), and it is
what `WP-17`/`WP-18` will need whenever ERG data does arrive.

---

## 4. The finite list

43 sim packages · 442 boxes done · 53 started · **106 open**.
43 viz sync items · 186 done · 2 started · **8 open**.

Everything open is marked below. **SERVES** = needed for the demo.
**PARK** = real work, not now, not cancelled.

### 4.1 SERVES the demo

| Package | What it is | Open |
|---|---|---|
| **WP-01** | CI and the analysis-check harness | 5 started |
| **WP-02** | Python restructure, world-model removal, archive | 11 started, 1 open |
| **WP-03** | The C++ subtree and error taxonomy | 1 started |
| **WP-04** | `config` — the bundle, so geometry comes from calibration | 4 started |
| **WP-05** | **The seam** — Resolved Run Spec (the Python/C++ boundary) | 4 started |
| **WP-06** | `io` — codec contract, streaming, translate | 2 started |
| **WP-07** | `bus` — the signal header | 2 open |
| **WP-08** | `bus` — **cycle reconstruction** (the v1 defect that broke foreign data) | 4 open |
| **WP-09** | `scheduler` — multi-rate, held/stale inputs | 12 open |
| **WP-10** | `module_host` — loading and running the DLL | 3 started, 2 open |
| **WP-12** | `ingest` — the map from ERG topics to ports | 1 started |
| **WP-14** | `simengine` and the C ABI — the C++ run path | 2 started |
| **WP-16** | **DELETION** — retire `sil_host`, end seven duplications | 1 open |
| **WP-20** | `graph` — wiring and **transitive coherence** (the measured/simulated check) | 3 started, 4 open |
| **WP-22** | the run manifest — provenance behind the click-to-evidence answer | 6 started |
| **WP-27** | `transport` — engine ↔ player | 8 open |
| **WP-28** | **`launcher` — the measured/simulated toggle. This is red item #8.** | 2 started |
| **WP-29** | `pyapi` and `plugins` — so component layers load | 1 started |
| **SM-08** | viz: Qt out, headless in | 3 open |
| **SM-10** | viz: fix `CLAUDE.md`, which still says the module has no source | 1 started |
| **SM-12** | viz: **delete the Python scene** — Decision B | 4 open |
| **SM-05 / SM-07** | viz: supersession bookkeeping | 1 open, 1 started |

### 4.2 PARKED until the demo runs

| Package | What it is | Open | Why parked |
|---|---|---|---|
| **WP-11** | `mutate` — the override verbs | 2 started, 1 open | Nudging inputs is not needed to prove the chain. |
| **WP-17** | `io` — index, seek, selection, merge | **11 open** | **Parked with ERG, 2026-08-27.** Only on the path because ERG needed it. |
| **WP-18** | `io` — codec coverage and export | **11 open** | **Parked with ERG.** `mcap` read/write already works. |
| **WP-19** | `prep` | **18 open** | Preparation tooling. No demo dependency. |
| **WP-23** | `orchestrate` — the batch face | 5 started | POC is the developer face only. |
| **WP-18b** | export (CSV/video/plots) | *(half of WP-18)* | Writers matter, but reading ERG is what the demo needs. |
| **WP-30** | Images — bulk by reference, lazy decode | **8 open** | This is the door to red item #20. Opens *after* the POC. |
| **WP-31** | Package — delivery, self-test, budgets, docs | **23 open** | "Make it a product" comes after the product is proven once. |

**All five never-started packages are now parked** (`WP-17`, `WP-18`, `WP-19`,
`WP-30`, `WP-31` — 71 of the 106 open boxes). Every remaining demo item sits in a
package that is already part-built, and the largest single one is `WP-28` with
**one design item left**.

---

## 5. The critical path

```
record df once with `mode: simulate`, every port in AND out   (R-SIM-6, BUILT)
        │
        └─►  that file is now a legitimate `measured` source
                    │
                    ├─►  choose measured vs simulated   WP-28  ← red item #8, 1 item left
                    │    and refuse an incoherent mix   WP-20
                    │
                    ├─►  run df against it              WP-10, WP-09
                    │
                    ├─►  draw it and answer "why"       WP-27, WP-22, WP-29
                    │
                    └─►  DEMO   (the two runs match)
```

**Step zero is a check, not a build:** produce one recording containing df's
outputs and confirm `mode: measured` consumes it. If that works, the demo is
close. If it does not, that is the first real defect to fix — and it is found in
an hour rather than after 22 boxes of io work.

Deletions run **alongside**, not after: `WP-02`, `WP-16`, `SM-08`, `SM-12`.
Rule, permanently: **nothing is done until the thing it replaced is gone.**

---

## 6. First three actions

Movement A from the agreed plan. None of these add capability; all three make
the work visible.

1. **Fix the resume pointer.** It must lead with the headline number and stop
   naming `WP-01` as "next" because two of its boxes are half-ticked. It has
   said `WP-01` from 20% to 79%.
2. **Finish `WP-01` and turn CI on.** 19 done, 5 started. This closes the
   perpetually-"next" package *and* gives a machine that reports daily that the
   thing still works.
3. **Write the first sim Test Execution Record.** Run the 1,520 tests, date it,
   record it. Newest evidence today is 22 days old and covers under half.

**The test of Movement A:** within about a week, opening the project tells you in
one line that you are nearly done and everything passes.

---

## 7. The freeze

**From today until the demo runs: no new requirements, no new work packages, no
new design documents.** Corrections to existing text are allowed. New scope is
not — it goes on the parked list.

This document is the finite list. If it grows, the freeze has failed.

---

## 8. Where I may be wrong

Marked honestly, for correction rather than discovery later:

- **WP-09 (scheduler, 12 open)** — I marked it SERVES. If the demo's two stages
  run at one rate, most of it may be parkable. Worth checking before starting.
- **WP-27 (transport, 8 open)** — SERVES assumes the player attaches to a live
  engine. If the POC records first and views after, much of this parks.
- **WP-18** — I split it read/export by judgement. The split may not be clean in
  the actual boxes.
- ~~**The ERG measurement itself**~~ — **answered 2026-08-27: it does not exist
  and cannot be obtained. ERG is parked entirely**, and the demo was rewritten
  around a self-produced recording (§1). The `.erg` codec stays built and unused.
- **Step zero of §5 is unverified.** I have not confirmed that a recording
  containing df's outputs can be produced and then consumed by `mode: measured`.
  Requirement 15 is marked built, but *built* is not *demonstrated*. **This is
  now the first thing to check, and it replaces ERG as the top open risk.**
