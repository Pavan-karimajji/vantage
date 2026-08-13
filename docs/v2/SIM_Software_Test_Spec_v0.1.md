# SIM — Replay & Simulation Engine
## Software Test Specification — v0.1

**Owner:** SIM Team (tool supplier)
**Derived from:** `SIM_Software_Requirements_v0.1.md` (identifiers and acceptance criteria) and `SIM_Implementation_Design_v0.1.md` (artifacts under test).
**Status:** Draft for review. Not baselined. **Software level only** — the system (`SYT-*`) and end-to-end (`E2E-*`) test requirements, and the user-experience requirements for the tool as a whole, are deliberately not in this issue and are the next pass.

---

## 0. How to read this document

### 0.1 Scope, and the one rule that keeps it lean

SwReq §33.3 fixes what this document must add and what it must not:

> *Per identifier: preconditions and fixtures, exact steps, exact expected values … **It must not restate an acceptance criterion in different words** — where it needs different words, this document is wrong and is changed.*

So every row below gives a **fixture** and **steps**, and its expected value is the `Accept` clause of the requirement it serves, cited rather than paraphrased. A row that reworded an `Accept` clause would create a second copy free to drift from the first, which is `CN-0287` at test granularity.

**This is why the document is lean, and the leanness is the design rather than a shortcut.** The assertion already exists, once, in the Software Requirements.

### 0.2 Levels and identifiers

Every identifier below is **cited by a requirement in the Software Requirements**; none is invented here. `SW-0371` requires the identifier to appear inside the test that implements it, so the link is found by `grep` and not by a sentence in a plan.

| Prefix | Level | Proves |
|---|---|---|
| `UT-<item>-nn` | Unit | One software item through its own interface, collaborators stubbed |
| `IT-nn` | Integration | Two or more items across one named interface — most often the seam or the module ABI |
| `ANL-SW-nn` | Analysis | A static or derived property: a grep, a symbol dump, an import direction, a counter, a hash |
| `INSP-SW-nn` | Inspection | A property with no possible execution, against a **named** checklist |

**The counts are emitted by `docs/v2/py/trace_check.py --counts`, not typed here.** They were typed in an earlier draft and were wrong by one within a day, which is `SW-0373`'s own argument arriving a category smaller than it was written for: a number derivable from the document is a second stored copy, and a second copy drifts whether it holds a status or a total.

Item tokens: `IO` `BUS` `SCH` `HOST` `MUT` `RUN` `ERR` `EDG` `EXE` `CFG` `GRF` `ING` `RES` `SPC` `ORC` `PRP` `DIA` `SES` `SCN` `RND` `PLR` `LNC` `API` `PLG` `TRN`.

### 0.3 Rules this document is held to

| # | Rule | Enforced by |
|---|---|---|
| TV-1 | Every requirement has ≥1 test here, and every test here serves ≥1 requirement. | `ANL-SW-65`, `docs/v2/py/trace_check.py` |
| TV-2 | A test identifier appears verbatim inside its implementing test. | `ANL-SW-65` |
| TV-3 | **Every `ANL-*` check ships with a planted-violation test** proving it fails when it should. A check nobody has seen fail is a check nobody should believe. | `ANL-SW-64` |
| TV-4 | A measurement names its platform, shell, CPU and build type beside its number. | `SW-0367` |
| TV-5 | No test restates an `Accept` clause. | Review, `INSP-SW-08` |
| TV-6 | Verification status lives in the suite's results, never in a column here. | `ANL-SW-67`, `INSP-SW-08` |

### 0.4 The four thresholds that were missing — supplied or seeded, 2026-08-13

`⊘` means the harness is specified and buildable but no observation could fail
it, because the bound is the customer's (`R-REQ-10`). **A requirement nobody can
fail is a requirement that will be declared satisfied**, so such a row is marked
rather than given a plausible number.

**Four rows carried the mark and none does now** (`OQ-14`, `OQ-16` closed):

| Row | Now |
|---|---|
| `ANL-SW-63` | **Supplied.** ≥ 10.4 recordings/hour per worker, ≤ 5 min 46 s per recording, ≤ 4 GB peak per worker, on SysReq §18.0's reference configuration — derived from *1000 recordings overnight, 8 cores, 32 GB, lean `df`* |
| `ANL-SW-52`, `ANL-SW-43` | **Seeded.** No absolute was supplied, so each takes its bound from its first measurement on the reference configuration and is failable from the second run, with the seeding run marked and the consumed headroom printed on pass |
| `ANL-SW-57` | **Restructured.** The gate is the **diff**, not the stopwatch: each of the five common changes must touch exactly its declared file set. Failable today; the wall clock is recorded as an observation |

**Seeded is not unsupplied.** A seeded row has a number the next run can exceed,
a written reason and printed headroom; an unsupplied row has none of those. What
a seeded row does not answer is *"is it fast enough?"* — an absolute, and it
stays with whoever owns throughput expectations. Two rows elsewhere still carry
`⊘` for a different reason (`UT-DIA-02`, `UT-RND-06`): those await an
implementation, not a number.

---

## 1. Fixture catalogue

Named once, reused everywhere. A test that needs a fixture not listed here needs a new row here first — an ad-hoc fixture is how two tests come to disagree about what "a recording" means.

| Fixture | What it is | Used by |
|---|---|---|
| **`F-TINY`** | The existing `tests/fixtures/tiny.mcap` — framework-produced, every message sharing a `log_time_ns` per cycle. **The case that works today.** | codec, bus, runner |
| **`F-FOREIGN`** | A crafted recording in which **no two messages share a timestamp** and each carries its own `counter`, `t_source` and `status`. **The case that does not work today** (`SW-0049`) and the single most important fixture in this suite. | `UT-BUS-07`…`UT-BUS-13`, `ANL-SW-16` |
| **`F-LADDER`** | Five variants of `F-FOREIGN`: one per recovery-ladder rung — a source cycle id · counter only · source time only · reception time only — plus one whose source time is present but **not monotonic**, for the demotion case. | `UT-BUS-08`, `UT-BUS-09` |
| **`F-LONG`** | The same content at 1×, 5× and 20× duration, for streaming and memory claims. | `ANL-SW-12`, `UT-IO-05`, `UT-SES-*` |
| **`F-BULK`** | A recording carrying a large per-message payload (point cloud or image) beside small signals. | `UT-IO-06`, `UT-BUS-17`, `UT-SCN-*` |
| **`F-MULTI`** | Three sources with different time domains, one sharing a capture-group identity. | `UT-IO-15`…`UT-IO-17`, `UT-PRP-02` |
| **`F-DAMAGED`** | `F-FOREIGN` with a truncated tail, a counter gap and one bad checksum. | `UT-PRP-03`…`UT-PRP-06` |
| **`F-STUB`** | The existing `echo_stub` component: real generic ABI, no algorithm. **Lets the whole suite run with no compiled component present** (`SW-0378`). | host, runner, scheduler, `IT-*` |
| **`F-STUB2`** | A second stub at a different declared period, for base-grid, hold and age tests. | `UT-SCH-*`, `UT-BUS-14` |
| **`F-STUB-SLOW`** | A stub that sleeps past the per-cycle timeout on a nominated tick. | `UT-HOST-13`, `UT-ORC-12` |
| **`F-STUB-CRASH`** | A stub that segfaults on a nominated tick. | `UT-ORC-08`, `UT-EDG-08` |
| **`F-STUB-NOCLOCK`** | A stub that reads wall-clock time, for the negative case. | `UT-HOST-17` |
| **`F-CHAIN4`** | A four-stage graph — `vdy → perception → fusion → aeb` — with every mode combination reachable. Includes the concept's own broken case: **simulate → measured → measured → simulate**. | `UT-GRF-12`…`UT-GRF-22` |
| **`F-SPEC`** | A minimal valid Resolved Run Spec, plus one variant per §3.2 violation (a stem, a relative path, a missing policy, an address string). | `UT-SPC-*`, `ANL-SW-01` |
| **`F-CFGSET`** | A four-kind configuration set (composition, connections, source binding, layout) across all four merge layers, with includes and variables. | `UT-CFG-*` |
| **`F-MAP`** | An ingest map with units, array shape, header binding, an `absent:` block, and a second map claiming one of the same ports. | `UT-ING-*` |
| **`F-LIBDIR`** | A deployed library directory: binary + `config/` bundle + `sim/` plug-ins + `bundle.sha256`, with **no source checkout reachable**. | `IT-14`, `IT-15`, `IT-17`, `UT-RES-*` |
| **`F-RUNPAIR`** | Two completed runs of one spec, differing in exactly one manifest dimension, one pair per determinism axis. | `UT-DIA-08`…`UT-DIA-12` |
| **`F-INDEX`** | A hand-written `RecordingIndex` and `ModuleManifest` set — no file on disk, no library present. What lets the graph, coherence and ingest suites run with nothing to open. | `UT-GRF-*`, `UT-ING-*`, `UT-CFG-*` |
| **`F-PLANTED`** | Per `ANL-*` check, a copy of the tree with exactly one deliberate violation. **`TV-3`.** | every `ANL-*` |

---

## 2. `ANL-SW-nn` — analysis

The mechanised checks. These are the highest-leverage tests in the suite: each one turns a rule that would otherwise be reviewed into a rule that fails a build. **Every row ships its `F-PLANTED` variant** (`ANL-SW-64`).

| ID | Serves | What it scans | How it fails |
|---|---|---|---|
| `ANL-SW-01` | `SW-0001` | An emitted spec against the spec schema | Any field that is a reference, stem, relative path, applied default or expression |
| `ANL-SW-02` | `SW-0006`, `SW-0062` | `src/simcore/**`, `src/simengine/**` for `gcd`, `snap` and time-unit conversion | Any period arithmetic in the engine. `snap` must also return nothing in `adas_sim/graph/**` (`SW-0173`) |
| `ANL-SW-03` | `SW-0007` | `src/simcore/**`, `src/simengine/**` for dotted-address splitting and `self`/`source` prefixes | Any reference parser in the engine |
| `ANL-SW-04` | `SW-0011`, `SW-0032` | `src/simcore/**`, `src/simengine/**` for a YAML open and for an ingest-map parser | The engine reading a map file |
| `ANL-SW-05` | `SW-0013` | Call graph from every per-tick entry point | Any Python frame reachable per message |
| `ANL-SW-06` | `SW-0016`, `SW-0142` | Symbol dump of `simcore` and `simengine` | Any interpreter symbol |
| `ANL-SW-07` | `SW-0017`, `SW-0409` | **Symbols**, not imports: which C entry points each Python package reaches | A binding outside `pyapi/`, `transport/` and `resolve/`; or any initialise, execute, shutdown or step entry point reachable from the configuration layer |
| `ANL-SW-08` | `SW-0018`, `SW-0079`, `SW-0187`, `SW-0203` | The four capabilities by name across `src/simcore/**`, `src/simengine/**` | Any implementation of config parse, ingest parse, wiring validation or library search |
| `ANL-SW-09` | `SW-0019` | `prove_equal.py`'s report, plus coverage before/after each deletion | An unexplained failure, or coverage decreasing |
| `ANL-SW-10` | `SW-0020` | The **seven** named duplicated capabilities | Any with two implementations |
| `ANL-SW-11` | `SW-0021` | Diff of adding a format | A changed file outside the new codec and the registry |
| `ANL-SW-12` | `SW-0025` | Peak RSS over `F-LONG` at 1×/5×/20× | Variation above 20%, or a container sized by file message count |
| `ANL-SW-13` | `SW-0029` | Bytes read for a single-topic range query | Above the stated factor of that topic's own bytes |
| `ANL-SW-14` | `SW-0046` | Type scan of the engine's time-carrying members | Any floating-point time member |
| `ANL-SW-15` | `SW-0048` | `Origin` enum vs the published schema | Any difference in either direction |
| `ANL-SW-16` | `SW-0049` | `**` for timestamp-equality grouping; cycles over `F-FOREIGN` | The grep hitting, or a cycle carrying one port |
| `ANL-SW-17` | `SW-0061`, `SW-0109` | Per-cycle execution routes in the engine | A second stepping entry point or fast path |
| `ANL-SW-18` | `SW-0072` | Two runs of one spec; the order's inputs | Order differing, or depending on container/pointer/thread/filesystem order |
| `ANL-SW-19` | `SW-0075` | Payload access from any scheduler entry point | Any reachable payload read |
| `ANL-SW-20` | `SW-0080` | Symbol dump for component symbol names | Any beyond the fixed ABI set |
| `ANL-SW-21` | `SW-0082` | The ABI export set vs the header | A sixth export, or a drift from the published list |
| `ANL-SW-22` | `SW-0088` | The engine's conversion path | Any module name, or a per-module conversion source file |
| `ANL-SW-23` | `SW-0097` | `Verb` enum vs the published schema | Any difference in either direction |
| `ANL-SW-24` | `SW-0106`, `SW-0361` | All six closed vocabularies vs their schemas | Any difference in either direction. **SV-8** |
| `ANL-SW-25` | `SW-0118` | Writes to any reader from the runner | Any back edge from simulated output to input |
| `ANL-SW-26` | `SW-0120` | Bytes read for a slice vs for the whole file | Slice cost scaling with file length |
| `ANL-SW-27` | `SW-0121` | The four error kinds vs the schema, both languages | A fifth kind, or a shape difference |
| `ANL-SW-28` | `SW-0122` | `check_error_parity.py` over both taxonomies | Any enumeration or field difference. **The one permitted duplication, kept honest** |
| `ANL-SW-29` | `SW-0126` | Exit-code table, and imports of `contrib/check` | A code encoding a verdict, or an import from `src/` |
| `ANL-SW-30` | `SW-0127` | Emitted log events vs the published vocabulary | Any event outside it |
| `ANL-SW-31` | `SW-0141` | Non-comment line count of `simengine/main.cpp` | Above 100 (`CN-0389`'s review check, mechanised) |
| `ANL-SW-32` | `SW-0145` | Binary hash invoked by interactive, batch and CI paths | Any difference |
| `ANL-SW-33` | `SW-0146` | Link line and `stdin` reads in `simengine` | A GUI toolkit, or a prompt |
| `ANL-SW-34` | `SW-0164`, `SW-0411` | Imports of `io`/`ctypes` from `config/`, `graph/`, `ingest/`, `runspec/` | Any payload-opening import in those four. `resolve/` is excluded here and covered by `ANL-SW-07` instead, because its obligation is *not executing*, which a folder check states wrongly |
| `ANL-SW-35` | `SW-0167` | `graph/` for a hard-coded stage sequence | Any chain not built from manifests |
| `ANL-SW-36` | `SW-0202` | `ingest/**` for `eval`/`exec`/`lambda`/`compile` and operator tokens | Any, outside `units.py`'s factor and offset |
| `ANL-SW-37` | `SW-0212` | Call sites of `resolve_library` | More than one |
| `ANL-SW-38` | `SW-0214` | The three resolvers' return types and shared helper | Any not returning `Resolution[...]` through `order.py` |
| `ANL-SW-39` | `SW-0229` | Imports of every `cli/` module | Anything beyond `argparse` and `adas_sim.pyapi` |
| `ANL-SW-40` | `SW-0232` | `VERBS` length vs the published CLI reference | A verb in one and not the other |
| `ANL-SW-41` | `SW-0238`, `SW-0338` | Engine invocation sites across every face | More than one invocation shape |
| `ANL-SW-42` | `SW-0256` | Configuration schemas the batch face accepts | Any batch-only schema |
| `ANL-SW-43` | `SW-0272` | Estimate vs measured duration over a sample, against the factor declared from the first campaign | Outside the declared factor, or the factor claimed rather than measured |
| `ANL-SW-44` | `SW-0273` | Producers of an `Evidence` record | More than one |
| `ANL-SW-45` | `SW-0287` | Imports from `player/**` | Any of `io`, `resolve`, `transport` reached directly |
| `ANL-SW-46` | `SW-0302` | Provider imports and filesystem calls | A renderer, `cv2`, `matplotlib`, Qt, or disk access |
| `ANL-SW-47` | `SW-0303` | Imports from `scene/**` | Any of `render`, `player`, `io`, `session`. **`D-3`** |
| `ANL-SW-48` | `SW-0304` | Provider signatures for event callbacks | Any callback parameter |
| `ANL-SW-49` | `SW-0305` | Plug-in sources for spelled port addresses | Any literal address other than `self.<port>`/`source.<port>` |
| `ANL-SW-50` | `SW-0311` | Providers for history-dependent state | Any integration of a time-varying signal |
| `ANL-SW-51` | `SW-0317` | Colour literals across the tree | Any outside `render/theme.py` |
| `ANL-SW-52` | `SW-0323` | Frame time at the stated tick and layer count, against the seeded budget | Above the seeded budget, or re-seeded without the seeding run being marked |
| `ANL-SW-53` | `SW-0325`, `SW-0357` | `src/**` — which is `adas_sim/`, `simcore/` and `simengine/` together — for `aeb`/`bsd`/`lca`/`acc`/`ldw`/`lka` and the world-model client's name | Any hit. `tests/` deliberately out of scope (`R-SIM-1`) |
| `ANL-SW-54` | `SW-0326` | Toolkit imports under `player/panels/**` | Any Qt import below the shell |
| `ANL-SW-55` | `SW-0331` | The plot panel's address space | Any second addressing mechanism |
| `ANL-SW-56` | `SW-0340` | `SURFACE` vs the user documentation | An action in one and not the other |
| `ANL-SW-57` | `SW-0348` | The diff produced by each of the five declared common changes on a reference project | Any change touching a file outside its declared set, needing a rebuild, or needing a source edit |
| `ANL-SW-58` | `SW-0350` | Engine pointers and buffer maps outside `transport/` | Any. **The line concept §5.3 says must not be crossed** |
| `ANL-SW-59` | `SW-0354` | Imports from `transport/**` | Any from `io`, or any format name |
| `ANL-SW-60` | `SW-0362` | Package contents across two projects | Any difference |
| `ANL-SW-61` | `SW-0364` | `LoadLibrary`/`dlopen` calls and separator arithmetic | Any outside `dso.cpp` and `config/paths.py` |
| `ANL-SW-62` | `SW-0368` | Thread pools inside `simcore`, `--jobs` inside a run | Any intra-run parallelism |
| `ANL-SW-63` | `SW-0369` | Per-worker throughput, per-recording wall time and peak resident memory over the reference campaign | Below 10.4 recordings/hour per worker, above 5 min 46 s per recording, above 4 GB peak per worker, or the host not recorded beside the measurement |
| `ANL-SW-64` | `SW-0370` | Every `scripts/check_*.py` against its `F-PLANTED` variant | Any check that passes a planted violation. **`TV-3`** |
| `ANL-SW-65` | `SW-0371` | Every cited identifier vs the test sources | Any identifier not appearing in its test |
| `ANL-SW-66` | `SW-0372` | `SW → SYS` links | Any `SW` with no parent, except the five §32.3 records as known |
| `ANL-SW-67` | `SW-0373` | The document set for a stored status column | Any hand-maintained verification status |
| `ANL-SW-68` | `SW-0374` | Every `.cpp/.hpp/.h/.py` for the header block | Any missing or wrong `COMPONENT:` token |
| `ANL-SW-69` | `SW-0375` | One port's string in log, configuration and display | Any character difference |
| `ANL-SW-70` | `SW-0376` | CI history from the first increment | Any increment with no automated run |
| `ANL-SW-71` | `SW-0380` | Word count of the maintained document set | Reported per release, trended, not gated |
| `ANL-SW-72` | `SW-0383` | `io/codecs/**` for module names; manifests for codec names | Any hit either way |
| `ANL-SW-73` | `SW-0405` | Plug-in access to module memory | Any pointer read instead of a named subscription |
| `ANL-SW-74` | `SW-0408` | Every `SW` for a non-empty `Accept` and ≥1 test | Any with neither. **SV-1** |
| `ANL-SW-75` | `SW-0413` | Writers of the scheduler's simulation-time member | More than one, a public setter, or any assignment from a message timestamp |
| `ANL-SW-76` | `SW-0415` | Every artifact writer across `adas_sim/**`, `src/simcore/**`, against the artifact-kind declaration | A kind written that the declaration does not carry; or a scanned-writer count of zero reported as `PASSED` rather than `SKIPPED` |
| `ANL-SW-77` | `SW-0416` | The generated use-constraints statement against the declaration and the recorded limit entries, plus its content hash | A cited kind with no entry, a blank entry, or a hash mismatch showing the generated file was hand-edited |
| `ANL-SW-79` | `SW-0418` | `docs/v2/py/**` — the rollup against the plan's boxes, and a second regeneration against the first | A hand-edited mark that passes; a second `--write-status` that changes a byte; a `[~]` with no `closed by` that passes; an undecomposed requirement rendered *not started* rather than *unknowable* |
| `ANL-SW-78` | `SW-0417` | Each cited kind's named detecting check, resolved against the suite by `scripts/check_trace.py`'s resolver | An identifier resolving to no test, or a blank cell. `undetected` passes and is counted |

---

## 3. `IT-nn` — integration

Each crosses one named interface. The seam (`IF-09`) and the module ABI (`IF-01`) carry most of them, which is the decomposition working: those are the two places two items can disagree.

| ID | Serves | Interface | Fixture | Steps |
|---|---|---|---|---|
| `IT-01` | `SW-0002` | `IF-09` | `F-SPEC`, `F-STUB`, `F-TINY` | Emit a spec; **delete the configuration source tree**; run the engine with only spec, recording and binary present; compare port values against the run made with the tree present. **The test that proves the seam is closed.** |
| `IT-02` | `SW-0011` | `IF-09` | `F-MAP`, `F-FOREIGN` | Emit a spec from a map; run; confirm every translation applied came from the spec and no map file was opened. |
| `IT-03` | `SW-0013` | `IF-09` | `F-LONG`, `F-STUB` | Profile a representative run; inspect the per-message path for interpreter frames. Confirms `ANL-SW-05`; does not replace it. |
| `IT-04` | `SW-0019` | — | each retiring implementation's own corpus | Run the retiring tests against the survivor before deletion. **Is `WP-15a`, the gate in front of `WP-16`.** |
| `IT-05` | `SW-0077` | `IF-09` | `F-STUB`, `F-STUB2` | Run one spec on an idle and a loaded machine; diff port values. |
| `IT-06` | `SW-0086` | `IF-01` | `F-STUB`, `F-CHAIN4` | Wire `Init`/`Reset`/cycle-end as control ports in the same file and grammar as data; observe each transition at the module. |
| `IT-07` | `SW-0087` | `IF-01` | `F-LIBDIR` | `adasInit(NULL)`; confirm the bundle resolved module-relative; repeat with an explicit path and with a project mismatch. |
| `IT-08` | `SW-0107` | `IF-09` | `F-CHAIN4` | Declare an override pinning a port across the injection boundary; confirm it is refused without a waiver and takes the waiver path with one. |
| `IT-09` | `SW-0114` | `IF-09` | `F-CHAIN4`, `F-STUB` | Run with mixed record policies; confirm every declared port is present or explicitly `excluded`, answerable from the artifact alone. |
| `IT-10` | `SW-0131` | `IF-09` | `F-CHAIN4`, `F-STUB2` | Diff the engine's own graph-and-schedule dump against the configuration layer's prediction. **A disagreement is a defect in the seam.** |
| `IT-11` | `SW-0144` | `IF-09` | `F-SPEC`, `F-STUB` | Embed `simcore` from a test host that is **not** `simengine`; run to completion. |
| `IT-12` | `SW-0158` | `IF-13` | `F-CFGSET` | Run from a customer checkout with the package installed read-only. |
| `IT-13` | `SW-0162` | `IF-09` | `F-LIBDIR`, `F-STUB` | Change a calibration value in the bundle; re-run; **build nothing**; observe the changed result. |
| `IT-14` | `SW-0194` | `IF-05` | `F-LIBDIR` | Delete the source checkout; run; the map resolves from the deployed directory. |
| `IT-15` | `SW-0209` | `IF-08` | `F-LIBDIR` | Point the player at a folder of libraries; layers render with no `PYTHONPATH` and no sibling checkout. |
| `IT-16` | `SW-0216` | `IF-10` | `F-RUNPAIR` | Reproduce a run from its manifest alone; compare port values. |
| `IT-17` | `SW-0237` | `IF-10` | `F-LIBDIR` | Copy an artifact directory to a machine with no build and no compiler; open it. |
| `IT-18` | `SW-0240` | `IF-04` | `F-STUB` | Delete every generated binding; decode every port from the manifest's `FileDescriptorSet`. |
| `IT-19` | `SW-0298`, `SW-0352` | `IF-11` | `F-STUB`, `F-LONG` | Measure engine tick rate with no player, with one attaching mid-run, and after detach. |
| `IT-20` | `SW-0299` | `IF-11` | `F-LIBDIR` | Open a finished run with **no engine run**; every panel populates. |
| `IT-21` | `SW-0343` | `IF-16` | `F-CHAIN4` | Make a selection in the launcher, save, launch; confirm `launch()` was reached only through the written path, and the headless re-run is identical. |
| `IT-22` | `SW-0379` | — | `df` and `vdy` | A **second** component completes the published checklist unaided, with no SIM-team edit and no framework file changed. |

---

## 4. `INSP-SW-nn` — inspection

Used only where no execution is possible. Each names its checklist; *"inspected"* may never mean *"someone read it"*.

| ID | Serves | Checklist | Reviewer |
|---|---|---|---|
| `INSP-SW-01` | `SW-0126` | Every exit code, against the question *"could a reader take this as a functional verdict?"* | SIM team + one automation-framework owner |
| `INSP-SW-02` | `SW-0150` | The four file kinds' key sets, against the question *"would two teams change this file for unrelated reasons?"* | SIM team + one algorithm team |
| `INSP-SW-03` | `SW-0193` | The unit table, against the boundary in `SW-0202` — declarative correction versus computation | SIM team + one recording owner |
| `INSP-SW-04` | `SW-0230` | Each verb's scripted form against `DD-07`'s three statements | SIM team |
| `INSP-SW-05` | `SW-0276` | The evidence chain's terminus, against *"does any field answer why rather than where?"* | SIM team |
| `INSP-SW-06` | `SW-0311` | Each layer provider, against *"does this reconstruct, estimate, or integrate?"* | SIM team + the owning component team |
| `INSP-SW-07` | `SW-0358` | The four extension points and their conformance kits | SIM team |
| `INSP-SW-08` | `SW-0373` | The document set, against *"is verification status stored anywhere by hand?"* — **including this document** | SIM team |
| `INSP-SW-09` | `SW-0393` | The module ABI contract text, against *"is the clock prohibition stated where a module author reads it?"* | SIM team + one component team |
| `INSP-SW-10` | `SW-0399` | The format/content split: what ships in the package versus what lives in the customer repository | SIM team + one algorithm team |
| `INSP-SW-11` | `SW-0416` | Each recorded limit entry, against *"is this limit governed by a requirement or a test, or was it written for this document?"* | SIM team + quality/safety |

---

## 5. `UT-<item>-nn` — unit

Expected values are the served requirement's `Accept` clause (§0.1). Each row gives the fixture and the steps only.

### 5.1 `SI-01` `io` — `UT-IO-01` … `UT-IO-27`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-IO-01` | `SW-0021` | `F-TINY` | Implement a throwaway codec against `Reader`/`Writer`; count files changed outside it and the registry. |
| `UT-IO-02` | `SW-0022` | — | Register two codecs with different capabilities; query each without opening a file. |
| `UT-IO-03` | `SW-0023` | `F-TINY` | Open by extension; register a second codec for the same extension. |
| `UT-IO-04` | `SW-0024` | — | Register a `round_trip` codec with no writer; register a non-round-trip codec and `OpenRead` it. |
| `UT-IO-05` | `SW-0025` | `F-LONG` | Read to completion at 1×, 5×, 20×; sample peak resident bytes. |
| `UT-IO-06` | `SW-0026` | `F-BULK` | Drive each bound to fire alone; then present a single message larger than `max_bytes`. |
| `UT-IO-07` | `SW-0027` | `F-BULK` | Read a batch without touching payloads; count decodes. Then access one; count again. |
| `UT-IO-08` | `SW-0028` | `F-LONG` | Open twice; time and count bytes for each. Then alter the file's size and mtime and open again. |
| `UT-IO-09` | `SW-0029` | `F-MULTI` | Range-query one topic; count bytes read against that topic's own bytes in the range. |
| `UT-IO-10` | `SW-0030` | `F-LONG` | Seek to the midpoint; read one batch; read `IMP-0135`'s byte counter. |
| `UT-IO-11` | `SW-0031` | `F-MULTI` | Apply a `Selection` on each of source, instance, cycle and topic; enumerate what was delivered. |
| `UT-IO-12` | `SW-0032` | `F-FOREIGN`, `F-MAP` | Construct a `Translator` from a spec table; deliver a topic absent from the table. |
| `UT-IO-13` | `SW-0033` | `F-MAP` | Apply a factor and offset; re-read the same message; compare. |
| `UT-IO-14` | `SW-0034` | `F-MAP` | Declare a row whose `proto_type` differs from the message's. |
| `UT-IO-15` | `SW-0035` | `F-MULTI` | Merge under each of the four policies; enumerate the delivered sequence for each. |
| `UT-IO-16` | `SW-0036` | `F-MULTI` | Merge on capture basis, then on reception basis; read the basis back from the manifest. |
| `UT-IO-17` | `SW-0037` | `F-MULTI` | Force-align; inspect `restamped` on every message and on the export it produces. |
| `UT-IO-18` | `SW-0038` | `F-TINY` | Write each `MetaKind`; read them back; write an undeclared kind. |
| `UT-IO-19` | `SW-0039` | `F-FOREIGN` | Read a topic carrying no provenance block. |
| `UT-IO-20` | `SW-0040` | `F-TINY` | Write the same messages twice into two files; compare bytes. |
| `UT-IO-21` | `SW-0041` | `F-LONG` | Write a long run; sample resident bytes and the file's growth during it. |
| `UT-IO-22` | `SW-0042` | `F-TINY`, `F-STUB` | Produce a merged output; load it alone with no other input. |
| `UT-IO-23` | `SW-0381` | `F-TINY`, `F-FOREIGN` | Open one recording per shipped R1 reader. |
| `UT-IO-24` | `SW-0382` | `F-MULTI` | Open one recording per shipped R2 reader. |
| `UT-IO-25` | `SW-0384` | `F-TINY` | Export to each of the three R1 targets; re-open each. |
| `UT-IO-26` | `SW-0385` | `F-FOREIGN` | Export; inspect all eight header fields, including the `unknown` ones. |
| `UT-IO-27` | `SW-0386` | `F-CHAIN4` | Export a named port subset; attempt to load the export as a resim input. |

### 5.2 `SI-02` `bus` — `UT-BUS-01` … `UT-BUS-22`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-BUS-01` | `SW-0043` | `F-FOREIGN` | Enumerate every field of every port value on every path, and in an export and an evidence answer. |
| `UT-BUS-02` | `SW-0044` | `F-FOREIGN`, `F-TINY` | Read a message with a capture stamp and one without; attempt to construct a header defaulting capture to reception. |
| `UT-BUS-03` | `SW-0045` | `F-STUB2` | Hold a value across several ticks; read `age_ns()` at each; search the type for a stored age field. |
| `UT-BUS-04` | `SW-0046` | `F-CFGSET` | Declare a period in integer microseconds; then a fractional one. |
| `UT-BUS-05` | `SW-0047` | `F-FOREIGN` | Read a port whose status is absent; format it; attempt arithmetic on it. |
| `UT-BUS-06` | `SW-0048` | `F-CHAIN4` | Produce one value per origin tag; enumerate. |
| `UT-BUS-07` | `SW-0049` | `F-FOREIGN` | Reconstruct cycles; count ports per cycle and compare to the graph's expected input set. |
| `UT-BUS-08` | `SW-0050` | `F-LADDER` | Reconstruct each variant in turn; read `RungUsed` per port from the run manifest. |
| `UT-BUS-09` | `SW-0051` | `F-LADDER` | Force a port's rung down and read it back; then attempt to force it up. |
| `UT-BUS-10` | `SW-0052` | `F-LADDER` | Read `quality` from a port value, from its export and from its evidence answer. |
| `UT-BUS-11` | `SW-0053` | `F-DAMAGED` | Reconstruct across the counter gap; enumerate reported gaps and count produced cycles. |
| `UT-BUS-12` | `SW-0054` | `F-FOREIGN` | Deliver an unchanged freshness key twice; read `is_repeat`. |
| `UT-BUS-13` | `SW-0055` | `F-FOREIGN` | Run a port at a rate differing from its declared period; read the reported comparison. |
| `UT-BUS-14` | `SW-0056` | `F-STUB2` | Read a not-due producer's port at several ticks; inspect value, `updated` and age. |
| `UT-BUS-15` | `SW-0057` | `F-CHAIN4` | Build a stage's port set with its producer `simulate`, then `measured`, then `off`; compare the sets. |
| `UT-BUS-16` | `SW-0058` | `F-BULK` | Run past the buffer count; read reuse count and high-water bytes; read a view taken before reuse. |
| `UT-BUS-17` | `SW-0059` | `F-BULK` | Publish a bulk array; inspect what the port value carries and what the recording carries. |
| `UT-BUS-18` | `SW-0060` | `F-MAP` | Declare a `static` port; query its due-ness, hold state and age. |
| `UT-BUS-19` | `SW-0387` | `F-LADDER` | Deliver a port carrying both stamps; read which was used from the manifest. |
| `UT-BUS-20` | `SW-0388` | `F-SPEC` | Resolve a catalogue at load; then one whose version is out of range. |
| `UT-BUS-21` | `SW-0389` | `F-CHAIN4` | Move a port between two producers; re-open a recording and a plug-in made before the move. |
| `UT-BUS-22` | `SW-0390` | `F-SPEC` | Declare a project-namespaced port; then one colliding with a core port. |

### 5.3 `SI-03` `scheduler` — `UT-SCH-01` … `UT-SCH-14`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-SCH-01` | `SW-0061` | `F-STUB`, `F-STUB2` | Enumerate the functions that decide a module executes; confirm every suite test reaches the one. |
| `UT-SCH-02` | `SW-0064` | `F-STUB2` | Run 60 s on a 10 ms grid with a 30 ms module; compare fired ticks against the expected set; inspect for float or epsilon comparison. |
| `UT-SCH-03` | `SW-0065` | `F-FOREIGN`, `F-STUB` | Give a module a 20 ms input; deliver a repeat, then a fresh value. Repeat with a `periodic` module and no arrivals. |
| `UT-SCH-04` | `SW-0066` | `F-STUB2` | Run a stub whose internal gating has drifted from its declared period; read the finding from the run manifest. |
| `UT-SCH-05` | `SW-0067` | `F-SPEC` | Construct with a grid step below the floor, then with a tick count above the ceiling. |
| `UT-SCH-06` | `SW-0068` | `F-FOREIGN` | Exercise each of the five policies on one port; search the scheduler for a default policy table. |
| `UT-SCH-07` | `SW-0070` | `F-DAMAGED` | Exercise each of the four missing-data behaviours; count warnings emitted for a long gap. |
| `UT-SCH-08` | `SW-0071` | `F-MULTI` | Deliver out-of-order messages within the declared buffer depth, then beyond it. |
| `UT-SCH-09` | `SW-0072` | `F-CHAIN4` | Run one spec twice; compare the order; vary container insertion order between runs. |
| `UT-SCH-10` | `SW-0073` | `F-CHAIN4` | Declare an edge delay of zero, then one; observe which cycle's value the consumer receives. |
| `UT-SCH-11` | `SW-0076` | `F-CHAIN4`, `F-STUB2` | Read the schedule dump before tick 0; compare against what executed. |
| `UT-SCH-12` | `SW-0078` | `F-LONG` | Run a paced and an unpaced session over one spec; diff port values. |
| `UT-SCH-13` | `SW-0413` | `F-FOREIGN`, `F-STUB2` | Run over a recording whose message density varies; enumerate the simulation-time sequence and compare it against the arithmetic sequence the grid step defines. Repeat over `F-TINY`. |
| `UT-SCH-14` | `SW-0414` | `F-FOREIGN`, `F-STUB2` | Declare a period of 20 ms against a port recorded at 25 ms; enumerate the ticks the values were delivered on, and read both rates from the run manifest. |

### 5.4 `SI-04` `module_host` — `UT-HOST-01` … `UT-HOST-18`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-HOST-01` | `SW-0079` | `F-STUB` | Open by absolute path; then by a path that does not exist; read the message. |
| `UT-HOST-02` | `SW-0081` | `F-STUB` | Load a stub declaring an unsupported ABI version; count lifecycle entry points invoked; read both numbers from the message. |
| `UT-HOST-03` | `SW-0083` | `F-STUB` | Present a missing transitive dependency, a wrong architecture and a missing symbol, on both platforms. |
| `UT-HOST-04` | `SW-0084` | `F-STUB` | Drive the six phases; read the trace for each transition and its outcome. Then fail one transition. |
| `UT-HOST-05` | `SW-0085` | `F-STUB` | Reset and continue, then unload and reload; compare the traces. Then load a stub declaring no reset export. |
| `UT-HOST-06` | `SW-0089` | `F-STUB` | Present an undersized buffer once, then one still undersized after the grow; inspect for a retry loop. |
| `UT-HOST-07` | `SW-0090` | `F-STUB` | Read the port set from `adasManifest`; search the engine for a configuration file, naming convention or table supplying module properties. |
| `UT-HOST-08` | `SW-0091` | `F-STUB` | Load a manifest-less binary with and without the legacy marker; read the count of legacy modules in the run manifest. |
| `UT-HOST-09` | `SW-0092` | `F-STUB-SLOW` | Hang a module; confirm the abort occurs within the configured bound; read stage, tick and elapsed; confirm fail, crash and timeout stay distinct. |
| `UT-HOST-10` | `SW-0093` | `F-STUB-SLOW` | Attach a debugger; step through a cycle exceeding the bound; count configuration edits required. |
| `UT-HOST-11` | `SW-0094` | `F-STUB-CRASH` | Fail on a nominated tick; from the report alone, re-execute that cycle in a debugger without replaying the preceding ones. |
| `UT-HOST-12` | `SW-0095` | `F-STUB` | Attach a debugger to the engine; hit a breakpoint inside a loaded module, on both platforms. |
| `UT-HOST-13` | `SW-0096` | `F-STUB-CRASH` | Run with one stage isolated; crash that stage; read which stage crashed and which was isolated. |
| `UT-HOST-14` | `SW-0365` | `F-STUB` | Load a library built with a non-conforming floating-point flag set; read the warning and when it is emitted. |
| `UT-HOST-15` | `SW-0391` | `F-STUB` | Regenerate a manifest differing from the checked-in one; read the field-by-field report; inspect the checked-in file afterwards. |
| `UT-HOST-16` | `SW-0392` | `F-STUB` | Delete the generated shim and rebuild; compare bytes. Then hand-edit it and rebuild. |
| `UT-HOST-17` | `SW-0393` | `F-STUB-NOCLOCK` | Scan the loaded module's import table for clock symbols; read the manifest's declaration. |
| `UT-HOST-18` | `SW-0394` | `F-STUB` | Run an undeclared non-deterministic module on the fresh-process axis. Then declare it and read the mark in every artifact. |

### 5.5 `SI-05` `mutate` — `UT-MUT-01` … `UT-MUT-10`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-MUT-01` | `SW-0097` | `F-SPEC` | Apply each of the six verbs; then name a seventh in a configuration. |
| `UT-MUT-02` | `SW-0098` | `F-CHAIN4` | Apply every verb to a repeated field; count elements before and after each. |
| `UT-MUT-03` | `SW-0099` | `F-SPEC` | Address a port, a field path, `[i]` and `[*]`; then attempt a predicate. |
| `UT-MUT-04` | `SW-0100` | `F-CHAIN4` | `drop` an element of a `fixed_slots` port; read every index afterwards. |
| `UT-MUT-05` | `SW-0101` | `F-CHAIN4` | Apply each of the five faults; read the header field each acted on. |
| `UT-MUT-06` | `SW-0102` | `F-CHAIN4` | Apply three verbs to one value; count decode and encode calls. |
| `UT-MUT-07` | `SW-0103` | `F-CHAIN4` | Override a port; read its origin from the value, from the export and from the evidence answer. |
| `UT-MUT-08` | `SW-0104` | `F-FOREIGN` | Apply `delay` to a value with a capture stamp, then to one whose capture stamp is unknown. |
| `UT-MUT-09` | `SW-0105` | `F-SPEC` | Enumerate `Touches`; confirm no port outside it reaches `ApplyTo`. |
| `UT-MUT-10` | `SW-0108` | `F-SPEC` | Scope a fault to a window; observe the port inside, outside, and read the window from the manifest. |

### 5.6 `SI-06` `runner` — `UT-RUN-01` … `UT-RUN-10`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-RUN-01` | `SW-0109` | `F-STUB`, `F-SPEC` | Enumerate tick-advancing functions; confirm `Run` reaches the same body as `StepOnce`. |
| `UT-RUN-02` | `SW-0110` | `F-CHAIN4` | Set a stage `measured`; count library loads; compare its published ports against its declaration. |
| `UT-RUN-03` | `SW-0112` | `F-CHAIN4` | Set a stage `off`; enumerate its ports; compare the consumer's handling against a missing input. |
| `UT-RUN-04` | `SW-0113` | `F-CHAIN4` | Run a mixed-mode graph; read the injection-boundary event emitted before tick 0. |
| `UT-RUN-05` | `SW-0116` | `F-CHAIN4` | Command an actuation the recording does not contain; read the divergence tick; re-run and compare; find it in the manifest and on the timeline. |
| `UT-RUN-06` | `SW-0117` | `F-CHAIN4` | Continue past divergence and the grace window; read an arbitrary slice of the export and look for the flag. |
| `UT-RUN-07` | `SW-0119` | `F-STUB-CRASH` | Kill the process mid-run; read the checkpoint's last completed cycle; compare against the last cycle present in the output. |
| `UT-RUN-08` | `SW-0120` | `F-LONG` | Run a six-second slice of a twenty-minute recording; compare wall time and bytes read against the full run. |
| `UT-RUN-09` | `SW-0395` | — | **`DEF`** — deferred with its parent. No case is written; the identifier is reserved so its absence is a decision. |
| `UT-RUN-10` | `SW-0396` | `F-STUB` | Re-execute one cycle from a saved input snapshot; compare against the original cycle's outputs. |

### 5.7 `SI-07` `errors` — `UT-ERR-01` … `UT-ERR-08`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-ERR-01` | `SW-0121` | — | Raise each kind from both languages; compare the four fields. |
| `UT-ERR-02` | `SW-0123` | `F-CFGSET` | Trigger an authoring error; read `expected` and `found` as separate machine-readable fields. |
| `UT-ERR-03` | `SW-0124` | `F-CFGSET` | Misspell a port, a topic, a layer and a style token; read the suggestions. |
| `UT-ERR-04` | `SW-0125` | `F-SPEC` | Trigger each exit condition on both platforms; compare the emitted tables. |
| `UT-ERR-05` | `SW-0127` | `F-CHAIN4` | Collect every emitted log event over a full run; compare against the published vocabulary. |
| `UT-ERR-06` | `SW-0128` | `F-DAMAGED` | Run headless at each of the four thresholds; read the exit code and the manifest's record of the threshold in force. |
| `UT-ERR-07` | `SW-0129` | — | Emit diagnostics containing non-ASCII characters from every entry point, in a default shell on both platforms. |
| `UT-ERR-08` | `SW-0130` | `F-DAMAGED` | Run producing warnings of several classes; reconcile the end summary's counts against the structured log's. |

### 5.8 `SI-08` engine diagnostics — `UT-EDG-01` … `UT-EDG-09`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-EDG-01` | `SW-0132` | `F-CHAIN4`, `F-STUB2` | Enable the trace; count rows against stages × ticks, including not-due stages. |
| `UT-EDG-02` | `SW-0133` | `F-CHAIN4` | Run the same spec with the trace on and off; compare port values. |
| `UT-EDG-03` | `SW-0134` | `F-LONG` | Run; read wall, read, per-stage, cycles and bytes from the run manifest. |
| `UT-EDG-04` | `SW-0135` | `F-LONG` | Read a known byte range; compare the counter against the file offsets touched. |
| `UT-EDG-05` | `SW-0136` | `F-CHAIN4` | Run with timing collection on and off; compare port values. |
| `UT-EDG-06` | `SW-0137` | `F-STUB`, `F-STUB2` | Read id, version, ABI version, path and binary hash per loaded module. |
| `UT-EDG-07` | `SW-0138` | `F-CHAIN4` | Set each of the four break conditions; confirm each stops where declared. |
| `UT-EDG-08` | `SW-0139` | `F-STUB-CRASH` | Crash; open the reproducer directory; confirm spec, tick, snapshot and stderr are present. |
| `UT-EDG-09` | `SW-0140` | `F-DAMAGED` | Call every diagnostic entry point with a partially loaded engine; confirm each returns and none raises. |

### 5.9 `SI-09` `simengine` — `UT-EXE-01` … `UT-EXE-06`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-EXE-01` | `SW-0142` | `F-SPEC` | Run to completion with no interpreter installed; scan loaded modules. |
| `UT-EXE-02` | `SW-0143` | `F-SPEC` | Pass `--wait-for-debugger`; read the printed pid; attach; confirm no cycle ran before attach. |
| `UT-EXE-03` | `SW-0146` | `F-SPEC` | Run with no display and closed stdin; omit a required argument. |
| `UT-EXE-04` | `SW-0147` | `F-STUB-CRASH` | Run with `--restart` unset, then set; read the outcome recorded in each manifest. |
| `UT-EXE-05` | `SW-0148` | `F-SPEC` | Trigger each taxonomy kind; compare the process exit code on both platforms. |
| `UT-EXE-06` | `SW-0397` | — | Load the shipped launch configurations on both platforms; resolve a symbol in a loaded module. |

### 5.10 `SI-10` `config` — `UT-CFG-01` … `UT-CFG-18`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-CFG-01` | `SW-0069` | `F-CFGSET` | Declare `interpolate` on a continuous port, then on an enum port. |
| `UT-CFG-02` | `SW-0149` | `F-CFGSET` | Set one value in all four layers; read the resolved value and its recorded layer. |
| `UT-CFG-03` | `SW-0150` | `F-CFGSET` | Place a key of each kind in each of the other three files. |
| `UT-CFG-04` | `SW-0151` | `F-CFGSET` | Break each file kind's schema; read file, line, wrong value and allowed values. |
| `UT-CFG-05` | `SW-0152` | `F-CFGSET` | Add an unknown key; then one differing by one character from a real key. |
| `UT-CFG-06` | `SW-0153` | `F-CFGSET` | Omit the version in each file kind; then set one beyond the supported range. |
| `UT-CFG-07` | `SW-0154` | `F-CFGSET` | Break each class of reference; confirm the failure occurs at load, before any tick. |
| `UT-CFG-08` | `SW-0155` | `F-CFGSET` | Read each file and write it back unchanged; compare bytes, comments and key order. |
| `UT-CFG-09` | `SW-0156` | `F-CFGSET` | Express one configuration inline and via includes; compare resolved values. Then create an include cycle. |
| `UT-CFG-10` | `SW-0157` | `F-CFGSET` | Use a declared variable, then an undeclared one; read the reported resolutions. |
| `UT-CFG-11` | `SW-0159` | `F-LIBDIR` | Offer a runtime file and a simulation file to the bundle; read the refusal and the rule it quotes. |
| `UT-CFG-12` | `SW-0160` | `F-LIBDIR` | Present two components disagreeing on project, then on an ego parameter. |
| `UT-CFG-13` | `SW-0161` | `F-CFGSET` | Resolve geometry for two projects; then for a class with no measured footprint. |
| `UT-CFG-14` | `SW-0163` | `F-CFGSET` | Declare a period in integer microseconds; read it as `period_ns` in the emitted spec. |
| `UT-CFG-15` | `SW-0165` | `F-CFGSET` | Validate with every recording and binary removed. |
| `UT-CFG-16` | `SW-0166` | `F-CFGSET` | Run the dry run; read the source layer for every resolved value. |
| `UT-CFG-17` | `SW-0363` | `F-CFGSET` | Run one byte-identical configuration set on both platforms; compare results; read the per-platform binary from the manifest. |
| `UT-CFG-18` | `SW-0398` | `F-CFGSET` | Author a composition file naming another unit. |

### 5.11 `SI-11` `graph` — `UT-GRF-01` … `UT-GRF-27`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-GRF-01` | `SW-0063` | `F-CHAIN4` | Declare a period that is not an integer multiple of the derived step. |
| `UT-GRF-02` | `SW-0074` | `F-CHAIN4` | Create a cycle of zero-delay edges; then close the same loop with a one-step delay. |
| `UT-GRF-03` | `SW-0111` | `F-CHAIN4`, `F-TINY` | Set a stage `measured` whose outputs the recording does not carry. |
| `UT-GRF-04` | `SW-0115` | `F-CHAIN4` | Exclude, then decimate, a port a `simulate` stage consumes — at record time, then at resim time. |
| `UT-GRF-05` | `SW-0167` | `F-CHAIN4` | Build from manifests; add a stage by manifest alone; search for a hard-coded sequence. |
| `UT-GRF-06` | `SW-0168` | `F-CHAIN4` | Declare two active producers for one port. |
| `UT-GRF-07` | `SW-0169` | `F-CHAIN4` | Leave a required input unbound; read the producers and source topics listed as considered. |
| `UT-GRF-08` | `SW-0170` | `F-CHAIN4`, `F-MAP` | Mismatch types stage-to-stage, then recording-to-stage. |
| `UT-GRF-09` | `SW-0171` | `F-CHAIN4` | Wire a data port to a control port. |
| `UT-GRF-10` | `SW-0172` | `F-CHAIN4` | Derive the grid from 20 ms and 30 ms periods; then set `base_grid:` in a file. |
| `UT-GRF-11` | `SW-0173` | `F-CHAIN4` | Declare a 19.99 ms period beside a 20 ms one; then search the schema and the graph package for any tolerance key or rounding call. |
| `UT-GRF-12` | `SW-0174` | `F-CHAIN4` | **simulate → measured → measured → simulate**; enumerate stale stages and the path that made each stale. |
| `UT-GRF-13` | `SW-0175` | `F-CHAIN4` | The same graph; enumerate each stale stage's transitive simulate descendants. |
| `UT-GRF-14` | `SW-0176` | `F-CHAIN4` | Construct one graph per verdict; read the verdict returned for each. |
| `UT-GRF-15` | `SW-0177` | `F-CHAIN4` | Classify with no reader, loader or path supplied. |
| `UT-GRF-16` | `SW-0178` | `F-CHAIN4` | Attempt the broken run; read the named path and the landing consumer; confirm nothing executed. |
| `UT-GRF-17` | `SW-0179` | `F-CHAIN4` | Read the offered remedies and which is marked suggested; apply it and re-classify. |
| `UT-GRF-18` | `SW-0180` | `F-CHAIN4` | Waive with a reason; read the mark in manifest, export and banner. Then waive with an empty reason. |
| `UT-GRF-19` | `SW-0181` | `F-CHAIN4` | Forbid waivers by policy; attempt one; read the exit code. |
| `UT-GRF-20` | `SW-0182` | `F-CHAIN4` | Create two orphans; count warnings over the run; read the per-stage badge flag. |
| `UT-GRF-21` | `SW-0183` | `F-CHAIN4` | Toggle a mode with gap closing on, then off; read what changed and what was warned. |
| `UT-GRF-22` | `SW-0184` | `F-CHAIN4` | Toggle a mode; inspect the original object afterwards. |
| `UT-GRF-23` | `SW-0185` | `F-FOREIGN`, `F-CHAIN4` | Compute feasible cuts from the topic index with nothing executed. |
| `UT-GRF-24` | `SW-0186` | `F-FOREIGN` | Declare a trace catalogue that disagrees with the file; read both sides of the divergence. |
| `UT-GRF-25` | `SW-0400` | `F-CHAIN4` | Override mode on one output port; read it in the manifest and in the classification. |
| `UT-GRF-26` | `SW-0401` | `F-CHAIN4` | Instantiate one manifest twice with distinct instance names; enumerate the port space. |
| `UT-GRF-27` | `SW-0411` | `F-INDEX` | Run coherence, cut feasibility, `measured` validation and family matching against a **hand-written** index and manifest set, with no file on disk and no library present. |

### 5.12 `SI-12` `ingest` — `UT-ING-01` … `UT-ING-14`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-ING-01` | `SW-0187` | `F-MAP` | Onboard a family; count rebuilt artifacts and edited source modules; count parsers in the tree. |
| `UT-ING-02` | `SW-0188` | `F-MAP` | Declare every field of a binding; read each back in the emitted spec. |
| `UT-ING-03` | `SW-0189` | `F-MAP`, `F-FOREIGN` | Bind the three header channels; then omit them and read the reported ladder rung. |
| `UT-ING-04` | `SW-0190` | `F-MAP` | Declare an `absent:` port with a reason; read it at load and in the feasible-cut answer. |
| `UT-ING-05` | `SW-0191` | `F-MAP`, `F-MULTI` | Present two files matching different maps by declared rule. |
| `UT-ING-06` | `SW-0192` | `F-MAP` | Make two applicable maps claim one port. |
| `UT-ING-07` | `SW-0193` | `F-MAP` | Apply each unit from the closed table; then name a unit outside it. |
| `UT-ING-08` | `SW-0195` | `F-MAP` | Search the module for a callable, lambda or `eval`; confirm the output is data only. |
| `UT-ING-09` | `SW-0196` | `F-MULTI` | Present two sources of one family and model with different instance numbers; then an incomplete identity. |
| `UT-ING-10` | `SW-0197` | `F-MULTI` | Resolve descriptions with each tier available in turn; read the tier reported per source. |
| `UT-ING-11` | `SW-0198` | `F-MULTI` | Present a description version inside, then outside, its type's accepted set. |
| `UT-ING-12` | `SW-0199` | `F-MULTI` | Resolve static data present in the recording, then absent from it; read the choice reported. |
| `UT-ING-13` | `SW-0200` | `F-FOREIGN` | Record a decision about a recording; compare the recording's bytes and mtime before and after. |
| `UT-ING-14` | `SW-0201` | `F-MULTI` | Read the precedence from `explain`; place a sidecar at each tier and confirm the declared order holds. |

### 5.13 `SI-13` `resolve` — `UT-RES-01` … `UT-RES-11`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-RES-01` | `SW-0203` | `F-LIBDIR` | Resolve a stem on both platforms; count resolver implementations in the tree. |
| `UT-RES-02` | `SW-0204` | `F-LIBDIR` | Resolve with several candidates present; read every directory searched and every rejection with its reason. |
| `UT-RES-03` | `SW-0205` | `F-LIBDIR` | Query availability for a present and an absent module; count `dlopen` calls. |
| `UT-RES-04` | `SW-0206` | `F-LIBDIR` | Read the bundle and its `bundle.sha256`; count bundles per component per build. |
| `UT-RES-05` | `SW-0207` | `F-LIBDIR` | Resolve module-relative, then with an explicit path, then with a project mismatch. |
| `UT-RES-06` | `SW-0208` | `F-LIBDIR` | Resolve from a recording's embedded bundle, from `config/`, and from a checkout; read which was stated. |
| `UT-RES-07` | `SW-0210` | `F-LIBDIR` | Record a run with plug-ins; inspect the recording for plug-in code and for its hash and identity. |
| `UT-RES-08` | `SW-0211` | `F-LIBDIR` | Present a plug-in whose declared generation is unsupported; count imports performed. |
| `UT-RES-09` | `SW-0213` | `F-LIBDIR` | Resolve a locally built library whose hash matches no published build. |
| `UT-RES-10` | `SW-0409` | `F-LIBDIR`, `F-STUB` | Enumerate the C entry points each Python package reaches; then attempt an execute call from the configuration layer. |
| `UT-RES-11` | `SW-0410` | `F-FOREIGN`, `F-STUB` | Probe a recording and a module; compare the index against what a full read reports and the manifest against what the module host reads; then serialise both and check no handle survives. |

### 5.14 `SI-14` `runspec` — `UT-SPC-01` … `UT-SPC-24`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-SPC-01` | `SW-0001` | `F-CFGSET`, `F-SPEC` | Emit a spec; run the unresolved-construct checker over it; then emit from a configuration leaving a stem. |
| `UT-SPC-02` | `SW-0003` | `F-LIBDIR` | Emit; change the search path; run; compare the loaded path against the manifest's. |
| `UT-SPC-03` | `SW-0004` | `F-CFGSET` | Emit twice from identical inputs; then after a semantic change; then after reordering meaningless keys. |
| `UT-SPC-04` | `SW-0005` | `F-SPEC` | Load a spec one major ahead; then one with no version. |
| `UT-SPC-05` | `SW-0008` | `F-SPEC` | Emit an override and a fault; confirm the address is structured; find it in the run manifest. |
| `UT-SPC-06` | `SW-0009` | `F-CHAIN4` | Emit; confirm every declared port carries a policy; answer *was this complete?* from the artifact alone. |
| `UT-SPC-07` | `SW-0010` | `F-CHAIN4` | Emit; read sampling and missing-data per port; search the engine for a default table. |
| `UT-SPC-08` | `SW-0012` | `F-SPEC` | Emit two specs differing in one mode; diff; count changed lines. |
| `UT-SPC-09` | `SW-0215` | `F-CHAIN4` | Run each face; confirm each produces a machine-readable manifest. |
| `UT-SPC-10` | `SW-0217` | `F-CHAIN4` | Produce each artifact kind; read the embedded manifest from each. |
| `UT-SPC-11` | `SW-0218` | `F-RUNPAIR` | Read the five identity fields from two manifests; derive the axis they differ on. |
| `UT-SPC-12` | `SW-0219` | `F-SPEC` | Declare overrides and faults; enumerate them in the manifest with verb, address, operands and window. |
| `UT-SPC-13` | `SW-0220` | `F-FOREIGN` | Run where a field cannot be filled; read the manifest entry. |
| `UT-SPC-14` | `SW-0221` | `F-CFGSET` | Derive a run id twice from identical inputs; then after a change. |
| `UT-SPC-15` | `SW-0222` | `F-STUB-CRASH`, `F-STUB-SLOW` | Crash a run, then time one out; read the manifest written for each. |
| `UT-SPC-16` | `SW-0223` | `F-CHAIN4` | Run with zero exporters configured. |
| `UT-SPC-17` | `SW-0224` | `F-CHAIN4` | Run a waived-incoherent graph past a divergence; read both fields from the manifest. |
| `UT-SPC-18` | `SW-0225` | `F-LONG` | Read the pre-run estimate and its upper-bound label; compare against the measured rate mid-run. |
| `UT-SPC-19` | `SW-0226` | `F-RUNPAIR` | Read the tolerance hash; change one `why:`; re-read. |
| `UT-SPC-20` | `SW-0227` | `F-CHAIN4` | Interrupt the write; inspect the destination for a partial manifest. |
| `UT-SPC-21` | `SW-0228` | `F-CHAIN4` | Validate a manifest against its published schema; then one a major version ahead. |
| `UT-SPC-22` | `SW-0402` | `F-CHAIN4` | Run with a one-step edge delay; read the latency model from the manifest. |
| `UT-SPC-23` | `SW-0006` | `F-CHAIN4`, `F-STUB2` | Emit a spec; add a data-driven stage at a shorter period and re-emit; add a static port and re-emit. Compare the three grid steps. |
| `UT-SPC-24` | `SW-0412` | `F-SPEC`, `F-TINY` | Emit a spec; replace the named recording with a different file of the same name; load. Then re-emit against the replacement and load again. |

### 5.15 `SI-15` `orchestrate` — `UT-ORC-01` … `UT-ORC-27`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-ORC-01` | `SW-0229` | — | Inspect each `cli/` module's imports and its statement count. |
| `UT-ORC-02` | `SW-0233` | `F-CHAIN4` | Run `record`, `run` and `resim`; enumerate what each produced and what each executed. |
| `UT-ORC-03` | `SW-0234` | `F-CHAIN4` | Dry-run every verb; then add a verb with no dry-run callable and build the table. |
| `UT-ORC-04` | `SW-0235` | `F-LONG` | Start a long run; observe progress; cancel; read the state left behind. |
| `UT-ORC-05` | `SW-0236` | `F-CHAIN4` | Run; enumerate the per-run directory's contents. |
| `UT-ORC-06` | `SW-0238` | `F-CHAIN4` | Invoke from Bench, `run`, `resim` and a batch worker; compare the invocation made. |
| `UT-ORC-07` | `SW-0241` | `F-STUB-CRASH` | Run a batch; inspect for threads; crash one entry. |
| `UT-ORC-08` | `SW-0242` | `F-STUB-CRASH`, `F-STUB-SLOW` | Produce one of each outcome in one batch; read the four reported distinctly. |
| `UT-ORC-09` | `SW-0243` | `F-STUB-CRASH` | Fail one entry of five; count entries completed. Repeat with `--fail-fast`. |
| `UT-ORC-10` | `SW-0244` | `F-CHAIN4` | Run a batch; rebuild the aggregate from the per-run manifests; compare. |
| `UT-ORC-11` | `SW-0245` | `F-STUB-CRASH` | Crash an entry; open the crash record on Bench; confirm it reaches the failing tick in process. |
| `UT-ORC-12` | `SW-0246` | `F-STUB-SLOW` | Exceed the processing threshold; read the interval, threshold and units reported. |
| `UT-ORC-13` | `SW-0247` | `F-STUB-SLOW` | Wedge a run without exceeding processing time; confirm the second monitor fires and the first does not. |
| `UT-ORC-14` | `SW-0248` | `F-LONG` | Breach the memory cap, then the wall-time cap; read each reported as its own reason. |
| `UT-ORC-15` | `SW-0249` | `F-CHAIN4` | Kill the parent mid-batch; resume; count entries re-executed. |
| `UT-ORC-16` | `SW-0250` | `F-CHAIN4` | Sweep one parameter; diff two entries' specs. |
| `UT-ORC-17` | `SW-0251` | `F-STUB` | Run each reset mode against each reset timing; read both from the manifest. |
| `UT-ORC-18` | `SW-0252` | `F-DAMAGED` | Exercise each of the four read-error behaviours; count skipped packages and read the run's flag. |
| `UT-ORC-19` | `SW-0253` | `F-DAMAGED` | Trigger retries up to the bound, then past it; read every retry from the manifest. |
| `UT-ORC-20` | `SW-0254` | `F-LONG` | Run a batch over one recording set; count sidecar index builds and writers. |
| `UT-ORC-21` | `SW-0255` | `F-STUB-CRASH` | Run the same spec on Bench, in batch, and with one stage isolated; observe where the crash lands. |
| `UT-ORC-22` | `SW-0256` | `F-CHAIN4` | Feed the developer's run configuration to the batch face; count configuration schemas involved. |
| `UT-ORC-23` | `SW-0366` | `F-CHAIN4` | Run the suite on both platforms; introduce a deliberate cross-platform difference. |
| `UT-ORC-24` | `SW-0367` | — | Submit a measurement with no platform attribution to the reporting tooling. |
| `UT-ORC-25` | `SW-0368` | `F-LONG` | Run one entry on a one-core and a many-core machine; compare port values and their order. |
| `UT-ORC-26` | `SW-0377` | — | Run the shipped self-test on a clean machine with no project, no component library and no recording of the user's own. |
| `UT-ORC-27` | `SW-0378` | `F-STUB` | Run the full suite on a machine with no component library installed. |

### 5.16 `SI-16` `prep` — `UT-PRP-01` … `UT-PRP-14`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-PRP-01` | `SW-0257` | `F-FOREIGN` | Hash a recording twice; then after a one-byte change; read the identity used in a run manifest. |
| `UT-PRP-02` | `SW-0258` | `F-MULTI` | Read all three identities; group two files captured simultaneously by different units. |
| `UT-PRP-03` | `SW-0259` | `F-DAMAGED` | Run all four check classes; read each result separately. |
| `UT-PRP-04` | `SW-0260` | `F-DAMAGED` | Use the result as a gate; read the exit code; attempt to simulate the refused recording. |
| `UT-PRP-05` | `SW-0261` | `F-DAMAGED` | Read the declared cost before opting in; then verify and read the bad checksum. |
| `UT-PRP-06` | `SW-0262` | `F-DAMAGED` | Open without recovery, then recover explicitly; read the mark and dropped range in every derived artifact. |
| `UT-PRP-07` | `SW-0263` | `F-FOREIGN` | Extract by time range and port; load the extract as a simulation input. |
| `UT-PRP-08` | `SW-0264` | `F-FOREIGN` | Extract N sections; read the names against the declared rule; then extract the complement. |
| `UT-PRP-09` | `SW-0265` | `F-TINY` | Convert between two capable formats; then request a pair the capability table forbids. |
| `UT-PRP-10` | `SW-0266` | `F-FOREIGN` | Inspect; compare the reported ports, rates and range against what a run actually reads. |
| `UT-PRP-11` | `SW-0267` | `F-FOREIGN` | Derive twice in sequence; read both steps from the lineage. |
| `UT-PRP-12` | `SW-0268` | `F-FOREIGN` | Run every prep verb with no module installed; inspect `prep`'s imports. |
| `UT-PRP-13` | `SW-0269` | `F-BULK` | Measure per-cycle bytes per port; compare against the trace catalogue's declared budget. |
| `UT-PRP-14` | `SW-0270` | `F-FOREIGN` | Run every prep verb; compare the input's bytes and mtime before and after. |

### 5.17 `SI-17` `diagnostics` — `UT-DIA-01` … `UT-DIA-15`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-DIA-01` | `SW-0271` | `F-CHAIN4` | Run the dry run; enumerate what it reported; count ticks executed and libraries loaded. |
| `UT-DIA-02` `⊘` | `SW-0273` | `F-CHAIN4` | Format a sampled set of addresses through both formatters; compare field for field; search for a second code path producing an evidence answer. |
| `UT-DIA-03` | `SW-0274` | `F-LADDER` | Ask for evidence where several fields are unfillable; inspect each for `unknown` versus a plausible default. |
| `UT-DIA-04` | `SW-0275` | `F-CHAIN4` | Run with evidence enabled and disabled; compare port values and per-tick cost against measurement noise. |
| `UT-DIA-05` | `SW-0277` | — | Run the environment report against a missing library, a corrupt bundle, an unreadable recording and an incompatible plug-in. |
| `UT-DIA-06` | `SW-0278` | `F-CHAIN4` | Misspell a name of each kind; read the suggestion and the set searched. |
| `UT-DIA-07` | `SW-0279` | `F-STUB` | Probe a module the framework has never seen; compare the listed ports against `adasManifest`; count framework files edited. |
| `UT-DIA-08` | `SW-0280` | `F-RUNPAIR` | Compare two runs differing at one tick; inspect the result for a bare pass or fail. |
| `UT-DIA-09` | `SW-0281` | `F-RUNPAIR` | Derive the axis from a pair differing in one dimension, then from one differing in host and build; search for a caller-supplied axis flag. |
| `UT-DIA-10` | `SW-0282` | `F-RUNPAIR` | Compare two recordings of one deterministic run differing in run identifier and timestamp. |
| `UT-DIA-11` | `SW-0283` | `F-RUNPAIR` | Search the same-process and fresh-process axes for a tolerance field; read a passing report on the other two for tolerance and headroom. |
| `UT-DIA-12` | `SW-0284` | `F-RUNPAIR` | Declare a tolerance row with no `why:`; then a tolerance on an integer field. |
| `UT-DIA-13` | `SW-0285` | `F-CHAIN4` | Name an internal port as a tap; read it in the output with its provenance; remove the tap and compare the run byte for byte. |
| `UT-DIA-14` | `SW-0286` | `F-CHAIN4` | Call each diagnostic from a script; consume its structured result without parsing text. |
| `UT-DIA-15` | `SW-0403` | `F-CHAIN4` | Ask the provenance question from a script and from the command line; compare field for field; search for a third derivation. |

### 5.18 `SI-18` `session` — `UT-SES-01` … `UT-SES-12`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-SES-01` | `SW-0288` | `F-LONG` | Advance the head; step backwards repeatedly; count module invocations from the cycle trace. |
| `UT-SES-02` | `SW-0289` | `F-LONG` | From behind the head, attempt every input sequence that could resume forward; enumerate the outcomes reachable. |
| `UT-SES-03` | `SW-0290` | `F-BULK` | Construct a session over a thousand-tick recording; count decodes. Read one port at one tick; count again. |
| `UT-SES-04` | `SW-0291` | `F-BULK` | Fill the cache with scenes of widely differing sizes; read the eviction basis; attempt to bound by count alone. |
| `UT-SES-05` | `SW-0292` | `F-LONG` | Run to the end sampling memory against tick count. Then retain a window beyond its bound. |
| `UT-SES-06` | `SW-0293` | `F-FOREIGN`, `F-MULTI` | Exercise each of the five granularities; confirm each lands on its stated boundary and that the cycle granularity lands on a complete input set. |
| `UT-SES-07` | `SW-0294` | `F-LONG` | Advance 200; cancel mid-job; read the resulting tick and confirm it is not mid-tick. |
| `UT-SES-08` | `SW-0295` | `F-LONG` | Mark a section; read its exact boundary ticks; replay headlessly from the written configuration and compare the range covered. |
| `UT-SES-09` | `SW-0296` | `F-CHAIN4` | Load a run with markers, a divergence and a waiver; click each and read the tick landed on. |
| `UT-SES-10` | `SW-0297` | `F-LONG` | Switch between formats; compare the stored value; recover the internal value from each format. |
| `UT-SES-11` | `SW-0300` | `F-LONG` | Construct a session over recordings of 1×, 5× and 20× duration; sample construction memory. |
| `UT-SES-12` | `SW-0404` | `F-LONG` | Exercise every transport control; compare the tick landed on against the tick intended. |

### 5.19 `SI-19` `scene` — `UT-SCN-01` … `UT-SCN-15`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-SCN-01` | `SW-0301` | `F-CHAIN4` | Build a scene; inspect each prim's units, frame and style; attempt to construct one with a colour. |
| `UT-SCN-02` | `SW-0302` | — | Import each provider; inspect its imports and its filesystem access. |
| `UT-SCN-03` | `SW-0304` | `F-CHAIN4` | Inspect every layer for a registered callback; render twice with identical inputs and compare. |
| `UT-SCN-04` | `SW-0305` | `F-CHAIN4` | Declare a reference resolving against no manifest; read the plug-in, the requested port and every port the manifest declares. |
| `UT-SCN-05` | `SW-0306` | `F-CHAIN4` | Declare a zero-match `requires=`; read the placeholder's name and primitive count. Then declare an ambiguous match. |
| `UT-SCN-06` | `SW-0307` | `F-LIBDIR` | Register two plug-ins using one short name; search for a central registry. Then register outside the declared namespace. |
| `UT-SCN-07` | `SW-0308` | `F-LIBDIR` | Add a provider by import alone; search for a provider roster. |
| `UT-SCN-08` | `SW-0309` | `F-BULK` | Exceed the per-layer byte budget; read whether the error names the layer or the primitive. |
| `UT-SCN-09` | `SW-0310` | `F-CHAIN4` | Build a layer containing one reconstructed primitive; read the layer's flag. Then construct a layer whose flags disagree. |
| `UT-SCN-10` | `SW-0312` | — | Serialise a scene; load it back; load one a minor version ahead; load one a major version ahead. |
| `UT-SCN-11` | `SW-0313` | `F-CHAIN4` | Resolve every token in every theme; then render an unknown token and read the token and table named. |
| `UT-SCN-12` | `SW-0314` | `F-CHAIN4` | Emit a prim with no frame, then in a declared frame, then in an undeclared one. |
| `UT-SCN-13` | `SW-0315` | `F-FOREIGN` | Render a recording from an unknown component; enumerate the default layer set for component names. |
| `UT-SCN-14` | `SW-0316` | `F-LIBDIR` | Open with a component default layout and no user layout; then with a user layout; then reset. |
| `UT-SCN-15` | `SW-0405` | `F-CHAIN4` | Render one layer over simulated and over replayed data; search the plug-in for a branch on origin. |

### 5.20 `SI-20` `render` — `UT-RND-01` … `UT-RND-06`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-RND-01` | `SW-0318` | — | Run the palette validator as a command against a passing and a deliberately failing palette; read the exit code. |
| `UT-RND-02` | `SW-0319` | `F-CHAIN4` | Produce a raster in a container with no display and no toolkit; inspect which layer imports the toolkit. |
| `UT-RND-03` | `SW-0320` | `F-CHAIN4` | Regenerate a document figure from a recording; compare against the live rendering within the declared tolerance. |
| `UT-RND-04` | `SW-0321` | `F-CHAIN4` | Interrupt a snapshot mid-write; inspect the destination. Then snapshot one cycle twice and compare hashes. |
| `UT-RND-05` | `SW-0322` | `F-CHAIN4` | Render one scene on both surfaces; enumerate which of them produces geometry. |
| `UT-RND-06` `⊘` | `SW-0324` | `F-BULK` | Seek past a thousand frames; count decodes against frames rendered; compare bytes crossing the engine boundary with context data on and off. |

### 5.21 `SI-21` `player` — `UT-PLR-01` … `UT-PLR-15`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-PLR-01` | `SW-0325` | — | Grep `src/**` — `adas_sim/`, `simcore/` and `simengine/` — for the six function tokens. |
| `UT-PLR-02` | `SW-0326` | `F-CHAIN4` | Construct and drive every panel with no window and no toolkit imported. |
| `UT-PLR-03` | `SW-0327` | `F-CHAIN4` | Toggle a layer; count SUT executions and scene rebuilds. |
| `UT-PLR-04` | `SW-0328` | `F-CHAIN4` | Change layout interactively; save; diff the file; reload. |
| `UT-PLR-05` | `SW-0329` | `F-CHAIN4` | Set a parameter globally, then scoped to one view-and-layer pair; read each back per view. |
| `UT-PLR-06` | `SW-0330` | `F-CHAIN4` | Place two input-listening layers in one view; declare the capability per layer; deliver one click. |
| `UT-PLR-07` | `SW-0331` | `F-CHAIN4` | Address a plot by port; compare its addressing against the other panels'. |
| `UT-PLR-08` | `SW-0332` | `F-CHAIN4` | Read one value's evidence from the panel and from `sim explain`; compare field by field. |
| `UT-PLR-09` | `SW-0333` | `F-CHAIN4` | Select a prim, a layer and a plotted sample; count actions to reach evidence for each. |
| `UT-PLR-10` | `SW-0334` | `F-FOREIGN` | Open a recording supporting some cuts; enumerate which stages offer `measured`. |
| `UT-PLR-11` | `SW-0335` | `F-CHAIN4` | Run overridden, incoherent, bundle-missing and restamped; read the badge for each. |
| `UT-PLR-12` | `SW-0336` | `F-LIBDIR` | Open a recording whose plug-in bundle is absent; read the named layers and expected hashes. |
| `UT-PLR-13` | `SW-0337` | — | Reach every published action through the command palette by search. |
| `UT-PLR-14` | `SW-0338` | `F-CHAIN4` | Switch between workspaces; count windows, engines and pipeline schemas involved. |
| `UT-PLR-15` | `SW-0339` | `F-CHAIN4` | Reach from the console a capability the interface does not expose; count statements and windows left. |

### 5.22 `SI-22` `launcher` — `UT-LNC-01` … `UT-LNC-07`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-LNC-01` | `SW-0341` | `F-CHAIN4` | Set mode and implementation per module; set a module `measured`; read whether its implementation survived. |
| `UT-LNC-02` | `SW-0342` | `F-CHAIN4` | Make a selection producing each verdict; read what the Launch control does for each. |
| `UT-LNC-03` | `SW-0344` | `F-LIBDIR` | Remove one platform's binary; read what is shown before launch; count load attempts. |
| `UT-LNC-04` | `SW-0345` | `F-FOREIGN`, `F-TINY` | Add two recordings with different feasible cuts; read what is offered per recording. |
| `UT-LNC-05` | `SW-0346` | `F-CHAIN4` | Add recordings, choose a layout, set modes, save and launch; count screens and actions. |
| `UT-LNC-06` | `SW-0347` | `F-CFGSET` | Write a configuration from the launcher; validate it with the same loader `sim run` uses. |
| `UT-LNC-07` | `SW-0348` | `F-CFGSET` | Make each declared common change; assert the diff touches exactly its declared file set with no rebuild and no source edit. Record the elapsed time as an observation, not a bound (`OQ-16`). |

### 5.23 `SI-23` `pyapi` — `UT-API-01` … `UT-API-05`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-API-01` | `SW-0014` | `F-BULK` | Read a bulk port into Python; count per-element allocations; compare the view's base pointer against the engine arena. |
| `UT-API-02` | `SW-0015` | `F-BULK` | Hold a view across a tick that reuses its buffer; read it. |
| `UT-API-03` | `SW-0230` | `F-CHAIN4` | Reach every capability from a script; count statements per verb. |
| `UT-API-04` | `SW-0231` | `F-CHAIN4` | Run each verb from the CLI and from a script; diff the artifact directories. |
| `UT-API-05` | `SW-0239` | — | Read the scripting version; confirm it moves independently of the module ABI and plug-in generation. |

### 5.24 `SI-24` `plugins` — `UT-PLG-01` … `UT-PLG-06`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-PLG-01` | `SW-0357` | — | Run the framework-source name check on a clean tree, then on its `F-PLANTED` variant. |
| `UT-PLG-02` | `SW-0358` | — | Exercise each of the four points through its shipped template plug-in and conformance kit; attempt to add a fifth. |
| `UT-PLG-03` | `SW-0359` | `F-LIBDIR` | Add one plug-in of each kind by registration alone; search for a plug-in roster. |
| `UT-PLG-04` | `SW-0360` | — | Bump each contract independently; read the generated matrix; load a combination outside it. |
| `UT-PLG-05` | `SW-0406` | — | Pin a version range; run inside it, then outside it. |
| `UT-PLG-06` | `SW-0407` | `F-CFGSET` | Apply a breaking change; run the shipped migration; validate the migrated configuration. |

### 5.25 `SI-25` `transport` — `UT-TRN-01` … `UT-TRN-05`

| ID | Serves | Fixture | Steps |
|---|---|---|---|
| `UT-TRN-01` | `SW-0349` | `F-STUB` | Drive one consumer over the in-process transport, then over shared memory; diff the consumer's source. |
| `UT-TRN-02` | `SW-0351` | `F-BULK` | Read a bulk port and a control message; observe which channel each used and whether the bulk read copied. |
| `UT-TRN-03` | `SW-0353` | `F-LONG` | Attach a deliberately slow reader; sample engine tick rate; read the reported drop count. |
| `UT-TRN-04` | `SW-0355` | `F-STUB` | Attach with matching versions, then with a mismatch. |
| `UT-TRN-05` | `SW-0356` | `F-STUB-CRASH` | Kill the engine with a player attached; observe what the player reports and how long it waits. |

---

## 6. What this document does not contain

| Not here | Where | Why |
|---|---|---|
| Expected values | The `Accept` clause of each `SW` | §0.1 — a second copy would drift |
| System tests (`SYT-*`) and end-to-end tests (`E2E-*`) | The System Test Specification | Deliberately the next pass |
| User-experience requirements and their tests | The Concept document | Deliberately the next pass |
| Test code | `tests/` | An identifier here appears verbatim there (`ANL-SW-65`) |
| Pass/fail records | The suite's output | `SW-0373` — status is derived, never stored |
