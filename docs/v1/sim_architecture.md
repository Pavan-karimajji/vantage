# Simulation & Visualization Platform — Architecture Concept (v1, superseded)

**Retired 2026-08-31 (Step 7 document-set shrink).** Full text:
`git show 1e2bb5b:docs/v1/sim_architecture.md` (2,841 lines, the largest
single file in the v1 set by byte size).

This was the master design document: vocabulary, the scalability defects it
was written to close, design principles, the architecture itself (pipelines
as data, the plugin bundle, the mode/impl staging model, the placement map
for where a plug-in is authored §5.8), how each defect closes, the staged
roadmap, and the decisions taken along the way. **Every decision in it that
still governs the product is codified in `.claude/rules/sim.md`
(`R-SIM-1`..`R-SIM-25`) and in a `docs/v2/` requirement** — see
`misc/STEP_7_SHRINK_PLAN.md` §1 for the ten-idea cross-reference. Retiring
this file removes the day-by-day design argument (why X over Y, the
abandoned alternatives) but not the decisions themselves, which live on in
the rule and the requirement.

`R-SIM-1`'s own index used to carry a "Full map: §5.8" pointer into this
file for its placement rule. §5.8 was a longer, dated restatement of the
same rule `R-SIM-1`'s own body already states verbatim ("Placement, in
order: cross-cutting knowledge…") — the rule does not need this file to stay
self-contained, but the pointer itself was not edited in this pass (see the
end-of-pass rule-edit list this retirement produced, held for separate
approval rather than touched here).

No live external reader and no `R-REQ-2` trace exposure (checked,
`misc/STEP_7_SHRINK_PLAN.md` §3).
