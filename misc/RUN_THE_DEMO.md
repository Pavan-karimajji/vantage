# Run the POC demo

**Written:** 2026-08-28, from the run recorded in
`docs/v2/SIM_Test_Execution_2026-08-28_f8.md`. Every command below was executed;
nothing here is from memory.

**What you are about to do** (`DEMO_AND_SCOPE.md` §1 — the definition of done):

> Open the launcher. Pick a recording the system itself produced. Set df to
> MEASURED — the picture comes from the file. Set df to SIMULATED — the same
> picture is computed live by the real DLL. The two match. Click an object and
> see which signal, tick, file and build produced it.

---

## 0. What must already be built

| Thing | Where | Build it with |
|---|---|---|
| `df_sil.dll` — the module under test | `modules/df/build-sil-vs2026/src/platform/df_sil/Release` | `modules/df/build.bat -t sil -p vs2026` |
| `df_viz.dll` — its **layers** (the picture) | `modules/df/build-sil_viz-vs2026/src/platform/df_viz/Release` | `modules/df/build.bat -t sil_viz -p vs2026` |
| `simengine.exe` — the engine | `modules/sim/build-gtest-vs2026/src/simengine/Release` | `cmake --build --preset gtest-vs2026 --parallel` in `modules/sim` |
| `vantage_app.exe` — the window | `modules/sim/vantage/build-sil-vs2026/build/cpp/vantage_app/Release` | `modules/sim/vantage/build.bat -t sil -p vs2026` |

**Platform: `vs2026`, native Windows.** The demo needs a real GL window; there
is no Linux path for it today.

Python is the repo's own venv — `modules\sim\.venv\Scripts\` — **not** a system
Python. Everything below assumes you are in `modules\sim`.

---

## 1. Produce a recording the system itself made

The demo's own recording is *not* checked in (it lands under gitignored `logs/`).
Make one: run `df` once against a stimulus recording and save every port, in
**and** out.

```
.venv\Scripts\sim.exe resim ..\df\tests\carla_testruns\aeb\aeb_closing_ego20mps_lead10mps_30m.mcap ^
  --pipeline ..\df\sim\pipelines\df_only.yaml ^
  --save logs\_step0\v_self.mcap ^
  --search ..\df\build-sil-vs2026\src\platform\df_sil\Release ^
  --config ..\df\src\project\base\default.yaml
```

Expect `resim complete: 100 tick(s)`. Check what it carries:

```
.venv\Scripts\sim.exe list topics logs\_step0\v_self.mcap
```

You should see **seven** topics — df's four outputs plus its three inputs:

```
/df/aeb.outputs   /df/aeb.compState   /df/bsd.outputs   /df/bsd.compState
/source/gen_object_list   /source/veh_dyn   /df/vehSig
```

That the inputs are named `/source/...` and not `/df/...` is what makes this file
re-simulatable as well as replayable — it is why the toggle can go **both** ways
off one recording. (If yours says `/df/objects`, you are on a build older than
2026-08-28.)

## 2. Open the launcher

```
vantage.bat
```

## 3. Fill it in

For this demo, exactly these six:

| Field | Put this | What it means |
|---|---|---|
| **Recording** | `…\modules\sim\logs\_step0\v_self.mcap` | The `.mcap` to open. Leave empty and you get Vantage's start page instead. The dropdown lists recent files first, then every `.mcap` under `modules/*/tests/**`. |
| **Plug-in root** | `..\df\build-sil_viz-vs2026\src\platform\df_viz\Release` | Where a component's **layers** come from — the picture of that component's own function. Leave empty and you still get the framework's own layers (ego, frame), just nothing function-specific. **Watch the coloured line under this box** — it tells you before you launch whether what you picked is really a viz plug-in root. |
| **project** | `base` | Which calibration set geometry is resolved from. Real values here: `base`, `cus1`, `2w_base`. Switching it must visibly change the drawn ego. |
| **pipeline.yaml** | `..\df\sim\pipelines\df_only.yaml` | A pipeline makes this a **RESIM** — the DLL is re-executed against the recording, so its outputs and layers actually exist. Leave empty to **REPLAY**: you see only what the file already contains. |
| **--search (dll dir)** | `..\df\build-sil-vs2026\src\platform\df_sil\Release` | The directory holding the built `df_sil.dll`. Only needed with a pipeline — it is how `impl: dll:df_sil` resolves to a real file. |
| **--config** | `..\df\src\project\base\default.yaml` | The calibration the DLL is initialised with (`adasInit`). Getting this wrong is how the viewer and the module end up reading different calibration and agreeing only by coincidence. |

Leave **preset**, **start at (s)** and **Legacy Python viewer** alone.

### The two that matter — `stage / mode`

| Field | What it means |
|---|---|
| **stage** | Which stage in the pipeline the mode applies to. `df_only.yaml` has exactly one, `df`, and it fills itself in. It only ever auto-fills a *blank* box — if you type a name that is not a stage it tells you so rather than quietly using a different one. |
| **mode** | `(as authored)` · `measured` · `simulate` · `off`. `(as authored)` changes nothing and runs the pipeline file exactly as written. |

Choosing a mode does **not** edit `df_only.yaml`. It writes a new file under
`logs\_launcher\` with that one field changed, and points the command at it —
so what runs is a real pipeline file you can read and re-run headlessly.

Watch the message beside the dropdowns:

- `OK: recording provides this cut · df = measured` — green, and the run config
  was written.
- `this recording cannot drive 'df' as measured — aeb.outputs: not provided by
  this recording; …` — amber. **Nothing was written and the mode did not
  apply**, so the command falls back to the authored pipeline. You get this if
  you point it at a stimulus-only recording, which genuinely has no df outputs
  to replay. That is the check working, not a bug.

### The rest of the screen

| | |
|---|---|
| **Command that will run** | The exact command the Launch button will execute. Copy it to run the same thing from a terminal. |
| **Launch Vantage** | Runs it. |
| **Probe a library…** | Reads a component library's port set straight from its manifest. |
| **sim doctor** | Reports the environment. |
| **Render snapshot** | Headless PNG (legacy Python renderer). |
| **Output** | Whatever the launched process printed. |

## 4. Do the demo

1. Set **mode** to `measured` → **Launch Vantage**. The picture comes from the
   file.
2. Close the window. Set **mode** to `simulate` → **Launch Vantage**. The same
   picture, recomputed live by the real DLL.

**What you should see, both times:** `Scene: 9 prims`; a layer tree with
`df/objects`, `df/hud`, `bsd.zone (derived)`, `bsd.warning`,
`bsd.sensor_fov (derived)`, `furniture`; `Timeline tick 100 LIVE`; the ego glyph
with its sensor-FOV cones.

**The two agree.** That is the point of the demo, and you confirm it by looking.
Underneath, the two runs' port values are byte-identical — asserted separately,
not by eye.

## 5. Click an object → where did this come from

In the window, select a drawn object; the evidence panel answers. The **same**
answer, from the same producer, is available headlessly:

```
.venv\Scripts\sim.exe explain df.aeb.outputs --session logs\_step0\v_self.mcap --at 46
```

```
address                  df.aeb.outputs
value                    critical_obj_id: 150
                         latent_pre_warning_active: true
tick                     46          t_ns  2350000000
topic                    df.aeb.outputs
origin                   simulated
run_id                   20260828T021356Z-8f809308
component_build_id       unknown
component_library_sha256 b3524ca8726bf29eecf2b7c8a4ada4fa5342a9a987bb98e1e2c1ff14f49994a6
```

Tick 46 is `t=2.30 s`, where AEB fires on this scenario.

Reading it:

- **`origin`** is the evidence grade. Try `source.gen_object_list` and it says
  `mocked` — because that stimulus *is* synthetic. It will never say `measured`
  for a mock.
- **`component_build_id` reads `unknown` and that is correct** — nothing records
  a build id today. The build is identified by
  **`component_library_sha256`**, the hash of the exact `df_sil.dll` that ran.
  Two different facts, each under its own name; the hash is never shown where a
  build id was asked for.
- **`unknown` always means "nobody recorded this"**, never a default.

## 6. Same thing without the GUI

```
.venv\Scripts\python.exe scripts\vantage_native.py logs\_step0\v_self.mcap ^
  --plugin-root ..\df\build-sil_viz-vs2026\src\platform\df_viz\Release ^
  --project base ^
  --search ..\df\build-sil-vs2026\src\platform\df_sil\Release ^
  --config ..\df\src\project\base\default.yaml ^
  --pipeline logs\_launcher\df_only__df_measured.yaml
```

Anything the launcher does, this does — it is the command the launcher builds.

---

## Known rough edges

Stated so you do not spend time on them:

- **`sim probe` reports `provides (0)`** on a perfectly good recording. It reads
  a different path from the engine's, and that path is still ingest-gated. The
  launcher's own feasibility line does work — use that.
- **`config_bundle_sha256` reads `unknown`** — the calibration hash is not
  recorded yet, only the build.
- **`aeb.compState` is empty.** Deliberate: AEB's heartbeat is not implemented
  yet in `df`, and this is not a sim defect.
- **`bsd_curve_r172_passby` passes honestly since 2026-08-28**, but is
  **under-asserted**: its BSD warning genuinely fires from t≈7.4 s to t≈9.6 s
  and no expectation covers that — `EXP-1` checks only the first 5 s of an
  ~11 s recording. A green here is real now, but it is not coverage.
