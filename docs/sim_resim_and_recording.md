# Resim & Recording — determinism, provenance, and the Session

Status: **concept, frozen for review 2026-07-27.** Part of the simulation
rework — see [sim_architecture.md](sim_architecture.md). This document owns the
run lifecycle: what a recording contains, what a run manifest guarantees, what
is and is not deterministic, and the Session that makes seeking possible.

Supersedes the forward direction of
[df_carla_mcap_replay_plan.md](../../../docs/df_carla_mcap_replay_plan.md), whose per-tick
recording design and `dt_s` reconstruction are carried forward unchanged.

---

## 1. The three modes, and what each guarantees

From `sim_architecture.md` §1, now with their guarantees:

| | **sim** | **resim** | **replay** |
|---|---|---|---|
| Stimuli from | a live world model | a recording | — |
| SUT executed | yes | yes | **no** |
| Paced by | wall clock / server | as fast as it runs | the viewer |
| Deterministic | **no** | **yes**, given the same recording + SUT + calibration | trivially |
| Repeatable output | no | bit-identical | identical |
| Needs CARLA | yes | no | no |
| Seekable | tail only | after pass 1 | fully |
| Command | `sim run <scenario>` | `sim resim <recording>` | `sim view <session\|mcap>` |

The distinction earns its keep in one sentence: **a bug found in sim is
reproduced in resim, and only resim can be put in CI.** Today's tooling already
relies on this (every verification in the existing docs that was actually
repeatable was a resim), but calls it "replay", which is why the docs keep
having to explain that you cannot seek backwards.

---

## 2. Run manifest — provenance

The single largest gap in the current recordings: **a `.mcap` in
`tests/carla_testruns/` does not record which DLL build, which calibration
project, or which scenario produced it.** `bsd_curve_r172_passby.mcap` is
mute about all three. A recording from before a calibration change is
indistinguishable from one after it, and a resim silently pairs any recording
with whatever `df_sil.dll` happens to be in `build-sil-vs2026/`.

Every run — sim or resim — is described by a manifest, written into the
recording and into every snapshot sidecar:

```yaml
manifest_version: 1
run:
  id: 20260727T213847Z-8f3c1a         # timestamp + short hash of this manifest
  kind: sim | resim
  created_utc: 2026-07-27T21:38:47Z
  host: <machine>                     # sim only; resim is machine-independent
source:
  kind: carla | mcap | carmaker | synthetic
  scenario: bsd/bsd_curve_r172_passby.yaml
  scenario_sha256: ...
  world: {map: Town04, server_version: "0.9.16"}   # sim only
  recording: bsd/bsd_curve_r172_passby.mcap        # resim only
  recording_sha256: ...
sut:
  project: base
  pipeline: df_only.yaml
  components:
    - name: df
      library_sha256: ...
      build_id: v0.4.2-17-g1b7b66c
      abi_version: 1
      manifest_sha256: ...             # the component's port manifest
      config_bundle: <library_dir>/config/     # the packed bundle (OD-4)
      config_bundle_sha256: ...        # empty ⇒ unverified provenance, said so in the HUD
      config_bundle_embedded: true     # the bundle's bytes are in this file, see §3.4
      enabled_functions: [aeb, bsd]
sensor_model: {object_range_m: 80, num_object_slots: 50}
seed: 0
```

Rules:

- **A resim records the manifest of the run it re-executed**, so the chain from
  a resim result back to the original sim run is complete.
- **A resim compares its SUT against the recording's producer manifest.** A
  differing `library_sha256` or `config_bundle_sha256` is normal (that is often
  the point — re-run yesterday's stimuli against today's build), so it is
  reported prominently, not blocked. A differing **port manifest** or **ABI
  version** is a hard error unless `--force`, because the stimuli may no longer
  mean what they meant.
- **`sha256` everywhere, `build_id` for humans.** `git describe` is convenient
  and lies after an uncommitted edit; the hash does not.

### 3.4 The config bundle travels with the recording

The recording embeds the SUT's **config bundle bytes** (`project.yaml`, the
`shared_config`'s `vehicle/ego_params.yaml`, the port manifest) on the
`/meta/config_bundle` topic — a few kB of YAML, written once at `t=0`.

Two things this buys, both of which the alternative (a hash alone) does not:

- **`sim view someone_elses.mcap` renders correctly on a machine with no
  build**, no Conan cache and no checkout. The viewer needs ego geometry,
  footprints and sensor poses to draw anything truthful, and until now its only
  source was a source-tree walk that a recipient may not have — or may have at a
  different revision.
- **The viewer provably reads the bytes the DLL read.** `ProjectModel` resolves
  embedded bundle → library `config/` → source checkout, in that order, and
  reports which one it used. Without this the two readers agree only by
  coincidence (`sim_architecture.md` §5.6).

A recording produced before stage C5 has no bundle. It loads with
`config_bundle: unknown`, the viewer falls back to the source checkout, and the
HUD says so — rather than presenting a reconstructed picture as if it were
provenanced.

---

## 3. Recording format

### 3.0 The model is abstract; mcap is one codec

**A recording is a model, not a file format.** The model is small and every
format must express it:

```
Recording
  meta:      manifest · config bundle · topic provenance      (§2, §3.4, §3.5)
  topics:    name -> {schema, provenance tag}
  messages:  (topic, log_time_ns, bytes) in log_time order
```

Everything above this line — `Session`, the pipeline, the Scene, the viewer,
expectations, diff — is written against **that model and never against a
format**. A format is a codec implementing a narrow interface:

```python
class RecordingReader(Protocol):
    def topics(self) -> Mapping[str, TopicInfo]: ...
    def read(self, topics: Iterable[str]) -> Iterator[RawMessage]: ...
    def meta(self, block: str) -> bytes | None: ...
    capabilities: Capabilities

class RecordingWriter(Protocol):
    def declare(self, topic: str, schema: Schema, provenance: Provenance) -> None: ...
    def write(self, topic: str, log_time_ns: int, payload: bytes) -> None: ...
    def put_meta(self, block: str, payload: bytes) -> None: ...
    def close(self) -> None: ...
```

Four methods each. Codecs register by file extension, so a new format is one
class plus one registration — nothing above the line changes, and no layer
provider, renderer or expectation ever learns a format exists.

**Capabilities are declared, not assumed.** Formats differ in real ways, and a
missing capability must degrade explicitly rather than silently:

| Capability | If absent |
|---|---|
| `embedded_schemas` | schemas come from the component manifests instead (§2) — which the ABI already carries, so this is survivable |
| `random_access` | pass 1 streams the whole file once into the Session; seeking still works, because seeking is a Session operation, not a file operation |
| `meta_blocks` | manifest / config bundle / provenance ride in a sidecar `<name>.meta.json`; the reader presents them identically |
| `arbitrary_topics` | a fixed-schema format maps our topics through a declared name table, supplied by the codec |

Formats worth anticipating, none of them designed here: **MDF4/MF4** (ASAM —
the likely form of a real vehicle measurement), **CarMaker results**
(§5.12's T3 converter), **rosbag2**, and whatever a future toolchain brings.
Each is a codec; none is an architecture change.

### 3.1 Container — mcap today

`.mcap` is the **default codec**, unchanged — it works, is Foxglove-native, and
both reader and writer are already in use. Protobuf message encoding, schemas
embedded as `FileDescriptorSet` (the technique `foxglove_stream.py` already uses
to build a channel schema from a `DESCRIPTOR`, generalised). It supports all
four capabilities above, which is why nothing forces the abstraction today —
and exactly why the abstraction has to be drawn now, while there is only one
codec and the boundary is free.

**Naming, so the two are not confused:** `adas_sim.io.<format>` holds format
codecs; `adas_sim.sources.<world>` holds world-model clients. An earlier draft
of the module layout listed `sources/mcap` beside `sources/carla`, which blurred
a file decoder and a simulator client into one word. They are different
abstractions with different reasons to change.

### 3.2 Topic layout

Today's topics are `df/gen_object_list`, `df/veh_dyn`, `carla/chase_camera`,
plus `df/aeb_outputs` and `df/bsd_outputs` on export.

**These names are wrong in a way that matters.** `df/gen_object_list` is named
for its *consumer*. It is produced by the bridge today and by
`perception-core` tomorrow, at which point the topic name asserts something
false. The corrected layout namespaces by **producer and port**, matching the
port names in [sim_sil_contract.md](sim_sil_contract.md):

| Topic | Content |
|---|---|
| `/source/gen_object_list` | stimulus produced by the source |
| `/source/veh_dyn` | " |
| `/source/veh_sig` | " |
| `/source/camera/<id>` | camera frames |
| `/truth/objects` | ground truth from the world model |
| `/truth/ego` | " |
| `/df/aeb.outputs` | observation, `<component>/<port>` |
| `/df/bsd.outputs` | " |
| `/df/aeb.comp_state` | " |
| `/perception-core/gen_object_list` | observation, once it exists |
| `/scene` | serialized `Scene` per tick (optional, see §6) |
| `/meta/manifest` | the run manifest, once, at `t=0` |
| `/meta/config_bundle` | the SUT's config bundle bytes, once, at `t=0` (§3.4) |
| `/meta/topic_provenance` | per-topic origin tag, once, at `t=0` (§3.5) |
| `/meta/event` | state transitions and markers |

### 3.5 Per-topic provenance — a mock is not a measurement

A manufactured recording and a real one share a *format*, not an *evidence
grade* (`sim_architecture.md` §5.11). Every topic therefore carries an origin
tag, written once at `t=0`:

| Tag | Meaning |
|---|---|
| `measured` | captured from real hardware |
| `truth` | ground truth from a world model — exact by construction |
| `mocked` | synthesised by a stand-in for a component that did not run |
| `simulated` | produced by a real component that executed in an earlier run |

Today every topic in every recording would be tagged `truth` or `mocked`:
`carla_bridge.py` derives `GenObjectList` from actor transforms and sets
`contributingSensors = 0x2` (the radar bit) on it — a reasonable stand-in, and
one nothing currently records as a stand-in. The viewer shows the tag, the run
manifest carries it, and `sim check`'s report states it, so "perception was
measured" can never quietly mean "perception was a CARLA mock". One enum per
topic; it removes a whole class of misread result.

`/source/*` and `/<component>/*` never collide even when a component produces
the same message type a source does — which is exactly the perception case, and
is what makes `truth` vs `observation` comparable in one file.

### 3.3 Timing

Carried forward unchanged from `../../../docs/df_carla_mcap_replay_plan.md` §3, because it is
correct: `log_time` is elapsed nanoseconds from run start; a tick's `dt_s` is
the gap from the previous tick's `log_time`; all messages of one tick share a
`log_time` and are grouped by it on read. This reconstructs the exact real-time
`dt_s` sequence the live bridge measured, which is what makes resim faithful
rather than idealised.

One clarification worth writing down: the live bridge paces on
`time.perf_counter()` at 20 Hz, deliberately **not** on the world server's
`elapsed_seconds` (that was measured to be unreliable when polled this fast in
async mode — up to ~13× error, ruled out as a fluke across repeated runs). So
recorded `dt_s` carries genuine wall-clock jitter. That is a feature: resim
replays the jitter the algorithm actually saw.

---

## 4. Determinism — what is guaranteed, and one real hole

**Guaranteed for resim:** same recording + same component libraries + same
configs ⇒ bit-identical observations. Nothing in the resim path reads a clock,
a random source or the filesystem beyond the recording and the configs.

**Not guaranteed for sim**, and not fixable: server tick timing, actor spawn
outcomes and wall-clock pacing all vary. This is why a sim run's value is
producing a recording, and why every repeatable claim should be made about a
resim.

### The hole: `VehSig` is not recorded

`carla_bridge.py` constructs `veh_sig_pb2.VehSig()` fresh each tick and never
records it. `df_dll_sim_mcap.py` does the same on the resim side, with a
comment explaining that this matches the live path because "no recorded
scenario engages a turn signal".

That is true today and **false the moment a turn-indicator scenario exists** —
which LCA, lane-change BSD suppression and any indicator-gated function all
need. At that point the recording will silently not contain an input the SUT
consumes, and resim will diverge from sim in a way nothing detects.

The fix is structural, not a patch: **every port the pipeline declares — every
stage's inputs *and* outputs — is recorded, always, with no per-port
exceptions.** The recorder derives its topic list from the pipeline's port
manifests rather than from a hardcoded pair of topics. Then "did we record
everything the SUT reads?" is answered by construction, and a resim can *assert*
that every declared input port is present before it starts.

**Outputs matter as much as inputs, for a reason that is not obvious.** A
recording that contains only stimuli can only ever be resimmed one way: run
everything. A recording that also contains every stage's *outputs* can be
resimmed with any stage taken from the recording instead of executed — the
per-stage measured/simulate model in `sim_architecture.md` §5.10. That is what
makes a single tool cover every level of simulation, and it is bought for a few
kB per tick of data that was computed anyway.

So there are two grades of recording, and the distinction is worth naming:

| Grade | Contains | Enables |
|---|---|---|
| **stimulus recording** | source ports + truth + camera | resim of the whole pipeline, nothing else |
| **session recording** (`--save session.mcap`) | the above **+ every stage's outputs + events + manifest + config bundle** | any cut point; simulated-vs-recorded comparison; `sim view` with no DLL present |

A session recording is this project's equivalent of a measurement in a
reference resim toolchain. **A sim run should write one by default** — it has
already computed every output, and a stimulus-only recording silently forecloses
every future cut point.

### Two smaller guarantees to state explicitly

- **Padding slots.** `build_gen_object_list()` always emits exactly
  `num_object_slots` objects, padding with all-zero `GenObject`s — a deliberate
  choice matching the reference fixed-array shape. Padding detection
  (`f_dist_x == 0 and f_dist_y == 0`) is currently reimplemented in the viewer
  as `_is_padding_slot()`. It moves into the framework once, next to the sensor
  model that creates the padding, so the two definitions cannot drift.
- **Buffer capacity.** Output buffers are sized from the port manifest
  (`sim_sil_contract.md` §4.3), not from a hand-picked `256`. A recording notes
  any port that needed a grow, because that is a manifest bug.

---

## 5. Time across components

Open question, scoped here rather than decided.

Today one component ticks at one rate and `dt_s` is passed straight through. A
real pipeline is multi-rate: perception at 30 Hz (camera-driven), functions at
20 Hz, VDY faster still.

The model this architecture assumes until evidence forces otherwise:

- the Session has **one tick grid**, defined by the source;
- each component declares a `period_s` (or `every_n_ticks`) in the pipeline
  YAML, defaulting to every tick;
- a component that does not run this tick keeps its previous outputs, and the
  consumer sees them with a **growing `ageS`** — which is exactly what
  `DfReqBuf.ageS` is for and what `AEB_MAX_AGE_OBJECTS_S` already gates on. So
  multi-rate behaviour is expressed with a mechanism that already exists and is
  already exercised;
- the viewer shows per-port age, and flags a port whose age exceeds the
  consuming function's calibrated maximum.

Not designed: sub-tick interpolation, or a component whose rate is not an
integer divisor of the grid.

---

## 6. The Session

```python
@dataclass
class Session:
    manifest: RunManifest
    ticks: list[Tick]           # index == cycle number
    events: list[Event]         # transitions, markers, expectation results
    def at(self, i: int) -> Tick: ...
    def seek_time(self, t_s: float) -> int: ...
```

Produced by pass 1 (resim or live sim), consumed by pass 2 (any renderer, the
expectation evaluator, an export). See `sim_architecture.md` §6.4 for why the
split exists; the operational consequences:

- **A Session is serializable.** `sim resim <recording> --save session.mcap`
  writes stimuli + observations + events + manifest into one file that
  `sim view` opens with no DLL present at all. That is the artefact you attach
  to a ticket, and the thing "replay" properly means.
- **Scenes are cached, not stored.** A Session stores `Tick`s; Scenes are
  rebuilt on demand from the layer providers (cheap, pure) and cached by tick
  index. Writing Scenes into the recording (`/scene`) is optional and is for
  one purpose only: letting a viewer that has none of our Python — Foxglove
  Studio, opened cold by someone else — still see the spatial picture.
- **A/B diff is two Sessions.** Same recording, two SUT builds or two projects,
  indexed by the same `i`. The diff is a first-class output: per-tick,
  per-port equality plus the first divergent tick, which is the number you
  actually want when a calibration change moves a warning by three cycles.

### Live sim and the Session

A live run appends to the Session as ticks arrive. Seeking backwards into
already-recorded ticks works; the head keeps advancing. "Live" is the tail, not
a different mode — one code path, one flag.

---

## 7. Export and sharing

| Artefact | Contains | Opened by |
|---|---|---|
| `<scenario>.mcap` (recording) | manifest, all source ports, truth, camera | `sim resim`, Foxglove |
| `session.mcap` | the above + all observations + events (+ optional `/scene`) | `sim view`, Foxglove |
| `snapshot.png` + `.json` | one frame + full provenance | any viewer / a ticket |
| `clip.mp4` | an interval at the current viewport + layers | anyone |
| `report.json` / `report.md` | expectation results across a scenario set | CI, review |

The current `--export` flag — which exists purely to hand Foxglove a file it
can scrub because the viewer cannot (D7) — is replaced by `--save session.mcap`,
whose purpose is sharing rather than working around a missing feature.

---

## 8. Migration of existing recordings

There are recordings in `tests/carla_testruns/{aeb,bsd}/` and timestamped
exports under `exports/`. They are valuable — several were the basis of
live-verified findings — and must not be invalidated.

- **Old recordings keep working.** The reader accepts the legacy topic names
  (`df/gen_object_list`, `df/veh_dyn`, `carla/chase_camera`) and maps them onto
  the new namespaced ones, with `VehSig` synthesised as it is today.
- **A recording without a manifest** is loaded with `manifest: unknown` and the
  viewer says so in the HUD, rather than pretending to provenance it does not
  have.
- **`exports/` is not migrated.** It is timestamped scratch output by design
  (`../../../docs/df_carla_scenario_layout.md` §6 keeps it flat for exactly this reason) and
  is regenerable.
- **Re-recording is not required** for the framework to land; it is required
  before a recording is used as a regression baseline, because a baseline
  without provenance is not a baseline.

---

## 9. CLI shape

The verbs name the two sides (`sim_architecture.md` §5.11) rather than bundling
them the way `carla_bridge.py --record` does today:

```
                       produces an artifact   executes a SUT
  sim record                    yes                no
  sim run                       optional           yes (live)
  sim resim                     optional           yes (from a recording)
  sim view / render             no                 no
```

```
sim record <scenario> -o out.mcap [--project P]        # PRODUCTION only — mocks
                                                       # run, nothing is executed
sim run    <scenario> [--record] [--view] [--project P] [--pipeline P]
sim resim  <recording> [--view] [--save session.mcap] [--project P]
sim view   <session|recording> [--preset NAME] [--layers ...]
sim render <session|recording> --at <t|tick> --out fig.png [--preset NAME]
sim check  <scenario-set> [--report report.md]         # headless expectations
sim diff   <sessionA> <sessionB>
sim list   scenarios | recordings | pipelines | ports <component>
```

One binary, subcommands by verb. Replaces two scripts with eleven flags between
them, and — more importantly — gives the GUI a stable thing to call: a manifest
plus a subcommand, rather than an argv line it has to assemble from checkboxes.

---

## 10. Open points

- **Recording size.** JPEG chase frames dominate. Whether to keep video in the
  same file, in a sidecar, or as a codec stream is an engineering call with a
  real disk cost; not decided.
- **Long runs.** Everything above assumes a run fits in memory (1200 ticks
  does, comfortably). A 30-minute drive at 20 Hz is 36 000 ticks and needs a
  windowed Session. Flagged, not designed — no scenario is near this.
- **Cross-machine determinism.** Bit-identical resim is claimed on one machine
  with one build. Floating-point differences across compilers/architectures are
  real and out of scope until a second target exists.
- **Recording a live sim's own timing jitter as data.** Per-tick component
  execution time is worth recording (it is free) and worth plotting on the
  timeline, but is not a determinism input. Cheap to add in C2; not specified.
