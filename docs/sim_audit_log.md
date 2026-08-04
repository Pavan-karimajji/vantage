# Simulation Platform — Audit Findings Ledger

**This file is an index, not a container.** Every finding's *fix* is a
checkbox in the stage that will do it, and every correction lives in the master
document that was wrong. A row here points at those; it never carries the
correction itself.

Produced and reconciled by `modules/sim/.claude/prompts/sim_audit.md`
(method: root `.claude/prompts/system_audit_and_replan.md`). Enforced by
`docs/py/check_audit_ledger.py`, inside `docs/py/run_all.py`.

## How to read a row

| Field | Meaning |
|---|---|
| **ID** | `AR-n`. **Stable, never reused** — cite it in commits and checkboxes. |
| **Lvl** | Origin level: **1** requirement · **2** design/contract · **3** plan/sequence · **4** code. Determines what must be edited, not how bad it is. |
| **Fix** | `code` · `verify` (proof missing) · `docs` · `plan` · `cleanup` — who acts. |
| **Landed in** | The document(s) and/or stage(s) that changed. **A `CLOSED` row must name at least one**, and the check fails if it names none or names one that does not resolve. |
| **State** | `OPEN` · `CLOSED` · `SUPERSEDED` · `WONTFIX` |

**The rule that governs level 1 and 2 findings:** they are **not closable until
the master document at that level has been edited**. Correcting a requirements
defect means editing `sim_requirements.md` — this ledger only records that it
happened and where. A row describing a correction no master document contains
is the failure the whole mechanism exists to prevent.

**Reconciliation precedes appending.** Every audit run re-verifies each `OPEN`
row before writing a new one. If a run cannot shrink this table, the previous
run's output was ignored — which is itself a finding.

## Which file to start from

| If the job is… | Start at |
|---|---|
| *"fix the audit findings"* | **this file** — pick rows from Open, then follow each to its owner |
| *"what do we build next"* | `sim_implementation_plan.md` §0a — the resume marker and build order |
| *"audit the module again"* | `../.claude/prompts/sim_audit.md` |

The two are not alternatives: this file is an **index by problem**, the plan is
the **queue by build order**. A finding always names its owner, so starting
here always leads back to the plan — but a fix session should still read the
owning stage before editing, because the stage carries the `**Must not**`
constraints and this file deliberately does not repeat them.

## How to work a row

1. **Read the row, then open its owner** — the stage or document under *Landed
   in / owner*. Do not fix straight from this file.
2. **Fix at the origin level.** `Lvl 1`/`2` means the master document
   (`sim_requirements.md`, `sim_architecture.md` or a contract doc) is edited —
   a requirements defect is not fixed by changing code that happens to satisfy
   the new reading.
3. **Re-verify with the evidence the row names** — the failing test, the build
   command, the check. Not "it looks right now".
4. **Tick the owning stage's checkbox**, citing the `AR-n`.
5. **Move the row to Closed**, filling *Landed in* with the document(s) and/or
   stage(s) actually edited, plus the date.
6. **Run `python docs/py/run_all.py`.** `check_audit_ledger.py` refuses a
   `CLOSED` row that names nothing, names something that does not resolve, or
   — for `Lvl 1`/`2` — names only a stage. That refusal is the point: it is
   what stops this file drifting into being the correction rather than the
   index of one.
7. **Commit citing the id** (`fix(sim): AR-1 -- …`).

**A fix session may not add findings.** If it discovers something new, note it
and leave it for the next audit run — mixing discovery into fixing is how a
ledger stops being reconcilable.

---

## Run 1 — 2026-08-04

First full-scope audit. Built every module in `GT-4`'s matrix for real, ran the
whole suite, and walked the requirements register row by row for the first
time. 22 findings.

### Open

| ID | Lvl | Fix | Finding | Landed in / owner | Since |
|---|---|---|---|---|---|
| **AR-1** | 4 | code | **The packed config bundle does not travel with `df_sil.dll`.** No `install()` rule for `config/`, and `modules/df/tests/CMakeLists.txt:95` copies the DLL without it. Two failing gtests; `adasInit(NULL)` returns `NULL` and `config_bundle_sha256` is empty for every consumer outside df_sil's own build tree. **Blocks `S-C5`.** | `sim_implementation_plan.md` `S-C5` (4-step fix in §0a) | 2026-08-04 |
| **AR-2** | 3 | plan | **`GT-4`'s `mathlib` row is not runnable** — `mathlib`'s `conf/build.yml` declares only `sil`/`package`; `-t gtest` exits *"unknown target"*. Not a blank measurement; a row that reads as a gate and is not one. **Needs a human decision.** | `sim_implementation_plan.md` §2 `GT-4`; resume marker | 2026-08-04 |
| **AR-3** | 3 | verify | **`tests/system/test_c5_relocatability.py` skips silently on Windows** (needs `g++`), so `S-C5`'s only Python-side system test never runs on the primary dev platform. Either build the fixture with the MSVC toolchain that is present, or declare it Linux-only in the skip reason. | `sim_implementation_plan.md` `S-C5` | 2026-08-04 |
| **AR-4** | 3 | verify | **`GT-13` and `GT-14` are blank and unowned**, as are `GT-8`'s and `GT-14`'s Owner/Date/Measured fields. They cannot be closed by code. **Needs a named person.** | `sim_implementation_plan.md` §2; resume marker | 2026-08-04 |
| **AR-5** | 3 | verify | **`GT-10` (every module builds standalone) is an intention with no test** — every build so far, including this audit's six, ran in a full checkout with editables registered, the configuration that hides a missing `requires:`. | `sim_implementation_plan.md` §2 `GT-10` | 2026-08-04 |
| **AR-6** | 3 | cleanup | **`docs/py/logs/` is silently uncommittable.** `.gitignore:40`'s unanchored `logs/` matches it at any depth, while `docs/py/README.md` declares it committed proof. Evidence trail stopped 2026-07-30 with `git status` clean throughout. README is right; the `.gitignore` is the defect. One-character fix (`/logs/`). **Flagged, not applied** — it makes 24 files appear and that is a commit decision (`R-GIT-2`). | `sim_implementation_plan.md` resume marker | 2026-08-04 |
| **AR-7** | 4 | code | **`ST-C9-1` is real but ungreppable** — implemented in `tests/system/test_c1c_resim_equivalence.py`, a file named for a different stage whose docstring announces `ST-C1c-1` and which never mentions `ST-C9-1`. It is `P0` `FR-SIM-66`'s primary verifier. One-line fix: put the id in the docstring. | `sim_implementation_plan.md` resume marker | 2026-08-04 |
| **AR-8** | 4 | code | **`ST-C2-3` is claimed by a docstring that does not implement it** — `tests/unit/test_c2_recorder.py` lists it; no test function exists and the plan's box is correctly unticked. `AR-7` with the polarity reversed. | `sim_implementation_plan.md` resume marker | 2026-08-04 |
| **AR-9** | 3 | cleanup | **`modules/mathlib` is not registered in the superproject's `.git/config`** — `git submodule status` shows `-`, so `submodule foreach`/`update` skip it. Working tree is a healthy clone; a fresh clone is unaffected. Fix: `git submodule init modules/mathlib`. | *(housekeeping — no stage)* | 2026-08-04 |

### Closed

| ID | Lvl | Fix | Finding | Landed in | Closed |
|---|---|---|---|---|---|
| **AR-10** | 1 | docs | **The register cannot express "built".** `Status` is `frozen`/`partial`/`open`/`parked`, where `frozen` means *decided, not built* — so 68 of 77 rows still read `frozen` after twelve stages, and a shipped requirement is indistinguishable from an unstarted one. Resolved **by derivation, not a new field**: a hand-kept `Built:` column would be the drifting second copy `R-SIM-22`/`D13` forbid. | `sim_requirements.md` §0a; `docs/py/check_requirement_coverage.py` (in `run_all.py`) | 2026-08-04 |
| **AR-11** | 1 | docs | **`FR-SIM-66` (`P0`) is verified at one depth only** while its headline says *"at whatever depth they were cut"* — `ST-C9-2`/`ST-C9-3` unwritten. `S-C9` was honest; the register was not. Now reports as `partial 2/3`. *(The work itself remains `S-C9`'s open items — not re-opened here.)* | `sim_requirements.md` §0a | 2026-08-04 |
| **AR-12** | 3 | docs | **`plan.md`'s status-summary row 25 contradicted item 25's own body in the same file** — *"design done, build not started, three decisions open"* vs Block 1 landed and `OD-1/2/3` confirmed. Body was right. | `plan.md` | 2026-08-04 |
| **AR-13** | 3 | docs | **Stage/test/gate/requirement counts disagreed across three places** (16 vs 21 vs 29 stages; 102/40 vs 125/43 tests; 7 gates; 45 requirements). Re-measured: 32 stage sections, 248 `UT-`, 84 `ST-`, 14 `GT-`, 77 requirements. | `plan.md`; `sim_implementation_plan.md` §0a, "Effort shape" | 2026-08-04 |
| **AR-14** | 3 | docs | **`S-C5`'s note recorded "558 tests"** when `S-C1d`, an earlier stage, had already recorded 643. Actual: 652 collected / 649 passed / 3 skipped. | `sim_implementation_plan.md` `S-C5` | 2026-08-04 |
| **AR-15** | 3 | plan | **`GT-4` was defined on test *count* only**, so a red build satisfied it — and currently would (238 above the 233 floor with two failures). A pass clause is now part of the gate. | `sim_implementation_plan.md` §2 `GT-4` | 2026-08-04 |
| **AR-16** | 3 | docs | **`GT-4`'s matrix had two blank rows and a wrong command form**; the `sil_host` row claimed *"builds + runs"* for a command that only builds (`sil.exe` bare gives `STATUS_DLL_NOT_FOUND`; runs correctly under `conanrun.bat`). All rows re-measured: `df` 238 with 2 failures · `interfaces` 10 (floor was 6) · `vdy` 18 · `perception-core` 2 (first number) · `sil_host` builds and runs · `mathlib` see `AR-2`. | `sim_implementation_plan.md` §2 `GT-4` | 2026-08-04 |
| **AR-17** | 3 | docs | **Every stage's Discipline line says `GT-1..GT-12`, but `GT-13`/`GT-14` exist** — so the two gates added *by an adversarial audit to catch dishonesty* were excluded from every per-stage re-check. Fixed **by definition, not mass edit**: §2 now classifies gates as per-stage vs milestone. Mass-editing to `GT-1..GT-14` would have retroactively claimed ticked stages re-checked them. | `sim_implementation_plan.md` §2 and `S-E3` gate; `.claude/rules/sim.md` | 2026-08-04 |
| **AR-18** | 2 | docs | **`R-SIM-1`'s stated scope did not match its enforced scope.** The rule and `modules/sim/CLAUDE.md` said *"this module must never contain the strings"*; `check_gt1` scans `src/adas_sim` only, and ~25 legitimate occurrences exist under `tests/`. The exemption is right — a parity test must name the component it achieves parity with — but was undocumented, so the rule read as violated. Rule narrowed to match defensible practice; enforcement unchanged. | `.claude/rules/sim.md` `R-SIM-1`; `modules/sim/CLAUDE.md` | 2026-08-04 |
| **AR-19** | 3 | docs | **`S-D7` landed 17/27 out of build order and nothing recorded it** — both this plan and `plan.md` claimed "Phase D not started". Real, green work (15 passing tests); the risk was a session re-implementing it. | `sim_implementation_plan.md` §0a and build-order table; `plan.md` item 25 | 2026-08-04 |
| **AR-23** | 2 | docs | **The operational layer had no mode for "same procedure, different module's inputs".** §7 offered three: root-canonical-referenced (submodule holds nothing), byte-identical-copied, component-local. A method that must be *pointed at* a module's documents fits none, so it lands either buried in one submodule (the next module forks it) or at root stuffed with one module's specifics. Added as a fourth mode — **root method + module binding** — with an ordered four-step placement test whose step 3 is the one that gets skipped. Applies to rules/skills/workflows/templates, not just prompts. | `docs/ai_operational_layer_spec.md` §7; `.claude/README.md`; `.claude/prompts/system_audit_and_replan.md` angle 5; `modules/sim/.claude/prompts/sim_audit.md` §6 | 2026-08-04 |
| **AR-20** | 3 | docs | **The audit prompt itself never asked anyone to walk the requirements register** — it listed it as a source, and angle 1 asked a question answerable in a paragraph. Rewritten: requirements is now angle 1 of five, walked row by row, with the propagation and ledger discipline this file implements. | `.claude/prompts/system_audit_and_replan.md` (method); `modules/sim/.claude/prompts/sim_audit.md` (instantiation); `.claude/routing.md` | 2026-08-04 |

### Won't fix

| ID | Lvl | Fix | Finding | Reason | Decided |
|---|---|---|---|---|---|
| **AR-21** | 3 | cleanup | **`.gitmodules` declares `[submodule "modules/sil"]` with `path = modules/sil_host`**, so `.git/config` carries `submodule.modules/sil.*` for a directory named `sil_host`. | Renaming the section requires a matching `.git/config` edit in every clone, for a cosmetic gain. Recorded so the next person who greps for `submodule.modules/sil_host`, finds nothing, and concludes it is missing, stops here. | 2026-08-04 |
| **AR-22** | 3 | cleanup | **`docs/py/reference_tool_path.txt` holds an absolute path carrying an organization name.** | Verified `.gitignore`d (line 49) by design — it is the machine-local pointer `_common.py:reference_tool_root()` reads, and never ships. Recorded so a future audit does not re-flag it. | 2026-08-04 |
