# Step 7 — Document Set Shrink Plan

**Status: PROPOSAL. Nothing in this file has been executed.** No file named
below has been deleted, moved, or edited by this pass. Written 2026-08-31,
after Movements A–C settled and the freeze ended by its own terms
(`START_HERE.md`).

## 0. Why this exists, and the rule it follows

`memory.md` §4 and §7 name the last untreated root cause: **41,341 lines /
3.3 MB** of specification (sim v1 + sim v2 + viz) for a concept an external
reference tool expresses in **three INI files, about 5 KB**. The v2 concept
document lists this as its own risk (`CN-0375`, §29, High): *"the document set
outgrows the product it describes."* It is traced to a real requirement,
`SYS-0265` ("survivable by someone who did not build it... the set's own size
shall be tracked"), verified by a not-yet-built `WP-31` item
(`scripts/measure_docs.py`, `IMP-0380`). Open question #21 in the concept
document is still live: *"how large should the derived document set be?"*
This plan answers that question with a number (§2) and a route to it (§3–§6).

**Scope.** This plan covers `modules/sim/docs/v1/`, `modules/sim/docs/v2/`,
and `modules/sim/misc/`'s tracked `.md` files — **1.1 M / 17,681 lines**,
**2.0 M / 18,213 lines**, and **~65 KB / 1,680 lines** respectively (measured
2026-08-31; `misc/mts_bench/` is a 7.2 MB gitignored local reference-tool
checkout, untracked, out of scope — it is not part of the spec).
`modules/viz/docs/` is a separate module's document set with its own owner
and is **not** planned here, though §7 names the two places this module's own
retirement touches it. The root `.claude/` rule/skill layer (61 files,
`rules/sim.md` alone 42 KB) is also out of scope — a cross-cutting
initiative, not a sim-module one; named, not planned.

**Method.** Every candidate below was checked three ways before a
disposition was assigned, because the last plan written from line counts and
directory listings called live code dead (`memory.md` §3): **(a)** `git log`
on the file, to see whether it is still being edited or only accreted;
**(b)** a repo-wide grep for every path string that names it, across `.md`,
`.py`, `.cpp`, `.hpp`, `.h`, `.cmake`, `.yaml`, `.yml`, with no extension
excluded a second time after the first pass changed the picture (see §4);
**(c)** for anything with an ID scheme (`FR-`/`NR-`/`CR-SIM-n`), a grep of
every v2 `Trace` field for that scheme, because `R-REQ-2` makes a retired
requirement's disposition mandatory, not optional, wherever a live trace
link would otherwise dangle.

## 1. What is genuinely good, and where it lives after this plan

`memory.md` §8 names ten ideas as the real output of two months and says not
to lose them. None of the ten live only in v1 prose — each is already
codified twice, in the root rule (permanent, untouched by this plan) and in
a v2 requirement (the live baseline, also untouched in structure by this
plan):

| # | Idea | Rule | v2 anchor |
|---|---|---|---|
| 1 | Two independent per-module switches, same port set either way | `R-SIM-10` | `SYS-0`-series staging reqs |
| 2 | Incoherence detection before the run, transitive, waivers stamped | `R-SIM-10` | coherence reqs, §11.2 concept |
| 3 | Geometry/pixels strictly separated | `R-SIM-2` | layer-provider reqs |
| 4 | Named, discovered ports | `R-SIM-4`, `R-SIM-21` | port-model reqs |
| 5 | A recording is a model; a format is a codec | `R-SIM-14` | `io/` reqs |
| 6 | Record inputs and outputs | `R-SIM-6` | recording reqs |
| 7 | Two clocks per message, never collapsed | `R-SIM-14` | `SYS-0114`/`SYS-0123`-area |
| 8 | Every drawn value traceable, one producer two formatters | `R-SIM-25` | `SYS-0`-series evidence reqs |
| 9 | `unknown` printed, never a plausible default | `R-SIM-25`, `NR-SIM-4` | evidence reqs |
| 10 | Closed override lists, written reasons | `R-SIM-15` | override reqs |

This is why the plan below can be aggressive with v1: retiring it does not
touch any of these ten. It only removes the *record of how they were
arrived at*, which git history keeps.

## 2. The target

**Land the tracked set at ~4,000–4,500 lines / ~700–800 KB — roughly an 88%
cut from today's 35,894 lines / 3.1 MB (v1+v2+misc).** Not "smaller":

- `docs/v1/` (17,681 lines / 1.1 MB) → **~950 lines / ~90 KB** (§3–§5).
- `docs/v2/` (18,213 lines / 2.0 MB) → **structure unchanged** (every `Shall`/
  `Accept`/`Verify`/`Trace` row stays — `R-REQ-3` fixes that anatomy and nothing
  here proposes touching it); only `SIM_Implementation_Plan_v0.1.md`'s
  narrative bloat is cut (§6), for an estimated **~2,500-line reduction on
  that one file's byte size**, not its structure.
- `misc/` (1,680 lines) → **~1,350 lines** once `MOVEMENT_B_PLAN.md` closes
  (§7); everything else in `misc/` is current and stays.

**Why this number and not smaller.** `SYS-0265`'s own `Accept` clause does
not name a byte budget — it asks that a new maintainer become productive
without reading all of it, and that size be *tracked*, not minimized to a
constant. 4,000–4,500 lines is derived, not guessed: it is what remains
after (a) every v1 document with no live external reader is reduced to a
disposition stub, (b) the two documents with real external readers
(`sim_visualization_spec.md`, `sim_player.md`) are reduced to exactly their
cited fragments, (c) the one document under `R-REQ-2` (`sim_requirements.md`)
is reduced to a compact ID→disposition register instead of 77 full essays,
and (d) v2's requirement bodies — the actual governed product spec — are
left alone in shape. It is not "smaller than the reference's 5 KB," because
that comparison was never the point (`memory.md` §7 says so explicitly): the
5 KB is proof a small concept can be described small, not a target to hit
for a document set that also carries 1,437 requirements' worth of
traceability the reference tool does not have.

## 3. `docs/v1/` — file by file, with what was checked and what is lost

| File | Lines / KB | External readers found (§0 method b) | `R-REQ-2` exposure (method c) | Disposition |
|---|---|---|---|---|
| `sim_implementation_plan.md` | 5,902 / 197 KB | none outside sim's own `rules/sim.md` index, `CLAUDE.md`, and `SIM_Implementation_Plan_v0.1.md`'s own self-reference (§0.1's forward pointer) | none — no `S-A1`…`S-E3` stage ID appears in any v2 `Trace` field | **Retire → stub.** Already explicitly dispositioned "not the build order" three times over (root `CLAUDE.md`, `rules/sim.md`, `START_HERE.md`). Biggest single file in the set. |
| `sim_architecture.md` | 2,841 / 167 KB (largest byte size) | `rules/sim.md` (`R-SIM-1`'s "Full map: …§5.8"), `modules/sim/CLAUDE.md` | none | **Retire → stub**, *and* drop the dangling "Full map: §5.8" pointer from `R-SIM-1` — checked: §5.8 ("Placement map") is a longer, dated restatement of the same decision rule `R-SIM-1`'s own body already carries verbatim ("Placement, in order: cross-cutting knowledge…"). The rule does not need the pointer to remain self-contained. |
| `sim_requirements.md` | 2,256 / 149 KB | `rules/sim.md`, `CLAUDE.md` | **49 distinct `FR-`/`NR-`/`CR-SIM-n` IDs are cited by name in live v2 `Trace` fields** (e.g. `SYS-0265`'s own Trace reads "`CN-0371, CN-0375; v1 NR-SIM-45`") | **Supersede, not delete — §4.** Deleting the file would leave 49 real, currently-resolvable trace links pointing at nothing, which `R-REQ-2` names as exactly the failure mode to avoid. |
| `sim_sil_contract.md` | 1,155 / — | none | none | **Retire → stub.** |
| `sim_resim_and_recording.md` | 1,008 / — | none | none | **Retire → stub.** |
| `sim_api_reference.md` | 990 / — | `rules/sim.md` only ("a signature there is a contract") | none | **Retire → stub**, and check `rules/sim.md`'s claim against the current build: if any symbol it names for "an implementation must produce" is no longer produced that way, that is a real, separate finding to raise before retiring — not assumed clean by this plan. |
| `sim_visualization_spec.md` | 909 / 48 KB | **`df_viz_Raw_Requirements_v0.1.md`, `df_viz_System_Requirements_v0.1.md`** ("the prim/style/theme catalogue §12 cites rather than redefines"), **`df_viz_Concept_Document_v0.0.1.md`** | none | **Extract, then retire the rest — §5.** Only §2 (Scene primitive catalogue) and §3 (style tokens/themes), ~130 of 909 lines, are what `df` actually cites. |
| `sim_learn.md` | 782 / — | none | none | **Retire → stub.** Narrative/tutorial framing, superseded in practice by a working demo (`RUN_THE_DEMO.md`) a reader can now run instead of read about. |
| `sim_scenarios_and_expectations.md` | 678 / — | none | none | **Retire → stub.** |
| `sim_naming_and_diagnostics.md` | 440 / 20 KB | **`docs/v2/errors.yaml`** (a live, build-adjacent config file, comment: *"a new class needs a design… from `docs/v1/sim_naming_and_diagnostics.md`"*) | none | **Keep, lightly trim.** Checked structurally: `N-1`…`N-13` (the cited naming rules) spans lines 35–296 — **260 of the file's 440 lines already are the cited content.** Only §2 (`DG-1`…`DG-5` diagnostics, ~35 lines), §3 (per-stage checklist) and §4 (traceability table) are candidates for trimming, and even those are small. Do not retire this one; there is almost nothing left to cut. |
| `sim_player.md` | 430 / 26 KB | **`modules/viz/cpp/viz/player/workspace_mode.hpp`** (a live C++ header, quoting it directly: *"A workspace is a mode of one window, not a second application" (`sim_player.md` §1)*, tied to real IDs `SW-0072`/`CN-0112`), **`VIZ_Concept_Document_v0.0.1.md`**, **`df_viz_Raw_Requirements_v0.1.md`** | none | **Extract, then retire the rest — §5.** §1 ("Names," ~45 lines) plus the "What shipped — reconciled" table (§10, ~110 lines) are the load-bearing parts; the middle (Bench/Campaign UI detail, keymap, feature checklist) is retireable. |
| `sim_portability.md` | 290 / — | `rules/sim.md`, already marked *"superseded, evidence only"* there, replacement already named (`SYS-0247`..`SYS-0251`) | none | **Already correctly dispositioned.** This is the model the rest of the table follows — the citing rule already names the successor. Nothing to do beyond folding it into the same stub pattern for consistency. |

**What is lost, stated plainly.** Full prose — the "why we chose X over Y"
narrative, the abandoned alternatives, the day-by-day design-session
argument — becomes retrievable only via `git log`/`git show` on the retired
path, not by reading the tree. For `sim_architecture.md` and
`sim_implementation_plan.md` in particular, that is a real loss of *texture*:
a new engineer reading only v2 gets the *what*, not the *why it isn't
something else*. The mitigation is the stub itself (§4): one paragraph per
retired file naming what it held and the exact commit it was retired at, so
the "why" is one `git show <sha>:<path>` away rather than lost.

## 4. The `sim_requirements.md` disposition (governed by `R-REQ-2`)

Replace the 77-row, essay-per-row register (2,256 lines) with a compact
table: one row per ID, in the same terms `R-REQ-2` already prescribes for a
retired requirement — **UID, a one-line paraphrase (not the full verbatim
origin quote), and its disposition** (`→ superseded by <v2 UID>` for the 49
cited rows, `→ retained, no v2 successor` or `→ parked` for the rest, each
checked against what the row actually says today, not assumed). Verbatim
origin quotes for the handful of rows where `memory.md`-style phrasing
genuinely carried the requirement (the register's own stated reason for
keeping them, §0) stay as a short blockquote under that row only — most rows
do not need one.

Estimated result: ~4 lines/row × 77 rows + header ≈ **320–350 lines**, an
~85% cut, with every one of the 49 live trace links still resolving to a
named disposition instead of 2,200 lines of now-historical design argument.

## 5. The extraction doc

New file, `docs/v1/FROZEN_DESIGN_ORIGINS.md`, holding exactly the fragments
identified in §3 as externally cited:

- From `sim_visualization_spec.md`: §2 (Scene primitive catalogue), §3 (style
  tokens/themes) — ~130 lines.
- From `sim_player.md`: §1 (Names — the one-window-not-second-application
  principle `workspace_mode.hpp` quotes directly), §10 (What shipped —
  reconciled) — ~155 lines.

Each fragment keeps its original section number and a one-line "extracted
from `sim_visualization_spec.md`/`sim_player.md`, retired `<date>`, full text
at `<commit>`" header, so `df_viz_System_Requirements_v0.1.md`'s existing
citations still resolve — those three docs' own `docs/v1/sim_...md` path
strings would need updating to point at the new file (§8, execution step,
not this pass). Target size for the new file: **~300 lines** including
headers. `sim_visualization_spec.md` and `sim_player.md` themselves become
stubs pointing at it, same pattern as everything else in §3.

## 6. `docs/v2/SIM_Implementation_Plan_v0.1.md` — the essay-checkbox defect

Not a v1 problem — a live drift inside the governed set, already implicitly
named in `memory.md` §4 ("single checkbox rows that are now essays,
2,400–4,375 characters each") and in `CLAUDE.md`'s own tick discipline: a
`[~]` box **must** say `closed by <command or condition>` (`R-REQ-6a`) — a
short clause, not a narrative. Measured directly this pass: **177 done/
started checkbox rows, 85 of them over 300 characters, totaling 79,512
characters** — the investigation narrative ("found live," "root cause,"
"verified independent of X") that belongs in a `SIM_Test_Execution_<date>.md`
record, which this module has been writing since 2026-08-27 for exactly this
purpose (19 of them exist).

**Proposal:** for every checkbox row whose closing clause exceeds ~200
characters, move the narrative into (or confirm it already exists in) the
matching dated Test Execution record, and shrink the checkbox line to `[x]
<item> — closed by <short clause>, see <Test_Execution file>`. This is not a
new discipline — it is enforcing the one `R-REQ-6a` already states, against
rows that drifted from it. Estimated reduction: 79,512 → ~15,000 characters
on that file (~80% cut in byte weight; line count is nearly unchanged, since
these are single long lines today). No `Shall`/`Accept`/`Verify`/`Trace`
anatomy is touched — this is scoped entirely to the implementation *plan's*
own checkbox prose, never to `SIM_Software_Requirements_v0.1.md`,
`SIM_System_Requirements_v0.1.md`, or the concept document, whose `R-REQ-3`
anatomy this plan does not propose changing anywhere.

## 7. `misc/`

- `START_HERE.md` (533 lines) is itself past its own stated budget — its own
  text says *"if it grew, it has failed"* and prescribes "keep about five" for
  the **Log** section, but **"Where we are" has never been trimmed** the same
  way; it carries full paragraphs back to 2026-08-27. Proposal for the
  execution pass: apply the same discipline already written for Log to Where
  We Are — fold anything superseded by a later entry into one line + a
  pointer to its Test Execution record, the same compression the Log section
  already does. Not done this pass (`START_HERE.md`'s three required fields
  are updated below, kept deliberately short, in the spirit of this
  proposal rather than adding to the problem).
- `MOVEMENT_B_PLAN.md` (324 lines) is not yet closeable — `B4`'s one real
  item (`io`'s `mcap.py`/`mcap.cpp` parity gap) is still open. **Not a
  candidate this pass.** Close it to a stub once `B4` resolves, same pattern
  as §3.
- `CONSOLIDATED_REQUIREMENTS.md` (143 lines), `DEMO_AND_SCOPE.md` (210),
  `RUN_THE_DEMO.md` (201) are current, actively read, and sized reasonably
  for what they do. **No change proposed.**
- `misc/mts_bench/` (7.2 MB) is untracked local reference material, not part
  of the spec. Out of scope, named for completeness only.

## 8. Sequencing, if the author approves execution

1. Write the 12 v1 stubs + `FROZEN_DESIGN_ORIGINS.md` + the compact
   `sim_requirements.md` register, in one pass, in `docs/v1/` (git history
   keeps the full text — this is a content replacement, not a `git rm`,
   which is itself a smaller, more reversible action than deletion and
   costs nothing extra to do this way).
2. Update the citing files' path strings where they pointed at content that
   moved: `df_viz_Raw_Requirements_v0.1.md`, `df_viz_System_Requirements_v0.1.md`,
   `df_viz_Concept_Document_v0.0.1.md`, `VIZ_Concept_Document_v0.0.1.md`,
   `workspace_mode.hpp`, `errors.yaml` — six files, each a one-line path
   edit to point at `FROZEN_DESIGN_ORIGINS.md` (or, for
   `sim_naming_and_diagnostics.md`, no change needed — it isn't moving).
   `rules/sim.md`'s own index (§0 of this file) gets rewritten to match —
   it is the normative index and must not describe files that no longer
   hold what it says they hold.
3. Run `trace_check.py` after (1)+(2) — it fails on a broken trace link by
   design, so a missed citation is caught mechanically rather than by
   review.
4. `SIM_Implementation_Plan_v0.1.md`'s checkbox-row compression (§6) is
   independent of 1–3 and can happen before, after, or in parallel.
5. `misc/START_HERE.md`'s own trim (§7) happens as ordinary session hygiene
   going forward, not as a one-time edit.

Each step is independently revertible from git history; nothing here is
one-way in the sense that matters — the *lines* shrink, the *record* does
not.

## 9. What this plan deliberately does not touch

- Any `Shall`/`Accept`/`Verify`/`Trace` row in `SIM_Concept_Document_v0.3.1.md`,
  `SIM_System_Requirements_v0.1.md`, `SIM_Software_Requirements_v0.1.md`, or
  `SIM_Implementation_Design_v0.1.md` — the governed product spec, `R-REQ-3`'s
  anatomy, untouched in shape or count.
- Any `SIM_Test_Execution_<date>*.md` record — append-only evidence,
  `R-REQ-6`, never edited after the fact.
- `docs/py/` — already correctly dispositioned as known-red evidence
  (`project_sim_docs_py_stale_paths` memory), a `WP-01` item, not this plan's.
- `modules/viz/docs/` — a different module's document set.
- The root `.claude/` rule/skill layer — cross-cutting, not sim's alone.
