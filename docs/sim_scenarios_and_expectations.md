# Scenarios & Expectations — schema, sensor model, and assertions as data

Status: **concept, frozen for review 2026-07-27.** Part of the simulation
rework — see [sim_architecture.md](sim_architecture.md). This document owns the
scenario schema and the expectation layer that turns 18 hand-watched test cases
into a suite something can run.

Builds on, and does not replace, two decisions that are correct and are kept:
the engine-vs-test-data split ([df_carla_scenario_architecture.md](../../../docs/df_carla_scenario_architecture.md) §1)
and the feature-subfolder layout ([df_carla_scenario_layout.md](../../../docs/df_carla_scenario_layout.md)).

---

## 1. What is right today

Worth stating first, because the schema change below is surgical rather than a
rewrite:

- **Scenarios are data under `tests/`, not code beside the engine.** The
  reasoning — binding code and test data change for different reasons at
  different rates — is sound and is the reason 18 scenarios did not rot the
  bridge.
- **Feature subfolders** (`aeb/`, `bsd/`) using the same token as
  `src/component/<fn>/` and `ENABLED_FUNCTIONS`. One vocabulary, three places.
- **Declarative actor behaviour** — the `lateral_profile` phase list, with a
  `raised_cosine` shape whose existence is justified by physics (a constant-rate
  slide produces no yaw rate, so the FR-BSD-705 spurious-warp case would have
  silently tested nothing). This is a genuinely well-designed piece and moves
  across unchanged.
- **Signed rates in the project convention** (`+y` = left), deliberately not
  "converge/diverge with an inferred sign", because inference breaks for a
  left-side target and is undefined at `lateral_offset_m: 0`.
- **A leading comment block on every scenario**, already parsed by two tools.
- **Back-compat sugar** — `lead:` normalising to a one-element `actors:` list,
  so older files kept running. The same technique is used again in §4.

---

## 2. The problem

### 2.1 Four concerns in one document

```yaml
carla:  {host, port, map}            # ① world-model binding
ego:    {...}                        # ② scenario content
actors: [...]                        # ②
object_range_m: 100.0                # ③ sensor model
num_object_slots: 50                 # ③
end_condition: {...}                 # ④ run control
roll_fault: {...}                    # ④ (fault injection)
df:     {dll_path, config_path}      # ⑤ SUT binding
```

Five, actually. Consequences:

- **The `carla:` block makes every scenario CARLA-specific** even though nothing
  about "a target converges at 0.25 m/s with Δv = 0" is. plan.md item 4
  (CarMaker) hits this immediately.
- **`df:` names a DLL path inside a test case.** Running the same scenario
  against a different build means editing the test data, or relying on `null`
  and whatever happens to be in `build-sil-vs2026/`.
- **`object_range_m` / `num_object_slots` are a sensor model** — the only sensor
  model that exists — filed as if they were scenario content. Real FOV, range,
  latency and dropout have nowhere to go.
- **No schema, no version.** A typo in a key is silently ignored.

### 2.2 Expectations are prose

Every scenario's expected outcome is written in its comment block. From
`bsd/bsd_mergein_vlat025.yaml`, verbatim:

> *"the target's near edge first touches the zone at `dist_y = -4.80 m` […]
> leaves 1.20 m of converge before entry = 4.80 s at this `v_lat`, during which
> the warning must still be OFF. […] The acceptance criterion is S-4: alert on
> within 300 ms of ANY PART entering, i.e. within 300 ms of t = 4.80 s. Proven
> analytically before this file was ever run live."*

That is three precise, machine-checkable assertions and one analytically derived
anchor time, written in English. Nothing checks any of them. A regression is
caught by a human reading a console stream and remembering what the comment
said.

Two pieces of tooling already parse this comment (`carla_bridge.py --list`
prints its first line; `df_sim_gui.py` shows the block as a tooltip). When two
tools parse your prose, the prose wants to be data.

---

## 3. Schema v2

Five top-level sections, one per concern, plus a version.

```yaml
schema: 2
id: bsd_mergein_vlat025
doc: |
  S-G2: NHTSA §10.6.1 converge/diverge (merge-in), v_lat = 0.25 m/s.
  Δv = 0, ego at the S-1 test speed. …
  (the existing comment block, now a field — still the first thing a
   reader sees, and still what --list and the GUI tooltip show)

# ── ① scenario: world-model agnostic content ──────────────────────────
scenario:
  road:
    hint: straight_multilane          # what the scenario NEEDS
    min_straight_m: 422
    lanes_right_of_ego: 2
  ego:
    speed_mps: 20.111
    lateral_profile: null
  actors:
    - name: target
      class: CAR                      # was `classification`
      long_offset_m: -1.0
      lateral_offset_m: -6.0
      speed_mps: 20.111
      lateral_profile:
        - {name: converge, rate_mps: +0.25, duration_s: 8}
        - {name: hold,     rate_mps:  0.0,  duration_s: 2}
        - {name: diverge,  rate_mps: -0.25, duration_s: 10}
  markers:                            # analytically derived anchor times (§5.3)
    zone_entry_s:      {value: 4.80,  from: "docs/bsd/py/bsd_g2_mergein_offline.py"}
    predicted_clear_s: {value: 12.12, from: "docs/bsd/py/bsd_g2_mergein_offline.py"}

# ── ② world: how ① is realised in a specific simulator ────────────────
world:
  carla:
    map: Town04
    spawn_point_index: 54
    ego_blueprint: vehicle.tesla.model3
    actor_blueprints: {target: vehicle.tesla.model3}
  # carmaker: {...}    ← later; ① is unchanged when it appears

# ── ③ sensor model ────────────────────────────────────────────────────
sensor_model:
  preset: ground_truth_ideal
  object_range_m: 100.0
  num_object_slots: 50

# ── ④ run control ─────────────────────────────────────────────────────
run:
  end_condition: {type: time_elapsed, max_s: 21.0}
  faults: []                          # was the top-level `roll_fault:`

# ── ⑤ SUT — a reference, never a path ─────────────────────────────────
sut:
  pipeline: df_only
  project: base
  # no dll_path. The build to run is a run-time choice (CLI/GUI/CI),
  # recorded in the run manifest, not baked into test data.

# ── expectations ──────────────────────────────────────────────────────
expect: [...]                         # §5
```

**The one structural idea:** `scenario:` says *what the case is*; `world:` says
*how to stage it in a given simulator*. A CarMaker back end adds a `carmaker:`
block and changes nothing else — which is the whole reason the split is worth
doing before item 4 rather than during it.

`road.hint` deserves a note. Today's scenarios encode simulator specifics
(`spawn_point_index: 54`) with the *requirement* explained in a comment ("510 m
straight ahead / 75 m behind at <0.75°, and it is the lane with two right-hand
driving lanes"). v2 keeps the concrete index in `world:` — it is hard-won and
must not be lost — and additionally states the requirement in `scenario:`, so a
different map or simulator has something to satisfy rather than a magic number
to copy.

### 3.0a Two ways a scenario is used

A scenario is a **production-side** description — what the world does. It is
consumed twice, by the two sides of `sim_architecture.md` §5.11:

- `sim record <scenario>` — run the world model and the mocks, **write an
  mcap, execute nothing**. This is how an algo test's stimulus is manufactured.
- `sim run <scenario>` — the same production, plus a live SUT (today's
  `carla_bridge.py --record`).

The `sut:` block below therefore only applies to `sim run`. A `sim record` run
ignores it — which is the point: the artifact it produces is independent of any
SUT, and can later be resimmed against several.

### 3.1 Presets, so files stay short

`sensor_model.preset` and `sut.pipeline` name shared documents:

```
modules/df/sim/sensor_models/ground_truth_ideal.yaml
modules/df/sim/pipelines/df_only.yaml
```

A scenario overrides only what it changes. Today all 18 scenarios repeat
`object_range_m` / `num_object_slots` / `df: {null, null}` verbatim — pure
duplication that a preset removes, and that becomes actively harmful once a
sensor model has fifteen fields.

### 3.2 Back-compat

Same technique the `lead:` sugar already established. A file without `schema: 2`
is loaded through an upgrader that maps v1 onto v2 in memory:

| v1 | v2 |
|---|---|
| `carla:` | `world.carla` |
| `ego:`/`actors:`/`lead:` | `scenario.ego` / `scenario.actors` (`lead:` sugar preserved) |
| `object_range_m`, `num_object_slots` | `sensor_model.*` |
| `end_condition:`, `roll_fault:` | `run.end_condition`, `run.faults` |
| `df:` | `sut` (a non-null `dll_path` is honoured, with a deprecation warning) |
| leading `#` block | `doc` |

Every v1 file keeps running unchanged. Migration is then a mechanical,
reviewable pass (§7), not a flag day.

---

## 4. Sensor model

Today the entire sensor model is two numbers, and the object list is CARLA
ground truth with a radar bit set on it. That is honest for the current stage
and is preserved as the `ground_truth_ideal` preset.

The section exists so that the things BSD's own analysis already knows about
have somewhere to go, rather than being hardcoded in the bridge or re-derived in
the viewer:

```yaml
# modules/df/sim/sensor_models/rear_radar_4wr.yaml
id: rear_radar_4wr
object_range_m: 100.0       # what the SIM synthesises — NOT the ECU's own
num_object_slots: 50        #   BSD_SENSOR_0_RANGE_MAX_CAR_M (see below)
sensors:                    # references only. Poses/FOV/range are REAL runtime
  - id: 0                   #   calibration (BSD_SENSOR_*) that the DLL reads
  - id: 1                   #   from the config bundle — never restated here.
occlusion:  {model: body_rect}      # the ego body occludes its own corner radar
detection:  {min_rcs_m2: 10.0}
latency_s:  0.0
noise:      none
dropout:    none
```

### 4.1 The real/simulated boundary

**A sensor model file holds only what the simulator does. It never holds a
value the DLL reads.** Everything in the second column below is real runtime
calibration that already lives in `df`'s `src/project/<p>/default.yaml` and
reaches both the DLL and the viewer through the packed config bundle
(`sim_architecture.md` §5.6) — restating any of it here would create exactly the
hand-maintained duplicate that `bsdviz/sensors.py`'s `P3`/`P4`/`P5` constants
already are.

| Simulation-only → here | Real runtime → the bundle, never here |
|---|---|
| `object_range_m`, `num_object_slots` | `BSD_SENSOR_<i>_RANGE_MAX_CAR_M`, `_RANGE_MIN_M` |
| `occlusion`, `noise`, `latency_s`, `dropout`, `detection.min_rcs_m2` | `BSD_SENSOR_<i>_POSE_*`, `_FOV_AZIMUTH_DEG`, `_SIDE` |
| `world.carla:` — map, spawn index, blueprints | `BSD_CLASS_LENGTH_M_*`, `BSD_CLASS_WIDTH_M_*` |
| `run.faults` — injected corruption | `EGO_LENGTH_M`, `EGO_WHEELBASE_M` (`shared_config`) |

`object_range_m: 100.0` and `BSD_SENSOR_0_RANGE_MAX_CAR_M: 80.0` are **different
numbers for different jobs** — what the sim feeds versus what the ECU believes
it can see. A scenario that sets the first below the second is a legitimate
test, not an inconsistency to reconcile.

### 4.2 Where world-model specifics live

Nothing CARLA-shaped goes into `shared_config` or the bundle. Three homes, by
change rate:

| Scope | Home |
|---|---|
| Per scenario — map, spawn point index, blueprints | the scenario's `world.carla:` block (§3) |
| Reusable engine constants — spawn z-clearance `0.05`, `TARGET_HZ`, `LaneAdvancer.REFRESH_DISTANCE_M`, the async-mode decision | `modules/sim/src/adas_sim/sources/carla/` (Python) |
| Reusable catalogues — blueprint → `GenObject.Classification`, blueprint dimensions | `modules/sim/src/adas_sim/sources/carla/catalogue.yaml` |

The catalogue is framework, not component content: a blueprint-to-class mapping
is a fact about CARLA, contains no function name, and every component that ever
drives CARLA needs the same one (`R-SIM-1` is satisfied — no `aeb`/`bsd`/… in
it).

The `occlusion` entry is not speculative. `viz.py`'s
`_draw_bsd_unobservable()` already builds an occluder rectangle from the ego
body because "the rear-corner radar sits inboard of the body skin", and notes
that without it the coverage model "reports the whole zone visible — found by
looking at the render, not by reasoning about the code". That physical fact
currently lives in a viewer function; it belongs in the sensor model, where both
the viewer and (eventually) the stimulus generator can use it.

**Explicitly not designed here:** the actual noise/latency/dropout models. This
section defines the slot and the preset mechanism; filling it is its own piece
of work with its own validation, and inventing numbers now would be worse than
leaving `none`.

---

## 5. Expectations

### 5.1 Shape

```yaml
expect:
  - id: EXP-1
    doc: "S-4: alert on within 300 ms of any part entering the zone"
    signal: df.bsd.outputs.left.warning
    becomes: NORMAL
    within_s: 0.300
    of: marker.zone_entry_s

  - id: EXP-2
    doc: "no warning before entry"
    signal: df.bsd.outputs.left.warning
    equals: OFF
    during: [0.0, marker.zone_entry_s]

  - id: EXP-3
    doc: "the right side is never involved"
    signal: df.bsd.outputs.right.warning
    equals: OFF
    always: true

  - id: EXP-4
    doc: "the raised warning is classified as a merge-in"
    signal: df.bsd.outputs.left.scenario
    equals: MERGE_IN
    whenever: df.bsd.outputs.left.warning != OFF

  - id: EXP-5
    doc: "clears within 300 ms of the analytic clear time"
    signal: df.bsd.outputs.left.warning
    becomes: OFF
    within_s: 0.300
    of: marker.predicted_clear_s
```

Those five are a direct transcription of one existing comment block. Nothing
was invented; the prose already said all of it.

### 5.2 Vocabulary

**Signal path** — `<component>.<port>.<field path>`, using the same port names
the manifest declares ([sim_sil_contract.md](sim_sil_contract.md) §3.2). Also
addressable: `source.*` (stimulus), `truth.*` (ground truth), and
`derived.*` for viewer-computed quantities such as TTC, which no ProPort
carries.

**Predicates:**

| Predicate | Meaning |
|---|---|
| `equals: V` + `always` / `during: [a,b]` / `whenever: <expr>` | value holds over a span |
| `becomes: V` + `within_s: d` + `of: <t>` | first transition to `V` lands within ±`d` of `t` |
| `never: V` | the signal never takes this value |
| `at_least_s` / `at_most_s` | a state is held for a duration |
| `count: {value: V, times: n}` | number of transitions into `V` |
| `between: [lo, hi]` | a numeric signal stays in range |
| `monotonic: decreasing` | for closing distances, TTC |

Kept deliberately small. Anything that needs more is a Python check registered
alongside the scenario, and the fact that one was needed is a signal worth
seeing in review.

**Tolerances.** `within_s` is mandatory on every timing predicate — there is no
default. A sim run carries wall-clock jitter and a resim runs on a 20 Hz grid,
so an exact-time assertion is a false promise. `within_s: 0.300` is the
requirement's own criterion, not a fudge factor, and writing it explicitly keeps
that distinction visible.

### 5.3 Markers — anchors with provenance

```yaml
markers:
  zone_entry_s: {value: 4.80, from: "docs/bsd/py/bsd_g2_mergein_offline.py"}
```

Anchor times are usually *derived*, not measured — the merge-in entry time is
computed from geometry and lateral rate in an offline script before the scenario
was ever run live. The `from:` field records that derivation, so a reviewer can
ask "where does 4.80 come from" and get an answer. This matches the repo's
existing provenance discipline for calibration values (`AUTHORITATIVE` /
`DERIVED` / `ASSUMED` / `UNVERIFIED` tags in `default.yaml`).

Markers also render on the timeline (`sim_visualization_spec.md` §7.3), so the
predicted entry time is a visible line you can see the warning land against.

### 5.4 Where results go

One evaluator, three consumers:

1. **The timeline** — each expectation draws its window as a translucent span
   with a pass/fail state. You see *why* it failed, not just that it did.
2. **`sim check`** — headless, exit code, no rendering. The CI form.
3. **The report** — `report.md` / `report.json`, one row per expectation, with
   the actual value and the actual time next to the expected ones.

```
bsd/bsd_mergein_vlat025                                       4/5 PASS
  ✓ EXP-1  left.warning → NORMAL   @ 4.95 s   (target 4.80 ±0.30)
  ✓ EXP-2  left.warning == OFF     over [0.00, 4.80]
  ✓ EXP-3  right.warning == OFF    always
  ✓ EXP-4  left.scenario == MERGE_IN whenever warning ≠ OFF
  ✗ EXP-5  left.warning → OFF      @ 12.55 s  (target 12.12 ±0.30)  ← +0.13 s late
```

The failure line names the tick, so `sim view <session> --at 12.55` opens
exactly there.

### 5.5 What this is not

Not a replacement for `df_tests` (gtest). Unit tests own algorithm-level
correctness with hand-built inputs; expectations own **scenario-level behaviour
of the composed SUT against realistic stimuli**. Different level, different
failure modes, both needed. The suite here is also not a KPI framework — it is
pass/fail per scenario. Aggregate statistics wait until there are enough
scenarios for an average to mean anything.

---

## 6. CI

```
sim check tests/sim_scenarios/bsd  --report report.md
sim check tests/sim_scenarios      --report report.md   # everything
```

Requires only: the recordings, the built component DLLs, and Python. No CARLA,
no display. That is the property that makes it CI-able and is a direct
consequence of the sim/resim split.

Ordering: run it after `df_tests`, before publishing. A scenario whose
recording is missing is **skipped with a warning, not failed** — recordings need
a live world server to produce and will not always be present in a partial
clone (`../../../docs/partial_clone_workflow.md`).

There is no CI in the repo yet (noted against plan.md item 20). This section
defines what CI would run when it exists; nothing here is blocked on it, since
`sim check` is equally useful from a terminal.

---

## 7. Migrating the 18 scenarios

Order matters — this is where expectations get written for the first time, and
they should be transcribed from what the comments already say rather than
invented.

1. **Upgrader first** (§3.2), verified by loading all 18 v1 files and asserting
   the resulting run behaves identically to today.
2. **`aeb/` first, three files.** Their expectations are simple and their
   analytic anchors are stated plainly (`fires at 2.0 s`). Proves the vocabulary.
3. **`bsd/` next, fifteen files.** Richer: two sides, a scenario enum, entry
   and clear times, several with analytically derived anchors already in the
   comment and a script named as the source.
4. **Any comment whose claim cannot be expressed** is left as prose and
   **listed** in the migration record. The list is the honest output: it says
   exactly what the predicate vocabulary is missing, which is better than
   quietly widening a tolerance until everything passes.
5. **Baseline once, then freeze.** First run records actual values; each is
   reviewed against the comment's claim before being accepted. An expectation
   that merely records what the code did today is worthless — worse than none,
   because it looks like a check.

Step 5 is the one that decides whether this is a test suite or a rubber stamp.

---

## 8. Folder layout

Unchanged for now:

```
modules/df/tests/carla_scenarios/<feature>/*.yaml
modules/df/tests/carla_testruns/<feature>/*.mcap
modules/df/tests/carla_testruns/exports/
```

The `carla_` prefix becomes inaccurate once `world:` supports a second
simulator. Renaming to `sim_scenarios` / `sim_recordings` is **OD-3** in
`sim_architecture.md` §10, deliberately deferred: the feature-subfolder layout
landed on 2026-07-27 and churning it immediately costs more than it returns.
Trigger: CarMaker actually landing, done as one `git mv` in one commit.

New, alongside the component's other sim content:

```
modules/df/sim/sensor_models/*.yaml
modules/df/sim/pipelines/*.yaml
modules/df/sim/viewpoints.yaml
modules/df/sim/layers/*.py
```

---

## 9. Open points

- **Computed anchors.** `markers:` are constants with a stated derivation. Some
  anchors would be better computed from the scenario itself (entry time =
  f(offset, rate, footprint)) so they cannot drift when the scenario changes.
  That means running the derivation at load time — a real feature with a real
  cost. Deferred; the `from:` provenance field is the interim mitigation.
- **Expectations over ground truth.** `truth.*` is addressable in a signal path,
  so "perception must detect this object within 200 ms of it entering the FOV"
  is expressible. Untested until perception exists (Phase D4).
- **Cross-scenario invariants.** "No scenario ever raises a right-side warning
  for a left-side target" is a property of the set, not of one file. Worth
  having, no mechanism proposed.
- **Fault injection vocabulary.** `run.faults` currently generalises the single
  existing `roll_fault:` (corrupt-after / invalid-after on the roll signal).
  Which faults are worth injecting generally — port drop, stale age, corrupted
  payload, out-of-range value — is a real design question, not answered here.
