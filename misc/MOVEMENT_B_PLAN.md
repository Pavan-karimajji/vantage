# Movement B — finish what exists

**Written:** 2026-08-27 · **Status:** plan only, nothing executed.
**Reads with:** `memory.md` (why), `DEMO_AND_SCOPE.md` (the finite list),
`CONSOLIDATED_REQUIREMENTS.md` (the 25 lines).

Movement A is done. This is the plan for the movement that **all three previous
attempts died in**: deleting what was replaced. Every migration in this project
so far has been a copy, never a move, so nothing has ever been finished.

**The rule that governs every step below:**

> Nothing is done until the thing it replaced is gone.
> Delete only behind a gate that proves the replacement works.

---

## B0 — Preconditions

| | |
|---|---|
| Gate state | 1 known failure (Conan editable, parked WP-31) |
| Decisions in force | **A** C++ where possible · **B** player permanently in viz · **C** ~~ERG~~ **parked** · **D** vdy months away · **E** demo = done, as POC |
| Freeze | in force — corrections allowed, new scope goes to the parked list |

**The ERG blocker is answered: no such measurement exists and none can be
obtained (2026-08-27).** `B5` is therefore **parked in full**, and the demo was
rewritten around a recording the system produces itself (`DEMO_AND_SCOPE.md` §1).
The `.erg` codec stays built (`WP-06b`, 8/8) and unused until data appears.

**The new top risk** is step zero of the revised critical path: can a recording
containing df's *outputs* be produced, and does `mode: measured` consume it?
`R-SIM-6` says yes and is marked built — but built is not demonstrated. **Check
this before anything else in Movement C.** An hour's work, and it decides whether
the demo is close or blocked.

---

## B1 — Close the viz sync plan · **10 boxes, all closed 2026-08-29**

The whole remainder of a 43-item plan. All of it was deletion or truth-telling.

| Item | Work | Gate |
|---|---|---|
| `SM-10` — **done** | The real finding wasn't `modules/sim/CLAUDE.md` (already correct) but `modules/viz`'s own `CLAUDE.md`, still opening *"this module does not exist yet — there is no source here"* over 112 files / ~11,300 lines. Fixed. | The file describes what is actually on disk |
| `SM-05` — **done** | supersession bookkeeping, closed once `SM-12`'s dual-run window closed | trace check clean |
| `SM-07` — **done** | `MP-4` re-cut | trace check clean |
| `SM-08` — **done** | Qt out, headless in — turned out to already be true (`SM-12` deleted the last Python `PySide6` importer as a side effect). Real remaining work: `pyproject.toml`'s `viewer` extra dropped, two stale docstrings fixed, `sim-ci.yml`'s three install lines corrected (would have failed outright on the now-unknown `viewer` extra), `ANL-SM-02` built for real and wired into `ci_gate.py`. `figures`/`foxglove` extras also now dead in source — found, not touched, separate finding. | `ANL-SM-02` real and green: no CI image installs a graphical toolkit |
| `SM-12` — **done** | **Deleted the Python scene** — the `D-6` box. This *is* Decision B: `scene/`, `render/`, `player/shell/` gone, `player/panels/` down to `pipeline_panel.py` (`SI-22`'s own `KEEP`); ~20 dependent files individually triaged and fixed (`core/runner.py` split, `cli/render.py`/`cli/view.py` deleted, `plugins/registry.py`'s `EXTENSION_POINTS` amended, `scripts/vantage.py` deleted, `vantage.bat`/`gui.py`/`vantage_native.py` lost their `--legacy` fallback — a real, named capability loss, not silently dropped). `df`'s own `sim/layers/{bsd,common}.py` confirmed orphaned-but-harmless, not touched (separate submodule, separate finding). | `ANL-SM-03` real and green: exactly one layer-provider implementation remains |

**Exit:** the sync plan self-deleted, per its own §6.6 — §2/§3 removed,
2026-08-29. **Both honest exceptions named at the time are now closed
(2026-08-30):** `sync_check.py` is deleted — `scripts/next.py` was rewritten
to drop the hard import, per the sync plan's own "minus its gate table"
(§6.6), and now runs each of the three modules' own `trace_check.py` instead.
`scripts/check_cross_module_trace.py`'s 60 `BROKEN` findings were triaged:
56 (every `SIM:SW-*`/`SIM:SYS-*` one) were exactly the suspected parser gap
— a third disposition-table definition shape the checker didn't recognize —
fixed; the remaining 3 (`VIZ:IMP-0036`/`0064`/`0065`) are real dangling links
in `df_viz_Implementation_Design_v0.1.md`, left unfixed and named for whoever
owns df's design doc next. Full account:
`docs/v2/SIM_Test_Execution_2026-08-29_b1_close.md` (the original close) and
`docs/v2/SIM_Test_Execution_2026-08-30_sync_check_retire.md` (this pass).

**`E2E-VZ-01`'s `PASS`, from here on, means C++-vs-frozen-snapshot, not
two live implementations agreeing** — the Python side that used to be the
second half of that comparison no longer exists. Stated explicitly in the
closing Test Execution record so it is never over-read later.

## B2 — Delete the `df_viz` remnant · **~4,900 lines**

`modules/df/src/platform/df_viz/` is a half-finished extraction: its `viz/`
subfolder is emptied to two directories, everything else was copied to
`modules/viz` and the original left standing.

1. **Gate:** df builds and its tests pass linking `modules/viz` only.
2. Delete `modules/df/src/platform/df_viz/`.
3. **Verify:** df build green; no reference to the old path survives a grep.

## B3 — Delete legacy tooling · **~6,300 lines**

The tooling the `R-SIM` rules were written to replace, still present.

| Target | Size | Gate before deleting |
|---|---|---|
| `modules/df/tools/carla/` | ~3,200 | ⚠ **see the caution below** |
| `replay/viz.py` | 561 | the viz player renders the same recordings |
| `scripts/df_sim_gui.py` | 658 | `vantage.bat` covers what it did |
| `docs/bsd/py/bsdviz/` | 1,878 | the layer plug-ins cover it |

> ⚠ **Caution — do not delete blind.** `carla_bridge.py` inside `tools/carla/`
> is what **generates the recordings**. The parked scenario finding (only 4 of
> 18 recordings exist; the warning never fires in any that run) is entangled
> with it: it was fixed on 2026-08-16 by a commit saying *"live bridge was
> broken since S-C3"*. Deleting the recording generator before that is
> understood would remove the ability to regenerate the corpus. **Resolve the
> parked finding, or confirm ERG replaces this corpus entirely, before B3 row 1.**

## B4 — Resolve the Python/C++ overlap · Decision A

`modules/sim/src` carries two stacks: `adas_sim` (Python, 26,272 lines) and
`simcore` (C++, 31,064). `io`, `runspec`, `session`, `abi` and `diagnostics`
exist in both.

| Item | Work |
|---|---|
| `WP-16` (1 open) | **DELETION** — retire `sil_host`, end seven duplications |
| `WP-02` (11 started, 1 open) | Python restructure, world-model removal, archive |

**Method, per overlapping sub-package:** name the winner (C++, per Decision A),
prove parity, delete the loser, verify.

**Do not over-delete.** Python still legitimately owns the once-per-run half —
resim, config resolution, the run spec. The engine split is a stated rule:
*per tick is C++, once per run is Python*, joined by the Resolved Run Spec
(`WP-05`, the seam). Python that has no C++ replacement is not dead code.

## ~~B5 — Readers and writers~~ · **PARKED 2026-08-27**

`WP-17` (11 boxes) and `WP-18` (11) are parked with ERG. They were on the
critical path only because ERG needed them; `mcap` read and write already work
on both the Python and C++ sides, which is all the revised demo requires.

**Unpark when** a real measurement in a format sim cannot yet read arrives —
ERG, MDF4, rosbag. The `.erg` codec is already written, so that day starts from
`WP-17`, not from zero.

---

## Order, and why

```
B1 (viz, 10 boxes)  ──►  B2 (df_viz remnant)  ──►  B4 (py/c++ overlap)
                                │
          B3 (legacy tooling)  ◄┘   only after the parked scenario
                                    finding is resolved, or ruled irrelevant
```

B1 first: small, finishes a whole 43-item plan, and one of its boxes stops every
future session being misinformed on its first read. B4 last of the three, because
it is the largest and the least urgent now that ERG is parked.

**Movement B no longer blocks the demo.** With ERG gone, the demo's critical path
(`DEMO_AND_SCOPE.md` §5) runs entirely through already-part-built packages —
chiefly `WP-28`, which has one design item left. **If the goal is to see the demo
soonest, do Movement C's step zero first and Movement B after.** Movement B is
the debt that makes the next six months cheap; it is not the gate on the POC.

## Definition of done for Movement B

1. The viz sync plan has deleted itself.
2. `modules/df/src/platform/df_viz/` does not exist.
3. Exactly one implementation of io, session, abi, runspec and diagnostics.
4. The gate is green with no parked-failure exceptions other than WP-31 scope.
5. ~~`sim` can read a real ERG measurement end to end.~~ *Parked with ERG.*

---

## Two findings to decide on separately

**1. The parked scenario finding.** Only 4 of 18 scenarios can run; of those, the
single passing one asserts `warning == 'OFF' always` — it passes by asserting
nothing happens — while all three that assert a warning fires report *never
became*. Parked by decision on 2026-08-27. It is entangled with B3 (above) and
with the demo, which is *"see the BEV with objects and the warning zone."*

**2. ~~A company email domain appears in 419 files~~ — settled 2026-08-27.**
Writing the organisation as **L&T EPS** is approved, so the 419 files are not a
confidentiality problem and no scrub is required. If the spelling is ever
normalised, `docs/file_header_template.md` is the one file that matters — every
new file inherits from it, which is why the string spread this far.
