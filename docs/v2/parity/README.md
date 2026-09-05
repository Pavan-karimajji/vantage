# PARITY — read this first

**What this is.** The requirement set for bringing `sim` and *Vantage* up to
the behaviour of a production-grade developer bench.

It **amends** the v2 set next door; it does not replace it, and there is no sim
v3 here or proposed. Where a row belongs to a requirement that already exists,
it says so and changes nothing here — the obligation lives in exactly one
place.

**Nothing in this file is derived.** No counts, no progress, no "what's next" —
the checker computes all of that, and a second copy goes stale. This file holds
only what no tool can know.

## Run it

```
cd modules/sim/docs/v2/parity

python py/trace_check.py            # every check; exit 1 on findings
python py/trace_check.py --status   # what is built, from the plan's checkboxes
python py/trace_check.py --stats    # counts, budget history, commentary
python py/trace_check.py --matrix   # the generated traceability matrix
python py/trace_check.py --next-uid # next free UID per layer
python py/trace_check.py --selftest # plant a violation per check, prove it is caught
```

Two more, and both should pass before any commit that touches `py/`:

```
python py/test_checker_additions.py           # what a plant cannot express
python py/test_checker_additions.py --plant   # prove those checks can fail
```

`--status` names the next work package. **That is the answer to "where do I
start" — not this file.**

## The documents

| File | What it holds |
|---|---|
| `PARITY_Stakeholder_Requirements.md` | What a developer using the bench gets |
| `PARITY_System_Requirements.md` | What the bench must do, observably |
| `PARITY_Software_Requirements.md` | What each software item must do inside |
| `PARITY_Implementation_Design.md` | The build order, then one row per software requirement naming **which file, which symbol** |
| `PARITY_Test_Spec.md` | Every test, all layers, one file |
| `layers.yaml` | **The one declaration.** Layers, budget, caps, surfaces, items — everything the checker reads |
| `selftest_mutations.yaml` | A planted violation per check |
| `PARITY_Change_Register.md` | **The thinking.** Every candidate change, in plain English, with where it went |

## Why the register exists

It is where the reasoning lives, so the requirement documents carry only the
result. Of 29 candidates only 14 became requirements here; the rest already had
an obligation somewhere and would have become a second copy free to drift
(`R-REQ-1`).

**Read it before proposing anything.** A row marked `NO CHANGE` was examined
and rejected with a reason, and `PARK` rows carry a trigger rather than a date.
Both exist so nobody re-derives them.

## The shape, and why

Four layers, and each was added because the set below could not be built from.
Both additions are dated in `layers.yaml`'s `budget_history`, which prints on
every `--stats` run:

| Layer | Answers |
|---|---|
| `STK` | What a developer gets |
| `SYS` | What the bench does, observably |
| `SW` | What each item does inside |
| `IMP` | Which file, which symbol, in what order |

**Size is not what is capped.** `R-REQ-14`: commentary is, at 6 lines per
requirement. A document is as long as the problem needs — capping length
punishes thoroughness and makes a writer merge two obligations into one row,
which the finished document cannot show.

## Open questions

Three, none blocking the first seven work packages. They live in
`../../../misc/START_HERE.md`, with what each one blocks — because they are
decisions about this module, not about this folder.

## If you change the checker

`py/trace_check.py` is **byte-identical** to
`.claude/templates/requirements/trace_check.py` below its `COMPONENT:` header,
and to the copies in `modules/df/docs/ldw` and the template's own worked
example. Change it in the template, propagate to all three, and run each one's
checks and selftest before committing. A copy that drifts from its template is
the one thing this arrangement exists to prevent.
