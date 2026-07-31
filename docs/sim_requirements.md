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
| **Status** | `frozen` (decided, not built) · `partial` (decided in outline, a named part undesigned) · `open` (still a question) · `parked` (deliberately not designed) |
| **Priority** | `P0` the tool is not usable without it · `P1` a stated goal degrades without it · `P2` valuable, deferrable. **Unmarked means `P1`** |

**Why a priority field exists.** An earlier version of this register had 54 rows,
all `frozen`, all equally mandatory. That provides no guidance at the exact
moment guidance is needed — when time runs short and something must give. The
three levels are deliberately coarse; a finer scale would just move the
argument rather than settle it.

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
asserts the check itself fails on a planted violation. **Priority.** `P0` — the boundary that makes the framework reusable at all. **Status.** frozen.

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
**Answered by.** viz §16 — the checklist, produced as the deliverable.
**Verified by.** `DC-4` (every checklist row names the stage that delivers it,
so no row can be quietly dropped) plus each row's own stage gate.
**Status.** frozen.

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

### FR-SIM-15 — A component ships a default workspace
**Requirement.** Opening a recording should give a sensible arrangement of
panels, not an empty grid the user assembles by hand.
**Origin.** 2026-07-28, inferred from the reference measurement console's
visualization config, whose layout is a tree of tabs, splitters and named views
with ratios. Our design had per-user saved layouts but no **component-shipped
default** — half the mechanism.
**Answered by.** viz §13b — `modules/<name>/sim/workspace.yaml`, composing
panels + viewpoints + signals declared elsewhere. A default, never a lock; the
user's own layout wins and `Reset layout` returns to it. `R-SIM-1` holds: the
framework reads the file and does not know what the component is.
**Verified by.** `UT-B3-11`, `UT-B3-12`. **Status.** frozen.

### FR-SIM-16 — Layers may react to interaction, without becoming stateful
**Requirement.** A layer must be able to follow the cursor or highlight a
selection — a crosshair, a measurement aid, click-a-detection.
**Origin.** 2026-07-28, inferred from the reference console, where a render
context declares `MouseListener` / `KeyboardListener` / `WindowListener`. Our
providers could not do either: they are pure functions of a tick with no way to
know where the pointer is.
**Answered by.** viz §7.5 + arch §5.3 — the interaction **state**
(`cursor` in the layer's own frame in metres, `selection`, `modifiers`,
`toggles`) is carried on `LayerCtx`, and a provider declares `reacts_to=`. Not
an event callback, which would put UI state inside the one thing that must have
none. The provider stays a pure function of `(tick, ctx)`, so caching and golden
tests are unaffected — the cache key simply includes interaction for layers that
declare a dependency on it.
**Verified by.** `UT-B3-13`, `UT-B3-14`. **Status.** frozen.

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
**Verified by.** `UT-B3-15` (**pass 1 does not run on the GUI thread**, asserted
on thread identity with a deliberately slow reader — not on elapsed time, which
would pass on a fast machine with the bug present), `UT-B3-16` (a cancelled load
leaves no partial `Session` reachable), `UT-B2-12` (the Scene cache respects a
stated bound, so responsiveness does not decay into memory exhaustion on a long
run), `ST-B2-2`, `MC-4`.
*Strengthened 2026-07-28:* this previously rested on `MC-4` and `ST-B2-2` alone
— a human saying it felt responsive, and a timing budget. Neither can fail when
the work is on the wrong thread but the machine is fast, which is exactly how a
threading defect reaches a slower machine. **Status.** frozen.

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

### FR-SIM-47 — The UI and the concept must be lean, and not frightening
**Requirement.** A developer looking at the tool should understand what to do,
and not be put off by the apparent size of it.
**Origin.** 2026-07-28: *"UI and concept should be so lean that developer by
looking at it should understand what to do and not get scared whats all of
this."*
**Answered by.** [sim_player.md](sim_player.md) §2 and §6, which turn this into
three measurable limits rather than a sentiment: **L-1** at most 12 controls
visible at rest, **L-2** at most 3 steps from launch to a moving picture,
**L-3** at most 4 concepts before first use (*recording, pipeline, stage,
layer*). The design set contains roughly forty concepts; the other thirty-six
are revealed **only when something is abnormal** — provenance tags appear when a
port is not `simulated`, the config bundle appears when it is missing, codec
capabilities appear inside the error a degrade produces. The rule is *a concept
earns screen space by being wrong.*
**Verified by.** `MC-5` (a newcomer reaches a moving picture in under two
minutes with no instructions, then explains `measured` vs `simulate`
unprompted), `UT-D8-5` (control count in the default layout), `UT-D8-6`
(a fully normal run shows no provenance, bundle or capability notice at
all), `ST-D8-2` (three actions to a moving picture), `GT-8`.
**Priority.** `P0` — if it is not usable, nothing else in this register matters. **Status.** frozen.

### FR-SIM-49 — Naming conventions must be appropriate for debugging
**Requirement.** The naming conventions are not only for tidiness — they must
make debugging easier.
**Origin.** 2026-07-28: *"naming conventions also should be also appropriate for
debugging."*
**Answered by.** [sim_naming_and_diagnostics.md](sim_naming_and_diagnostics.md)
— `N-1..N-13` plus the diagnostics contract `DG-1..DG-5`. The premise it is
derived from: a run passes through seven layers (world → codec → recording →
wiring → SUT → provider → renderer), and the entire debugging task is deciding
**which of the seven lied**. Every rule is chosen so one name answers that, and
each is checked by **the isolation test** — paste the name alone into a message;
can a colleague say what it is, who produced it and where to look? `objects`
fails; `perception-core.gen_object_list` passes.

The load-bearing ones: **one token in every layer** (`N-1`) so a single grep
returns the whole vertical slice; **no translation tables** (`N-6`) so the log,
the file and the column header cannot disagree; **every object reprs its own
name** (`N-7`); **an error names expected, found, where it looked and a next
action** (`N-8`), made mandatory by the exception constructor so a bad message
is an author-time `TypeError`; **one `run_id` joins all six artefacts** (`N-9`);
**a fixed, greppable log line with a closed `event=` vocabulary** (`N-10`).
Diagnostics turn names into questions: **`sim explain <name>`** (`DG-2`) and
**`sim doctor`** (`DG-3`), both of which read only what the system already
knows — no new index to maintain.
**Verified by.** `UT-A1-5` (repr), `UT-A1-7` (run id), `UT-C1b-9` (one token),
`UT-A4-10` (no translation), `UT-B4-4` (correlation), `UT-D6-7`, `UT-D6-8`,
`UT-D8-8` (message contract), `ST-D7-4`. **Status.** frozen.

### FR-SIM-48 — Name the player and its two workspaces
**Requirement.** Good names for the master player and for the two stages inside
it — one for project-scale simulation, one for the developer.
**Origin.** 2026-07-28: *"algo give good names for master player and also for 2
stages inside that one one for sim (ltmts) and other for developer one (ltmb).
or you are free to choose whatever type of segregation and naming is expected."*
**Answered by.** [sim_player.md](sim_player.md) §1 — **Vantage** (the
application), **Bench** (developer workspace, was `ltMB`), **Campaign**
(project workspace, was `ltMTS`). Plain English on purpose: `R-SIM-16`'s claim
is that these are two faces of one product, and two invented words would teach
the opposite. The product name is deliberately **not** the module, package or
import name — `modules/sim`, `adas-sim` and the `sim` CLI are unchanged, so a
rename stays a marketing change rather than a refactor. A workspace is a mode
of one window, switched with one key, **with the open pipeline file surviving
the switch untouched**.
**Verified by.** `UT-D8-9` (no product or workspace token anywhere in
`adas_sim/` outside `app/`), `UT-D8-1` (the pipeline file's bytes survive a
workspace switch), `GT-9`.
**Status.** frozen.

### FR-SIM-17 — Step-wise execution: play, pause, step, advance-N
**Requirement.** Run the algorithm step-wise — start, pause, one step forward,
one step backward (which stops the simulation, because backward is not
applicable), and run-forward by a chosen count: 50, 100, 200 or custom.
Reference: the measurement application's transport toolbar.
**Origin.** 2026-07-28: *"speaking of running algorithm in step wise it would be
good to have start, pause, one step forward, one step backward (this should stop
simulation because backward isn't applicable), run too forward where he can
choose 50,100,200, custom steps to advance the recording simulation steps."*
**Answered by.** `R-SIM-17` + viz §5/§5.1/§5.2 + arch §6.4 *"The head"*. The
asker's own caveat is the design: **backward is not the mirror of forward.**
Forward calls `exec()`; backward would need to undo it, and the SUT holds state
the ABI does not expose — so stepping back **leaves execution mode and enters
review**, where everything already computed stays freely scrubbable via the
two-pass Session. Resuming forward offers exactly two named choices — *skip to
head* or *recompute from tick 0* (deterministic resim only) — and never the
third one a naive implementation reaches for, silently continuing from the
rewound position so the SUT sees tick 400's stimulus with tick 900's state.
Advance-N runs as one cancellable job with progress. Snapshot-based true rewind
(`adasSaveState`/`adasRestoreState`) is **parked** — no requirement needs it.
**Verified by.** `UT-B2-7..10`, `ST-B2-3`. **Status.** frozen.

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

### FR-SIM-22 — The config source is overridable and always displayed
**Requirement.** The embedded → library → checkout resolution order must be a
default, not a lock.
**Origin.** 2026-07-28, inferred from the reference console, which exposes
exactly this as a per-artifact-kind user toggle (*use the description from the
recording, or from disk*). An embedded bundle can be stale, and testing a new
calibration against an old recording is a real workflow.
**Answered by.** Arch §5.6 — `--config-source embedded|library|checkout|<path>`
and a GUI dropdown; **whichever was used is always displayed**, because a silent
override recreates the confusion the bundle exists to remove.
**Verified by.** `UT-C5-8`. **Status.** frozen.

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
**Verified by.** `UT-C1c-10`, `UT-D3-2`. **Status.** frozen — **mechanism added
2026-07-31 by `FR-SIM-66`.** The requirement was correct and had no
implementation: `UT-C1c-10` is the *failure* path (a `measured` stage whose
outputs are missing raises), which is not the same as reading a topic index and
answering the question. "Read from the topic index at load" also silently
assumed topics *are* port names, which holds only for recordings this framework
produced (`D14`).

### FR-SIM-66 — Vantage must adapt to recordings it did not produce, at whatever depth they were cut
**Requirement.** The player must open a component's existing test-run
recordings — which carry only that component's own ports, at one depth — and
resim against them; and must do the same for another team's recordings, in
another format, cut at a different depth, without a framework change.
**Origin.** 2026-07-31: *"here the challenge will be because these bsd mcaps
doesnt contain full chain of effect inputs, it directly gives objects, I think
we need to think if its possible to make them run with vantage correctly.
tomorrow imagine perception guys have similar test runs where they only created
scenarios with specific ports needed for them in mcaps (or any other format).
vantage should be able to adapt to it and all of this happens in my view with
strong port consistency and good vantage preprocessing step. there are 2
dimensions here. 1st is multiple types of recordings. 2nd is multiple stages of
ports coming as inputs."*
**Answered by.** `R-SIM-23` + arch `D14`. **Both dimensions are real and are
already separated in the design — one is solved, one was named and not built:**

| Dimension | Status | Where |
|---|---|---|
| **1 — multiple recording *types*** (mcap, MF4, CarMaker, "any other format") | **solved** | `R-SIM-14`: a recording is a model, a format is a codec of ~4 methods registered by extension, with declared capabilities |
| **2 — multiple *depths* of ports as input** (objects-only vs detections-only) | **named, not mechanised** | `R-SIM-10` gives per-stage `mode:`/`impl:`; `CR-SIM-21` asserts the recording knows its own cuts; nothing reads a topic index and answers |

The missing piece is the asker's own *"good vantage preprocessing step"*, and
their *"strong port consistency"* is exactly the precondition for it
(`R-SIM-21`/`R-SIM-22`). **One boundary is added to the idea:** preprocessing is
**declaration, never computation** — renaming and origin-tagging only. A
preprocessing step that computes is an unversioned algorithm between the
recording and the SUT, so a resim would reproduce the recording *plus whatever
it did*, which breaks `R-SIM-5`'s determinism and `R-SIM-7` outright. A schema
that does not match a port's `proto_type` means *this recording does not support
that cut*, never a coercion.
*A third axis exists and is deliberately **not** opened: the same logical port
under a different message type. `UT-C1c-6`'s hard `proto_type` mismatch is the
right answer inside our own org (`R-IFACE-1` makes `interfaces` the single
contract), and outside it that is a codec's job (`FR-SIM-50`), never the ingest
map's.*
**Verified by.** `UT-C9-1..6`, `ST-C9-1`, `ST-C9-2`. **Priority.** `P0` — the
asker's stated primary workflow (open BSD's existing recordings, resim `df`
alone) does not work without it. **Status.** frozen 2026-07-31.

### CR-SIM-3 — Vantage authors nothing; scenarios belong to the module
**Requirement.** *"vantage is not at all a tool to create scenarios, I will
still keep scenario creation concept at respective module level … it makes sense
right because scenarios creation will be job of respective module."*
(2026-07-31)
**Answered by.** Already the design — `FR-SIM-63` puts scenario *instances* with
the component that owns their expectations, and `sim_scenarios_and_expectations.md`
§0 gives the reasoning (an `expect:` block names component ports, so scenarios
in `modules/sim` would fail `GT-1`). **Recorded as its own constraint because
the documents stated the ownership and never stated the *negative*** — that the
player is a consumer of scenarios and never an editor of them. `sim_learn.md`'s
first draft of the CLI walkthrough showed `sim run scenarios/bsd_overtake.yaml`
as a bare relative path, which reads as though scenarios ship with the tool;
corrected to the real module path in the same review. Vantage **executes**
`modules/df/tests/carla_scenarios/bsd/<case>.yaml` against `df`'s own DLL; it
does not create, own, or store it.
**Verified by.** `GT-1`, `ST-E1-6`. **Priority.** `P1` — a boundary that erodes
quietly. **Status.** frozen 2026-07-31.

### CR-SIM-22 — Expectations are data, from one source
**Requirement.** A scenario's acceptance criteria must be machine-readable and
exist exactly once — not restated in a comment, a test and a report.
**Origin.** **Derived**, from defect `D11` (architecture §3): today a scenario's
intent lives in prose at the top of its file, so nothing can check it, the
timeline cannot mark it, and a report has to be written by hand. Nobody asked
for this in words; it is the constraint that makes `NR-SIM-31`'s "thoroughly
tested" mean anything for scenarios.
**Answered by.** `R-SIM-8` — the `expect:` block is the single source, and the
same block drives the timeline marker, the headless `sim check` and the report.
Every timing predicate carries an explicit `within_s` (there is no default
tolerance, because a silent default is how a timing test stops testing timing),
and an anchor derived offline records `from:` provenance, matching the
calibration discipline.
**Verified by.** `UT-C3-2` (each predicate), `UT-C3-3`, `ST-C3-1`.
**Status.** frozen.

### FR-SIM-44 — Setting a stage to `sim` must close the chain automatically
**Requirement.** On the UI where per-component measured/simulated is set,
selecting two stages as simulated must not leave an intervening stage measured —
the intervening stage should become simulated by itself.
**Origin.** 2026-07-28: *"on the ui itself where I am setting which component
should have meas and which should be sim, there itself if I set df and rsp as sim
then em shouldnt get set as meas it should automatically be sim is what I mean.
do you think its a wrong approach."*
**Answered by.** Arch §5.10 *"The severed chain"* + `R-SIM-10`. **Not a wrong
approach — it is right, with one refinement.** The mechanism stays as designed
(execution never propagates upstream; the only check is per-port resolvability),
but the *default* changes: a `measured` stage between two `simulate` stages is a
**severed chain** — the upstream stage computes into nothing, so the toggle
lies — and the GUI and loader close it by default. The override remains legal,
because holding a downstream stage on known-good input while watching an
upstream stage's divergence is a real setup; the orphaned stage is then badged
*"computed, not consumed"*. Default correct, escape hatch visible, never silent.
**Verified by.** `UT-C1c-16` (the loader detects a severed chain),
`UT-D6-4` (the GUI acts on it and offers undo), `UT-D6-5`, `UT-D6-6`.
Two levels on purpose: a correct detector behind a GUI that ignores it
is exactly the silent toggle this requirement exists to prevent.
**Status.** frozen.

### FR-SIM-45 — A developer must be able to tweak individual inputs
**Requirement.** The failure being designed against: developers could not
flexibly tweak the inputs they wanted for a run, which is what drove them to
private tooling.
**Origin.** 2026-07-28: *"the problem we faced in previous firm is developer
couldn't flexibly tweak the inputs he want to execute simulation, it could be
players over configuration or something I dont know. but i dont want this tool to
end up in this way."*
**Answered by.** `R-SIM-15` + arch §5.10 *"Per-port overrides"* — `const`,
`hold`, `offset`, `scale`, at a port or a field path, declared in the pipeline
and recorded in the run manifest. **The verb list is closed**: the reference
console's per-argument glob-and-substitute mapping rules are what an open
expression grammar becomes, and that is the over-configuration this requirement
names. If four verbs are insufficient the answer is a `stub:` stage — real
code, in a file, reviewable — not a fifth verb.
**Widened 2026-07-31 (`OD-8`, closes `OQ-10`), and the widening is not a fifth
verb.** The four verbs were **scalar-shaped**, and the requests developers
actually make are structural — *delete object 3*. So `select` and `drop` are
added over repeated fields, with a closed index grammar (`[i]`, `[*]`, and
**no predicate**); the arithmetic list stays closed at four. The line that keeps
it closed: **an override may destroy or attenuate information, never create an
entity** — `R-SIM-7` one level up, which rules out `insert`/`move`/`duplicate`
on principle rather than on taste. A fixed-slot port clears in place and never
compacts, because compaction renumbers indices and breaks track association
silently. And the audit's third example — *"make the cut-in happen half a second
earlier"* — is refused as an override and answered by editing the scenario,
which is already data.
**Verified by.** `UT-D6-1`, `UT-D6-2`, `ST-D6-2`. **Status.** frozen.

### FR-SIM-46 — One tool, not a developer tool and a project tool
**Requirement.** Whether the project-scale player and the developer-facing
DLL-resim/wiring tool are designed independently or as common tooling; and
whether a new component should first be exercised through a DLL-wrapper mapping,
then handed to a platform team for integration.
**Origin.** 2026-07-28: *"Now I dont know if the player (for now lets name its as
ltMTS) and ltMB (matchbox) should be independently designed or we can have a
common tooling for this"*; *"the core aim is to ship everything as a single
entity"*; *"tomorrow if a candidate designed new component with a dll … use ltmb
tool dll wrapper concept to map the ports easily … once its clear later he will
give requirement for sim guys to incorporate that component."*
**Answered by.** Arch §5.16 — **one engine, two faces.** The two personas are
real; two engines are not, because they would give two namespaces, two project
schemas and a developer validating something other than what the project runs,
destroying the batch face's audit value. The developer's pipeline file *is* the
input to the mass run. On onboarding: the DLL-wrapper mapping step **must not
exist for components we own** — `adasManifest` makes the port set discoverable
(`sim probe`), and hand-mapping would create a second description free to drift
from the manifest; the handoff to a platform team is itself the queue that
causes private players. `impl: "legacy:<lib>"` keeps the wrapper concept for
binaries that genuinely cannot carry a manifest.
**Verified by.** `GT-8`, `GT-9`, `UT-D6-3`, `ST-D6-1`, `ST-D7-3`.
**Priority.** `P0` — one engine, two faces — the decision every other structure rests on. **Status.** frozen.

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
**Verified by.** the codec contract itself — `UT-A4-7` proves a new codec is
~4 methods and that `Session`/viewer/expectations never learn a format exists,
which is the whole of what CarMaker needs. **The CarMaker codec is designed,
not scheduled**: no stage builds it, because no CarMaker results file exists
to test against. **Status.** frozen (design); **deferred** (build) — trigger:
the first results file landing in the repo, then one stage on the S-A4
template.

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

### FR-SIM-52 — Writers and export dumps, with port selection and timestamps
**Requirement.** Symmetrically with readers, writers that emit specific formats;
for a given format the user chooses **which ports** are frozen into the output,
with proper timestamping.
**Origin.** 2026-07-28: *"we also need output export dump concept just like
reader we also need writers that writes in specific formats, there also for
suppose if its csv (just example) you should give which ports we want to freeze
in the csv or mcap or whatever with proper timestamping."*
**Answered by.** `R-SIM-14` (extended) + recording doc §7.1–7.3. Readers and
writers are the same codec table, which makes `sim convert` a consequence rather
than a feature. **A recording and an export are separated deliberately:** a
recording round-trips and can be resimmed; an export (CSV, Parquet, mp4) is
lossy and terminal, selects ports by their manifest names (`R-SIM-4` — no third
vocabulary), flattens to one row per tick, and carries the recording's own
`log_time_ns` timebase plus optional `tick_index`/`scenario_time_s`. Origin tags
(`R-SIM-12`) and override marks (`R-SIM-15`) survive into the export header, a
missing port is an error by default, and a held multi-rate value is
distinguishable from a blank via `<port>.age_s`. A write-only codec is refused
as a resim input by **capability**, not convention.
**Verified by.** `UT-D7-1..5`, `ST-D7-1`. **Status.** frozen.

### NR-SIM-21 — Mass-scale runs must be expressible
**Requirement.** The project-scale face exists for auditing, reporting and
mass-scale simulation.
**Origin.** 2026-07-28: *"ltMTS is more at project level helping people to
simulate at big scale that will help in auditing and reporting or even at mass
scale simulation"*; *"what is lagging currently to attempt things at scale."*
**Answered by.** `sim batch` (recording doc §9) over a folder/glob/list with one
report, taking **the same pipeline file** used interactively (`R-SIM-16`), plus
`sim convert`. **This is currently the largest functional gap** — `sim resim`
runs exactly one recording and there is no way to express *"run this over 500
recordings"*. Storage and compute sizing for such a run is **not designed**
(§10, parked until `sim batch` exists to size it).
**Verified by.** `ST-D7-2`, `ST-D7-3`. **Priority.** `P0` — the project-scale
face has no other reason to exist. **Status.** **`partial`** — the verb and the
one-pipeline-file identity are designed; **throughput, storage and retention
are not** (see `NR-SIM-22`, `NR-SIM-23`). Marked `frozen` until 2026-07-28,
which was wrong: a requirement whose own text says a core part is undesigned
is not frozen, and calling it so hides the gap from exactly the person
planning around it.

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
**Verified by.** `DC-5` (every path the map claims either exists or is marked
NEW) and `GT-1`/`GT-6` (the boundary the map describes, enforced by grep).
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
**Verified by.** `DC-1` (every internal link in `modules/sim/docs` resolves —
a doc that moved and left a dangling reference has not really moved) and
`ST-E1-3`. **Status.** frozen.

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
**Verified by.** `ST-D5-1`, `ST-D5-2`, `ST-D5-3`. **Priority.** `P0` — the deliverable itself. **Status.** frozen.

### FR-SIM-64 — A component's plug-ins must be *delivered*, not merely *checked out*
**Requirement.** The player must run as a standalone entity: point it at the
right libraries in specific paths and it works — no sibling git checkout of the
component whose picture it is drawing.
**Origin.** 2026-07-31: *"eventhough ui is of bsd interest, I dont want to keep
this here modules/df/sim and move to modules/sim because this sim should always
run as a standalone entity. but how I feel that happens is by it taking right
dlls and keep it in specific paths."*
**Answered by.** `R-SIM-20` + arch §5.7a. **The proposed move is rejected and
the underlying need is accepted** — the two are separable, and this register
records both halves because the reasoning matters more than the verdict.
Authoring stays in `modules/<name>/sim/` (moving it into the framework is `D9`
inverted: `sim` would own every component's content, `GT-1` would have to be
deleted, and every picture change would become a framework release). Delivery is
what was missing: the build copies `sim/` into `<library_dir>/sim/` exactly as
`R-SIM-3a` already copies calibration into `<library_dir>/config/`, and the
player discovers plug-ins from a plug-in path. The asker's own proposed
mechanism — *"taking right dlls and keep it in specific paths"* — is precisely
this, and is adopted verbatim as the mechanism.
**Verified by.** `ST-C8-1`, `ST-C8-2`, `GT-12`. **Priority.** `P0` — `FR-SIM-70`
is not deliverable without it. **Status.** frozen 2026-07-31.

### CR-SIM-2 — A plug-in never spells a port address; it binds through the manifest
**Requirement.** Port names must be frozen in a declaration and read from it,
not typed into code at each use site.
**Origin.** 2026-07-31: *"the golden rule I feel is missing everywhere in code
of sim or as part of this whole exercise we are touch port names inside the code
rather than freezeing them in some config and reading them (atleast it looks
like that, commanality in architecture is what I really doubt by using those
names. there might be other such kind of instances as well)."*
**Answered by.** `R-SIM-21` + arch `D13`. The concern is **confirmed on the
consumer side and already solved on the producer side**, which is why it looked
ambiguous: `df_interface_c.cpp` holds one named constant per port read by both
the manifest builder and the dispatch (`UT-C1b-11/12` bind them), while
`modules/df/sim/layers/bsd.py` carries the literal `"df.bsd.outputs"` bound by
nothing — and whose `df.` segment is not even the component, but the *pipeline
stage name*. The asker's *"there might be other such kind of instances as well"*
is also correct: `S-C3`'s `expect:` blocks and `S-D3`'s workspace files are the
next two, and both are routed through the same binding path rather than growing
their own.
**Verified by.** `GT-11`, `UT-B1-14`, `UT-C1c-22`. **Priority.** `P0` — the
failure mode is a silently missing overlay, indistinguishable from a
non-firing algorithm. **Status.** frozen 2026-07-31.

### NR-SIM-11 — The per-component ABI shim is generated, not hand-written
**Requirement.** Derived from the asker's *"commanality in architecture is what
I really doubt"* (2026-07-31), applied to the C++ side.
**Answered by.** `R-SIM-22` + arch `D12`. `S-C1b` cost `df` ~400 lines of port
table, manifest builder, dispatch and dump tool — none of it wrong, all of it
per-component, and all of it a mechanical restatement of one port list in four
grammars. Eight components would be ~3,200 lines of hand-maintained near-copies,
which is `D1`'s own shape one level up. Declared once as data in
`conf/ports.yaml` (beside `conf/build.yml`, `R-VAR-3`), gated by
`ENABLED_FUNCTIONS` (`R-VAR-5`), generated at build time.
**Verified by.** `UT-C1d-1..5`, `ST-C1d-1`. **Priority.** `P1` — `df` works
today; the cost lands on component two. **Status.** frozen 2026-07-31.

### NR-SIM-12 — A change to a shared contract must be proven not to break any component's build
**Requirement.** Tests must also verify that builds are not broken, across
modules, and that each module still builds standalone.
**Origin.** 2026-07-31: *"in test cases I feel if we touch some components
source code as per the need of the requirements tests should also include from
your md point of view to also trigger builds not being broken. our concept is
standalone builds. standalone vantage. everthing standalone should be possible
one way or the other right."*
**Answered by.** `GT-4` widened from one component to a **build matrix** with a
per-module measured floor, plus `GT-10` (standalone build from a partial clone)
and `GT-12` (standalone player). This is a gap the register genuinely had:
`S-C1a`'s defect #1 was an `interfaces` change that broke `df`'s CMake generate,
and `S-C1b`'s delta #2 was a link-visibility change with cross-repo reach —
neither would have been caught by any gate as written, and both were found by a
human running a build by hand.
**Verified by.** `GT-4`, `GT-10`, `GT-12`, `ST-E3-2`. **Priority.** `P0` — the
alternative is discovering a broken component when someone else pulls.
**Status.** frozen 2026-07-31.

### FR-SIM-65 — `sil_host` runs a complete pipeline, and that is its whole job
**Requirement.** *"sil-host is meant to run complete pipeline in simulation and
thats the only job of it."* (2026-07-31)
**Answered by.** Arch §9, extended — and `OQ-11` **closed in favour of building
it** (`S-C7`). The requirement is a statement of intent that the design asserted
in one document and listed as undecided in another; two documents disagreeing
about whether a capability exists is a `GT-7` failure, and the honest options
were to build it or to stop claiming it. Building it, because the claim "one
concept, two hosts" is otherwise a slogan, and because the engine is small once
`S-C1a`/`S-C1b` hold: read the pipeline file, load N libraries by manifest, wire
by name, tick. Everything it needs already exists as protobuf and C in
`interfaces`.
**Verified by.** `ST-C7-1`, `ST-C7-2`. **Priority.** `P1` — Vantage covers the
development loop; this covers trustworthy timing and the no-Python integration.
**Status.** frozen 2026-07-31.

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

### NR-SIM-22 — A component that crashes or hangs must not take the run with it
**Requirement.** Derived, 2026-07-28, from a validation pass against the
mass-scale goal: the design classified every error the framework can *observe*
(`§5.14`) and none that it cannot. A segfault in a library loaded in-process
takes the host with it, so an unattended run of 500 recordings would die on
recording 3 and report nothing.
**Answered by.** `R-SIM-19` + arch §5.18. Isolation is a property of the **face**
— Bench in-process (a crash should be immediate, with a stack), Campaign one
subprocess per recording (isolation at run granularity, zero per-tick cost),
plus per-stage `mode: isolated` for bisecting. A **per-`exec()` timeout is
required, not optional**: a hung library is as damaging as a crashing one and
harder to diagnose, because the symptom is "still running". `fail` / `crash` /
`timeout` are three outcomes that are never merged, because they send different
people to investigate. Every crash records the five things `Open on Bench` needs
to reproduce it in-process.
**Verified by.** `UT-D7-7`, `UT-D7-8`, `ST-D7-5`, `ST-D7-6`.
**Priority.** `P0` — without it the batch face cannot run unattended, which is
the only way it is ever used. **Status.** frozen.

### NR-SIM-23 — Throughput, storage and retention must be sized before the first campaign
**Requirement.** Derived: `R-SIM-6` records **every stage's inputs and outputs**,
and `NR-SIM-21` wants 500-recording runs. Nobody has multiplied those together.
**Answered by.** **Nothing yet.** This is recorded as a requirement rather than
left as an assumption so that it is visible in planning. What must be produced
before the first real campaign: per-recording size at the current port set,
wall-clock per resim, parallelism model for `sim batch -j`, and a retention
policy (what is kept as a baseline, what is regenerable, what is deleted).
**Verified by.** `ST-D7-7` — a measured campaign over the real recording set,
with its numbers written into the implementation plan.
**Priority.** `P1` — a campaign that fills a disk mid-run fails worse than one
that was never started. **Status.** **`open` — narrowed 2026-07-31 to
retention.**

> **Narrowed, not closed, and this is a deliberate disagreement with the audit.**
> §12.4 recommends *"superseded by `NR-SIM-42`; close it rather than carrying
> two."* Two of the three parts are indeed superseded: per-recording **size** and
> the pre-run **estimate** are now `NR-SIM-42`'s declared per-port record policy,
> and **throughput** is `NR-SIM-41`'s measurement. What is not superseded is
> **retention** — what is kept as a regression baseline, what is regenerable from
> a recording plus a pipeline, and what is deleted on what schedule. That is an
> operations policy, not a volume control, and closing this row would lose it.
> `OQ-8` is narrowed to match.

### NR-SIM-24 — A resim must be pinnable to a specific component build
**Requirement.** Derived: run manifests record component build hashes
(`R-SIM-6`), so a divergence can be *detected* — but nothing lets you re-run
against the earlier build to confirm it. Detection without reproduction is half a
regression workflow.
**Answered by.** **Partially.** The recording embeds the hashes; what is missing
is a way to point a pipeline at a stored artefact for that hash. The likely shape
is a Conan package reference in `impl:` rather than a bare stem, which costs one
resolver and no new concept — but it is not designed.
**Verified by.** *(none yet — deliberately. Writing a test id here for work
that has no design would make the register look covered when it is not.)*
**Priority.** `P1`. **Status.** **`open`.**

### CR-SIM-23 — A pipeline file must carry a schema version
**Requirement.** Derived: scenarios have a v1-to-v2 upgrader; pipelines have no
version field at all. The pipeline file is **the** artefact `R-SIM-16` says must
survive everywhere — Bench to Campaign, GUI to CLI, developer to CI, and into
every recording's manifest. It is the file most certain to outlive its format and
the only one with no migration story.
**Answered by.** `version:` as a required top-level key, an upgrader on the same
shape as the scenario one, and a load error naming both versions when a file is
newer than the reader. Unversioned files are treated as `v1`.
**Verified by.** `UT-C1c-18`, `UT-C1c-19`.
**Priority.** `P0` — cheap now, and the kind of thing that is never cheap later.
**Status.** frozen.

### NR-SIM-25 — Resim must actually run somewhere automatic
**Requirement.** Derived: `R-SIM-5` says resim is *"deterministic and the only
thing that goes in CI"*, and there is no CI (`plan.md` item 20). No stage in the
implementation plan creates one, so as written the rule is unbuildable.
**Answered by.** Stage `S-C6` — the **minimum** automatic gate: `sim check` over
the scenario set on every push, nothing more. Deliberately minimal, because the
broader CI question belongs to `plan.md` item 20 and this requirement only needs
the resim half to be true.
**Verified by.** `ST-C6-1`, `ST-C6-2`.
**Priority.** `P1` — determinism nobody re-checks decays silently, which is the
one failure mode a resim tool cannot tolerate. **Status.** frozen.

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
**Verified by.** `DC-6` — checked mechanically at every docs commit rather
than remembered. **Status.** frozen.

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
| **OD-6** | The evidence chain is a **join over facts already recorded**, with one producer and two formatters (GUI + `sim explain`) | 2026-07-31 | — |
| **OD-7** | Bulk arrays are **referenced** into the recording, never inlined in a `Prim`; `SceneCache` bounds by bytes | 2026-07-31 | — |
| **OD-8** | Add `select`/`drop` over repeated fields; arithmetic stays closed at four; **an override may destroy but never create an entity** | 2026-07-31 | widens `R-SIM-15` |
| **OD-9** | Two integer-nanosecond stamps per message — reception and capture — with capture `None` when unknown | 2026-07-31 | — |
| **OD-10** | Determinism is **two gates and two measurements**, not four gates; tolerance exists only where a difference is legitimate, lives per component with a mandatory `why:`, and is printed on every passing report | 2026-07-31 | narrows `NR-SIM-40` as written |
| **OD-11** | **One config bundle per component, permanently**; the pipeline asserts project agreement and hard-fails on disagreeing ego params | 2026-07-31 | closes `OQ-1` |
| **OD-12** | `period_ns` is calibration: per **function**, integer microseconds, in the bundle, reported through the manifest; the DLL's own `updated` is authoritative | 2026-07-31 | closes `OQ-12` |
| **OD-13** | A `PortValue` retains bytes and **parses lazily**; windowing a `Session` is rejected because it would break free backwards seek | 2026-07-31 | replaces the windowed-Session plan in `OQ-6` |

`OD-6`..`OD-13` were taken on 2026-07-31 in answer to §12's audit and the open
questions it sharpened. Each is stated in full, with its rejected alternatives,
in the section named in `sim_architecture.md` §10's table.

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

### 10a. Deferred asks — raised 2026-07-31, explicitly **not** being built now

Three asks handed over with the instruction *"we will not be taking them now …
so that you can have a eye on these as well when you are trying to derive stuff
currently and leave an open ended architecture."* Recorded here in full, each
with **what the current design already provides** and **what must stay open**,
because the point of raising them early is to avoid designing them out.

#### DF-1 — Where is a function's sample time configured, SIL or sim?
**Origin.** *"Need to see where do you configure sample time of each function,
is it inside sil or is it inside sim."*
**Already answered, and worth knowing now:** `R-SIM-18` — **declared by SIL,
scheduled by sim.** The component states `period_ns` in its own manifest
(`ComponentManifest.period_ns`, field 10); the pipeline derives the base grid as
the **GCD** of the declared periods and executes each stage only on its due
ticks, holding its outputs (`updated=False`, `age_s` from integer nanoseconds)
in between. A host cannot set a component's rate, deliberately: a rate the host
could override would let the picture disagree with what the ECU runs.
**What is *not* right yet, and is the asker's own golden rule applied to their
own question:** `df` currently declares it as a C++ literal
(`constexpr uint64_t kPeriodNs = 50000000`). A cycle time is **calibration** —
it belongs in the config bundle, reachable by a sweep without a rebuild
(`NR-SIM-6`), and merely *reported* through the manifest. Tracked as `OQ-12`.
**Keep open:** per-*function* rates within one component. Today `period_ns` is
per component, which is correct while `df`'s functions all run at 20 Hz; the
manifest's `PortSpec` is the natural place for a per-function period if AEB and
BSD ever diverge, and nothing in `R-SIM-18`'s GCD scheduler assumes otherwise.

#### DF-2 — Headless Vantage, for cloud or local automation
**Origin.** *"We need to create a headless running concept for this simulation
in vantage to enable automation in cloud or local pc."*
**Already provided:** the whole of Phases A–C is headless by construction —
`GT-9` requires every capability to be reachable in ≲3 lines from a plain script
with no CLI and no window, and `sim check` (`S-C3`) and `sim batch` (`S-D7`) are
already specified as headless verbs. Qt is an **extra**, not a core dependency
(`S-A1`), so a console install pulls no GUI at all. `S-D8` additionally
specifies an offscreen render suite.
**Keep open:** nothing structural. The one thing to protect is `GT-9` itself —
the moment a capability becomes reachable only through the window, headless
automation stops being free and starts being a port.

#### DF-3 — Batch playlist with an explicit worker count
**Origin.** *"for the inside sim batch running concept with bpl (batch
playlist), we need to make this run as threadpoolexec, so in headless mode in
cmd itself we will give something like -nThread = 20 something like that so
those many threads can be deployed."*
**Already provided:** `NR-SIM-21` (mass-scale runs) and `S-D7`'s `sim batch`.
**One correction to carry forward, and the reason to record this now rather than
at `S-D7`:** the unit of concurrency must be a **process, not a thread**.
`R-SIM-19` already requires `sim batch` to run one **subprocess per recording`,
for a reason that outranks convenience — a component under test may segfault or
hang, and a crashing DLL in a worker thread takes the whole batch with it,
losing the other 19 results. Python's GIL is the second, lesser reason: the work
is a C DLL ticking plus protobuf, so threads would contend rather than scale.
**So the flag lands as `--jobs N` over a process pool** (`concurrent.futures.
ProcessPoolExecutor`), which is the same ergonomics the ask describes —
`sim batch playlist.yaml --jobs 20` — with per-run isolation, per-run timeout
(`R-SIM-19`), and `fail`/`crash`/`timeout` reported as three distinct outcomes
rather than merged. **Keep open:** the playlist file format itself is
undesigned; `R-SIM-16` constrains it to be the developer's own project file with
a scenario list wrapped around it, never a second schema.

---

## 11. Open questions

| ID | Question | Where it is discussed |
|---|---|---|
| ~~OQ-1~~ | ~~One config bundle per component, or one per pipeline?~~ — **closed 2026-07-31** (`OD-11`): **per component, permanently** — a bundle is a build output and a pipeline is a run-time composition, so a per-pipeline bundle would be either unbuilt or hand-assembled, i.e. a second place to edit a value. The multi-component risk is a *consistency* question and is answered by two load-time checks: project agreement (a warning with a declared escape) and **ego-parameter agreement (a hard error, no escape)** | contract §9.1 |
| ~~OQ-2~~ | ~~Multi-rate components~~ — **closed 2026-07-28** by `R-SIM-18` / arch §5.17: declared period, derived base grid, ideal scheduler with jitter as an injected error model | arch §5.17 |
| ~~OQ-3~~ | ~~Computed scenario anchors vs. constants with `from:` provenance~~ — **closed 2026-07-31**: neither horn was necessary. An anchor is an **existing `expect:` predicate used as a time reference**, so `at: {first: <signal>, crosses: <value>, dir: rising}` adds *no* grammar; a constant still requires `from:`. Anchors that drift are exactly the ones a predicate can find; anchors derived outside the run correctly stay constants | scenarios §9.1 |
| ~~OQ-4~~ | ~~Fault-injection vocabulary beyond today's `roll_fault`~~ — **closed 2026-07-31**: five faults — `drop` · `stale` · `delay` · `invalidate` · `corrupt` — **derived from `PortValue`'s own four metadata fields plus its payload**, so the list is closed by construction rather than by taste. Reuses the override address grammar; `delay` is expressible only because `CR-SIM-4` exists | scenarios §9.2 |
| ~~OQ-5~~ | ~~Data volume through ctypes at raw-sensor injection levels~~ — **closed 2026-07-31**: the question named the wrong boundary. `NR-SIM-41` measured the read path at 46 µs/msg ≈ **300 MB/s in C libraries**, so a bulk port is bounded by **storage and I/O, not by the language crossing**. Answered by three decisions already taken — bulk-by-reference (`NR-SIM-43`), lazy parse (`OQ-6`) and declared volume (`NR-SIM-42`). Measurement still required at the first bulk port (`GT-13`) | arch §5.10 |
| ~~OQ-6~~ | ~~Windowed `Session` for very long runs (36 000+ ticks)~~ — **closed 2026-07-31** (`OD-13`), **and the original framing was wrong**: the memory is in *parsed messages*, not in the tick count, and the resim path never parses. A `PortValue` retains bytes and parses lazily, memoised, bounded by bytes. **Windowing is rejected** because a window that has scrolled past a tick must re-execute to redraw it, which breaks `R-SIM-17`'s free backwards seek. Parked with a trigger: a recording whose *bytes* do not fit, which `NR-SIM-42` now predicts in advance | recording §10 |
| ~~OQ-7~~ | ~~Cross-machine / cross-compiler determinism~~ — **closed 2026-07-31** by `NR-SIM-40` / `R-SIM-24` / `OD-10`. It was mis-filed as a question: it is a precondition of the product's main claim. Now **axis D of a four-axis report**, and a *measurement* rather than a gate — bit-identity across machines is not required, a declared and tracked bound is, and a divergence there is a finding about the **component**, not about the framework | recording §4a |
| OQ-8 | Campaign **retention** — what is kept as a baseline, what is regenerable, what is deleted. *Narrowed 2026-07-31:* the sizing half is answered by `NR-SIM-42` (declared per-port record policy + a pre-run estimate); retention is an operations question and is not the same question, so it stays open rather than being declared closed with it | `NR-SIM-23` |
| ~~OQ-9~~ | ~~Pinning a resim to a stored component build~~ — **shape resolved 2026-07-31**, scheduling deferred at `P2`. Two halves: a `pkg:` form in `impl:` beside the file form, and — the valuable half — **`--pin-builds`, which verifies each resolved library against the `library_sha256` the recording already records** and refuses on mismatch. Adds one manifest field (`package_ref`). A locally built DLL is honestly reported as unpinnable | recording §10 |
| ~~OQ-10~~ | ~~Are four override verbs enough?~~ — **closed 2026-07-31** (`OD-8`). The gap was not a fifth *arithmetic* verb but **addressing a repeated field at all**. Adds `select`/`drop` and a closed index grammar (`[i]`, `[*]`, no predicate); arithmetic stays at four. The governing line: **an override may destroy or attenuate information, never create an entity** — which is `R-SIM-7` one level up, and rules out `insert`/`move`/`duplicate` on principle. Fixed-slot ports clear in place, never compact | arch §5.10 |
| ~~OQ-11~~ | ~~`sil_host` has no generic pipeline-file reader~~ — **closed 2026-07-31** in favour of building it (`FR-SIM-65`, stage `S-C7`). Two documents disagreed about whether the capability existed, which is a `GT-7` failure; the honest options were build it or stop claiming it | arch §9, `S-C7` |
| ~~OQ-12~~ | ~~`period_ns` is a C++ literal, and a cycle time is calibration~~ — **closed 2026-07-31** (`OD-12`): yes to the bundle, **and yes to per-function**, decided now because moving later changes the manifest schema, the scheduler's unit of dueness and every consumer's `updated`/`age_s` reasoning. Declared in **integer microseconds** (`<COMPONENT>_<FN>_PERIOD_US`) because a YAML float of seconds re-introduces the rounding drift `R-SIM-18` refuses. **No ABI parameter is added**: the component is scheduled at the GCD of its own functions' periods and decides internally what to run; the DLL's `updated` flag is authoritative over the predicted schedule, so a disagreement is a *reported finding* | contract §9.2, `DF-1` |
| ~~OQ-13~~ | ~~Concept count per contribution~~ — **diagnosed and closed 2026-07-31, without removing an API.** Counting honestly, the ten are not ten: themes are a theme-author's concept, frames default to `ego`, `derived`/`assumed_geometry` matter only when something is unusual, and the three grep gates are one sentence and do not even apply to `modules/<name>/sim/`. **The unavoidable core is four** — decorator, `ctx`, `Prim`, style token — which is exactly `FR-SIM-47`'s `L-3` limit. So the defect is in the *presentation*, not the API: `.claude/templates/sim_layer_provider.py` teaches all ten at once (and still imports a decorator that was removed). Actions: a canonical minimal layer of ≤15 lines mentioning none of the six optional concepts, and `derived`/`assumed_geometry` presented as **one** idea with two cases — *the value was reconstructed* vs *the shape was assumed* — rather than two independent flags. `GT-8` keeps measuring the consequence; the cause now has a target | `GT-8`, `FR-SIM-47` |
| OQ-15 | **Should the interactive viewer exist at all?** `render/` + `view/` + `viewer.py` are ~3,000 of 8,300 lines — **36% of the codebase spent on the least differentiated part.** Foxglove and rerun already render a scene graph, and `R-SIM-13`'s "the viewer renders a `Session`" plus `S-D1`'s `SceneUpdate` export mean adopting one is already a supported path. The differentiator is the pipeline engine and the `mode:`/`impl:` matrix, not the window. `S-B3` is built and is not the question; **`S-D5` (package the player) and `S-D8` (Vantage as a product) are not**, and they are the expensive half. Decide before `S-D5`, not during it | `NR-SIM-46`, `S-D5` |
| OQ-14 | **The design set is larger than the code it describes** (~600 KB of normative prose across ten documents vs. ~8,300 lines of Python; the implementation plan alone is 3,745 lines). Every stage re-ticks two discipline checklists and twelve global gates. That overhead has been worth it so far — `S-A3`'s and `S-C1a`'s findings were both caught *by* the discipline — but it is not obviously worth it at Phase E, and the honest failure mode is documents that silently stop being maintained rather than a decision to stop maintaining them. Re-assess at `S-E3` | plan §0 |

---

## 12. Adversarial audit — 2026-07-31

Commissioned as *"think about only failure cases … behave like an external
auditor or as a competitor to my architecture … no bias you can be brutal."*
Written against the design as it stands, from the position of someone trying to
make it fail rather than trying to ship it.

**Standing summary.** The architecture's *structure* survives the attack: the
Scene/port/pipeline separation is sound, `mode:`×`impl:` is genuinely the right
primitive, and `R-SIM-14`'s codec model is better than most commercial tools
manage. **What does not survive is the evidence base.** Nine of the register's
strongest claims — determinism, throughput, storage, responsiveness,
"state-of-the-art", scaling to perception — are asserted with **no number
attached and no test that can fail**. A requirement nobody can fail is a
requirement that will be declared satisfied. That, not any structural flaw, is
what would kill this tool.

**A note on quantity.** This audit adds nine requirements to a register that
already holds forty-plus, in a project with twenty-eight stages and one
maintainer. That is itself a risk (`OQ-14`), so §12.4 names what to **cut** to
pay for them. An audit that only adds is an audit that will be ignored.

---

### 12.1 The findings that could kill it

#### A1 — Determinism is the product's core claim and is neither measured nor bounded

`R-SIM-5` makes resim *"deterministic and the only thing that goes in CI."*
Everything downstream — regression baselines, `sim check`, campaign verdicts —
rests on it. The evidence for it is `ST-C2-2`: *"`sim resim` reproduces
byte-identical outputs across two runs."* **Two runs, same process, same
machine, same binary.** That proves the code does not read the clock. It says
nothing about the failure modes that actually occur:

- floating-point contraction (FMA on/off), x87 vs SSE, a different `libm`,
  `-ffast-math` reaching in through a dependency;
- uninitialised memory that is stable on one machine;
- iteration order over an unordered container in C++;
- a different compiler, a different optimisation level, a different machine.

`OQ-7` names cross-machine determinism as an open **question**. It is not a
question — it is the precondition for the product's main claim, and it is
currently unowned. **And there is no tolerance policy anywhere in the register:**
the plan's risk table advises deciding one "before the first run", which is
guidance in a table, not a requirement. The predictable failure is the classic
golden-suite death spiral — a baseline made on machine A fails on machine B,
someone adds a tolerance to make it green, the tolerance widens under pressure,
and the suite stops catching regressions while still reporting green.

→ **`NR-SIM-40`**.

#### A2 — Throughput is unmeasured, and "one engine, two faces" dies on it, not on design

`R-SIM-16` forbids two engines because the developer must validate the same
thing the project runs. That argument is about *semantics* and is correct. It
has no answer to *economics*.

Every tick crosses ctypes N times, and each crossing is: serialize protobuf in
Python → copy → parse in C++ → run → serialize → parse in Python. Python
protobuf without the C++ backend is roughly fifty times slower than with it, and
nothing in the design pins which backend is present. At 20 Hz over a 300-tick
scenario this is invisible. Over ten thousand recordings in a campaign it is the
whole cost.

**The competitor's move is obvious and cheap:** *"your resim is an order of
magnitude slower than the C++ host you already own, and you built the framework
around the slow one."* If that is true, campaigns migrate to `sil_host`,
Vantage keeps the developer loop, and within two quarters they diverge — which
is precisely the outcome `R-SIM-16` exists to prevent, arrived at through
performance rather than through architecture. `OQ-5` names data volume "at
raw-sensor injection levels" only; the ordinary case is unbudgeted.

→ **`NR-SIM-41`**.

#### A3 — "Record every port" is stated as a virtue with no size budget

`R-SIM-6` requires every stage's inputs *and* outputs, justified as *"a few kB
per tick of data already computed."* At today's object-level ports that
arithmetic holds — roughly 100 kB/s, 360 MB/hour, fine.

`FR-SIM-3` then requires scaling to perception. A camera stream, a radar point
cloud or an occupancy grid is three to four orders of magnitude larger, and the
existing recordings **already carry `carla/chase_camera`**. There is no per-port
record policy, no rate decimation, no lossy/lossless distinction, no retention
rule, and no way for the tool to say *"this campaign will produce 14 TB"* before
it produces it. `NR-SIM-23` asks for sizing and is marked undesigned; `OQ-8`
repeats it.

The failure is not subtle: the first perception campaign fills a disk, someone
disables recording for the big ports, and `R-SIM-6`'s "true by construction"
guarantee quietly becomes false — with no signal, because nothing checks that
what was declared was recorded.

→ **`NR-SIM-42`**.

#### A4 — Nothing lets a developer prove a picture, and disbelief is how these tools die

The most common death of a visualization tool is not a crash. It is a developer
who sees something odd, cannot confirm where it came from, stops trusting the
window, and goes back to `printf`. Every subsequent feature is then wasted.

The design has good instincts pointed at this — `R-SIM-7` (never re-derive,
mark `derived`), `R-SIM-3a` (bundle provenance), origin tags per topic,
`sim explain` for names. **What is missing is the last mile: from a thing on
screen to the bytes that produced it.** `Prim` already carries `pick_id`;
`PortValue` already carries `origin` and `age_s`; the recording already carries
topics and provenance. The chain exists in pieces and is not joined, and no
requirement asks for it to be.

This is the cheapest high-value addition available in the whole design, and it
is the one that converts a viewer into an evidence tool — which is what a
safety-relevant programme actually needs.

→ **`FR-SIM-67`**.

#### A5 — The Scene IR was sized for twenty boxes and is claimed to scale to perception

`Prim` inlines its geometry (`points_m`, and a `Heatmap`'s array). `Scene` is
serialized to protobuf per tick and memoised in `SceneCache`. That is correct
and pleasant for the current content — tens of prims per tick.

A perception layer means a 100 000-point cloud per frame. Inlined, that is
megabytes per tick, protobuf-encoded, held in an LRU keyed by
`(tick, layer_selection, theme)`. Scrubbing a 36 000-tick session then fails on
memory rather than on design (`OQ-6` anticipates the session, not the prim), and
`NR-SIM-5`'s "stays responsive" has no number to fail against.

The fix is structural and cheap **now**, expensive after `S-D4`: bulk arrays are
**referenced** into the recording, not carried in the Scene. `S-D4` is where
this lands or where it becomes permanent.

→ **`NR-SIM-43`**.

#### A6 — The recording has one clock where the vehicle has two

Confirmed in the shipped codec: `io/mcap.py` writes
`publish_time=log_time_ns` — the two timestamps are deliberately collapsed, and
the recording model (`R-SIM-14`) declares one time field.

A real sensor frame is *captured* at one instant and *received* by the consuming
ECU at another; the gap is latency, and it varies. `R-SIM-18` is right that
jitter and latency belong in injected error models rather than in the scheduler
— but **an injected latency cannot be recorded and replayed faithfully into a
one-timestamp model.** Replay the recording and the latency is gone, because
only one of the two instants survived. Every "is my algorithm sensitive to
sensor latency" question is therefore unanswerable from a recording, which is
one of the top three reasons this class of tool is bought.

mcap already carries both fields. The model discards one.

→ **`CR-SIM-4`**.

---

### 12.2 Serious, not fatal

#### A7 — The plug-in path is code execution with no version and no policy
`R-SIM-20` has the player import Python from a directory beside a DLL, and
`R-SIM-6`/`R-SIM-20` have recordings embed bundle **hashes**. Two things are
undecided and must not be decided by accident: whether a recording may carry
executable plug-ins (it must not — a recording is data, and opening a colleague's
file must never run their code), and what happens when a plug-in written against
one Scene/`LayerCtx` generation meets a player built for another. `NR-SIM-9`
versions the recording, the ABI and the Scene **for the player**, and says
nothing about the plug-in API — the one interface that is now explicitly
external. → **`NR-SIM-44`**.

#### A8 — The closed override list cannot express the most common request
`R-SIM-15`'s four verbs are scalar-shaped. The requests developers actually make
are structural: *delete object 3*, *shift that target 2 m left*, *make the cut-in
happen half a second earlier*. `OQ-10` already worries the list is too narrow;
this sharpens it — the gap is not "a fifth arithmetic verb", it is **addressing
an element of a repeated field at all**. The documented escape hatch is a
`stub:` stage, i.e. writing Python, which means the closed list did not prevent
a private fork, it merely made one heavier. Recommendation: add `select` /
`drop` over repeated fields, keep the arithmetic list closed at four, and hold
the line on expressions. → modifies `R-SIM-15`, closes `OQ-10`.

#### A9 — SIL proves the algorithm and is quietly assumed to prove the integration
Every port crosses the ABI as serialized protobuf, in both hosts. Production is
Adaptive AUTOSAR passing structs (`R-SIL-1`). So the data path exercised in SIL
is **not** the data path that ships: a field present in the struct and absent
from the proto — or defaulted differently — diverges with no symptom. Nothing in
the register states this boundary, and "we tested it in SIL" will eventually be
offered as integration evidence. → **`CR-SIM-5`**, and it is a *disclosure*
requirement, not an engineering one.

#### A10 — Twelve global gates enforced by human diligence, in a project that has already shown diligence failing
`GT-4`'s floor sat 138 tests stale for six days. Two Phase C stages were reported
green against a substitute toolchain. Both were caught by review, and the
response in each case was to write down a date. **The mechanism that failed was
manual verification, and it was replaced with more careful manual verification.**
`S-C6` adds one CI job at the end of Phase C — after every stage that has already
relied on the honour system. Recommendation: move `S-C6` to the **front** of
Phase C. It is the cheapest stage in the plan and every later stage's evidence
depends on it. → modifies plan ordering; no new requirement.

#### A11 — Nobody owns this, and the maintainer is the bus factor
`GT-8` measures how long a *user* takes to a first picture. Nothing measures how
long a **maintainer** takes to make a safe change to 8,300 lines, 24 rules,
twelve gates and 600 KB of normative prose — currently authored by one person.
This is the most probable actual ending: not a design failure, an ownership
failure. → **`NR-SIM-45`**.

---

### 12.3 Requirements this audit adds

### NR-SIM-40 — Determinism must be measured across the axes that break it, and tolerance is declared once
**Requirement.** Reproducibility is verified along four axes, each reported
separately: same process · same machine, fresh process · same machine, rebuilt
binary · different machine. A **single declared tolerance policy** (exact for
integers and enums; a named absolute/relative bound per float field family)
lives in one place, is recorded in the run manifest, and may only be widened by
an explicit, reviewed change — never by a test author fixing a red run.
**Origin.** Audit `A1`; sharpens `R-SIM-5` and closes `OQ-7`, which mis-filed a
precondition as a question.
**Answered by.** `R-SIM-24` — a `sim determinism` verb producing a report per
axis, run at `S-C6` and on every component-build change. Divergence is reported with the
first diverging tick, port and field — never as a bare pass/fail.
**Design, 2026-07-31: `sim_resim_and_recording.md` §4a (`OD-10`)**, with three
refinements to this text as written:
(a) **the axis is derived from the two runs' manifests, never declared by a
flag** — a pair differing in more than one dimension is not evidence for the
narrower axis, which kills the standard "verified cross-machine" cheat;
(b) **two gates and two measurements, not four gates** — axes A/B must be exact
and block CI, while C/D are measured and tracked, because bit-identity across a
rebuild or a machine is not always achievable and mandating it produces a red
build nobody can fix and a tolerance that then widens to hide it;
(c) **tolerance exists only on C/D** — axes A/B have no tolerance *field*, so
there is nothing to widen; the file is per component (`modules/<name>/sim/
tolerance.yaml`, `R-SIM-1`), every row needs a `why:`, and **a passing report
prints the tolerance it used**, which is the only anti-spiral mechanism that does
not rely on someone choosing to look. And: **a divergence on C/D is a finding
about the component, not about the framework.**
**Verified by.** `ST-C6-3`, `ST-C6-4`. **Priority.** `P0` — every regression
claim in the system rests on this. **Status.** frozen 2026-07-31.

### NR-SIM-41 — Per-tick cost and campaign throughput are budgeted and measured
**Requirement.** A stated per-tick wall-clock budget for a reference pipeline,
measured on a named machine and recorded with a date; and a campaign throughput
figure (recordings/hour/worker). The protobuf backend actually in use is
reported by `sim doctor`, because the pure-Python fallback is a silent
order-of-magnitude regression. If measured throughput makes the batch face
unusable at project scale, that is a **design finding about `R-SIM-16`**, to be
recorded rather than absorbed by quietly using a different tool for campaigns.
**Origin.** Audit `A2`.
**First measured data point, 2026-07-31** (partial — input path only, not a full
per-tick budget; `GT-13` still open). Machine: the development Windows host,
`modules/sim/.venv` (Python 3.12). Recording:
`modules/df/tests/carla_testruns/.../bsd_ego_lane_exit.mcap`, 11.1 MB,
826 messages, 3 topics, ~275 ticks.

| Step | Cost |
|---|---|
| mcap iterate (read every message, touch payload) | **46.4 µs/msg** |
| + `memmove` into a ctypes port buffer | **49.3 µs/msg** (the copy adds **2.9 µs**) |
| **Python input path, per tick** | **≈148 µs** |
| **Whole recording** | **0.04 s** |

Two things this establishes. **No parse happens on the input path** — the
recording holds serialized protobuf and the port buffer wants serialized
protobuf, so filling an input is a copy; the parse is inside the DLL, in C++.
And the 46 µs/msg is **not interpreter overhead**: at 13.7 kB/message average
this is ≈300 MB/s, i.e. zstd decompression and I/O in C libraries, which a C++
reader would not meaningfully beat. Extrapolated: 10 000 recordings ≈ 7 min of
input handling single-threaded, ≈20 s across 20 workers.
*Still to measure: `adasExec` cost per tick, Scene build, and the deserialize
path used by layers/expectations (which is the one that can actually be slow).*

**This requirement is a measurement, not an argument for a rewrite.** Recorded
because the audit's `A2` was read that way once. A further reason the framing
misleads: **a resim has no real-time deadline.** `dtS` is passed to `adasExec`
as a number derived from the recording's integer nanoseconds, never measured
wall-clock, and the scheduler is ideal by design (`R-SIM-18`) — so host slowness
costs **throughput and never fidelity**. There is no drift, no jitter and no
missed deadline to be caused by a slow input path. (That is categorically unlike
HIL or a live rig, which is why `R-SIM-19`'s timeout exists for a *hung* library
and why HIL is parked.) The per-tick cost is dominated
by **the component under test**, not by the host: a ctypes call is single-digit
microseconds and a protobuf parse via the C backend tens, against an `exec()`
doing real algorithm work. **If a number comes back bad, the escalation order is
fixed and a language change is not on it:**
1. **Stop deserializing what nobody reads.** A pure resim moves bytes from the
   recording into the port buffer; only a layer, an expectation or a plot needs
   a message object. This is the largest available win and costs no redesign.
2. **Report the protobuf backend** (`sim doctor`) — the pure-Python fallback is
   a silent ~50× regression and nothing currently pins which one is loaded.
3. **Process pool for the batch face** (`DF-3`, `R-SIM-19`) — already required
   for crash isolation, and it is also the throughput answer.
4. **Use the C++ host for campaigns** (`S-C7`) — the design's own answer, ~400
   lines on the generic ABI, with `ST-C7-1` proving byte-identical results so
   the two faces cannot diverge (`R-SIM-16`).
5. **Rewriting the framework in C++ — never.** It would trade the property the
   whole plan is built on (Phases A/B ship and test with **no compiler**;
   410 tests in ~40 s) for a constant factor, and it would kill `R-SIM-20`'s
   external plug-in path, since a compiled player means every new layer is a
   recompile — which is `D2` restored.
**Verified by.** `ST-D7-4`, `GT-13`. **Priority.** `P0` — `R-SIM-16`'s one-engine
claim is falsifiable only against a number. **Status.** frozen 2026-07-31.

### NR-SIM-42 — Recording volume is bounded by declared per-port policy, and estimated before it is produced
**Requirement.** Each port carries a record policy — full rate, decimated, or
excluded — declared in the pipeline beside its wiring, never a global switch. A
port that is **excluded is named in the recording's own metadata**, so
`R-SIM-6`'s "everything the SUT reads was recorded" degrades *visibly* to
"everything except these, by declaration" instead of silently becoming false.
`sim record`/`sim batch` estimate and report expected size before starting.
**Origin.** Audit `A3`; makes `NR-SIM-23` and `OQ-8` actionable rather than
undesigned.
**Answered by.** `sim_resim_and_recording.md` §3.6. Four properties keep the hole
narrow: `full` is the default and there is deliberately **no global switch**; the
policy is recorded for *every* declared port, not only the exceptions, so a
reader can answer "was this complete?" from the file alone; an excluded port
feeds **`R-SIM-23`'s feasible-cut query rather than a second mechanism**; and
declaring a stage `simulate` while excluding an input it consumes is a **load
error at record time** and merely an infeasible cut at resim time — two different
times, two correct answers.
**Verified by.** `UT-C2-12`, `ST-C2-3`. **Priority.** `P0` before the first
perception campaign; `P1` today. **Status.** frozen 2026-07-31.

### FR-SIM-67 — Every rendered value is traceable to the bytes that produced it
**Requirement.** For any selected prim, layer or plotted sample, the tool answers
in one action: which port, which topic, which tick, which origin tag
(`measured`/`truth`/`mocked`/`simulated`/`overridden`), which config bundle,
which component build — and whether the value was **published by the SUT or
reconstructed by a layer** (`R-SIM-7`'s `derived`). Headless equivalent:
`sim explain <signal> --at <tick>`.
**Origin.** Audit `A4`. Nothing in the register asked for this; the pieces
(`pick_id`, `PortValue.origin`, topic provenance, `bundle_origin`, `run_id`)
all exist and are not joined.
**Answered by.** `R-SIM-25`; design in `sim_architecture.md` §5.19 (`OD-6`) and
the panel in viz §7.2. **No new capture and no new index** — the chain is a join
over three keys that already exist (`run_id` → the manifest; `Layer.id` → the
provider's *resolved* `requires` → ports → topics → origin; `pick_id` → the
entity). Two rules carry it: **one producer, two formatters** (the GUI panel and
`sim explain` call the same `evidence()`), so identical answers are structural
rather than a discipline; and **a field it cannot fill reads `unknown`, never a
plausible default**. One field is added — `Prim.derived`, because a layer
legitimately mixes SUT-published and reconstructed geometry and a per-layer flag
makes the honest answer impossible; the two are bound so they cannot disagree.
One hole is closed with it: `@signal` must declare its inputs like
`@layer_provider` does, or computed plot samples end the chain invisibly.
**Verified by.** `UT-D3-8`, `ST-D6-3`. *Corrected 2026-07-31 — this row
originally cited `UT-D3-5`, which exists but tests a CLI-to-GUI manifest
round-trip and has nothing to do with evidence. See §12.7.*
**Priority.** `P0` — a picture a developer cannot confirm is a picture they stop
using, and every other feature is then sunk cost. **Status.** frozen 2026-07-31.

### NR-SIM-43 — The Scene carries geometry, not bulk data
**Requirement.** A `Prim` inlines small geometry only. Bulk arrays — point
clouds, images, occupancy/semantic grids — are **referenced** by topic and tick
into the recording and resolved by the renderer at draw time. A declared
per-Scene size budget is enforced in the codec; a Scene exceeding it is a
`ContractError` naming the layer, not a slow render. `SceneCache` bounds by
**bytes**, not entry count.
**Origin.** Audit `A5`. Structural and cheap before `S-D4`; permanent after.
**Answered by.** `sim_architecture.md` §5.3 (`OD-7`) — a `BulkRef` field
(topic + `log_time_ns` + optional path + count + encoding), resolved by the
renderer at draw time. It is a *coordinate into the recording*, not a second
storage mechanism, so a Scene stays serializable. **It is enforceable precisely
because `R-SIM-7` holds**: if a value is big it came from a port, and if it came
from a port it is in the recording — a layer that *computed* a 100 000-cell grid
would already be forbidden. The budget check lives in `Layer.__post_init__`,
because a `Prim` does not know its layer and the error must name one.
*Confirmed against the code:* `SceneCache` bounds by **entry count**
(`max_size=256`), not bytes, so the current ceiling is 256 × whatever a Scene
weighs.
**Verified by.** `UT-A3-12`, `UT-A3-13`, `UT-B2-15`, `UT-D4-4`. *Corrected
2026-07-31 — this row originally cited `UT-D4-3`, which exists but tests the
pixel-versus-metre naming rule (`N-4`). See §12.7.*
**Priority.** `P1` today, `P0` at `S-D4`. **Status.** frozen 2026-07-31.

### CR-SIM-4 — A message carries capture time and reception time
**Requirement.** The recording model carries **two** integer-nanosecond stamps
per message: when the data was *captured/valid* and when it was *received* by
the consumer. Codecs that support only one (or none) declare it as a capability
and degrade explicitly (`R-SIM-14`). `Tick` exposes both; `age_s` derives from
capture time.
**Origin.** Audit `A6`. `io/mcap.py` currently writes
`publish_time=log_time_ns`, collapsing them; mcap itself supports both.
**Why it is not cosmetic — restated 2026-07-31, because the original reasoning
was wrong.** The claim above (*an injected latency cannot survive a round-trip*)
does not hold for recordings this framework produces: a latency model delays
*which tick a value lands on*, and that is the one thing the current model does
record, so resim reproduces the delay exactly. The real defect is that the delay
is **invisible and unattributable** — `age_s` reads `0.0` for data that is 80 ms
old, so the stale banner lies in the situation it exists for, and a truth
comparison lands at the wrong instant and reads as perception bias. The strongest
case is one the audit did not make: **a foreign recording arrives with both
stamps and we discard one, irreversibly.**
**Answered by.** `sim_resim_and_recording.md` §3.3 (`OD-9`) — a 4-tuple
`(topic, log_time_ns, capture_time_ns, bytes)` with **`capture_time_ns: int |
None`; `None` when unknown, never defaulted to reception**, because equality
would manufacture an `age_s` of exactly `0.0` that is indistinguishable from a
true one. `Capabilities.capture_time` declares it; `PortValue.age_s` becomes
*derived* rather than stored, which removes an existing ambiguity. In mcap it is
one line — the format already carries both fields with these exact semantics.
**Verified by.** `UT-A4-13`, `UT-C2-13`. **Priority.** `P0` — every recording
written before this lands is permanently missing a field. **Status.** frozen
2026-07-31.

### NR-SIM-44 — The plug-in API is versioned, and a recording never executes code
**Requirement.** Two statements, both explicit. (1) A recording carries plug-in
bundle **hashes and identities, never executable content** — opening a
colleague's file must never run their code, and a missing plug-in degrades to
"these layers unavailable, named" (`R-SIM-6`). (2) The plug-in API carries its
own generation, independent of the Scene major and the ABI version; a plug-in
outside the player's supported range is **refused with both numbers named**, not
half-loaded.
**Origin.** Audit `A7`; extends `NR-SIM-9`, which versions everything the player
reads except the one interface `R-SIM-20` newly made external.
**Answered by.** `sim_architecture.md` §5.7a. Two details decided rather than
left implicit. **The data/code asymmetry is stated on purpose**: a recording
embeds the config *bundle's* bytes (`R-SIM-6`) and must never embed a plug-in,
because configuration is data and a plug-in is code — left unstated, someone
eventually resolves the apparent inconsistency in the wrong direction. And the
API generation lives in **`modules/<name>/sim/plugin.yaml`, a file rather than a
module attribute**, because the player must decide *before importing* and reading
a Python constant requires the import that "refused, not half-loaded" forbids.
The file also carries the bundle hash `R-SIM-20` needs, so it replaces a side-car
rather than adding one.
**Verified by.** `UT-C8-4`, `UT-D5-4`. **Priority.** `P1`. **Status.** frozen
2026-07-31.

### CR-SIM-5 — What SIL does not verify is stated, not assumed
**Requirement.** The documentation states plainly that SIL exercises the
protobuf port path, while production is Adaptive AUTOSAR passing structs
(`R-SIL-1`) — so a field present in one representation and absent or
differently-defaulted in the other diverges **with no symptom in SIL**. A
mechanical check that every port's proto and its production struct carry the
same field set is the closing action; until it exists, the limitation is
disclosed.
**Origin.** Audit `A9`. Nobody asked; the risk is that "we tested it in SIL" is
offered as integration evidence.
**Verified by.** `ST-E3-6` (the disclosure exists and is current).
**Priority.** `P1` — a disclosure requirement, cheap, and expensive to be
without at a safety review. **Status.** frozen 2026-07-31.

### NR-SIM-45 — The tool must be survivable by someone who did not build it
**Requirement.** A named owner and a named second reader. A measured
**maintainer** onboarding number, the peer of `GT-8`'s user number: time for
someone who did not write it to land a reviewed change touching a rule, a stage
and a test. Recorded with a date and a name, like `GT-8`.
**Origin.** Audit `A11`. 8,300 lines, 24 rules, twelve gates, twenty-eight
stages and ~600 KB of normative prose currently have one author.
**Verified by.** `GT-14`. **Priority.** `P0` — the most probable actual ending
is an ownership failure, not a design failure. **Status.** frozen 2026-07-31.

### NR-SIM-46 — Build-vs-adopt for the interactive viewer is decided explicitly, before it is paid for
**Requirement.** Before `S-D5`, record a decision on whether the interactive
viewer is built and shipped or whether `Scene` → an existing viewer (Foxglove,
rerun) is the primary surface, with the reasoning and the rejected alternative —
the same discipline `OD-1`..`OD-5` already follow.
**Origin.** Audit / `OQ-15`. `render/` + `view/` are ~36% of the codebase and
the least differentiated part of it; the differentiator is the pipeline engine.
`S-B3` is sunk and is not in question — `S-D5`/`S-D8` are, and they are the
expensive half.
**Verified by.** A recorded decision. **Priority.** `P1`. **Status.** open —
**this is the one requirement here deliberately left open**, because it is a
product judgement, not an engineering one.

> **Case laid out and a recommendation made, 2026-07-31 — `sim_architecture.md`
> §5.15a. The decision itself is not taken here.**
>
> **The number the question rests on was wrong, and wrong in the direction that
> made "adopt" look attractive.** Measured on the tree as it stands, `render/` +
> `view/` is **3,838 lines (46 %)**, not ~3,000 (36 %) — but only **1,832 lines
> (22 %)** are replaceable by an external viewer, and the part with a genuine
> external equivalent (a BEV canvas: `bev.py` + `clip.py`) is **415 lines, 5 %**.
> `view/` imports no GUI toolkit at all — it is headless view state, including
> `R-SIM-17`'s head/review model, which no external viewer has. `theme.py`
> survives too, because a `SceneUpdate` needs colours.
>
> **Recommendation: split along the boundary the architecture already draws
> rather than treating this as binary.** Keep the Qt shell as a *console* (the
> pipeline panel, the stage matrix, transport-against-the-head, expectations,
> the evidence panel — none of which is scene rendering, and none of which an
> external viewer can supply because it has no pipeline). **Promote `S-D1`
> (Foxglove `SceneUpdate`) from "a third renderer" to the interop surface** —
> §12.4's own *"a fork in the road, not a menu"*, taken in the promote direction.
> Scope `S-D5` to the console, trim `S-D8` accordingly, and defer `S-D2`.
>
> If the decision goes the other way, the cost is bounded and known:
> `viewer.py`, `bev.py`, `clip.py` are deleted; `view/` and `theme.py` stay;
> `S-D5`/`S-D8` collapse into a Foxglove extension; and **`FR-SIM-70` must be
> renegotiated in writing** — *"install Foxglove, add this extension"* is not the
> Windows executable that requirement asks for, and it fails `FR-SIM-47`'s `L-2`.

---

### 12.4 What to change and what to cut, to pay for the above

**Modify — requirements that cannot currently fail.** Each of these is stated in
language no test can contradict, which means it will be declared satisfied:

| Requirement | Problem | Fix |
|---|---|---|
| `FR-SIM-10` "a state-of-the-art 2D BEV" | unfalsifiable | bind to viz spec §16's feature checklist plus `MC-1`; "state of the art" is the motivation, the checklist is the requirement |
| `NR-SIM-5` "stays responsive on a long run" | no number | a frame-time budget at a stated tick count, measured — pairs with `NR-SIM-41` |
| `FR-SIM-3` "scale to perception" | no criterion | a named perception-scale recording that loads, renders and scrubs within `NR-SIM-43`'s budget |
| `NR-SIM-23` throughput/storage sizing | marked undesigned | superseded by `NR-SIM-42`; close it rather than carrying two |
| `R-SIM-15` four verbs | cannot address a repeated field | add `select`/`drop`; keep arithmetic closed at four; closes `OQ-10` |
| `R-SIM-16` "one engine, two faces" | "identical" is false where isolation differs (`R-SIM-19`: in-process vs subprocess) | state the one permitted difference explicitly, or the claim is falsifiable by inspection |

**Cut or defer — to fund the additions.** The register is not short of ambition;
it is short of evidence. Recommended:

- **`S-D2` (matplotlib renderer)** — defer until the 53-figure driver actually
  blocks. It is a *second* renderer for an audience of one document set, while
  `NR-SIM-40` (determinism) is unowned.
- **`S-D1` (Foxglove export)** — defer **or** promote to primary, but do not
  build it as a third renderer alongside a Qt viewer and matplotlib. `OQ-15`
  makes this a fork in the road, not a menu.
- **The `forced` and `print` themes** — four themes, a six-check OKLCH validator
  and a CVD simulation, for a tool with one user today. Keep `dark`/`light`;
  bring the others back when someone prints something.
- **`R-SIM-14`'s export/write-only codec distinction** — correct, and no
  requirement asks for it yet. Keep the rule, drop it from `S-D7`'s scope until
  a second format exists.

**Move — one ordering change worth more than any addition.** `S-C6` (CI) sits at
the **end** of Phase C, after every stage that relied on manual verification —
and manual verification is the mechanism that has already failed twice in this
project (`GT-4`'s stale floor; two stages reported green from a substitute
toolchain). It is the cheapest stage in the plan. **Move it to the front of
Phase C.**

---

### 12.5 What would make this outstanding

Three additions, all of which fall out of properties the design *already* has and
which no comparable tool ships. Each is cheap **because** of decisions already
taken — which is the strongest available evidence that the architecture is right
even where its evidence base is thin.

1. **`sim bisect` — find the build that broke a scenario.** Deterministic resim
   (`R-SIM-5`), `build_id` in every manifest (`S-C1a`), a recording that
   round-trips, and expectations as data (`R-SIM-8`) are together everything a
   bisect needs. Given a red scenario and a range of component builds, return
   the first bad build automatically. Nobody in this space ships this, and here
   it is roughly a hundred lines over machinery that already exists.
2. **Change-driven test selection — "which recordings exercise what I just
   touched?"** `S-C9`'s feasible-cut query plus per-topic port manifests plus
   `owner_function` in the manifest already answer *which recordings contain the
   ports a given function produces or consumes*. That turns a 10,000-recording
   campaign into the 40 runs that can possibly change — the single highest-value
   thing a resim platform can do for a developer's inner loop.
3. **Expectation coverage — which ports does any expectation actually
   constrain?** With `expect:` as data over one address space (`R-SIM-8`,
   `NR-SIM-8`), the unconstrained surface is computable: every declared port no
   scenario ever asserts on. That is a coverage metric for *behaviour* rather
   than for lines, and it is the number that tells a programme where it is
   actually untested.

**And one framing worth adopting.** The strongest claim this platform can make
is not "we visualise ADAS runs" — several tools do. It is: **"every number this
tool shows you can be traced to the bytes that produced it, and every result can
be reproduced on another machine to a declared tolerance."** `FR-SIM-67` and
`NR-SIM-40` are the two requirements that make that sentence true, and they are
the two the register did not have.

---

### 12.6 Response to the audit — where it was right, and where it was not

*Written 2026-07-31, as the resolution pass that turns §12's findings into
designs. The audit was commissioned adversarially and is not sacred; it was
checked against the code and against the register before being acted on. Four of
its claims did not survive that check unchanged, and in three cases the
correction changes what gets built.*

**Verified against the code, and confirmed:**

| Claim | Check |
|---|---|
| `A5` — `Prim` inlines bulk geometry | **confirmed.** `Prim.values` is a nested float tuple, `Prim.data` is raw image bytes, `Prim.points_m` is unbounded |
| `A5` — `SceneCache` is unbounded in bytes | **confirmed, and worse than stated.** It bounds by *entry count* (`max_size=256`), so the memory ceiling is 256 × whatever a Scene weighs |
| `A6` — the codec collapses the two clocks | **confirmed.** `io/mcap.py` writes `publish_time=log_time_ns`, and the reader yields only `log_time` |
| `A8` — the override list cannot address a repeated field | **confirmed, and cheaper to fix than assumed.** `contracts/override.py` operates on `float`; overrides are parsed and load-validated but **not yet applied to any port's bytes**, so the grammar is still free |
| `A3`, `A4`, `A7`, `A11` | confirmed as stated |

**Corrected — `A6`'s reasoning, which changes the field's semantics.** The audit
argues that *"an injected latency cannot be recorded and replayed faithfully …
replay the recording and the latency is gone."* **That is false for recordings
this framework produces.** A latency model delays *which tick a value lands on*,
and which tick a value lands on is exactly what the current model records; resim
hands the same bytes to the same tick, so the delay survives. What is actually
lost is that the delay becomes **invisible and unattributable** — `age_s` reads
`0.0` on arrival when the data is 80 ms old, and a truth comparison silently
lands at the wrong instant. The strongest argument is one the audit does not
make: a **foreign** recording (a real measurement, an MF4) arrives with both
stamps and we discard one, irreversibly. `CR-SIM-4` stands; its justification is
rewritten in recording §3.3, and the corrected reasoning is what forces
`capture_time_ns` to be `None`-when-unknown rather than defaulted to reception.

**Corrected — `OQ-15`'s headline number, in the direction that flatters "adopt".**
`render/` + `view/` is 3,838 lines (46 %), not ~3,000 (36 %); but only 1,832
(22 %) are replaceable, and only 415 (5 %) have a genuine external equivalent.
`view/` imports no GUI toolkit. See `NR-SIM-46` and arch §5.15a.

**Corrected — `A10`'s recommendation is right and its instruction is
unexecutable.** *"Move `S-C6` (CI) to the front of Phase C"* cannot be done as
written: `S-C6` runs `sim check` over the scenario set, and the scenario set does
not exist until `S-C3`. What moves to the front is its **first half** — an
automatic gate running the existing test suite, `check_invariants.py` and
`docs/py/run_all.py` on every push. That is buildable today, costs about an hour,
and closes the actual failure mode the finding names (manual verification, which
has now failed twice). The `sim check` half stays after `S-C3`. Splitting the
stage is the difference between acting on the finding and deferring it again.

**Partly overtaken — `A2` (throughput).** `NR-SIM-41` already carries a measured
first data point and a fixed escalation order, so the finding is largely
answered; `GT-13` remains open for `adasExec` cost, Scene build and the
deserialize path. Two things to add. First, **escalation step 1 —*"stop
deserializing what nobody reads"* — stops being a contingency and becomes the
design** (`OD-13`, lazy `PortValue`), so the largest available win is taken
before it is needed rather than after. Second, the audit's *"the competitor's
move"* framing assumes campaigns must run in Python; they must not. `S-C7` makes
`sil_host` read the same pipeline file, and `ST-C7-1` proves byte-identical
results. **"Your resim is slower than your own C++ host" is answered by "yes —
and you can run either, from the same pipeline file, with a test proving they
agree"**, which is a stronger position than a single-language tool can hold. The
two-host structure converts `A2` from a vulnerability into a differentiator.

**A note on quantity, which the audit itself raised.** This pass resolves
fourteen items and adds, in total: one field on `Prim`, one on `PortValue`, one
element on the message tuple, one field on `Capabilities`, two override verbs,
one `Evidence` record, one `plugin.yaml`, one per-component `tolerance.yaml`, and
two manifest fields. It **removes** three concepts — the windowed `Session`, the
eager parse, and the tolerance-in-a-risk-table — and makes one existing flag
(`Layer.derived`) honest instead of approximate. That ratio is the intended one:
`OQ-14` says the design set is already larger than the code, so a resolution that
only adds would be the wrong kind of answer.

---

### 12.7 A defect the audit pass itself introduced — two requirements cited the wrong tests

*Found 2026-07-31 while propagating the resolutions into the implementation
plan. Recorded rather than quietly fixed, because the **class** of defect
matters more than the two instances.*

`FR-SIM-67` (the evidence chain) cited `UT-D3-5`, and `NR-SIM-43` (the Scene
carries geometry, not bulk data) cited `UT-D4-3`. Both ids exist. Neither test
is about the requirement citing it:

| Requirement | Cited | What that test actually asserts |
|---|---|---|
| `FR-SIM-67` | `UT-D3-5` | a run manifest written by the CLI reopens in the GUI panel with every field intact |
| `NR-SIM-43` | `UT-D4-3` | a pixel-valued and a metre-valued field never share a bare name (`N-4`) |

**Why nothing caught it.** `check_traceability.py` verifies that a cited id
**exists**, that it is unique, and that it is filed under the stage it names. It
cannot verify that a test is *about* the requirement citing it — no mechanical
check can, short of the tests existing. So the register read as fully traced
while two of the audit's own `P0`/`P1` additions were verified by nothing.

**This is the same shape as the defect the checker's own comment describes** —
*"a misfiled test is a gate that silently covers nothing"* — one level up: a
**mis-cited** test is a requirement that silently proves nothing. It is also
`D13`'s shape a third time: a name written by hand, bound to its target by
nothing, failing silently.

**Fixed** by defining `UT-D3-8` and `UT-D4-4` under the right stages and
repointing both rows; `NR-SIM-43` additionally now cites `UT-A3-13` and
`UT-B2-15`, which are the tests that actually carry its two halves.

**The general lesson, which is the reason this section exists.** When a review
adds requirements *and* their test ids in one pass, the ids are chosen from
memory of a 4,000-line plan and are exactly the kind of thing that looks right.
The cheap discipline: **after adding a requirement, open the test it cites and
read it.** Two of eleven were wrong here — a rate high enough that "it passed
the checker" was never sufficient evidence.
