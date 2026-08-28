# SIM — Test Execution Record — 2026-08-28 · `WP-28` launcher campaign

**Second campaign of 2026-08-28.** The first
(`SIM_Test_Execution_2026-08-28.md`) closed the step-zero fixes `F-1`…`F-4`.
This one drives the POC demo's gesture through `WP-28`'s launcher. Two
campaigns share a date, so the campaign name is appended (`R-REQ-6`).

**This record is evidence, not a specification.** Exempt from the 2026-08-27
freeze on that basis, never edited after the fact.

## Campaign

| | |
|---|---|
| Question | Does `WP-28`'s launcher deliver the demo — pick a recording, flip `df` measured↔simulated, agree, click for provenance? |
| Method | `D` demonstration (real `df_sil.dll`, real `simengine.exe`, the self-produced recording from this morning's campaign) + `T` test |
| Driven through | `Selection` → `classify` → `cuts_for_recording` → `to_run_config` → `launch(path)` — the launcher's own public API, nothing reaching around it |
| Raw evidence | `modules/sim/logs/_wp28/`, `logs/ci_gate/2026-08-28-wp28/` (gitignored) |
| Committed | **No.** Working tree only. |

## Result

**The headless half of the demo works. One real defect was found on the demo
path and fixed (`F-7`). The visible half has no work-package box anywhere,
which is a decision for the author, not something this pass should invent.**

---

## What was demonstrated

Both toggle directions, driven entirely through the launcher API against the
self-produced recording `logs/_step0/v_self.mcap` (df's inputs *and* outputs,
inputs under their producing identity — `F-3`):

```
recording : v_self.mcap
feasible cuts, computed before any run:
  df       feasible=True

=== df -> measured ===        === df -> simulate ===
  can_launch=True               can_launch=True
  wrote run_measured.yaml       wrote run_simulate.yaml
  resim complete: 100 tick(s)   resim complete: 100 tick(s)
  launch() returned 0           launch() returned 0
```

Both configs were written by `to_run_config` and executed by `launch(path)` —
the one function a Launch button may call, which reloads and re-classifies the
file rather than trusting the `Selection` that wrote it (`CN-0175`). That the
two runs' outputs are byte-identical, with AEB firing 20 ticks at `t=2.300 s`,
was established this morning and is not re-derived here.

## `F-7` · every cut reported infeasible against a real recording — **FIXED**

**Found by driving the demo, not by a test.** `cuts_for_recording` reported

```
df  feasible=False  (aeb.outputs: not provided by this recording; ...)
```

for a recording that carries exactly those four outputs — and `mode: measured`
against that same file then ran 100 ticks successfully. The pre-run feasibility
answer and the run disagreed.

**Cause: two correct halves with incompatible key conventions, joined by a
third module that nothing tested.**

| | keys its `RecordingIndex.topics` by | pinned by |
|---|---|---|
| `graph.feasible.feasible_cuts` | **bare** port name (`fn.out`) | `test_grf_feasible.py`, `test_lnc_cuts.py` — every fixture |
| `Session.feasible_cuts` | bare, via `manifest_port` | its own callers |
| `resolve.probe.describe_recording` | the recording's **topic** (`/stage/fn.out`) | `test_res_probe.py` |

`launcher/cuts.py` feeds the third into the first. Each endpoint is correct and
separately tested; **no test ever fed a real recording through the join**, so
every hand-built fixture agreed with itself and the real path silently returned
"nothing is feasible". This is what `R-SIM-23`'s *"computed before the run, not
discovered by failing one"* was supposed to prevent, inverted: the query said no
and the run said yes.

**Fix**: `_bare_keyed` in `launcher/cuts.py` translates the index into the keys
`feasible_cuts` matches on, **per stage** — `feasible_cuts` is now called once
per stage against that stage's own restricted view, so a topic can only ever
satisfy the stage that produced it. An already-bare index (hand-built, or
`Session`'s) passes through untouched, so the existing fixtures keep meaning
what they meant. Neither pinned contract was changed.

**Coverage added** (`tests/unit/test_lnc_cuts.py`, 3 new cases using a **real**
mcap written through the registered codec):

- a real recording carrying both stages' outputs → both feasible;
- **the planted violation** (`R-REQ-9`) — one topic withheld → only that stage
  infeasible, naming the port;
- two stages declaring an identically-named port → one stage's topic does not
  make the other look feasible.

**Seen to fail.** With `_bare_keyed`'s translation removed, all three new cases
fail and the four pre-existing hand-built ones still pass — which is precisely
the gap they exist to close.

**Scope note:** the defect is inside `IMP-0345`, a box that is `[x]` and whose
own test still passes. The box is not unticked: the defect was in the *join*,
which no box owned. Correcting it needs no plan change.

## What is left, and why no box was ticked

`WP-28` reads **6/7**, with its **Exit gate already `[x]`**. Its one open box,
`IMP-0344`, is `[~]` and correctly blocked: `version` reads the literal
`"unknown"` (`NR-SIM-4`) because a non-loading version source is `WP-21`'s
`library.py::is_available` + `resolve/bundle.py`, and `WP-21` is **0/15,
untouched**. Nothing in this campaign could close it, and nothing was ticked.

**The demo's remaining piece has no box.** Establishing this took reading the
packages rather than assuming:

- `WP-28` is the **headless launcher model** — `Selection`, `classify`,
  `cuts`, `write`, `availability`. Complete, and now demonstrated against the
  real demo instead of a stub.
- `WP-34a` owns the **launcher face** (`scripts/gui.py`, `vantage.bat`) and is
  **closed**. That GUI picks a recording and a plug-in root; it has **no mode
  control at all** and does not import `adas_sim.launcher` — grep for
  `measured`/`simulate`/`Selection` in `scripts/gui.py` returns nothing.
- So *"flip `df` between measured and simulated in the face"* is owned by
  neither, and the freeze forbids inventing a work package for it.

**And "watch the two pictures agree" cannot be asserted headlessly.**
`vantage_app.exe` has no snapshot/offscreen flag — its argv is `--config`,
`--project`, `--plugin-root`, `--bundle`, and it refuses `--pipeline`/`--search`
(`WP-34`'s own named gap). It is a real windowed GLFW app, so the picture
comparison is a demonstration a person watches. The **substance** behind it is
already asserted headlessly: the two runs' port values are byte-identical
(this morning's record), and the picture is a pure function of the `Session`.

## Verification

| Check | Before this pass | After | Verdict |
|---|---|---|---|
| `pytest` | 1515 passed · 1 failed · 11 skipped | **1518 passed · 1 failed · 11 skipped** | +3 new, no regression |
| `check_invariants.py` | clean | clean | pass |
| `check_headers` / `closed_sets` / `no_duplication` / `artifact_kinds` / `time_units` | clean | clean | pass |
| `sim check` | 18 scenarios, 0 failed | 18 scenarios, 0 failed | pass |
| `check_trace.py` | 155 `R-REQ-9` violations | **155** | unchanged — parked (`WP-31`) |
| `ci_gate.py` | `status=fail` | **`status=fail`** | unchanged, same two parked inputs |

The single `pytest` failure is `test_conan_editable_add_resolves_adas_sim`
(Conan remote credential prompt), already parked. `ci_gate.py` exits 1 on
exactly the 155 `R-REQ-9` citations and that Conan test — **nothing was
relaxed**: no floor moved, no tolerance widened, `ci_gate_config.yaml`
untouched.

**One self-inflicted failure worth recording, because it recurred.** The first
`pytest` run after the fix showed **5** failures: a docstring in
`launcher/cuts.py` used real component port names as examples, tripping `GT-1`
(`R-SIM-1` — the framework's own source may not contain a function's name) and
failing the four invariant-harness tests with it. Same mistake as this
morning's `meta.cpp` comment. Examples in framework source must be
component-agnostic; corrected, and both runs above are post-correction.

## Files changed

| File | Why |
|---|---|
| `src/adas_sim/launcher/cuts.py` | `F-7` — `_bare_keyed`, per-stage `feasible_cuts` call |
| `tests/unit/test_lnc_cuts.py` | `F-7` — 3 real-recording cases incl. the planted violation |

## Re-run commands

```
cd modules/sim
python logs/_wp28/drive_toggle.py                     # the demo gesture, launcher API
python -m pytest tests/unit/test_lnc_cuts.py -q
python scripts/ci_gate.py --artifact-dir logs/ci_gate/<name>
```

A later campaign is a **new file**, never an edit to this one (`R-REQ-6`).
