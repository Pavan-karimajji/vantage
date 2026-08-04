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

**A fix session may not go looking for new findings.** Mixing open-ended
discovery into fixing is how a ledger stops being reconcilable.

**But a finding that is the direct output of a row you were working belongs to
that row, and is recorded.** *(Refined 2026-08-04, after the first fix session
hit exactly this: `AR-5` was "run `GT-10` for the first time", running it
failed for `df`, and the root cause — `interfaces` ships no `cmake/` in its
Conan package — is what `AR-5` was **for**. Discarding it to honour a rule
against sprawl would have thrown away the verification's entire result.)* The
test: **did the assigned row produce this, or did you wander into it?** The
former is recorded with a new id and cross-referenced from the row that found
it; the latter waits for the next audit.

**A fix session may not fix what it newly records**, and that half is firm.
`AR-24` needs a packaging change, a republish and a re-probe — a separate
verification cycle, which is precisely why finding it and fixing it are
different sessions.

---

## Run 1 — 2026-08-04

First full-scope audit. Built every module in `GT-4`'s matrix for real, ran the
whole suite, and walked the requirements register row by row for the first
time. 22 findings.

### Open

| ID | Lvl | Fix | Finding | Landed in / owner | Since |
|---|---|---|---|---|---|
| **AR-4** | 3 | verify | **`GT-13` and `GT-14` are blank and unowned.** Sharpened 2026-08-04 so the remaining decision is small: **`GT-13` cannot be filled yet and that is legitimate** -- per-tick cost and campaign throughput (`NR-SIM-41`) need `S-D7`'s batch half, frame time at a stated tick count (`NR-SIM-5`) needs the player, recording size (`NR-SIM-42`) needs `ST-C2-3`, and determinism across four axes (`NR-SIM-40`) needs `S-C6`. Its blanks are its finding until those land. **`GT-14` is the one that needs a person now** -- a named owner and a named second reader, plus a measured maintainer-onboarding time. No stage can produce those, and `S-E3` is where their absence becomes a blocked gate. | **human decision** -- `sim_implementation_plan.md` section 2, resume marker | 2026-08-04 |
| **AR-24** | 4 | code | **A component cannot be built from a partial clone: `interfaces` ships no `cmake/` in its Conan package.** `package_info()` declares `builddirs = ["cmake"]`, but `modules/interfaces/CMakeLists.txt` installs `cpp/`, `include/` and `proto/` and never `cmake/` -- so `CMake(self).install()` produces a package whose declared build dir does not exist, and a consumer's `include(sil_ports_generate)` / `include(config_bundle_pack)` finds nothing. `df` from a clean partial clone fails at CMake configure. Not staleness: the package downloaded from `adas-local` fine. The recipe's own comment predicted it -- *"untested by this stage (today's only exercised path is editable mode), kept symmetric on principle"*. Fix is an `install(DIRECTORY cmake/ ...)` in `interfaces`, **plus a republish and a re-probe**, which is why it was recorded rather than fixed in the same session that found it. Blocks `FR-SIM-66`'s "only that component checked out" claim and `docs/partial_clone_workflow.md`'s documented first-run. | `sim_implementation_plan.md` section 2 `GT-10`; needs an owning stage | 2026-08-04 |

### Closed

| ID | Lvl | Fix | Finding | Landed in | Closed |
|---|---|---|---|---|---|
| **AR-2** | 3 | plan | **`GT-4`'s `mathlib` row was not runnable** -- `conf/build.yml` declared only `sil`/`package`, so `-t gtest` exited *"unknown target"*. Decided in favour of wiring the target rather than striking the row: mathlib is the base of the dependency graph (`R-MATH-3`) and `df`'s 238 tests exercise it only transitively, which is the "watching one consumer" blindness `GT-4` was widened to prevent. `TC-U1`/`U2`/`U3` + `TC-D2` implemented (29 cases, green on `-P base` and `-P cus1`); `TC-U4`/`U5`/`D1` stay **open** in `math_library_plan.md` -- they need a published ULP bound, an allocation hook and a golden file, which is item 22's work, and ticking them without those artefacts closes a box without its guarantee. **Its first link found a real latent defect**: `e_atan2f.c`/`e_powf.c` referenced `fabsf` while `s_fabsf.c`'s definition was renamed to `__olm_fabsf` -- unresolved at link, invisible because nothing had ever linked mathlib's float path. Fixed by renaming at the call sites, which is also the bit-exact answer (openlibm's internals must call openlibm, not the host CRT). `df` re-verified 238/238 against the rebuilt mathlib. | `modules/mathlib/CMakeLists.txt`; `modules/mathlib/conf/build.yml`; `modules/mathlib/tests/`; `docs/math_library_plan.md` section 9; `sim_implementation_plan.md` section 2 `GT-4` | 2026-08-04 |
| **AR-5** | 3 | verify | **`GT-10` was an intention with no test.** Now run for the first time: fresh superproject clone, **one** submodule initialised, and a separate `CONAN_HOME` -- the last part being essential, since this repo's normal Conan home registers every `adas-*` package editable and resolves them from the working checkout, which is exactly the configuration `GT-10` says hides the failure. Result: **`mathlib` PASS, `df` FAIL.** The verification is complete and recorded; the defect it exposed is `AR-24`. | `sim_implementation_plan.md` section 2 `GT-10` (method + measured results) | 2026-08-04 |
| **AR-1** | 4 | code | **The packed config bundle did not travel with `df_sil.dll`.** No `install()` rule for `config/`, and `modules/df/tests/CMakeLists.txt` copied the DLL without it, so `adasInit(NULL)` returned `NULL` and `config_bundle_sha256` was empty for every consumer outside df_sil's own build tree. Fixed both sites: an `install(DIRECTORY ...)` whose destination tracks `install(TARGETS)` (`bin/` Windows, `lib/` Linux -- `P-5`), and a `copy_directory` beside the test DLL. **238/238 on `-P base` and `-P cus1`.** *Surfaced a second real defect:* `adasInit("")` returned a handle, because `""` fell through to the bundle tier instead of being refused as a supplied-but-invalid path -- and `UT-C1b-13` had been passing only because no bundle had ever been packed beside `df_tests.exe`. Both fixed. | `modules/df/src/platform/df_sil/CMakeLists.txt`; `modules/df/tests/CMakeLists.txt`; `modules/df/src/platform/df_sil/df_interface_c.cpp`; `sim_implementation_plan.md` `S-C5` | 2026-08-04 |
| **AR-3** | 3 | verify | **`ST-C5-1`'s Python half showed a misleading skip reason on Windows** -- and the original finding was overstated: the test already declared itself POSIX-only with a reason. The real defect was marker order. Both `skipif`s are true on Windows, `g++` matched first, so a Windows developer read *"no C++ toolchain available"* -- an environment gap rather than a designed boundary. Platform marker now first, naming where the Windows path is proven for real (`UT-C5-1`, green at 238/238). No MSVC port of the fixture: it would duplicate C++ coverage that exists. | `modules/sim/tests/system/test_c5_relocatability.py`; `sim_implementation_plan.md` `S-C5` | 2026-08-04 |
| **AR-6** | 3 | cleanup | **`docs/py/logs/` was silently uncommittable.** `.gitignore`'s unanchored `logs/` matched it at any depth while `docs/py/README.md` declares it committed proof, so the evidence trail stopped on 2026-07-30 with `git status` clean throughout. Anchored to `/logs/`, which still ignores `modules/sim/logs/` as the rule's own comment intends; the 26 orphaned evidence logs are now tracked. | `modules/sim/.gitignore`; `docs/py/logs/` | 2026-08-04 |
| **AR-7** | 4 | code | **`ST-C9-1` was real but ungreppable** -- implemented in `tests/system/test_c1c_resim_equivalence.py`, whose docstring announced only `ST-C1c-1`, so grepping the suite for a `P0` requirement's primary verifier found nothing. The docstring now names both ids and says which claim each makes (`ST-C9-1` is about the ingest map, `ST-C1c-1` about the ABI) so a future split moves each id with the half that still proves it. | `modules/sim/tests/system/test_c1c_resim_equivalence.py` | 2026-08-04 |
| **AR-8** | 4 | code | **`ST-C2-3` was claimed by a docstring that does not implement it.** `tests/unit/test_c2_recorder.py` listed it among its coverage; no test function asserts it and the plan's box is correctly unticked. Removed, with a note to re-add the id in the same commit that adds the test. | `modules/sim/tests/unit/test_c2_recorder.py` | 2026-08-04 |
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
| **AR-9** | 3 | cleanup | **`modules/mathlib` was not registered in the superproject's `.git/config`** -- `git submodule status` showed `-`, so `submodule foreach`/`update` skipped it even though the working tree was a healthy clone. | **Not a repo defect.** This is per-clone local state, and the remedy is already documented: `git submodule update --init` (`docs/partial_clone_workflow.md`). Run on this machine, so `mathlib` now reports its commit like every other submodule -- but there is nothing to commit, and a fresh clone was never affected. Recorded rather than closed because the ledger check rightly refused a CLOSED row that could name no landed-in artefact; "fixed my machine" is not "fixed the repo". | 2026-08-04 |
| **AR-21** | 3 | cleanup | **`.gitmodules` declares `[submodule "modules/sil"]` with `path = modules/sil_host`**, so `.git/config` carries `submodule.modules/sil.*` for a directory named `sil_host`. | Renaming the section requires a matching `.git/config` edit in every clone, for a cosmetic gain. Recorded so the next person who greps for `submodule.modules/sil_host`, finds nothing, and concludes it is missing, stops here. | 2026-08-04 |
| **AR-22** | 3 | cleanup | **`docs/py/reference_tool_path.txt` holds an absolute path carrying an organization name.** | Verified `.gitignore`d (line 49) by design — it is the machine-local pointer `_common.py:reference_tool_root()` reads, and never ships. Recorded so a future audit does not re-flag it. | 2026-08-04 |
