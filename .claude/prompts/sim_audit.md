# Prompt: sim_audit — full-scope audit & replan for `modules/sim`

**Execute `../../../../.claude/prompts/system_audit_and_replan.md` (root) with
the bindings below.** That file is the method — traversal order, the
propagation rule, the ledger discipline, the five angles. This file only says
*which documents, which ids, which commands* for `sim`. Nothing here restates
the method; if the two ever disagree, the root method wins.

**Paths** are relative to `modules/sim/` unless they begin `modules/`
(superproject-relative) or are called out as root.

---

## 1. The document triad

| Level | Document | Role |
|---|---|---|
| **1 · Requirements** | `docs/sim_requirements.md` | **Master register.** `FR-`/`NR-`/`CR-SIM-n`, verbatim asks, `Status`/`Priority`/`Verified by` per row, decisions register (§9), explicitly-parked (§10), open questions (§11), adversarial audit (§12). **Outranks every other document here** — when it disagrees with a design doc or the code, they are wrong. Read §0a first: it states what the register deliberately does *not* track. |
| **2 · Design** | `docs/sim_architecture.md` | Master design. §5.x answers the register; §10 holds `OD-n` decisions and `D-n` defects. |
| **3 · Plan** | `docs/sim_implementation_plan.md` | Checkbox-tracked build order. §0a `START HERE` + the build-sequence table is the authority on order; §2 the global gates; §9 traceability. |
| **4 · Code** | `src/adas_sim/**`, `tests/**`, plus each component's `modules/<name>/sim/**` plug-ins | |

**Binding satellite/contract docs** (level 2, all normative): `sim_sil_contract.md` ·
`sim_api_reference.md` (**a signature there is a contract**) ·
`sim_visualization_spec.md` · `sim_resim_and_recording.md` ·
`sim_scenarios_and_expectations.md` · `sim_player.md` ·
`sim_naming_and_diagnostics.md` (`N-1..N-13`, `DG-1..DG-5`) ·
`sim_portability.md` (`P-1..P-10`).

`docs/sim_learn.md` is a plain-language narrative — useful for sanity-checking
your own understanding, **not authoritative**.

## 2. The ledger

**`docs/sim_audit_log.md`** — stable ids `AR-n`. Enforced by
`docs/py/check_audit_ledger.py` (inside `run_all.py`), which fails if a
`CLOSED` row names no landed-in anchor, or names one that does not resolve.
That check is what makes the root method's *"level 1/2 findings are not
closable until the master document was edited"* rule real rather than
aspirational.

## 3. ID families

`FR-SIM-n` / `NR-SIM-n` / `CR-SIM-n` requirements · `R-SIM-1..25` rules (root
`.claude/rules/sim.md`) · `OD-n` decisions, `D-n` defects, `OQ-n` open
questions (architecture §10) · `S-A1`…`S-E3` stages **(declared STABLE — never
renumber, even when resequencing)** · `UT-`/`ST-` tests · `GT-1..GT-14` gates
(§2 classifies per-stage vs milestone) · `MC-1..5` manual checks ·
`DC-n` document invariants · `P-n` portability · `N-n`/`DG-n` naming and
diagnostics · `AR-n` audit findings.

## 4. Commands — run all of these, none is optional

From the **superproject root**:

```
modules/sim/.venv/Scripts/python.exe -m pytest modules/sim/tests -q
modules/sim/.venv/Scripts/python.exe modules/sim/scripts/check_invariants.py
modules/sim/.venv/Scripts/python.exe modules/sim/docs/py/run_all.py
```

**Use that interpreter, not a bare `python`** — a `python` on `PATH` has
already misled a session here. On Linux the venv path is
`modules/sim/.venv/bin/python` (`P-6`).

Real builds — **`GT-4`'s whole matrix, not just `df`**:

```
python scripts/build.py <module> -t gtest -p vs2026 -P base
python scripts/build.py sil_host -t sil -p vs2026 -P base   # then run sil.exe under conanrun.bat
```

`conan remote login adas-local demo -p demo` first, or builds stall ~10 min
then fail with `EOF when reading a line`.

> **Check every shell before writing "no compiler here."** This repo's Windows
> shell has Conan + CMake + MSVC; a WSL shell in the same checkout has neither
> wired to `AdasInterfaces`. A session recorded "no toolchain", landed `S-C5`
> unverified, and it was red — the toolchain was one shell away.

## 5. Root `docs/` — sim's two lists

The root method's angle 5 stratifies the superproject's `docs/` and states the
two module-independent classes (normative, completed-item records). This
section names only sim's own two. Measured 2026-08-04: 45 documents, **no
orphans** — everything is cited by something.

**Sim-adjacent — in scope:** `ai_operational_layer_spec.md` (angle 5 governs
`.claude`, including this file) · `df_sil_dll.md` + `sil_integration_host.md` +
`partial_clone_workflow.md` (the ABI / host / clone contracts sim consumes) ·
`shared_config_plan.md` (the bundle's inputs).

**Legacy tooling sim replaces — retirement inventory only, owned by `S-E1`:**
`df_carla_bridge_blueprint.md` · `df_carla_viz_plan.md` ·
`df_carla_mcap_replay_plan.md` · `df_carla_scenario_architecture.md` ·
`df_carla_scenario_layout.md` · `df_carla_tools_relocation_plan.md`.

Sim's entry in root `plan.md` is **item 25**.

## 6. This module's half of the operational layer

**Audit targets, every run:** `modules/sim/CLAUDE.md` and this file. They are
the module half of the root method's angle 5.

`modules/sim/.claude/` currently holds **only** `prompts/sim_audit.md`. Do not
add `rules/`, `skills/`, `templates/` or `workflows/` here unless there is a
genuine sim-only deviation — everything cross-cutting is root-canonical
(`docs/ai_operational_layer_spec.md` §7). Placement of anything new is decided
by the root method's angle 5; it is not restated here.

## 7. Module-specific "stop and ask"

**In addition to** the root method's `STOP AND ASK` list (which already covers
contradicting design documents — `GT-7`, and two have disagreed here — a test
that needs a tolerance or gate weakened, and being unable to run the real
build):

- A stage's scope appears to require changing `src/component/**`. It must not.
- The exemption a failing test wants is a `GT-1`/`GT-11` one.
- The work needs a **seventh override verb, a sixth fault, an expression
  anywhere, or a port address spelled as a literal.** Each is a closed list
  with a written reason; reopening one is a design change, not an
  implementation choice.

## 8. Known traps

- **`GT-1`'s literal grep has a word-boundary gap** — `\b` treats `_` as a word
  character, so `BSD_SENSOR_0_...` slips through. Run
  `scripts/check_invariants.py`, never the literal grep.
- **The documented flake:**
  `tests/system/test_b3_viewport_controls.py::test_dragging_pans_the_viewport_and_a_second_click_still_selects`
  is a fixture-isolation bug in §10's risk table. Not yours unless a stage says
  it is — but note which direction it failed, the observation has reversed once.
- **`tests/system/test_c5_relocatability.py` skips silently on Windows** (needs
  `g++`). A green suite on the primary dev platform does not mean it ran.
- **A green `run_all.py` does not mean the requirements are met.**
  `check_requirement_coverage.py` scores `UT-`/`ST-` only, so a row resting on
  an `MC-`/`GT-`/`DC-` verifier reports on its remaining ids alone —
  `FR-SIM-47` (`P0`) reads `proven 3/3` with `MC-5` never run. 21 of 77 rows
  are affected. Read `sim_requirements.md` §0a's caveat table before quoting a
  coverage number (`AR-34`; the mechanical fix is `AR-36`, blocked on `AR-35`).
- **A ticked box does not mean the code contains the feature.** Run 3 found two
  panels with passing system tests that the application never constructs
  (`AR-45`), because the tests instantiate the widget directly. When a stage
  claims a UI element, **grep for its constructor in `app/`**, not just for its
  test.
- **`run_all.py` has six checks, not five** — `check_verifier_discoverability.py`
  ratchets a baseline (19). Lower it when you fix one; raising it needs a
  written reason, like a `GT-4` floor.
