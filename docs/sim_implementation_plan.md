# Simulation Platform — Implementation Plan

Status: **frozen for implementation 2026-07-28.** This is the **normative,
checkbox-tracked** execution of [sim_architecture.md](sim_architecture.md) §8.
The architecture documents say *what and why*; this one says *in what order,
built how, and proven by which test*.

Design set (read before starting a stage): [sim_architecture.md](sim_architecture.md)
(master) · [sim_sil_contract.md](sim_sil_contract.md) ·
[sim_visualization_spec.md](sim_visualization_spec.md) ·
[sim_resim_and_recording.md](sim_resim_and_recording.md) ·
[sim_scenarios_and_expectations.md](sim_scenarios_and_expectations.md) ·
[sim_player.md](sim_player.md) (the application) ·
**[sim_api_reference.md](sim_api_reference.md) — the exact symbols to type;
a signature there is a contract** ·
[sim_naming_and_diagnostics.md](sim_naming_and_diagnostics.md) (`N-1..N-13`,
`DG-1..DG-5`; its §3 checklist is ticked per stage) ·
**[sim_portability.md](sim_portability.md) — read before writing any code;
its `P-1`..`P-10` apply to every stage, and its §3 checklist is ticked per
stage.**
Normative rules: superproject `.claude/rules/sim.md` (`R-SIM-1..17`).
Backlog entry: superproject `plan.md` item 25.

---

## 0. How to use this document

- **Every `- [ ]` is a unit of work or a test.** Tick it when it is done *and
  its test passes*. Never tick a scope box whose tests are still open.
- **Labels are stable.** `S-A1`…`S-E3` are stages; `UT-A1-1` a unit test;
  `ST-A1-1` a system test; `GT-1` a global gate. Cite them in commits
  (`feat(sim): S-A2 EgoModel + UT-A2-1..7`).
- **A stage is done when its gate passes**, not when its code is written. The
  gate is the last box in each stage.
- **Order is not a suggestion.** Each stage assumes the previous ones. Where a
  stage may be reordered, it says so.
- **Nothing is deleted before its replacement is proven.** All removal is
  Phase E, and Phase E is gated on Phases A–D.
- **One branch per stage**, off `feat/sim-platform` in the affected repo(s).
  Superproject pointer bumps follow `R-GIT-1` (submodule commits first).

### Effort shape

24 stages (Phase C's first is split into three sub-stages). A and B touch **no C++ and no DLL at all** — the entire viewer is
built and tested against recorded files. C is the only phase that changes
production C++. E only deletes.

---

## 1. Prerequisites

- [ ] **Python 3.12** — the interpreter every existing tool already targets
      (`py -3.12`, `tools/carla/requirements.txt`). Do not silently move to a
      newer one; `.pyc` files for 3.14 exist in the tree from an accidental run.
- [ ] **Dependencies**, declared in `modules/sim/pyproject.toml`:
      - core: `pyyaml>=6`, `protobuf>=4.25`, `mcap>=1.0`,
        `mcap-protobuf-support>=0.5`, `numpy>=1.26`
      - viewer: `PySide6>=6.6` (OD-1)
      - print renderer: `matplotlib>=3.8` (extra `[figures]`)
      - interop: `foxglove-sdk>=0.25` (extra `[foxglove]`)
      - dev: `pytest>=8`, `pytest-cov`
      Every non-core dependency is an **extra**, so a console resim installs
      nothing it does not use — the deferred-import discipline today's tooling
      already follows, moved into packaging.
- [ ] **`opencv-python` is not a dependency of the new framework.** It exists
      today only because `viz.py` needed a window. Qt replaces it. If a numeric
      image operation is needed later, add it deliberately.
- [ ] **Test command**: `python -m pytest modules/sim/tests -q` from the
      superproject root. No CI exists (`plan.md` item 20); this command *is* the
      gate, run by hand and cited in the commit.
- [ ] Conan remote reachable — `conan remote login adas-local demo -p demo`
      before any build stage, or builds stall ~10 min then fail with
      `EOF when reading a line`.

---

## 2. Global gates — re-checked at the end of every stage

These are the invariants that make the architecture true rather than aspirational.
A stage that breaks one is not done.

- [ ] **GT-1 — no function names in the framework.**
      `grep -rniE '\b(aeb|bsd|lca|acc|ldw|lka)\b' modules/sim/src` returns
      nothing (`R-SIM-1`).
- [ ] **GT-2 — no renderer in a layer provider.** No
      `cv2`/`matplotlib`/`PySide6`/`foxglove` import under any
      `modules/*/sim/layers/` (`R-SIM-2`).
- [ ] **GT-3 — no physical constant in a layer provider or renderer.** No
      literal vehicle/sensor dimension outside `model/` (`R-SIM-3`).
- [ ] **GT-4 — `df_tests` stays green.** `ctest` on
      `modules/df/build-gtest-vs2026` at its current count (90/90 as of
      2026-07-24) or higher. Never lower.
- [ ] **GT-5 — build machinery untouched.** `diff -q` of `conanfile.py`,
      `scripts/build.py`, `build.bat`/`.sh`, `scripts/build_gui.py`,
      `.clang-format` against another component is silent (`R-BUILD-1..6`).
- [ ] **GT-6 — the framework imports no component.** `modules/sim` never
      imports from `modules/df` or `interfaces`' generated bindings
      (`R-SIM-11`).
- [ ] **GT-7 — docs match code.** Any behaviour that contradicts a design doc
      is either a code bug or a doc bug; fix one, in the same commit.
- [ ] **GT-8 — time to first picture, measured.** A developer with **only their
      own component checked out** gets a rendered run from a recording in
      **under 10 minutes**, editing nothing in `modules/sim`. Timed on a real
      newcomer, recorded with the date and the person's role — not asserted
      (`R-SIM-16`, `FR-SIM-46`). This is the gate that decides whether anyone
      writes a private player; no feature substitutes for it.
- [ ] **GT-9 — no logic in the app layer.** `modules/sim/src/adas_sim/cli/` and
      `…/app/` contain argument parsing, layout and dispatch only. Every
      capability is reachable in ≲3 lines from a plain script
      (`Session.open`, `SilComponent`, a provider, a codec) — checked by a test
      that imports each without touching the CLI (`R-SIM-16`).

---

## 3. Test strategy

### 3.1 The two kinds

| | **Unit (UT)** | **System (ST)** |
|---|---|---|
| Scope | one entity, in isolation | a whole path, end to end |
| Inputs | constructed in the test | a real recording / a real build |
| Runs in | `modules/sim/tests/unit/` | `modules/sim/tests/system/` |
| Needs | nothing but the package | fixtures; some need `modules/df` built |
| Speed | milliseconds | seconds |

`modules/sim/tests/integration/` holds the tests that need **another module**
present (a built `df_sil.dll`, `modules/df`'s recordings). They **skip with a
named reason** when it is absent, so a partial clone still runs the suite
(`docs/partial_clone_workflow.md`).

### 3.2 The framework's tests need no C++ — by design

`SilComponent` is a **Protocol**, with two implementations:

- `CtypesSilComponent` — loads a real DLL over the generic ABI;
- `InProcessSilComponent` — a Python callable plus a manifest.

The second is the *same mechanism* `impl: stub:` uses (`R-SIM-10`), so it costs
nothing extra and lets every `Pipeline`, `Runner`, `Session` and wiring-
validation test run with **zero build dependency**. The ctypes path is exercised
in `tests/integration/`, skipped when `df_sil.dll` is not built.

*(Recorded in [sim_sil_contract.md](sim_sil_contract.md) §4.1.)*

### 3.3 Fixtures

- [ ] `tests/fixtures/tiny.mcap` — a synthetic 20-tick recording committed in
      `modules/sim`, so the framework's own suite is self-contained. Generated
      by a checked-in script, not hand-crafted, so it can be regenerated.
- [ ] `tests/fixtures/golden/` — golden `Scene`s (serialized) and golden
      manifests. Regenerated by `pytest --update-goldens`, **never** edited by
      hand; a golden change must appear in the diff and be justified in review.
- [ ] Real recordings under `modules/df/tests/carla_testruns/` are used by
      integration tests only, read-only, never modified.

### 3.4 What cannot be automated, and is therefore a named manual check

Stated honestly rather than pretended away — the same caveat the existing viz
work carries ("needs a human watching the window"):

| ID | Check | When |
|---|---|---|
| MC-1 | The BEV *looks* right — labels legible, no collisions, colours readable | S-B1, S-B3 |
| MC-2 | Live CARLA bridge still records correctly against a real server | S-C2 |
| MC-3 | Foxglove Studio renders the exported scene | S-D1 |
| MC-4 | The Qt shell feels responsive while scrubbing a long session | S-B3 |
| MC-5 | **The onboarding check** (`FR-SIM-47`) — a developer who has never seen the tool reaches a moving picture in **under two minutes**, unaided, and then explains `measured` vs `simulate` on the pipeline dock **unprompted**. If they cannot, the dock is wrong, not the developer | S-D8 |

Each is a checkbox with a date and the name of whoever looked.

`MC-5` additionally records the **number** (time to moving picture, and whether
the explanation was correct), because it feeds `GT-8` and a remembered
impression is not a measurement.

---

## 4. Phase A — Foundations

**No C++, no DLL, no behaviour change to anything that exists.**

### S-A1 — `modules/sim` package skeleton

**Purpose.** The tree, the packaging, the error taxonomy, the run id and the
log line — everything every later stage imports. Nothing here has behaviour
worth demonstrating; it exists so that nothing later has to invent a name.

**Must not.** Import Qt, matplotlib, mcap or protobuf at package import time
(`UT-A1-2`). The console resim path must install none of them.

- [ ] `pyproject.toml` — package `adas-sim`, `requires-python = ">=3.12"`, core
      deps + extras (§1). Entry point `sim = adas_sim.cli:main` — the launcher
      is generated per platform rather than written by us (`P-6`)
- [ ] `src/adas_sim/` with exactly these subpackages, matching
      [sim_api_reference.md](sim_api_reference.md) §1 **byte for byte**:
      `core/ model/ scene/ contracts/ io/ sources/ view/ render/ check/ cli/
      app/`, each with `__init__.py`; root `__init__.py` carries `__version__`
      - **`sinks/` is deliberately absent.** An earlier draft had it for
        recording writers; `R-SIM-14` made readers and writers one symmetric
        codec table, so writers live in `io/`. Two homes for one concept is
        how `sim convert` would have become a feature instead of a consequence
      - **`view/` holds transport and viewport state** — pure state, no
        pixels. `render/` turns that state into output. Keeping them apart is
        what lets `UT-B2-3` assert that a layer toggle re-renders without
        re-executing
- [ ] `conanfile.py` — `package_type = "unknown"`, no `settings`, data-only
      recipe following `shared_config`'s shape exactly
      (`docs/shared_config_plan.md` §3.2/§3.3)
- [ ] `tests/{unit,system,integration,fixtures}/` + `conftest.py`
- [ ] `scripts/check_invariants.py` — implements GT-1, GT-2, GT-3, GT-6, and
      **is itself tested** by `UT-A1-3`
- [ ] `core/errors.py` — the **closed** taxonomy of `DG-5` / api reference §9:
      `AuthoringError` (exit 2) · `EnvironmentError_` (3) · `ContractError` (4)
      · `InternalError` (70), all deriving `SimError`, whose constructor takes
      **keyword-only `expected` / `found` / `where` / `hint`**. A message that
      is only an identifier is therefore a `TypeError` at author time, not a
      disappointment at run time (`N-8`)
      - plus `ProvenanceWarning(Warning)` — **a warning, never an error**: a
        project mismatch degrades and is shown, it does not stop a run
        (`R-SIM-3a`)
- [ ] `core/ids.py` — `new_run_id()` per `N-9`; the hashed inputs are listed in
      api reference §2.1 and are **sorted before hashing** (`P-8`)
- [ ] `core/logging.py` — the `Event` StrEnum (closed) and `log()` emitting one
      fixed-order line (`N-10`)
- [ ] Console UTF-8 reconfiguration at every entry point (`P-4`) — three lines,
      and the bug it prevents was already hit once in `docs/py/_common.py`
- [ ] file headers on every `.py` per `R-STYLE-1`, `COMPONENT: SIM` (`R-NAME-6`)

**Tests**
- [ ] `UT-A1-1` `import adas_sim` succeeds; `__version__` is a non-empty string
- [ ] `UT-A1-2` every subpackage imports without side effects (no disk, no
      network, no window at import time) **and without importing Qt,
      matplotlib, mcap or protobuf** — asserted on `sys.modules`
- [ ] `UT-A1-3` `check_invariants.py` passes on the empty tree, and **fails** on
      a deliberately planted function identifier (the check is tested, not
      trusted)
- [ ] `UT-A1-4` each error class carries `expected`/`found`/`where`, exposes its
      `exit_code`, and is distinguishable by type; constructing one without the
      keyword arguments raises `TypeError`; `ProvenanceWarning` is a `Warning`
      and is not raisable as a `SimError`
- [ ] `UT-A1-5` **every public class reprs its own name** and no `repr` contains
      `0x` (`N-7`) — the cheapest debugging feature in the system and the
      easiest to skip
- [ ] `UT-A1-6` **import direction**: `core`/`model`/`scene`/`contracts`/`io`/
      `check` never import `render`, `view`, `cli` or `app` (module-graph scan,
      api reference §1)
- [ ] `UT-A1-7` `new_run_id` is stable for identical inputs and differs for any
      single changed input (`N-9`) — the equality is itself diagnostic
- [ ] `UT-A1-8` `log()` emits one line with fields in the fixed order of `N-10`;
      an `event` outside the closed enum is a `TypeError`; a multi-line `msg` is
      flattened, never wrapped
- [ ] `UT-A1-9` the subpackage set on disk **equals** api reference §1's list —
      neither doc nor tree may drift alone
- [ ] `ST-A1-1` `pip install -e modules/sim` then `python -c "import adas_sim"`
      from a directory outside the repo
- [ ] `ST-A1-2` `conan editable add modules/sim` succeeds and `conan graph info`
      resolves `adas-sim`

**Discipline** (every stage)
- [ ] [sim_portability.md](sim_portability.md) §3 ticked — exposure here:
      `P-2` (no absolute paths), `P-4` (console + file encoding), `P-6` (entry
      point, not a `.bat`), `P-10` (every dep has a Linux wheel)
- [ ] [sim_naming_and_diagnostics.md](sim_naming_and_diagnostics.md) §3 ticked —
      exposure here: `N-3` (this stage names the modules; a generic name added
      now is permanent), `N-7`, `N-8`, `N-10`
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `pytest modules/sim/tests -q` green; `GT-1..GT-3`, `GT-6` pass; and
      `UT-A1-9` green — the tree and the API reference agree, which is the
      cheapest moment to make that true and the most expensive to retrofit

### S-A2 — `model/` — configuration is the source of geometry

**Purpose.** Every number that describes the physical world comes from resolved
YAML, never a module constant. Implements `R-SIM-3`, closes **D3**. Ports the
generic half of `modules/df/docs/bsd/py/bsdviz/{calib,egogeom}.py`.

**Must not.** Contain a single literal vehicle or sensor dimension (`GT-3`), and
must not know the name of any driving function — sensor keys are parsed **by key
shape**, never by their domain prefix, which is data (`GT-1`).

- [ ] `model/project.py` — `ProjectModel.resolve(...)` (api reference §6).
      Resolution order **explicit → embedded-in-recording → library `config/` →
      source checkout**, and `bundle_origin` **always states which**
      (`R-SIM-3a`). The failure this prevents: the viewer and the SUT reading
      different files and agreeing only by coincidence
- [ ] `model/ego.py` — `EgoModel`: `x_front = wheelbase + overhang_front`,
      `x_rear = x_front - length`, `half_width = width/2`. Frame per `R-COORD-1`
      (origin at rear-axle centre, +x forward, +y left)
- [ ] `model/objects.py` — `ObjectModel.footprint(class_name)` with the
      three-step precedence: per-object `geometry` → class table → declared
      fallback. **The fallback sets `assumed_geometry=True`**, and `R-SIM-3`
      requires it to be drawn in a style that makes it visibly a guess
- [ ] `model/sensors.py` — `SensorModel`, parsing `<PREFIX>_SENSOR_<i>_<FIELD>`
      **by key shape** (`UT-A2-9` plants a different prefix and expects it to
      work unchanged)
- [ ] `model/cameras.py` — `CameraModel`: intrinsics/extrinsics fields
      **declared**, projection unimplemented until S-D4. Declaring the shape now
      costs nothing and stops S-D4 from inventing it
- [ ] Every `open`/`read_text` names `encoding="utf-8"` (`P-4`); every path is a
      `Path` (`P-1`); every key comparison is exact, never case-folded (`P-3`)

**Tests**
- [ ] `UT-A2-1` `EgoModel.load("base")` → `x_front == 3.60`, `x_rear == -0.90`,
      `half_width == 0.90`
- [ ] `UT-A2-2` `base`, `2w_base`, `cus1` each yield their own numbers and no
      two are equal — the `R-SIM-3` promise that switching project changes the
      picture
- [ ] `UT-A2-3` a missing key raises `AuthoringError` naming **the key and the
      file**, not "KeyError"
- [ ] `UT-A2-4` footprint precedence: with `geometry` present it wins; without,
      the class table; without that, the fallback **and** `assumed_geometry`
      is `True`
- [ ] `UT-A2-5` two different object classes resolve to different footprints
- [ ] `UT-A2-6` `SensorModel` yields exactly the declared sensor count with
      pose/FOV/range/side populated; a **case-differing** key does **not**
      resolve, on every platform (`P-3`)
- [ ] `UT-A2-7` resolution order: with all four sources present, explicit wins;
      with three, the embedded bundle wins; `bundle_origin` reports which
- [ ] `UT-A2-8` unknown project raises naming **every searched path** (`N-8`)
- [ ] `UT-A2-9` **prefix independence**: a fixture using a different key prefix
      parses identically — proving the parser reads shape, not domain (`GT-1`)
- [ ] `UT-A2-10` a project mismatch emits `ProvenanceWarning` and **still
      resolves** — it degrades visibly, it does not stop a run (`R-SIM-3a`)
- [ ] `ST-A2-1` **equivalence with the code being replaced** — for every project,
      `EgoModel` and `SensorModel` values equal what the existing `bsdviz`
      modules produce today (skipped, with a named reason, if `modules/df` is
      absent)

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-1`, `P-3` (case-sensitive key and
      file lookup is first exercised here), `P-4`
- [ ] naming §3 ticked — exposure: `N-4` (every geometry value carries a unit
      suffix; a bare `width` is the defect that produces a plausible wrong
      picture), `N-8`
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-A2-1` green for all three projects — the replacement is provably
      value-identical before anything depends on it. `UT-A2-9` green, because a
      geometry layer that knows a function's name would pass every other test
      here and still be wrong

### S-A3 — `scene/` types + `render/theme.py`

**Purpose.** The central IR (`R-SIM-2`). Everything upstream produces `Scene`;
everything downstream consumes it. Getting this wrong is the one mistake that
cannot be localised later.

**Must not.** `scene/` imports nothing from `render/`, `view/`, `io/` or
`sources/`. A `Prim` never carries a colour, a pixel coordinate or a viewport
reference — only metres, a named frame and a **semantic** style token.

- [ ] `scene/types.py` — frozen `Prim`, `Layer`, `Scene` per api reference §5
      and visualization spec §2. Every prim carries `frame`, `style`, `pick_id`,
      `z`, `alpha`. `width_px`/`offset_px` are **the only** pixel fields, and
      exist because legibility is not physical (`R-SIM-2`)
- [ ] `scene/frames.py` — the frame graph: `ego` (default, `R-COORD-1`),
      `world`, `sensor:<id>`, `image:<cam>`. Composition is static (model) plus
      dynamic (`tick.pose`)
- [ ] `scene/registry.py` — `@layer_provider`, `@inspector_fields`, `@signal`;
      discovery **by import**, so a component adds a layer by existing.
      Duplicate id raises naming **both** providers (`N-8`)
- [ ] `scene/codec.py` — Scene to bytes and back, **protobuf**: field numbering
      gives minor-version tolerance for free, and a Foxglove renderer wants the
      schema anyway. `Scene.version` is `major.minor`; additive is minor
- [ ] `render/theme.py` — the token table for `dark`/`light`/`print`/`forced`
- [ ] `render/palette_check.py` — the six-check validator over each categorical
      set (visualization spec §3.4), runnable as `python -m`

**Tests**
- [ ] `UT-A3-1` every prim type constructs and is immutable (assignment raises)
- [ ] `UT-A3-2` `Scene` to bytes and back round-trips to an equal object
- [ ] `UT-A3-3` a prim with no `frame` defaults to `ego`; an unknown frame raises
      naming the known frames
- [ ] `UT-A3-4` an unknown style token raises — **no silent default colour**.
      A silent default is how a debug layer ends up looking authoritative
- [ ] `UT-A3-5` every token in the table resolves in **all four** themes
- [ ] `UT-A3-6` registry: duplicate layer id raises naming both providers
- [ ] `UT-A3-7` registry discovery finds a provider added by import alone
- [ ] `UT-A3-8` a `Scene` written with a **higher minor** version still reads —
      unknown fields skipped, known ones survive (`NR-SIM-3`)
- [ ] `UT-A3-9` a `Scene` written with a **higher major** version is **refused**
      with both versions named — never partially rendered
- [ ] `UT-A3-10` `scene/` imports nothing from `render`/`view`/`io`/`sources`
      (module scan) — the layering that makes `R-SIM-2` mechanical
- [ ] `UT-A3-11` no `Prim` field accepts a colour value: constructing one with
      a hex-literal style raises, because a hex string is not a semantic token
- [ ] `ST-A3-1` `python -m adas_sim.render.palette_check` exits 0 for `dark` and
      `light`; every pair in the 6-8 dE band has a **named** secondary encoding

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-4` (the codec writes bytes; encoding
      and newline must be explicit or goldens differ across platforms), `P-8`
      (any prim ordering that reaches bytes is sorted)
- [ ] naming §3 ticked — exposure: `N-2` (a `Layer.id` is fully qualified and
      reaches the viewer, a log line and a golden), `N-3`, `N-8`
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-A3-1` green — the palette is validated by computation, not taste; and
      `UT-A3-10` + `UT-A3-11` green, because a `Scene` that *can* hold a colour
      will eventually hold one

### S-A4 — `io/mcap` codec

**Purpose.** Prove `R-SIM-14`'s claim — a recording is a *model*, a format is a
*codec* of ~4 methods — by building the first one and nothing else.

**Must not.** Let any other module learn that mcap exists. `Session`, pipeline,
Scene, viewer and expectations are written against the model (`UT-A4-11`).

- [ ] `io/base.py` — `RecordingReader`/`RecordingWriter` Protocols,
      `Capabilities` (incl. `round_trips`, `write_only`), `TopicInfo`,
      `Provenance` enum (`measured|truth|mocked|simulated|overridden|unknown`),
      per api reference §4
- [ ] `io/registry.py` — `register(ext, reader=, writer=)`, lookup by extension;
      unknown extension raises naming **the extension and every registered one**
- [ ] `io/mcap.py` — the default codec; all capabilities true
- [ ] `io/legacy.py` — maps today's legacy topic names onto namespaced ones and
      synthesises the missing `VehSig` (recording doc §8). **This is the one
      sanctioned name translation** (`N-6`), declared as data and printed by
      `sim explain`
- [ ] `tests/fixtures/make_tiny_mcap.py` + the generated `tiny.mcap` — generated
      by a checked-in script, never hand-crafted, so it can be regenerated

**Tests**
- [ ] `UT-A4-1` write N messages, read back identical `(topic, log_time, bytes)`
- [ ] `UT-A4-2` `topics()` returns schema and provenance for each
- [ ] `UT-A4-3` meta blocks (`manifest`, `config_bundle`, `topic_provenance`)
      round-trip
- [ ] `UT-A4-4` a recording with no meta loads with `provenance == unknown` and
      does **not** raise — it degrades and says so (`R-SIM-6`)
- [ ] `UT-A4-5` legacy topic names map correctly; a legacy file reports
      `manifest: unknown`
- [ ] `UT-A4-6` `capabilities` are declared and reported
- [ ] `UT-A4-7` unknown extension raises naming registered codecs
- [ ] `UT-A4-8` `dt_s` reconstruction: gaps from `log_time`, tick 0 measured
      from 0 (recording doc §3.3)
- [ ] `UT-A4-9` a tick missing one of its grouped messages is reported, not
      silently dropped
- [ ] `UT-A4-10` **no name is translated**: for a round-trip through every
      registered codec, the set of topic and field names in the model is
      unchanged (`N-6`). `io/legacy.py` is the declared exception and its
      mapping is readable as data
- [ ] `UT-A4-11` **no module outside `io/` names a format**: a scan for format
      tokens across `core`/`model`/`scene`/`contracts`/`check` returns nothing
      (`R-SIM-14`)
- [ ] `UT-A4-12` two writes of the same messages produce **byte-identical**
      files: topic order sorted, no wall-clock in the payload (`P-8`)
- [ ] `ST-A4-1` **every** existing recording under the component's test-run
      directories loads; tick count > 0; no exception (skips with a named
      reason if that component is absent)
- [ ] `ST-A4-2` read, write, read yields an identical topic/message set

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-4` (explicit newline on every write),
      `P-8` (sorted topic order; integer `log_time_ns`, never a float), `P-1`
- [ ] naming §3 ticked — exposure: `N-6` (this stage is where a translation
      table would first be tempting), `N-2`, `N-8`
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-A4-1` green across every existing recording, and `UT-A4-11` +
      `UT-A4-12` green — nothing outside `io/` knows a format exists, and a
      recording is reproducible byte for byte


---

## 5. Phase B — The viewer, on pure replay

**Still no C++ and no DLL.** Every stage here is driven by an already-exported
`.mcap` that already carries the component's output ports — so this is *replay*
in the §1 sense, and the framework never needs a SIL binding yet.

**That ordering is a design decision, not a convenience.** Building the viewer
before the generic ABI exists means the only way to drive a component here would
be a component-specific ctypes binding **inside the framework** — which is an
`R-SIM-1` violation that would then have to be unpicked. Replay avoids needing
one at all: by the time the framework talks to a library (`S-C1c`), the generic
ABI already exists and the binding is component-agnostic by construction.

Two consequences worth holding on to:

- **Everything in Phase B is testable with no build.** A recording plus a golden
  is the whole fixture set, which is why `GT-4` cannot regress here.
- **The viewer's contract is fixed before its first real input arrives.** The
  viewer renders a `Session` (`R-SIM-13`) and nothing else, and it is easiest to
  keep that true while a `Session` is the only thing that exists.

### S-B1 — Layer providers + parity render

**Purpose.** Prove the Scene IR carries a real function's picture. Closes
**D2**, **D5**. First stage that touches a component repo — **adding, never
removing**.

**Must not.**
- Import a renderer, `cv2`, `matplotlib` or Qt from any provider (`GT-2`).
- **Recompute anything the SUT already produced** (`R-SIM-7`). If a ProPort
  carries a warning state, draw *that* state. `UT-B1-6` proves it by feeding a
  deliberately contradictory output and requiring the layer to show the
  contradiction — a layer that "corrects" the SUT is a layer that hides bugs.
- Delete or edit the existing viewer. Parity is demonstrated **against** it, and
  it is removed only in `S-E1` (`NR-SIM-30`).

- [ ] `modules/<name>/sim/layers/common.py` — ego body, objects, grid/frame
      furniture, HUD fields (the component-generic half)
- [ ] `modules/<name>/sim/layers/<fn>.py` — one file per function; each is the
      *only* place that function's picture is described
- [ ] Layers reconstructed from calibration rather than read from a port carry
      `derived=True` and render with the `derived` style variant — a **marked**
      stopgap, never a silent one (`R-SIM-7`)
- [ ] `modules/<name>/sim/viewpoints.yaml` — named viewpoints as data
- [ ] `render/bev.py` — the **Qt-independent** Scene-to-raster core, so it is
      testable headless and reusable by the image renderer. Qt enters in `S-B3`
      and never below this line
- [ ] `view/viewport.py` — `Viewport`, follow modes, presets, zoom-about-cursor

**Tests**
- [ ] `UT-B1-1` `requires` gating — a Tick lacking a function's output yields
      **no** layers for it and raises nothing
- [ ] `UT-B1-2` provider purity — same `Tick` twice yields equal `Layer`s
- [ ] `UT-B1-3` no provider module imports a renderer (AST scan; `GT-2` as a
      test, so the rule fails a run rather than a review)
- [ ] `UT-B1-4` the ego layer's box equals `EgoModel`'s numbers — asserted by
      **changing the project and seeing the box change**, not by comparing to a
      literal, which would just restate the constant being tested
- [ ] `UT-B1-5` two different object classes draw different footprints
- [ ] `UT-B1-6` warning state is **read**, not recomputed: feeding a
      contradictory output makes the layer show the contradictory value
      (`R-SIM-7`)
- [ ] `UT-B1-7` layers built from calibration reconstruction carry
      `derived=True` and render with the `derived` style variant
- [ ] `UT-B1-8` padding slots in a fixed-size object list produce no prims — the
      classic "50 objects at the origin" picture
- [ ] `UT-B1-9` viewport: metre-pixel-metre round-trips; zoom about the cursor
      keeps the cursor's world point fixed; scale clamps at its declared bounds
- [ ] `UT-B1-10` renderer hit-test resolves to the prim actually drawn — one
      hit-test path, not one per prim type
- [ ] `UT-B1-11` a provider reads `age_s`/`valid` off a `PortValue` and a stale
      port changes what it draws — the metadata survives the boundary
- [ ] `UT-B1-12` a **temporal** layer (an ego trail) built from `ctx.history`
      produces the right polyline, and the provider holds no state between
      calls: call it twice **out of order** and get identical output
- [ ] `UT-B1-13` **a provider is pure**: called twice with the same `LayerCtx`
      it returns equal layers and holds no attribute that changed between the
      calls (`R-SIM-2`)
- [ ] `UT-B1-14` no two layer ids share a prefix (`N-3b`) — solo/mute selects by
      id, and a prefix collision silently selects the wrong set
- [ ] `ST-B1-1` replay an existing recording — the `Scene` for every tick matches
      the golden
- [ ] `ST-B1-2` the same replay under a **different project** produces a
      different ego box and different geometry — configuration drives the
      picture (**D3**), and this is the test that proves it end to end
- [ ] `ST-B1-3` headless render of 100 ticks raises nothing and produces
      non-blank frames
- [ ] `MC-1` a human confirms the rendered frame is equivalent to the existing
      viewer's on the same tick — recorded with date and name

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-1`, `P-3` (a viewpoint or layer file
      referenced with the wrong case works here and fails on Ubuntu)
- [ ] naming §3 ticked — exposure: `N-2` (layer ids are fully qualified and
      reach the layer panel, goldens and `sim explain`), `N-3b` (no layer id may
      be a prefix of another, or solo/mute selects the wrong set)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-B1-1` + `MC-1` — parity proven before anything new is added. **The
      existing viewer is NOT deleted here** (that is `S-E1`), because parity is
      only meaningful while both exist
- [ ] `ST-B1-2` green — otherwise `D3` is closed on paper only

### S-B2 — `Session` + time transport

**Purpose.** Split executing from viewing, which is what makes backwards seek
possible at all. Closes **D7**; delivers the *scrolling* requirement
(`FR-SIM-12`) and the head model (`R-SIM-17`, `FR-SIM-17`).

**Must not.**
- Accumulate time as a float. `t_ns` is an integer accumulated from `dt_ns`;
  `t_s` is **derived and never fed back** (`P-8`). A float seconds accumulator
  here is precisely what makes a resim non-reproducible, and it fails silently.
- Let pass 2 mutate anything pass 1 produced. `Session` is immutable; that is
  what makes 100 random seeks a cheap test rather than a flaky one.
- Implement a backwards `exec()`. There is no inverse; see the head model.

- [ ] `core/tick.py` — `PortValue` (message + `age_s`/`valid`/`updated`/
      `origin`), `Tick` with **integer `t_ns`/`dt_ns`** and `pose`
      (api reference §2.2)
- [ ] `core/history.py` — `HistoryView`, a read-only windowed view over earlier
      ticks, and `FrameTree` composing static (model) + dynamic (`tick.pose`)
      transforms — together these are `LayerCtx`. **A windowed view, not the
      whole session**: handing a provider the full history invites it to become
      a second analysis engine
- [ ] `core/session.py` — `Session`, `at(i)`, `seek_ns(t_ns)`, `events`,
      `deterministic`
- [ ] `core/runner.py` — pass 1 for the replay case; pass 2 is the renderer
- [ ] `view/transport.py` — play/pause, step ±1/±10, speed, loop marks, goto,
      jump-to-event, **and the head** (`R-SIM-17`): `head_tick`, `is_at_head`,
      advance-N as one cancellable job with progress, `review_mode` on stepping
      back, and `resume_options()` returning **exactly two named choices** so
      that silently continuing from a rewound tick is not representable
- [ ] Scene cache keyed by `(tick, layer_selection, theme)`, with a **stated
      bound** — an unbounded cache over a 36 000-tick session is `OQ-6` arriving
      early

**Tests**
- [ ] `UT-B2-1` `seek_time` maps a time to the correct tick at boundaries
- [ ] `UT-B2-2` **backwards seek**: from tick N to tick 0 returns tick 0's exact
      data — the thing that is impossible today
- [ ] `UT-B2-3` toggling a layer re-renders and does **not** re-run pass 1
      (assert a pass-1 call counter is unchanged) — the test that keeps the
      layer panel feeling like a tool rather than a re-run
- [ ] `UT-B2-4` speed/loop/step arithmetic at the ends (tick 0, tick N)
- [ ] `UT-B2-5` cache invalidates on theme change, **not** on viewport change
- [ ] `UT-B2-6` **time is exact**: `t_ns` accumulated over 10 000 ticks equals
      the sum of `dt_ns` with zero drift; `t_s` is derived and never fed back
- [ ] `UT-B2-7` **stepping backward leaves execution mode**: `is_at_head` goes
      false, `review_mode` true, and the SUT's `exec()` counter does not advance
      on any further backward step or seek
- [ ] `UT-B2-8` **resume offers exactly two choices**, and *recompute-from-0* is
      unavailable when `deterministic` is false, carrying its reason
- [ ] `UT-B2-9` **no silent continue**: advancing from a rewound tick without
      choosing raises, rather than calling `exec()` with mismatched state
- [ ] `UT-B2-10` advance-N arithmetic: 50/100/200/custom clamp at the end;
      cancel at tick *k* leaves `head_tick == k`
- [ ] `UT-B2-11` `Session` is immutable: mutating a returned `Tick` or its
      `ports` raises, so pass 2 cannot corrupt pass 1
- [ ] `UT-B2-12` the Scene cache respects its bound and evicts least-recently-
      used, measured on a session larger than the bound
- [ ] `ST-B2-1` on a ≥1000-tick session, 100 random seeks all return correct data
- [ ] `ST-B2-2` a full pass 1 over the largest existing recording completes
      within a stated budget, **recorded as a number** — not asserted as a limit
      until a baseline exists
- [ ] `ST-B2-3` **rewind then recompute-from-0 is exact**: recomputing to tick
      *N* reproduces the original tick *N* byte-for-byte on a deterministic
      resim

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-8` (integer `t_ns` throughout; a
      float seconds accumulator here is what makes resim non-reproducible)
- [ ] naming §3 ticked — exposure: `N-7` (`Session`/`Tick`/`Transport` reprs are
      what a debugger shows during a seek bug), `N-10` (`tick=` on every line)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `UT-B2-2` + `ST-B2-1` green; the "forward only, no rewind" caveat is
      deleted from the existing tool's docstring only in `S-E1`
- [ ] `UT-B2-6` green — exact time is the precondition for every determinism
      claim later in this plan, and it is cheapest to establish here

### S-B3 — Qt viewer shell

**Purpose.** The interactive surface: docks, panels, layer tree, inspector,
timeline, plots. Everything a developer touches, over the `Session` that `S-B2`
made seekable.

**Must not.**
- **Run pass 1 on the GUI thread.** Building a `Session` blocks for as long as
  the recording is long; doing it on the UI thread defeats the scrubbing this
  phase exists to deliver, and the symptom (a frozen window) gets misread as a
  performance problem rather than a threading one. Pass 1 runs on a worker;
  results are handed back by signal; the GUI never blocks on it.
- **Put logic in the shell** (`GT-9`). A panel arranges and dispatches; anything
  it computes belongs in `core/`, `view/` or `check/` where it is testable
  headless. The test for this is whether `ST-B3-1` can do it with no window.
- Name a font family, write a settings path by hand, or assume a display
  exists (`P-7`).

- [ ] `render/viewer.py` — the Qt window; a **dockable peer-panel grid** where
      BEV, camera, plots, timeline, inspector, layers and pipeline are all
      panels, none privileged (visualization spec §11.1)
- [ ] **Threading**: pass 1 on a `QThread`/worker, progress by signal,
      cancellable; the Scene cache is read from the GUI thread only. One
      documented ownership rule, stated in the module docstring
- [ ] `view/layers.py` — layer tree, groups, solo/mute, verbosity level, search,
      per-project persistence
- [ ] `view/workspace.py` — read `modules/<name>/sim/workspace.yaml`; shipped
      default, user override, reset (viz §13b). **A component's arrangement, not
      an application mode** — Bench/Campaign arrive in `S-D8` and load this
- [ ] `Interaction` on `LayerCtx` + `reacts_to=` on the provider decorator;
      the cache key includes interaction **only for declaring layers**, so a
      mouse move does not invalidate the whole scene (viz §7.5)
- [ ] `view/inspector.py` — docked, declared fields, pin, multi-select,
      copy-as-text
- [ ] `view/timeline.py` — signal lanes (one scale per lane), state lanes with
      labels, event markers, bookmarks, click-to-seek
- [ ] `view/signals.py` — the **one signal resolver** (viz §7.4):
      `<component>.<port>.<field>` · `source.*` · `truth.*` · `derived.*`. Raw
      port fields resolve off the manifest with **no registration**; only
      computed signals register with `@signal` (`NR-SIM-8`)
- [ ] `view/plots.py` — `timeseries` / `xy` / `state` / `distribution` panels
      over that resolver
- [ ] `view/measure.py` — ruler with snap, range rings, cursor readout carrying
      the **frame name**, persistent annotations
- [ ] HUD + the stale/invalid banner (viz §10)
- [ ] `cli/view.py`, `cli/render.py` — argument parsing only. **Not
      `app/cli.py`**: `app/` is the GUI and holds no logic (`GT-9`)

**Tests**
- [ ] `UT-B3-1` layer-tree state: group tri-state, solo/mute, persistence
      round-trips
- [ ] `UT-B3-2` inspector resolves a `pick_id` to its provider's declared fields;
      an entity that disappears is **dropped, not shown stale**
- [ ] `UT-B3-3` timeline: a state lane emits an event marker at every transition
      and only there
- [ ] `UT-B3-4` ruler distance/dx/dy/bearing correct; snap picks the nearest
      anchor within the threshold
- [ ] `UT-B3-5` stale banner appears exactly when `valid == 0` or the port's age
      exceeds its declared maximum
- [ ] `UT-B3-6` one signal string resolves identically for the timeline strip
      and a plot panel; a **raw port field needs no registration** at all
- [ ] `UT-B3-7` a `timeseries` lane with two signals of different magnitude
      creates **two lanes**; a single lane with two y-scales is rejected —
      a dual-axis plot is the most reliable way to make two signals look
      correlated when they are not
- [ ] `UT-B3-8` `xy` panel plots signal-vs-signal; colouring by a third works
- [ ] `UT-B3-9` playhead is shared — seeking in a plot moves the BEV and the
      timeline to the same tick
- [ ] `UT-B3-10` panel grid: open/close/split/tab/float; a saved layout restores
- [ ] `UT-B3-11` a component's `workspace.yaml` opens its declared tabs, splits
      and ratios; a **missing** workspace falls back to BEV + timeline, no error
- [ ] `UT-B3-12` the user's own layout wins over the shipped default, and
      `Reset layout` returns to it
- [ ] `UT-B3-13` a provider declaring `reacts_to=("cursor",)` receives the
      cursor **in its own frame, in metres**, and re-renders on cursor change
- [ ] `UT-B3-14` a provider declaring nothing is **not** re-rendered on a mouse
      move — interaction stays cheap, and purity holds
- [ ] `UT-B3-15` **pass 1 does not run on the GUI thread**: with a deliberately
      slow reader, the window stays responsive and progress is reported;
      asserted on thread identity, not on elapsed time
- [ ] `UT-B3-16` cancelling a load leaves no partial `Session` reachable — a
      half-built session rendered as if complete is a silent wrong picture
- [ ] `UT-B3-17` no Qt module is imported by anything under `core/`, `model/`,
      `scene/`, `contracts/`, `io/` or `check/` (`GT-9`, api reference §1)
- [ ] `ST-B3-1` `sim render <recording> --at <t> --preset <name> --out fig.png`
      produces a non-blank PNG **headlessly**
- [ ] `ST-B3-2` the full panel set opens and renders under an offscreen
      platform, on both platforms (`P-7`) — this is how the GUI is tested at all
- [ ] `MC-4` a human confirms scrubbing a long session feels responsive
- [ ] `MC-1` (repeat) a human confirms the full shell reads well

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-7` (every Qt rule: standard paths, no
      named font families, high-DPI policy set before the app object, offscreen
      must work)
- [ ] naming §3 ticked — exposure: `N-3a` (panel and dock classes are where
      generic names like `manager`/`handler` appear first), `N-7`
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `UT-B3-15` + `ST-B3-2` green — responsive by construction and testable
      with no display, which is what makes every later GUI stage cheap
- [ ] Every item in visualization spec §4–§9 demonstrable on one recording,
      ticked individually below:
      - [ ] pan / zoom / fit / presets / follow modes
      - [ ] scrub, step, speed, loop, jump-to-event
      - [ ] layer tree with groups + verbosity
      - [ ] selection + docked inspector
      - [ ] timeline signal + state lanes with markers
      - [ ] ruler, range rings, annotations
      - [ ] plot panels (timeseries / xy / state / distribution), playhead-synced
      - [ ] dockable peer-panel grid with a saveable layout
      - [ ] snapshot PNG **+ provenance sidecar**, and video export

### S-B4 — Capture with provenance

**Purpose.** A picture that leaves the tool must carry enough to be believed.
Closes `FR-SIM-13`.

**Must not.** Write a PNG whose sidecar could be lost without anyone noticing.
The sidecar is written in the same call, or the capture fails.

- [ ] `render/capture.py` — `snapshot(session, tick, viewport, layers, out)`
      writing `out.png` **and** `out.json` atomically (temp file, then rename;
      a half-written pair is worse than none)
- [ ] The sidecar carries: `run_id` (`N-9`), tick, `t_ns`, project,
      `bundle_sha256` **and** `bundle_origin`, scenario, pipeline hash, every
      component build hash, viewport, active layers, theme, Scene version, tool
      version
- [ ] `render/clip.py` — interval export to mp4, same sidecar, one per clip
- [ ] `cli/render.py` — headless `sim render --at <t|tick> --out fig.png`,
      working under an offscreen platform (`P-7`)
- [ ] Print variant: same Scene, `print` theme, vector output where the renderer
      supports it — one Scene, two renderers, never two drawing paths (`D5`)

**Tests**
- [ ] `UT-B4-1` a snapshot writes exactly two files, and neither exists if the
      other could not be written
- [ ] `UT-B4-2` the sidecar contains every field listed above; a missing one
      fails the test by name, not by count
- [ ] `UT-B4-3` a plot panel captures with the same sidecar shape as the BEV —
      one capture path, not one per panel type
- [ ] `UT-B4-4` a snapshot sidecar carries the **same `run_id`** as its session
      (`N-9`) — given any one artefact you can find the other five
- [ ] `UT-B4-5` `bundle_origin` is recorded, so a picture rendered from a
      checkout is distinguishable from one rendered from the embedded bundle
      (`R-SIM-3a`)
- [ ] `ST-B4-1` `sim render` twice at the same tick produces byte-identical PNGs
- [ ] `ST-B4-2` `sim render` works with **no display**, under an offscreen
      platform, on both platforms (`P-7`)

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-7` (offscreen is the tested path, not
      a fallback), `P-4`, `P-2`
- [ ] naming §3 ticked — exposure: `N-9` (this is where the correlation id earns
      its keep), `N-4` (sidecar fields carry units)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-B4-1` + `ST-B4-2` green — a snapshot is reproducible evidence, and it
      is producible on a build machine with no screen


---

## 6. Phase C — The SIL contract, the production side, the bundle

**The only phase that changes production C++**, and therefore the only phase
that can break a shipping component. Three properties hold throughout:

- **Every C++ change is additive until Phase E.** The generic exports live
  *beside* the positional ones and are tested against them; nothing is removed
  until `S-E2`, gated on the new path being proven equivalent.
- **`src/component/**` is never touched.** The new exports are a name-lookup
  shim onto the existing body (`df_sil_dll.md` rule 9). If a stage here needs an
  algorithm change, the stage is wrong.
- **`GT-4` is re-checked after every commit in this phase**, not just at the
  stage gate. A component's own test suite going from green to green is the only
  evidence that "additive" was true.

**Two platform traps this phase must avoid**, both of which an earlier draft of
this plan walked into and which are the reason
[sim_portability.md](sim_portability.md) exists:

| Trap | Wrong | Right |
|---|---|---|
| Locating the library's own directory | `GetModuleFileNameW` — Windows-only, and it appears in the natural first draft of `adasInit(NULL)` | a one-function abstraction: `GetModuleFileNameW` on Windows, `dladdr` on Linux, declared in the contract doc and implemented once (`P-5`) |
| The bundle's output path | `<build>/…/Release/config/` — `Release/` is a multi-config generator artefact that does not exist under Make/Ninja | `$<TARGET_FILE_DIR:…>/config/`, which is correct for every generator |

### S-C1a — `interfaces`: the ABI header and the manifest schema

*(`S-C1a`/`S-C1b`/`S-C1c` are the three sub-stages of the architecture's single
**C1**; they land separately because each is independently verifiable.)*

**Purpose.** Define the generic ABI and the manifest that makes ports
discoverable. **`D1` closes here or nowhere** — this is the stage that stops
`dfExec` growing a parameter pair per function.

**Must not.** Consume the header anywhere yet. This stage is purely additive:
`interfaces` builds, nothing links against the new symbols, and no component
changes. That is what makes it independently revertible.

- [ ] `interfaces/include/adas/adas_sil_abi.h` — `AdasPort`, `AdasPortSet`, the
      five exports (`sim_sil_contract.md` §3.1). **Where `R-SIM-4` is built**:
      ports are named and discovered, so adding a function adds a manifest line,
      never an ABI parameter and never a host edit
      - **C, not C++**: no `bool`, no namespaces, no default arguments, no
        `class`. Fixed-width integer types only (`int32_t`, `uint64_t`), and
        `size_t` for buffer lengths
      - **`cdecl` on both platforms.** No `__stdcall`, no `WINAPI`, no
        `__declspec` outside a single export macro that expands to
        `__attribute__((visibility("default")))` on GCC/Clang (`P-5`)
      - Struct layout is explicit: no bitfields, no `#pragma pack`, and every
        struct's size is asserted in a static assertion so a compiler change is
        a build failure rather than a silent ABI break
- [ ] `interfaces/proto/Adas__Sil/component_manifest.proto` — `ComponentManifest`
      incl. `project`, `config_bundle_sha256`, `descriptor_set`, `abi_version`,
      and per port: name, direction, `proto_type`, required/optional
      - Field naming per `R-NAME-4`; port names per `N-1` — **the token chosen
        here is the token every later layer reuses, and it is permanent**
- [ ] `R-NAME-4` / `R-STYLE-1` headers on both

**Tests**
- [ ] `UT-C1a-1` (gtest, `interfaces`) the header compiles as **C**, not just
      C++ — a `.c` translation unit including it, built as C11
- [ ] `UT-C1a-2` `ComponentManifest` round-trips in C++ and in Python
- [ ] `UT-C1a-3` every struct's `sizeof` and member offsets match the static
      assertions — an ABI break becomes a build failure, not a field that reads
      as garbage at run time
- [ ] `UT-C1a-4` the header contains no Windows-only type or calling convention
      (text scan for `WINAPI`/`__stdcall`/`HANDLE`/`DWORD`) — `P-5` as a test,
      because this header is the single hardest thing to change later
- [ ] `ST-C1a-1` `interfaces` builds clean; Python bindings generate

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-5` (the ABI header must compile for
      both toolchains; no Windows-only types), `P-8` (integer time in the
      manifest)
- [ ] naming §3 ticked — exposure: `N-1` (this stage fixes the port-name token
      that every later layer reuses — an abbreviation chosen here is
      permanent), `N-11`
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-C1a-1` green; `UT-C1a-4` green; nothing consumes the header yet
      (purely additive, and therefore revertible in one commit)

### S-C1b — the component library: generic exports **alongside** the positional ones

**Purpose.** Make one real component speak the generic ABI, with both ABIs live
and tested against each other (`sim_sil_contract.md` §6). This is the first
stage that modifies a shipping artefact.

**Must not.** Touch `src/component/**`. `adasExec` is a **name-lookup shim onto
the existing body** (`df_sil_dll.md` rule 9) — if this stage needs an algorithm
change, the design is wrong, not the algorithm. And must not remove or alter the
positional exports: `sil_host` still calls them, and `ST-C1b-2` proves it.

- [ ] `adasAbiVersion` / `adasManifest` / `adasInit` / `adasExec` /
      `adasShutdown` in the component's `*_interface_c.cpp`, `adasExec`
      dispatching **by port name** onto the existing implementation
- [ ] Manifest generator driven by `ENABLED_FUNCTIONS` (`R-VAR-5`), embedding
      the `FileDescriptorSet` — so the manifest **cannot drift from what was
      compiled**, which is the whole reason it is generated rather than written
- [ ] `<component>.ports.yaml` emitted beside the artefact **and** checked in,
      so a port change shows up as a reviewable diff rather than a rebuild
- [ ] `try/catch(...)` on every new `extern "C"` body (rule 12) — an exception
      crossing the ABI boundary is undefined behaviour, and the generic path
      doubles the number of places it could happen
- [ ] Export visibility via the one macro from `S-C1a`; **no `.def` file**, which
      would be a second, Windows-only source of truth for the export list

**Tests** — in the component's own `tests/unit/sil/`
- [ ] `UT-C1b-1` every existing positional-API test assertion **mirrored** onto
      the generic path, with identical expected values
- [ ] `UT-C1b-2` an unknown input port is ignored (forward compatibility: an
      older library must tolerate a newer host offering extra ports)
- [ ] `UT-C1b-3` a required input that is absent behaves exactly as `valid == 0`
- [ ] `UT-C1b-4` an all-default (zero-byte) payload with `valid == 1` is accepted
      — the regression from `df_sil_dll.md` §1 bug 2, re-asserted on the new path
- [ ] `UT-C1b-5` an undersized output buffer returns the **required size** and
      writes nothing — the caller retries once, and a second undersize is a bug
- [ ] `UT-C1b-6` embedded manifest equals the emitted `<component>.ports.yaml`
- [ ] `UT-C1b-7` a build with one function **disabled** yields no port for it in
      either the manifest or the YAML (`R-VAR-5`: selection is compile-time)
- [ ] `UT-C1b-8` `descriptor_set` contains every `proto_type` the manifest names,
      **transitively** — a host builds message classes from this alone, so a
      missing nested type is a failure that only appears on another machine
- [ ] `UT-C1b-9` **one token, every layer** (`N-1`): the manifest's port tokens,
      the `ENABLED_FUNCTIONS` list and the `src/component/` directory names
      agree exactly; any disagreement fails naming all three. This is what makes
      a single grep return the whole vertical slice
- [ ] `UT-C1b-10` an exception thrown inside the implementation is caught at the
      boundary and returned as a status, never propagated across `extern "C"`
- [ ] `ST-C1b-1` **equivalence**: for a fixed sequence of inputs, the generic
      and positional paths produce **byte-identical** outputs
- [ ] `ST-C1b-2` `sil_host` still builds and runs unchanged (it still calls the
      positional API)

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-5` (exports are `cdecl` on both; no
      `__stdcall`, no `.def`), `P-3`
- [ ] naming §3 ticked — exposure: `N-1` (the manifest is where
      one-token-every-layer becomes checkable — `UT-C1b-9`), `N-4` (port fields
      carry units)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-C1b-1` green — the new path is proven equivalent **before** anything
      depends on it, which is the precondition for `S-E2` ever removing the old
      one
- [ ] `GT-4` green at or above its prior count, checked **per commit** in this
      stage, not only here

### S-C1c — `contracts/` — `SilComponent`, `Pipeline`

**Purpose.** The Python side of the contract, and the wiring engine. After this
stage the framework can drive any component that ships a manifest — including
components that do not exist yet, which is `FR-SIM-70`'s claim.

**Must not.** Import a generated protobuf binding, or name a component, a
function or a port anywhere in the framework. `GT-6` and `GT-1` are both live
here, and `UT-C1c-3` runs with the generated bindings made **unimportable** so
the claim is tested rather than asserted.

- [ ] `contracts/component.py` — the `SilComponent` Protocol plus
      `CtypesSilComponent` and `InProcessSilComponent` (api reference §3.1)
- [ ] `contracts/loader.py` — **`resolve_library`**, the single place the
      framework consults the platform (`P-5`). `<stem>` expands to
      `<stem>.dll` on Windows and `lib<stem>.so` / `<stem>.so` on Linux; a miss
      names **every pattern tried and every directory searched** (`N-8`)
- [ ] Proto class resolution from `descriptor_set` via `DescriptorPool` +
      `message_factory` — **no generated bindings imported** (`R-SIM-11`)
- [ ] Per-handle port buffers (fixes the ctypes keepalive trap: a buffer that is
      garbage-collected while the DLL holds a pointer to it fails rarely and
      unreproducibly, which is the worst failure mode available); grow-once-and-
      retry on undersize
- [ ] `contracts/pipeline.py` — `mode:` × `impl:`, wiring **per port**,
      load-time validation in the order given in api reference §3.3
- [ ] `contracts/override.py` — the closed four-verb list (`R-SIM-15`)
- [ ] Component pipeline files under `modules/<name>/sim/pipelines/`

**Tests**
- [ ] `UT-C1c-1` ABI version mismatch fails loudly at load, naming both versions
- [ ] `UT-C1c-2` manifest parse yields discovered ports; **no hardcoded port
      name anywhere in the framework** (grep, as a test)
- [ ] `UT-C1c-3` message classes built from `descriptor_set` alone, with the
      generated bindings **not importable** in the test environment
- [ ] `UT-C1c-4` ports match by name regardless of order
- [ ] `UT-C1c-5` buffer grow-and-retry succeeds once and logs; a second failure
      raises
- [ ] `UT-C1c-6` pipeline wiring: `proto_type` mismatch raises naming both ends
- [ ] `UT-C1c-7` missing required input raises naming the port
- [ ] `UT-C1c-8` a reference to a port nobody produces raises
- [ ] `UT-C1c-9` a forward reference (B feeding an earlier A) raises — **no
      silent last-tick value**, which would look like it worked
- [ ] `UT-C1c-10` `mode: measured` with the recording lacking that stage's
      outputs raises naming the missing topics
- [ ] `UT-C1c-11` `mode: measured` ignores that stage's inputs and injects
      recorded outputs
- [ ] `UT-C1c-12` `mode: off` yields `valid == 0` downstream
- [ ] `UT-C1c-13` flipping `mode` does not require `impl:` to change — the
      toggle is reversible without re-authoring (`R-SIM-10`)
- [ ] `UT-C1c-14` stages execute in declaration order, single-threaded; a
      pipeline whose declaration order contradicts its wiring is a load error
- [ ] `UT-C1c-15` `resolve_library` returns the right file for each platform
      pattern (parametrised over both), and a miss names every candidate
- [ ] `UT-C1c-16` **severed chain detected** — `simulate → measured → simulate`
      on one path is found; `off → measured → simulate` is **not** flagged
      (`R-SIM-10`; the GUI's auto-close in S-D6 builds on this)
- [ ] `UT-C1c-17` an override applies at a port and at a field path, and a verb
      outside the closed four is a **load error**, not a warning (`R-SIM-15`)
- [ ] `ST-C1c-1` resim **every** existing recording through
      `CtypesSilComponent` and compare with the positional path —
      byte-identical (integration; skips with a named reason if the library is
      not built)
- [ ] `ST-C1c-2` an algo-test pipeline runs with everything `measured` except
      one stage — the canonical shape of `R-SIM-12`

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-5` (**the** stage that owns
      `resolve_library`; every platform difference in the framework lives here
      and nowhere else), `P-2`
- [ ] naming §3 ticked — exposure: `N-8` (wiring errors are the most-read
      messages in the system: expected, found, where it looked, next action),
      `N-5`
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-C1c-1` green over every recording — the generic path is proven
      equivalent before anything depends on it exclusively
- [ ] `GT-6` green — the framework imports no generated bindings, tested by
      making them unimportable rather than by inspection

### S-C2 — `sources/` — the production side

**Purpose.** Separate *producing* a recording from *executing* one
(`R-SIM-12`). Today one 983-line script does both, which is why it is 983 lines.

**Must not.** Move the existing bridge. This stage **decomposes by copy**: the
original keeps working until `S-E1` deletes it, gated on this stage's tests.
Nothing in `sources/` may name a driving function (`GT-1`).

- [ ] `sources/base.py` — the `Source` Protocol; `emits()` declares what this
      world can produce, so a pipeline asking for a level the source cannot
      emit is a **startup error naming both ends** (`R-SIM-10`)
- [ ] `sources/<world>/` — connection, spawn, lane advance, actor behaviour,
      frame conversion, chase transform — the engine, **verbatim in behaviour**.
      Behavioural equivalence is the point; tidiness is not
- [ ] `sources/<world>/mocks.py` — world-model to port synthesis, tagged
      `mocked`; ground truth tagged `truth` (`R-SIM-12`)
- [ ] `sources/<world>/catalogue.yaml` — blueprint to classification/dimensions
- [ ] `sources/synthetic.py` — scripted stimuli, no world model. **This is the
      one every framework test uses**, so it must land with the others rather
      than after them
- [ ] `core/manifest.py` — the run manifest (recording doc §2), carrying the
      `run_id` (`N-9`)
- [ ] Recorder derives its topic list **from the pipeline's port manifests**
      (`R-SIM-6`) and writes every stage's inputs *and* outputs — so "did we
      record everything the SUT reads?" is true by construction rather than by
      diligence
- [ ] `cli/record.py`, `cli/run.py`, `cli/resim.py` — argument parsing only.
      **Not `app/cli.py`**: `app/` is the GUI and holds no logic (`GT-9`), and
      the package map is asserted by `UT-A1-9`

**Tests**
- [ ] `UT-C2-1` frame conversion — the existing sign conventions, re-asserted
      (world to ego, right-to-left flip, `R-COORD-1`)
- [ ] `UT-C2-2` lane-advance heading ramp + yaw-rate averaging against a
      **mocked** world — the technique already proven for the original
- [ ] `UT-C2-3` angle difference across the ±180° seam
- [ ] `UT-C2-4` lateral-profile phases incl. `raised_cosine` displacement =
      `rate * duration / 2`
- [ ] `UT-C2-5` run manifest contains every declared field; hashes are stable
- [ ] `UT-C2-6` the recorder's topic list **equals** the union of the pipeline's
      declared ports — no port silently unrecorded (`R-SIM-6`)
- [ ] `UT-C2-7` the previously-unrecorded ego-signal port is recorded — the
      determinism hole in recording doc §4 is closed
- [ ] `UT-C2-8` provenance tags: mocked ports `mocked`, world truth `truth`,
      component outputs `simulated` (`R-SIM-12`)
- [ ] `UT-C2-9` a resim against a recording whose port manifest differs is a
      **hard error**; a differing library hash is a **warning** — the two are
      not the same severity and must not be merged
- [ ] `UT-C2-10` `emits()` is honoured: a pipeline requesting a port this source
      cannot produce fails at load naming the source and the port
- [ ] `UT-C2-11` no module under `sources/` launches a process through a shell
      or names an absolute path (`P-2`, `P-6`)
- [ ] `ST-C2-1` `sim record` on the synthetic source produces a recording that
      `sim resim` consumes with every stage `measured` except one
- [ ] `ST-C2-2` `sim resim` reproduces byte-identical outputs across two runs
- [ ] `MC-2` a live run records correctly against a real world-model server

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-2` (a world-model client is the
      likeliest place an absolute path creeps in), `P-6` (never launch a
      simulator through a shell)
- [ ] naming §3 ticked — exposure: `N-5` (a source's emitted names state origin,
      not intent), `N-12` (`sources/` in a traceback must mean *the world* lied)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-C2-2` green; `MC-2` recorded with a date and a name
- [ ] The original bridge still runs — this stage copied, it did not move, and
      `S-E1` is the only place anything is deleted (`NR-SIM-30`)

### S-C3 — Scenario schema v2 + expectations

**Purpose.** Move a scenario's intent out of prose and into data. Closes
**D10**, **D11**; builds `R-SIM-8`.

**Must not.** Write an expectation that merely records today's behaviour. An
expectation transcribed from a comment is checked against **what the comment
claimed**, not against what the code currently does — otherwise the suite locks
in the present including its bugs, and every later regression reads as a broken
test rather than broken code. The migration record (this stage's gate) lists
every claim that could **not** be expressed, which is the honest output of that
review.

- [ ] Schema v2 loader + **v1 upgrader** (`sim_scenarios_and_expectations.md` §3.2)
- [ ] `sensor_models/`, `pipelines/`, `viewpoints.yaml` presets
- [ ] `check/expect.py` — the predicate vocabulary (§5.2), `markers:` with
      `from:` provenance. **This is where `R-SIM-8` is built**: expectations
      are data from one source, every timing predicate carries an explicit
      `within_s`, and the same block drives the marker, `sim check` and the
      report — never three copies
- [ ] `check/report.py` — `report.md` / `report.json`
- [ ] `cli/check.py` — `sim check` (argument parsing only, `GT-9`)
- [ ] Timeline renders expectation windows (visualization spec §7.3)

**Tests**
- [ ] `UT-C3-1` every v1 scenario loads through the upgrader and yields the same
      effective run configuration
- [ ] `UT-C3-2` each predicate — `equals`/`always`/`during`/`whenever`,
      `becomes`+`within_s`+`of`, `never`, `at_least_s`/`at_most_s`, `count`,
      `between`, `monotonic` — passes on a crafted signal and **fails** on a
      crafted counter-signal (both directions, or the predicate is untested)
- [ ] `UT-C3-3` a timing predicate without `within_s` is a **schema error**
- [ ] `UT-C3-4` `marker.<name>` resolves; a missing marker names itself
- [ ] `UT-C3-5` report lists actual value and actual time next to expected
- [ ] `UT-C3-6` **one address space**: the same signal string resolves
      identically for a plot panel and for an `expect:` predicate; a raw port
      field needs no registration, a `derived.*` one does
- [ ] `ST-C3-1` all 18 scenarios load under v2
- [ ] `ST-C3-2` `sim check tests/carla_scenarios` runs headless, exits non-zero
      on a deliberately broken expectation
- [ ] `ST-C3-3` a scenario whose recording is missing is **skipped with a
      warning**, not failed

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-4` (scenario YAML read as UTF-8; report written with explicit newline or two machines produce different reports), `P-3`
- [ ] naming §3 ticked — exposure: `N-2` (an `expect:` path is the one address space, fully qualified), `N-4` (`within_s` is a unit-suffixed name for a reason)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] All 18 scenarios have `expect:` blocks **transcribed from their existing
      comment blocks**, each reviewed against the comment's claim before being
      accepted (§7 step 5 — an expectation that merely records today's behaviour
      is worse than none)
- [ ] The migration record lists every claim that **could not** be expressed

### S-C4 — Viewer reads real calibration; kill the duplicates

**Purpose.** Delete the hand-maintained duplicate of calibration the DLL already
reads. Small stage, disproportionate value: a duplicate that drifts produces a
picture that disagrees with the algorithm while looking authoritative.

**Must not.** Move any calibration into `shared_config` (`R-SIM-9`: those keys
are already runtime calibration with one consumer). This stage **deletes a
duplicate**; it does not relocate a source of truth.

- [ ] `SensorModel`/`ObjectModel` sourced from the project config for the
      component's layers; the hand-maintained pose constants and the
      per-project `if` branch are no longer used by the live path
- [ ] The duplicated constants are **deleted, not commented out** — a commented
      constant is a duplicate that still reads as authoritative

**Tests**
- [ ] `UT-C4-1` changing a sensor value in the project YAML changes the drawn
      FOV — asserted **on the Scene**, not by eye
- [ ] `UT-C4-2` the per-project branch is gone: two projects produce different
      geometry through the same code path, with no conditional on project name
- [ ] `ST-C4-1` no sensor pose or class footprint literal remains in any Python
      module on the live path (grep, as a test — `GT-3`)

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-3` (this stage deletes a duplicate of
      real calibration keys; a case-only mismatch would silently resurrect it)
- [ ] naming §3 ticked — exposure: `N-1` (the deletion is only safe because both
      spellings were the same token)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-C4-1` green — and `UT-C4-1` green, because a grep proving the literal
      is gone does not prove the replacement is wired to anything

### S-C5 — The packed config bundle (OD-4)

**Purpose.** One atomic bundle per (project, build), beside the library, so the
SUT and the viewer provably read the same bytes (`R-SIM-3a`). Closes
`plan.md` item 19 with evidence.

**Must not.** Compile configuration into the library — that would kill the
edit-and-re-run calibration loop. Copied **beside** the artefact, never inside
it (production uses AUTOSAR frozen parameters instead, `R-SIL-1`).

- [ ] Build copies `project.yaml` + `shared_config`'s `vehicle/ego_params.yaml`
      + `<component>.ports.yaml` into **`$<TARGET_FILE_DIR:…>/config/`** with
      `bundle.sha256`
      - `$<TARGET_FILE_DIR>`, **not** a hand-written `…/Release/…` path:
        `Release/` is a multi-config-generator artefact that does not exist
        under Make or Ninja, so a hard-coded path builds on Windows and silently
        writes to the wrong place on Linux
- [ ] `ParamLoader` reads a **directory**, not a file
- [ ] **`adasInit(NULL)` resolves `<library_dir>/config/`** — via a one-function
      abstraction over `GetModuleFileNameW` (Windows) and `dladdr` (Linux),
      declared in `sim_sil_contract.md` and implemented **once**. Calling the
      Windows API directly is the natural first draft and is wrong (`P-5`)
- [ ] `bundle.sha256` is computed over **UTF-8 bytes, `\n` newlines, sorted
      POSIX-style relative paths** (`P-9`) — a bundle built on Windows and one
      built on Linux must hash identically, or the "did the two readers agree?"
      guarantee is itself platform-dependent, which is worse than not having it
- [ ] `adasManifest()` reports `project` + `config_bundle_sha256`
- [ ] Recorder embeds the bundle on `/meta/config_bundle`
- [ ] `ProjectModel` prefers explicit → embedded → library → checkout, and the
      HUD **always says which** (`bundle_origin`)

**Tests**
- [ ] `UT-C5-1` `adasInit(NULL)` resolves the bundle beside the library
- [ ] `UT-C5-2` an explicit path always wins over the packed bundle
- [ ] `UT-C5-3` explicit path whose project differs from `manifest.project` →
      **`ProvenanceWarning`**, run proceeds (`R-SIM-3a`)
- [ ] `UT-C5-4` `bundle.sha256` changes when any file in the bundle changes,
      **including a case-only rename** (`P-3`)
- [ ] `UT-C5-5` the hash is **platform-stable**: computed from a fixture with
      mixed line endings and a shuffled directory iteration order, it is
      unchanged (`P-9`)
- [ ] `UT-C5-6` `run.overrides:` materialises a derived bundle; the manifest
      records the base hash **and** the override set
- [ ] `UT-C5-7` an override never writes back to the authoring YAML, and a swept
      run reports provenance as a statement, not a project mismatch
- [ ] `UT-C5-8` `--config-source` forces each of embedded / library / checkout /
      explicit, and the source actually used is reported every time
- [ ] `UT-C5-9` a recording with an embedded bundle renders with **no checkout
      present** — the claim `R-SIM-3a` exists to make
- [ ] `ST-C5-1` **the relocatability test**: copy the build output + `config/`
      to a directory with no Conan cache and no repo checkout; `sil_host` and
      `sim resim` both run correctly (this closes `plan.md` item 19)
- [ ] `ST-C5-2` the viewer's `bundle_origin` reports `embedded` for a new
      recording and `checkout` for a legacy one — the two readers agreeing by
      coincidence is exactly what this reports on

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-9` (**the** stage that owns bundle
      hashing), `P-5` (the library-directory lookup), `P-3`
- [ ] naming §3 ticked — exposure: `N-9` (the bundle hash joins the recording,
      the HUD and the report)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-C5-1` green — item 19 closed with evidence
- [ ] `UT-C5-5` green — the hash means the same thing on both platforms, which
      is what makes it usable as provenance at all


---

## 7. Phase D — Reach

### S-D1 — Foxglove `SceneUpdate` + Scene-in-recording

- [ ] `render/foxglove.py` — Scene → scene entities, one entity per layer
- [ ] frame graph emitted once from the project model (the fix for the
      transform-tree failure in `df_carla_viz_plan.md` §2)
- [ ] `/scene` topic written into a session recording

**Tests**
- [ ] `UT-D1-1` every prim type maps to a valid scene entity
- [ ] `UT-D1-2` every entity's `frame_id` exists in the emitted frame graph —
      the stranding bug, asserted
- [ ] `ST-D1-1` a written session recording opens in Foxglove Studio and shows
      the scene with working layer toggles and seek → `MC-3`

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-4`, `P-8` (entity ordering must be sorted or two exports of one scene differ)
- [ ] naming §3 ticked — exposure: `N-2` (a Foxglove entity id is a `Layer.id`, unchanged -- `N-6`)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-D1-1` green — the interop claim (`R-SIM-13`: visualization is
      identical regardless of origin) is demonstrated in a foreign viewer,
      not argued from the Scene's shape

### S-D2 — matplotlib renderer + `bsdviz` figure driver migration

- [ ] `render/matplotlib.py` — `print` theme, vector output, the `bev_axes`
      furniture guarantee
- [ ] `df_bsd_image_creation.py` driver rebuilt on the framework

**Tests**
- [ ] `UT-D2-1` the same Scene renders through both the raster and matplotlib
      renderers with no provider change
- [ ] `ST-D2-1` the BSD figure set regenerates and each figure is byte-stable
      across two runs
- [ ] `ST-D2-2` a figure and the live view of the same geometry use the same
      token → same semantic appearance (**D5** closed)

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-4` (figure output must be byte-stable across platforms), `P-7` (matplotlib runs headless here)
- [ ] naming §3 ticked — exposure: `N-6` (a figure label is the signal name, never a hand-typed caption)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-D2-1` + `ST-D2-2` green — one Scene, two renderers, one palette.
      A figure that disagrees with the live view is `D5` reopening

### S-D3 — GUI on run manifests

- [ ] `app/gui/` — component-agnostic, discovery-driven
- [ ] Pipeline panel per visualization spec §13 (per-stage measured/simulate)
- [ ] `modules/sim/sim_gui.bat`

**Tests**
- [ ] `UT-D3-1` discovery: stages from the pipeline, `impl:` choices from
      manifests on disk, `measured` availability from the recording topic index
- [ ] `UT-D3-2` `measured` is disabled with a reason when the recording lacks
      the topics
- [ ] `UT-D3-3` a `measured` stage below a `simulate` stage is flagged
- [ ] `UT-D3-4` the GUI builds a valid run manifest that the CLI accepts
      verbatim
- [ ] `ST-D3-1` every run in this plan is launchable from the GUI with no
      hand-typed command

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-7`, `P-2` (a run manifest must not embed a machine path)
- [ ] naming §3 ticked — exposure: `N-8` (the GUI surfaces the same messages the CLI raises -- one wording, not two), `N-9`
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `UT-D3-4` + `ST-D3-1` green — the GUI produces manifests the CLI
      accepts, which is what keeps them one engine (`R-SIM-16`) rather than
      two paths that drift

### S-D4 — Perception readiness

Gated on `perception-core` existing. Everything before it is additive.

- [ ] `CameraModel` + `render/image_view.py` (project Scene prims onto a frame)
- [ ] `ground_truth` and `perception` layer groups; `perception.error` derived
- [ ] `sources/carla` emits camera/radar stimuli

**Tests**
- [ ] `UT-D4-1` projection round-trips for a known intrinsic/extrinsic pair
- [ ] `UT-D4-2` a `Box` with `height` projects to a 3D box; the BEV and image
      views come from the same prim
- [ ] `ST-D4-1` a two-component pipeline runs and ground truth vs perception is
      visible side by side

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-8` (camera/projection maths must not introduce float time), `P-1`
- [ ] naming §3 ticked — exposure: `N-4` (intrinsics and extrinsics are unit-suffixed; a pixel and a metre sharing a bare name is the defect this rule exists for)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-D4-1` green — two components in one pipeline, with the downstream
      component's entry **byte-identical** to its single-component form
      (`R-SIM-10`'s central invariant, first demonstrated here)

### S-D5 — Package the player (`adas-sim.exe`)

Turns the library into the application of arch §5.15. Windows only.

- [ ] One-folder frozen build (PyInstaller or equivalent) bundling CPython, Qt,
      the framework, the renderers and the codecs
- [ ] **External plug-in import path** — `--plugins <root>` (repeatable) plus
      auto-discovery of a `sim/` folder beside a component library; providers
      are imported from outside the bundle, so adding a function's layers never
      rebuilds the player
- [ ] `--version` prints the player version **and** its compatibility statement:
      supported ABI generation, Scene major, recording-model and manifest
      versions
- [ ] Settings/layouts in `%LOCALAPPDATA%`, never inside the install or a repo
- [ ] Open-a-recording entry point (argument, and drag-onto-exe)

**Tests**
- [ ] `UT-D5-1` an input outside a declared compatibility range is **refused
      with both numbers named** (`NR-SIM-9`)
- [ ] `UT-D5-2` `--version` reports every one of the four version fields
- [ ] `UT-D5-3` the plug-in path imports providers from outside the bundle, and
      two roots with a duplicate layer id raise naming both
- [ ] `ST-D5-1` **the clean-machine test**: the frozen build opens a session
      recording and renders it on a machine with **no repo, no Python, no Conan
      cache and no component checkout**
- [ ] `ST-D5-2` pointed at a component library + its `config/` bundle, the
      player discovers its ports from the manifest and resims — **without that
      component having existed when the player was built** (`FR-SIM-70`)
- [ ] `ST-D5-3` a component's layer providers load from `--plugins` and draw,
      with no framework rebuild

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-6`, `P-7`, `P-10` (packaging is where a Linux-unavailable dependency finally bites; §4's bring-up table is the checklist)
- [ ] naming §3 ticked — exposure: `N-9` (`--version` prints the compatibility statement; a shipped binary must identify itself)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-D5-1` + `ST-D5-2` green — the player is genuinely component-agnostic
      and genuinely standalone, both demonstrated rather than argued

### S-D6 — Developer ergonomics: per-port overrides, `sim probe`, severed chain

Closes `FR-SIM-44`, `FR-SIM-45`, `FR-SIM-46`. This is the stage that decides
whether anyone writes a private player, so `GT-8` is measured here.

- [ ] `contracts/override.py` — the **closed** verb set `const` · `hold` ·
      `offset` · `scale`, resolved at a port or a field path
      (`egoDyn.vx`, `objects[*].pos_x`), applied between wiring and `exec()`
- [ ] Overrides land in the run manifest; the affected topic is tagged
      `origin: overridden` (`R-SIM-12`) and badged in the HUD (`R-SIM-15`)
- [ ] `cli/probe.py` — `sim probe <lib>`: load, read `adasManifest`, print the
      port set, types and schema names. **No mapping step, ever** (arch §5.16.1)
- [ ] `contracts/pipeline.py` — **severed-chain detection**: a `measured` stage
      between two `simulate` stages on one data path; auto-close on set,
      overridable, orphan stage flagged (`R-SIM-10`)
- [ ] `app/gui/pipeline_panel.py` — the per-stage mode toggle performs the
      auto-close undoably and renders the *"computed, not consumed"* badge
- [ ] `cli/explain.py` — **`sim explain <name>`**, the flagship debugging verb
      (`DG-2`). Accepts a port, field, layer id, style token, codec name,
      run id or error code; prints kind, type+unit, producer stage and mode,
      origin tag, topic presence, schema, which layer draws it, which
      expectation asserts it, and its value at the current tick. Every line
      comes from something already in the system — no new index
- [ ] `cli/doctor.py` — **`sim doctor`** (`DG-3`): interpreter and install
      mode; which library each `impl:` stem resolves to **and by which
      pattern, listing every directory searched** (`P-5`); which config
      bundle each stage resolves, from where, its hash, **and whether the
      viewer and the SUT would agree** (`R-SIM-3a`); codec capabilities;
      which cuts a recording supports; platform, line endings, console
      encoding (`P-4`). Non-zero exit on anything that would break a run
- [ ] `cli/list.py` — `sim list ports|topics|layers|signals` (`DG-1`)
- [ ] `impl: "legacy:<lib>"` — **scope only**: the adapter's config shape is
      specified, not implemented. No such binary exists yet; implementing it
      before one does would be speculative

**Tests**
- [ ] `UT-D6-1` each of the four verbs applies correctly at a port and at a
      field path; a fifth verb name is a **load error**, not a warning
- [ ] `UT-D6-2` an override appears in the run manifest and tags its topic
- [ ] `UT-D6-3` `sim probe` on `InProcessSilComponent` prints the same port set
      the pipeline resolves — one source, no second description
- [ ] `UT-D6-4` the **GUI** acts on a severed chain: given the detection from
      `UT-C1c-16`, setting a stage to `simulate` flips the intervening
      stages and shows the undo bar. Detection is the loader's; **acting on
      it is this stage's** — two tests, because a correct detector behind a
      GUI that ignores it is exactly the silent toggle `R-SIM-10` bans
- [ ] `UT-D6-5` auto-close flips only the intervening stages, and undo restores
      the exact prior modes
- [ ] `UT-D6-6` forcing the gap open is permitted and yields exactly one
      orphan-stage warning naming the stage
- [ ] `UT-D6-7` `sim explain` resolves each of the six accepted name kinds,
      and on an unknown name suggests a fuzzy match rather than failing
      bare (`DG-2`, `N-8`)
- [ ] `UT-D6-8` `sim doctor` exits non-zero on a broken stem, a bundle
      mismatch and a missing codec capability — and each message names the
      file (`DG-3`)
- [ ] `ST-D6-1` **day one, end to end**: a fresh component library with only a
      manifest is probed, wired into a five-line pipeline, run against
      `tiny.mcap`, and its outputs appear in a recording — **no edit anywhere in
      `modules/sim`** (`FR-SIM-46`)
- [ ] `ST-D6-2` a pipeline with overrides resims reproducibly: two runs produce
      byte-identical outputs and identical manifests

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-5` (`sim probe` and `sim doctor` are the tools that *explain* library resolution, so they must exercise every pattern), `P-2`
- [ ] naming §3 ticked — exposure: `N-1`/`N-6` (`sim explain` only works because one name means one thing everywhere -- this stage is where that pays off), `N-8`
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-D6-1` green **and `GT-8` measured and recorded** — the number goes in
      this document, whatever it is

### S-D7 — Writers, exports, `sim convert`, `sim batch`

Closes `FR-SIM-52`, `NR-SIM-21`. Readers already exist (S-A4); this stage makes
the codec table symmetric and adds the two verbs that scale it.

- [ ] `io/base.py` — the writer half of the codec protocol; capability flags
      extended with `round_trips` and `write_only`
- [ ] `io/mcap.py` — writer path (already partly present via the recorder)
- [ ] `io/csv.py` — **write-only** export codec: port selection by manifest
      name, one row per tick, one column per leaf field, `log_time_ns` plus
      optional `tick_index`/`scenario_time_s`, `<port>.age_s` for multi-rate,
      `#`-prefixed provenance preamble
- [ ] `cli/convert.py` — `sim convert <in> <out>`, recording → recording, refused
      when either side lacks `round_trips`
- [ ] `cli/export.py` — `sim export <in> <out> --ports …`, honouring
      `on_missing: error|blank|omit-column` (default `error`)
- [ ] The loader **refuses an export as a resim input by capability**, naming
      the file and the missing capability (`R-SIM-14`)
- [ ] `cli/batch.py` — `sim batch <recordings…|glob|list.txt> --pipeline P
      [--report] [-j N]`: the **same pipeline file** used interactively, one
      report, per-recording pass/fail, continue-on-failure

**Tests**
- [ ] `UT-D7-1` a port selection exports exactly the named leaf columns, in
      declared order
- [ ] `UT-D7-2` `log_time_ns` in the export matches the recording tick-for-tick
- [ ] `UT-D7-3` a held multi-rate value is distinguishable from a blank via
      `age_s`; a missing port errors by default and blanks only when asked
- [ ] `UT-D7-4` origin tags and override marks survive into the export header
- [ ] `UT-D7-5` a `write_only` codec is **refused** as a resim input, naming the
      capability
- [ ] `UT-D7-6` `sim convert` round-trips `tiny.mcap` → other → back with
      identical topics, schemas, provenance and message bytes
- [ ] `ST-D7-1` `sim export` on a real recording opens in a spreadsheet and in
- [ ] `ST-D7-4` an export header carries the `run_id`, the bundle hash and the
      origin tags of every exported port (`N-9`, `R-SIM-12`) — an export
      frequently becomes the thing a report quotes
      `pandas.read_csv` with the preamble skipped by its comment character
- [ ] `ST-D7-2` `sim batch` over ≥20 recordings produces one report with a row
      per recording; a failing recording does not abort the run
- [ ] `ST-D7-3` the pipeline file used by `sim resim` runs **unmodified** under
      `sim batch` (`R-SIM-16` — the identity is the point)

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-4` (an export written on two machines must be byte-identical or it is not evidence), `P-8` (sorted columns and topics)
- [ ] naming §3 ticked — exposure: `N-2`/`N-4` (a column header is a fully qualified, unit-suffixed name -- the export is often what a report quotes), `N-9`
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `UT-D7-5` + `ST-D7-2` + `ST-D7-3` green — an export can never be mistaken
      for a recording, and scale uses the developer's own file

### S-D8 — **Vantage**: the shell, and the Bench / Campaign workspaces

Closes `FR-SIM-47`, `FR-SIM-48`. Everything before this stage builds capability;
this stage decides whether anyone meets it. Spec:
[sim_player.md](sim_player.md).

**Shell**
- [ ] `app/shell/window.py` — one window, six regions (player §3): transport,
      pipeline dock, centre panel grid, layers dock, timeline, status
- [ ] `app/shell/workspace.py` — `Workspace` = a dock arrangement + a
      permission set. **Switching does not reload the engine and does not touch
      the open pipeline file** (`R-SIM-16` made visible in one gesture)
- [ ] `app/shell/palette.py` — `Ctrl+K` command palette listing every action,
      including those of closed docks. This is what lets `L-1` hold without
      hiding features
- [ ] `app/shell/startpage.py` — recent files, `Open recording…`,
      `Probe a library…`, three shipped sample pipelines. **No form, ever**

**Bench workspace**
- [ ] Per-port override affordance in the pipeline dock; an overridden port is
      amber **in every view it appears in** (`R-SIM-15`)
- [ ] Mode toggle with visible severed-chain auto-close and a one-line undo bar
      (`R-SIM-10`)
- [ ] `app/panels/probe.py` — drop a library on the window, see its ports. The
      day-one screen (arch §5.16.1)
- [ ] `app/panels/console.py` — Python console with `session`, `pipeline`,
      `scene` bound. The pressure valve that prevents a private fork (`GT-9`)

**Campaign workspace**
- [ ] Recording-set list + results table, driven by `sim batch` (S-D7)
- [ ] **`Open on Bench`** on any result row — that recording, that pipeline,
      at the failing tick. No conversion, no re-authoring
- [ ] The equivalent `sim batch` invocation is shown and copyable
- [ ] Locked: no overrides, no live mode toggles, no console; editing anything
      offers to open it on the Bench

**Lean limits, as code**
- [ ] `L-1` ≤ 12 controls visible at rest in the default Bench layout
- [ ] `L-2` ≤ 3 steps from launch to a moving picture
- [ ] `L-3` ≤ 4 concepts required before first use; every other concept surfaces
      **only when abnormal** — provenance when a port is not `simulated`, the
      bundle when missing, codec capabilities inside a degrade error

**Tests**
- [ ] `UT-D8-1` switching workspace preserves the loaded `Session`, the pipeline
      object **and the pipeline file's bytes** (asserted on the file, not the model)
- [ ] `UT-D8-2` Campaign refuses an override and offers the Bench instead;
      the refusal names the workspace, not a generic "not permitted"
- [ ] `UT-D8-3` `Open on Bench` reconstructs recording + pipeline + tick, and
      the reconstructed pipeline is **byte-identical** to the Campaign's
- [ ] `UT-D8-4` the shown `sim batch` invocation, run verbatim, reproduces the
      Campaign's result
- [ ] `UT-D8-5` `L-1`: the default Bench layout exposes ≤ 12 enabled controls
      (counted from the widget tree, offscreen)
- [ ] `UT-D8-6` `L-3`: with a fully normal run, no provenance badge, bundle
      warning or capability notice is present anywhere in the widget tree
- [ ] `UT-D8-7` a pipeline with one unresolvable stage still renders the
      resolvable ones, with the broken stage badged — degrade visibly, never
      refuse to draw
- [ ] `UT-D8-9` **the product and workspace names stay in `app/`**: no
      `Vantage`/`Bench`/`Campaign` token anywhere in `adas_sim/` outside
      `app/` (AST + text scan). The engine must not know which workspace is
      open — the same discipline `GT-1` applies to function names
      (`FR-SIM-48`)
- [ ] `UT-D8-8` no failure message consists only of an identifier; every one
      names expected, found and where it looked (§5.14's message contract),
      asserted over a table of induced failures
- [ ] `ST-D8-1` **portability**: the whole suite green on Linux with
      `QT_QPA_PLATFORM=offscreen` and no component built, skipping exactly the
      integration tests that need a library and naming why
      ([sim_portability.md](sim_portability.md) §4)
- [ ] `ST-D8-2` start page → open → play, driven programmatically, in ≤ 3 user
      actions (`L-2`)
- [ ] `MC-5` run and its **number recorded in this document**

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-7` (the whole Qt rule set), `P-3`, `P-2` (workspace state goes to the OS config location, never a written-out path)
- [ ] naming §3 ticked — exposure: `N-3a` (shell/panel classes attract generic names), `N-7`, `N-8` (`UT-D8-8` is the message contract, tested over induced failures)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `UT-D8-1` + `UT-D8-3` + `ST-D8-1` green, **and `MC-5` recorded with its
      measured time** — the workspace split is real only if one pipeline file
      survives it, and the tool is lean only if a stranger proved it

---

## 8. Phase E — Retirement (what leaves `modules/df`)

**Nothing here starts until Phases A–D are ticked.** Each deletion has a named
gate that proves the replacement works first.

### S-E1 — Delete `df`'s private tooling

**Delete** (gate: the named stage is green):

| Path | Lines | Replaced by | Gate |
|---|---|---|---|
| - [ ] `tools/carla/replay/viz.py` | 562 | `render/` + `df/sim/layers/` | S-B1, MC-1 |
| - [ ] `tools/carla/replay/foxglove_stream.py` | 113 | `render/foxglove.py` | S-D1 |
| - [ ] `tools/carla/replay/df_dll_sim_mcap.py` | 381 | `sim resim` | S-C1c, S-C2 |
| - [ ] `tools/carla/replay/requirements.txt` | — | `pyproject.toml` extras | S-A1 |
| - [ ] `tools/carla/df_ctypes.py` | 104 | `contracts/component.py` | S-C1c |
| - [ ] `tools/carla/mcap_recorder.py` | 99 | `io/mcap.py` + `sources/carla` | S-A4, S-C2 |
| - [ ] `tools/carla/carla_bridge.py` | 983 | `sources/carla/**` | S-C2, MC-2 |
| - [ ] `tools/carla/actor_behaviour.py` | 136 | `sources/carla/behaviour.py` | S-C2 |
| - [ ] `tools/carla/frame_convert.py` | 61 | `sources/carla/frames.py` | S-C2 |
| - [ ] `tools/carla/README.md`, `replay/README.md` | — | `modules/sim/README.md` | S-D3 |
| - [ ] `scripts/df_sim_gui.py` + `sim_gui.bat` | 647 | `app/gui/` | S-D3 |
| - [ ] `docs/bsd/py/bsdviz/{calib,egogeom,canvas,palette,frame,annotate,logs}.py` | ~440 | `model/`, `render/theme.py`, `render/matplotlib.py`, `scene/frames.py` | S-A2, S-A3, S-D2 |
| **Total removed** | **≈3,530** | | |

**Move into `modules/df/sim/`** (content, not framework):
- [ ] `docs/bsd/py/bsdviz/{zone,coverage,sensors,lean,kinematics}.py` → the BSD
      layer provider + figure content
- [ ] `docs/bsd/py/bsdviz/check.py` → stays a figure-verification concern under
      `docs/bsd/py/`

**Keep, untouched:**
- [ ] `src/component/**`, `src/platform/**`, `src/project/**`, `include/`,
      `conf/`, `CMakeLists.txt`, all build machinery
- [ ] `tests/unit|integration|fixtures` (gtest)
- [ ] `tests/carla_scenarios/**`, `tests/carla_testruns/**`
- [ ] `docs/bsd/{req,ref,images,logs}` and the figure content in `docs/bsd/py/`

**Tests**
- [ ] `ST-E1-1` nothing under `modules/df` imports `cv2`, `foxglove`, `mcap` or
      `ctypes`
- [ ] `ST-E1-2` no `sys.path.insert` into `docs/` anywhere (**D4** closed)
- [ ] `ST-E1-3` `modules/df/tools/` no longer exists
- [ ] `ST-E1-4` GT-4 — `df_tests` unchanged and green (this is a Python-only
      deletion, exactly as the 2026-07-13 relocation proved)

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-2` (deleting the old tooling must not leave an absolute path in a doc that referenced it)
- [ ] naming §3 ticked — exposure: `N-12` (after this stage a traceback path means exactly one layer; that is the point of the deletion)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-E1-1..4` green **and every replacement stage named in the table above
      already ticked** — `NR-SIM-30` is the rule this gate enforces: nothing is
      deleted before its replacement is proven, and the table's right-hand
      column is the proof obligation, checked row by row

### S-E2 — Retire the old ABI

- [ ] `sil_host/main.cpp` moves to the generic ABI
- [ ] Delete `dfApiVersion`/`dfInit`/`dfExec`/`dfShutdown` from
      `df_interface_c.h/.cpp`
- [ ] `df_sil_dll.md` updated — rules 8 and 11 now resolved, recorded as such

**Tests**
- [ ] `ST-E2-1` no reference to the removed symbols anywhere
- [ ] `ST-E2-2` `sil_host` runs end to end on the generic ABI
- [ ] `ST-E2-3` GT-4 green; `adasAbiVersion()` still `1` (adding functions never
      bumped it — the whole point)

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: `P-5` (removing the positional exports must not break either platform's loader path)
- [ ] naming §3 ticked — exposure: `N-1` (the old positional names disappear; nothing may keep a second spelling alive)
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-E2-1..3` green — the positional ABI is gone and `D1` cannot recur.
      `adasAbiVersion()` still `1` after every function added since S-C1a is
      the proof that adding a function never touched the ABI

### S-E3 — Final invariant gates

- [ ] `scripts/check_invariants.py` wired to run all of GT-1..GT-7
- [ ] `.claude` artifacts reviewed against the shipped code; any rule the code
      contradicts is fixed on one side
- [ ] `plan.md` item 25 marked `[x]`; item 19 marked `[x]` (closed by S-C5);
      item 4 re-scoped to the CarMaker codec

**Tests**
- [ ] `ST-E3-1` `check_invariants.py` exits 0
- [ ] `ST-E3-2` the full suite — `pytest modules/sim/tests` + `ctest` on `df` —
      green, with counts recorded

---

## 9. Traceability — every requirement to a stage and a test

| # | Requirement | Stage | Proven by |
|---|---|---|---|
| R1 | Scalable architecture for N functions | S-A3, S-B1 | `UT-B1-1`, GT-1 |
| R2 | Excellent 2D BEV, state of the art | S-B1..S-B4 | viz spec §16 checklist, `MC-1` |
| R3 | **Scrolling / time transport** | S-B2 | `UT-B2-2`, `ST-B2-1` |
| R4 | **Snapshots** | S-B4 | `UT-B4-1`, `ST-B4-1` |
| R5 | **Config-driven geometry per project** | S-A2, S-B1 | `UT-A2-1/2`, `ST-B1-2` |
| R6 | Python↔C adaptability via protobuf | S-C1a..S-C1c | `UT-C1c-3`, `ST-C1c-1` |
| R7 | Scales to perception | S-D4 | `ST-D4-1` |
| R8 | Visualization outside `df` | S-A1, S-E1 | GT-1, `ST-E1-3` |
| R9 | GUI restructured | S-D3 | `UT-D3-1..4` |
| R10 | `shared_config` = real runtime config only | S-C5 | `UT-C5-4`, R-SIM-9 |
| R11 | Config packed with the DLL | S-C5 | `ST-C5-1` |
| R12 | `df` vs superproject clarity | — | architecture §5.8 |
| R13 | `df`-alone resim | S-C1c, S-C5 | `UT-C1c-3`, `ST-C5-1` |
| R14 | Any injection level, one concept | S-C1c | `UT-C1c-10..13`, `ST-C1c-2` |
| R15 | Per-component measured/simulate (console model) | S-C1c, S-D3 | `UT-C1c-11`, `UT-D3-2` |
| R16 | Two sides: produce vs execute | S-C2 | `ST-C2-1` |
| R17 | Algo test = mock → mcap → isolate df | S-C2, S-C3 | `ST-C1c-2`, `ST-C2-1` |
| R18 | Change recording format easily | S-A4 | `UT-A4-7`, R-SIM-14 |
| R19 | Add components easily | S-C1c | `UT-C1c-2`, architecture §5.13 |
| R20 | Visualization constant regardless of origin | S-B1, S-D1 | `ST-B1-1`, R-SIM-13 |
| R21 | CarMaker | plan.md item 4 | a codec, per §5.12 |
| R22 | `df` cleaned up | S-E1 | `ST-E1-1..4` |
| R23 | Everything thoroughly tested | S-E3 | `ST-E3-2` |
| R24 | **A player application, not only a library** (`FR-SIM-70`) | S-D5 | `ST-D5-1`, `ST-D5-2` |
| R25 | **Step-wise execution + the head** (`FR-SIM-17`) | S-B2 | `UT-B2-7..10`, `ST-B2-3` |
| R26 | **Setting `sim` closes the chain** (`FR-SIM-44`) | S-D6 | `UT-D6-4..6` |
| R27 | **Developer can tweak individual inputs** (`FR-SIM-45`) | S-D6 | `UT-D6-1/2`, `ST-D6-2` |
| R28 | **One tool, not two; no onboarding handoff** (`FR-SIM-46`) | S-D6 | `GT-8`, `GT-9`, `ST-D6-1` |
| R29 | **Writers + export dumps with port selection** (`FR-SIM-52`) | S-D7 | `UT-D7-1..5`, `ST-D7-1` |
| R30 | **Mass-scale runs expressible** (`NR-SIM-21`) | S-D7 | `ST-D7-2`, `ST-D7-3` |

Defects `D1`–`D11` (architecture §3) map through architecture §6; each closes at
the stage named there.

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| **Golden Scenes churn on every cosmetic change** | Goldens are Scenes, not pixels — geometry and tokens, so a theme edit does not touch them. `--update-goldens` diffs must be reviewed. |
| **The parity gate is subjective** | `ST-B1-1` compares Scenes (objective); `MC-1` compares appearance (human, recorded). Both, not one. |
| **`ST-C1c-1` byte-equality fails for float reasons** | Compare parsed protobuf fields with an explicit tolerance policy decided *before* the first run, not after seeing a failure. |
| **Qt learning cost** | The Scene keeps the renderer thin; `render/bev.py` is Qt-independent and testable headless, so only the shell is Qt. |
| **Phase C touches production C++** | Every C++ change is additive until S-E2; both ABIs live and are tested against each other. |
| **No CI** | The test command is the gate and is cited in each commit. Wiring CI is `plan.md` item 12, unblocked by this work. |
| **`modules/sim` unpublished** | Until `adas-sim` is published, a checkout is needed; that is the same interim state `interfaces` and `shared_config` already live in. |

**Discipline** (every stage)
- [ ] portability §3 ticked — exposure: every `P-` rule, re-checked -- this is the last gate before the system is called done
- [ ] naming §3 ticked — exposure: every `N-` rule, re-checked; `DG-2`/`DG-3` must answer for every name the system can produce
- [ ] `python docs/py/run_all.py` green; `GT-1..GT-9` re-checked

**Gate**
- [ ] `ST-E3-1` + `ST-E3-2` green **and every global gate `GT-1..GT-9`
      ticked** — including `GT-8`'s measured number, which is the only one a
      green suite cannot substitute for
