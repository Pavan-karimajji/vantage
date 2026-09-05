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

### Stage 3 — System requirements ◀ **current — start here next**

`SYS`: grow from 27 toward the expectation of 40, then re-point every row's
trace so the layer below can attach.

**Where the growth is, identified on the restart.** Several rows are carrying a
list where they should be carrying an obligation — nine transport actions in
`SYS-0015`, five step granularities in `SYS-0017`, the whole named-source
mechanism in `SYS-0003`. Splitting those is the same correction `STK` has now
had twice.

**Closed by.** Every `STK` row decomposed; every row naming a declared surface;
no dangling trace.

### Stage 4 — Software requirements

`PARITY_Software_Requirements.md`: up to 56 rows, each naming one of the 17
declared software items and tracing to a `SYS` row.

**This is the layer the set was missing**, and the one that decides whether a
developer can build from it. For `WP-01` alone it must answer: the schema
shape, what happens when zero candidates match, a matched topic whose type
disagrees with the port, how `absent:` interacts with a candidate list, and
where the match is reported. Each of those is otherwise a decision somebody
makes silently at the keyboard.

**Closed by.** Every `SYS` row decomposed (`C-UNDECOMP` silent); every row
naming a declared item.

### Stage 5 — Test specification and the self-test

One test per requirement, a named fixture catalogue, cases stating **both**
sides. Then `selftest_mutations.yaml`: one planted violation per check.

**Closed by.** `trace_check.py` exits clean — no orphans, no widows, no one-way
links — and `--selftest` catches every plant.

### Stage 6 — Implementation plan

**Rewritten on the restart, not extended.** Work packages land the *lowest*
declared layer, so they now land `SW` rows rather than `SYS` rows — the
checker's `C-UNLANDED` moved with the layer, which is how the change announced
itself.

**One hard ordering constraint.** The feed interface (`C-16`) is unwritten and
every transport control is a call on it. It is first, and it belongs to `viz`.
It blocks two packages; the rest are independent of it.

**Closed by.** Every `SW` row landed by exactly one package; `--status`
derives.

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

**Restarted at Stage 1 on 2026-09-05.** Stages 1 and 2 are done in their
three-layer form.

```
layer     reqs   budget   tests
-------------------------------
STK         16       16      14
SYS         27       40      27
SW           0       56       0
-------------------------------
total       43      112      41

Budget basis (R-REQ-13): 14 change_items x 8 = 112.
```

`python py/trace_check.py` reports findings that are **the re-point pass
itself**, enumerated by name exactly as `R-REQ-12` says it should be:

| Findings | What they mean |
|---:|---|
| 29 × `C-UNDECOMP` | Every `SYS` row now needs an `SW` child — Stage 4 |
| 1 × `C-LAYER-EMPTY` + 1 × `C-DOC-MISSING` | The `SW` document itself |
| 2 × `C-DANGLING` | `STT-15` and `STT-16`, the two new stakeholder tests |

Nothing is reported about size, commentary, categories, surfaces or status
marks.

**Two consequences of declaring `SW` that are worth seeing before Stage 6.**
`C-UNLANDED` went quiet — not because the plan is complete, but because work
packages land the *lowest* declared layer, which is now `SW`. The existing plan
lands `SYS` rows and must be rewritten. And the v2 handoff grew: rows that
describe the design this work replaces are not merely absent coverage, they are
coverage that will become wrong.

**Two rules and one mechanism came out of this set and now govern every
module.** `R-REQ-13`/`R-REQ-14` were rewritten and pushed (`78d9702`);
`R-REQ-6a`'s plan checks were mechanised the same day. This set runs no local
variant — its `py/trace_check.py` is byte-identical to the template below its
header, and `ldw` and the template's own example run the same file green.

**Next: Stage 3.**

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
