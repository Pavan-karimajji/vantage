# Simulation Platform — Master Requirements Register

Status: **frozen 2026-07-28.** Every requirement, question and constraint raised
during the 2026-07-27/28 design sessions, captured as a numbered register so
that nothing has to be re-derived from memory or re-litigated later.

This is the **source** document. [sim_architecture.md](sim_architecture.md) and
its siblings are the *answers*; [sim_implementation_plan.md](sim_implementation_plan.md)
is the *execution*. When the three disagree, this register says what was
actually asked for.

Reading order for someone new: this file → `sim_architecture.md` →
`sim_implementation_plan.md`.

---

## 0. How this register works

| Field | Meaning |
|---|---|
| **ID** | `FR-SIM-n` functional · `NR-SIM-n` non-functional/quality · `CR-SIM-n` constraint |
| **Requirement** | what was asked for, in the terms it was asked in |
| **Origin** | when it was raised, and the verbatim phrasing where the exact words carry the meaning |
| **Answered by** | the design section and/or rule that resolves it |
| **Verified by** | the test that proves it, from the implementation plan |
| **Status** | `frozen` (decided, not built) · `open` (still a question) · `parked` (deliberately not designed) |

Verbatim quotes are kept **because the phrasing is the requirement** — "scrolling
snapshots blah blah all that are needed" is a real instruction to enumerate the
feature set rather than guess at it, and paraphrasing would lose that.

---

## 1. Architecture & scalability

### FR-SIM-1 — One framework, N functions
**Requirement.** The simulation stack must absorb the roadmap's remaining
driving functions without editing shared files each time.
**Origin.** 2026-07-27: *"right now in df aeb bsd are there but there is plan
for lot of other front and rear safety features like lca lka acc ldw and so
on."*
**Answered by.** Scene IR + layer-provider registry (arch §5.3); named ports
(arch §5.4, `R-SIM-4`). Adding a function = one layer file + one manifest line.
**Verified by.** `UT-B1-1`, `GT-1`. **Status.** frozen.

### FR-SIM-2 — One framework, N components
**Requirement.** Adding a component (perception-core, RSP, planning) must not
touch the framework, the host, or any other component.
**Origin.** 2026-07-28: *"multiple components if added tomorrow then also this
concept has to be added easily."*
**Answered by.** Arch §5.13 extension-point table — the right-hand column is the
list of things that must *not* change.
**Verified by.** `UT-C1c-2`, arch §5.13. **Status.** frozen.

### FR-SIM-3 — Scale to perception
**Requirement.** The concept must extend to perception, which does not exist
yet — camera views, plotting, "everything" pluggable.
**Origin.** 2026-07-27: *"right now its all for driving functions, the
architecure proposal you are giving should help me to also scale it up for
perception that is not there yet but camera view or plotting or whatever
everything should be easily plugged into this one."*
**Answered by.** Arch §7 (worked instance) and §5.10 (the general mechanism);
`perception` / `ground_truth` / `perception.error` layer groups; camera panel
(viz §11.4); **plot panels (viz §7.4)** and the dockable peer-panel grid
(viz §11.1).
**Verified by.** `ST-D4-1`, `UT-B3-6..10`. **Status.** frozen (D4 gated on
perception-core existing).

### CR-SIM-1 — The framework names no function
**Requirement.** The framework must not know about AEB, BSD, LCA, ACC, LDW, LKA.
**Origin.** Derived from FR-SIM-1/2; made a hard rule so it cannot erode.
**Answered by.** `R-SIM-1`; `modules/sim` vs `modules/<name>/sim/` split
(arch §5.7).
**Verified by.** `GT-1` (a grep, re-run every stage), and `UT-A1-3` which
asserts the check itself fails on a planted violation. **Status.** frozen.

---

## 2. Visualization

### FR-SIM-10 — A state-of-the-art 2D BEV, and it is *the* developer view
**Requirement.** Excellent visualization; the 2D BEV is the primary developer
view, to be usable wherever needed.
**Origin.** 2026-07-27: *"excellent visualization"*, *"state of the art
structure"*; 2026-07-28: *"2d bev is the right developer view I want to use it
wherever needed."*
**Answered by.** Whole of `sim_visualization_spec.md`; the feature checklist
(§16) is the enumerated answer — 34 features, each marked works / partial /
absent with the stage that delivers it.
**Verified by.** viz §16 checklist; `MC-1`. **Status.** frozen.

### FR-SIM-11 — Enumerate the BEV feature set rather than guess
**Requirement.** The BEV's features are to be *checked* and completed — the
asker did not have the list.
**Origin.** 2026-07-27: *"features of 2d bev also to be checked, scrolling
snapshots, blah blah all that are needed"*, and *"I am not in a stage to put of
this well, i think you can."*
**Answered by.** viz §16 — the 34-row checklist, produced as the deliverable.
**Verified by.** each row's own stage. **Status.** frozen.

### FR-SIM-12 — Time transport ("scrolling")
**Requirement.** Scrub through a run.
**Origin.** 2026-07-27: *"scrolling"*.
**Answered by.** Two-pass Session (arch §6.4) + viz §5. Backwards seek is
possible only because executing and viewing are separated — today it is
impossible by construction.
**Verified by.** `UT-B2-2` (backwards seek), `ST-B2-1`. **Status.** frozen.

### FR-SIM-13 — Snapshots
**Requirement.** Snapshot a moment of a run.
**Origin.** 2026-07-27: *"snapshots"*.
**Answered by.** viz §9 — PNG + **provenance sidecar** (tick, project, scenario,
pipeline, build hashes, viewport, layers, theme), print-quality variant, video
export of a marked interval, and a headless `sim render`.
**Verified by.** `UT-B4-1`, `ST-B4-1` (two renders of the same tick are
byte-identical). **Status.** frozen.

### FR-SIM-14 — Plotting as a first-class, pluggable panel
**Requirement.** Plotting must plug into the same concept.
**Origin.** 2026-07-27: *"camera view or plotting or whatever everything should
be easily plugged into this one."* **Found missing during the 2026-07-28 audit**
— only a timeline strip existed, which is a transport companion, not an analysis
surface.
**Answered by.** viz §7.4 (timeseries / xy / state / distribution panels over
the one signal address space, see `NR-SIM-8`) and §11.1 (dockable peer-panel
grid).
**Verified by.** `UT-B3-6..10`, `UT-B4-3`. **Status.** frozen.

### NR-SIM-1 — Visualization is constant regardless of data origin
**Requirement.** The visualization concept must not change whether data comes
from mcap, CarMaker, or anything else.
**Origin.** 2026-07-28: *"this visualization concept I want to keep it constant
eventhough if its from mcap or from carmaker simulation whatever it is."*
**Answered by.** `R-SIM-13` — **the viewer's only input is a `Session`**; it
never talks to a world model, a DLL or a file. Nothing in the visualization spec
names a world model or a format, and nothing in it ever may.
**Verified by.** `ST-B1-1`, viz §1. **Status.** frozen. *Limitation stated: live
viewing requires that we own the loop; a simulator that owns its own loop has
its own live view and ours runs from its recording.*

### NR-SIM-2 — One picture, many media
**Requirement.** Implicit but load-bearing: a requirement figure and a live run
must be the same picture.
**Origin.** Derived from defect **D5** (two rendering stacks drew the BSD zone
in two different colours with two coordinate helpers).
**Answered by.** Semantic style tokens + one theme table per medium (viz §3);
one Scene behind the interactive, print and Foxglove renderers.
**Verified by.** `ST-D2-2`. **Status.** frozen.

### NR-SIM-3 — The Scene IR must evolve without breaking recordings or goldens
**Requirement.** Derived, and found missing in the 2026-07-28 review: the Scene
is serialized into recordings, goldens and a Foxglove stream, so it is a wire
format and will gain fields.
**Answered by.** Arch §5.3 — `major.minor` on `Scene`; additive changes are
minor and an old reader skips what it does not know; a removal/rename/unit
change is major and a reader that cannot handle it **refuses, naming the
version**. Protobuf codec chosen for exactly this property. Goldens record their
version.
**Verified by.** `UT-A3-8`, `UT-A3-9`. **Status.** frozen.

### NR-SIM-4 — One failure policy: fail at load, warn in the HUD, never substitute
**Requirement.** Derived, and found missing in the 2026-07-28 review: fifteen
places said "raises naming both ends" or "is a warning, not silence" without a
single stated policy.
**Answered by.** Arch §5.14 — three classes (authoring error / provenance
warning / hard fault) with the rule that *every validation possible before tick
0 happens before tick 0*, and that a missing bundle or unknown provenance is
reported rather than quietly replaced.
**Verified by.** `UT-A3-4`, `UT-C1c-6..10`, `UT-C5-3`, `UT-C3-3`.
**Status.** frozen.

### NR-SIM-5 — The viewer stays responsive on a long run
**Requirement.** Derived: pass 1 over ~1200 ticks on the UI thread would freeze
the window, defeating the scrubbing requirement it exists to serve.
**Answered by.** viz §11.1 — pass 1 on a worker with progress and a viewable
tail; pass 2 on the UI thread, cheap because Scenes are cached and providers are
pure. Per-tick parallelism is left available by that purity, not built.
**Verified by.** `MC-4`, `ST-B2-2`. **Status.** frozen.

### NR-SIM-7 — The tick model must carry what the specs already promise
**Requirement.** Derived from a 2026-07-28 critical re-read: four things the
design promised elsewhere were unimplementable against the `Tick` as modelled.
**Answered by.** Arch §5.2 —
(a) a port is a **`PortValue`** (message + `age_s` + `valid` + `updated` +
`origin`), not a bare message, so the stale/invalid banner (`UT-B3-5`),
multi-rate visibility and per-port provenance become possible;
(b) time is **integer nanoseconds**, `t_s` derived for display, so the
bit-identical-resim guarantee does not rest on float accumulation;
(c) `Tick.pose` carries the **ego pose in world**, without which the `world`
follow mode and every trajectory layer are unimplementable;
(d) a layer provider receives **`LayerCtx`** (model + read-only windowed
`history` + `frames`), without which trails and track history cannot be drawn —
purity is preserved because history is an *input*, not accumulated state.
**Verified by.** `UT-B1-11`, `UT-B1-12`, `UT-B2-6`, `UT-B3-5`.
**Status.** frozen.

### NR-SIM-8 — One signal address space
**Requirement.** Derived: the design had a `@timeline_signal` decorator for the
viewer and a `signal:` path grammar for expectations — two address spaces for
one concept, which drift.
**Answered by.** viz §7.4 — one grammar
(`<component>.<port>.<field>` · `source.*` · `truth.*` · `derived.*`), one
resolver, five consumers (timeline, plots, HUD, expectations, diff). Raw port
fields need no registration because the manifest declares their type; only
computed signals register, with `@signal`. Anything plottable is assertable.
**Verified by.** `UT-B3-6`, `UT-C3-6`. **Status.** frozen.

---

## 3. Configuration

### FR-SIM-20 — Geometry comes from configuration, per project, at run time
**Requirement.** Ego length/width (and everything physical) must come from the
YAMLs so the picture adapts per project at run time.
**Origin.** 2026-07-27, the headline ask: *"take information from configurations
(for example ego length and width from yamls and use them for right plotting so
runtime based on each project visualization gets adapated)."*
**Answered by.** `ProjectModel`/`EgoModel`/`ObjectModel`/`SensorModel`
(arch §5.5); `R-SIM-3`. Deletes `EGO_LENGTH_M = 4.3` and
`OBJECT_LENGTH_M = 4.5` from the viewer.
**Verified by.** `UT-A2-1/2`, `ST-A2-1` (equivalence with today's values),
`ST-B1-2` (switching project visibly changes the drawn ego). **Status.** frozen.

### FR-SIM-21 — Configuration is packed with the build, beside the DLL
**Requirement.** The build should pack the configuration where the DLL is.
**Origin.** 2026-07-28: *"once we build this we get it inside the build and pack
them inside the build where we get the dll itself what do you think?"*
**Answered by.** **OD-4** (arch §5.6) — one atomic hashed bundle per
(project, build) in `<library_dir>/config/`; `adasInit(NULL)` resolves it
module-relative; `adasManifest()` reports project + bundle hash; the bundle is
embedded in recordings. **Copied beside the DLL, never compiled into it** —
baking it in would kill the edit-a-value-and-re-run calibration loop.
**Verified by.** `UT-C5-1..5`, `ST-C5-1`. **Status.** frozen. **Reverses**
plan.md item 19's 2026-07-22 decision — see §6.

### CR-SIM-10 — `shared_config` and the bundle hold real runtime config only
**Requirement.** `shared_config` is for realistic/real-time configuration.
Nothing simulation-specific may enter it or the packed bundle.
**Origin.** 2026-07-28: *"shared_config we will be using for realtime
configrations and information. any carla related values and all are shouldnt be
packed here as they are only simulation related. whatever build packs is never
simulated type ones."*
**Answered by.** `R-SIM-9` + the admission table (arch §5.6): a file enters the
bundle **iff some component's DLL reads it at run time**.
**Verified by.** `UT-C5-4`; the admission table is the review check.
**Status.** frozen.

### CR-SIM-11 — World-model specifics live with the tooling
**Requirement.** CARLA-specific values belong in the Python tooling, not in the
build bundle.
**Origin.** 2026-07-28: *"you have to pack the carla related specification in py
file related place for tools but not bundle it withing build as its not sil
specific."*
**Answered by.** Three homes by change rate (scenarios §4.2): per-scenario in
`world.carla:`; engine constants in `adas_sim/sources/carla/`; the
blueprint→class catalogue in `sources/carla/catalogue.yaml`.
**Verified by.** the admission table; `GT-3`. **Status.** frozen.

> **Correction this forced.** An earlier draft proposed migrating sensor poses
> and class footprints into `shared_config`. **Withdrawn** — `BSD_SENSOR_*` and
> `BSD_CLASS_*` are already runtime calibration the DLL reads
> (`bsd_params.cpp:96,119`), already in `df`'s own `default.yaml`, with one
> consumer, and `shared_config_plan.md` §1 already froze that file as
> permanently local to `df`. The real defect was narrower: `bsdviz/sensors.py`'s
> `P3`/`P4`/`P5` are a hand-maintained **duplicate** of those keys. Stage
> **C4** just deletes the duplicate; `shared_config` gains nothing.

### NR-SIM-6 — Calibration sweeps must not require a rebuild
**Requirement.** Derived, and surfaced by reviewing OD-4 critically: if the
config bundle is a build output, a parameter sweep — the core calibration
workflow — would need N builds.
**Answered by.** Arch §5.6 "Overrides and sweeps" — a run may declare
`run.overrides:`; the framework materialises a derived bundle, hashes it, and
records the base hash **plus the override set** in the manifest. Provenance
stays a statement rather than a warning, and an A/B diff can attribute a
difference to the parameter. Authoring homes untouched — an override is a run
property, never an edit, and never writes back.
**Verified by.** `UT-C5-6`, `UT-C5-7`. **Status.** frozen.

---

## 4. Interfaces — Python ↔ C

### FR-SIM-30 — A proper architecture for the Python↔C boundary
**Requirement.** The protobuf-based Python-to-C adaptability needs a defined
architecture.
**Origin.** 2026-07-27: *"also we have python to c adapatability i think we are
doing with protbuf that also should have good architecute to be defined."*
**Answered by.** `sim_sil_contract.md` — one generic ABI
(`adasInit`/`adasExec`/`adasShutdown`/`adasManifest`/`adasAbiVersion`) with
**named port sets**, plus a per-component manifest generated from
`ENABLED_FUNCTIONS`. Adding a function adds a manifest line, never an ABI
parameter. `df_ctypes.py` is deleted.
**Verified by.** `UT-C1b-1..8`, `ST-C1b-1`, `ST-C1c-1`. **Status.** frozen
(**OD-2**).

### NR-SIM-10 — A host must not require generated bindings or a sibling checkout
**Requirement.** A component must stay independently resimmable.
**Origin.** 2026-07-28: *"with this sim outside df we cant do resim only with df
repo. Am i correct."*
**Answered by.** `R-SIM-11` — `adasManifest()` carries the `FileDescriptorSet`,
so message classes are built from the DLL that produced the bytes; plus the
config bundle travelling with the DLL and `adas-sim` being a Conan package.
Arch §5.9 shows the count of checked-out modules **goes down**, from
`df` + `interfaces`(built) + `shared_config` to `df` + a downloaded package.
**Verified by.** `UT-C1c-3` (bindings deliberately not importable), `GT-6`.
**Status.** frozen. *The premise was corrected: today's resim already needs
three modules, not one.*

---

## 5. Simulation modes, levels and sides

### FR-SIM-40 — Correct vocabulary: sim / resim / replay
**Requirement.** "Replay" is the wrong word.
**Origin.** 2026-07-27: *"as mentioned for sil sim and resim (replay is wrong
word I guess)."*
**Answered by.** Arch §1 — *sim* (live world, non-deterministic), *resim* (SUT
re-executed against a recording, deterministic, the only thing that goes in CI),
*replay* (a recorded result rendered, no computation). `R-SIM-5`.
**Verified by.** naming discipline; `ST-C2-2` proves resim determinism.
**Status.** frozen.

### FR-SIM-41 — One concept for every level of simulation
**Requirement.** From df-alone with CARLA-mocked objects, up to a full chain
(RSP → perception → fusion → functions), the concept must scale — and
`sil_host` must not end up with its own object generator.
**Origin.** 2026-07-28: *"how do we do df alone sim with simulating obj inputs
from carla py bridge and then tomrrow if it goes till full sil-host sim … how
does this concept scale … but sil-host pipeline in future will also simulate the
objects from code itself right."*
**Answered by.** `R-SIM-10` — object synthesis is a **stand-in for a missing
component**, i.e. a pipeline stage, never a source feature. Depth is data;
a downstream component's pipeline entry is byte-identical across levels.
`sil_host` runs `dll:`/`stubdll:` stages plus `mode: measured` injection and
**never grows its own object generator**.
**Verified by.** `UT-C1c-10..14`, `ST-C1c-2`. **Status.** frozen.

### FR-SIM-42 — Per-component measured vs simulated, from a GUI
**Requirement.** A console where you set, per component, whether it is taken
from measurement or simulated — as the reference measurement/resim toolchain
does.
**Origin.** 2026-07-28: *"we have gui where we set which components are taken
from measurement and which components has to be simulated. thats how the tool
looks for us. does any concept like this will work as a single solution for us
for any level of simulation?"*
**Answered by.** Adopted wholesale. It forced splitting one field into two:
**`mode:`** (`simulate`/`measured`/`off`) = *executed or injected*, and
**`impl:`** (`dll:`/`stub:`/`stubdll:`) = *by what*. `impl:` is retained on a
`measured` stage so the toggle is reversible in one edit. GUI surface: viz §13.
The invariant that makes it a single solution: *a stage's interface is its port
set, and executed and injected produce the same port set — a consumer cannot
tell which it got.*
**Verified by.** `UT-C1c-11/13`, `UT-D3-1..4`. **Status.** frozen.

> **This amended `R-SIM-6`**: record every stage's inputs **and outputs**.
> A stimulus-only recording supports exactly one cut point; a recording with
> every stage's outputs supports any. Two recording grades result — *stimulus*
> vs *session*, the latter being this project's equivalent of a measurement.

### FR-SIM-43 — Two sides: producing a recording vs executing one
**Requirement.** Two distinct stories — (a) resim a measurement containing
freezes of all ports, and (b) an algo test where perception and VDY are mocked
from CARLA into an mcap, then df is simulated and the rest taken from
measurement.
**Origin.** 2026-07-28: *"I have some measurement coming from a source may be in
mcap format only … where I have all measurement freezes (measfreeze) from all
ports of the code. and then other case for algo test resimulation where I will
have to mock the perception and vdy from carla and create an mcap out of it …
so 2 sides are there for this story."*
**Answered by.** Arch §5.11 + `R-SIM-12`. Production and consumption are
independent concerns joined only by the artifact — today's `carla_bridge.py`
does both at once, which is why it is 983 lines. **A mock belongs on the
production side by default**: freeze it into the mcap, then resim with that
stage `measured` and only the component under test `simulate` — the canonical
algo test, reproducible with no world model present, shipped as an
*isolate ‹component›* preset. CLI verbs name the sides: `sim record` (produce
only) · `sim run` (both) · `sim resim` (execute an artifact).
**Verified by.** `ST-C2-1`, `ST-C1c-2`. **Status.** frozen.

### CR-SIM-20 — A mock is not a measurement
**Requirement.** Derived from FR-SIM-43: a manufactured recording and a real one
share a format, not an evidence grade.
**Answered by.** Per-topic origin tags — `measured` / `truth` / `mocked` /
`simulated` (recording §3.5). Today every topic would be `truth` or `mocked`,
and nothing records that.
**Verified by.** `UT-C2-8`. **Status.** frozen.

### CR-SIM-21 — Which cuts a recording supports is a property of the recording
**Requirement.** Derived: a manufactured stimulus mcap has no df outputs, so df
must be `simulate` there; a real measurement allows any cut.
**Answered by.** Read from the topic index at load; the GUI disables what the
file cannot support; `mode: measured` against a recording lacking that stage's
outputs is a **startup error**, never a partial injection.
**Verified by.** `UT-C1c-10`, `UT-D3-2`. **Status.** frozen.

---

## 6. Recording, formats and foreign simulators

### NR-SIM-20 — Changing the recording format must be easy
**Requirement.** Tomorrow the format may not be mcap.
**Origin.** 2026-07-28: *"tomorrow if I change from mcap to another format, the
architecture should allow me to make changes easily (to accept new input format
easily)."*
**Answered by.** `R-SIM-14` — a recording is a **model**
(`meta` + `topics{schema, provenance}` + `(topic, log_time, bytes)`); a format
is a **codec** of ~4 methods in `adas_sim.io.<fmt>`, registered by extension,
with declared capabilities that degrade explicitly. Anticipated: MDF4/MF4,
CarMaker results, rosbag2.
**Verified by.** `UT-A4-7`, `ST-A4-1`. **Status.** frozen.

> **Correction this forced.** An earlier module layout listed `sources/mcap`
> beside `sources/carla`, blurring a file decoder and a simulator client into
> one word. Split: `io/` = format codecs, `sources/` = world-model clients.

### FR-SIM-50 — CarMaker
**Requirement.** How does the concept work with CarMaker, given CarMaker is a
test run with its own executable?
**Origin.** 2026-07-28: *"how does it work with carmaker is second question i
have. sim concept should be able to work correctly because carmaker is going to
be a test run with an exe right."*
**Answered by.** Arch §5.12 — **a codec, not an integration.** CarMaker runs as
a normal test exe and writes its native results; `adas_sim.io.carmaker` converts
them to a recording; everything downstream is unchanged. This is §5.11's point
applied: production and consumption joined by a file.
**Verified by.** plan.md item 4. **Status.** frozen.

### FR-SIM-51 — CarMaker closed loop
**Requirement.** Component-level and full-chain simulation *inside* CarMaker.
**Origin.** 2026-07-28, then explicitly de-prioritised the same day: *"if
carmaker simulation concept doesnt have any problem then just ignore it. lets
not make it a big deal."*
**Answered by.** If ever needed: a `Pipeline` exposes the same generic ABI as a
single `SilComponent`, so a foreign host links one thing and gets whatever depth
the pipeline YAML declares.
**Status.** **parked** — not designed. Every run today is open-loop read-only by
deliberate choice, and plan.md item 6 (actuation + arbiter) does not exist yet.

---

## 7. Repo structure & ownership

### FR-SIM-60 — Move visualization out of `df`
**Requirement.** Take the visualization concept outside `df`; possibly a SIL
package.
**Origin.** 2026-07-27: *"right now we are keeping it in df carla folders, but
we may need to also plan on how it will get a good shape to take this
visualizatoin concept outside df. may be as a sil package or whatever."*
**Answered by.** `modules/sim` submodule (arch §5.7). Rejected alternatives are
recorded there with reasons.
**Verified by.** `ST-E1-3`, `GT-1`. **Status.** frozen.
*Confirmed later against the reference stack's own `mf_plot` — a peer component
module described as a "plotter for function/measurement analysis", i.e. the same
structural choice. Difference is language only (theirs C++, in-process; ours
Python, dev-time), and the Scene is serializable so a C++ renderer stays a
future adapter rather than a rewrite.*

### FR-SIM-61 — Clarity on what lives in `df` vs the superproject
**Requirement.** A clear statement of the split.
**Origin.** 2026-07-28: *"but then the question is what are you keeping in df
and what are all inside 1v-superproject. give me clarity."*
**Answered by.** Arch §5.8 — the placement map, with a four-step decision rule
and a table per repo.
**Status.** frozen.

### FR-SIM-62 — A module's docs live with the module
**Requirement.** `modules/sim` should be a proper repo with its own `docs/`, and
the design docs moved there.
**Origin.** 2026-07-28: *"also I recommend creating sim inside modules and make
it like proper git repo already create docs folder and move all the mds
accordingly what say?"*
**Answered by.** Done. Placement rule refined in arch §5.8: **docs follow their
module** (as `modules/df/docs/bsd/` already does); root `docs/` keeps what no
single module owns. The test is *ownership*, not *audience*.
**Status.** frozen.

### FR-SIM-63 — Scenario **instances** stay with the component that owns their expectations
**Requirement.** Should scenario creation be part of `sim` or part of `df`?
**Origin.** 2026-07-28: *"Now I am think scenario creation should be part of sim
folder or part of df … why i got this question is ebcause of this md file …
sim_scenarios_and_expectations.md inside sim repo."*
**Answered by.** **The schema, the engine and the validation are `sim`'s; the
cases are the component's.** The decisive constraint is `CR-SIM-1`: a scenario's
`expect:` block names component ports (`df.bsd.outputs.left.warning`), so
scenarios in `modules/sim` would put function names in the framework and `GT-1`
would fail. Full reasoning and the promotion trigger: scenarios doc §0.
**Verified by.** `GT-1`. **Status.** frozen.

### FR-SIM-70 — The outcome is a **player application**, not only a library
**Requirement.** What this exercise is actually building is a measurement/resim
player — porting/ingest, resim at any cut point, visualization, plotting — in
the same class as the reference measurement/resim console, deliverable as a
Windows executable.
**Origin.** 2026-07-28: *"arent you trying to create some player which could be
an executable (in win …) that has all of these feature of porting, resim,
visualization and all like mts."* **Not covered before this** — the design
described a library for developers with a repo and a Python environment, and
never named the application or its users.
**Answered by.** Arch §5.15. The architecture already makes it possible:
`R-SIM-1` + `R-SIM-11` + `R-SIM-3a` + `R-SIM-14` + `R-SIM-13` together mean the
player is **component-agnostic at build time** and can ship before any component
exists, with components appearing at run time as data — the reference console's
own model. Two delivery forms from one codebase: the `adas-sim` package for
developers and CI, and a packaged `adas-sim.exe` needing no repo, no Python and
no Conan cache. **Windows first; Linux deliberately out of scope.**
**Constraint it imposes:** a frozen executable must keep an **external plug-in
import path**, or adding a function's layers would mean rebuilding the player.
**Verified by.** `ST-D5-1`, `ST-D5-2`, `ST-D5-3`. **Status.** frozen.

### NR-SIM-9 — A shipped player owes an explicit compatibility statement
**Requirement.** Derived from `FR-SIM-70`: a library may shrug at an old input;
a distributed tool may not.
**Answered by.** Arch §5.15 — the player declares and enforces the ABI
generation, Scene major, recording-model version and manifest version it can
open; anything outside is refused **with both numbers named**, per §5.14's
hard-fault class. Half-opening an old recording is the silent-wrong-picture
failure arriving by a different door.
**Verified by.** `UT-D5-1`, `UT-D5-2`. **Status.** frozen.

---

## 8. Delivery & process

### NR-SIM-30 — Nothing is deleted before its replacement is proven
**Requirement.** `df` must end up clean and neat, with the removal planned.
**Origin.** 2026-07-28: *"i hope you also have planned what has to be removed
from df to make clean and neat."*
**Answered by.** Implementation plan §8 (Phase E) — a table of ≈3,530 lines,
each row naming the stage that must be green first, plus what moves and what is
kept untouched.
**Verified by.** `ST-E1-1..4`. **Status.** frozen.

### NR-SIM-31 — Incremental, checkbox-tracked, tested at every step
**Requirement.** A structured, sequenced implementation plan with unit and
system test cases per entity, tickable as work lands, thoroughly tested by the
end.
**Origin.** 2026-07-28: *"create right checkboxes so that as implementation goes
in bit and pieces we will mark each as done … implementation plan should be in a
sequence where it should be incremental along with their tests … by end of this
implementation concept till end everything has to be thoroughly tested."*
**Answered by.** `sim_implementation_plan.md` — 20 stages, 281 checkboxes, 102
unit tests, 40 system tests, 7 global gates re-checked every stage, 4 named
manual checks, a traceability matrix.
**Verified by.** `ST-E3-2` (the final full-suite gate). **Status.** frozen.

### CR-SIM-30 — All work on feature branches
**Requirement.** Not on `main`.
**Origin.** 2026-07-28: *"also create feature branches and not main where we
make all changes."*
**Answered by.** `feat/sim-platform` in all five repos; `R-GIT-1`/`R-GIT-2`.
**Status.** frozen.

### NR-SIM-32 — Promote decisions into the AI operational layer
**Requirement.** Update the skills so the approach is state of the art.
**Origin.** 2026-07-27: *"the outcome of this exercise is a very detailed
concept plan architecture design and at the end updating the skills wherever
needed to make the approach stae of the art."*
**Answered by.** `.claude/rules/sim.md` (`R-SIM-1..14`), skills
`sim_scene_layers` / `sim_visualization_patterns` / `sil_python_binding`,
`workflows/add_sim_layer.md`, `templates/sim_layer_provider.py`, plus routing
and cross-references. Recorded in `docs/ai_operational_layer_spec.md` §8 as a
new subject area added after that spec was frozen.
**Verified by.** `ST-E3-1`. **Status.** frozen.

---

## 9. Decisions register

| ID | Decision | Date | Reverses |
|---|---|---|---|
| **OD-1** | Qt (PySide6) for the interactive viewer; Foxglove as the share/interop renderer; matplotlib as the print renderer | 2026-07-27 | — |
| **OD-2** | The generic named-port ABI **now**, not a descriptor over today's `dfExec` | 2026-07-27 | — |
| **OD-3** | **Defer** renaming `tests/carla_scenarios/` until CarMaker lands | 2026-07-27 | — |
| **OD-4** | Pack an atomic hashed config bundle beside the DLL | 2026-07-27 | **plan.md item 19** (2026-07-22 "keep the pointer") |

Two design reversals made during the sessions, kept visible so they are not
silently re-made:

1. **`adas-sim` is a Conan package**, not pip-editable-only. The earlier call
   ignored the partial-clone requirement — `pip install -e ../sim` needs the
   checkout, so it never solved the problem it was chosen for.
2. **Sensor poses and class footprints do not move to `shared_config`.** See
   `CR-SIM-10`.

And one sequencing correction found in the 2026-07-28 audit:

3. **Phases A and B touch no C++ and no DLL.** The viewer is built on pure
   *replay* of already-exported mcaps, which avoids needing a `df`-specific
   ctypes binding inside the framework before the generic ABI exists — a
   `CR-SIM-1` violation that the original ordering would have forced.

---

## 10. Explicitly parked

Recorded so that "we never thought about it" is never the explanation.

| Item | Why parked | Trigger to revisit |
|---|---|---|
| 3D scene graph | The Scene IR is 2.5D; no requirement asks for orbiting 3D | a requirement that needs it |
| Closed-loop actuation into a world model | Every run is open-loop read-only by design | plan.md item 6 existing |
| CarMaker closed loop (`FR-SIM-51`) | De-prioritised by the asker | a scenario requiring it |
| HIL | Nothing precludes it — a `sources/` implementation over a real bus | a rig existing |
| Sensor error models (noise, latency, dropout) | The slot and preset mechanism are defined; the models are not | BSD coverage work needing honest degradation |
| Multi-run statistics / KPI dashboards | `sim check` reports pass/fail, not analytics | enough scenarios for an average to mean something |
| Renaming `tests/carla_scenarios/` | OD-3 | CarMaker landing |
| Promoting sensor mounting to `shared_config` | One consumer today | a second function/component needing the same physical sensor |
| Debug ProPorts (`<fn>.debug`) | Re-derived layers are marked `derived=True` as a stopgap | the first disagreement between a reconstruction and the DLL |

---

## 11. Open questions

| ID | Question | Where it is discussed |
|---|---|---|
| OQ-1 | One config bundle per component, or one per pipeline? | contract §9 |
| OQ-2 | Multi-rate components — one tick grid with growing `ageS`, or something more? | recording §5 |
| OQ-3 | Computed scenario anchors vs. constants with `from:` provenance | scenarios §9 |
| OQ-4 | Fault-injection vocabulary beyond today's `roll_fault` | scenarios §9 |
| OQ-5 | Data volume through ctypes at raw-sensor injection levels | arch §5.10 |
| OQ-6 | Windowed `Session` for very long runs (36 000+ ticks) | recording §10 |
| OQ-7 | Cross-machine / cross-compiler determinism | recording §10 |
