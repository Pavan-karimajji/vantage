# Scenarios & Expectations — schema, sensor model, and assertions as data (v1, superseded)

**Retired 2026-08-31 (Step 7 document-set shrink).** Full text:
`git show 1e2bb5b:docs/v1/sim_scenarios_and_expectations.md` (678 lines).

This document designed the scenario schema v2 (world-model-agnostic content,
world realization, sensor model, run control, SUT reference, expectations),
the sensor-model shape, the expectation predicate vocabulary, CI wiring, and
migration of the 18 legacy scenarios, plus two open points (anchors, and the
five-fault vocabulary derived rather than invented). **The governing rules
are `R-SIM-8`** (expectations are data, from one source) and **`R-SIM-9`**
(the bundle/`shared_config` hold real runtime configuration only; sensor
error models and fault injection live with the tooling); both unchanged by
this retirement. The scenario-corpus finding this document's era produced
(only 4 of 18 scenarios runnable) is tracked as an open risk in
`misc/START_HERE.md`, not lost here.

No live external reader and no `R-REQ-2` trace exposure (checked,
`misc/STEP_7_SHRINK_PLAN.md` §3).
