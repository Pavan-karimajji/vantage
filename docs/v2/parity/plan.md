# PARITY — the plan

**What we are doing.** Bringing `sim` and *Vantage* up to the behaviour and
the feel of a production-grade developer bench, and writing the requirements
for that work **before** doing it.

**Read this file to know where we stopped.** Every stage below states what it
produces and the check that closes it. The stage marked *current* is where
work is.

---

## 1. The goal, in three sentences

The concept is right and most of it is built — a demo runs end to end. What is
missing is a set of specific, nameable behaviours that separate *"it works"*
from *"a developer would choose to use it every day"*: ordered fallbacks in
the ingest map, more than one recording per run, real transport controls, a
diagnostic log that does not drown itself, plug-ins that say what they are.

This pass writes those as requirements, at two layers, and then plans the
work. The size target is **about 17 lines of specification per requirement** —
the rate the `ldw` set achieves — not a fixed total. A harder problem earns
more rows; it never earns fatter ones.

---

## 2. The one thing this plan is designed to avoid

The previous requirement effort in this module reached roughly **13,000 lines
across nine documents**, and the obvious explanation is wrong. It was measured
on 2026-09-05, and the two big requirement documents are **not** bloated per
row:

| Document | Lines | Requirements | Lines per requirement | Prose |
|---|---:|---:|---:|---:|
| `SIM_System_Requirements_v0.1.md` | 2689 | 274 | 9.8 | 29% |
| `SIM_Software_Requirements_v0.1.md` | 3651 | 378 | 9.7 | 20% |
| `modules/df/docs/ldw` (the reference set) | 295 | 29 | 10.2 | 31% |

They are the same shape as the set held up as the model, and the median
`Shall`+`Accept` is 41 words against a 60-word cap. **Those two documents are
large because they carry 652 requirements**, which is a scope question, not a
writing one.

Where the prose genuinely does dominate is elsewhere, and it is worth naming so
this set does not repeat it: `SIM_Concept_Document_v0.3.1.md` is 1551 lines and
**79% prose**, and about 400 lines of the System document are crosswalk,
disposition and open-question tables rather than requirements.

So the rule for this pass is aimed at that, stated once and applied everywhere:

> **A requirement row states the obligation and the acceptance test. Nothing
> else.**

Justification lives in `PARITY_Change_Register.md`. History lives in git. If a
row cannot be said in 60 words, it is two rows.

Three mechanical guards back that up, all in `layers.yaml`:

| Guard | Value | Kind | Rule |
|---|---|---|---|
| Commentary per requirement | 6 non-requirement lines | **capped** | `R-REQ-14` |
| Words per row | 60 (`Shall` + `Accept`) | one-obligation detector | `R-REQ-14` |
| Headline length | 90 characters | one-obligation detector | `R-REQ-14` |
| Requirement count | *uncapped* — expectation reported only | — | `R-REQ-13` |
| Document length | *uncapped* | — | `R-REQ-14` |

---

## 2a. How a cap is handled *while* writing

A cap that binds while writing silently shapes the content, and the reader
never learns what was left out. That happened once in this set: `STK` was
written to a budget of 10, four rows quietly ended up carrying two obligations
each, and it surfaced only because it was reported afterwards. By then the
compression already looks like a finished document.

**This is no longer a local arrangement.** It was promoted the same day into
`.claude/rules/requirements.md` as `R-REQ-13` and `R-REQ-14`, so it governs
every module rather than this folder — the point of a principle is that the
next person does not have to rediscover it.

**What the rule says.** Cap the commentary; never the count, never the length.

- **Uncapped: how many requirements, and how long a document is.** A document
  is as long as the problem needs. Capping either punishes thoroughness and is
  what forces the invisible merge.
- **One-obligation detectors, never raised:** `Shall`+`Accept` ≤ 60 words,
  headline ≤ 90 characters. A row over them carries more than one obligation
  (`R-REQ-1`) and the fix is to split it, which makes the set better.
- **Capped: commentary** — every line that is not a requirement field, a
  headline, a heading or blank — at **6 per requirement**.
- **The budget is an expectation that gets reported, not a failure.** Over it
  is a scope signal for a person to judge, never something a checker resolves
  by making the writing smaller. Changing the basis costs a dated
  `budget_history:` entry, and that history prints on every run.

**Why 6, and why commentary at all.** Measured across every set in this repo on
2026-09-05: readable documents run **1.6 to 4.3** commentary lines per
requirement; the two that became unreadable run **81 and 990**. Length
separated neither — `sim` v2's System document is 2,689 lines and healthy by
this measure. Four would have failed the `ldw` reference set's own stakeholder
document, whose preamble earns its place; six passes everything healthy and
still catches the failures by more than an order of magnitude.

**Tested, in both directions, in two modules.** `py/trace_check.py --selftest`
plants a commentary violation and proves it is caught. `py/test_checker_
additions.py` covers what a plant cannot express — the *absence* of a finding:
that a 900-line document raises nothing, that over-budget is a note rather than
an error, and that the length cap is gone from the checker rather than merely
quiet. `--plant` then reverts each change and proves those checks go red. Both
run clean on this set and on `modules/df/docs/ldw`.

## 3. What gets created, and why each file exists

| File | What it is | Written in |
|---|---|---|
| `layers.yaml` | **The one declaration.** Layers, categories, budget, size caps, surfaces. Everything the checker does is driven from here. | Stage 1 |
| `PARITY_Change_Register.md` | The elicitation output — every candidate change in plain English, with a disposition. Not a requirement document. | Stage 1 |
| `py/trace_check.py` | The checker. A module-agnostic copy from `modules/df/docs/ldw`; it contains no reference to this module. | Stage 1 |
| `PARITY_Stakeholder_Requirements.md` | `STK` — what a developer using the bench must be able to do, and how well. | Stage 2 |
| `PARITY_System_Requirements.md` | `SYS` — what the bench must do at a surface someone can observe. | Stage 3 |
| `PARITY_Test_Spec.md` | Every test, all layers, one file. A test's layer is read from its id prefix. | Stage 4 |
| `selftest_mutations.yaml` | The planted violations, as data — one per check, proving the check catches it. | Stage 4 |
| `PARITY_Implementation_Plan.md` | The `WP-nn` work packages, in dependency order, with progress boxes. | Stage 5 |
| `PARITY_Handoff.md` | What is amended in the v2 set rather than written here, and what is allocated to `viz`. | Stage 6 |

**Two layers only, and that is a decision.** `STK` and `SYS`. No software
layer: every row here changes a system that already has software requirements
next door, and a third layer would generate trace links between two documents
written by the same person in the same hour. Adding it later is a one-line
change plus a re-point pass the checker enumerates by name (`R-REQ-12`).

---

## 4. The stages

Each stage is a single sitting. Nothing after Stage 1 starts before the stage
above it closes, because each one's check reads the one before.

> **Restarted 2026-09-05 at Stage 1**, after the author's finding that a
> two-layer set cannot be built from. The stages below are the three-layer
> sequence; what the two-layer run produced is not discarded — `STK` and `SYS`
> were re-entered and grown, not rewritten. `layers.yaml`'s third
> `budget_history` entry carries the evidence.

### Stage 1 — Foundation, register, and the layer declaration ✅ **done**

The folder, the checker, the change register, and `layers.yaml` — layers,
categories, budget, size caps, surfaces and **software items**.

**Why the register comes first.** It is where the de-duplication happens. Of 29
candidates, only 14 earn a new requirement here; the rest already have an
obligation somewhere and would have become a second copy free to drift
(`R-REQ-1`). Doing that sorting inside the requirement document is how a set
doubles in size without covering anything more.

**Re-entered on the restart** to declare the `SW` layer and its 17 software
items. An item has to be declared before any row can name one, which is why
this stage owns the list.

**Closed by.** `--stats` reports the declared budget; every register candidate
carries a disposition; the `KEEP` count equals `budget_basis.count`.

### Stage 2 — Stakeholder requirements ✅ **done**

`STK`: one row per developer-facing outcome — **16 rows**.

**Grown from 14 on the restart, by splitting rather than padding.** Two rows
held two outcomes each: *feed the bench from a renamed recording* also carried
*know which name fed each port*, and *move through a recording* also carried
*control how fast it plays*. Each half is separately falsifiable and separately
useful, which is the test. Nothing was added to reach the budget — that would
be the mirror image of the compression this set has already corrected twice.

**One category, `feature`.** `kpi` is deliberately not declared: the bench is a
developer tool, not a vehicle feature, so it carries no performance target a
stakeholder could hold us to (`R-REQ-16`, author's call).

**Closed by.** `STK` at 16 with every row carrying the declared category, and
no size-cap or `Status` finding.

### Stage 3 — System requirements ✅ **done**

`SYS`: **27 → 39 rows**, against an expectation of 40.

**Twelve rows added, and none of them padding.** Four came from splitting rows
that carried a mechanism rather than an obligation — `SYS-0003` held *declare
several sources*, *have a default* and *override per port* in one sentence, and
now holds the first two with `SYS-0029` and `SYS-0030` beside it. The rest are
obligations that were simply missing, and most were named while writing the
budget entry: what happens when **no** candidate address matches and how that
differs from a declared hole (`SYS-0034`); a step granularity the recording
cannot support (`SYS-0033`); a requested speed the machine cannot hold
(`SYS-0032`); a range's bounds stated in the recording's timebase rather than
wall clock (`SYS-0039`); who made a mark and when (`SYS-0040`).

**Two rows were re-pointed, not rewritten.** `SYS-0002` and `SYS-0016` always
belonged to outcomes that only got their own stakeholder rows at Stage 2, so
their `Trace` now reads `STK-0016` and `STK-0015`. That is the re-point pass
`R-REQ-12` describes, done by name rather than by guess.

**Closed by.** All 16 `STK` rows decomposed, confirmed in `--matrix`; every row
naming a declared surface; worst row 45 words of 60, worst headline 61 of 90.

### Stage 4 — Software requirements ✅ **done**

`PARITY_Software_Requirements.md`: **54 rows**, each naming one of the 17
declared software items and tracing to a `SYS` row.

**This was the layer the set was missing.** Every question named in the restart
now has a row: the schema shape (`SW-0001`), a malformed entry (`SW-0002`),
zero candidates matching (`SW-0007`), a matched topic whose type disagrees with
the port (`SW-0006`), how a declared hole parses beside provided ports
(`SW-0003`), and where the match is reported (`SW-0005`, `SW-0014`). Each was
previously a decision somebody would make silently at the keyboard.

**All 17 declared items are used and none is invented** — checked, not
assumed.

**Closed by.** `C-UNDECOMP` silent — all 39 `SYS` rows decomposed. Worst row 40
words of 60; worst headline 59 of 90.

### Stage 5 — Test specification and the self-test ✅ **done**

**109 tests, 164 cases**, one per requirement, across a 23-entry fixture
catalogue and one named checklist.

**One structural fix, found by writing it.** `SW-0052` was verified by `ANL-02`
— but `ANL` is declared under `SYS`, so an `ANL` test serving an `SW` row would
have tripped `C-TESTLAYER`. The obligation ("every live operation delegates to
a headless function") is reachable by reflection, so it became `UT-livectl-02`
rather than moving the prefix and breaking `ANL-01`'s layer. The alternative —
declaring `ANL` at two layers — is not expressible, and should not be: a test
prefix names exactly one layer.

**Closed by.** 109 requirements, 109 tests, no orphans, no widows, no one-way
links. `--selftest` catches all 18 plants. Commentary 2.6 / 1.7 / 1.2 per
requirement against a cap of 6.

### Stage 6 — Implementation design, then the plan ✅ **done**

**Two documents, and the split is the point.** `PARITY_Implementation_Design.md`
carries **54 rows, one per software requirement**, each naming a concrete file
and symbol — `ingest/resolve.py::resolve_port`, `runspec/sources.py::SourceSet`,
`viz/cpp/viz/player/transport.hpp::Transport`. Every directory named exists
today, so a `NEW` row names a file that does not exist yet inside a package
that does. **A path there is a promise: the code goes at that path under that
name.** The work packages stayed one line each — what they land, and what for.

**`Change` is a closed vocabulary, checked.** `KEEP` · `MOVE` · `DEDUPE` ·
`EXTEND` · `NEW` · `DROP`, derived from what exists today rather than asserted,
enforced by the new `C-CHANGE`. A row claiming `NEW` for code already present
is a design error a reviewer can see without opening the file.

**Three checker changes, each forced by a real defect rather than anticipated:**

- **`row_style: table`.** A design is one row per requirement — 379 of them in
  the v2 set — and in the block anatomy that is six lines each and unscannable.
  But the checker parsed only the block form, and `count_commentary` read a
  table row as prose, so a 54-row design would have failed `R-REQ-14` on the
  one document that rule explicitly exempts.
- **`C-ORPHAN` scoped to layers that declare tests.** `IMP` declares none: it
  is verified by the tests of the `SW` it serves, plus build gates. Demanding
  its own test ids would invent a second, weaker copy of them.
- **`C-TWOWAY` scoped the same way.** An `IMP` row repeats its parent's test
  ids so it reads standalone. That is a citation, not a claim to be served —
  requiring the test to name the design row back would invent a link
  `R-REQ-11` never asked for.

**Two plants went stale and one came back.** `C-DUPLAND` and `C-PLANUID` were
anchored on the old `SYS`-landing plan text and reported *anchor not found*
rather than passing quietly. `C-UNLANDED` returned exactly where this file said
it would — it reads the lowest declared layer, which has now been `SYS`, `SW`
and `IMP` in turn, and the selftest caught it going blind both times.

**Closed by.** `PASS — 163 requirements, 109 tests, no findings`; `--selftest`
**all 20 caught**; `--status` reports 13 packages landing 54 design rows.

### Stage 7 — Handoff ✅ **done**

`PARITY_Handoff.md`: where each of the fifteen non-`KEEP` register rows lands,
so a disposition is a decision with an address rather than a decision to do
nothing.

**Every target was read before being named, and two did not say what the
register assumed.** That is the useful part of the stage:

- **`C-17` was already satisfied.** `SIM:SYS-0192` already carries both axes in
  full — none / reset / reset-and-init, and before-batch / before-entry /
  before-section. The register said it "gains this vocabulary", written from the
  study's summary rather than from the row. Only the presentation is open, and
  that is a `viz` player item. Re-marked `NO CHANGE` at the system layer.
- **`C-04` conflicts with its target.** `SIM:SYS-0084` says an unused stage's
  ports **shall simply be absent**; `C-04` wants them **bound to a typed
  sink**. Both keep the graph whole and only one can be the convention, so it
  is written up as an open decision rather than resolved quietly — picking
  either silently would leave the other requirement standing and wrong.

**And one correction to this set's own record.** The restart's budget entry
claimed `SIM:SW-0011` and `SIM:SW-0032` would become *actively wrong*. Both
were read at this stage and **both survive**: they specify the *resolved*
topic-to-port table, and resolution picks one address per port before the spec
is written, so inverting the map's key does not invert the spec's table.
`SIM:SW-0029` was a false positive in the original grep. Corrected in
`layers.yaml` where the claim was made, not only where it was found. The
argument that mattered — that the new behaviour had **no** software coverage —
needed no help from the one that was too strong.

**Closed by.** Every non-`KEEP` register row has a named destination; three
open questions are stated with what they block, and none blocks the first seven
work packages.

## 5. What this pass does **not** do

- **No code.** Not one line until the set is closed and the plan is agreed.
- **No sim v3.** This is a delta on the v2 set, not a re-baseline. Two
  rewrites already happened in this module.
- **No re-opening settled scope.** The out-of-scope list in
  `misc/CONSOLIDATED_REQUIREMENTS.md` and the decisions in
  `misc/START_HERE.md` stand.
- **No status marks in a specification.** Whether something is done is derived
  by the checker and by the implementation plan, never typed into a
  requirement (`R-REQ-6`).

---

## 6. Where we stopped

**All seven stages are done, 2026-09-05.** The set was restarted once at Stage
1, on the author's finding that a two-layer set cannot be built from.

```
layer     reqs   budget   tests
-------------------------------
STK         16       16      16
SYS         39       40      39
SW          54       56      54
IMP         54       56       0
-------------------------------
total      163      168     109

PASS -- 163 requirements, 109 tests, no findings.
Selftest -- all 19 planted violations caught, no baseline codes.
Status  -- 13 packages, 0 done, 54 of 54 design rows landed, contents derived.

Commentary per requirement (cap 6):  STK 2.6  SYS 1.7  SW 1.2  IMP 1.4
```

**The chain is closed end to end and checked in both directions.** 16
stakeholder outcomes → 39 system rows → 54 software rows → 54 design rows, each
naming a file and a symbol, each landed by exactly one of 13 work packages,
every requirement served by a test and every test serving a requirement.

| Document | Lines | Rows |
|---|---:|---:|
| `PARITY_Stakeholder_Requirements.md` | 170 | 16 |
| `PARITY_System_Requirements.md` | 293 | 39 |
| `PARITY_Software_Requirements.md` | 375 | 54 |
| `PARITY_Implementation_Design.md` | 196 | 54 rows + 13 packages |
| `PARITY_Test_Spec.md` | 695 | 109 tests, 164 cases |
| **Specification total** | **1729** | **163 requirements — 10.6 lines each** |
| `PARITY_Change_Register.md` | 415 | 29 disposed candidates |
| `PARITY_Handoff.md` | 116 | 15 destinations, 3 open questions |
| `layers.yaml` · `selftest_mutations.yaml` | 226 · 273 | declaration · 19 plants |

**10.6 lines of specification per requirement**, against `ldw`'s 17. Four times
the size of the two-layer version and denser per row than when it started —
`R-REQ-14` working as intended: more rows, never fatter ones.

**Three open questions, none blocking** (`PARITY_Handoff.md` §5): the `C-04`
convention, whether the run spec carries the matched candidate, and who writes
`IF-06`. The first seven work packages proceed regardless.

**The next thing is code, not documents.** `--status` names `WP-01`: the ingest
map keyed by port, landing eight design rows, blocked by nothing.

## 7. Running the checker

```
cd modules/sim/docs/v2/parity
python py/trace_check.py            # every check; exit 1 on findings
python py/trace_check.py --stats    # counts, budget, and the budget history
python py/trace_check.py --next-uid # next free UID per layer, and headroom
python py/trace_check.py --matrix   # the generated traceability matrix
python py/trace_check.py --selftest # plant a violation per check (needs Stage 4's data)
```

This copy of the checker carries three additions the `ldw` original does not,
so they carry their own evidence rather than riding on a selftest that
predates them:

```
python py/test_checker_additions.py           # 20 checks, both directions
python py/test_checker_additions.py --plant   # remove each addition, prove the test goes red
```

`--plant` works on a throwaway copy; the real checker is never edited. Run
both before any commit that touches `py/`.

Nothing this prints is typed anywhere. It is recomputed on every run.
