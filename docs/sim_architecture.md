# Simulation & Visualization Platform — Architecture Concept

Status: **concept, frozen for review 2026-07-27.** No code written. This is the
master document for the rework; four sibling documents own the detail:

| Doc | Owns |
|---|---|
| [sim_sil_contract.md](sim_sil_contract.md) | The Python↔C boundary: named port sets, component manifests, pipelines |
| [sim_visualization_spec.md](sim_visualization_spec.md) | The viewer: Scene primitives, BEV feature set, renderers, themes |
| [sim_resim_and_recording.md](sim_resim_and_recording.md) | sim / resim / replay, run manifests, determinism, recording format |
| [sim_scenarios_and_expectations.md](sim_scenarios_and_expectations.md) | Scenario schema, sensor model, expectations-as-data, headless CI |

**Looking for "where does this file go?"** → §5.8, the placement map.

Supersedes the *forward direction* of `../../../docs/df_carla_viz_plan.md`,
`../../../docs/df_carla_bridge_blueprint.md`, `../../../docs/df_carla_mcap_replay_plan.md`,
`../../../docs/df_carla_scenario_architecture.md` and `../../../docs/df_carla_scenario_layout.md`. Those
docs are **not** rewritten — they record decisions that were correct when made,
and several of them (the scenario/engine split, the feature subfolder layout,
the `yaw_rate` averaging derivation) are carried forward unchanged. Each gets a
forward pointer, per the pointer-vs-historical rule established in
`../../../docs/df_carla_tools_relocation_plan.md` §5.

---

## 0. What this is, in one paragraph

Today `df` can be driven by a live world simulator, recorded to a file,
re-executed from that file, and watched in a 2D bird's-eye view. All of that
works. None of it is *structured* — it is one component's private tooling, with
the algorithm's identity (AEB, then BSD) welded into every layer from the C ABI
up to the pixel colours. The next six functions and the whole perception domain
cannot be added to it without editing every file each time. This document
replaces that with a **framework** — a component-agnostic simulation and
visualization platform in its own submodule — and reduces each function's
contribution to a small, declarative plug-in.

---

## 1. Vocabulary — fix this first

The current naming conflates three different operations, which is why the
folder is called `replay/` while the file in it is called `df_dll_sim_mcap.py`.
Freeze these four words; they are used with exactly these meanings everywhere
from here on.

| Term | Meaning | Today |
|---|---|---|
| **sim** | A world model (CARLA, later CarMaker) generates stimuli **live, in the loop**; the SUT is executed against them as they are produced. Non-deterministic — wall-clock paced, server-paced. | `carla_bridge.py` |
| **resim** | The SUT is **re-executed** against **recorded** stimuli. No world server, no wall clock. Deterministic: same recording + same SUT build + same calibration ⇒ same outputs, byte for byte. | `replay/df_dll_sim_mcap.py` (misnamed) |
| **replay** | A **recorded result** is played back with **no computation at all**. Only rendering. | opening an `--export`ed `.mcap` in a viewer |
| **SUT** | *System under test* — the composed set of component DLLs being ticked, plus the calibration project they were initialised with. | one `df_sil.dll` + one `default.yaml` |

Four supporting terms:

- **stimulus** — one tick's complete input set to the SUT (`GenObjectList`,
  `VehDyn`, `VehSig`, later raw sensor frames).
- **observation** — one tick's complete output set (`AebOutputs`, `BsdOutputs`,
  `CompState`…), plus any derived quantity the viewer computes for display only
  (TTC, for example, which no ProPort carries).
- **port freeze** — one port's contents written to the recording for one tick.
  The reference toolchain's `MEAS_FREEZE`; here, one message on that port's
  topic. A recording containing a freeze of *every* port is what makes any cut
  point possible (§5.10).
- **mock** — a stand-in that manufactures a port's data because the component
  that would produce it did not run. Distinct from *measured* (real hardware),
  *truth* (world-model ground truth) and *simulated* (a real component that did
  run) — and tagged as such in the recording, §5.11.

**Two sides, joined by one artifact.** *Producing* a recording and *executing*
one are independent concerns; §5.11 separates them, because today's
`carla_bridge.py` does both at once and that is why it is 983 lines.

**Why it matters beyond tidiness.** "Replay" implies you can seek backwards.
`df_dll_sim_mcap.py`'s own docstring has to apologise for the fact that you
cannot ("forward only, no rewind — `dfExec` is stateful, so 'going back' would
mean literally re-running from cycle 0"). That apology is a symptom of calling
a *resim* a *replay*. §6.4 removes the limitation entirely by separating the
two: resim once into a Session, then replay the Session freely.

---

## 2. What exists today

Facts, not judgements. Line counts as of 2026-07-27.

| File | Lines | Role |
|---|---|---|
| `modules/df/tools/carla/carla_bridge.py` | 983 | CARLA connect, spawn, actor motion, frame conversion, `GenObjectList`/`VehDyn` synthesis, `dfExec` call, console log, recording, end conditions, scenario resolution, CLI |
| `modules/df/tools/carla/actor_behaviour.py` | 136 | Declarative lateral motion profiles |
| `modules/df/tools/carla/frame_convert.py` | 61 | World frame → ego frame |
| `modules/df/tools/carla/df_ctypes.py` | 104 | ctypes mirror of `df_interface_c.h` |
| `modules/df/tools/carla/mcap_recorder.py` | 99 | mcap writer + chase camera |
| `modules/df/tools/carla/replay/df_dll_sim_mcap.py` | 381 | Resim driver, `--viz`/`--step`/`--export`, CLI |
| `modules/df/tools/carla/replay/viz.py` | 562 | OpenCV BEV canvas + tkinter inspect popups |
| `modules/df/tools/carla/replay/foxglove_stream.py` | 113 | Foxglove live server, two signal channels + video |
| `modules/df/scripts/df_sim_gui.py` | 647 | tkinter launcher that shells out to the two CLIs |
| `modules/df/docs/bsd/py/bsdviz/**` | 1322 | matplotlib figure library: calibration reader, BEV axes factory, palette, symbols, annotations, coverage, ego geometry, zone, sensors |
| **Total** | **~4400** | |

Plus 18 scenario YAMLs under `modules/df/tests/carla_scenarios/<feature>/` and
recordings under `tests/carla_testruns/<feature>/`.

This is a real, working, live-verified stack. Several of its decisions are
good and are **kept**: the engine-vs-test-data split, the feature subfolder
layout, deferred imports so a console run needs no GUI dependency, the
`DfReqBuf`/`DfProBuf` shape as the wire form of `ReqPort`/`ProPort`, the
declarative `lateral_profile` phase list, and the API-version check at DLL load.

---

## 3. The scalability defects

Eleven, each stated as an observable fact plus what breaks when the roadmap
arrives. This list is the requirements set for everything after it.

### D1 — The C ABI grows a parameter pair per function

`df_interface_c.h` declares

```c
int dfExec(void* handle, double dtS,
           const DfReqBuf* objects, const DfReqBuf* egoDyn, const DfReqBuf* vehSig,
           DfProBuf* aebOutputs, DfProBuf* bsdOutputs,
           DfProBuf* aebCompState, DfProBuf* bsdCompState);
```

`dfApiVersion()` already went 1 → 2 when BSD landed, growing `dfExec` from five
parameters to nine. `../../../docs/df_sil_dll.md` rule 11 predicted this in writing:
*"`fnExec()`'s parameters are hardcoded to AEB's specific ports — there is no
generic/variadic buffer mechanism."* With ACC, LCA, LDW, LKA and rear-safety
functions on the roadmap, that signature reaches 17+ parameters, every one of
them a breaking ABI change that also edits `df_ctypes.py`, `sil_host/main.cpp`,
`carla_bridge.py` and `df_dll_sim_mcap.py`. The same rule flags a second,
related unknown it cannot express: front-vs-rear object port differentiation
(`/front/objects` vs `/rear/objects`).

### D2 — The renderer takes one keyword argument per function

`viz.py`'s entry point is

```python
def build_bev_frame(objects_msg, outputs, veh_dyn_msg=None,
                    bsd_outputs=None, bsd_calib=None) -> np.ndarray
```

`outputs` is AEB-typed and positional; BSD was bolted on as two keywords with
an explicit contract that the AEB path stays byte-identical. That contract does
not survive a third function, let alone a seventh. There is no registry, no
layer concept, no way for `df` to add a function's visualization without
editing a shared file — and no way for `perception-core` to add anything at all.

### D3 — Geometry is hardcoded, while the real numbers sit in YAML

```python
OBJECT_LENGTH_M, OBJECT_WIDTH_M = 4.5, 1.8
EGO_LENGTH_M, EGO_WIDTH_M = 4.3, 1.8
```

Meanwhile `modules/shared_config/projects/<project>/vehicle/ego_params.yaml`
carries `EGO_LENGTH_M: 4.5`, `EGO_WIDTH_M: 1.8`, `EGO_WHEELBASE_M: 2.7`,
`EGO_OVERHANG_FRONT_M: 0.9` — the real, project-scoped values — and
`src/project/<project>/default.yaml` carries `BSD_CLASS_LENGTH_M_MOTORCYCLE:
2.10`. So the ego box on screen is a different vehicle from the one the
algorithm is calibrated for, and a motorcycle target renders as a car.

The need is already conceded in code: `_draw_ego_box()` grew a `bsd_calib`
branch that draws the *real* asymmetric body (`x_rear = -0.90`, `x_front =
+3.60`) with a comment explaining that the cosmetic symmetric box "puts the
zone's own landmarks at the wrong place relative to what's on screen". That
is the correct behaviour, implemented as a per-function special case instead of
as the general rule.

**This is the user-stated headline requirement**: the picture must be a
function of the project's configuration, resolved at run time.

### D4 — Runtime code reaches into a docs folder

```python
sys.path.insert(0, str(DF_ROOT / "docs" / "bsd" / "py"))
from bsdviz import calib as bsdviz_calib
```

`bsdviz` is the more mature of the two visualization libraries — it has a
calibration reader, a BEV axes factory that cannot be bypassed, a semantic
palette, a symbol table and a figure registry — but it lives under `docs/`
because it was built to generate 53 document figures. The live viewer borrows
from it through a `sys.path` injection, and where the borrowed API is
insufficient it hardcodes around it: `_bsd_project_sensor()` selects the sensor
pose by comparing `bsd_calib.project` to the string `"2w_base"`, because
`bsdviz.calib.Calibration` exposes no sensor-pose accessor.

### D5 — Two rendering stacks with no shared vocabulary

The BSD zone is drawn twice: `viz.py` `COLOR_BSD_ZONE = (60, 200, 230)` (OpenCV
BGR) and `bsdviz/palette.py` `ZONE_FILL = "#ffe08a"` / `ZONE_EDGE = "#b8860b"`
(matplotlib hex). Two coordinate helpers (`_to_px()` vs `canvas.bev_axes()`),
two ego-body renderers, two grid styles. A reviewer comparing a requirement
figure against a live run is comparing two different pictures of the same
geometry, and neither one is authoritative.

### D6 — The viewport is a constant

```python
CANVAS_WIDTH_PX, CANVAS_HEIGHT_PX = 900, 700
PX_PER_METER = 10.0
ORIGIN_PX = (450, 620)   # ego near the bottom, forward is up
```

Fixed size, fixed scale, fixed anchor, chosen for AEB's forward-looking
geometry. For BSD the region of interest is *behind and beside* the ego, so the
top 88% of the canvas is empty road and the zone is squeezed into the bottom
strip. There is no pan, no zoom, no fit, no rotation, no follow mode, no view
preset. For LCA (50 m rear zone) and ACC (150 m forward) the same constant
cannot serve both.

### D7 — No time transport

Playback is `time.sleep(dt_s)` in the tick loop; `--step` blocks on a keypress;
seeking backwards is impossible by construction. The `--export` flag exists
purely to work around this — it writes an mcap so that a *different tool*
(Foxglove Studio) can provide the scrub bar the viewer lacks. That is the right
instinct and the wrong place to solve it.

### D8 — Three incomplete views of one run

The live OpenCV window has the spatial truth but no seek, no share, no history.
The live Foxglove stream has seek-ish playback and plots but **no spatial
scene** — the 3D `SceneUpdate` design was tried and dropped after a frame-tree
bug (`../../../docs/df_carla_viz_plan.md` §2 design #2). The exported mcap has seek and share
but again no spatial scene. So no single artefact answers "what did the
algorithm see and decide at t = 3.2 s", and the one that comes closest cannot
be sent to anyone.

### D9 — Everything is `df`'s private property

The framework — clock, tick loop, mcap I/O, canvas, palette, ctypes binding,
GUI — is 100% inside `modules/df`. `perception-core`, `perception-lane`,
`planning` and `vdy` have no path to any of it except copy-paste, which
`R-BUILD-6` exists to prevent for build machinery and which is no more
acceptable here.

### D10 — The scenario file is four files in a trench coat

```yaml
carla:  {host, port, map}          # world model binding
ego:    {blueprint, speed_mps, …}  # scenario content
actors: [...]                      # scenario content
df:     {dll_path, config_path}    # SUT binding
object_range_m: 80                 # sensor model
num_object_slots: 50               # sensor model
end_condition: {...}               # run control
roll_fault: {...}                  # fault injection
```

Four independent concerns in one document with no schema and no version. The
`carla:` block makes every scenario CARLA-specific even though nothing about a
"target merges in at 0.25 m/s" is; plan.md item 4 (CarMaker) will discover this.

### D11 — Expectations are prose

18 scenarios, zero assertions. The expected outcome of each is written as a `#`
comment at the top of its YAML, which `carla_bridge.py --list` prints and
`df_sim_gui.py` shows as a hover tooltip. Two pieces of tooling already parse
that comment — the strongest possible signal that the expectation wants to be
data. Nothing verifies it, so a regression is caught only by a human reading a
console stream.

---

## 4. Design principles

Six, in priority order. Every structural decision below traces to one.

1. **One intermediate representation between "what happened" and "how it is
   drawn."** A function contributes geometry in metres; renderers contribute
   pixels. Neither knows the other. (→ D2, D5, D8)
2. **Framework at the root, content in the component.** Exactly the
   single-source-at-root principle the `.claude` layer already runs on: the
   platform is authored once in its own submodule; `df` contributes plug-ins,
   `perception-core` contributes plug-ins. (→ D9)
3. **Configuration is the source of geometry.** Nothing physical is a Python
   constant. Ego body, object footprints, sensor poses and FOVs come from the
   project's YAML, resolved per run. (→ D3)
4. **Named, discovered ports — never positional, never a central roster.** The
   same reasoning as `R-VAR-2` (no central module roster): a component
   *declares* its ports; the host *discovers* them. Adding a function is a
   pure addition. (→ D1, D10)
5. **Resim is deterministic and cheap; compute once, look many times.** Separate
   *executing* the SUT from *viewing* the result. (→ D7)
6. **Every expectation is data, and the same data drives the viewer marker and
   the CI assertion.** (→ D11)

---

## 5. The architecture

### 5.1 Layers

```
 ┌───────────────────────────────────────────────────────────────────────┐
 │ L5  FRONT ENDS      sim GUI  ·  sim CLI  ·  notebooks  ·  CI runner   │
 ├───────────────────────────────────────────────────────────────────────┤
 │ L4  RENDERERS       interactive viewer  ·  matplotlib (print)  ·      │
 │     & SINKS         Foxglove SceneUpdate  ·  mcap  ·  console  ·      │
 │                     PNG / video  ·  expectation evaluator             │
 ├───────────────────────────────────────────────────────────────────────┤
 │ L3  SCENE           Scene = ordered Layers of frame-typed, metre-      │
 │     (the IR)        valued Prims with semantic style tokens.           │
 │                     Built by LayerProviders from one Tick.             │
 ├───────────────────────────────────────────────────────────────────────┤
 │ L2  SESSION         Runner: for each stimulus → Pipeline.exec → Tick.  │
 │     & RUNNER        Session = the ordered Ticks + the run manifest.    │
 ├───────────────────────────────────────────────────────────────────────┤
 │ L1  SOURCES         StimulusSource: carla | mcap | carmaker | synth    │
 │     & SUT           Pipeline: ordered SilComponents, wired by name     │
 ├───────────────────────────────────────────────────────────────────────┤
 │ L0  CONTRACTS       interfaces protos · shared_config project data ·   │
 │                     the generic SIL C ABI · the port manifest schema   │
 └───────────────────────────────────────────────────────────────────────┘
```

Each layer depends only downward. The two load-bearing interfaces are **L1↔L2**
(the `Tick`) and **L3↔L4** (the `Scene`).

### 5.2 The Tick — L1↔L2

```python
@dataclass(frozen=True)
class Tick:
    index: int                     # 0-based cycle number
    t_s: float                     # elapsed time from run start
    dt_s: float                    # gap since the previous tick
    stimulus: Mapping[str, Message]    # port name -> parsed protobuf
    observation: Mapping[str, Message] # port name -> parsed protobuf
    truth: Mapping[str, Any]           # ground truth from the world model, if any
    aux: Mapping[str, Any]             # camera frames, per-component status, timings
```

Everything downstream reads a `Tick` and nothing else. `stimulus` and
`observation` are keyed by **port name** (`"objects"`, `"aeb.outputs"`,
`"bsd.outputs"`), which is what makes L1 and L3 both function-agnostic.

`truth` matters more than it looks: today the CARLA bridge *is* the perception
system — it synthesises `GenObjectList` from actor transforms. Once
`perception-core` is in the pipeline, ground truth becomes a separate,
independently drawable thing, and the difference between `truth` and
`observation` is exactly what a perception engineer needs to see. Keeping the
slot from day one costs nothing and makes §7 a pure addition.

### 5.3 The Scene — L3↔L4 (the central decision)

A `Scene` is what to draw for one tick, expressed in **metres, in a named
frame, with semantic style tokens** — never pixels, never colours.

```python
@dataclass(frozen=True)
class Scene:
    t_s: float
    layers: tuple[Layer, ...]

@dataclass(frozen=True)
class Layer:
    id: str            # "bsd.zone.left", "aeb.corridor", "perception.tracks"
    group: str         # "bsd" | "aeb" | "perception" | "ground_truth" | "world"
    label: str         # human text for the layer panel
    default_on: bool
    z: int             # draw order within the scene
    prims: tuple[Prim, ...]

@dataclass(frozen=True)
class Prim:            # one of: Polyline Polygon Box Circle Points Text
    frame: str         #   Arrow Grid Heatmap Image
    style: str         # semantic token, e.g. "zone.entry", "object.critical"
    pick_id: str | None    # selectable? then the inspector asks its layer for fields
    ...                    # geometry fields, all in metres
```

Five properties are doing the work:

- **Metres in a named frame.** `"ego"` is the default (origin at the rear-axle
  centre, +x forward, +y left — `R-COORD-1`). `"world"`, `"sensor:<id>"` and
  `"image:<cam>"` also exist. A renderer owns the frame→pixel transform; a
  layer provider never computes a pixel. `_to_px()` disappears from the ~40
  call sites that use it today.
- **Semantic style tokens, not colours.** `style="zone.entry"`, not
  `(60, 200, 230)`. One theme module maps tokens to colour + line style + hatch
  + marker, per output medium. This is what makes D5 fixable: the live viewer's
  dark theme and the document figure's light/print theme are two theme tables
  over one scene.
- **Layers are named and grouped, with a default visibility.** Straight from
  the reference measurement stack's display-list API, whose draw entry point is
  `DrawStartNewGroup(group, subgroup, active_on_startup)` — a pattern with two
  decades of production use behind it. The layer panel (§ visualization spec)
  falls out of this for free, and so does a per-function verbosity level.
- **`pick_id` makes selection a scene-level concept**, so click-to-inspect works
  for a zone corner or a lane polyline, not only for the two entity types
  `viz.py` currently hit-tests.
- **Frozen and serializable.** A `Scene` can be written into the recording, sent
  to Foxglove as a `SceneUpdate`, diffed between two runs, or golden-tested
  against a stored reference. Rendering becomes reproducible, which is what
  makes document figures and live views provably identical.

**A layer provider is the entire contribution a function makes to the viewer:**

```python
@layer_provider(group="bsd", requires=["bsd.outputs", "objects"])
def bsd_layers(tick: Tick, model: ProjectModel) -> Iterable[Layer]:
    ...
```

Discovered by import, exactly as `bsdviz`'s `@figure` registry is discovered
today, and for the same stated reason (`R-VAR-2`: a missing central roster is
unrepresentable by design). Adding LCA's visualization is one new file in
`modules/df/sim/layers/lca.py` and zero edits anywhere else. That single
sentence is the answer to D2.

### 5.4 The Pipeline — L1

Detailed in [sim_sil_contract.md](sim_sil_contract.md); the shape:

```yaml
# a pipeline is data
pipeline:
  - component: perception-core
    library: perception_core_sil.dll
    config:  projects/{project}/perception.yaml
    inputs:  {camera_front: source.camera_front, radar_rear: source.radar_rear}
  - component: df
    library: df_sil.dll
    config:  src/project/{project}/default.yaml
    inputs:  {objects: perception-core.gen_object_list,
              egoDyn:  source.veh_dyn,
              vehSig:  source.veh_sig}
```

Today's runs are the one-element case. Nothing about the runner, the recorder,
the viewer or the GUI changes when the second element appears — which is the
whole point of §7.

### 5.5 The project model — L0, and the answer to D3

```python
model = ProjectModel.load(project="base")
model.ego         # EgoModel   — from shared_config .../vehicle/ego_params.yaml
model.objects     # ObjectModel — footprint per GenObject.Classification
model.sensors     # SensorModel — pose, FOV, range, per sensor id
model.cameras     # CameraModel — intrinsics + extrinsics, for image overlays
model.calib       # raw key→value view of the project's default.yaml sections
```

`EgoModel` computes the asymmetric body **once**, from real parameters:

```
x_front =  EGO_WHEELBASE_M + EGO_OVERHANG_FRONT_M
x_rear  =  x_front - EGO_LENGTH_M
half_w  =  EGO_WIDTH_M / 2
```

for `base`: `x_front = +3.60`, `x_rear = -0.90` — matching the values
`viz.py`'s BSD branch currently obtains via `bsdviz.egogeom`. Promoting that
from a BSD special case to *the* ego model is the whole of the fix.

`ObjectModel` resolves a footprint in this precedence order:

1. `GenObject.geometry.shape_point_coordinates`, when perception actually fills
   it (the item parked in `../../../docs/df_carla_viz_plan.md` §6 — this is where it lands);
2. the project's class-footprint table, keyed by
   `GenObject.attributes.e_classification`;
3. a declared fallback, drawn with a distinct "assumed geometry" style token so
   a viewer can *see* that the box is a guess rather than a measurement.

**Where each of these already lives — corrected 2026-07-27.** An earlier draft
of this section proposed migrating sensor poses and class footprints into
`shared_config`. That was wrong on both counts and is retracted:

| Data | Authoring home | Read by the DLL? | Consumers |
|---|---|---|---|
| `EGO_LENGTH_M`, `EGO_WHEELBASE_M`, … | `shared_config/projects/<p>/vehicle/ego_params.yaml` | yes (`bsd_zone.cpp:18`) | `df` **and** `vdy` — genuinely shared |
| `BSD_SENSOR_<i>_POSE_*`, `_FOV_*`, `_RANGE_*` | `df`'s `src/project/<p>/default.yaml` | **yes** (`bsd_params.cpp:119-122`) | `df` only |
| `BSD_CLASS_LENGTH_M_*`, `_WIDTH_M_*` | `df`'s `src/project/<p>/default.yaml` | **yes** (`bsd_params.cpp:96-97`) | `df` only |

Sensor poses, FOVs, ranges and class footprints are **already real runtime
calibration that the DLL already reads**, and they already sit in the right
place. Moving them to `shared_config` would have contradicted
`../../../docs/shared_config_plan.md` §1's frozen decision — *"`df`'s own
`projects/<name>/default.yaml` … permanently local to `df`, never a
`shared_config` candidate"* — and would have promoted single-consumer data to a
shared home, which is the same mistake `R-MATH-2`'s two-consumer rule exists to
prevent elsewhere.

**The real defect is narrower, and is a duplicate rather than a location.**
`bsdviz/sensors.py` hardcodes the sensor poses as Python constants `P3`/`P4`/
`P5`, and `viz.py`'s `_bsd_project_sensor()` selects between them with
`if bsd_calib.project == "2w_base"`. The code's own comment concedes what that
means: the constants are *"confirmed byte-identical to base/2w_base's own
`BSD_SENSOR_*` calibration (checked 2026-07-27)"* — i.e. a second copy of
calibration the DLL already loads, kept in agreement by hand. The fix is to
**delete the copy and read the bundle**, not to move anything. `SensorModel` and
`ObjectModel` therefore source from the bundle's `project.yaml`; no
`shared_config` change is required, and none is scheduled.

**Promotion trigger, recorded rather than acted on.** Sensor keys are prefixed
`BSD_*` today. The moment a second function or component needs the *same
physical sensor* (a front radar shared by ACC and AEB, or `perception-core`
needing the rear-corner pose), that duplication is the trigger to promote sensor
mounting into `shared_config/projects/<p>/vehicle/sensors.yaml` — same
two-consumer discipline used everywhere else in this repo. Not before.

### 5.6 Configuration delivery — the packed bundle

**Decided 2026-07-27.** Reopens and reverses plan.md item 19's
"keep the pointer" decision of 2026-07-22 (`../../../docs/shared_config_plan.md` §10).
The reversal is deliberate and the reason is new, so it is stated in full.

#### Why the earlier decision no longer holds

Item 19 weighed *keep an absolute compile-time pointer* against *copy into the
build output and resolve relative to the binary*, and kept the pointer because
SIL had no shipping consumer and production uses a different mechanism anyway.
Both facts are still true. What changed is that this architecture creates a
**second reader of the same configuration**, and today the two read different
files:

| Reader | Reads |
|---|---|
| `df_sil.dll` | `ADAS_EGO_PARAMS_PATH` — an absolute path baked at compile time into the Conan cache (or an editable checkout) |
| the viewer (`bsdviz.calib.Calibration`) | the **source checkout**, located by walking up from its own file (`DF_ROOT = THIS_DIR.parents[3]`) |

In editable mode those coincide. After a `conan create` they do not. Edit a
YAML without rebuilding and the viewer draws the new number while the DLL used
the old one — silently, with nothing to detect it. That breaks the single
property everything here rests on: **the picture must show what the algorithm
actually did** (§4 principle 1, `R-SIM-7`).

Two further defects found while checking this, both closed by the same change:

- **`src/project/<p>/default.yaml` is not Conan-resolved at all.** The host
  passes it at run time (`DEFAULT_CONFIG_PATH = DF_ROOT / "src" / "project" /
  "base" / "default.yaml"`), so `df`'s own per-function calibration is read from
  the *working tree*, and the DLL's behaviour depends on checkout state rather
  than on the build.
- **The two halves can silently mismatch.** `ADAS_EGO_PARAMS_PATH` is baked per
  `-DADAS_PROJECT`, but `--config-path` is free at run time. Passing
  `cus1/default.yaml` to a `base`-built DLL yields cus1 function calibration
  with base ego params — a combination that exists in no project.

#### The admission rule — real runtime configuration only

**A file enters the bundle if and only if some component's DLL reads it at run
time.** Nothing simulation-specific ever enters the bundle, and nothing
simulation-specific ever enters `shared_config`. `shared_config` is
**real-vehicle / runtime configuration**; the bundle is the ECU's own view of
the world, packaged.

| Kind | Example | Home | In the bundle? |
|---|---|---|---|
| Real vehicle geometry | `EGO_WHEELBASE_M` | `shared_config/.../vehicle/ego_params.yaml` | **yes** |
| Real function calibration | `BSD_ZONE_LATERAL_OUTER_M` | `df`'s `src/project/<p>/default.yaml` | **yes** |
| Real sensor mounting / FOV / range | `BSD_SENSOR_0_POSE_YAW_DEG` | same | **yes** |
| Real class-footprint assumptions | `BSD_CLASS_WIDTH_M_MOTORCYCLE` | same | **yes** |
| World-model binding | `map: Town04`, `spawn_point_index: 54`, `vehicle.tesla.model3` | the scenario's `world.carla:` block | **no** |
| World-model engine constants | z-clearance `0.05`, `TARGET_HZ`, `REFRESH_DISTANCE_M`, blueprint→class catalogue | `modules/sim/…/sources/carla/` | **no** |
| Sim sensor modelling | `object_range_m`, `num_object_slots`, noise, latency, dropout, occlusion model | `modules/df/sim/sensor_models/*.yaml` | **no** |
| Fault injection | `roll_fault:` | the scenario's `run.faults` | **no** |

Two consequences worth stating, because both will otherwise get "helpfully"
unified later:

- **`BSD_SENSOR_0_RANGE_MAX_CAR_M: 80.0` and `sensor_model.object_range_m: 100.0`
  are different numbers for different jobs** — the first is what the ECU
  believes its sensor can see, the second is what the stimulus generator chooses
  to synthesise. They must never be merged, and a scenario that sets the second
  below the first is a deliberate, legitimate test.
- **The drawn ego will not match the CARLA vehicle, and that is correct.**
  `ego_params.yaml` is a placeholder mid-size sedan; scenarios spawn
  `vehicle.tesla.model3`. Once the viewer draws the ego from the bundle, the BEV
  box and the chase-camera vehicle differ in size. Do **not** "fix" this by
  reading CARLA's bounding box into `ego_params.yaml` — the viewer shows the
  ECU's view, and a visible disagreement means the calibration does not match
  the test vehicle, which is information.

#### The bundle

One **atomic, hashed configuration bundle per (project, build)**, written into
the build output beside the library:

```
ws/df-base-sil-vs2026/.../Release/
  df_sil.dll
  config/
    project.yaml              ← src/project/<project>/default.yaml
                                 (incl. BSD_SENSOR_*, BSD_CLASS_* — already
                                  read by the DLL, already in the right place)
    vehicle/ego_params.yaml   ← shared_config (df + vdy — genuinely shared)
    df_sil.ports.yaml         ← the port manifest (C1)
    bundle.sha256             ← hash over the above, in a declared order
```

That is the whole bundle. It needs no new `shared_config` content: everything
the viewer must know to draw a truthful picture is already runtime calibration
the DLL reads.

- **Copied into the build output, not compiled into the DLL.** Baking it in as
  a resource is closest to the production model but kills the
  edit-a-value-and-re-run loop, which is precisely the BSD calibration
  workflow. Production legitimately differs (Adaptive AUTOSAR frozen
  parameters, `CLAUDE.md` rule 6, `R-SIL-1`) — this is a **SIL delivery
  property**, not a production one.
- **Authoring homes are unchanged.** `R-VAR-4` still holds: calibration is
  authored under `projects/<name>/` and the build selects one project via
  `-o project=` / `-DADAS_PROJECT`. The bundle is a *build output*, never a
  second place to edit a value.
- **Resolution order at run time:**
  1. an explicit path from the host — always wins, so a deliberate
     cross-project experiment stays possible;
  2. `adasInit(NULL)` → `<library_dir>/config/`, resolved from the module's own
     path (`GetModuleFileNameW` / `dladdr`). Platform-specific disk discovery in
     the composition root is exactly where `R-ARCH-5` puts it.
- **`adasManifest()` reports `project` and `config_bundle_sha256`**, so the run
  manifest populates itself, the viewer loads the same bytes the DLL loaded, and
  a mismatch between an explicit override and the built project is a **warning
  the framework raises** rather than a silent wrong answer.
- **The bundle is embedded in the recording** (a few kB of YAML). `sim view` on
  someone else's `.mcap` then renders correctly on a machine with no build, no
  Conan cache and no checkout — which is also the §10.2 relocatability trigger,
  reached as a by-product rather than as the goal.

`ProjectModel.load()` therefore resolves in this order: the recording's embedded
bundle → the SUT library's `config/` bundle → the source checkout (development
fallback, flagged in the HUD as unverified provenance). Until the bundle exists
(stage C5), only the third path is available and the divergence above is real —
so the viewer states which source it used, from day one.

### 5.7 Repo home — the `modules/sim` submodule

**Decision: a new sibling submodule, `modules/sim`, package name `adas-sim`.**

Rejected alternatives, with the reason:

| Option | Rejected because |
|---|---|
| Keep it in `modules/df/tools/` | D9 verbatim. `perception-core` cannot reach it, and every cross-component change becomes a `df` change. |
| Put it in `modules/sil_host` | `sil_host` is a C++ *executable host*. Merging a Python framework into it conflates "a host that ticks DLLs" with "the framework that hosts, records and draws". Related (§9), not the same. |
| Put it in `modules/interfaces` | `interfaces` is the contract repo — schemas and headers only (`R-IFACE-1`). A viewer is not a contract. |
| A folder at the superproject root | Breaks the one-repo-per-component model (`R-GIT-1`) and cannot be consumed by a partially-cloned checkout. |

The split that makes it work:

```
modules/sim/                          FRAMEWORK — component-agnostic, no function names
  src/adas_sim/
    core/       clock · runner · session · manifest · errors
    contracts/  sil_abi · component · pipeline · ports        (→ sim_sil_contract.md)
    model/      project · ego · objects · sensors · cameras   (→ §5.5)
    io/         mcap · (rosbag · mdf4 · carmaker…)            format CODECS (R-SIM-14)
    sources/    carla · carmaker · synthetic                  world-model CLIENTS
    sinks/      console · image · video                       (recordings are written by io/)
    scene/      types · registry · builder · frames           (→ §5.3)
    render/     theme · viewer · matplotlib · foxglove · image_view
    view/       viewport · transport · layers · inspector · timeline · measure
    check/      expect · report                               (→ sim_scenarios…md)
    app/        cli · gui
  docs/       the five design documents + the implementation plan
  tests/
  README.md · CLAUDE.md · conanfile.py · pyproject.toml

modules/df/sim/                       CONTENT — df's plug-ins only
  layers/         common.py · aeb.py · bsd.py · lca.py · …
  pipelines/      df_only.yaml · algo_test_df.yaml
  sensor_models/  ground_truth_ideal.yaml · …
  viewpoints.yaml
  df_sil.ports.yaml                   generated port manifest (checked in)

modules/perception-core/sim/          CONTENT — later, same shape
  layers/       detections.py · tracks.py · lanes.py
  perception_core_sil.ports.yaml
```

The rule, stated so it cannot erode: **`modules/sim` must never contain the
strings `aeb`, `bsd`, `lca`, `acc`, `ldw` or `lka`.** A grep for them is the
enforcement, cheap enough to be a CI check and a code-review reflex. It is the
same test `R-ARCH-2` uses for middleware-free algorithm code, applied here.

`modules/df/tools/carla/` does not survive: `carla_bridge.py` decomposes into
`adas_sim.sources.carla` (framework) plus its scenario data (already test data,
already in the right place). `df_ctypes.py`, `viz.py`, `foxglove_stream.py`,
`mcap_recorder.py` and `df_dll_sim_mcap.py` are all fully absorbed by framework
modules. `df_sim_gui.py` becomes `adas_sim.app.gui`, which is then
component-agnostic in the same sense `scripts/build_gui.py` already is
(`R-BUILD-4`).

`bsdviz` splits: its generic half (`calib`, `canvas`, `palette`, `frame`,
`egogeom`, `symbols`, `annotate`, `logs`, the `@figure` registry) becomes
`adas_sim.model` + `adas_sim.render.matplotlib`; its BSD half (`zone`,
`coverage`, `sensors`, `lean`, `kinematics`, `check`) becomes
`modules/df/sim/layers/bsd.py` plus figure content that stays under
`docs/bsd/py/`. The 53-figure driver keeps working, on top of the shared
framework — and the `sys.path.insert` into a docs folder (D4) is deleted rather
than tidied.

### 5.8 Placement map — what lives where

The complete allocation, because the rework touches three repos and "where does
this go" is the question that will keep recurring.

#### The decision rule, in order

1. **Is it cross-cutting knowledge, backlog, or superproject orchestration?**
   → the **superproject root**. The root holds **no source code** — only
   `../../../plan.md`, cross-cutting `docs/`, the `.claude/` AI layer, the build
   dispatcher, toolchains and CI.
2. **Does it name a function (`aeb`, `bsd`, `lca`, …) or belong to exactly one
   component?** → **that component's submodule**.
3. **Otherwise it is framework** → **`modules/sim`**.
4. **Exception — build machinery** (`conanfile.py`, `scripts/build.py`,
   `build.bat`/`.sh`, `scripts/build_gui.py`, `.clang-format`): byte-identical
   *copies* in every component, per `R-BUILD-1..6`. Shared knowledge is
   referenced; shared machinery is duplicated. Do not confuse the two.

#### Superproject root — `1v-superproject/`

| Path | Holds | Changed by this rework |
|---|---|---|
| `../../../plan.md` | the backlog, one item per open problem | item 25 added; items 1/2/4/19 annotated |
| `docs/*.md` | cross-cutting design docs **not owned by one module** | the 6 `df_carla_*.md` get forward pointers; this rework's own 5 docs live in `modules/sim/docs/` instead — see below |
| `.claude/**` | rules, skills, workflows, templates, routing — root-canonical | `rules/sim.md`, 3 skills, 1 workflow, 1 template |
| `scripts/` | cross-component orchestration (build dispatcher, publish, guards) | unchanged |
| `toolchains/`, `ci/`, `ws/` | toolchain files, CI, build workspaces | unchanged |
| `modules/` | the submodules themselves | gains `modules/sim` |

**Never at root:** component source, component tests, scenario data, recordings,
calibration.

**Docs follow their module.** A module's own design docs live with the module —
`modules/sim/docs/` for this rework's five documents, exactly as
`modules/df/docs/bsd/` holds BSD's requirement stack. Root `docs/` keeps what no
single module owns: the build/variant model, the AI-layer spec, naming, and
historical plans for work already absorbed elsewhere. The test is *ownership*,
not *audience*: `sim`'s docs are read by every component but authored by one
module, so they live in it. (`plan.md` stays at root and links across — a
partial clone without `modules/sim` sees the item and the pointer, the same way
it already does for `modules/df/docs/bsd/`.)

#### `modules/sim` — NEW, the framework

Everything component-agnostic. No function names, ever (`R-SIM-1`).

```
modules/sim/
  docs/       the five design documents for this rework  ← you are here
  src/adas_sim/
    core/       clock · runner · session · manifest
    contracts/  sil_abi · component · pipeline · ports      ← was df_ctypes.py
    model/      project · ego · objects · sensors · cameras ← was bsdviz.calib/egogeom
    io/         mcap · (rosbag · mdf4 · carmaker…)          ← format CODECS, §3.0 of
                                                              sim_resim_and_recording.md
    sources/    carla · carmaker · synthetic                ← WORLD-MODEL clients,
                carla/catalogue.yaml (blueprint → class)      was carla_bridge.py
    sinks/      console · image · video                     ← non-recording outputs
                                                              (recording writing is io/)
    scene/      types · registry · builder · frames         ← NEW (the Scene IR)
    render/     theme · viewer · matplotlib · foxglove      ← was viz.py, foxglove_stream.py,
                                                              bsdviz.canvas/palette
    view/       viewport · transport · layers · inspector · timeline · measure ← NEW
    check/      expect · report                             ← NEW
    app/        cli · gui                                   ← was df_sim_gui.py
  tests/  README.md  CLAUDE.md  pyproject.toml  sim_gui.bat
```

No `CMakeLists.txt` and no `build.bat` — it produces no compiled artifact,
exactly the precedent `shared_config` set (`../../../docs/shared_config_plan.md` §3.3).

**It does have a `conanfile.py` (`adas-sim`) — decision corrected 2026-07-27.**
An earlier draft said pip-editable only, on the grounds that no C++ build
depends on it. That reasoning was wrong because it ignored the partial-clone
requirement (§5.9): `pip install -e ../sim` needs the checkout, so it does not
solve the problem it was chosen for, and no wheel index exists to install from
instead. A Conan package resolved from the existing local remote does solve it,
reuses machinery already proven twice (`adas-interfaces`, `adas-shared-config`),
and follows the same `package_type = "unknown"`, no-`settings`, data-only recipe
shape `shared_config` uses. A consumer declares it in `conf/build.yml`
`requires:` like anything else; `conan editable add` covers local development.

#### `modules/df` — what stays, what leaves, what is new

| Path | Verdict | Note |
|---|---|---|
| `src/component/{aeb,bsd,acc,lca,ldw,lka,common,utils}/` | **stays** | untouched — `../../../docs/df_sil_dll.md` rule 9 |
| `src/platform/df_sil/` | **stays**, extended | gains the generic ABI, the manifest generator, config-bundle packing (C1/C5) |
| `src/platform/{autosar,orin,standalone,tda4vm}/` | **stays** | unaffected |
| `src/project/<p>/default.yaml` | **stays** | df's own calibration — permanently local (`../../../docs/shared_config_plan.md` §1). Includes `BSD_SENSOR_*` / `BSD_CLASS_*` |
| `include/`, `conf/build.yml`, `CMakeLists.txt` | **stays** | |
| `conanfile.py`, `build.bat/.sh`, `scripts/build.py`, `scripts/build_gui.py` | **stays** | byte-identical machinery (`R-BUILD`) |
| `tests/unit/`, `tests/integration/`, `tests/fixtures/` | **stays** | gtest; gains generic-ABI mirror tests |
| `tests/carla_scenarios/<feature>/` | **stays** | test data belongs to the component under test |
| `tests/carla_testruns/<feature>/` | **stays** | recordings, same reason |
| `docs/bsd/{req,ref,images,logs}/` | **stays** | BSD requirements/figures — component-specific |
| `docs/bsd/py/` figure content | **stays** | figure *content*; the driver moves onto the framework (D2) |
| `docs/bsd/py/bsdviz/` | **splits** | generic half → `adas_sim.model`/`render`; BSD half → `df/sim/layers/bsd.py` |
| `tools/carla/**` | **leaves** | → `adas_sim.sources.carla`, `contracts`, `sinks`, `render` |
| `scripts/df_sim_gui.py`, `sim_gui.bat` | **leaves** | → `adas_sim.app.gui`, `modules/sim/sim_gui.bat` |
| **`sim/` — NEW** | | df's contribution to the framework |

```
modules/df/sim/
  layers/         common.py · aeb.py · bsd.py · lca.py …   ← what df draws
  pipelines/      df_only.yaml                              ← how df is composed
  sensor_models/  ground_truth_ideal.yaml · rear_radar_4wr.yaml  ← SIM-only modelling
  viewpoints.yaml                                           ← named BEV presets
  df_sil.ports.yaml                                         ← generated port manifest
```

**Why `sim/` and `tests/` are both in `df` and are not the same thing:**
`tests/` holds **test cases** — what to run and what to expect. `sim/` holds
**df's contribution to the framework** — how df is driven, composed and drawn,
regardless of which case runs. Different change rates, the same reasoning that
put scenario data outside the engine folder in the first place
(`../../../docs/df_carla_scenario_architecture.md` §1).

#### The other submodules

| Module | Role after the rework |
|---|---|
| `modules/shared_config` | **exactly `projects/<p>/vehicle/ego_params.yaml`** — real, genuinely cross-component vehicle data (`df` + `vdy`). No sim data, ever (`R-SIM-9`). No new files from this rework |
| `modules/interfaces` | gains `adas_sil_abi.h` + `component_manifest.proto` (C1) — they are cross-component contracts, so `R-IFACE-1` puts them here |
| `modules/sil_host` | unchanged until C1, then moves to the generic ABI. Stays the no-Python C++ host (§9) |
| `modules/perception-core`, `perception-lane`, `planning`, `vdy` | gain their own `sim/` folder when they have something to contribute — same shape as `df/sim/`, no framework change (§7) |

---

### 5.9 Can a `df`-only clone still resim?

**The objection is right, and the baseline is worse than it looks.** Moving the
framework out of `df` adds a dependency — but "resim with only `df` checked out"
is **already not true today**:

| Today's resim needs | Why |
|---|---|
| `modules/df` | the DLL, the recordings |
| `modules/interfaces`, **checked out *and built*** | `INTERFACES_GENERATED_PY = .../interfaces/build/generated_py`, imported by `sys.path` insert in both `carla_bridge.py` and `df_dll_sim_mcap.py` |
| `modules/shared_config`, checked out (for `--viz`) | `bsdviz/calib.py:19`'s `SHARED_CONFIG_ROOT` |

So the real question is not "does this add a dependency" but "how many
checked-out modules does a resim need, before and after". Three changes already
in this design each remove one:

1. **`adas-sim` is a Conan package** (§5.7) — resolved from the local remote,
   never needing `modules/sim` on disk. Same mechanism `shared_config` was made
   a package for, in its own words: *"so a component's own standalone build can
   resolve it without needing this module checked out as a sibling folder on
   disk."*
2. **`adasManifest()` carries the `FileDescriptorSet`**
   ([sim_sil_contract.md](sim_sil_contract.md) §3.2). The DLL already contains
   every schema it speaks; emitting the descriptor set lets a Python host build
   message classes at run time via `DescriptorPool` + `message_factory`. That
   **deletes the `interfaces/build/generated_py` dependency outright** — no
   `interfaces` checkout, no `-DADAS_GENERATE_PYTHON_PROTO=ON` build, no
   `sys.path` insert, and no `from Bsd__Outputs import bsd_outputs_pb2` anywhere.
3. **The packed config bundle** (§5.6) — the viewer reads calibration from
   beside the DLL, so `shared_config` need not be on disk either.

| | checked-out modules a resim needs |
|---|---|
| today | `df` + `interfaces` (built) + `shared_config` |
| after | **`df`** only, plus a downloaded `adas-sim` package |

Strictly fewer than today, and the one remaining dependency is a package
download rather than a build. Until `adas-sim` is published, the interim cost is
one `git submodule update --init modules/sim` — one command, and the same
interim state `interfaces` and `shared_config` already live in.

### 5.10 Pipeline depth — where the simulation starts

The second scaling question: today a CARLA Python script synthesises
`GenObjectList` and hands it to `df`. Tomorrow the chain runs radar signal
processing → detections → fusion → functions, or camera → perception →
functions. Does the "a Python script makes the objects" approach survive? And
will `sil_host` end up synthesising objects *again*, in C++?

**Reframe: object synthesis is not a source feature. It is a stand-in for a
component that does not exist yet.** Today's CARLA bridge is playing the role of
`perception-core`. Once that is stated, the answer falls out: it is a **pipeline
stage with an alternative implementation**, not a special capability of the
world-model binding.

#### Two orthogonal questions, not one

This is the model the reference measurement/resim toolchain has used for two
decades, and it is worth adopting wholesale: its console presents the component
chain with a **per-component toggle — take this one from measurement, or
simulate it** — and the operator moves the boundary rather than switching tools.

Mapping that onto the pipeline shows a distinction an earlier draft of this
section collapsed. Each stage answers **two** independent questions:

| Question | Field | Values |
|---|---|---|
| Is this stage **executed at all**, or are its outputs **injected**? | `mode:` | `simulate` · `measured` · `off` |
| If executed, **by what**? | `impl:` | `dll:<lib>` · `stub:<name>` · `stubdll:<lib>` |

```yaml
components:
  - name: perception-core
    mode: measured                              # ← the only field you flip
    impl: "dll:perception_core_sil.dll"         #   kept, so flipping back is free
  - name: df
    mode: simulate
    impl: "dll:df_sil.dll"
    inputs: {objects: perception-core.gen_object_list, egoDyn: source.veh_dyn}
```

Keeping `impl:` on a `measured` stage is deliberate: the toggle must be
**reversible without re-authoring the pipeline**, which is the whole ergonomic
point of the reference console. `mode: off` exists for a stage that is neither
run nor injected — its consumers see `valid=0`, which is a real fault-injection
case the ABI already expresses.

| `impl:` | What it is | Python host | `sil_host` |
|---|---|---|---|
| `dll:<lib>` | a real component's SIL library | yes | yes |
| `stub:<name>` | a Python model standing in for a missing component | yes | **no** |
| `stubdll:<lib>` | the same idea, built as a DLL on the generic ABI | yes | yes |

#### The single concept

> **A stage's interface is its port set, and "executed" and "injected" produce
> the same port set. A consumer cannot tell which it got.**

That one invariant is what makes a single tool cover every level. It has three
consequences worth stating separately:

- **Any cut, not one cut.** `mode` is per stage, and wiring is per *port*, so a
  stage can be simulated while one of its inputs comes from a recording:
  `inputs: {objects: measured:/perception-core/gen_object_list, egoDyn: vdy.veh_dyn}`.
  Finer-grained than a single boundary, and the same mechanism.
- **Depth is data.** Ground-truth objects → real perception → RSP in the loop is
  the same pipeline with different `mode`/`impl` values (below), and a
  downstream component's entry is byte-identical across all of them.
- **Real vehicle measurements slot in later unchanged.** When recorded drives
  exist, they are recordings like any other; only a format converter in
  `sources/` is new. The concept does not move.

#### What this requires of a recording

A stage can be `measured` **only if the recording contains its output ports.**
That makes recording completeness the enabler for everything above, and it
amends `R-SIM-6`: record **every stage's inputs *and* outputs**, not just the
source's stimuli. A `--save session.mcap` already does this — it is our
equivalent of a measurement, and a plain sim recording should write all stage
outputs too (they are computed anyway, and the cost is a few kB per tick).

The pipeline loader validates this at load: `mode: measured` against a recording
lacking that stage's topics is a **startup error naming the missing topics**,
and the GUI simply does not offer the choice
([sim_visualization_spec.md](sim_visualization_spec.md) §13).

#### The free comparison this unlocks

When a stage is `simulate` **and** the recording also contains its recorded
outputs, both values exist for every tick. Comparing them is free, and it
answers the question that dominates resim work:

> *"My new build diverges from the reference run — at which tick, on which
> port, by how much?"*

Reported as a per-port, per-tick divergence with the **first** differing tick
called out, and surfaced on the timeline as an event marker. This is the
same machinery as §6.4's A/B diff of two Sessions, applied within one run.

#### Levels, as pipeline data

One chain, four settings of the same two fields. `rsp` and `perception-core`
appear in every row — a stage that is not yet real is `mode: off` or
`mode: measured`, never absent, so the chain itself never changes shape.

| | `rsp` | `perception-core` | `df` | Source must emit |
|---|---|---|---|---|
| **L0** — pure resim of functions | `off` | `measured` | `simulate` | (nothing — recording only) |
| **L1** — today | `off` | `simulate` / `stub:carla_ground_truth` | `simulate` | actor ground truth |
| **L2** — real perception | `off` | `simulate` / `dll:perception_core_sil.dll` | `simulate` | camera frames, radar detections |
| **L3** — RSP in the loop | `simulate` / `dll:rsp_sil.dll` | `simulate` / `dll:…` | `simulate` | raw radar cube |

```yaml
# L1 — today. Moving to L2 edits ONE impl: line; moving to L0 edits ONE mode:.
components:
  - {name: rsp,             mode: off}
  - {name: perception-core, mode: simulate, impl: "stub:carla_ground_truth"}
  - {name: df,              mode: simulate, impl: "dll:df_sil.dll",
     inputs: {objects: perception-core.gen_object_list, egoDyn: source.veh_dyn}}
```

`df`'s own entry is **byte-identical across all four rows**. That is the property
worth protecting, and it is what named ports buy (`R-SIM-4`): a component never
knows, and never needs to know, what produced its inputs.

The **source** correspondingly declares what it *can* emit — `objects_truth`,
`camera/<id>`, `radar_detections`, `radar_cube`, `veh_dyn` — and the pipeline
wires from `source.<x>`. A pipeline that asks for a level the source cannot
produce is a **startup error naming both ends**, not a run that quietly
degrades.

#### On the duplication you are worried about

> *"sil-host pipeline in future will also simulate the objects from code itself
> right"*

**Only if we let it, and the rule prevents it: there is never a second
implementation of the same stand-in.** Two mechanisms cover every case:

- **`sil_host` consumes a recording.** The Python/CARLA path synthesises once,
  writes an `.mcap`, and `sil_host` replays `recording:/source/gen_object_list`.
  One synthesiser, one output, two hosts. This is the default and covers the
  regression case entirely.
- **If a stand-in genuinely must run in C++** — a real-time rig, or a
  Python-free deterministic regression — it is promoted from `stub:` to
  `stubdll:`: built as a DLL exposing the **same generic ABI as any component**,
  and therefore drivable identically by both hosts. Still one implementation,
  in the language it has to be in, and still just a pipeline element.

**Host boundary, stated so it cannot erode:** `sil_host` runs `dll:`,
`stubdll:` stages plus `mode: measured` injection. It never runs a Python `stub:`, and it never
grows its own object generator. A stand-in that `sil_host` needs is a
`stubdll:`, by definition. Driving a *live* CARLA server from `sil_host` is
explicitly out of scope — CARLA's client is Python, no requirement asks for it,
and the recording path already covers what it would buy.

#### What this buys beyond scaling

Because the level is data, the same scenario can be run at several levels and
the results diffed (§6.4's A/B mode): ideal objects versus real perception,
against the *same* function build. The difference in `AebOutputs` is then
attributable to perception rather than argued about — which is the question that
will dominate once `perception-core` is real.

#### The honest limit

Compute stays in the DLLs, so a Python host driving the tick loop is fine. **Data
volume is the constraint**: a radar cube or an uncompressed camera frame per tick
crossing a ctypes boundary is a different regime from a 50-slot object list. The
generic ABI's caller-owned buffers already avoid a copy on the output side, and
sources can hand buffers in by pointer, but level 3 will need measurement before
it is promised. Flagged here, not solved — no component at that level exists.

---

### 5.11 Two sides, one artifact — producing a recording vs. executing one

§5.10 describes **one** of two concerns. They are independent, they are joined
only by the recording, and conflating them is what makes today's
`carla_bridge.py --record` a 983-line file that connects to a world model,
synthesises perception, executes the SUT, prints, and writes a file — four jobs
across both sides at once.

```
  PRODUCTION SIDE                      ARTIFACT                  CONSUMPTION SIDE
  how a recording comes to exist                                 how one is executed & viewed
  ───────────────────────────────      ─────────────────         ───────────────────────────
  real vehicle measurement       ─┐
  CARLA mock (perception, VDY)   ─┤                              per-stage mode: measured|simulate
  CarMaker run                   ─┼──►    .mcap      ──────►     + viewer, expectations, diff
  hand-written synthetic         ─┤    port freezes,             (§5.10)
  a previous session             ─┘    manifest, bundle
```

**The consumption side does not care which producer made the file.** That is
the whole value of putting a serialized artifact between them: a real vehicle
measurement and a CARLA mock are executed by exactly the same tool, with the
same per-stage toggles.

#### The two workflows this makes explicit

**(A) Resim a measurement.** A recording arrives containing a freeze of every
port of the running code — the reference toolchain's `MEAS_FREEZE` of each port
is exactly what our per-port topic is. Every stage can therefore be `measured`
or `simulate`, freely, because every stage's data is present.

**(B) Algo test — manufacture the stimulus, then resim.** No measurement exists.
You *mock* the upstream — perception and VDY from CARLA — **write that to an
mcap, and stop**. Then resim it with the component under test `simulate` and
everything else `measured`:

```yaml
# "isolate df" — the algo-test shape
components:
  - {name: vdy,             mode: measured}   # from the manufactured mcap
  - {name: perception-core, mode: measured}   # from the manufactured mcap
  - {name: df,              mode: simulate, impl: "dll:df_sil.dll"}
```

This is the canonical algo-test configuration and ships as a preset: **every
stage `measured` except the component under test.** The GUI offers it as
*isolate ‹component›* rather than requiring it to be hand-assembled.

#### Which side does a mock belong on?

Both are possible; the choice is not arbitrary.

| | Mock on the **production** side | Mock as a live `stub:` stage (§5.10) |
|---|---|---|
| What happens | its output is frozen into the mcap like any other port | it runs every tick inside the run |
| Determinism | frozen — bit-identical forever | re-runs, and re-derives |
| Shareable / CI-able | yes, it is a file | only if the mock's inputs are |
| Needs the world model at resim time | **no** | yes, if it reads one |
| Right when | the mock is a stand-in for missing perception — **the default** | the mock must react to something computed in the loop (closed loop), or you deliberately do not want to persist it |

**Default to the production side.** Freezing a mock's output makes an algo test a
file plus a pipeline, reproducible on a machine with no CARLA — which is the
point of an algo test. The live `stub:` stage exists for the cases the table's
last row names, not as the normal path.

#### What a recording can and cannot offer

**Which cuts are possible is a property of the recording, not of the tool.**

| Recording | Contains | Cuts available |
|---|---|---|
| real vehicle measurement | freezes of every port | any stage `measured` or `simulate` |
| session recording (from a resim) | source ports + every stage's outputs | any stage |
| **manufactured stimulus** (workflow B) | only the mocked upstream ports | upstream stages `measured`; **the component under test must be `simulate`** — nothing exists to inject |
| today's stimulus recording | `GenObjectList`, `VehDyn`, camera | df must be `simulate` |

The pipeline loader resolves this from the recording's topic index and the GUI
disables what the file cannot support (§13 of the visualization spec). Nothing
here needs a mode the tool has to guess.

#### Per-port provenance — a mock is not a measurement

A manufactured recording and a real one are the same *format*. They are not the
same *evidence*, and a report that calls both "measured" is misleading. So every
recorded port carries a provenance tag alongside its data:

| Tag | Meaning |
|---|---|
| `measured` | captured from real hardware |
| `truth` | ground truth from a world model (exact by construction) |
| `mocked` | synthesised by a stand-in for a component that did not run |
| `simulated` | produced by a real component executing in an earlier run |

The viewer shows it, the run manifest records it, and `sim check`'s report
states it — so "perception was measured" can never quietly mean "perception was
a CARLA mock". This costs one enum per topic and removes an entire class of
misread result.

#### What this means for today's code

`carla_bridge.py` splits along the seam rather than moving wholesale:

| Job | Side | Lands in |
|---|---|---|
| connect to CARLA, spawn, drive actors | production | `adas_sim.sources.carla` |
| CARLA → `GenObjectList`/`VehDyn` synthesis | production (a **mock**, tagged `mocked`) | `adas_sim.sources.carla.mocks` |
| write the mcap | production | `adas_sim.io.mcap` (the codec) |
| call `dfExec`, print, draw | consumption | `core.runner` + the viewer |

and the CLI names the two sides instead of bundling them
([sim_resim_and_recording.md](sim_resim_and_recording.md) §9):
`sim record` produces an artifact and executes nothing; `sim run` produces *and*
executes live (today's `--record` behaviour); `sim resim` executes an existing
artifact.

---

### 5.12 Who owns the loop — and why CarMaker is not a problem

CARLA is a *server*: Python connects as a client and **our runner owns the
loop**. CarMaker is not — it runs as its own executable and owns its own loop.
That difference sounds like it needs new architecture. It does not.

**CarMaker runs as a normal test exe and writes its native results; a format
codec (`adas_sim.io.carmaker`, R-SIM-14) turns those into a recording.** From
there every downstream concern is unchanged — resim at any level, per-stage
`measured`/`simulate`, the viewer, expectations, diff. A CarMaker run becomes a
recording exactly as a real vehicle measurement does, which is §5.11's whole
point: production and consumption are separate sides joined by a file.

So the CarMaker work is **a codec, not an integration**, and it is the only
CarMaker work this design requires.

**Parked — closed loop.** The one thing a file cannot give you is closed loop:
the function's output steering CarMaker's vehicle model, which needs our code
running *inside* their process. If that is ever wanted, the enabling decision is
small and already implied — **a `Pipeline` exposes the same generic ABI as a
single `SilComponent`**, so a foreign host links one thing and gets whatever
depth the pipeline YAML declares. Nothing needs designing until a scenario
actually requires closed loop; today every run is open-loop read-only by
deliberate choice (`../../../docs/df_carla_bridge_blueprint.md`), and plan.md item 6
(actuation + arbiter) does not exist yet.

**The invariant that keeps visualization constant regardless of any of this:**

> **The viewer never talks to a world model, a DLL or a file. It renders a
> `Session`.**

A Session comes from our own runner, or is reconstructed from a recording in
any format. The viewer cannot tell which, so the visualization is **identical**
across CARLA, CarMaker, mcap and a real vehicle measurement. That is not an
aspiration — it follows from the viewer's only input being `Session`, which is
why the Scene IR sits where it does (§5.3).

### 5.13 Extension points — what "easy to add" actually means

The claim "adding X is easy" is only meaningful if it says what must **not**
change. This is that table, and it is the acceptance test for the whole design.

| To add… | You write | You touch | Must **not** change |
|---|---|---|---|
| **A recording format** (rosbag, MDF4/MF4, CarMaker results, a future format) | one `RecordingReader` (+ `Writer` if producing), ~4 methods, registered by extension | `adas_sim.io.<fmt>` | `Session`, pipeline, Scene, viewer, expectations, every layer provider — none of them ever see a format |
| **A world model** (CarMaker, another simulator) | one `StimulusSource` if we drive it, **or** one format codec if it runs standalone and writes results | `adas_sim.sources.<world>` or `adas_sim.io.<fmt>` | the pipeline, the ABI, the viewer, scenarios' `scenario:` block (only `world.<name>:` is new) |
| **A component** (perception-core, RSP, planning) | the generic ABI + a generated manifest in that component; one line in a pipeline YAML | that component's repo | the framework, the host, any other component, the recorder, the viewer |
| **A function inside a component** (LCA, ACC…) | one `ENABLED_FUNCTIONS` entry → manifest line; one `sim/layers/<fn>.py` | that component | the ABI, `adasExec`'s signature, the renderer, the GUI |
| **A renderer** (Qt, matplotlib, Foxglove, image) | one Scene→output adapter | `adas_sim.render.<name>` | the Scene, any layer provider |
| **A viewpoint, sensor model, pipeline, scenario** | a YAML file | that component's `sim/` or `tests/` | any code at all |

If a proposed change would force an entry in the right-hand column, the design
has been violated — that is the check to apply in review, not a feeling about
whether something "seems modular".

---

## 6. How each defect closes

| # | Defect | Closed by |
|---|---|---|
| D1 | ABI grows per function | Named port set + per-component manifest — [sim_sil_contract.md](sim_sil_contract.md) |
| D2 | Renderer grows per function | `LayerProvider` registry over the Scene IR — §5.3 |
| D3 | Hardcoded geometry | `ProjectModel` resolved per run — §5.5 |
| D4 | Runtime imports from `docs/` | `bsdviz` split into framework + content — §5.7 |
| D5 | Two rendering stacks | One Scene, N renderers, one theme table — §5.3 |
| D6 | Constant viewport | `view/viewport` with pan/zoom/fit/presets — visualization spec §4 |
| D7 | No time transport | Two-pass Session + `view/transport` — §6.4 below |
| D8 | Three partial views | Scene → Foxglove `SceneUpdate` + Scene-in-mcap — visualization spec §11.3 |
| D9 | `df`-private | `modules/sim` submodule — §5.7 |
| D10 | Monolithic scenario | Four-section schema — [sim_scenarios_and_expectations.md](sim_scenarios_and_expectations.md) |
| D11 | Prose expectations | `expect:` block + headless evaluator — same doc |

### 6.4 The two-pass Session — how backwards seek becomes possible

The current viewer executes and draws in the same loop, so the frame you are
looking at is destroyed by the act of computing the next one. Because
`dfExec` is stateful, going back means re-running from cycle 0 — correct, and
the reason `--step` is forward-only.

Split the two:

```
pass 1  (resim)   stimuli ──► Pipeline.exec ──► Session = [Tick₀ … Tick_n]
pass 2  (view)    Session[i] ──► LayerProviders ──► Scene ──► Renderer
```

Pass 1 is deterministic and runs at full speed — for reference, a 60 s
recording at 20 Hz is 1200 ticks, i.e. well under a second of `dfExec` calls.
Pass 2 is pure and can be re-run for any `i`, in any order, as often as you
like. Therefore:

- **seek anywhere, instantly, forwards or backwards** — the thing D7 says is
  impossible;
- speed control, loop-over-interval, frame-accurate step;
- toggling a layer, changing the theme or resizing the window **re-renders
  without re-executing**, which is what makes layer toggles feel instant;
- an A/B diff of two Sessions (two SUT builds, or two calibration projects) is
  just two arrays indexed by the same `i`.

Memory cost is bounded and small: a `Tick` holds parsed protobuf messages, and
a 50-slot `GenObjectList` plus outputs is a few kB — a 1200-tick session is
single-digit MB. Camera frames are the exception and are held by reference into
the recording, decoded on demand.

Live **sim** cannot do pass 1 ahead of time — the world is producing stimuli as
you watch. It therefore appends to the Session as it goes: you can seek
backwards into what has already happened, and "live" is simply the tail. Same
code, one flag.

---

## 7. Scaling to perception — one worked instance of §5.10

§5.10 gives the general mechanism (injection level as pipeline data, stand-ins
as stages). This section walks the specific case, because it is the one that
lands first and it is the one the current bridge is silently doing already.

The user's requirement is that this architecture must accept perception —
which does not exist yet — without redesign. Concretely:

**Today**

```
CARLA actors ──(bridge synthesises)──► GenObjectList ──► df ──► AebOutputs/BsdOutputs
```

**With perception**

```
CARLA sensors ──► camera frames ─┐
                  radar dets   ──┴─► perception-core ──► GenObjectList ──► df ──► outputs
CARLA actors  ──────────────────────────────────────────────► truth (ground truth)
```

What each layer needs, and why it is already provided:

- **L1 sources** — `adas_sim.sources.carla` gains sensor spawning (CARLA already
  provides `sensor.camera.rgb`, and `mcap_recorder.py` already spawns and JPEG-
  encodes one). The `Tick.aux` slot carries frames; `Tick.truth` keeps carrying
  the actor-derived object list that the bridge synthesises today. **Nothing in
  L2–L5 changes.**
- **L1 pipeline** — one `impl:` line changes (§5.10): the
  `stub:carla_ground_truth` stage that stands in for `perception-core` today
  becomes `dll:perception_core_sil.dll`. Because ports are named and wired by
  data, `df`'s own entry is byte-identical before and after.
- **L3 scene** — `modules/perception-core/sim/layers/` contributes a
  `perception` group (detections, tracks, association lines, lane polylines,
  free-space polygon, confidence ellipses). `ground_truth` is a second group
  from `Tick.truth`. Both are visible simultaneously and independently
  toggleable — **so perception error becomes something you can look at**,
  which is the single most useful thing a perception debug view does and which
  falls out of the layer model for free.
- **L4 renderers** — the image renderer projects the *same* Scene prims onto a
  camera frame using `model.cameras`. A 3D box drawn in the BEV and its
  projection on the camera image are literally the same `Prim`, so they cannot
  disagree. This is the camera-overlay item parked in `../../../docs/df_carla_viz_plan.md` §6,
  and the reason OpenCV was chosen back then ("same drawing calls carry
  forward") — the Scene generalises that instinct instead of relying on it.
- **L5** — a camera panel next to the BEV panel; the GUI's component list grows
  by discovery, not by a hardcoded checkbox.

The one thing that genuinely must be built for perception and cannot be
pre-built: `CameraModel` (intrinsics/extrinsics) and the projection maths. That
is scoped in the visualization spec §11.4 and scheduled in §8 below.

---

## 8. Staged roadmap

Twenty stages in five phases (C1 lands as three sub-stages). Each stage is independently landable and leaves
the tree working; no stage requires the next one to be useful. Stage labels are
referenced from plan.md and are the labels the **implementation plan**
([sim_implementation_plan.md](sim_implementation_plan.md)) executes against —
that document is the normative, checkbox-tracked version of this table, with
per-stage unit and system test cases. This table is the summary.

### Phase A — Foundations (no user-visible change)

| Stage | Content | Done when |
|---|---|---|
| **A1** | Bootstrap `modules/sim` submodule: package skeleton, `core/`, `pyproject.toml`, `CLAUDE.md`, editable install, CI-less smoke test | `import adas_sim` works from a partial clone with only `sim` + `interfaces` checked out |
| **A2** | `model/` — `ProjectModel`/`EgoModel`/`ObjectModel` over existing `ego_params.yaml` + `default.yaml`; port `bsdviz.calib`/`egogeom` | `EgoModel.load("base").x_front == 3.60`, and `2w_base`/`cus1` resolve to their own numbers |
| **A3** | `scene/` types + `render/theme.py`; golden-test the token table | A `Scene` round-trips to/from bytes; every token resolves in both themes |
| **A4** | `io/mcap` codec (reader + writer) + the legacy-topic mapping for today's recordings (§8 of the recording doc) | Every existing `.mcap` under `tests/carla_testruns/` loads into a `Session`, and a written file round-trips |

### Phase B — Parity, then the viewer

| Stage | Content | Done when |
|---|---|---|
| **B1** | Renderer + `df/sim/layers/{common,aeb,bsd}.py` reproducing today's picture from a Scene. **Driven by pure replay of an already-`--export`ed `.mcap`** — those files already carry `df/aeb_outputs` and `df/bsd_outputs`, so no DLL is executed and no SIL binding is needed yet | The new path is visually equivalent to `viz.py`'s output on the same recording, and the Scene it builds matches a golden |
| **B2** | Two-pass `Session` + `view/transport` — scrub, seek both ways, step, speed, loop | Backwards seek works on a 1200-tick session; `--step`'s forward-only caveat deleted from the docs |
| **B3** | Interactive viewer shell: layer panel, inspector, viewport pan/zoom/presets, measure, timeline | Every item in visualization spec §4–§8 demonstrable on one BSD recording |
| **B4** | Capture: snapshot PNG **+ provenance sidecar**, print-quality snapshot, video export of a marked interval | Visualization spec §9; a snapshot is reproducible from its sidecar alone |

### Phase C — Contracts and content

| Stage | Content | Done when |
|---|---|---|
| **C1** | Generic SIL ABI + `df_sil.ports.yaml` manifest + `contracts/` — `df_ctypes.py` deleted | `df` exposes AEB+BSD ports through one generic `adasExec`; adding a third function needs no host change; `sil_host` and Python both drive it |
| **C2** | `sources/` refactor: `carla_bridge.py` decomposed into `sources/carla` + run manifest; recordings carry SUT/calibration provenance | A recording states which DLL build and which project produced it; resim refuses a mismatched SUT unless overridden |
| **C3** | Scenario schema split + `expect:` + headless `sim check` | All 18 scenarios migrated, expectations moved from comments to data, one command runs them all and reports pass/fail |
| **C4** | Delete the duplicated calibration in the viewer: `bsdviz.sensors`' hardcoded `P3`/`P4`/`P5` poses and `_bsd_project_sensor()`'s `if project == "2w_base"` go; `SensorModel`/`ObjectModel` read `BSD_SENSOR_*` / `BSD_CLASS_*` from the bundle. **No `shared_config` change** — §5.5 | No sensor pose or class footprint exists in Python; changing a `BSD_SENSOR_*` value in the project YAML visibly moves the drawn FOV |
| **C5** | Packed config bundle (§5.6): build copies `project.yaml` + `shared_config`'s `vehicle/ego_params.yaml` + port manifest into `<build>/…/Release/config/`, hashed; `adasInit(NULL)` resolves it module-relative; `adasManifest()` reports project + bundle hash; bundle embedded in recordings | A build output plus its `config/` runs on a machine with no Conan cache and no checkout; the viewer provably reads the same bytes the DLL read; a project/bundle mismatch is a warning, not silence |

### Phase D — Reach

| Stage | Content | Done when |
|---|---|---|
| **D1** | Foxglove `SceneUpdate` renderer + Scene-in-mcap sink | An exported mcap opened cold shows the full spatial scene with working layer toggles and seek |
| **D2** | matplotlib renderer; `bsdviz` figure driver migrated onto the framework | The 53 BSD figures regenerate byte-stable from the shared framework; live view and figures use one palette |
| **D3** | GUI on run manifests; `.claude` artifacts finalised | Every run is launchable from the GUI as a manifest; skills/workflows landed |
| **D4** | Perception: sensor sources, `perception`/`ground_truth` layer groups, `CameraModel` + image-projection renderer | A pipeline with two components runs, and perception output vs ground truth is visible side by side |

### Phase E — Retirement (the cleanup that makes `df` neat)

Nothing is deleted before its replacement is proven. This phase is where the
~2,300 lines of `df`-private tooling actually leave the tree.

| Stage | Content | Done when |
|---|---|---|
| **E1** | Delete `modules/df/tools/carla/**` and `scripts/df_sim_gui.py` + `sim_gui.bat`; retire the `bsdviz` generic half | Nothing under `modules/df` imports `cv2`, `foxglove`, `mcap` or `ctypes`; `df` holds only `sim/` plug-ins + scenarios + recordings |
| **E2** | `sil_host` moves to the generic ABI; delete `dfExec`/`dfInit`/`dfShutdown`/`dfApiVersion` from `df_interface_c.h` | Nothing references the old symbols; `df_sil_dll.md` updated; `adasAbiVersion()` still 1 |
| **E3** | Final invariant gates (§5.13) wired as a check script | `grep -riE 'aeb\|bsd\|lca\|acc\|ldw\|lka' modules/sim/src` is empty; no renderer import in any layer provider; every machinery `diff -q` clean |

**Ordering rationale.** Phase A is invisible but unblocks everything and is
low-risk. B1 is deliberately a *parity* stage — the new path must reproduce the
old picture before anything new is added, which makes the change reviewable.
B2/B3 deliver the user-visible wins (scrubbing, snapshots, layers, a viewport
that fits the function) earliest. D4 is last because perception does not exist;
everything before it is built so that D4 is additive. Phase E deletes only what
Phases A–D have already replaced and proven.

**Why the viewer (B) can safely precede the SIL contract (C).** The obvious
worry is that B needs to execute the DLL, which would force the framework to
carry a `df`-specific ctypes binding before the generic ABI exists — a direct
`R-SIM-1` violation. It does not: **Phase B runs on pure *replay*.** The
`--export`ed `.mcap` files that already exist carry both the stimuli *and*
`df/aeb_outputs`/`df/bsd_outputs`, so B builds `Tick`s and `Scene`s from a file
and executes nothing. That is stronger as a rendering gate too — no DLL variance
in a test about pixels — and it means the entire viewer is developed and tested
with zero C++ involvement.

**C4 → C5 ordering.** C4 removes the viewer's duplicated copy of calibration
the DLL already reads; C5 then packs that calibration beside the DLL so both
provably load the same bytes. C4 first means C5 has a single reader to point at
rather than two to reconcile. C5 depends on C1 (the manifest it packs and
the `adasManifest()` fields it fills) and is the reason C1's manifest carries
`project` and `config_bundle_sha256` rather than component identity alone. Until
C5 lands, `ProjectModel` reads the source checkout and **says so in the HUD** —
the divergence in §5.6 is real in the meantime and must be visible, not assumed
away.

---

## 9. Relationship to `sil_host`

`modules/sil_host` is a C++ executable that loads component DLLs and ticks
them; `adas_sim` is a Python framework that loads component DLLs and ticks
them, then records and draws. They are not competitors, and neither absorbs
the other:

- Both become clients of **one** pipeline description (§5.4) and **one** port
  manifest format (C1). A pipeline YAML that runs under `sim resim` runs under
  `sil_host` unchanged, provided every stage is one `sil_host` can execute.
- `sil_host` stays the answer for "run the real composition with no Python in
  sight" — closest to a production integration, and the right place for timing
  measurements that a Python host would distort.
- `adas_sim` stays the answer for development, inspection and regression.

**The boundary, stated so it cannot erode** (§5.10): `sil_host` executes
`dll:` and `stubdll:` stages plus `mode: measured` injection. It never executes a Python `stub:`,
and **it never grows its own object generator**. A stand-in that `sil_host`
needs is promoted to a `stubdll:` — one implementation, on the same generic ABI,
drivable by both hosts. Driving a *live* CARLA server from `sil_host` is out of
scope: CARLA's client is Python, nothing requires it, and consuming a recording
already covers what it would buy.

The convergence point is C1 and nothing else. Until C1, `sil_host` continues to
call `dfExec` directly, unaffected.

---

## 10. Decisions

**All three CONFIRMED 2026-07-27** — the user accepted every recommendation as
written. Kept below with their alternatives so the reasoning is not
re-litigated. A fourth decision (configuration delivery) was taken in the same
pass and is recorded in §5.6.

### OD-1 — Interactive viewer toolkit — **CONFIRMED: Qt (PySide6)**

| Option | For | Against |
|---|---|---|
| OpenCV window + tkinter (today) | Zero new dependency; already works | Not a UI framework: no scrub bar, no dock panels, no layer tree; two event loops already caused one bug (`../../../docs/df_carla_viz_plan.md` §5.1c) |
| **Qt (PySide6)** ← recommended | Real widgets: dock panels, timeline scrubber, layer tree, inspector, ruler, video export; single event loop; mature | ~80 MB dependency; a real learning cost |
| Foxglove only | No UI code at all; free scrub/plots/3D/image panels | Bespoke overlays are constrained by the panel model; the earlier live-connection attempt failed on frame trees; UX is rented |
| Local web app | Most flexible, best-looking | Largest build; a second language in the stack |

**Recommendation: Qt for the interactive viewer, Foxglove kept as the
share/interop renderer (D1), matplotlib as the print renderer (D2).** Because
all three are thin adapters over one Scene, this is not three UIs to maintain,
and the earlier frame-tree failure is exactly the class of bug an explicitly
frame-typed Scene prevents. The architecture is renderer-agnostic by
construction, so this decision is reversible at the cost of one module.

### OD-2 — Generic ABI now, or a descriptor over the current one — **CONFIRMED: generic ABI, now**

C1 can be done two ways: change `df_interface_c.h` to a generic named-port
`adasExec` (breaking, one `dfApiVersion` bump, touches `sil_host` and the
gtest), or keep `dfExec` and describe its positional signature in a YAML the
Python side reads. The second is cheaper today and strictly worse forever.

**Recommendation: the generic ABI, now** — precisely because only one component
has a C API today and the second does not exist yet. The cost never gets lower
than this. Full comparison in [sim_sil_contract.md](sim_sil_contract.md) §5.

### OD-3 — Renaming `tests/carla_scenarios/` → `tests/sim_scenarios/` — **CONFIRMED: defer**

The `carla_` prefix becomes inaccurate the moment plan.md item 4 (CarMaker)
lands, and the scenario content is already world-model-agnostic apart from the
`carla:` block that C3 removes.

**Recommendation: do not rename now.** The feature-subfolder layout landed on
2026-07-27 (`../../../docs/df_carla_scenario_layout.md`) and churning it a day later costs
more than it returns. Trigger the rename when CarMaker actually lands, and do
it as one `git mv` in the same commit — the same discipline
`../../../docs/df_carla_tools_relocation_plan.md` applied.

### OD-4 — Configuration delivery — **CONFIRMED: pack a bundle beside the DLL**

Raised and settled 2026-07-27, after OD-1..3. Reverses plan.md item 19's
2026-07-22 "keep the pointer" decision. Full reasoning, the two additional
defects it closes, and the bundle layout are in §5.6; the build/runtime work is
stage C5. Recorded here so the decision list is complete.

---

## 11. What is deliberately not designed here

- **A 3D scene.** The Scene IR is 2.5D — metres in a plane, plus an optional
  height on `Box`. Full 3D is a renderer concern and no requirement asks for it.
  The decision recorded in `../../../docs/df_carla_viz_plan.md` §2 (a 2D view is what the
  problem calls for) still stands.
- **Closed-loop actuation into the world model.** Every run today is open-loop
  read-only by design (`../../../docs/df_carla_bridge_blueprint.md`). Closing the loop is a
  `sources/carla` capability, additive to this architecture, and gated on
  plan.md item 6 (actuation + arbiter) existing at all.
- **HIL.** Nothing here precludes it — a `sources/` implementation over a real
  bus is the same interface — but no requirement exists.
- **Sensor error models.** `object_range_m`/`num_object_slots` are the whole
  sensor model today. Real FOV/latency/noise/dropout modelling belongs in
  `sources/`, is genuinely needed to make BSD's coverage work honest, and is
  scoped only as a schema slot in C3 — not designed.
- **Multi-run statistics / KPI dashboards.** The `check/report` output in C3 is
  a pass/fail report, not an analytics platform. Revisit when there are enough
  scenarios for aggregate numbers to mean something.
