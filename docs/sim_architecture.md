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

- **stimulus** — one tick's complete input set to the SUT (`DfObjList`,
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
| `modules/df/tools/carla/carla_bridge.py` | 983 | CARLA connect, spawn, actor motion, frame conversion, `DfObjList`/`VehDyn` synthesis, `dfExec` call, console log, recording, end conditions, scenario resolution, CLI |
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

Thirteen, each stated as an observable fact plus what breaks when the roadmap
arrives. This list is the requirements set for everything after it.

`D1`–`D11` were catalogued in the original 2026-07-27 survey of today's
tooling. **`D12` and `D13` were added by the 2026-07-31 review** and are a
different species: they are defects in *this design's own implementation*, each
one the original defect's shape reappearing one level up after `D1`/`D2` were
closed. They are recorded here rather than as review notes because a defect
that recurs at the next level is the most valuable kind to name.

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

### D12 — The ABI stopped growing per function; the *shim* grows per component

**Found 2026-07-31, after `S-C1b` landed.** `D1` is genuinely closed: adding a
driving function adds a manifest row, and `adasAbiVersion()` still reads `1`.
But look at what `S-C1b` actually cost `df` — a named-constant block per port, a
static input table, a static output table, a `buildManifest()` walking both, an
`adasExec` dispatch block per function, a `df_manifest_dump` executable, a CMake
target, and 14 tests. Roughly 400 lines, of which the overwhelming majority is
*mechanical restatement of the port list in four grammars*.

None of it is wrong. All of it is per-component. `perception-core`,
`perception-lane`, `planning` and `vdy` each get their own near-identical copy,
hand-written and hand-maintained — and `R-BUILD-6` already tells us what happens
to N near-identical copies that are not generated: they drift, and the drift is
found by whoever is unlucky.

**The shape is D1's exactly, moved up one level.** D1 was *"the interface grows
per function"*; D12 is *"the adapter to the interface is rewritten per
component"*. The tell is the same in both cases: a human types the same
structure N times and a test is asked to notice when they diverge.

**What breaks when the roadmap arrives.** Eight components × ~400 lines ≈ 3,200
lines of glue that exists only because nobody generated it. Every ABI evolution
(a new manifest field, a new port attribute) is then an eight-repo edit —
precisely the cross-submodule change `R-BUILD-6` exists to warn about, with none
of `R-BUILD`'s byte-identical-copy protection, because these files are *not*
identical: each names its own ports.

Closed by `R-SIM-22` — declare the ports as data, generate the shim.

### D13 — A plug-in's port address is a literal, and a wrong one fails silently

**Found 2026-07-31, inspecting `modules/df/sim/layers/bsd.py`.** The framework
never hardcodes a port name — `GT-1` guarantees that, and it holds. But the
guarantee stops at the framework boundary, and the *component's own plug-in* is
on the other side of it:

```python
@layer_provider("bsd.warning", group="bsd", requires=("df.bsd.outputs",))
def warning_layer(ctx):
    bsd_outputs = ctx.history.last(1)[-1].port("df.bsd.outputs").message
```

Three separate problems in one string:

1. **`df.` is not the component — it is the *stage name* someone typed in a
   pipeline YAML.** Rename the stage to `driving_functions` and the layer stops
   binding. Nothing in the design says a stage name is a stable identifier;
   `Pipeline` builds the address as `f"{stage.name}.{port.name}"`, and stage
   names are authoring choices.
2. **`bsd.outputs` is a C++ constant in another repo, in another language.**
   `UT-C1b-11`/`UT-C1b-12` bind it tightly to the dispatch and the ports header
   — and to nothing on the Python side.
3. **The failure is silent.** `scene/registry.py`'s `requires` gate returns `()`
   when a port is absent. On screen, a missing overlay is indistinguishable from
   *"the algorithm did not raise a warning"* — which is the single worst
   failure mode a debugging tool can have, because it produces a confident
   wrong answer rather than an error.

A fourth instance is already scheduled: `S-C3`'s `expect:` blocks will name
these same addresses as strings in scenario YAML.

**The shape is D3's exactly, moved into the plug-in.** D3 was *"the number is
typed into Python while the real one is in YAML"*; D13 is *"the name is typed
into Python while the real one is in the manifest"*. Same defect, same
consequence — a confidently wrong picture — and it survived precisely because
`GT-1` guards the framework and nothing guards the plug-in.

Closed by `R-SIM-21` — bind relative to the component, resolve once at load,
error loudly on a miss.

**Note on the sibling defect this exposes.** `bsd.py` also calls
`path.read_text()` on `df`'s project YAML *inside the layer provider*, which
`R-SIM-2` forbids twice over (a provider never touches disk) and which bypasses
the config bundle's whole reason for existing (`R-SIM-3a`: the viewer must read
the bytes the SUT was initialised with, not the checkout that happens to be
adjacent). Same root cause — the plug-in boundary was specified and never
gated — so it is carried as part of `D13`'s closure rather than as a fourteenth
defect.

### D14 — A recording's topics never reach a port, and the one bridge is hardcoded in the framework

**Found 2026-07-31.** `R-SIM-6` makes topic names equal port names *for
recordings this framework produced*. Every recording that already exists was
produced by something else, and for those the chain is broken in the middle:

| Layer | Name | Source |
|---|---|---|
| Recording on disk | `df/gen_object_list` | today's exports |
| After `io/legacy.py` | `/source/gen_object_list` | `LEGACY_TOPIC_MAP` |
| `Tick.ports` key | `source.gen_object_list` | `runner._topic_to_port_name` |
| What a pipeline asks for | `source.` **`objects`** | `df_sil.ports.yaml`'s input port |

**The last two lines never meet.** `gen_object_list` is not `objects`, and
nothing in the system maps one to the other. `io/legacy.py` renames a *topic to
another topic* and leaves the port question unasked; §3.2 of
[sim_resim_and_recording.md](sim_resim_and_recording.md) even notes that
`gen_object_list` "is named for its *consumer*" and "asserts something false" —
identifying the naming defect without connecting it to the port.

**The evidence this is real rather than theoretical:** `ST-C1c-1` — *"resim
every existing recording"* — passes, and passes by **hardcoding the bridge
inside the test** (`TOPIC_GEN_OBJECT_LIST = "df/gen_object_list"`, with its own
comment mapping positional buffers to manifest port names). The test proves what
it claims, which is ABI equivalence. It does not prove a legacy recording can
drive a `Pipeline`, because the mapping it hardcodes is precisely the mapping
the product does not have.

**Two structural problems, not one:**

1. **The mapping lives in the framework.** `io/legacy.py` holds function-named
   strings under a named `GT-1` exemption, justified at `S-A4` as narrow and
   one-off. It is about to stop being one-off: the moment `perception-core` has
   its own recordings with its own topic vocabulary, the framework needs a
   second table, then a third for a supplier's data. A carve-out that repeats is
   a mechanism that was not built (`R-SIM-1`).
2. **`CR-SIM-21` is named but not mechanised.** *"Which cuts a recording
   supports is a property of the recording, read from its topic index"* is
   correct and there is no code that reads a topic index and answers it. The
   only path is `UT-C1c-10`'s **failure** path — a `measured` stage whose
   outputs are missing raises. That is the error path, not the discovery path,
   and a user who wants to know what a file can do should not have to start a
   run and read a traceback.

**The shape is `D12`/`D13`'s, a third time**: a declaration written as code, at a
boundary specified on one side only. The producer side of recording was
specified in full (`R-SIM-6`); the **ingest** side — everything not produced by
us — was assumed to be a migration detail.

**What breaks when the roadmap arrives.** Exactly the workflow this platform
exists for: open a component's existing test-run recordings in the player,
resim that component alone, with only that component checked out. A BSD
recording carries objects and outputs and no perception layer at all; a
perception team's recording will carry detections and no objects. Both are
legitimate, both support exactly one cut, and neither can currently tell the
tool which one.

Closed by `R-SIM-23` — an ingest map owned by whoever owns the recordings, and
a feasible-cut query answered before the run.

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
class PortValue:
    message: Message        # the parsed protobuf
    age_s: float            # how stale this value is at this tick
    valid: bool             # was anything received (never inferred from bytes)
    updated: bool           # did its producer write it *this* tick
    origin: Provenance      # measured | truth | mocked | simulated | unknown

@dataclass(frozen=True)
class Tick:
    index: int                          # 0-based cycle number
    t_ns: int                           # elapsed ns from run start — the authority
    dt_ns: int                          # gap since the previous tick
    pose: Pose2D                        # ego pose in the world frame at this tick
    stimulus:   Mapping[str, PortValue] # port name -> value + metadata
    observation: Mapping[str, PortValue]
    truth: Mapping[str, Any]            # ground truth from the world model, if any
    aux: Mapping[str, Any]              # camera frames, per-component timings

    @property
    def t_s(self) -> float: ...         # derived, for display only
```

Three details in that shape are load-bearing, and each was found by checking the
model against something the specs already promise:

- **A port is a value *plus its metadata*, never a bare message.** `AdasPort`
  carries `ageS`/`valid`/`updated` across the C boundary and an earlier draft of
  this model threw them away — which would have made the stale/invalid banner
  (viz §10) and its test `UT-B3-5` impossible to implement, and would have
  hidden multi-rate behaviour (§5 of the recording doc) entirely. Carrying
  `origin` here too is what lets the viewer show per-port provenance
  (`R-SIM-12`) rather than only a run-level tag.
- **Time is integer nanoseconds; `t_s` is a derived convenience.** The recording
  is already `log_time_ns` (integer). Passing through `float` and back loses
  exactness, and accumulating a float `elapsed_s` over tens of thousands of
  ticks drifts — which would quietly undermine the bit-identical-resim guarantee
  (`R-SIM-5`) that everything in CI rests on. Floats appear at the display
  boundary and nowhere else.
- **`pose` — the ego's pose in the world frame — is part of the tick.** Without
  it the `world` follow mode (viz §4.2, "ego moves through it, trail drawn") and
  every world-frame or trajectory layer are unimplementable. It is one small
  struct and it is the only dynamic frame transform; the static ones
  (sensor→ego, camera→ego) come from `ProjectModel`.

Everything downstream reads a `Tick` and nothing else. `stimulus` and
`observation` are keyed by **port name** (`"objects"`, `"aeb.outputs"`,
`"bsd.outputs"`), which is what makes L1 and L3 both function-agnostic.

`truth` matters more than it looks: today the CARLA bridge *is* the perception
system — it synthesises `DfObjList` from actor transforms. Once
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

#### How the Scene evolves without breaking what already exists

The Scene is serialized — into recordings (§5.11), into golden test fixtures,
into a Foxglove stream. It is therefore a **wire format**, and it will gain
fields. Without a stated evolution rule, a recording made today becomes
unreadable next quarter and goldens churn for reasons nobody can reconstruct.

`Scene` carries a `version` (`major.minor`), and the rule is:

| Change | Version | Old reader sees |
|---|---|---|
| new optional field on a prim; new prim type; new style token; new layer | **minor** | ignores what it does not know, renders the rest |
| a field removed, renamed, or given a new meaning; a unit changed | **major** | **refuses to render** and says why |

Three consequences, all deliberate:

- **`scene/codec.py` uses protobuf, not an ad-hoc encoding.** Protobuf's field
  numbering gives the additive property for free — an unknown field is skipped
  rather than fatal — and the same schema is what a Foxglove renderer wants
  anyway. This is why §5.3's codec entry says protobuf is preferred.
- **A major bump is a migration, not a flag day.** `scene/codec.py` carries a
  reader for the previous major; a recording states the version it was written
  with, and one that cannot be read is **refused with its version named**, never
  half-rendered.
- **Goldens record their Scene version.** A major bump requires regenerating
  them, and that regeneration must appear in the diff with a justification —
  the same discipline the implementation plan's §3.3 already sets.

**Prefer adding over changing.** The primitive set is closed and deliberately
small (viz §2) precisely so that a new need is usually met by a new *optional
field* or a new *style token* — both minor — rather than by redefining
something. A proposal that needs a major bump should be argued for on that
basis.

#### The Scene carries geometry, not bulk data — resolving `NR-SIM-43`

*Added 2026-07-31, answering audit finding `A5`. `OD-7`.*

`Prim` inlines everything it draws: `points_m`, a `Heatmap`'s `values` array, an
`Image`'s `data` bytes. For tens of prims of tens of points that is correct and
pleasant. For the perception content `FR-SIM-3` requires — a 100 000-point cloud,
a camera frame, an occupancy grid — it is megabytes per tick, protobuf-encoded
per tick, held in a cache that today bounds itself by **entry count**
(`SceneCache(max_size=256)`), not by bytes. 256 entries of megabytes is
gigabytes, and `NR-SIM-5`'s "stays responsive" has no number to fail against.

**The rule.** A `Prim` inlines **small geometry only**, under a declared
per-Scene budget. Anything bulk is **referenced** and resolved by the renderer at
draw time:

```python
@dataclass(frozen=True)
class BulkRef:                 # a Prim field, never a Prim of its own
    topic: str                 # the recording topic that carries the payload
    log_time_ns: int           # which message
    field: str = ""            # optional path within the message
    count: int = 0             # elements, for budgeting and for the HUD
    encoding: str = ""         # "f32[2]", "jpeg", "u8grid" — declared, not sniffed
```

Three properties make this cheap rather than a new subsystem:

- **It is not a new storage mechanism.** The bytes are already in the recording;
  a `BulkRef` is a *coordinate into it*. Nothing is copied, nothing is written
  twice, and a Scene stays serializable — a `BulkRef` survives into a golden, a
  Foxglove stream and a `/scene` topic exactly as a number would.
- **It is enforceable precisely because `R-SIM-7` holds.** If a value is big, it
  came from a port; if it came from a port, it is in the recording. A layer that
  *computed* a 100 000-cell grid would be estimating what nothing produced, which
  `R-SIM-7` already forbids. So "bulk data always has a topic to point at" is not
  an assumption — it is a consequence of a rule that is already gated.
- **The budget check names the layer, not the frame rate.** A `Prim` does not
  know which layer it is in, so the check lives in `Layer.__post_init__`, which
  knows both, and raises a `ContractError` naming the layer, the prim kind and
  the count. A budget breach is an authoring error at build time
  (`§5.14`), never a slow render someone profiles a week later.

**`SceneCache` bounds by bytes.** `max_size=256` becomes `max_bytes`, with the
entry count as a secondary cap. This is the change that makes `NR-SIM-5`
falsifiable: a stated byte ceiling at a stated tick count is a number a test can
fail.

**Alternatives rejected.** *Leave it inline and cap the point count in the
provider* — pushes the budget into every component's plug-in, where it is
un-auditable and where the first person to need 200 000 points simply raises
their own constant. *A separate `BulkPrim` type* — doubles the primitive
catalogue and forces every renderer to handle two shapes for one idea; a field
on the existing prim does not. *Stream Scenes instead of caching them* — throws
away the free backwards scrub that `R-SIM-17` is built on.

**Cost.** One small frozen type, one validation, one resolve step in each
renderer, and `SceneCache` re-bounded. **What it does not solve:** rendering
100 000 points *quickly* at high zoom — the `Heatmap`/`Points` downsampling
question (viz §17) is a renderer concern and stays open. Nor does it bound the
*recording*; that is `NR-SIM-42`'s job.

**A layer provider is the entire contribution a function makes to the viewer:**

```python
@layer_provider(group="bsd", requires=["bsd.outputs", "objects"])
def bsd_layers(tick: Tick, ctx: LayerCtx) -> Iterable[Layer]:
    ...

@dataclass(frozen=True)
class LayerCtx:
    model:       ProjectModel   # resolved configuration — §5.5
    history:     HistoryView    # read-only window over earlier ticks
    frames:      FrameTree      # static (from model) + dynamic (tick.pose) transforms
    interaction: Interaction    # cursor (in-frame, metres), selection, modifiers, toggles
```

**`ctx` carries history, and that is not a weakening of the purity rule.** An
earlier draft passed only `(tick, model)`, which made every *temporal* layer
impossible to write — track history, a target's path, the ego trail the `world`
follow mode explicitly promises (viz §4.2), a velocity trace. Those are geometry
and therefore belong to a layer provider; the alternative (a renderer that
remembers) would put state in the one place that must not have it.

`interaction` is the same idea applied to input (viz §7.5). The reference
console lets a layer declare `MouseListener`/`KeyboardListener`; handing a
provider an event callback would put UI state inside the one thing that must
have none, so the interaction **state** is an input instead, and a provider
declares `reacts_to=` so the cache knows when to re-render it. Cursor arrives in
the layer's own frame in metres — a provider that needed pixels would be
breaking `R-SIM-2`.

`HistoryView` is **read-only and windowed**: a provider asks for the last *N*
ticks or a time span, and cannot write, cannot reach forward, and cannot hold a
reference across calls. So a provider stays a pure function of its arguments —
same inputs, same layers — which is what keeps Scene caching and golden tests
sound (`R-SIM-2`). The rule "no state *between* ticks" is unchanged; what changes
is that history is now an *input* rather than something a provider was tempted
to accumulate.

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

**A pipeline is a DAG, not a chain.** Wiring is per port and names a producer,
so one component can feed several (`perception-core.gen_object_list` reaching
both `df` and, later, `planning`), and a component can draw inputs from several
producers. The list order is a **declared topological order**, validated at load
against the wiring — a stage referencing a producer that runs later is the
forward-reference error, not a silent last-tick read. Stating this now costs
nothing; discovering it after the runner assumes a chain costs a rewrite. A
component may also appear more than once under distinct names
(`perception.front`, `perception.rear`), since a stage's identity is its name,
not its library.

### 5.5 The project model — L0, and the answer to D3

```python
model = ProjectModel.load(project="base")
model.ego         # EgoModel   — from shared_config .../vehicle/ego_params.yaml
model.objects     # ObjectModel — footprint per DfObj.Classification
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

1. `DfObj.geometry.shape_point_coordinates`, when perception actually fills
   it (the item parked in `../../../docs/df_carla_viz_plan.md` §6 — this is where it lands);
2. the project's class-footprint table, keyed by
   `DfObj.attributes.classification`;
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

#### Overrides and sweeps — the calibration loop the bundle must not break

Making the bundle a **build output** raises an obvious objection: calibration
work is a *sweep* — run this scenario with `AEB_TTC_PRE_WARNING_THRESHOLD_S`
from 0.8 to 1.4 in steps and see where the warning moves. If configuration only
arrives via the build, every step is a rebuild, and the loop this design claims
to protect is dead.

It is not, because an explicit path always wins (§3.4 of the contract). But the
mechanism must be *named*, or every sweep run reports a project-mismatch warning
and the noise trains people to ignore warnings:

```yaml
run:
  overrides:                              # declared, not smuggled
    aeb.AEB_TTC_PRE_WARNING_THRESHOLD_S: 1.2
```

The framework materialises a derived bundle from the packed one plus the
overrides, hashes it, and records **both** the base bundle's hash and the
override set in the run manifest. Consequences:

- provenance stays exact — a swept run is `bundle <hash> + 1 override`, which is
  a *statement*, not a warning;
- two swept runs differ in the manifest, so an A/B diff (§6.4) can attribute the
  difference to the parameter rather than to "something changed";
- `sim check` over a sweep produces one report row per value, which is the
  actual output of a calibration session.

Authoring homes are still untouched (`R-VAR-4`): an override is a **run
property**, never an edit, and it never writes back. A value that survives a
sweep gets promoted into the project YAML by a human, deliberately.

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
fallback, flagged in the HUD as unverified provenance).

**That order is a default, not a lock.** The reference console exposes exactly
this as a per-artifact-kind user toggle (*use the description from the
recording, or from disk*), and it is right to: an embedded bundle can be stale,
and testing a new calibration against an old recording is a real thing people
need to do. So the source is overridable — `--config-source
embedded|library|checkout|<path>` on the CLI, a dropdown in the GUI — and
**whichever was used is always displayed**, because an override that is silent
recreates the exact confusion the bundle exists to remove. Until the bundle exists
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

#### 5.7a Authoring home vs. deployed form — the distinction this section was missing

**Added 2026-07-31**, resolving a recurring and entirely reasonable objection:
*"if the player is supposed to be standalone, why does BSD's picture live in
`df`? Shouldn't it move into `modules/sim`?"*

The objection is two questions wearing one coat, and the answer to each is the
opposite of the other:

| Question | Answer | Why |
|---|---|---|
| Where is a component's plug-in **authored and owned**? | `modules/<name>/sim/` — unchanged | Moving it into the framework is `D9` with the polarity reversed: instead of `df` owning everyone's viewer, `sim` owns everyone's content. Every component's picture change becomes a `sim` commit, a `sim` review and a `sim` release; `GT-1` would have to be deleted; and the framework acquires a reason to know what a driving function is |
| Does the player need `modules/<name>` **checked out** to render it? | **It must not — and today it does** | This is the real defect, and it is what the objection is actually detecting |

The table above is the whole resolution: **the folder is right; the delivery
mechanism is missing.** A git checkout is not a delivery mechanism — it is an
authoring convenience that happens to also make the files reachable, which is
why the gap was invisible.

The fix is symmetric with one already in this design. `R-SIM-3a` already says
the *configuration* is copied beside the library at build time, because
requiring `shared_config` on disk to read a run was unacceptable. **Plug-ins get
exactly the same treatment** (`R-SIM-20`):

```
<library_dir>/                     e.g. build/.../Release/, or an installed tree
  df_sil.dll
  config/                          R-SIM-3a — calibration the SUT was built with
    default.yaml  ego_params.yaml  df_sil.ports.yaml  bundle.sha256
  sim/                             R-SIM-20 — what this component contributes
    layers/  pipelines/  sensor_models/  viewpoints.yaml  bundle.sha256
```

Consequences, each of which is the standalone property the objection wanted:

- **`vantage <dir-of-dlls>` works with no repo.** The player walks its plug-in
  path, finds a manifest per library, and imports that library's `sim/`. No
  sibling checkout, no `PYTHONPATH`, no environment variable.
- **Adding a driving function never rebuilds the player.** This is the
  constraint `FR-SIM-70` already imposed on a frozen executable ("a frozen
  executable must keep an external plug-in import path") — `R-SIM-20` is that
  constraint made concrete, rather than left as a note.
- **A recording renders correctly on a machine with no build**, because it
  embeds the plug-in bundle's hash beside the config bundle's, and a missing one
  is reported in the HUD rather than substituted from whatever checkout is
  nearby (`R-SIM-6`'s existing discipline, extended).
- **`modules/df/sim/` is still `df`'s**, reviewed by the people who own the
  algorithm, released on the component's cadence.

Stated as the one-liner to remember: **the component owns the picture; the build
delivers it; the player discovers it.** Only the middle clause was missing, and
its absence is what made two correct rules look like a contradiction.

*Authoring homes are unchanged by this — the deployed `sim/` folder is a build
**output**, never a second place to edit a layer. Same discipline `R-SIM-3a`
states for the config bundle, and the same failure it exists to prevent.*

##### The plug-in path is an external interface — `NR-SIM-44` / `A7`

*Added 2026-07-31.* `R-SIM-20` makes the player **import Python from a directory
beside a DLL**. That is a code-execution boundary, and `NR-SIM-9` versions
everything the player reads *except* this one — the only interface the same
review made external. Two statements, both explicit, because both would otherwise
be decided by accident.

**1. A recording carries plug-in identity and hashes, never executable content.**
Opening a colleague's file must never run their code. A missing plug-in degrades
to *"these layers unavailable"*, **named with the hashes that were expected**, so
the fix is *install these* rather than *why is my screen empty*.

*This looks inconsistent with `R-SIM-6`, which embeds the config bundle's bytes,
and it is worth saying why it is not:* **configuration is data and a plug-in is
code.** Data cannot execute; the whole reason the bundle travels is so a viewer
with no build can read the same numbers. Stating the asymmetry here is deliberate
— left unstated, someone eventually "fixes" the inconsistency in the wrong
direction, and a recording becomes a delivery vehicle.

The honest cost is that a recording opened on a machine without the component's
plug-ins renders only framework-generic layers. Two mitigations already exist and
neither is new machinery: the plug-in bundle deploys beside the library
(`R-SIM-20`), so *having the library* means *having the layers*; and the optional
`/scene` topic (recording §6) stores the computed geometry itself, so a recording
that carries its Scenes renders with **no plug-ins at all** — which is the right
answer for *"send someone a file they can look at"*.

**2. The plug-in API carries its own generation**, independent of the Scene major
and the ABI version, declared in a **manifest file** rather than in Python:

```yaml
# modules/<name>/sim/plugin.yaml — deployed to <library_dir>/sim/plugin.yaml
api: 1
component: <name>
provides: [layers, viewpoints, workspace, ingest, sensor_models, tolerance]
sha256: <bundle hash>
```

**A file, not a module attribute, and the reason is decisive:** the player must
decide *before importing*. Reading a `PLUGIN_API` constant requires importing the
module, and importing an incompatible plug-in is precisely what "refused, not
half-loaded" forbids. The file also becomes the natural home for the bundle hash
`R-SIM-20` needs anyway, so it replaces an ad-hoc hash side-car rather than
adding a concept.

The player declares the range it supports; a plug-in outside it is **refused with
both numbers named**, on `NR-SIM-9`'s existing terms.

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
    scene/      types · registry · builder · frames ·
                default_layers                              ← NEW (the Scene IR; default_layers
                                                                is the framework's own ego/frame/
                                                                trail furniture, AR-52, 2026-08-07)
    render/     theme · viewer · matplotlib · foxglove      ← was viz.py, foxglove_stream.py,
                                                              bsdviz.canvas/palette
    view/       viewport · transport · layers · inspector · timeline · measure ← NEW
    check/      expect · report                             ← NEW
    app/        cli · gui                                   ← was df_sim_gui.py
  tests/  README.md  CLAUDE.md  pyproject.toml
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
| `scripts/df_sim_gui.py`, `sim_gui.bat` | **leaves** | → `adas_sim.app`, launched by the `vantage` console entry point — **not** a new `.bat`, which is Windows-only (`P-6`) |
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
`DfObjList` and hands it to `df`. Tomorrow the chain runs radar signal
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

#### The severed chain — the one arrangement that lies

`mode` is per stage, and the previous paragraphs are careful to say that
execution never propagates upstream. That is true of the *mechanism* and
insufficient as a *default*, because one arrangement is almost always a mistake:

```
rsp = simulate   →   em = measured   →   df = simulate
                     ↑ rsp's output dies here
                                          ↑ df's input never saw rsp
```

`rsp = simulate` here is a **lie**. Nothing it computes reaches anything: `em`
is not executing, so it consumes nothing, and its recorded outputs are what `df`
reads. The operator moved a toggle and the picture did not change — which is one
of the more demoralising things a tool can do to someone.

Note what this is *not*. It is not upstream propagation, and the common case is
untouched: `rsp = off, em = measured, df = simulate` is pure function resim,
with no hole and nothing to warn about, because `rsp` is not claiming to run.
The anomaly is specifically **a `measured` stage between two `simulate` stages
on one data path**.

So the rule is stated on the gap, not on the direction (`R-SIM-10`):

- **Default: close it.** Setting `rsp` and `df` to `simulate` flips `em` to
  `simulate` too, in the GUI and in the loader, undoably.
- **Allow the override.** Forcing `em` back to `measured` stays legal, because
  one real setup needs it: *"I changed `rsp`, show me its divergence from the
  recording, but hold `df` on known-good input so `df`'s behaviour does not move
  underneath me."* Two panels, one run.
- **Badge the lie.** The orphaned stage then reads *"computed, not consumed"* in
  the pipeline panel, and headless runs warn at load.

Forbidding it outright would delete the setup above; leaving it silent is how
the toggle stops being believed. Default correct, escape hatch visible.

#### Per-port overrides — what "tweak the inputs" actually means

`mode` and `inputs:` repoint a *whole* port. That is not the knob a developer
reaches for at 18:00 while debugging their own function; they want to pin one
field and re-run. Without it, they write their own host — which is the outcome
`R-SIM-16` exists to prevent, arriving through a side door.

```yaml
inputs:
  objects: perception-core.gen_object_list
  egoDyn:  measured:/vdy/veh_dyn
  egoDyn.vx:       {const: 22.0}     # pin one field
  egoDyn.yaw_rate: {hold: true}      # freeze at its first value
  objects[*].pos_x: {offset: -1.5}   # shift every slot
```

**Four verbs — `const`, `hold`, `offset`, `scale` — and a hard stop there.**
The temptation is an expression language, and it must be refused: the reference
console's `ValueHandleRules` (glob patterns plus URI string-replacement rules
per argument) is exactly what an open grammar becomes, and it is the mechanism
behind the over-configuration complaint this design answers. If four verbs prove
insufficient, the honest answer is a `stub:` stage — real code, in a real file,
reviewable — not a fifth verb.

An override is **declared, not smuggled**, on the same terms as a calibration
override (§5.6): it lands in the run manifest, the HUD badges the port, and the
topic carries `origin: overridden` so no report can mistake a pinned input for a
measured one.

##### Addressing a repeated field — resolving `OQ-10` / `A8`

*Added 2026-07-31. `OD-8`.*

`OQ-10` worried that four verbs are too few. The audit sharpened it correctly:
the gap is not a fifth *arithmetic* verb, it is that the four verbs are
**scalar-shaped** and the requests developers actually make are **structural** —
*delete object 3*. The escape hatch (write a `stub:` stage) means the closed list
did not prevent a private fork; it made one heavier, which is the failure
`FR-SIM-45` names.

Two things are therefore added and one is refused.

**1. The address grammar is stated and closed.** It was previously implied by the
example above (`objects[*].pos_x`) and implemented nowhere —
`contracts/override.py` is scalar-only today, which is why this is cheap now.

| Form | Means |
|---|---|
| `port` | the whole port |
| `port.field` | a scalar field, at any depth (`egoDyn.vx`) |
| `port.repeated[i]` | one element, by index |
| `port.repeated[*]` | every element |
| `port.repeated[i].field` · `port.repeated[*].field` | a field within those |

**Index and `*` only. No predicate.** `objects[?class=="truck"]` is an
expression, and an expression grammar is the over-configuration this design
answers.

**2. Two structural verbs — `select` and `drop` — and the list closes again at
six.** `drop` removes the addressed element(s); `select` keeps them and drops the
rest. They are the complement pair over a set, which is why *two* is the right
number rather than five:

> **An override may destroy or attenuate information. It may never create an
> entity.**

That is `R-SIM-7` applied one level up, and it is what rules out `insert`,
`duplicate`, `move` and `reorder` on principle rather than on taste. `const` on a
scalar attenuates a field that always existed; `insert objects[4]` manufactures a
target no producer emitted, and the resim would then be reproducing the recording
plus whatever the pipeline invented.

**Fixed slots do not shift.** `df`'s object list is a fixed-size array padded
with all-zero slots (`num_object_slots`). `drop objects[3]` there must **clear
slot 3 in place**, never compact 4→3, because compaction renumbers every
downstream index and silently breaks track association — a confidently wrong
answer, which is the failure mode this whole architecture exists to prevent. The
framework cannot guess which shape a port has, so it does not: the port declares
it, `fixed_slots: true`, in the same `conf/ports.yaml` that already declares the
port (`R-SIM-22`). One optional key, read generically, no component knowledge in
the framework.

**3. What is refused, and where it goes instead.** The audit's third example —
*"make the cut-in happen half a second earlier"* — is **not an override at all**.
It is a change to the scenario, and a scenario is already data
([sim_scenarios_and_expectations.md](sim_scenarios_and_expectations.md), `R-SIM-8`).
Answering it with an override would require a time-varying verb, which is a
schedule, which is a program. Time-varying and conditional overrides stay
refused; the honest answers are *edit the scenario* or *write a `stub:` stage*,
and both are files someone reviews.

**Cost.** Two verbs, one address grammar, one optional declaration key.
**What it replaces:** the `stub:`-stage escape hatch for the two most common
requests. **What it does not solve:** anything predicated or time-varying, by
design.

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

**`OQ-5` closes 2026-07-31, and the answer is that three other decisions already
made it.** The question was *"data volume through ctypes at raw-sensor injection
levels"*, and it named the wrong boundary. `NR-SIM-41`'s first measurement puts
the mcap read path at **46 µs/message at ≈300 MB/s** — that is zstd and I/O
inside C libraries, not interpreter overhead, and a C++ reader would not
meaningfully beat it. A 4 MB radar frame therefore costs ≈13 ms to *read* and
~1 ms to `memmove`, so at raw-sensor levels the cost is **storage and I/O
bandwidth, an order of magnitude above the language boundary**. The ctypes
crossing was never the risk.

That means level 3 needs no new mechanism, only the three already decided:

- **bulk data is referenced, never inlined** (`NR-SIM-43`, §5.3) — so a frame is
  read once and pointed at, not copied into a Scene per tick;
- **a port's bytes are parsed lazily** (`OQ-6`, recording §10) — so a resim that
  nobody plots never materialises a 4 MB message at all;
- **volume is declared and estimated before the run** (`NR-SIM-42`) — so the
  disk answer arrives before the disk does.

Restated as the honest limit: **raw-sensor injection is bounded by bytes moved,
not by the host language, and a bulk port is handed in by pointer into the
recording rather than copied.** The measurement that would falsify this stays
required (`GT-13`) and its trigger is unchanged — the first component with a bulk
port.

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
| today's stimulus recording | `DfObjList`, `VehDyn`, camera | df must be `simulate` |

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
| CARLA → `DfObjList`/`VehDyn` synthesis | production (a **mock**, tagged `mocked`) | `adas_sim.sources.carla.mocks` |
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

### 5.14 Failure behaviour — fail at load, warn in the HUD, never substitute

Fifteen places in these documents say something "raises naming both ends" or "is
a warning, not silence". That is a single policy, stated here once so it is
implemented once.

| Class | Examples | Behaviour |
|---|---|---|
| **Authoring error** — the YAML, pipeline or scenario is wrong | port type mismatch, missing producer, forward reference, `mode: measured` without the recording's topics, a timing predicate with no `within_s`, an unknown style token | **detected at load, never at first tick.** Non-zero exit, message naming the file, the key, and *both ends* of any mismatch |
| **Provenance warning** — the run can proceed but something is unverified | no config bundle, `provenance: unknown`, explicit config path whose project ≠ the built project, an output buffer that had to grow | run proceeds; surfaced in the **HUD and the run manifest**, not only in a log |
| **Hard fault** — a bug, or a real failure | ABI version mismatch, `adasExec` returning 0, a codec that cannot decode, a `stub:` stage under a host that cannot run Python | **fails immediately and loudly.** Never degrades, never substitutes a default |

The load-time rule is the load-bearing one: **every validation that can be done
before tick 0 is done before tick 0.** A 1200-tick run that dies at tick 900
because a port was misspelled has wasted the run and taught nothing.

The never-substitute rule is the second: a missing config bundle is *reported*,
not quietly replaced from the source checkout (`R-SIM-3a`); an unknown
provenance is *reported*, not assumed to be `measured` (`R-SIM-12`). Silent
substitution is how a viewer ends up confidently showing the wrong thing, which
is the failure mode this whole architecture exists to prevent.

### 5.15 The player — this is an application, not only a library

Read end to end, what §5.1–§5.14 describe is a **measurement/resim player**:
open a recording, choose per stage what is taken from measurement and what is
simulated, execute, watch it in a BEV, plot signals against each other, and
check it against expectations. That is the same class of tool as the reference
measurement/resim console, and it is worth saying so explicitly rather than
letting it be an emergent property nobody named.

#### It is already component-agnostic at build time — that was not an accident

Four rules combine to something none of them says alone:

| Rule | What it removes from the player's build |
|---|---|
| `R-SIM-1` | any component's name |
| `R-SIM-11` | generated protobuf bindings — schemas come from the DLL's manifest |
| `R-SIM-3a` | the config — it travels beside the DLL |
| `R-SIM-14` | any specific file format — codecs are registered |
| `R-SIM-13` | any world model — the viewer takes a `Session` |

**So the player can be built and shipped without any component existing**, and a
component appears at run time as data. That is exactly the model the reference
console uses — the tool ships; the component simulation libraries are plugged
in — and it is what makes this sustainable across `df`, `perception-core`, RSP
and whatever follows.

#### What ships, and what is plugged in

| Ships **inside** the player | Plugged in **at run time** |
|---|---|
| the framework (`core`, `contracts`, `scene`, `view`, `check`) | component libraries (`*_sil.dll`) + their `config/` bundles |
| the renderers and the format codecs | component `sim/` plug-ins — layers, pipelines, viewpoints, sensor models |
| the CLI and the GUI shell | recordings, scenarios, expectation sets |
| a bundled CPython + Qt runtime | — |

**One consequence that constrains the packaging.** Component `sim/` content is
Python. A frozen executable therefore **must keep an external plug-in import
path** — it cannot bake in only what it was built with, or adding LCA's layers
would mean rebuilding the player, which defeats the whole plug-in model. The
player takes a plug-in root (a component checkout, or a folder beside a DLL),
adds it to the import path at start-up, and discovers providers there exactly as
an unfrozen run does. Same shape as the reference console loading a simulation
DLL it was not built against.

#### Two delivery forms, one codebase

| Form | For | Needs |
|---|---|---|
| **`adas-sim` package** (Conan / importable) | algorithm developers, CI, scripting | the repo and a Python environment |
| **`adas-sim.exe`** (packaged application) | integration and validation engineers, anyone reviewing a run | nothing — no repo, no Python, no Conan cache |

The second is a *packaging* of the first, not a fork. Everything in the plan up
to that point produces the library; one stage packages it. **Windows first;
Linux is deliberately out of scope for now.**

#### Checked against the reference console (2026-07-28)

The reference measurement stack was examined directly — its shipped player
folder and the per-component simulation configs several components carry. What
it confirmed, what it changed, and the one place our design is deliberately
different:

**Confirmed, no change needed:**

| Reference | Ours |
|---|---|
| Component is a plug-in DLL named by path with `$VARIABLE$` substitution | `impl: "dll:{build}/…"` |
| Exposed ports alias an internal name to a pipeline-visible one | the port manifest *is* the alias table |
| `MeasFreeze` wired as a service per component | port freezes, derived from the manifest (`R-SIM-6`) |
| A cycle id declared **identically** for the live device and the recorded one | *executed and injected are indistinguishable* (`R-SIM-10`) — the same invariant, at the trigger level |
| Player ships per-device plug-in libraries **and** per-device raw-view libraries | codecs (`io/`) and layer providers, both plugged in at run time (§5.15) |
| Shipped tool lays out as `cfg/ · dll/ · ini/ · data/ · log/` | the S-D5 packaging shape |

**Changed as a result:** component-shipped **workspaces** (viz §13b),
**interaction-aware layers** (viz §7.5), and a **user-visible config-source
override** (§5.6). Each closed a real gap.

**Where ours is deliberately different, so it is not "fixed" later.** The
reference maintains **two visualization configs — online and offline** — because
some visualizers only exist offline (recorded images have no live counterpart).
We do not, and must not: a layer declares `requires=[ports]`, so one declaration
**degrades automatically** when a port is absent — a live run simply has no
camera-overlay layer, with nothing to maintain and nothing to drift. Two
hand-maintained variants of the same view is exactly the duplication class
`D5` came from.

#### The compatibility statement a shipped tool owes its users

A library can shrug at an old input; a shipped player cannot. It declares, and
enforces, exactly what it reads:

- **ABI generation** it can drive (`adasAbiVersion`);
- **Scene major** it can render (§5.3);
- **recording-model version** and **manifest version** it can open.

Anything outside that range is refused with both numbers named — the authoring/
hard-fault split of §5.14 applied to the product boundary. A player that
half-opens an old recording is the silent-wrong-picture failure this whole
architecture exists to prevent, arriving by a different door.

#### 5.15a Build or adopt the interactive viewer — the case, both ways

*Written 2026-07-31 for `NR-SIM-46` / `OQ-15`. **Decided 2026-08-05: the
recommendation below is adopted, unmodified** — `NR-SIM-46`'s own entry
records the decision; this section is kept as the case it was decided from,
not rewritten into a retroactive justification.*

**First, the number the question rests on is wrong.** `OQ-15` and the audit both
state that `render/` + `view/` + `viewer.py` are *"~3,000 of 8,300 lines — 36% of
the codebase spent on the least differentiated part."* Measured on the tree as it
stands:

| Package | Lines | Imports Qt? | Survives adopting an external viewer? |
|---|---|---|---|
| `render/viewer.py` | 1,417 | **yes** | no — this is the window |
| `render/bev.py` + `clip.py` | 415 | no | no — Scene → 2D drawing |
| `render/theme.py` + `palette_check.py` | 462 | no | **yes** — `SceneUpdate` needs colours too |
| `render/capture.py`, `plots.py`, `timeline.py` | 369 | no | **yes** — headless render, `sim render` |
| `view/*` (transport, layers, workspace, inspector, measure, hud, plots, timeline, viewport) | 1,167 | **no** | **yes** — headless view state, incl. `R-SIM-17`'s head/review model |

`render/` + `view/` is in fact **3,838 lines, 46%** — the audit understated it —
but only **1,832 lines (22%)** are replaceable by an external viewer, and of that,
the part with a genuine external equivalent — a BEV canvas — is **415 lines, 5%**.
`view/` imports no GUI toolkit at all; it is the headless state model, and an
adopted front-end would still need it, because Foxglove has no notion of *the
head* (`R-SIM-17`) and no per-stage `mode:`/`impl:` matrix to render.

**So the honest framing is not "36% on a window we could rent".** It is: *does
the 1,417-line Qt shell plus its packaging (`S-D5`) and productisation (`S-D8`)
earn its keep against `Scene` → Foxglove?*

| | Adopt (Foxglove/rerun primary) | Build (Qt console, as planned) |
|---|---|---|
| **What it removes** | 1,832 lines, Qt packaging, offscreen rendering, an installer, a GUI compatibility statement | nothing |
| **What it cannot do** | the pipeline panel (viz §13), the measured/simulate matrix, the severed-chain badge, `Open on Bench`, expectation markers, the evidence panel (§5.19) — none of these are scene rendering, and an external viewer has no pipeline to show | — |
| **Against `FR-SIM-70`** | *"install Foxglove, add this extension, open this file"* is a materially worse answer than a Windows executable, and fails `FR-SIM-47`'s `L-2` (≤3 steps to a moving picture) | meets it as written |
| **Ownership** | a third-party product with its own licence, release cadence and commercial dimension — a procurement decision, not only a technical one | ours, and `NR-SIM-45`'s bus factor is worst exactly here |
| **Sunk / remaining** | `S-B3` is built and green either way | `S-D5` + `S-D8` are the unbuilt, expensive half |

**Recommendation — split the window along the line the architecture already
draws, and do not treat this as a binary.** The `Scene` *is* the boundary:

1. **Keep the Qt shell as a *console*, not as a renderer.** Its differentiated
   content is the pipeline panel, the stage matrix, transport-against-the-head,
   expectations and evidence — everything that needs the engine. The BEV becomes
   one panel among several rather than the product.
2. **Promote `S-D1` (Foxglove `SceneUpdate`) from "a third renderer" to *the
   interop surface*** — first-class, tested, always available. That is the
   audit's own §12.4 advice (*"defer **or** promote to primary — a fork in the
   road, not a menu"*), taken in the promote direction, and it is what makes
   sharing, 3D and "a colleague with no install" real answers rather than
   aspirations.
3. **Scope `S-D5` to the console** and trim `S-D8`'s ambition accordingly.
   Vantage is a console with a BEV; it is not competing with a scene viewer.
4. **Defer `S-D2` (matplotlib)** with a named trigger: a figure that headless
   `sim render` cannot produce. Agreed with the audit.

This keeps 22% of the code that the differentiated 78% needs anyway, and it
declines to spend `S-D8` on out-rendering products whose renderer is their whole
business. **If the decision goes the other way** — adopt as primary — the cost is
bounded and known: `render/viewer.py`, `bev.py`, `clip.py` are deleted, `view/`
and `theme.py` stay, `S-D5`/`S-D8` collapse into a Foxglove extension, and
`FR-SIM-70` must be renegotiated in writing rather than quietly dropped.

---

### 5.16 One engine, two faces — and why there is not a second tool

Two tools were proposed, split by persona and scale: a project-level one for
mass runs, auditing and reporting, and a developer-level one that is permissive,
adaptable and lets someone do whatever they want to their own DLL. The
distinction between the two *users* is real. The conclusion that they need two
*engines* does not follow, and this section records why — so the question does
not get reopened in three months.

#### The reference tool, mapped onto this design

The reference resim/wiring console was examined concept by concept
(2026-07-28, from its own shipped example projects):

| Reference concept | Here | Same thing? |
|---|---|---|
| Component (a pipeline element DLL) | pipeline stage (§5.4) | yes |
| DLL-wrapper component | `impl: "dll:…"` | yes — different binding method |
| `bsig`/`rrec` readers, `bsig` writer | `io/` codecs (`R-SIM-14`) | yes |
| Datapool signal URIs | topic / port namespace (`R-SIM-4`) | yes |
| 2D viewer, signal plot, dashboard | renderers + plot panels (visualization spec §7.4, §11) | yes |
| Integrated/external Python component | `stub:` stage | yes |
| Machines — batch over a folder, playlists, combinators | **nothing** | **no — a real gap, §5.16.3** |

Nearly everything maps. There is **exactly one** genuine architectural
difference, and it is not a difference of tool:

> The reference console binds to binaries that never agreed to be bound — it
> recovers signatures from debug symbols, and a human then hand-writes every
> argument's mapping. We own our components, so we mandate a manifest
> (`R-SIM-4`) and **derive** the binding.

That is a **stage adapter**, not a second product.

#### 5.16.1 The developer's day one — no port mapping, no handoff

The workflow proposed for a new component was: build the DLL, use a wrapper to
map its ports, feed it from a reader, check the outputs — then later raise a
requirement for a platform team to incorporate it into the project-level tool.
The first, third and fourth steps are right. The other two must not exist here.

**Why the mapping step must not exist.** The reference wrapper is verbose
because the DLL is opaque; ours is not. A developer hand-mapping the ports of a
component **they just wrote** pays that cost without having that problem — and
the mapping becomes a *second* description of the port set, living in a project
file, free to drift from the manifest. That drift is what `R-SIM-4` exists to
prevent.

**Why the handoff step is dangerous.** "Later, ask the platform team to
incorporate it" puts a **queue between a developer and the platform**, and that
queue is the single most reliable cause of privately-written players — the
outcome this architecture is trying to avoid. With a manifest there is nothing
to incorporate: the component is in the tool the moment it builds, because the
tool discovers it exactly as `sim probe` did.

```
1. build the DLL on the generic ABI     ← the only integration work
2. sim probe df_sil.dll                 ← prints the port set, read from the DLL
3. reader → my stage → writer           ← a five-line pipeline
4. sim run                              ← outputs in a recording, inspectable
```

**Where the wrapper concept does survive:** `impl: "legacy:<lib>"`, for binaries
that genuinely cannot carry a manifest — supplier deliveries, prebuilt
third-party libraries, anything predating the ABI. Per-argument wiring is real
work there, and it is quarantined to those stages instead of being everyone's
default.

#### 5.16.2 Two faces over one engine

| | **Developer face** | **Project face** |
|---|---|---|
| Shape | interactive, one run | batch, N recordings |
| Posture | permissive — live poking, per-port overrides (§5.10), generic plots | locked — provenance-tagged, reproducible, reports |
| Stance | *"let me try something"* | *"prove it, for the record"* |
| Input | **the same pipeline YAML** | **the same pipeline YAML** + a scenario list and a mode matrix |

Splitting the engine instead would produce two namespaces, two project schemas,
the handoff queue above, and — fatally — **what the developer validated would
not be what the project runs**, which destroys the audit value the project face
exists for. The property worth protecting is that a developer's own debugging
setup *is* the artifact that goes into the mass run; they add a list around it
and re-express nothing. That is unavailable the moment the engines differ.

Both faces may write the pipeline file directly, as the reference GUI does —
a file that is hand-writable, GUI-writable and diffable, with **no window
geometry inside it** (§5.16.4).

#### 5.16.3 What is missing for scale, honestly

Two capabilities the reference tool has and this design does not, both small on
top of what already exists:

- **`sim batch`** — run a pipeline over a folder or list of recordings,
  headless, one report. This is the reference tool's playlist/folder machinery,
  and it is how resim scales past one file. There is currently **no way to
  express "run this over 500 recordings"**.
- **`sim convert`** — recording → recording across formats, which the codec
  table (`R-SIM-14`) already gives for free once readers and writers are
  symmetric; only the verb was never named.

Deliberately **parked**: the reference tool's generic signal explorer over the
whole datapool. Useful, large, and not needed until someone asks.

#### 5.16.4 What is deliberately not copied

- **Window layout inside the project file.** In the reference tool's own
  examples, over half of a 16 kB project file is dock geometry. It makes the
  pipeline undiffable and unreviewable. Here: pipeline in git, window layout in
  user state (visualization spec §13b).
- **A component catalogue keyed by DLL path.** That is what produces an
  `Unknown MO` entry — a config referencing a binary that is not there, with no
  statement of what was expected. Here: keyed by component name, resolved
  through the manifest, and a miss is a load error naming both ends (§5.14).
- **Configuration spread across several independent surfaces.** The reference
  console's blank-screen failure is diagnosable only by checking a config tree,
  a component's properties and a data-source setting in turn. Here, one file per
  run and one load-time validation pass.

---

### 5.17 Rate — resolving `OQ-2` before it becomes expensive

`OQ-2` asked whether multi-rate components need more than "one tick grid with a
growing age". It is answered here rather than left open, because it is a
**data-model** decision: `Tick`, `Session`, the recorder and every layer
provider are shaped by it, and discovering the answer at `S-C1c` means reworking
all four.

Real chains are multi-rate — radar, camera and fusion do not tick together — so
"they all tick at once" is not a simplification we get to keep.

#### The three options, and why the middle one wins

| | Model | Keeps `Session` an array? | Verdict |
|---|---|---|---|
| **A** | One grid, everything executes every tick | yes | **rejected** — forces every stage to the fastest rate, which is neither what the ECU does nor what the recording contains |
| **B** | One **base grid**, per-stage **declared period**, scheduled execution | **yes** | **chosen** |
| **C** | Event-driven, no grid, latest-value semantics | **no** | rejected — most general, but it destroys `Session[i]`, and with it O(1) seek and the whole two-pass model (§6.4) |

C is what a real bus does, and that is exactly why it is wrong here: we are not
a bus, we are a **deterministic re-execution** of one. Giving up the array to
model a bus faithfully would cost the property the viewer is built on.

#### B, stated precisely

- **A stage declares its period** in its manifest — `period_ns`, beside its
  ports (`R-SIM-4`). Rate becomes *discovered*, exactly like ports, rather than
  assumed by the host.
- **The base grid is derived**, not configured: the greatest common divisor of
  the declared periods. A period that is not an integer multiple of the base is
  a **load error naming both numbers** — there is no rounding, because a
  rounded period accumulates into a drift that looks like an algorithm bug.
- **A stage executes only on its due ticks.** On every other base tick its
  outputs are **held**: `updated=False`, and `age_s` grows exactly, from integer
  nanoseconds.
- **A stage may declare a phase offset**, so two stages of equal period can be
  ordered deliberately rather than by declaration accident.

**The consumer contract does not change**, and that is the point: a stage always
receives its full port set, with some values older than others — which is
precisely what it sees in the vehicle. `R-SIM-10`'s invariant survives intact:
*executed* and *injected* still produce the same port set, and a consumer still
cannot tell which it got.

#### What this buys, and the one thing it deliberately refuses

Recording is unaffected in shape: a message is written **when produced**, so a
slow topic is simply sparse — which every codec already handles, and which makes
a recording's own message density the honest record of what ran.

The refusal: **the scheduler is ideal.** Perfect periods, no jitter, no drift.
That is not naivety, it is where the fidelity belongs — **jitter, latency and
drop are sensor/bus *error models*** (`R-SIM-9`), injected per scenario and
therefore *testable*, rather than ambient properties of the runner that would
make every resim non-reproducible. A tool whose scheduler jitters cannot tell
you whether your algorithm is sensitive to jitter; one with an ideal scheduler
and an injectable jitter model can.

---

### 5.18 Fault containment — what happens when the component under test dies

§5.14 classifies *errors the framework can observe*: a bad YAML, a version
mismatch, an `adasExec` returning failure. It does not cover the failure most
likely to actually occur when running native code under test:

> **the component crashes the process, or hangs.**

A segfault in a DLL loaded in-process takes the Python host with it. Today that
would mean an overnight run of 500 recordings dies on recording 3 and reports
nothing — which fails the mass-scale goal completely, and fails it silently.

#### Isolation is a property of the *face*, not a global setting

| | Default | Why |
|---|---|---|
| **Bench** (interactive, one run) | **in-process** | A crash should be immediate, with the stack, and a debugger attachable. Isolation here would hide what you are trying to see |
| **Campaign / `sim batch`** | **one subprocess per recording** | A crash marks that recording and the batch continues. Isolation at *run* granularity, so the per-tick cost is zero |

Plus an explicit `mode: isolated` per stage, for the interactive case where you
are bisecting *which* stage crashes and want the others to survive.

#### Three outcomes that must never be merged

A run ends in exactly one of these, and a report that collapses them is a report
that sends the wrong person to investigate:

| Outcome | Means | Owner |
|---|---|---|
| `fail` | an expectation was not met | the algorithm |
| `crash` | the process died — signal, or non-zero exit | the component's code |
| `timeout` | `exec()` did not return within its declared budget | the component's code, but a *different* bug, and the more confusing one |

A **per-`exec()` timeout** is required, not optional: a hung DLL is as damaging
as a crashing one and much harder to diagnose, because the symptom is "the batch
is still going".

#### A crash must be reproducible, or it will not be fixed

The batch records, for every crash: the recording, the pipeline, the last tick
reached, the captured stderr, and the `run_id` (`N-9`). Those five are exactly
what `Open on Bench` (`sim_player.md` §5) needs to reproduce it **in-process**,
where a debugger can be attached.

That round trip — *crash in Campaign, reproduce on Bench, fix, re-run Campaign* —
is the loop that makes crashes get fixed rather than retried. Without it, a
crash in a 500-run report is a line of text nobody can act on.

### 5.19 The evidence chain — from a thing on screen to the bytes that produced it

*Added 2026-07-31, answering audit finding `A4` / `FR-SIM-67` / `R-SIM-25`.
`OD-6`.*

The way a visualization tool dies is not a crash. It is a developer who sees
something odd, cannot confirm where it came from, stops believing the window, and
goes back to `printf` — after which every other feature is sunk cost. The design
already has good instincts pointed at this (`R-SIM-7`'s `derived` marker,
`R-SIM-3a`'s bundle provenance, per-topic origin tags, `sim explain` for names).
**What it did not have is the join.** `Prim.pick_id`, `PortValue.origin`, topic
provenance, `bundle_origin` and `run_id` all exist, in five places, related by
nothing.

#### The join already exists — it was never written down

No new capture is needed, because three keys are already present and already
unique:

| Key | Present since | Answers |
|---|---|---|
| `run_id` | `S-A1` (`N-9`) | the run manifest: config bundle, component builds, pipeline, overrides |
| `Layer.id` → the provider's **resolved** `requires` | `R-SIM-21` / `S-C9` | which ports fed this layer, and therefore which topics and origin tags |
| `Prim.pick_id` | `S-A3` | which entity *within* the layer |

So the chain is a **query over recorded facts**, not a new index to maintain.
That is why the audit calls it the cheapest high-value addition available, and
the assessment is correct.

#### One producer, two formatters

```python
@dataclass(frozen=True)
class Evidence:
    address:       str            # what was asked about, as typed
    kind:          str            # port | field | prim | layer | signal
    value:         str            # the value at that tick, formatted
    tick:          int
    t_ns:          int
    port:          str | None     # resolved address (R-SIM-21), never a literal
    topic:         str | None     # the recording topic that carried it
    origin:        Origin         # measured|truth|mocked|simulated|overridden|unknown
    published:     bool | None    # True: the SUT emitted it. False: a layer rebuilt it
    stage:         str | None     # pipeline stage, with its mode: and impl:
    overrides:     tuple[str, ...]   # verbs applied to this port or field
    faults:        tuple[str, ...]   # fault injections targeting it
    config_bundle: str | None     # hash + which source resolved (embedded/library/checkout)
    component:     str | None     # build_id, library sha, abi version, manifest sha
    plugin:        str | None     # plug-in bundle id + hash that produced the layer
    run_id:        str
```

**Two rules govern it, and they are the whole design:**

1. **`Evidence` is assembled only from recorded facts.** A field it cannot fill
   is `None`/`unknown` — never inferred, never defaulted to a plausible value.
   This is `§5.14`'s never-substitute rule applied to the one surface whose entire
   purpose is being believed. An evidence panel that guesses is worse than none.
2. **There is exactly one producer and two formatters.** `evidence(address,
   session, tick)` returns the record; the GUI panel renders it and
   `sim explain <signal> --at <tick>` prints it. *"GUI and headless answer
   identically"* is then structural rather than a discipline — which is the same
   shape `GT-9` already requires of every other capability, so it costs no new
   principle.

`address` accepts either a signal address from the one address space
(`NR-SIM-8` — `df.bsd.outputs.left.warning`) or a prim reference
(`<layer_id>#<pick_id>`). Both resolve into the same record. In the GUI the prim
reference is free, because the renderer hit-tested the prim it actually drew
(viz §7.1) and therefore already knows its layer.

#### The one field this adds, and what it replaces

`Prim` gains **`derived: bool = False`**. `Layer.derived` already exists, but a
layer legitimately *mixes* — it draws the SUT's own warning state *and* a zone
polygon reconstructed from calibration — and a per-layer flag makes the honest
answer impossible for exactly the case `R-SIM-7` cares about. The two are then
bound so they cannot disagree: **a layer with `derived=False` may not contain a
prim with `derived=True`**, checked in `Layer.__post_init__`.

So `Layer.derived` keeps its job (the `…(derived)` badge in the layer panel) and
stops being a lie for mixed layers. That is what the field replaces: not a
feature, an inaccuracy.

#### The hole this exposes, and closes

A plotted sample may come from a **computed** signal (`@signal`), not from a raw
port field. Computed signals currently declare nothing about their inputs, so the
chain would stop at them — and a hole in an evidence chain is worse than no
chain, because it is invisible. Therefore `@signal` declares its inputs the same
way `@layer_provider` declares `requires=`, resolved at load by the same
`R-SIM-21` path. One decorator argument; no new mechanism.

#### The limit, stated

The chain answers **where a value came from**. It does not answer **why the
algorithm produced it**, and it must not pretend to: it stops at the component
boundary, because inside `adasExec` there is nothing the framework can see. The
only way further in is a SIL-only `<fn>.debug` ProPort, which stays parked
(§11) with its trigger unchanged. An `Evidence` record that reached inside the
SUT would be a reconstruction, i.e. exactly the `derived` case it exists to flag.

Second limit: evidence is only as good as the recording's provenance. A file with
no manifest yields a record that is honestly full of `unknown` — which is the
correct answer and is why `Provenance.UNKNOWN` exists.

**Alternatives rejected.** *A `port` field on `Prim`* — a prim is usually built
from several ports (an object box needs `objects` *and* the pose), so one field
would force a lie or a list, and the layer already declares the true set.
*A side-car provenance index written per run* — a second description free to
drift from the manifest, which is `FR-SIM-46`'s own rejected onboarding step
wearing a different hat. *GUI-first, with a headless exporter later* — the
headless path is the one CI and reports use, and a second implementation of "what
produced this" is how the two stop agreeing.

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
| D12 | Shim grows per component | `conf/ports.yaml` + generated table/manifest/dispatch — `R-SIM-22`, plan `S-C1d` |
| D13 | Plug-in port address is a literal, failing silently | Component-relative binding, resolved at load, error on miss — `R-SIM-21`, plan `S-B1`/`S-C1c` deltas + `GT-11` |
| D14 | A recording's topics never reach a port; the one bridge is hardcoded in the framework | Declared ingest map owned by the recordings' owner + a feasible-cut query — `R-SIM-23`, plan `S-C9` |

**Two invariants the 2026-07-31 adversarial audit added are not defect closures
but *evidence* obligations**, and belong here because every defect above is
closed by an argument that assumes them. `R-SIM-24` — determinism is **measured**
along the four axes that break it (same process, fresh process, rebuilt binary,
different machine) under one declared tolerance policy; today only the first is
exercised, which is the axis that cannot fail. `R-SIM-25` — every rendered value
is **traceable** to the bytes that produced it, joining `Prim.pick_id`,
`PortValue.origin`, topic provenance, `bundle_origin` and `run_id`, which exist
separately and are never connected. Full reasoning:
[sim_requirements.md](sim_requirements.md) §12 (`A1`, `A4`).

**`D12` and `D13` are both "the closed defect, one level up."** Worth stating as
a standing check rather than a one-off finding: after closing a defect of the
form *"X is written N times by hand"*, ask where the **new** X is written by
hand. `D1` moved the growth from the ABI into the shim (`D12`); `D3` moved the
hardcoding from geometry into the port name (`D13`). The next candidate is
already visible — `S-C3`'s `expect:` strings and `S-D3`'s workspace files will
be the third and fourth places a port address is spelled by a human, and both
should be resolved through the same binding path `R-SIM-21` introduces rather
than growing their own. *`D14` then found the third instance before that
prediction could be tested, in a place the pattern did not predict — the
**ingest** side of recording. Generalising once more: the question is not only
"where is X written by hand" but **"which side of this boundary did we
specify?"** `R-SIM-6` specified how we *write* a recording in complete detail
and left how we *read someone else's* as a migration note; `GT-1` guards the
framework and not the plug-in. Both defects are on the unspecified side.*

**The next boundary to check, before something crosses it:** `sources/` ↔ the
world model (`S-C2`) and `check/` ↔ a scenario's `expect:` strings (`S-C3`).
Both are one-sided today.

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
a 50-slot `DfObjList` plus outputs is a few kB — a 1200-tick session is
single-digit MB. Camera frames are the exception and are held by reference into
the recording, decoded on demand.

Live **sim** cannot do pass 1 ahead of time — the world is producing stimuli as
you watch. It therefore appends to the Session as it goes: you can seek
backwards into what has already happened, and "live" is simply the tail. Same
code, one flag.

#### The head — why stepping backwards leaves execution mode

Generalising that flag gives the concept the whole transport is defined against
(`R-SIM-17`). The **head** is the furthest tick computed so far.

| Where | What it is | What is possible |
|---|---|---|
| **behind** the head | immutable data | seek, scrub, step back, toggle layers, re-render — free, never re-executes |
| **at** the head | live execution | run / pause, step forward, advance-N |

This is why *step backward* is not the mirror of *step forward*. Forward calls
`exec()`; backward would have to **undo** it, and the SUT holds state the ABI
does not expose — filters, counters, hysteresis. There is no inverse `exec()`
and there will not be one.

So stepping backwards **leaves execution mode and enters review**, which is
exactly right and costs nothing: everything already computed stays fully
scrubbable. Resuming forward from behind the head then offers precisely two
honest choices, both named in the UI:

- **skip to head** — resume where execution actually is; or
- **recompute from tick 0** — deterministic resim only (`R-SIM-5`), exact, and
  cheap at these tick counts (a 1200-tick session is well under a second of
  `exec()` calls).

What is forbidden is the third option a naive implementation reaches for:
silently continuing from the rewound position, so the SUT sees tick 400's
stimulus with tick 900's internal state. That is a fabricated run that looks
plausible — the failure mode this architecture is most concerned with.

Periodic state snapshots would make true rewind-and-continue possible, and are
**parked**: they need an ABI addition (`adasSaveState`/`adasRestoreState`) and
no requirement asks for it. Recomputing from zero covers the case today.

---

## 7. Scaling to perception — one worked instance of §5.10

§5.10 gives the general mechanism (injection level as pipeline data, stand-ins
as stages). This section walks the specific case, because it is the one that
lands first and it is the one the current bridge is silently doing already.

The user's requirement is that this architecture must accept perception —
which does not exist yet — without redesign. Concretely:

**Today**

```
CARLA actors ──(bridge synthesises)──► DfObjList ──► df ──► AebOutputs/BsdOutputs
```

**With perception**

```
CARLA sensors ──► camera frames ─┐
                  radar dets   ──┴─► perception-core ──► DfObjList ──► df ──► outputs
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

Twenty-one stages in five phases (C1 lands as three sub-stages). Each stage is independently landable and leaves
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
| **C5** | Packed config bundle (§5.6): build copies `project.yaml` + `shared_config`'s `vehicle/ego_params.yaml` + port manifest into the library's own output directory (`$<TARGET_FILE_DIR:…>/config/` — **never** a hand-written `…/Release/…` path, which is a multi-config-generator artefact that does not exist under Make or Ninja), hashed; `adasInit(NULL)` resolves it module-relative; `adasManifest()` reports project + bundle hash; bundle embedded in recordings | A build output plus its `config/` runs on a machine with no Conan cache and no checkout; the viewer provably reads the same bytes the DLL read; a project/bundle mismatch is a warning, not silence |
| **C6** | Resim + determinism in CI (`NR-SIM-25`, `NR-SIM-40`) | `sim check` runs on every push; `sim determinism` reports all four axes with the axis **derived** from the two runs' manifests |
| **C7** | `sil_host` reads the same pipeline file (`FR-SIM-65`) | One pipeline file runs unchanged under both hosts, with byte-identical results |
| **C8** | Plug-ins delivered beside the library (`R-SIM-20`, `FR-SIM-64`) | `vantage <dir>` renders with no checkout, no `PYTHONPATH` |
| **C9** | Recording ingest + feasible cuts (`R-SIM-23`, closes `D14`) | An existing recording states which ports it provides and which cuts it supports, **before** a run |

> **This table is content, not order.** Phase C is built in the sequence given by
> [sim_implementation_plan.md](sim_implementation_plan.md) §0a, which is *not* id
> order: `S-C0` runs first, four model-level deltas follow, and `S-C9`, `S-C4`
> and `S-C8` are each built earlier than their ids suggest. The plan is the
> authority on sequence; this section is the authority on what each stage
> contains.

### Phase D — Reach

| Stage | Content | Done when |
|---|---|---|
| **D1** | Foxglove `SceneUpdate` renderer + Scene-in-mcap sink | An exported mcap opened cold shows the full spatial scene with working layer toggles and seek |
| **D2** | matplotlib renderer; `bsdviz` figure driver migrated onto the framework | The 53 BSD figures regenerate byte-stable from the shared framework; live view and figures use one palette |
| **D3** | GUI on run manifests; `.claude` artifacts finalised | Every run is launchable from the GUI as a manifest; skills/workflows landed |
| **D4** | Perception: sensor sources, `perception`/`ground_truth` layer groups, `CameraModel` + image-projection renderer | A pipeline with two components runs, and perception output vs ground truth is visible side by side |
| **D5** | **Package the player** (§5.15): frozen Windows build, external plug-in import path, compatibility statement | The build opens a session recording on a machine with no repo, no Python, no Conan cache — and drives a component that did not exist when it was built |
| **D6** | **Developer ergonomics** (§5.10, §5.16): per-port overrides, `sim probe`, severed-chain auto-close | A new component is probed, wired and run without one edit inside `modules/sim` — and `GT-8` is measured on a real newcomer |
| **D7** | **Writers, exports, `sim convert`, `sim batch`** (§5.16.3, recording §7) | One pipeline file runs over a folder of recordings and produces a report; an export can never be fed back as a resim input |
| **D8** | **Vantage** — the shell plus the *Bench* and *Campaign* workspaces ([sim_player.md](sim_player.md)) | A stranger reaches a moving picture in under two minutes unaided (`MC-5`), and one pipeline file survives a workspace switch byte-for-byte |

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
  **This sentence was written as settled fact and was not**, which the
  2026-07-31 review corrected. Until `S-C7` lands it is an *intention*: today
  `sil_host` is 54 lines of `main.cpp` calling `dfInit`/`dfExec`/`dfShutdown`
  positionally against exactly one component, with no pipeline reader, no
  wiring, and no notion of a second stage. `S-C1b`/`S-E2` only move that one
  call site onto the generic ABI — they do not make this sentence true. The
  discrepancy was visible as `OQ-11` in [sim_sil_contract.md](sim_sil_contract.md)
  §9 while this section asserted the opposite; two documents disagreeing about
  whether a capability exists is exactly what `GT-7` is for. **Resolved in
  favour of building it** (`S-C7`), because the alternative — softening the
  claim — would leave "one concept, two hosts" as a slogan, and because the
  engine is small once C1 holds: read the pipeline file, load N libraries by
  manifest, wire ports by name, tick. The pieces it needs (`R-SIM-4`'s manifest,
  `R-SIM-18`'s declared period, `R-SIM-10`'s `mode:`/`impl:` semantics) are all
  `S-C1a`/`S-C1b` outputs already sitting in `interfaces` as protobuf and C.
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

**What `sil_host` is *for*, stated positively**, since "the C++ one" is not a
purpose. Its job is to **run a complete pipeline in simulation with no Python in
the process** — and that single sentence implies everything else about it:

- *Complete pipeline*, so it needs the pipeline reader and the N-stage wiring
  that `S-C7` adds. One component ticked in a loop is not a pipeline, and is not
  what this executable exists to be.
- *No Python*, so timing measured here is trustworthy, `stub:` stages are
  unavailable by construction, and a stand-in it needs is promoted to a
  `stubdll:` rather than reimplemented (the rule above).
- *In simulation*, so it consumes recordings and stand-ins — it is not a
  production integrator, and it never acquires a world-model client.

Everything `sil_host` must **not** become follows from the same sentence: not a
recorder (that is `sources/` + `io/`), not a viewer (that is `R-SIM-13`), and
never its own object generator (§9's standing rule). It is the pipeline engine
without the studio around it.

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

### OD-5 — Product and workspace naming — **CONFIRMED: Vantage / Bench / Campaign**

Settled 2026-07-28, in answer to `FR-SIM-48`. **Vantage** is the application,
**Bench** the developer workspace, **Campaign** the
project-scale workspace — both replacing internal working names used during
design. Full reasoning:
[sim_player.md](sim_player.md) §1.

Three properties were required of the answer, and they are what rule out the
alternatives:

- **Plain English, not invented words.** `R-SIM-16`'s whole claim is that these
  are two faces of one product. Two coined names would teach the opposite before
  anyone read a document.
- **The product name is not the code name.** `modules/sim`, `adas-sim` and the
  `sim` CLI are unchanged, so renaming the product later is a marketing change
  and not a refactor. Enforced by `UT-D8-9`.
- **A workspace is a mode of one window**, switched with one key, with the open
  pipeline file surviving the switch byte-for-byte (`UT-D8-1`). If the switch
  had to convert anything, the two-engine design would have won by the back
  door.

Rejected: naming the CLI after the product (churn across every document for no
gain); *Studio*/*Lab* for the developer face (both imply authoring, and this
face analyses); *Fleet*/*Batch* for the project face (the first is about
vehicles, the second about scheduling — neither carries "produces a report
someone reads").

### OD-6 .. OD-13 — the 2026-07-31 concept-resolution pass

Taken in answer to the adversarial audit (`sim_requirements.md` §12) and to the
open questions it sharpened. Each is stated in full in the section named, with
its rejected alternatives; this table exists so the decision list stays complete
and so none is silently re-made.

| ID | Decision | Where | Closes |
|---|---|---|---|
| **OD-6** | **The evidence chain is a join over facts already recorded, with one producer and two formatters.** No new index, no new capture; `Prim` gains one `derived` flag, `@signal` declares its inputs | §5.19 | `A4`, `FR-SIM-67`, `R-SIM-25` |
| **OD-7** | **Bulk arrays are referenced into the recording, never inlined in a `Prim`;** `SceneCache` bounds by bytes | §5.3 | `A5`, `NR-SIM-43` |
| **OD-8** | **`select`/`drop` are added over repeated fields; arithmetic stays closed at four; an override may destroy but never create an entity** | §5.10 | `A8`, `OQ-10` |
| **OD-9** | **A message carries two integer-nanosecond stamps — reception and capture — with capture `None` when unknown, never defaulted to reception** | recording §3.3 | `A6`, `CR-SIM-4` |
| **OD-10** | **Determinism is two gates and two measurements, not four gates; tolerance exists only on the axes that may legitimately differ, is declared per component with a mandatory `why:`, and is printed on every passing report** | recording §4 | `A1`, `NR-SIM-40`, `OQ-7` |
| **OD-11** | **One config bundle per component, permanently; a pipeline asserts project agreement and hard-fails on disagreeing ego params** | contract §9 | `OQ-1` |
| **OD-12** | **`period_ns` is calibration: declared per function in integer microseconds in the config bundle, reported through the manifest, and the DLL's own `updated` flag is authoritative over the predicted schedule** | contract §9 | `OQ-12`, `DF-1` |
| **OD-13** | **A `PortValue` retains bytes and parses lazily; windowing a `Session` is rejected as the primary answer because it would break free backwards seek** | recording §10 | `OQ-6` |

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
