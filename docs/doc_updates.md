# Documentation cleanup — the plan

**This file is scaffolding.** It plans a one-off restructuring of
`modules/sim/docs/*.md` ahead of a content freeze, tracks its progress, and is
**deleted when the last box below is ticked**. Nothing here is normative; the
documents it edits are.

---

## 1. The outcome being bought

Today the design set is **20,889 lines across 13 documents**, of which the
implementation plan alone is 8,964 lines carrying only **819 checkboxes** — the
other 91% is prose, and most of that prose is a *journey*: what was tried, what
broke on which date, which audit run re-opened it. That was the right thing to
write while the work was moving. It is the wrong thing to read at a freeze.

After this pass a reader should be able to open the set and answer, quickly:

- **What is this tool, and what is it for?** → `sim_learn.md`
- **How do I run it, and what do I configure?** → `sim_learn.md` §4/§5 *(new)*
- **What was asked for?** → `sim_requirements.md`
- **How is it built, and why that way?** → `sim_architecture.md`
- **What is done, what is left, which test proves it?** → `sim_implementation_plan.md`

**Every ID survives.** A grep for `S-C5`, `UT-B1-8`, `AR-52` or `FR-SIM-66`
must still land somewhere useful, because those strings are in commit messages,
test docstrings and source comments. What goes is the narrative *around* the ID,
not the ID.

### The measured target

| Document | Now | Target | Nature of the cut |
|---|---:|---:|---|
| `sim_implementation_plan.md` | 8,964 | ~2,400 | per-stage findings/status narrative → checkbox + one-line limits |
| `sim_requirements.md` | 2,254 | ~950 | §0a audit preamble; editorial prose inside rows |
| `sim_architecture.md` | 2,841 | ~1,500 | defects D1–D14 and decisions OD-1–13 → tables; resolved OQs folded |
| `sim_sil_contract.md` | 1,155 | ~700 | resolved open points; restated rule text |
| `sim_resim_and_recording.md` | 1,007 | ~650 | resolved open points; dated corrections in code fences |
| `sim_visualization_spec.md` | 910 | ~650 | §17 open points; rationale prose |
| `sim_api_reference.md` | 805 | ~750 | light — it is signatures, and a signature is a contract |
| `sim_learn.md` | 726 | ~780 | **grows**: −180 phase prose, +230 how-to-use / how-to-configure |
| `sim_scenarios_and_expectations.md` | 678 | ~450 | migration log; resolved open points |
| `sim_naming_and_diagnostics.md` | 440 | ~330 | rationale under each `N-`/`DG-` |
| `sim_player.md` | 431 | ~300 | §10 "what shipped, reconciled" |
| `sim_portability.md` | 291 | ~230 | §4a dated reconciliation → folded into §2/§4 |
| `sim_audit_log.md` | 387 | **0** | deleted (§3.2) |
| **Total** | **20,889** | **~9,690** | **≈54% smaller** |

Line counts are a proxy, not a goal. A stage that genuinely needs twelve lines
gets twelve lines.

---

## 2. Decisions taken before planning

| # | Question | Decision |
|---|---|---|
| 1 | The `**Origin.**` field's dated verbatim quotes in the register | **Keep the quote, drop the date.** The phrasing is the requirement; the date is a log |
| 2 | `sim_audit_log.md` | **Delete the file.** All 61 rows are closed or won't-fix — there is nothing open to migrate |
| 3 | Scope beyond `docs/` | **Include** `modules/sim/README.md` and `modules/sim/CLAUDE.md` |
| 4 | Superproject `plan.md` item 25 | **Compact** to a one-line pointer at the plan's §0a |

---

## 3. Invariants — what this pass must not break

### 3.1 The machine-enforced document contracts

Six scripts in `docs/py/` parse these documents. They are the reason this
cleanup is safe to do at all: they will catch a dropped ID that review would
miss. **Baseline captured before any edit: all four fast checks pass**
(`check_doc_invariants`, `check_traceability`, `check_rules_coverage`,
`check_requirement_coverage`).

Structures that are **load-bearing** and must be preserved byte-shape:

| Shape | Required by | Note |
|---|---|---|
| `### FR-SIM-n — Title` (em-dash or `--`) | `check_traceability`, `check_requirement_coverage`, `check_doc_invariants` DC-8 | also `NR-`/`CR-` |
| `### S-Xn — Title` | `check_traceability`, `check_audit_ledger` | stage headings |
| `**Requirement.**` `**Origin.**` `**Answered by.**` `**Verified by.**` `**Status.**` `**Priority.**` | `check_requirement_coverage` `FIELD_RE` | a field ends at the next `**Xx`, so **field order and the bold-dot shape matter** |
| `**Tests**` bold marker | `check_traceability` | toggles test-harvest mode; tests must sit under it |
| `**Gate**` bold marker | `check_traceability` §3 | every stage must have one |
| `- [ ] \`UT-A2-1\`` — id is the **first token** after the box | `check_requirement_coverage`, `check_verifier_discoverability` | `> ` prefix and `~` state allowed |
| `- [x] \`GT-1\`` / `MC-` / `DC-` | `check_requirement_coverage` `OTHER_DEFN_RE` | the only way a gate's state is representable |
| A test id is defined **under the stage its id names** | `check_traceability` §2 | `UT-B1-*` must live in `S-B1` |
| viz §16 checklist: every row names a stage | `check_doc_invariants` DC-4 | `\b(?:S-)?[A-E]\d[a-z]?\b` |
| arch §5.8: every `` `modules/…` `` path claimed | `check_doc_invariants` DC-5 | informational, but keep honest |
| api ref §10 CLI table ≡ `cli/__init__.py` `add_parser` | `check_doc_invariants` DC-9 | **14 verbs**, exact set |
| Every internal `[..](..)` link resolves | `check_doc_invariants` DC-1 | **deleting `sim_audit_log.md` breaks 6 links — §3.2** |
| Every `R-SIM-n` cited by ≥1 requirement **and** ≥1 stage | `check_rules_coverage` | all 26 rules; a rule that loses its last citation fails |
| No `aeb`/`bsd`/`lca`/`acc`/`ldw`/`lka` in framework-owned scripts | `check_doc_invariants` DC-7 | applies to `docs/py/*.py`, not to the docs' prose |
| Every **ticked** `UT-`/`ST-` id appears in some source file | `check_verifier_discoverability` | so **never untick and never rename** a done test |

**The rule that follows from the table:** compress prose freely; never touch a
checkbox line's `- [x] \`ID\`` prefix, a `### ` heading's id, or a `**Field.**`
marker.

### 3.2 Consequences of deleting `sim_audit_log.md`

Six live references must be handled in the same commit or `DC-1` goes red:

| Where | Action |
|---|---|
| `sim_implementation_plan.md` ×5 (lines ~797, 802, 940, 944, 8918) | remove the links; §9a becomes "Audit findings" → a short closed note (§4.4) |
| `sim_learn.md` ~604 (`AR-55` narrative) | that whole paragraph is a dated log — deleted anyway (§4.1) |
| `modules/sim/CLAUDE.md` ~88 | rewrite the audit paragraph |
| `modules/sim/.claude/prompts/sim_audit.md` ~35 | prompt tells future audits to write a ledger — update to say the ledger was retired at the freeze and findings land directly in the owning stage |
| root `plan.md` ×2 (834, 1542) | absorbed by the item-25 compaction (§4.9) |
| `docs/py/check_audit_ledger.py` + its entry in `run_all.py` | **delete both.** It checks one file that no longer exists. Bonus: it is the script that makes `run_all.py` time out on WSL |

Three source files cite `AR-53`/`AR-55`/`AR-56` in docstrings
(`scene/default_layers.py`, `tests/system/test_ar53_*.py`,
`tests/system/test_c8_relocatability_installed.py`). **Leave them.** They
describe a real behaviour and read fine without the ledger; rewriting test
docstrings is code churn outside this pass's scope.

### 3.3 The ID census

631 distinct IDs exist across the set today:

```
S- 33 · UT- 248 · ST- 87 · GT- 14 · MC- 5 · DC- 7 · FR/NR/CR-SIM 80
R-SIM 26 · N- 13 · DG- 5 · P- 10 · D(defect) 14 · OD- 13 · OQ- 15 · AR- 61
```

A census script (kept in the job scratch dir, **not committed**) re-runs after
every file and diffs against this baseline. Expected losses, and only these:

- **`AR-1`…`AR-61`** — all 61, with the ledger. Their *content* survives where
  it changed a design; their *rows* do not.
- **Resolved `OQ-n`** — folded into the `OD-` table or into the rule that
  answered them (§4.3). Each one is listed explicitly at the point of deletion.

Anything else disappearing is a bug in the edit, not a plan outcome.

A permanent census check is **deliberately not added**: after the freeze it
would fail every time someone legitimately adds an ID, and the four surviving
checks already enforce the ID *relationships* that matter.

---

## 4. Editing rules, applied everywhere

These are the transformations. Each is stated once here and referenced by the
per-file plan rather than restated.

**T1 — Status blocks.** A stage's
`**Status: DONE — implemented and verified 2026-07-29.** pytest: 41 passed…`
carries nothing the checkboxes do not. Replace with a single
`**Status.** done` / `in progress — <what is left>` / `not started`.
No dates, no test counts, no "green".

**T2 — Findings.** `**Finding:** <a bug found and fixed>` → **delete**. The
one exception: a finding describing a **live constraint a future developer
would otherwise re-break** survives as one line under `**Known limits.**`.
The test: does it describe the *current state of the code* (keep, compressed)
or *the journey to it* (delete)? Roughly 6 of the 33 survive — e.g. `UT-B1-9`'s
axis-aligned-bbox hit-test over-approximation, `UT-B1-8`'s
`num_of_used_objects` being unpopulated on disk.

**T3 — Deltas and supersessions.** `**Superseded 2026-08-07 (AR-52):** X moved
from A to B because…` → fold the **result** into the checkbox text and drop the
journey. The checkbox describes what is true now.

**T4 — Linkage.** Prose dependency narration → a compact field on the stage
header line: `Links: S-C2, S-B1`. **Case by case** — only where the dependency
is real and *not* implied by stage ordering. A stage that simply follows the one
before it gets no Links field.

**T5 — Dates.** Delete every `2026-xx-xx`. Target: **zero** date lines per
document except one `Status: frozen <date>` in each header. (Today: 350 in the
plan, 140 in the register, 77 in the ledger.)

**T6 — Rationale.** Keep the conclusion plus a one-clause reason. Delete the
multi-paragraph argument-with-rejected-alternatives — **except** in
`sim_architecture.md` §5, which *is* the rationale document, and in
`.claude/rules/sim.md`, which is out of scope and untouched.

**T7 — Restated rule text.** Several docs quote `R-SIM-n` at length. The rules
file is normative and lives elsewhere; docs **cite**, they do not restate.
Replace a restatement with `(R-SIM-14)`.

**T8 — Resolved open points.** An `## Open points` section listing questions
that a later `OD-` answered: delete the resolved entries, keep genuinely open
ones, and where the answer is load-bearing add one line to the section that now
owns it.

---

## 5. Per-file plan

### 5.1 `sim_learn.md` — 726 → ~780 *(the alignment target)*

The only document that **grows**. It is the door, and it currently stops short
of the two questions a new reader asks next: *how do I run it* and *what do I
configure*.

| § | Now | Action |
|---|---|---|
| 0 | One analogy | **Keep**, unchanged |
| 1 | The problem, before any design | **Keep**, trim ~15 lines |
| 2 | "The five ideas" — actually **seven** | **Keep all seven**, fix the heading to say seven. These are the conceptual core |
| 3 | The walkthrough, phase by phase | **Cut hard, 165 → ~55.** It restates the plan stage by stage and will go stale. Becomes: the 5-line phase table, the "why this order" argument (which is genuinely good and lives nowhere else), and a pointer to the plan |
| **4** | — | **NEW — "How you actually use it."** The 14 real CLI verbs grouped by intent: *look* (`view` `render` `explain` `list` `probe` `doctor`) · *produce* (`record` `run`) · *re-execute* (`resim` `check` `determinism` `batch`) · *move data* (`convert` `export`). Each one line. Then the sim/resim/replay distinction (`R-SIM-5`) restated once against the verbs, because that is where it becomes concrete |
| **5** | — | **NEW — "What you configure, and where."** The file-kind table (below). Verified against disk at execution time |
| 4→6 | The questions you will actually ask | **Keep**, trim each answer ~25% |
| 5→7 | A day in the life | **Keep** the command block. **Delete** the 25-line `--plugin-root` / `AR-55` incident paragraph — replace with one factual line: *`--plugin-root` accepts either a built library directory or a source checkout* |
| 5a→8 | Recordings we did not make | **Keep** — this is the sharpest section in the set. Trim the closing status paragraph to one line |
| 6→9 | Where to go next | **Keep**, minus the audit-log row |

**The §5 file-kind table** — the deliverable that shows whether I understood the
system. Columns: *File · Lives in · Owned by · Decides · Rule*. Rows:

| File | Decides |
|---|---|
| `projects/<p>/default.yaml` | calibration — every physical number (`R-VAR-4`, `R-SIM-3`) |
| `shared_config` `vehicle/ego_params.yaml` | the ego body; agreement across components is a **hard error** (`R-SIM-3a`) |
| `<library_dir>/config/` + `bundle.sha256` | the packed bundle a build emits — **read, never edited** (`R-SIM-3a`) |
| `modules/<n>/conf/build.yml` | project × target × platform, `ENABLED_FUNCTIONS` (`R-VAR-3`) |
| `modules/<n>/conf/ports.yaml` | the port declaration the ABI shim is generated from (`R-SIM-22`) |
| `<n>_sil.ports.yaml` | **generated** mirror — a dump of what compiled, never hand-edited |
| `modules/<n>/sim/plugin.yaml` | plug-in generation + bundle hash; read *before* import (`R-SIM-20`) |
| `modules/<n>/sim/pipelines/*.yaml` | the wiring: per stage `mode:` and `impl:`, overrides, `record:` policy (`R-SIM-10`, `R-SIM-15`) |
| `modules/<n>/sim/viewpoints.yaml` | named camera viewpoints |
| `modules/<n>/sim/workspace.yaml` | the component's default panel arrangement (`FR-SIM-15`) |
| `modules/<n>/sim/tolerance.yaml` | determinism tolerance, `default: exact`, every row needs a `why:` (`R-SIM-24`) |
| `modules/<n>/sim/ingest/*.yaml` | which topic in a foreign recording satisfies which port (`R-SIM-23`) |
| `modules/<n>/sim/sensor_models/*.yaml` | sensor **error** models — noise, latency, dropout (`R-SIM-9`) |
| `modules/<n>/tests/*_scenarios/**/*.yaml` | the scenario and its `expect:` block (`R-SIM-8`) |

Plus a short **"the other inputs"** block: the **DLL** (`<n>_sil.dll` — carries
its own manifest and `FileDescriptorSet`, which is why no generated bindings are
needed, `R-SIM-11`); **`.mcap`** (the recording, read+write); **`.jsonl`**
(read+write); **CSV** (**write-only export** — lossy, terminal, never a resim
input, `R-SIM-14`); **Foxglove `SceneUpdate`** (export).

### 5.2 `sim_requirements.md` — 2,254 → ~950

- **§0** How this register works — keep the field table and the priority
  paragraph. Trim ~10 lines.
- **§0a** *What this register does not say* — **the biggest single cut in this
  file, 105 → ~12 lines.** It currently holds two dated measurement tables
  (2026-08-04 and 2026-08-06), a superseded-reading warning, an `AR-34` caveat
  box and three per-row findings. All are logs of audit runs.
  What survives, as plain fact with no dates:
  - `Status` is about the **decision**, never the code — there is no `built`
    value, and this register cannot answer "what is left".
  - `python docs/py/check_requirement_coverage.py` derives that answer from the
    plan's own ticks and **is** the authority on it.
  - It scores only `UT-`/`ST-` ids; a row resting on `MC-`/`GT-`/`DC-` reads
    `proven` on its code verifiers alone. **This caveat is still true and must
    survive** — it is the one statement in §0a that is not a log.
- **The 80 rows** — mechanical, applied to every row:
  - `**Origin.**` keep the verbatim quote, **drop the date prefix** (decision 1)
  - `**Answered by.**` / `**Verified by.**` / `**Status.**` / `**Priority.**` —
    **untouched**, they are parsed
  - editorial paragraphs inside a row → one clause. Example: `FR-SIM-16`'s
    "Not an event callback, which would put UI state inside the one thing that
    must have none" is a keeper as a clause; the surrounding 6 lines are not.
  - Any `*Limitation stated: …*` italic → **keep**, it is live fact.

### 5.3 `sim_architecture.md` — 2,841 → ~1,500

- **§0–§2** keep, light trim.
- **§3 The scalability defects, D1–D14** — 306 → ~40. Each defect is now
  history: it describes what was wrong with tooling that Phase E deletes. But
  stages cite them (*"closes D3"*), so the IDs must resolve. → **one table**:
  `ID · the defect in one line · closed by`.
- **§4 Design principles** keep.
- **§5.1–§5.19** — the design proper, and **the one place T6 does not apply**.
  Trim redundancy and restated rule text (T7), keep the arguments. ~1,600 → ~950.
  Notably: §5.8's placement map stays exactly as-is (DC-5 parses it).
- **§6 How each defect closes** — merge into §3's table's third column, delete
  the section. §6.4 (two-pass Session) is real design → **move into §5** as
  §5.20 rather than deleted.
- **§7 Scaling to perception** keep.
- **§8 Staged roadmap** — duplicates the plan's phase structure. Cut to a
  5-line table pointing at the plan.
- **§10 Decisions OD-1…OD-13** — ~100 → ~20. One table:
  `ID · question · decision`. The reasoning behind each is in §5 already.
- **§11 What is deliberately not designed** keep — a scope boundary is content.
- **`OQ-1`…`OQ-15`** scattered through the file: resolved ones
  (`OQ-1`/`2`/`3`/`4`/`10`/`11`/`12` at least — verified at execution time)
  fold into the OD table as `answered by`; genuinely open ones stay. **Each
  deletion listed in the progress log**, per §3.3.

### 5.4 `sim_implementation_plan.md` — 8,964 → ~2,400 *(the main event)*

- **§0 How to use this document** — keep, 18 lines.
- **§0a ▶ START HERE** — **999 → ~70 lines.** Currently the largest single
  block of dated narrative in the set: audit boxes, "what the real build found",
  per-block landing notes, environment misdirection notes. Becomes:
  1. Where the work stands, in 3 lines.
  2. The **build-order queue table** (this is the genuinely valuable part and it
     survives intact) — id · what · state.
  3. The four id-order deviations, as 4 lines.
  Everything dated goes.
- **§1 Prerequisites** keep (~27 lines).
- **§2 Global gates GT-1…GT-14** — 316 → ~90. Keep every gate, keep its
  checkbox where one exists. Cut the rationale paragraphs to one line each.
  **Note a real defect to fix while here:** `GT-3`, `GT-8`, `GT-9`, `GT-10`,
  `GT-11`, `GT-13`, `GT-14` and `DC-1/4/5/6` have **no checkbox anywhere**, so
  their state is unrepresentable and `check_requirement_coverage` reports `?`.
  Give each one a checkbox in this section — it costs one line and closes the
  gap the register's own §0a caveat complains about.
- **§3 Test strategy** — 63 → ~25.
- **§4–§8 the 33 stages** — **6,900 → ~1,700.** The per-stage template:

  ```markdown
  ### S-A2 — `model/` — configuration is the source of geometry

  **Status.** done · implements `R-SIM-3` · closes `D3`

  **Purpose.** Every number describing the physical world comes from resolved
  YAML, never a module constant.

  **Must not.** Contain a literal vehicle or sensor dimension (`GT-3`); know
  the name of any driving function — sensor keys parse by key shape (`GT-1`).

  - [x] `model/project.py` — `ProjectModel.resolve()`; order explicit →
        embedded → library `config/` → checkout, `bundle_origin` states which
  - [x] `model/ego.py` — `EgoModel`, frame per `R-COORD-1`
  …
  **Known limits.** `ProjectModel.footprint/.sensor/.camera` not implemented —
  no generic cross-component calibration source exists yet (`R-SIM-9`).

  **Tests**
  - [x] `UT-A2-1` `EgoModel.load("base")` → `x_front 3.60`, `x_rear -0.90`,
        `half_width 0.90` (approx — exact `==` would be flaky)
  …
  **Gate**
  - [x] `ST-A2-1` green for all three projects; `UT-A2-9` green
  ```

  Rules applied: T1 status, T2 findings (≈6 of 33 survive as `Known limits.`),
  T3 deltas folded into checkbox text, T4 links only where non-obvious.
  **The `**Discipline**` block** (portability §3 / naming §3 / `run_all.py`
  ticked — present in every stage, ~6 lines each, ~200 lines total) collapses
  to a single line per stage, since it is the same three items every time.
- **§9 Traceability** — keep; it is a table and it is the map.
- **§9a Audit findings** — rewrite to ~5 lines: the ledger was retired at the
  freeze; findings from any future audit become checkboxes in the owning stage.
- **§10 Risks** — keep, trim.

### 5.5 `sim_sil_contract.md` — 1,155 → ~700

Keep §0 (written for a newcomer, and good), §1–§4, §7, §8, §10. Cut: **§5**
(`OD-2` — a decision already made and recorded in arch §10; 30 → 3 lines),
**§6 Migration** (a phase-E concern the plan owns; 22 → 5), **§9 Open points**
per T8. Apply T7 throughout — this file restates `R-SIM-4`/`R-SIM-22` at length.

### 5.6 `sim_resim_and_recording.md` — 1,007 → ~650

Keep §1–§7. Cut: **§8 Migration of existing recordings** (45 → ~12, it is a
one-time task the plan tracks), **§10 Open points** per T8. Strip the dated
parenthetical inside the `tolerance.yaml` code fence (§4) — the *schema* is the
content, "corrected 2026-08-06, sim build queue row 2" is not.

### 5.7 `sim_visualization_spec.md` — 910 → ~650

**§16 feature checklist is untouchable** (DC-4 parses every row and each must
name a stage) — and it is also the answer to `FR-SIM-11`, so it is content.
Cut §17 open points per T8; trim rationale under §2/§3/§7 per T6.

### 5.8 The four small specs

- **`sim_api_reference.md`** (805 → ~750): lightest touch in the set — a
  signature there is a contract. Strip the 3 date lines and §11's editorializing.
  **§10's CLI table must keep exactly the 14 verbs** `cli/__init__.py` registers
  (DC-9).
- **`sim_scenarios_and_expectations.md`** (678 → ~450): cut §7 *Migrating the 18
  scenarios* to a pointer (it is a task, not a design), §9/§9.1/§9.2 open points
  per T8 — `OQ-3` and `OQ-4` are answered and their answers belong in §5 and §4
  respectively.
- **`sim_naming_and_diagnostics.md`** (440 → ~330): keep all `N-1..N-13` and
  `DG-1..DG-5` and §3's per-stage checklist. Trim the rationale under each rule
  to one line.
- **`sim_portability.md`** (291 → ~230): keep `P-1..P-10` and §3's checklist.
  **§4a** *Reconciled against real measurement — 2026-08-06 (AR-49)* → fold its
  factual findings into §2's rules and §4's bring-up list, delete the section.

### 5.9 Outside `docs/`

- **`modules/sim/README.md`** — refresh the document table (drop the audit-log
  row), point newcomers at `sim_learn.md` first.
- **`modules/sim/CLAUDE.md`** — rewrite the audit paragraph (§3.2); confirm the
  routing it describes still matches the restructured set.
- **`modules/sim/.claude/prompts/sim_audit.md`** — update the ledger contract:
  findings land as checkboxes in the owning stage, no ledger file.
- **root `plan.md` item 25** — replace the dated status cell with a one-line
  pointer at `sim_implementation_plan.md` §0a. Also fixes the two dead
  audit-log links (lines 834, 1542).
- **`docs/py/`** — delete `check_audit_ledger.py` and its `run_all.py` entry.
  Keep the other five checks and both frozen surveys unchanged. Fold `AR-22`'s
  standing note (`reference_tool_path.txt` is `.gitignore`d by design, do not
  re-flag) into `docs/py/README.md` as one line, and `AR-21`'s
  (`.gitmodules` declares `submodule "modules/sil"` at path `modules/sil_host`,
  cosmetic, deliberately not renamed) into root `plan.md` — both exist purely to
  stop a future audit re-raising them, which is a real service worth 2 lines.

---

## 6. Execution order and verification

Ordered so that the riskiest structural change happens while the checks are
still cheap to re-run, and so that no step depends on a later one.

| # | Step | Verify |
|---|---|---|
| 1 | Delete `sim_audit_log.md` + `check_audit_ledger.py` + `run_all.py` entry; fix all 6 inbound links | `check_doc_invariants` (DC-1) |
| 2 | `sim_implementation_plan.md` §0a, §2, §3 | traceability + requirement coverage |
| 3 | `sim_implementation_plan.md` Phase A + B stages | census; traceability |
| 4 | `sim_implementation_plan.md` Phase C stages | census; traceability |
| 5 | `sim_implementation_plan.md` Phase D + E stages, §9/§9a/§10 | all four checks |
| 6 | `sim_requirements.md` | requirement coverage; DC-8; rules coverage |
| 7 | `sim_architecture.md` | DC-5; rules coverage |
| 8 | `sim_sil_contract.md`, `sim_resim_and_recording.md`, `sim_visualization_spec.md` | DC-4; rules coverage |
| 9 | `sim_api_reference.md`, `sim_scenarios_*.md`, `sim_naming_*.md`, `sim_portability.md` | DC-9; rules coverage |
| 10 | `sim_learn.md` — restructure **and** author §4/§5 | verify every claim against disk |
| 11 | README, CLAUDE.md, audit prompt, root `plan.md` | DC-1 |
| 12 | Full pass + census diff; delete this file | all checks green |

**After every step:** the four fast checks plus the census diff. `run_all.py`
becomes usable on WSL once step 1 removes the ledger check that times out.

**`sim_learn.md` is last on purpose.** It is the alignment deliverable — the
document that shows whether the whole exercise was understood — and it should be
written against the restructured set, not against what the set used to say.

---

## 7. Progress

- [x] 1 · ledger deleted, `check_audit_ledger.py` deleted, all 6 inbound
      references fixed. **Side benefit: `run_all.py` now completes on WSL** —
      the ledger check was the script that timed out
- [x] 2 · plan §0a (999 → 159) and §2 global gates (316 → 183); §3 left as-is,
      it was already lean. Every `GT-`/`DC-` cited by a requirement now has a
      checkbox, closing the "unrepresentable state" gap the register complained
      about
- [x] 3–5 · plan stages, **mechanical pass only** (see *Remaining* below):
      per-item journey narrative truncated, Status blocks dropped, Discipline
      blocks collapsed to one line, journey paragraphs removed. §9a rewritten
- [ ] 6 · requirements register
- [ ] 7 · architecture
- [ ] 8 · sil contract / resim / visualization
- [ ] 9 · api ref / scenarios / naming / portability
- [x] 10 · learn — §3 restructured (185 → 63) and **§4 "How you actually use
      it"** + **§5 "What you configure, and where"** authored, every claim
      verified against disk. Sections renumbered; `## 2` corrected from "five
      ideas" to seven
- [x] 11 · `README.md` (stale counts fixed: 45→80 requirements, 21→32 stages,
      `R-SIM-1..14`→`..25`), `CLAUDE.md`, `.claude/prompts/sim_audit.md`
- [ ] 11b · root `plan.md` item 25
- [ ] 12 · full verification, census diff, delete this file

### Where it stands

| Document | Start | Now | Target |
|---|---:|---:|---:|
| `sim_implementation_plan.md` | 8,964 | **5,797** | ~2,400 |
| `sim_architecture.md` | 2,841 | 2,841 | ~1,500 |
| `sim_requirements.md` | 2,254 | 2,254 | ~950 |
| `sim_learn.md` | 726 | **782** | ~780 ✓ |
| `sim_audit_log.md` | 387 | **0** ✓ | 0 |
| others (8 files) | 5,717 | 5,715 | ~3,760 |
| **Total** | **20,889** | **17,389** | **~9,690** |

**All five checks pass** after every step
(`check_doc_invariants`, `check_traceability`, `check_rules_coverage`,
`check_requirement_coverage`, `check_verifier_discoverability`).

### Remaining, precisely

**The plan's stages need a hand pass.** The mechanical pass cut 3,167 lines
safely but cannot finish the job: what is left is **2,828 lines of checkbox-body
continuation text**, where the journey is woven into the scope sentence rather
than appended as a marked `**Finding:**`. Compressing those is per-item
judgment — roughly 350 items. Start with the worst offenders by line-to-box
ratio:

| Stage | Lines | Boxes |
|---|---:|---:|
| `S-D3` | 393 | 16 |
| `S-B1` | 325 | 38 |
| `S-C5` | 294 | 33 |
| `S-D6` | 270 | 23 |
| `S-C1c` | 265 | 49 |
| `S-D8` | 239 | 28 |

Those six alone are 1,786 lines and should land near 450.

**22 `AR-n` citations survive** inside prose sentences (34 pure-attribution
parentheticals were stripped mechanically). They are now dangling — the ledger
is gone — and should be removed as each document gets its hand pass.

### Deletions log

Per §3.3 — every ID removed, with the reason. Verified by census diff
(`census_before` vs `census_after`): **`UT-`, `ST-`, `GT-`, `MC-`, `FR/NR/CR-`,
`R-SIM-`, `N-`, `DG-`, `P-`, `D`, `OD-`, `OQ-` are all fully preserved.**

| ID(s) | Where | Why |
|---|---|---|
| `AR-1`…`AR-61` (30 of 61 so far) | `sim_audit_log.md` | the ledger was deleted; all 61 rows were closed or won't-fix, so nothing open was lost. 22 citations still to remove |
| `DC-7` | plan prose | never cited by a requirement; still defined in `check_doc_invariants.py`, which is where `check_traceability.py` harvests it. **Not a loss** |
| `S-C1` | plan prose | never a stage — an artefact of the `S-C1a`/`b`/`c`/`d` prefix matching the census regex. **Not a loss** |

Two won't-fix notes worth re-homing before this file is deleted (§5.9): the
`reference_tool_path.txt` `.gitignore` rationale → `docs/py/README.md`, and the
`.gitmodules` `submodule "modules/sil"` / `path = modules/sil_host` mismatch →
root `plan.md`. Both exist only to stop a future audit re-raising them.
