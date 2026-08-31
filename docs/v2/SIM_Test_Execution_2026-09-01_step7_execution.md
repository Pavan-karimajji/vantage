# SIM Test Execution — 2026-09-01 — Step 7 execution

**Campaign.** Execute `misc/STEP_7_SHRINK_PLAN.md` (written 2026-08-31,
approved by the author for execution 2026-09-01), following the plan's own
§8 sequencing, one phase per commit, with two amendments given at approval
time: (a) run the plan's own conditional check on `sim_api_reference.md`
before any retirement, stopping that item on a real finding rather than
retiring on assumption; (b) do not edit `.claude/rules/sim.md` in this pass
— collect every rule-file edit the retirement makes necessary into a list
for separate approval instead.

## 0. Preliminary commit

`misc/STEP_7_SHRINK_PLAN.md` and the `misc/START_HERE.md` update that
accompanied it (both already drafted, uncommitted, from the prior session)
were committed first, per instruction: `sim` `1e2bb5b`, superproject
`37cebaa`.

## 1. Conditional check (amendment a) — result: a real, separate finding

The plan's §3 row for `sim_api_reference.md` said: "check `rules/sim.md`'s
claim against the current build: if any symbol it names ... is no longer
produced that way, that is a real, separate finding to raise before
retiring — not assumed clean by this plan."

**Checked directly against `modules/sim/src/adas_sim/` as it exists today.**
The document's §1 package map, §1a file table and §5 (`Prim`/`Layer`/
`LayerProvider`) describe `scene/`, `render/` and `app/` Python packages —
all three are now empty directories (`scene/`/`render/` contain only
`__pycache__`; `app/` does not exist at all). Commit `7d4c626`
("SM-12: delete the Python scene/render/player implementation", 2026-08-29,
Decision B) removed them wholesale. The package map also no longer matches
in structure beyond that: `contracts/` became `graph/`, `core/` was split
into `session/`/`engine/`/others, and `config/`, `diagnostics/`, `ingest/`,
`launcher/`, `orchestrate/`, `plugins/`, `pyapi/`, `resolve/`, `runspec/`
did not exist when the document was written. `Pipeline` now lives in
`graph/build.py`, not `contracts/pipeline.py`; `Session` in
`session/session.py`, not `core/session.py`; `PortValue` in
`session/tick.py`, not `core/tick.py`.

**Disposition: `sim_api_reference.md` is excluded from this pass's
retirement.** It is not merely stale (the disposition every other v1 file
received) — its central claim ("a signature here is a contract") is false
for a large fraction of its own content, describing code that no longer
exists. Retiring it to a stub on the assumption it was safe, as the plan's
own table tentatively proposed, would have been exactly the "assumed
clean" failure mode the conditional check exists to prevent. Left as full
text, unretired, pending its own remediation — a decision for the author,
not this pass.

## 2. Phase 1 — v1 document retirement

Commits: `sim` `d35f7b5` (the nine stubs + extraction + register),
`df` `b4c44c4`, `viz` `6fe91cf` (citation path updates), superproject
`47358df`/`a1b85fb`/`246d5ae` (pointer bumps).

- **9 files retired to stubs**, each naming its successor and the exact
  commit holding full text (`1e2bb5b`): `sim_implementation_plan.md`,
  `sim_architecture.md`, `sim_sil_contract.md`, `sim_resim_and_recording.md`,
  `sim_learn.md`, `sim_scenarios_and_expectations.md`, `sim_portability.md`
  (folded into the same pattern for consistency, per the plan), and
  `sim_visualization_spec.md`/`sim_player.md` after extraction.
- **`docs/v1/FROZEN_DESIGN_ORIGINS.md`** created, holding the two
  documents' externally-cited fragments verbatim: the Scene primitive
  catalogue and style-token/theme taxonomy (from `sim_visualization_spec.md`
  §2/§3), and the Vantage naming rationale plus the "what shipped —
  reconciled" table (from `sim_player.md` §1/§10).
- **`sim_requirements.md` superseded** with a compact per-ID disposition
  table (`R-REQ-2`), built from `docs/v2/SIM_System_Requirements_v0.1.md`
  §25's own existing v1→v2 crosswalk rather than re-derived — verified by
  diff that all 80 IDs in the original register (not 77; the register's own
  count was stale) appear in that crosswalk, so every one resolves to a
  named v2 successor, a cut, or a process disposition.
- **`sim_naming_and_diagnostics.md` inspected, left untouched** — the
  plan's own conclusion ("almost nothing left to cut," 260 of 440 lines
  already the cited content) held up on a second look.
- **5 cross-repo citing files updated**, path-only, no content change:
  `df_viz_Raw_Requirements_v0.1.md`, `df_viz_System_Requirements_v0.1.md`,
  `df_viz_Concept_Document_v0.0.1.md` (`df`); `VIZ_Concept_Document_v0.0.1.md`,
  `cpp/viz/player/workspace_mode.hpp` (`viz`) — each repointed at
  `FROZEN_DESIGN_ORIGINS.md` where it cited extracted content, or annotated
  "retired, evidence only at commit `1e2bb5b`" where it cited content that
  was not extracted (`workspace_mode.hpp`'s §4/§5 references). `errors.yaml`
  needed no change — `sim_naming_and_diagnostics.md` is not moving.
- Two pre-existing, unrelated dirty files in `df`
  (`src/platform/cm/Movie/Camera.cfg`) and `viz`
  (`src/third_party/{glfw,stb}/.pin_manifest.sha256`) were left untouched
  and unstaged throughout — not part of this work.

**Verified after phase 1:** `python3 docs/v2/py/trace_check.py` — clean
pass, identical `CN`/`SYS`/`SW`/`IMP`/`WP`/test counts and the same six
known notes as the pre-retirement baseline. `python3
docs/v2/py/trace_check.py --status` — identical 297/376 (79%) derived
progress, no drift. `python3 scripts/check_invariants.py` — clean
(`GT-1, GT-2, GT-3, GT-6, GT-11, UT-D8-9, WP-02(b),
ANL-SW-02/03/04/07/08/35/37/38/61`).

## 3. Phase 2 — essay-checkbox compression

Commits: `sim` `4c7aba5`, superproject `bc46c44`.

**Scope re-measured before executing, and found larger/different in shape
than the plan assumed.** The plan's §6 said 85 of 177 top-level checkbox
rows in `SIM_Implementation_Plan_v0.1.md` exceed 300 characters, totaling
79,512 characters (measured here: 69,785 characters — close, the small gap
is plausibly a counting-method difference, not a re-derivation error).
Checked directly: **none of the 85 rows already cite a
`SIM_Test_Execution_*.md` file**, and all 85 are historical narrative from
before the 2026-08-27 reset that started the dated-record discipline (24
such records exist, none matching any of these 85 rows' own stated closure
dates, which range from 2026-08-12 to 2026-08-25). The plan's "move the
narrative into (or confirm it already exists in) the matching dated Test
Execution record" therefore had no record to move into or confirm against
for any of the 85 rows — the literal instruction would have meant authoring
new, retroactively-dated files purely to relocate text already present,
adding no new verification.

**Raised to the author before proceeding** (`AskUserQuestion`); decision:
point each compressed row at the git commit that closed it instead of a
Test Execution file, the same provenance pattern this same shrink effort
already uses for the v1 doc stubs. Implemented via `git blame` per line
(49 distinct commits across the 85 rows) plus a hand-drafted short closing
clause per row, applied by an exact-line-number Python replacement (not
`sed`/regex, to avoid any risk of matching the wrong occurrence in
near-duplicate text).

**Result:** 70,504 → 33,343 characters across the 85 touched lines
(~53% reduction) — short of the plan's ~80% estimate, because several rows
carry `IMP-*`/`SW-*` id lists that `trace_check.py` itself parses
(`Lands:`/`Files:` rows) and those were kept verbatim rather than
compressed, on the reasoning that shrinking a machine-checked list for
brevity risks the exact drift `R-REQ-1`/`R-REQ-11` exist to prevent. 67 of
the 85 rows remain over 300 characters after compression for the same
reason — judged an acceptable outcome against the goal (removing
investigative narrative, not minimizing byte count for its own sake) rather
than pushed further.

No `Shall`/`Accept`/`Verify`/`Trace` anatomy touched anywhere else in the
v2 set, as the plan specified.

**Verified after phase 2:** `trace_check.py` — clean, identical counts to
the phase-1 baseline. `trace_check.py --status` — identical 297/376 (79%),
**no derived-mark drift** (`R-REQ-6a`'s own requirement: "the ordinary
check run recomputes every derived mark and fails on disagreement").
`check_invariants.py` — clean, same nine checks.

## 4. End-of-pass rule-file edit list (amendment b) — presented, not applied

Two edits to `.claude/rules/sim.md`, collected per instruction rather than
applied in this pass:

1. **R-SIM-1's row** — drop the dangling "Full map:
   `modules/sim/docs/v1/sim_architecture.md` §5.8." sentence.
   `sim_architecture.md` is now a stub with no §5.8; the rule's own body
   already restates the placement rule verbatim (flagged safe to drop by
   `STEP_7_SHRINK_PLAN.md` §3 before any retirement happened).
2. **The preamble's `sim_api_reference.md` citation** — amend from "the
   exact symbols an implementation must produce — a signature there is a
   contract" to a status note: stale, not retired, checked 2026-08-31
   against the current build and found to describe deleted packages;
   treat as unreliable pending its own remediation.

No other rule edit is needed — every other retired file is a stub or
compact register that names its own successor, and per the author's own
framing at approval time, "a rule pointing at a stub that names its
successor is not broken, it is stale, and stale is survivable for one
pass."

## 5. Net effect, measured

| Set | Before | After | Change |
|---|---|---|---|
| `docs/v1/` | 17,681 lines / 1.1 MB | 2,078 lines / 119,720 bytes | **−88% lines, −89% bytes** |
| `docs/v2/` | 18,213 lines / ~2.0 MB | 18,213 lines / 1,715,487 bytes | line count unchanged (as the plan predicted — the compressed rows were single long lines); **−~18% bytes** from the checkbox compression alone |
| `misc/` (tracked `.md`) | ~1,680 lines | 1,904 lines | **+13%** — this pass's own `STEP_7_SHRINK_PLAN.md` and `START_HERE.md`/this record's additions outweigh the (deferred, per §7) `START_HERE.md` "Where we are" trim |
| **Total** | ~35,894 lines / ~3.1–3.3 MB | ~22,195 lines / ~1.87 MB | **−38% lines, −~40% bytes** |

**The plan's own headline target — "~4,000–4,500 lines total" — was not
reached, and could not have been from the plan's own numbers.** Its §2
states `docs/v2/` structure stays "unchanged" and estimates only a byte
reduction on the implementation plan, "not its structure" — meaning `docs/
v2/`'s ~18,200 lines were never going to move. A total near 4,000–4,500
requires `docs/v2/` itself to shrink by an order of magnitude, which no
part of the plan proposed. This reads as an arithmetic inconsistency in the
plan's own §2, not a shortfall in execution — the two things the plan's own
per-section breakdown ordered done (v1 → ~950–2,000ish lines, the
implementation plan's byte weight cut) are both done, verified, and
committed. Named here rather than quietly reconciled, per this project's
own "a finding, not a style choice" discipline.

## 6. What remains, per the plan's own §7 and §9

- `misc/START_HERE.md`'s "Where we are" trim — explicitly deferred by the
  plan to "ordinary session hygiene going forward," not a one-time edit.
  Not done this pass.
- `MOVEMENT_B_PLAN.md` — not yet closeable (`B4`'s one real item still
  open), unchanged, per the plan's own §7.
- The two `.claude/rules/sim.md` edits above — held for separate approval.
- `sim_api_reference.md` — unretired, its own remediation (rewrite against
  the current C++/Python split, or a different disposition) is a separate
  decision for the author.
- Nothing in `docs/v2/`'s `Shall`/`Accept`/`Verify`/`Trace` anatomy was
  touched, per the plan's explicit §9 exclusion.
