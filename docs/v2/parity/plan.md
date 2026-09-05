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

### Stage 6 — Implementation design, then the plan ◀ **current — start here next**

**Two documents, and the split is the point.** The work packages stay short —
a checkbox, what it lands, and the ordering. The detail goes in an
implementation **design**, one row per software requirement, naming *which
file, which symbol, in what order*. That is the shape
`SIM_Implementation_Design_v0.1.md` already uses across 379 rows, and it is
the right one: **a path in a design row is a promise that the code goes at that
path under that name.**

Each row carries: the `SW` it serves · the software item · the work package
that lands it · a **change class** · the concrete artifact and the one design
statement that makes the `SW`'s `Accept` reachable · the tests it is checked
by. The change class is derived from what exists today, never asserted —
`KEEP` · `MOVE` · `DEDUPE` · `EXTEND` · `NEW` · `DROP`.

**What a design row is not.** It is not its `SW` reworded with a filename
attached. The value it adds is exactly one of: *where the code goes*, *what the
symbol is called*, *what its signature is*, or *what has to be deleted first*.

**Two mechanical questions this stage has to answer first**, both real:

- **A design of 54 rows is a table, not 54 six-line blocks** — 379 rows in the
  v2 set proves the point. The checker parses the block anatomy, and counts a
  table row as commentary, so a table-shaped layer needs a declared row style
  before it can be checked at all. That is the first task of the stage, not an
  afterthought.
- **`C-UNLANDED` is firing 54 times right now**, because the existing plan
  lands `SYS` rows and the lowest layer is `SW`. Re-pointing it is not
  bookkeeping — it is the checker naming every requirement nothing will build.

**One hard ordering constraint.** The feed interface (`C-16`) is unwritten and
every transport control is a call on it. It is first, and it belongs to `viz`.
It blocks two packages; the rest are independent of it.

**Closed by.** Every `SW` row served by at least one design row and landed by
exactly one package; `--status` derives.

**Length is expected here, and is not the thing to control.** `R-REQ-14` was
amended on 2026-09-05 to say so: an implementation document is expected to be
long and dense, and what is capped in it is **execution narration** — what was
run, what was found, how long it took — which belongs in a Test Execution
Record or a commit message. The test is tense: a design row says what *will* be
true of the code; narration says what *happened*. A row in the past tense is in
the wrong document. The v2 plan reached 85 essay-length checkbox rows and had
to be compressed by 53%; that is the failure this clause exists to prevent, and
it is not the same failure as being detailed.

### Stage 7 — Handoff

For each `AMEND` row, the exact v2 requirement that gains a clause; for each
`ALLOCATE` row, the `viz` id it becomes.

**Bigger than it was.** It must now also dispose of the v2 `SW` rows this work
invalidates — `SW-0011` and `SW-0032` both specify "the resolved topic-to-port
table", which `SYS-0001` inverts, and there will be more.

**Closed by.** Every non-`KEEP` register row has a named destination, and no
obligation appears in two sets.

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

**Restarted at Stage 1 on 2026-09-05. Stages 1 to 5 are done.**

```
layer     reqs   budget   tests
-------------------------------
STK         16       16      16
SYS         39       40      39
SW          54       56      54
-------------------------------
total      109      112     109

Test cases: 164.
Commentary per requirement (R-REQ-14, cap 6):  STK 2.6   SYS 1.7   SW 1.2
Selftest -- all 18 planted violations caught.
```

**The requirement set is closed and traced both ways.** `C-UNDECOMP` is silent
at every layer; every requirement has a test and every test serves a
requirement.

**Exactly one finding remains, 54 times over:**

```
C-UNLANDED   SW-0001 .. SW-0054   no work package lands it -- nothing will build it
```

That is Stage 6, and it is the checker asking for precisely what the author
asked for: a plan detailed enough to build from. Nothing else is reported — not
size, commentary, categories, surfaces, items, layers or status marks.

| Document | Lines | Rows |
|---|---:|---:|
| `PARITY_Stakeholder_Requirements.md` | 170 | 16 |
| `PARITY_System_Requirements.md` | 293 | 39 |
| `PARITY_Software_Requirements.md` | 375 | 54 |
| `PARITY_Test_Spec.md` | 695 | 109 tests, 164 cases |
| **Specification total** | **1533** | **109 requirements — 14.1 lines each** |

**14.1 lines of specification per requirement**, against `ldw`'s 17. The set
grew four-fold from the two-layer version and got *denser* per row, which is
the shape `R-REQ-14` is aiming at: more rows, never fatter ones.

**Committed and pushed through Stage 2** — `sim ec9c1d8`, superproject
`1deb181` and `590fdcd`, `df db2543a`. Stages 3, 4 and 5 are not yet committed.

**Next: Stage 6**, where the file-level detail lands.

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
