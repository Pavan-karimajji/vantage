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

> **The claim above is no longer an argument — a second codec exists**
> *(reconciled 2026-08-06, audit run 3, `AR-49`)*. `S-C9`'s `ST-C9-3` landed
> `io/jsonl.py`, and the interesting part is what it cost and what it did
> **not** touch: the shared reader/writer machinery moved to `io/base.py`
> first, `io/mcap.py` shrank by ~110 lines, and `jsonl` registered by
> extension. Nothing above the line changed — no `Session`, pipeline, Scene,
> viewer or expectation learned that a second format exists. **That is
> `NR-SIM-20`'s evidence, and it is stronger than `UT-A4-7`'s** (which proves
> the protocol is four methods on a fixture, not that a real second format
> fits it).
>
> Three codecs now ship, and they are deliberately not peers: **`mcap`**
> round-trips and is the recording format; **`jsonl`** round-trips and exists
> to prove the model is not mcap-shaped (and to be readable in a text editor
> when a codec is suspected); **`csv`** is `write_only=True`,
> `round_trips=False` — an *export*, refused as a resim input by capability
> rather than by convention (§7.2, `UT-D7-5`).
>
> The reader that turns a **foreign** vocabulary into ports is not a codec at
> all — it is `R-SIM-23`'s ingest map (`io/ingest.py`, `S-C9`), declared data
> under `modules/<name>/sim/ingest/`. Keeping the two apart is the same
> distinction §3.0 draws between `io/` and `sources/`: a codec knows a
> *format*, an ingest map knows a *vocabulary*, and merging them would put an
> unversioned preprocessing step between a recording and the SUT.

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
port names in [sim_sil_contract.md](sim_sil_contract.md). A port's dot becomes
a topic slash — `aeb.compState` → `/df/aeb/compState` — which is `N-1`'s own
table (`recording topic: /<component>/<token>/<port>`). *An earlier draft of
this table wrote `/df/aeb.outputs`, keeping the dot and contradicting `N-1` in
the one place a topic name is actually enumerated; corrected 2026-07-30
(`GT-7`).*

| Topic | Content |
|---|---|
| `/source/gen_object_list` | stimulus produced by the source |
| `/source/veh_dyn` | " |
| `/source/veh_sig` | " |
| `/source/camera/<id>` | camera frames |
| `/truth/objects` | ground truth from the world model |
| `/truth/ego` | " |
| `/df/aeb/outputs` | observation, `/<component>/<token>/<port>` |
| `/df/bsd/outputs` | " |
| `/df/aeb/compState` | " |
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
`carla_bridge.py` derives `DfObjList` from actor transforms and sets
`contributing_sensors = 0x2` (the radar bit) on it — a reasonable stand-in, and
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

#### Two clocks, not one — resolving `CR-SIM-4` / `A6`

*Added 2026-07-31. `OD-9`.*

**First, the audit's justification needs correcting, because the corrected
version is what fixes the field's semantics.** `A6` argues that *"an injected
latency cannot be recorded and replayed faithfully into a one-timestamp model —
replay the recording and the latency is gone."* That is **not true** for
recordings this framework produces. A latency error model delays *which tick a
value lands on*, and which tick a value lands on is precisely the one thing the
current model does record. Resim hands the same bytes to the same tick, so the
delay survives intact.

What is actually lost is narrower, and worse for being invisible:

1. **The delay cannot be seen.** The recording says *"objects arrived at tick
   N"*. It does not say *"these objects describe the world at tick N−1.6"*. So
   `age_s` — which `PortValue` carries and the HUD displays — reads `0.0` at the
   moment of arrival, which is **false**: the data is 80 ms old. The stale-data
   banner lies in exactly the situation it exists for.
2. **Truth is compared at the wrong instant.** A perception-vs-truth diff at tick
   N compares detections describing t = N−1.6 against ground truth at t = N. That
   is a systematic offset that reads as perception bias — a confidently wrong
   number, from a comparison the design advertises as free (§5.10).
3. **A foreign recording arrives with both stamps and we discard one.** This is
   the strongest case and the audit does not make it: a real measurement, an MF4,
   a supplier's file all carry capture and reception natively. Collapsing them at
   ingest is lossy and irreversible, and no later stage can recover it.

So `CR-SIM-4` stands, restated: the defect is not that latency is *lost*, it is
that latency is **invisible and unattributable**.

**The model.** Two integer-nanosecond stamps per message:

| Field | Means | Role |
|---|---|---|
| `log_time_ns` | **reception** — when the consumer saw it | unchanged. The *scheduling* clock: groups messages into ticks, drives resim, orders the file |
| `capture_time_ns` | **validity** — the instant the data describes | new, optional |

The message triple becomes a **4-tuple**, `(topic, log_time_ns,
capture_time_ns, bytes)`, with `capture_time_ns: int | None`.

**`None`, never "equal to reception".** This is the one detail worth being
stubborn about. `None` means *unknown*; equality means *simultaneous*. Defaulting
an unknown capture time to the reception time would produce an `age_s` of exactly
`0.0` — a plausible-looking answer that is indistinguishable from a true one,
which is the substitution `NR-SIM-4` forbids and the failure this field exists to
close. Every existing recording is `None` by construction: a file whose
`manifest_version` predates this change has capture unknown regardless of what
its bytes contain, because this writer set `publish_time = log_time_ns`
unconditionally and the equality carries no information.

**The ripple, honestly scoped.** Five touch points, all small, all cheap now and
permanent if deferred:

- **`io/base.py`** — the tuple gains an element; `group_by_log_time` still groups
  on `log_time_ns`, because grouping is a *scheduling* question.
- **`Capabilities`** — one field, `capture_time: bool`. A codec that has no
  second stamp declares it and degrades explicitly, which is `R-SIM-14`'s
  existing mechanism, so this costs no new concept.
- **`io/mcap.py`** — **one line.** mcap already carries both, with exactly these
  semantics: `publish_time` is when the producer published, `log_time` is when it
  was logged. The writer currently sets `publish_time=log_time_ns`; it will set
  capture. The reader yields both.
- **`PortValue`** — gains `capture_ns: int | None`, and **`age_s` stops being a
  stored field and becomes derived**: `(t_ns − capture_ns)/1e9` when capture is
  known, else the schedule-derived hold age (`R-SIM-18`). That *removes* an
  ambiguity rather than adding one — today `age_s` silently means two different
  things depending on why the value is old.
- **Error models** — a latency injection now writes both numbers, and both are
  true. `sim explain` can then say *"this value is 80 ms old, delayed by
  `rear_radar_4wr.yaml`"*, which is `§5.19`'s evidence chain reaching a fact that
  is currently unrepresentable.

**Alternatives rejected.** *A `Stamp` value type instead of a 4-tuple* — cleaner
in the abstract, but it renames the model's headline shape in three documents and
adds a type `sim_learn.md` would have to teach, for no behaviour. *Carry capture
only in a meta side-band* — puts a per-message fact in a per-run block and cannot
express a per-message delay. *Derive capture from the sensor model at read time*
— a reconstruction, i.e. `R-SIM-7`'s forbidden estimate, and it would silently
disagree with a real measurement's own stamp.

**What it does not solve.** Two stamps give delay and age. They do **not** model
transport: queuing, reordering, partial loss and bus arbitration are not
expressible as two numbers, and are not attempted. Nor does this make latency
*testable* on its own — that needs the sensor error models, which stay parked
with their trigger unchanged (`§10`).

### 3.6 Per-port record policy — bounding volume without breaking `R-SIM-6`

*Added 2026-07-31, answering audit finding `A3` / `NR-SIM-42`.*

`R-SIM-6` records every declared port and calls it *"a few kB per tick of data
already computed"*. At today's object-level ports that arithmetic is right —
about 100 kB/s, 360 MB/hour. `FR-SIM-3` then requires scaling to perception,
where a camera stream, a radar point cloud or an occupancy grid is three to four
orders of magnitude larger, and the existing recordings **already carry
`carla/chase_camera`**.

The audit's predicted failure is the one to design against, and it is not
subtle: the first perception campaign fills a disk, someone disables recording
for the big ports, and `R-SIM-6`'s *"true by construction"* guarantee quietly
becomes false **with no signal**, because nothing checks that what was declared
was recorded.

So the hole must exist — and it must be **narrow, declared, and loud**.

**Declared per port, in the pipeline, beside the wiring:**

```yaml
components:
  - name: perception-core
    mode: simulate
    record:
      "*":                full          # the default, stated
      camera_front:       {decimate: 10}   # every 10th tick
      radar_cube:         excluded
```

Four properties, each closing a way the hole could widen:

- **`full` is the default and exclusion is an explicit act**, per port. There is
  deliberately no global `--no-record` switch: a global switch is how everything
  ends up excluded by one person in a hurry.
- **The policy is recorded for *every* declared port, not only the exceptions.**
  A reader can then answer *"was this complete?"* from the file alone, without
  knowing what pipeline produced it. `R-SIM-6` degrades from *everything* to
  *everything except these, by declaration* — visibly, in the artifact.
- **Exclusion feeds the feasible-cut query, not a second mechanism.** An excluded
  port is, to a later run, indistinguishable from a port the recording never had
  — which is exactly the case `R-SIM-23` already computes and `sim probe` already
  reports. So the honest consequence (*"this file cannot resim perception,
  because its inputs were excluded"*) arrives through the machinery that exists.
- **Decimating a consumed input is caught at both ends, at the right time.** At
  *record* time, declaring a stage `simulate` while excluding or decimating an
  input it consumes is a **load error** — you are recording a run whose own
  inputs you are not keeping, which can never be resimmed. At *resim* time it is
  not an error at all, merely a cut that `sim probe` reports as infeasible.
  Two different times, two different answers, both correct; conflating them
  would either forbid a legitimate output-only recording or permit a silently
  unresimmable one.

**Estimated before it is produced, with both numbers labelled.** `sim record` and
`sim batch` print an upper bound from the manifest's `max_bytes` per port × tick
count × recordings *before starting*, then revise it from the measured rate after
the first hundred ticks. An upper bound labelled as an upper bound is useful; a
single confident figure that turns out to be either would not be.

**Cost.** One pipeline key, one meta block, one estimator. **What it replaces:**
the unexamined assumption that everything is always recorded at full rate.
**What it does not solve:** *retention* — what is kept as a baseline, what is
regenerable, what is deleted. That is an operations question, it is not the same
question as volume control, and it stays with `NR-SIM-23`.

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
  `num_object_slots` objects, padding with all-zero `DfObj`s — a deliberate
  choice matching the reference fixed-array shape. Padding detection
  (`dist_x == 0 and dist_y == 0`) is currently reimplemented in the viewer
  as `_is_padding_slot()`. It moves into the framework once, next to the sensor
  model that creates the padding, so the two definitions cannot drift.
- **Buffer capacity.** Output buffers are sized from the port manifest
  (`sim_sil_contract.md` §4.3), not from a hand-picked `256`. A recording notes
  any port that needed a grow, because that is a manifest bug.

### 4a. The determinism report — measuring the claim everything rests on

*Added 2026-07-31, answering audit finding `A1` / `NR-SIM-40` / `R-SIM-24`.
Closes `OQ-7`. `OD-10`.*

`R-SIM-5` makes resim *"deterministic and the only thing that goes in CI"*, and
every regression baseline, `sim check` verdict and campaign result rests on it.
The evidence for it is `ST-C2-2` — two runs, **same process, same machine, same
binary**. That proves the code does not read a clock. It says nothing about the
failures that actually occur, and the audit is right that this is the gap most
likely to end the tool's credibility.

#### First, one thing the claim never meant

**Determinism is a property of port values, never of file bytes.** A recording
contains a `run_id`, a creation timestamp and a host name, so two recordings of
one perfectly deterministic run are *never* byte-identical files. `ST-C2-2`'s
phrase *"byte-identical outputs"* is correct if "outputs" means port payloads and
meaningless if it means files — and that ambiguity is exactly how a test gets
quietly weakened later. Stated here so it cannot be: **the comparison is over
`(topic, log_time_ns, bytes)` for declared ports; `meta` is excluded by
construction.**

#### The axis is derived from the artifacts, never declared by a flag

Four axes, each a comparison of two runs that differ **only** in the named
dimension:

| Axis | Catches what the previous cannot | Whose defect is it? |
|---|---|---|
| **A — same process** | reading a clock or a random source; iteration over an unordered container; state carried between `exec()` calls that should not be | ours or the component's |
| **B — fresh process** | hash seed, ASLR, static-init order, a cached file, uninitialised memory the OS happens to zero | ours or the component's |
| **C — rebuilt binary** | a non-reproducible build (embedded paths/timestamps), changed inlining, FP contraction from a changed flag | **the component's** |
| **D — different machine** | a different `libm`, x87 vs SSE, FMA availability, a different OS | **the component's** |

The temptation is `sim determinism --axis fresh-process`. **Refused: a flag can
lie.** Instead, `sim determinism <run-a> <run-b>` takes two session recordings
and **derives** the axis by comparing their manifests — `host`, `process_nonce`,
`components[].library_sha256`, `components[].build_id`, `config_bundle_sha256`.
A pair that differs in *more* than one dimension is not evidence for the narrower
axis, and the report says so rather than attributing the divergence. That kills
the standard cheat where *"cross-machine determinism verified"* is claimed from a
pair that also rebuilt the binary.

This needs **one** new manifest field: `process_nonce`, random per process, so
two runs in one process share it. It lives in `meta`, which the comparison
already excludes, so it cannot perturb the thing it measures.

#### Two gates and two measurements — not four gates

This is the substantive correction to `NR-SIM-40` as written, which reads as
though all four axes must pass.

- **Axes A and B are gates.** They must be **exact**, always, for everything.
  A float that differs between two runs of the same binary on the same machine is
  a bug, not a tolerance case. These block CI (`S-C6`).
- **Axes C and D are measurements.** Bit-identity across a rebuild or across
  machines is genuinely hard for floating point and many safety programmes accept
  a bounded difference. Requiring it as a gate would produce a red build that
  nobody can fix and a tolerance that then widens to hide it — the death spiral,
  arrived at by mandate. So C and D are **measured, declared and tracked**: a
  regression is *the observed delta growing*, not *a delta existing*.

The second half of that split matters as much as the first: **when axis C or D
diverges, the finding belongs to the component, not to the framework.** The
report attributes it — component, port, field, first tick — so the conversation
is *"`df`'s binary is not portable-deterministic"* rather than *"the sim tool is
flaky"*. In a safety programme that is a genuinely valuable finding, and the tool
must not be the thing that gets blamed for surfacing it.

#### Tolerance: where it lives, and why it cannot widen quietly

**Tolerance and determinism are different questions, and merging them is what
creates the spiral.** Determinism = *same inputs, same code ⇒ same outputs*; its
correct tolerance is **exact**. Equivalence = *a legitimately changed thing
produces an acceptably similar result*; that is where a bound belongs.

Therefore: **axes A and B have no tolerance field at all.** Not "a tolerance set
to zero" — no field. You cannot widen what does not exist, and a red A/B run has
exactly one remedy: fix the code. That is a structural defence rather than a
procedural one, and it is the main reason to separate the axes.

For axes C and D, one file per component, beside the ingest map and for the same
reason (`R-SIM-1`: a float field family is `adas.common.VehDyn.vx`, which is the
component's fact, not the framework's):

```yaml
# modules/<name>/sim/tolerance.yaml -- the schema core.tolerance.load_tolerance
# actually reads (corrected 2026-08-06, sim build queue row 2; modules/df/sim/
# tolerance.yaml is the first real one). `default: exact` and "integers/enums
# never widen" are structural properties of `fields:`, not settable keys --
# there is deliberately nowhere to write `default: loose`.
fields:
  "aebOutputs.ttc_s":
    abs_tol: 1.0e-6
    why: "divides by a differenced velocity; last-bit sensitive under FMA"
```

Four mechanisms keep it honest, and the fourth is the one that actually works:

1. **`default: exact`.** Widening is an *addition*, visible in a review diff, not
   an edit to a number nobody re-reads.
2. **`why:` is mandatory** — a row without one is an `AuthoringError`. Same
   discipline as `absent:` in an ingest map (`R-SIM-23`) and `from:` on a
   scenario anchor (`R-SIM-8`): the person widening it writes a sentence they
   will be asked about.
3. **Integers and enums are exact and not overridable.** A discrete value that
   differs is a logic difference, never a rounding one.
4. **A passing report prints the tolerance it used, per field family, next to the
   pass.** So a run made green by a widened bound *announces the widening every
   time it passes*. A tolerance that has to introduce itself in every report is a
   tolerance that gets argued about — which is the only mechanism that has ever
   worked against the golden-suite spiral, because the others all rely on someone
   choosing to look.

And one leading indicator: the report states **headroom** — max observed |Δ| as a
fraction of the allowed bound, per family. Above 50 % is a warning **on a pass**,
because that is the run before the one that goes red and gets "fixed" by widening.

The tolerance file's hash joins `config_bundle_sha256` in the run manifest, so a
result always states the yardstick it was measured against.

#### Divergence is reported, never scored

A determinism result is never a bare pass/fail. It names **the first diverging
tick, the port, the field, both values, and the tolerance in force** — the same
five things `§5.10`'s A/B divergence already reports, because **it is the same
comparison**. That is what this design costs: no new comparison engine, only an
axis label derived from two manifests and a tolerance file to read. `sim
determinism` is the A/B diff of two Sessions with its axis attributed.

**Alternatives rejected.** *One global tolerance file in `modules/sim`* — names
component message types in the framework (`R-SIM-1`), and one file that every
component may widen is a commons. *Tolerance in the pipeline file* — the pipeline
is edited per run by the person whose run is red, which is the failure mode
itself. *Tolerance per scenario* — eighteen places to widen and no way to see the
set. *A `--tolerance` CLI flag* — invisible in the artifact, therefore
un-auditable.

**What it does not solve.** It cannot *prove* determinism — only fail to disprove
it over the recordings actually run; expectation-coverage (§12.5) is the
complementary question. It localises a non-deterministic component but does not
repair one. And axis D needs two machines, so it is honestly a nightly or
on-demand measurement, never a per-push gate.

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

**Evidence from the reference stack, recorded rather than acted on.** Its
components are not driven by a passed `dt` at all: a component subscribes to a
**cycle-end event from a named data source** (`UdexClientPort::CycleEndEvent`,
with a cycle id declared identically for the live device and the recorded one),
and its execution is wired through explicit **control ports** — a `Doit` server
port to run it and a `Done` client port to signal completion — separate from its
data ports. That is the industrial answer to multi-rate and event-driven
components, and it is more machinery than a single `adasExec(dt)` needs today.

Two things worth taking from it now, at zero cost: the cycle id being *the same*
for the live and the recorded source is precisely our
executed-and-injected-are-indistinguishable invariant (`R-SIM-10`), expressed at
the trigger level rather than the data level — which is a useful confirmation
that the invariant is the right one. And if `OQ-2` ever forces a change, the
shape to reach for is **a data-driven trigger plus explicit control ports**, not
a cleverer `dt`.

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

### 7.1 Writers are symmetric with readers

`R-SIM-14` makes a format a codec of ~4 methods. That symmetry is the whole
feature: **a format registered to be read is registered to be written** wherever
its declared capabilities allow, so `sim convert` falls out of the codec table
rather than being built. The reference toolchain's separate exporter components
(one per destination format) are a consequence of not having this symmetry.

```
sim convert  run.mcap  run.mf4               # recording → recording, lossless
sim export   run.mcap  ports.csv  --ports …  # recording → export, lossy
```

### 7.2 A recording and an export are different artifacts

They are produced by the same machinery and must never be confused:

| | **Recording** | **Export** |
|---|---|---|
| Round-trips | yes | no |
| Accepted by `sim resim` | yes | **never** |
| Content | every declared port (`R-SIM-6`) | an explicitly selected subset |
| Schema | embedded / referenced | flattened, declared at export time |
| Examples | mcap, MDF4, rosbag | CSV, Parquet, mp4, plot data |

A codec that cannot round-trip registers **write-only**, so the loader refuses
it by capability rather than by a naming convention someone will eventually
work around.

### 7.3 Selecting ports, and timestamping them

An export names the ports it wants, by their manifest names (`R-SIM-4`) — the
same tokens the pipeline and the layer panel use, so there is no third
vocabulary to learn:

```yaml
export:
  format: csv
  ports:
    - df.aeb.outputs                  # a whole port, flattened
    - df.aeb.outputs.brake_request    # one field
    - vdy.veh_dyn.vx
    - perception-core.gen_object_list[0..9].pos_x   # explicit slot range
  time:
    column: log_time_ns               # the recording's timebase, R-SIM-14
    also: [tick_index, scenario_time_s]
  on_missing: error                   # error | blank | omit-column
```

Four properties this must hold to:

- **One row per tick, one column per leaf field.** Multi-rate ports repeat their
  last value and a `<port>.age_s` column states how stale it is — a blank cell
  and a held value must be distinguishable (`OQ-2`).
- **`log_time_ns` is the timebase**, identical to the recording's, so an export
  and its source align tick-for-tick without a correlation step.
- **Origin tags survive.** A `mocked` or `overridden` port (`R-SIM-12`,
  `R-SIM-15`) is marked in the export's header block. An export is frequently
  the thing that reaches a report, and evidence grade must travel with it.
- **A missing port is an error by default**, naming the port and the recording.
  Silently emitting a blank column is how a report ends up claiming a signal was
  zero when it was absent.

Exports carry the run manifest's hashes in a header block (CSV: `#`-prefixed
preamble; columnar formats: file metadata), for the same reason recordings do —
an artifact without provenance is not evidence.

---

## 8. Migration of existing recordings

There are recordings in `tests/carla_testruns/{aeb,bsd}/` and timestamped
exports under `exports/`. They are valuable — several were the basis of
live-verified findings — and must not be invalidated.

- **Old recordings keep working.** The reader accepts the legacy topic names
  (`df/gen_object_list`, `df/veh_dyn`, `carla/chase_camera`) and maps them onto
  the new namespaced ones, with `VehSig` synthesised as it is today.
  **Insufficient as written — corrected 2026-07-31 (`D14`, `R-SIM-23`).** That
  mapping goes *topic → topic* and stops one step short of a **port**:
  `df/gen_object_list` becomes `source.gen_object_list`, while the port a
  pipeline actually wires is `objects`. The two never meet, and the only working
  bridge today is hardcoded inside `ST-C1c-1`. Migration is therefore not a
  rename — it is a **declaration of what a recording family provides**, which is
  the same problem another team's recordings and a foreign simulator's output
  pose, so it gets one mechanism rather than three. See `S-C9`.
- **The mapping is not the framework's to hold.** `LEGACY_TOPIC_MAP` currently
  lives in `io/legacy.py` under a named `GT-1` exemption. A topic called
  `df/gen_object_list` is a fact about **`df`'s** recordings; the declaration
  moves to `modules/df/sim/ingest/` and the exemption is deleted (`R-SIM-1`).
- **A recording states which cuts it supports, before it is run.** `CR-SIM-21`
  said this and nothing implemented it: a BSD recording carries objects and
  outputs and no perception layer, so it supports exactly one cut; a perception
  team's recording will carry detections and no objects and support a different
  one. Both are legitimate. `Session.provides()` / `feasible_cuts()` answer it
  from the topic index plus the manifests present, and `sim probe` prints it —
  rather than the user starting a run and reading `UT-C1c-10`'s error.
- **Two dimensions, deliberately kept separate.** *Format* (mcap, MF4,
  CarMaker) is a **codec** (§3.0, `R-SIM-14`); *depth* (which stage's ports are
  in the file) is an **ingest map plus `mode:`** (`R-SIM-10`, `R-SIM-23`).
  Keeping them apart is what makes "a new format" and "a new cut point" two
  small independent changes instead of one combinatorial one.
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
  sim batch                     optional           yes (N recordings)
  sim view / render             no                 no
  sim convert / export          yes                no
  sim probe                     no                 no
```

```
sim record <scenario> -o out.mcap [--project P]        # PRODUCTION only — mocks
                                                       # run, nothing is executed
sim run    <scenario> [--record] [--view] [--project P] [--pipeline P]
sim resim  <recording> [--view] [--save session.mcap] [--project P]
sim view   <session|recording> [--preset NAME] [--layers ...]
sim render <session|recording> --at <t|tick> --out fig.png [--preset NAME]
sim check  <scenario-set> [--report report.md]         # headless expectations
sim determinism <run-a> <run-b>                        # §4a — the AXIS is derived from
                                                       # the two manifests, never a flag
sim list   scenarios | recordings | pipelines | ports <component>

sim probe   <lib>                                      # port set from adasManifest —
                                                       # a new component's day one (arch §5.16.1)
sim batch   <recordings…|glob|list.txt> --pipeline P [--report report.md] [-j N]
sim convert <in> <out>                                 # recording → recording
sim export  <in> <out.csv> --ports … [--time …]        # recording → export (§7.2)
```

One binary, subcommands by verb. Replaces two scripts with eleven flags between
them, and — more importantly — gives the GUI a stable thing to call: a manifest
plus a subcommand, rather than an argv line it has to assemble from checkboxes.

`sim batch` is what makes the project-scale face possible (arch §5.16.2/§5.16.3)
and is the largest single gap today: `sim resim` runs one recording, and there
is currently no way to express *"run this over 500 recordings"*. It takes the
same pipeline file a developer was using interactively — that identity is the
point (`R-SIM-16`), not a convenience.

---

## 10. Open points

- ~~**Recording size.**~~ **Answered 2026-07-31** by §3.6 (per-port record
  policy, `NR-SIM-42`) for *what is written*, and by the Scene's bulk-by-
  reference rule (`sim_architecture.md` §5.3, `NR-SIM-43`) for *what is held*.
  The narrower sub-question — video in the same file, in a sidecar, or as a
  codec stream — is now a codec capability question (`R-SIM-14`) rather than a
  recording-model one, and is deferred to the first campaign that measures it.
- ~~**Long runs.**~~ **Answered 2026-07-31 — and the original answer was wrong.**
  See "Long runs are a parsing problem, not a windowing problem" below (`OQ-6`,
  `OD-13`).
- ~~**Cross-machine determinism.**~~ **Closed 2026-07-31** by §4a (`NR-SIM-40`,
  `R-SIM-24`, `OD-10`): it is not an open question but a precondition of the
  product's main claim, and it is now a **measurement** on axis D rather than a
  gate — bit-identity across machines is not required, a declared and tracked
  bound is. `OQ-7` closes with it.
- **Recording a live sim's own timing jitter as data.** Per-tick component
  execution time is worth recording (it is free) and worth plotting on the
  timeline, but is not a determinism input. Cheap to add in C2; not specified.
- **Pinning a resim to a stored component build (`OQ-9` / `NR-SIM-24`).** Shape
  decided below; scheduling deferred — see "Pinning a resim to the build that
  produced it".

### Long runs are a parsing problem, not a windowing problem — `OQ-6`

*Resolved 2026-07-31. `OD-13`.*

The original flag said a 36 000-tick run *"needs a windowed Session"*. Working
the problem changes the answer, because the memory is not in the tick count.

A `Session` holds `Tick`s, and a `Tick` holds `PortValue`s whose `message` is a
**parsed** protobuf. That is what is large: 36 000 ticks × ~5 ports × a parsed
50-slot `DfObjList` is expensive in a way that 36 000 small structs is not.
And `NR-SIM-41`'s measurement supplies the decisive fact: **the resim path never
parses at all.** The recording holds serialized protobuf, the port buffer wants
serialized protobuf, so filling an input is a `memmove`; the parse happens inside
the DLL, in C++. Only a *layer*, an *expectation* or a *plot* needs a message
object, and those touch a small fraction of ports.

**So: a `PortValue` retains its bytes and parses lazily, memoised, with the
parsed-message cache bounded by bytes** — the same bound `NR-SIM-43` puts on
`SceneCache`. A `Session` is then bounded by the recording's own size, which
`NR-SIM-42` now estimates before the run.

**Why windowing is rejected as the primary answer.** A window that has scrolled
past a tick must re-read and re-execute to show it again. That directly
contradicts `R-SIM-17`: *behind the head, a run is immutable data — seek, scrub
and step back are free and never re-execute the SUT*. Windowing would make
backwards scrubbing across a boundary silently non-free, which is the one
property the two-pass Session exists to provide. Lazy parsing costs nothing there,
because the bytes behind the head never change.

**Two things this buys beyond the memory.** It *is* `NR-SIM-41`'s escalation
step 1 — *"stop deserializing what nobody reads"*, the largest available
throughput win — promoted from a contingency to the design. And it is the same
mechanism `OQ-5` needs for bulk ports (hand the bytes to the DLL by pointer,
never materialise them in Python).

**Cost, and it is the most invasive item in this pass:** `PortValue.message`
becomes a lazily-computed property over retained bytes plus a schema handle, and
`PortValue` is a frozen core type that the built Phase A/B code and its tests
already use. The change is mechanical but it is not free, and it is the one
proposal here that touches shipped code rather than only documents.

**What stays parked:** true windowing, with a named trigger — a recording whose
*bytes* do not fit in memory, which `NR-SIM-42`'s estimate now predicts before
the run rather than discovering at tick 30 000.

### Pinning a resim to the build that produced it — `OQ-9` / `NR-SIM-24`

*Shape resolved 2026-07-31; deliberately low priority.*

A run manifest records `components[].library_sha256` and `build_id`, so a
divergence can be **detected**. Nothing lets you re-run against the earlier
build to confirm it, and detection without reproduction is half a regression
workflow.

Two halves, and only one of them is new:

- **Addressing.** `impl:` gains a package form beside the file form —
  `impl: "pkg:adas-df/1.4.2@#<revision>"` alongside `impl: "dll:df_sil.dll"`.
  One resolver, no new concept, and it is what `NR-SIM-24` already guessed.
- **Verification, which is the valuable half.** A package reference alone does
  not prove you got the same bytes; a version can be rebuilt and re-uploaded.
  **`sim resim <recording> --pin-builds`** reads each component's recorded
  `library_sha256`, resolves it (explicit `impl:` → a local artifact store keyed
  by hash → the Conan cache or remote by package reference), and **refuses to
  start if any hash does not match**, naming both. That converts *"I reproduced
  the old result"* from a hope into a statement.

One manifest field is added: `ComponentBuildInfo.package_ref`, empty when the
library was built locally.

**The honest limit, and it is a feature.** A locally built DLL that was never
packaged is unreproducible, and the report says so — *"this run used a local
build (sha …) with no package reference; it cannot be pinned"*. That is both the
truth and a nudge toward packaging the builds that produce baselines.

**Priority: `P2`.** It matters the first time a baseline from three months ago is
disputed, and not before. Recorded now so the two manifest fields it needs are
present from the start rather than retrofitted into recordings that no longer
exist.
