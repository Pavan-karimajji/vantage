# API reference — the symbols an implementation must produce (v1, superseded)

**Retired 2026-09-01 (Step 7 document-set shrink, closed out).** Full text:
`git show 79177fa:docs/v1/sim_api_reference.md` (991 lines).

**Retired on a finding, not an assumption.** This document was held back
from Step 7's first pass (2026-08-31) pending a conditional check — its own
"Reading rule" claimed *"a signature here is a contract."* Checked directly
against `modules/sim/src/adas_sim/` as it stood 2026-08-31: the check
failed for a real, substantial part of the document, so retirement is now
closed rather than assumed clean.

**What was wrong, specifically — the part actually deleted.** §1 (package
map), §1a's `scene`/`render`/`app`/`view` file tables, and §5
(`Prim`/`Layer`/`LayerProvider`, the Scene IR) describe Python packages
`7d4c626` ("delete the Python scene/render/player implementation",
2026-08-29, Decision B) removed wholesale — `scene/` and `render/` are now
empty directories, `app/` does not exist. The player is `viz`'s C++
implementation now (see `modules/viz/CLAUDE.md`); nothing in this document
describes it. The package map's other packages also drifted structurally:
`contracts/` became `graph/`, `core/` split into `session/`/`engine/`/
others; `config/`, `diagnostics/`, `ingest/`, `launcher/`, `orchestrate/`,
`plugins/`, `pyapi/`, `resolve/`, `runspec/` did not exist when this
document was written. `Pipeline` now lives in `graph/build.py`, not
`contracts/pipeline.py`; `Session` in `session/session.py`, not
`core/session.py`; `PortValue` in `session/tick.py`, not `core/tick.py`.

**What was still true, and where it moved — the part not deleted, spot-
checked before this retirement, so nothing here is discarded on a guess.**
§10's CLI verb table was **~80% accurate**: 11 of its 14 documented verbs
(`batch`, `check`, `convert`, `determinism`, `doctor`, `explain`, `export`,
`list`, `probe`, `record`, `resim`, `run`) are still registered in
`cli/__init__.py`; `sim diff` was already correctly documented as never
having existed; `view`/`render` are gone with the Python GUI (`7d4c626`,
same commit); `validate` is a new, undocumented verb (`cli/validate.py`).
§9's closed error taxonomy (`SimError`/`AuthoringError`/`ContractError`/
`InternalError`) is **conceptually unchanged, relocated** from
`core/errors.py` to `diagnostics/errors.py` — same names, same shape.
Neither of these is normative on its own; each is restated where it still
governs: `R-SIM-19` (crash/hang isolation), `R-SIM-25` (evidence,
`unknown` never a plausible default), `R-SIM-4`/`R-SIM-22` (named,
generated ports), `R-SIM-14`/`R-SIM-15`/`R-SIM-21` (codecs, closed override
verbs, manifest-bound port addresses) — all in `.claude/rules/sim.md`,
unchanged by this retirement.

**Net:** a stale contract is more dangerous than no contract — the failure
mode a reader risks is building against `scene.Prim`/`LayerProvider`
believing it current. Nothing normative is lost: every decision this
document encoded that still governs the product is already in
`.claude/rules/sim.md` and the v2 requirement set, the same pattern the
other nine retired `docs/v1/` files followed. `.claude/rules/sim.md`'s own
citation of this file's "a signature here is a contract" claim is removed
in the same pass, not merely reworded — see that file's own history for
the before/after.

No live external reader and no `R-REQ-2` trace exposure (checked,
`misc/STEP_7_SHRINK_PLAN.md` §3). Record of the conditional check and this
retirement decision: `docs/v2/SIM_Test_Execution_2026-09-01_step7_execution.md`.
