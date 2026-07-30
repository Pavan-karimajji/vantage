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
**Verified by.** `UT-C1c-10`, `UT-D3-2`. **Status.** frozen.

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
that was never started. **Status.** **`open`.**

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
| ~~OQ-2~~ | ~~Multi-rate components~~ — **closed 2026-07-28** by `R-SIM-18` / arch §5.17: declared period, derived base grid, ideal scheduler with jitter as an injected error model | arch §5.17 |
| OQ-3 | Computed scenario anchors vs. constants with `from:` provenance | scenarios §9 |
| OQ-4 | Fault-injection vocabulary beyond today's `roll_fault` | scenarios §9 |
| OQ-5 | Data volume through ctypes at raw-sensor injection levels | arch §5.10 |
| OQ-6 | Windowed `Session` for very long runs (36 000+ ticks) | recording §10 |
| OQ-7 | Cross-machine / cross-compiler determinism | recording §10 |
| OQ-8 | Campaign sizing — throughput, storage, retention (`NR-SIM-23`) | undesigned |
| OQ-9 | Pinning a resim to a stored component build (`NR-SIM-24`) | undesigned |
| OQ-10 | Are four override verbs enough? The closed list is the decision most likely to be wrong, and the escape hatch (a `stub:` stage) is heavier than the complaint that motivated `FR-SIM-45`. Watch it; do not pre-emptively widen it | `R-SIM-15` |
| OQ-11 | `sil_host` has no generic pipeline-file reader. The stated intent (contract §0, arch §9) is that one pipeline description runs unchanged under both Vantage and `sil_host`; only ABI-level compatibility (`S-C1b`, `S-E2`) is actually scheduled. Whether/when to build a real C++ engine that parses the same pipeline YAML is undecided | contract §9 |
