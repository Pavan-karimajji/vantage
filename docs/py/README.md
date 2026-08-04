# `docs/py` — frozen design evidence and cross-validation checks

Everything in this folder existed **before implementation started**. It is the
written-down version of the analysis that produced
[`../sim_architecture.md`](../sim_architecture.md) and the requirements register,
so that a claim in a design document can be re-checked rather than believed.

## The rule this folder exists for

> A design statement that came from inspecting something must be re-runnable.
> If a script produced it, the script is frozen here, named for the requirement
> it serves, and its output is committed under `logs/`.

Otherwise the design says *"the reference tool works like X"* and nobody can
tell, a year later, whether that was measured or remembered.

## Layout

| Path | Holds | Lifetime |
|---|---|---|
| `<REQ_ID>_<what>.py` | a survey/probe that produced evidence for one requirement | frozen — edit only to fix a bug, and re-log |
| `check_*.py` | invariant checks over the design documents themselves | run before every docs commit |
| `logs/<script>.<date>.log` | committed output, the proof | append-only; never edited by hand |

Post-implementation test output does **not** belong here — it goes to
`modules/sim/tests/` and its own reports. This folder is for evidence that
predates code.

## Naming

A survey script is named for the requirement it serves, using the register's ID
with underscores: `FR_SIM_46_reference_tool_survey.py` answers `FR-SIM-46`. A
check script is named for what it checks, because it serves all of them.

## Running

```bash
python docs/py/run_all.py            # every check + every available survey
python docs/py/check_traceability.py # one check
```

Surveys that need an external artefact (a reference tool installation) **skip
with a named reason** when it is absent, and never fail the run — the same
discipline `modules/sim/tests/integration/` uses. Every script is
platform-neutral and runs identically on Windows and Ubuntu
([`../sim_portability.md`](../sim_portability.md)).

## Index

| Script | Serves | What it establishes |
|---|---|---|
| `FR_SIM_46_reference_tool_survey.py` | `FR-SIM-46` | The reference console's concept inventory, and that each concept maps onto a stage / codec / renderer here — the evidence behind architecture §5.16's mapping table |
| `FR_SIM_45_argument_binding_survey.py` | `FR-SIM-45`, `FR-SIM-46` | How much hand-written configuration one `exec()` call costs when a tool must bind to an opaque DLL — the measured basis for the closed override verb list and for `sim probe` |
| `check_traceability.py` | all | Every `UT-`/`ST-`/`GT-` cited in the register exists in the plan; every requirement names a verifier; every stage's tests are reachable |
| `check_rules_coverage.py` | all | Every `R-SIM-n` is cited by at least one requirement and one stage; no requirement is orphaned from the rules |
| `check_requirement_coverage.py` | all | How much of each requirement is actually **proven** today, derived from the plan's own ticks — `check_traceability.py` proves a verifier *exists*, this one reports whether it has been *done*. Fails only on a verifier that resolves to no unit of work, or a non-parked row with no `Verified by`; low coverage is a status report, not a failure |
| `check_doc_invariants.py` | `R-SIM-1`, `NR-SIM-33` | No function name leaks into framework-owned prose paths; no absolute machine path; no company name; every internal doc link resolves |
| `run_all.py` | — | Runs all of the above, writes one log, returns non-zero on any check failure |
