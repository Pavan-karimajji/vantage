# SIL Contract — the Python↔C boundary, generalized (v1, superseded)

**Retired 2026-08-31 (Step 7 document-set shrink).** Full text:
`git show 1e2bb5b:docs/v1/sim_sil_contract.md` (1,155 lines).

This document designed the generic C-API ABI shared across every component
(`adasInit`/`adasExec`/`adasShutdown`/`adasManifest`/`adasAbiVersion`) and the
per-component named-port-set model that replaces per-function positional
growth: the problem it solved, the design (named port sets, the
`conf/ports.yaml` declaration), the Python-side binding, migration, versioning,
testing, and a checklist of what a component owes the framework. **The
governing rule is `R-SIM-4`** (ports named and discovered, never positional)
and **`R-SIM-22`** (the per-component shim generated from declared data,
never hand-written); both are unchanged by this retirement.

No live external reader and no `R-REQ-2` trace exposure (checked,
`misc/STEP_7_SHRINK_PLAN.md` §3).
