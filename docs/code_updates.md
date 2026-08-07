# Code comment cleanup — the plan

**Scaffolding**, like `doc_updates.md`. It plans a one-off pass over the
comments and docstrings in the code, tracks progress, and is **deleted when the
last box is ticked**. It changes no behaviour: **not one line of code is
edited** — only comments, docstrings and the prose inside them.

---

## 1. What is actually wrong

The comments carry the same defect the documents did: they record the
**journey** rather than the **state**. A constant's comment explains which audit
raised it; a function's docstring recounts what the first draft got wrong; a
module's docstring restates three paragraphs of design rationale that
`sim_architecture.md` already owns.

Measured:

| Area | Files | Lines | Comment + docstring | Ratio |
|---|---:|---:|---:|---:|
| `src/adas_sim/` | 115 | 20,295 | **6,427** | **31.7%** |
| `tests/` | 160 | 22,691 | 4,427 | 19.5% |
| `scripts/` | 5 | 1,303 | 333 | 25.6% |

Worst offenders by ratio: `model/project.py` **50.0%**,
`sources/carla/actor_behaviour.py` 47.9%, `scene/types.py` 41.7%,
`render/foxglove.py` 41.2%, `core/manifest.py` 37.8%, `core/runner.py` 37.3%.

A 30% comment ratio is not wrong by itself — this is a framework whose whole
value is its boundaries, and those need explaining. What is wrong is **which
30%**. Target: **~15% in `src/`**, achieved by deleting archaeology, not by
deleting explanation.

### One real defect this pass fixes, not just tidying

**Sixteen `cli/*.py` module docstrings are passed to `argparse` as
`description=__doc__`** — they are the text a user sees on `sim probe --help`.
Today `cli/probe.py`'s is a 20-line internal design essay citing `GT-9`,
`S-C9`, `S-D6`, `sim_architecture.md` §5.16.1 and `R-SIM-23`. That is not help
text; it is a design note in the user's face. These get rewritten **for the
user**, and the design rationale is deleted (it is already in the docs).

---

## 2. Invariants — what must not break

**A comment is not always inert here.** Four mechanisms read comment text or
depend on it:

| Mechanism | Constraint |
|---|---|
| `scripts/check_invariants.py` → **`GT-1`** | no `aeb`/`bsd`/`lca`/`acc`/`ldw`/`lka` anywhere under `modules/sim/src` — **comments included**. Never introduce one while paraphrasing |
| `scripts/check_invariants.py` → **`UT-D8-9`** | no `Vantage`/`Bench`/`Campaign` token in `adas_sim/` **outside `app/`** — comments included |
| `docs/py/check_verifier_discoverability.py` | every **ticked** `UT-`/`ST-` id in the plan must appear in some source file. Test docstrings are where most of them live. **Never delete a test id.** Baseline: 0 undiscoverable |
| `argparse description=__doc__` | 16 `cli/*.py` module docstrings + `scripts/vantage.py` + `scripts/ci_gate.py` are user-facing help |

Plus:

- **File header blocks stay** — `Copyright / Proprietary / COMPONENT: / @author`
  (`R-STYLE-1`, `R-NAME-6`). Never touched.
- **`#:` prefixes stay `#:`** where they are Sphinx-style attribute docs.
- **No code, no string literal, no import is edited.** If a change would alter
  behaviour, it is out of scope by definition.
- **Baseline to hold: `1032 passed, 10 skipped`**
  (`.venv/Scripts/python.exe -m pytest tests -q`, 126s).

---

## 3. Editing rules

**C1 — Module docstring: 1–5 lines.** What this module is, and the rule or spec
section it implements, as a citation. Delete the restated rationale — the rule
file and the design docs own it, and a copy drifts.

```python
# before (28 lines)
"""`ProjectModel.resolve(...)` -- configuration is the source of geometry
(R-SIM-3, sim_api_reference.md §6). Resolution order **explicit -> ...
**Deferred, deliberately:** `ProjectModel.footprint()`/`.sensor()`/ ... [20 more lines]
"""

# after
"""Configuration is the source of geometry (`R-SIM-3`, api reference §6).

`ProjectModel.resolve()` searches explicit -> embedded-in-recording ->
library `config/` -> source checkout, and `bundle_origin` always reports
which. The failure that prevents: the viewer and the SUT reading different
files and agreeing only by coincidence.

`footprint()`/`sensor()`/`camera()` are deliberately not implemented -- real
sensor poses and class footprints are the consuming component's calibration
(`R-SIM-9`), so there is no generic source to bind them to yet.
"""
```

**C2 — `cli/*.py` docstrings are help text.** Rewrite for the user: what the
verb does, what it takes, what it prints. 2–4 lines. Any `GT-`/`S-`/doc citation
that must survive moves to a `#` comment below the docstring, where the user
never sees it.

**C3 — `#:` constant comments: one line.** What the constant is, or the
non-obvious reason it exists. Delete plan archaeology ("recorded as a finding in
S-A2", "AR-51").

**C4 — Function and class docstrings.** Keep: what it does, non-obvious
arguments and returns, and **the invariant it protects**. Delete: what an
earlier draft did wrong, which review found it, what was considered and
rejected.

**C5 — Inline comments.** Keep every comment that says *why*. Delete the ones
that restate the code, and the ones that narrate history.

**C6 — IDs.** Keep `R-SIM-n`, `R-*`, `FR/NR/CR-SIM-n`, `S-*`, `UT-`/`ST-`,
`GT-`, `N-`, `DG-`, `P-`, `D*`, `OD-` and doc-section references — as **compact
parenthetical citations**, never as a sentence about the citation. Delete every
`AR-n` (the ledger is gone) and every date.

**C7 — Test files.** The module docstring keeps its **full id list** — that is
what `check_verifier_discoverability` reads — but loses the commentary between
ids. A per-test docstring becomes one line stating the claim the test makes.

```python
# before
"""S-C1c pipeline tests: UT-C1c-6, UT-C1c-7, ... UT-C1c-14, UT-C1c-16,
UT-C1c-17 (the pipeline-wiring half; `override.py`'s own semantics are
`test_c1c_override.py`'s), UT-C1c-18, ... ST-C1c-2 (docs/sim_implementation_plan.md).

Every fixture here is a synthetic, invented component ("producer", ...
"""
# after -- every id preserved, commentary compressed
"""`S-C1c` pipeline wiring: `UT-C1c-6`..`UT-C1c-14`, `UT-C1c-16`..`UT-C1c-21`,
`ST-C1c-2`. Override semantics are `test_c1c_override.py`'s.

Fixtures are synthetic components driven through `InProcessSilComponent` --
no DLL, no `interfaces` checkout, no real function name (`R-SIM-1`).
"""
```

**C8 — When in doubt, keep it.** The cost of a surviving good comment is one
line; the cost of deleting the sentence that explains a non-obvious boundary is
a future rewrite of working code.

---

## 4. Scope and order

Ordered by value per edit: the code a developer reads most, first.

| # | Batch | Files | Why here |
|---|---|---:|---|
| 1 | `cli/*.py` | 16 | the only comments a **user** sees; a real defect, not tidying |
| 2 | `model/`, `scene/`, `core/` | ~25 | the vocabulary every other module imports |
| 3 | `contracts/`, `io/` | ~15 | the boundaries — highest genuine explanation need, so edit carefully |
| 4 | `render/`, `view/`, `check/`, `sources/` | ~30 | `viewer.py` alone is 653 comment lines |
| 5 | `app/`, `scripts/` | ~15 | `app/` is the one place workspace names are legal |
| 6 | `tests/` | 160 | mechanical (C7), but the id lists make it the riskiest to automate |
| 7 | `modules/df/sim/**` | 4 | component-side plug-ins |
| 8 | C++ `*_sil/` in `df`, `vdy`, `perception-core` | 17 | same rules; `@file`/`@brief` headers stay |

**After every batch:** `check_invariants.py`, then `pytest tests -q` must still
read `1032 passed, 10 skipped`. After batches touching tests: also
`check_verifier_discoverability.py`.

---

## 5. Progress

- [x] 1 · `cli/` — **all 14 verb docstrings rewritten as user help text**
      (7,100 → 4,400 chars) **and 12 overlong `help=` strings rewritten.**
      Four of those carried a **stale factual claim** — *"adasInit(NULL)'s own
      bundle resolution is S-C5, not yet built"* — printed to users long after
      `S-C5` landed. Verified by rendering `--help` for each verb
- [~] 2 · `model/`, `scene/`, `core/` — **partly done.** 14 module docstrings
      and 5 large function docstrings rewritten (`project`, `batch_worker`,
      `diagnostics`, `evidence`, `tick`, `manifest`, `resim`, `batch`,
      `default_layers`, `registry`, `codec`, `signals`, `explain`,
      `determinism`, `plugins`; `build_manifest`, `verify_pinned_builds`,
      `_resolve_prim`, `layer_provider`, `build_scene`). **25 dangling `AR-n`
      and date attributions stripped** across 14 files. ~37 large docstrings
      still to do — the list is `docs/py`-free, regenerate it with the
      >420-char scan in §4
- [ ] 3 · `contracts/`, `io/`
- [ ] 4 · `render/`, `view/`, `check/`, `sources/`
- [ ] 5 · `app/`, `scripts/`
- [ ] 6 · `tests/`
- [ ] 7 · `modules/df/sim/**`
- [ ] 8 · C++ `*_sil/`
- [ ] 9 · final verification; delete this file

### Measured

| Checkpoint | pytest | invariants | `src/` ratio |
|---|---|---|---|
| baseline | 1032 passed, 10 skipped | clean | 31.7% |
| after batch 1 | 1031 passed, 10 skipped, **1 known flake** | clean | — |
| after batch 2 (partial) | **1032 passed, 10 skipped** — unit 765/2, system 88/8 + 179 | clean | **30.8%** |

Run in three parts (unit · system-non-GUI · system-GUI) rather than one
invocation: **765 + 88 + 179 = 1032 passed, 2 + 8 = 10 skipped — exactly the
baseline**, and the `test_b3_viewport_controls` flake does not appear, because
splitting the run breaks the fixture-ordering that provokes it. That is a
cheaper workaround than the full-suite invocation, and it is worth knowing while
`ST-E3-5` still owns fixing the flake properly.

The ratio has barely moved because ~37 of the 62 large docstrings are still to
do; the ones done were the ones a reader hits first.

### The safety net: `prove_comments_only`

Every edit is verified by parsing the file before and after, **stripping all
docstrings, and comparing the ASTs**. Comments never reach the AST at all, so
they are invisible to the comparison by construction; docstrings are removed
before it. Matching dumps prove **no statement, expression, literal or import
changed**. Current state: **41 files provably comment/docstring-only, 0 with
code changes**, measured against a snapshot taken after the CLI help-text work.

The script lives in the job scratch dir. It is worth keeping for any future
comment pass; it is not committed, because after this exercise there is nothing
for it to guard.

### Two corrections made mid-pass, both worth remembering

**1. IDs were being silently dropped.** An audit of every id family across the
edited files found 12 `R-SIM-`, 15 `GT-`, 13 `UT-`/`ST-`, 3 `DG-` and 4 `OD-`
citations gone. Most were in `cli/`, removed *deliberately* when the help text
was rewritten for users — but §3's rule C2 says they should have been re-homed
as `#` comments, and that step was skipped. Fixed: every `cli/` module now
carries a `# Design refs:` line under its docstring, so help text stays clean
**and** the ids stay greppable. The genuine over-compressions in `core/` and
`model/` had their citations restored inline.

**Net result: 298 → 305 distinct id citations across edited files — zero lost.**
`S-` *stage-history* citations ("seeded at S-A1", "S-B2Δ changed…") are the one
family deliberately reduced: they record when something was built, which is the
archaeology this pass exists to remove.

**2. A regex nearly ate `R-VAR-n`.** The attribution-stripping pattern matched
`AR-\d+`, and `R-VAR-2` *contains* `AR-2`. The anchoring saved it, but the check
that caught the one real loss was counting ids per family before and after —
not reading the diff. **Count ids mechanically after any bulk edit;** a regex
over identifier text is never obviously safe.

**The one failure is the documented flake**, not a regression:
`test_b3_viewport_controls.py::test_dragging_pans_the_viewport_and_a_second_click_still_selects`
— a fixture-isolation bug in the plan's §10 risk table. Confirmed **8 passed in
isolation**, and batch 1 touched only `cli/`, which that test does not import.

### A lesson worth keeping

The first attempt at the `help=` rewrite replaced whole **line ranges** and
dropped the `help=` keyword, breaking six files at once. Syntax was caught
immediately, but the real fix was replacing the string **by column offset**
(`col_offset`/`end_col_offset`) so an inline `help=` sharing its line with other
arguments survives. **Any scripted edit of Python source must be
column-precise, never line-precise** — the same discipline the docs pass used
for checkbox prefixes.
