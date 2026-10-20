# Run the POC demo

**Written:** 2026-08-28, from the run recorded in
`docs/v2/SIM_Test_Execution_2026-08-28_f8.md`. **Re-run and corrected 2026-10-20:**
the build locations, the Python environment and the recording below are the ones
that exist now, and §1, §5 and §6 were executed as written (outputs quoted).
Nothing here is from memory.

**What you are about to do** (`DEMO_AND_SCOPE.md` §1 — the definition of done):

> Open the launcher. Pick a recording the system itself produced. Set df to
> MEASURED — the picture comes from the file. Set df to SIMULATED — the same
> picture is computed live by the real DLL. The two match. Click an object and
> see which signal, tick, file and build produced it.

---

## 0. What must already be built

Every build tree lives under its module's `conan_workarea\`.

| Thing | Where | Build it with |
|---|---|---|
| `df_sil.dll` — the module under test | `modules\df\conan_workarea\build-sil-vs2026\src\platform\df_sil\Release` | `modules\df\build.bat -t sil -p vs2026 -P base` |
| `df_viz.dll` — its **layers** (the picture) | `modules\df\conan_workarea\build-sil_viz-vs2026\src\platform\df_viz\Release` | `modules\df\build.bat -t sil_viz -p vs2026 -P base` |
| `simengine.exe` — the engine | `modules\sim\conan_workarea\build-gtest-vs2026\src\simengine\Release` | `modules\sim\build.bat -t gtest -p vs2026` |
| `vantage_app.exe` — the window | `modules\sim\vantage\conan_workarea\build-sil-vs2026\build\cpp\vantage_app\Release` | `modules\sim\build.bat -t sil -p vs2026` (`vantage` is a sub-component of sim, `conf/build.yml` `subcomponents:`; it has no `build.bat` of its own) |

**Platform: `vs2026`, native Windows.** The demo needs a real GL window; there
is no Linux path for it today.

Python is the sim environment — `modules\sim\.venv-sim-win32\Scripts\` — **not**
a system Python. Everything below assumes you are in `modules\sim`.

---

## 1. Produce a recording the system itself made

The demo's own recording is *not* checked in (it lands under gitignored `logs/`).
Make one: run `df` once against a stimulus recording and save every port, in
**and** out. The stimulus is a CARLA recording of the `aeb_closing_ego20mps_lead10mps_30m`
scenario (produce it with `py -3.12 modules\df\tools\carla\carla_run.py aeb_closing_ego20mps_lead10mps_30m`,
or use the one already under `modules\df\tests\carla_testruns\aeb\`). The pipeline is
`df_replay.yaml`, which feeds every input `df_sil` has (objects, ego dynamics, vehicle
signals, lanes).

```
.venv-sim-win32\Scripts\sim.exe resim ..\df\tests\carla_testruns\aeb\aeb_closing_ego20mps_lead10mps_30m.mcap ^
  --pipeline ..\df\sim\pipelines\df_replay.yaml ^
  --save logs\_step0\v_self.mcap ^
  --search ..\df\conan_workarea\build-sil-vs2026\src\platform\df_sil\Release ^
  --config ..\df\src\project\base\default.yaml
```

Expect `resim complete: 61 tick(s)`. Check what it carries:

```
.venv-sim-win32\Scripts\sim.exe list topics logs\_step0\v_self.mcap
```

You should see **twelve** topics — the four driving functions' outputs (each with
its `compState`) plus the four inputs:

```
/df/aeb.outputs   /df/aeb.compState   /df/bsd.outputs   /df/bsd.compState
/df/cta.outputs   /df/cta.compState   /df/ldw.outputs   /df/ldw.compState
/source/gen_object_list   /source/veh_dyn   /source/veh_sig   /source/lanes
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
| **Plug-in root** | `..\df\conan_workarea\build-sil_viz-vs2026\src\platform\df_viz\Release` | Where a component's **layers** come from — the picture of that component's own function. Leave empty and you still get the framework's own layers (ego, frame), just nothing function-specific. **Watch the coloured line under this box** — it tells you before you launch whether what you picked is really a viz plug-in root. |
| **project** | `base` | Which calibration set geometry is resolved from. Real values here: `base`, `cus1`, `2w_base`. Switching it must visibly change the drawn ego. |
| **pipeline.yaml** | `..\df\sim\pipelines\df_replay.yaml` | A pipeline makes this a **RESIM** — the DLL is re-executed against the recording, so its outputs and layers actually exist. Leave empty to **REPLAY**: you see only what the file already contains. (`df_only.yaml` wires only objects and ego dynamics, which leaves the lane and vehicle-signal functions without their inputs.) |
| **--search (dll dir)** | `..\df\conan_workarea\build-sil-vs2026\src\platform\df_sil\Release` | The directory holding the built `df_sil.dll`. Only needed with a pipeline — it is how `impl: dll:df_sil` resolves to a real file. |
| **--config** | `..\df\src\project\base\default.yaml` | The calibration the DLL is initialised with (`adasInit`). Getting this wrong is how the viewer and the module end up reading different calibration and agreeing only by coincidence. |

Leave **preset**, **start at (s)** and **Legacy Python viewer** alone.

### The two that matter — `stage / mode`

| Field | What it means |
|---|---|
| **stage** | Which stage in the pipeline the mode applies to. `df_replay.yaml` has exactly one, `df`, and it fills itself in. It only ever auto-fills a *blank* box — if you type a name that is not a stage it tells you so rather than quietly using a different one. |
| **mode** | `(as authored)` · `measured` · `simulate` · `off`. `(as authored)` changes nothing and runs the pipeline file exactly as written. |

Choosing a mode does **not** edit `df_replay.yaml`. It writes a new file under
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

**What you should see, both times:** the layer tree lists `objects`, `hud`, every
function's layers (`aeb`, `bsd.zone`, `bsd.warning`, `bsd.sensor_fov`, `cta.*`,
`ldw.*` — an `ldw.*` or `cta.*` layer that needs a port the run does not carry is
greyed, and the process prints which one and why, e.g. `layer "camera.chase"
unavailable: required port "carla.chase_camera" is not carried by the driving
tick` for a recording made without `--camera`), `Timeline tick 61`, the ego glyph.
The Output pane of the launcher shows those lines.

**The two agree.** That is the point of the demo, and you confirm it by looking.
Underneath, the two runs' port values are byte-identical — asserted separately,
not by eye.

## 5. Click an object → where did this come from

In the window, select a drawn object; the evidence panel answers. The **same**
answer, from the same producer, is available headlessly:

```
.venv-sim-win32\Scripts\sim.exe explain df.aeb.outputs --session logs\_step0\v_self.mcap --at 46
```

```
address                   df.aeb.outputs
kind                      port
value                     sig_header {
                            source_timestamp_us: 3300000
                            cycle_counter: 47
                          }
                          critical_obj_id: 1
                          latent_pre_warning_active: true
tick                      46
t_ns                      2300000000
topic                     df.aeb.outputs
origin                    simulated
run_id                    20261020T182517Z-1996587f
config_bundle_sha256      8cac75b732f77540259687ce01e481d1daee00fd6c826bba82fc2846895f502c
component_build_id        unknown
component_library_sha256  379a0be621ec674364f511d0b600bd24ccf02f84ab470ce1625c150bd2aa2e53
```

(`run_id` and the hashes are those of the run on 2026-10-20; yours differ with your
build and your minute. The parts that must match are the tick, the time and the
two values.) Tick 46 is `t=2.30 s`, where AEB fires on this scenario.

Reading it:

- **`origin`** is the evidence grade. Try `source.gen_object_list` and it says
  `truth` — CARLA's own world, not a measurement and not a mock (`R-SIM-12`). It
  will never say `measured` for a simulator's ground truth.
- **`component_build_id` reads `unknown` and that is correct** — nothing records
  a build id today. The build is identified by
  **`component_library_sha256`**, the hash of the exact `df_sil.dll` that ran.
  Two different facts, each under its own name; the hash is never shown where a
  build id was asked for.
- **`unknown` always means "nobody recorded this"**, never a default.

## 6. Same thing without the GUI

```
.venv-sim-win32\Scripts\python.exe scripts\vantage_native.py logs\_step0\v_self.mcap ^
  --plugin-root ..\df\conan_workarea\build-sil_viz-vs2026\src\platform\df_viz\Release ^
  --project base ^
  --search ..\df\conan_workarea\build-sil-vs2026\src\platform\df_sil\Release ^
  --config ..\df\src\project\base\default.yaml ^
  --pipeline ..\df\sim\pipelines\df_replay.yaml
```

Run on 2026-10-20 this prints the resim step (`resim complete: 61 tick(s)`), then the
`vantage_app.exe` command it launched, and the window opens. For the **measured** half
use the pipeline file the launcher wrote with `df` set to `measured`
(`logs\_launcher\df_replay__df_measured.yaml`) as `--pipeline`.

Anything the launcher does, this does — it is the command the launcher builds.

---

## Known rough edges

Stated so you do not spend time on them:

- **`sim probe` reports `provides (0)`** on a perfectly good recording. It reads
  a different path from the engine's, and that path is still ingest-gated. The
  launcher's own feasibility line does work — use that.
- **`config_bundle_sha256` reads a real hash** (fixed `A-15`, proven on
  the real path `2026-08-31` — see
  `docs/v2/SIM_Test_Execution_2026-08-31_a15_real_path_proof.md`). If you see
  `unknown` instead, your `df_sil.dll` predates that fix or was not rebuilt
  after it — rebuild `df` (`build.bat -t sil -p vs2026`) and re-run the resim.
- **`aeb.compState` carries `function: aeb`, `state: RUNNING`** since `df`'s
  AEB heartbeat landed (2026-10-09). If it is empty, your `df_sil.dll` predates
  that — rebuild `df` (`build.bat -t sil -p vs2026`) and re-run the resim.
- **The window's layer tree was not re-read on 2026-10-20** — the run was
  confirmed to start (resim, then `vantage_app.exe` with the layer-availability
  lines above) but nobody looked at the tree, so the layer names in §4 are the
  plug-in's declared ones (`modules\df\src\platform\df_viz\conf\viz.yaml`), not a
  screenshot.
- **`bsd_curve_r172_passby` may be under-asserted** (the 2026-08-28 finding: its
  `EXP-1` checked only the first 5 s while the BSD warning fires later). Its
  schema-3 run warns from t≈7.5 s to t≈9.3 s; whether its expectations cover
  that window was not re-checked on 2026-10-20.
