# Portability — Windows today, Ubuntu tomorrow, no rewrite (v1, superseded)

**Retired 2026-08-31 (Step 7 document-set shrink), folded into the same stub
pattern as the rest of `docs/v1/` for consistency.** Full text:
`git show 1e2bb5b:docs/v1/sim_portability.md` (290 lines). Already correctly
dispositioned before this pass — `.claude/rules/sim.md` already marks this
document "superseded, evidence only" and already names its replacement:
**`SYS-0247`..`SYS-0251`** (`docs/v2/SIM_System_Requirements_v0.1.md` §20,
`P-1`..`P-10`, decomposed to `SW-0363`, verified by `SYT-NFR-15`..`SYT-NFR-19`).

This document held the ten portability rules (`P-1`..`P-10`: paths as
`Path`, no hard-coded absolute paths, case-sensitive-filesystem assumptions,
UTF-8/`\n` text, the one library-loading resolver, no shell/`.bat`, Qt
platform differences enumerated, explicit time/sort/randomness, a
platform-neutral config bundle, dependencies checked on both platforms), a
per-stage checklist, an Ubuntu bring-up estimate, and a 2026-08-06
reconciliation against real WSL-vs-Windows-shell measurement (`NR-SIM-47`).
The rules themselves are unchanged — they now live at `SYS-0247`..`SYS-0251`.

No live external reader and no `R-REQ-2` trace exposure (checked,
`misc/STEP_7_SHRINK_PLAN.md` §3).
