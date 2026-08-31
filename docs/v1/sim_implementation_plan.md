# Simulation Platform — Implementation Plan (v1, superseded)

**Retired 2026-08-31 (Step 7 document-set shrink).** Full text:
`git show 1e2bb5b:docs/v1/sim_implementation_plan.md` (5,902 lines).

**Not the build order — never was, after the v1/v2 restructure.** This
document was the previous effort's stage-by-stage plan (`S-A1`…`S-E3`, five
phases: Foundations, the pure-replay viewer, the SIL contract, Reach,
Retirement), 632 of its 740 checkboxes ticked. It read as convincingly
resumable and was explicitly dispositioned "not the build order" three times
over before this retirement (root `CLAUDE.md`, `.claude/rules/sim.md`,
`misc/START_HERE.md`) — see `misc/memory.md` §1 for the incident that made
that disposition necessary. The current build order is
`docs/v2/SIM_Implementation_Plan_v0.1.md` (`WP-nn` packages), tracked live by
`docs/v2/py/trace_check.py --status`.

No live external reader and no `R-REQ-2` trace exposure — no `S-A1`…`S-E3`
stage id appears in any v2 `Trace` field (checked,
`misc/STEP_7_SHRINK_PLAN.md` §3). The ten ideas this plan's era produced that
are still load-bearing are anchored in a root rule and a v2 requirement,
independent of this file — see `STEP_7_SHRINK_PLAN.md` §1.
