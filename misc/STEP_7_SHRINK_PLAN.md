# Step 7 — Document Set Shrink Plan · **RETIRED**

**Executed and closed 2026-09-01. Retired to this stub 2026-09-05**, using the
same pattern it itself applied to `docs/v1/`: a plan that has been carried out
is history, and history belongs in `git log`, not in a folder someone reads to
find out what to do next.

`START_HERE.md` records the closure in its own words — *"This closes Step 7 in
full — nothing from `STEP_7_SHRINK_PLAN.md` remains undecided."*

---

## What it did

It named the last untreated root cause in `memory.md` §4 and §7: a
specification set that had outgrown the product it described. Then it cut it,
in two phases:

- **`docs/v1/` — 10 files retired**, 9 to stubs naming their successor and
  `sim_requirements.md` superseded by a compact per-ID disposition register
  (`R-REQ-2`), because 49 of its IDs were live in v2 `Trace` fields and
  dropping it would have dangled every one. **17,681 → 2,078 lines.**
- **`SIM_Implementation_Plan_v0.1.md`** — 85 essay-length checkbox rows
  compressed to closing-commit pointers. **70,504 → 33,343 characters.**

Two documents were extracted rather than deleted, because live `df`/`viz`
requirement documents and one C++ header cited them:
`docs/v1/FROZEN_DESIGN_ORIGINS.md` holds those fragments unabridged.

## Where the detail is

| What | Where |
|---|---|
| The execution, decision by decision | `docs/v2/SIM_Test_Execution_2026-09-01_step7_execution.md` |
| What each retired file held, and what replaced it | that file's own stub in `docs/v1/` |
| The fragments that had live external readers | `docs/v1/FROZEN_DESIGN_ORIGINS.md` |
| The closure, in one paragraph | `START_HERE.md` |
| The plan's full text | `git log -- misc/STEP_7_SHRINK_PLAN.md` |

## One thing worth carrying forward

The plan's own arithmetic did not add up, and that was recorded rather than
quietly dropped: it targeted ~4,000–4,500 lines, which its §2 could never have
reached because `docs/v2/` was never going to shrink in line count. The set
went from ~35,894 to ~22,195 lines — a real 38% cut, and not the headline.

**A target that cannot be reached by the work it describes is a defect in the
plan, not a shortfall in the execution.** That is the lesson the file leaves
behind, and it is the reason this stub exists rather than a deletion.
