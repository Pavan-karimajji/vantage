# Resim & Recording — determinism, provenance, and the Session (v1, superseded)

**Retired 2026-08-31 (Step 7 document-set shrink).** Full text:
`git show 1e2bb5b:docs/v1/sim_resim_and_recording.md` (1,008 lines).

This document designed the sim/resim/replay distinction, the run manifest's
provenance fields, the recording format, determinism guarantees (and the one
real hole in them), time handling across components, the `Session`, export,
migration of existing recordings, and the CLI shape around all of it. **The
governing rules are `R-SIM-5`** (sim/resim/replay are three different
things), **`R-SIM-6`** (every port recorded, every run carries a manifest),
**`R-SIM-14`** (a recording is a model, a format is a codec — two clocks),
and **`R-SIM-24`** (determinism measured along the axes that break it); all
unchanged by this retirement.

No live external reader and no `R-REQ-2` trace exposure (checked,
`misc/STEP_7_SHRINK_PLAN.md` §3).
