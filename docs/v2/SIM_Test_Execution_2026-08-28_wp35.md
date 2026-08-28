# SIM — Test Execution Record — 2026-08-28 · `WP-35` · the demo

**Third campaign of 2026-08-28**, after `…_2026-08-28.md` (the step-zero
fixes) and `…_2026-08-28_wp28.md` (the launcher campaign). Campaign name
appended because the date no longer distinguishes them (`R-REQ-6`).

**This record is evidence, not a specification.** Exempt from the freeze on
that basis, never edited after the fact.

## Campaign

| | |
|---|---|
| Question | Does `DEMO_AND_SCOPE.md` §1 run, end to end, watched? |
| Method | `D` demonstration — real launcher, real `vantage_app.exe`, real `df_sil.dll`, real `df_viz.dll`, a recording the system produced itself — plus `T` (`UT-VTG-03`, 5 cases) |
| Platform | `vs2026`, native, driven through WSL2 interop |
| Evidence | `modules/sim/logs/_wp35/` (gitignored): 4 screenshots, the derived configs, the console transcripts |
| Committed | **No.** Working tree only. |

## Result

**Four of §1's five clauses are demonstrated. The fifth is three-quarters
answered, and the missing quarter is `F-8` — recorded, not fixed.**

| §1 clause | Status |
|---|---|
| Open the launcher | ✅ real `scripts/gui.py` window, screenshot `01`/`02` |
| Pick a recording the system itself produced | ✅ `logs/_step0/v_self.mcap`, written by `sim resim --save` |
| Set df to MEASURED — the picture comes from the file | ✅ screenshot `03`/`03b` |
| Set df to SIMULATED — computed live by the real DLL | ✅ screenshot `04` |
| The two pictures agree | ✅ watched — same 9 prims, same layer tree, same tick, same geometry |
| Click an object → signal, tick, file **and build** | ⚠️ signal, tick, file, origin and `run_id` — **build reads `unknown`** (`F-8`) |

---

## What was run

The launcher was opened twice, once per direction. Its fields were set
programmatically (`StringVar.set`, then the app's own `_refresh`) rather than
by mouse — **stated plainly because it matters**: this session cannot drive a
pointer. Everything downstream of the setting is the real thing: the real
widget tree, the real `_resolve_mode`, the real `launcher.write.to_run_config`,
and the real command string the Launch button would run.

**Screenshot `01` — `df = MEASURED`.** `stage / mode` shows `df` / `measured`
and the status reads, in green: *"OK: recording provides this cut · df =
measured"* — that is `launcher.cuts.cuts_for_recording` answering before the
run (`R-SIM-23`), through the join `F-7` fixed this morning.

**Screenshot `02` — `df = SIMULATE`.** Same screen, `simulate`, *"OK: df =
simulate"*.

The launcher wrote two real, readable configs, one `mode:` apart, `impl:`
retained on both so the toggle is reversible (`R-SIM-10`):

```yaml
version: 1
name: df_only
stages:
  - name: df
    mode: measured            # <- the only difference
    impl: dll:df_sil
    inputs:
      objects: source.gen_object_list
      egoDyn: source.veh_dyn
project: base
recording: ..\..\_step0\v_self.mcap
config: ..\..\..\..\df\src\project\base\default.yaml
```

and the command it built named that file:

```
… scripts\vantage_native.py …\logs\_step0\v_self.mcap
   --plugin-root …\df\build-sil_viz-vs2026\src\platform\df_viz\Release
   --project base --search …\df_sil\Release --config …\base\default.yaml
   --pipeline …\logs\_wp35\derived\df_only__df_measured.yaml
```

**Screenshots `03`/`03b` and `04` — the two pictures.** Both runs opened a real
`vantage_app.exe` window (`Get-Process`: `MainWindowTitle='vantage'`) against
the real deployed `df_viz` plug-in root. Both show the same scene: `Scene: 9
prims`; the same layer tree (`df/objects`, `df/hud`, `bsd.zone (derived)`,
`bsd.warning`, `bsd.sensor_fov (derived)`, `furniture`); `Timeline tick 100
LIVE`; the same ego glyph, the same sensor-FOV cones and the same geometry.

**They agree — watched, not asserted.** `vantage_app.exe` has no snapshot flag
and adding one was out of scope, so this claim rests on the two images plus the
already-asserted fact that the two runs' port values are byte-identical (the
2026-08-28 step-zero campaign, 20 firing AEB ticks each, `t=2.300 s`,
`critical_obj_id=150`). The screenshots add what that assertion cannot: that
the equality is visible to a person, through the face.

## Provenance — and `F-8`

`sim explain` is the evidence panel's headless twin — its own help says it
*"prints the same record the viewer's evidence panel shows, so the headless and
GUI answers cannot drift apart"* (`R-SIM-25`, one producer, two formatters). At
the tick where AEB fires:

```
address              df.aeb.outputs
value                critical_obj_id: 150
                     latent_pre_warning_active: true
tick                 46          t_ns  2350000000
topic                df.aeb.outputs
origin               simulated
run_id               20260828T021356Z-8f809308
component_build_id   unknown        <- F-8
config_bundle_sha256 unknown        <- F-8
```

and, on the same recording's input port:

```
address              source.gen_object_list
origin               mocked         <- F-2 working: a mock reports as a mock
```

That `origin: mocked` is worth stating: before this morning's `F-2` fix it read
`measured`, and `R-SIM-12` exists to forbid exactly that.

### `F-8` · the evidence record does not join `run_id` → the build — **NOT FIXED**

`component_build_id` reads `unknown`, and `NR-SIM-4`'s discipline makes that
the *right* thing to print rather than a guess. But it is **not** unknown: the
same recording's manifest carries it, one dereference away —

```
components: 1
  ComponentBuildInfo(name='df',
                     library_sha256='b3524ca8726bf29eecf2b7c8a4ada4fa5342a9a987bb98e1e2c1ff14f49994a6',
                     period_ns=50000000, …)
```

`R-SIM-25` states the join needs *"no new capture and no new index"*:
`run_id` → the manifest → build. The capture is there; the join is not made.

So §1's *"and build produced it"* is the one clause the demo cannot yet
satisfy, and `WP-35`'s Exit box is `[~]`, closed by this.

**Deliberately not fixed here.** It lives in `diagnostics`, not the launcher,
and this package is scoped verbatim to §1's wiring. Fixing it inside the demo
package would be exactly the scope creep the freeze exists to stop.

## Verification

| Check | Before | After | Verdict |
|---|---|---|---|
| `pytest` (collected) | 1530 | **1535** | +5 (`UT-VTG-03`) |
| `pytest` failures | 1 (parked Conan) | **1** (same) | no regression |
| `check_invariants.py` | clean | clean | pass |
| `check_headers` / `closed_sets` / `no_duplication` / `artifact_kinds` / `time_units` | clean | clean | pass |
| `sim check` | 18 scenarios, 0 failed | 18, 0 failed | pass |
| `check_trace.py` | 155 `R-REQ-9` | **155** | unchanged — parked |
| `trace_check.py` | PASS | **PASS** | `WP-35` closes both directions |
| `ci_gate.py` | `status=fail` | **`status=fail`** | same two parked inputs |

`ci_gate_config.yaml` untouched. No floor moved, no tolerance widened, no test
deleted or skipped to reach any of the above.

### `UT-VTG-03` — 5/5, including the planted violation

`tests/system/test_lnc_gui_mode_control.py`, against a real `LauncherApp` on a
withdrawn `Tk` root. Asserts the authored `pipeline.yaml`'s **bytes** are
unchanged; that the derived file reloads through `Pipeline.load` with the one
`mode:` changed; that both directions land separate files. **The planted
violation:** `measured` against a stimulus-only recording writes no config,
names the missing ports, and leaves the command on the authored pipeline —
so a mode that did not apply can never look like one that did.

### Two defects found while writing it, both fixed

1. **A typo'd stage name was silently replaced** with the pipeline's only
   stage — applying the mode to a stage the user had not named. Auto-fill now
   only ever fills a *blank* field.
2. **An unresolvable `dll:` stage was reported as an error even with no mode
   chosen.** `Pipeline.load` resolves every `dll:` stage, so it genuinely
   cannot name the stages without `--search`; with nothing asked for, that is
   silence, not an error.

## Files changed

| File | Why |
|---|---|
| `scripts/gui.py` | `IMP-0433` — the stage/mode row and `_resolve_mode()` |
| `tests/system/test_lnc_gui_mode_control.py` | `UT-VTG-03`, 5 cases |
| `docs/v2/SIM_Software_Requirements_v0.1.md` | `SW-0429` |
| `docs/v2/SIM_Implementation_Design_v0.1.md` | `IMP-0433` |
| `docs/v2/SIM_Software_Test_Spec_v0.1.md` | `UT-VTG-03` |
| `docs/v2/SIM_Implementation_Plan_v0.1.md` | `WP-35` |

## Re-run commands

```
cd modules/sim
python -m pytest tests/system/test_lnc_gui_mode_control.py -q
python logs/_wp35/demo_launcher.py measured 25      # the launcher, one direction
python scripts/vantage_native.py <recording> --pipeline logs/_wp35/derived/<derived>.yaml \
       --plugin-root <df_viz build> --search <df_sil build> --config <project default.yaml>
sim explain df.aeb.outputs --session <recording> --at 46
```

A later campaign is a **new file**, never an edit to this one (`R-REQ-6`).
