# VANTAGE — migration register

**A supporting document** (`R-REQ-17`, kind `register`, to be declared under
`context:` in `layers.yaml` by step 8). It records what becomes of the sim code
and of every sim v2 requirement row when Vantage replaces `sim`. It allocates no
UID and defines no requirement row. Nothing here is an obligation: the
obligations of Vantage are written in step 8.

Cited as `ARCH §n`: section n of `VANTAGE_Architecture.md` (frozen, 6a).
Decisions are cited as `D<n>` (`VANTAGE_DEV_PLAN.md` §2). Contract rows are cited
as `RCT:SYS-nnnn` and `RCT:IMP-nnnn`.

## 1. In plain words

Vantage is built from the sim code, not beside it (`D2`). So two questions have
to be answered before any new requirement is written:

1. **What happens to each piece of sim code?** Section 3 answers it, one row per
   directory or file, in four words: reused, corrected, replaced, retired.
2. **What happens to each sim v2 requirement row?** Section 4 answers it, one row
   per requirement row, in four words: carried, moved, superseded, retired
   (`D15`). A row that is carried is written again in the Vantage set (step 8);
   the others are not.

The register is read top to bottom: the words (section 2), the code (section 3),
the requirement rows (section 4), then how to check it (section 5). A reader who
only wants to know "is this sim feature kept?" looks up its code in section 3,
then its row in section 4.

Parts 6c, 6d and 6e of the writing order (`VANTAGE_DEV_PLAN.md` §6) fill the
tables of section 4. Part 1 (this file as first written) fills sections 1 to 3 and
leaves the tables of section 4 empty.

## 2. The words

Both lists are closed: a word that is not here is a finding.

### 2.1 Requirement rows

| Word | Meaning | Target |
|---|---|---|
| `carried` | the obligation stays in Vantage; a row of the Vantage set (step 8) will hold it | `VNT`, or a `VNT:` UID once step 8 allocates one |
| `moved` | the obligation now lives in the contract | one or more `RCT:SYS-nnnn` or `RCT:IMP-nnnn`, comma-separated; each must exist |
| `superseded` | a decision or the frozen architecture replaced it | `D<n>` (a decision of the plan) or `ARCH §n` (a section of the architecture), comma-separated |
| `retired` | no longer needed | the dash; the Why is never empty |

A row table has the columns `UID`, `Disposition`, `Target`, `Why`, and nothing
else. A UID is qualified by its set, because the two sets reuse numbers:
`SIM:CN-0001`, `SIM:SYS-0001`, `SIM:SW-0001`, `SIM:IMP-0001`, `PARITY:STK-0001`,
`PARITY:SYS-0001`, `PARITY:SW-0001`, `PARITY:IMP-0001`.

**The universe** is every live requirement row of the two sets. A UID that a sim
v2 document lists as retired is not in it: such a row already has a disposition
in its own document (for example the retired-UID tables of
`SIM_System_Requirements_v0.1.md` and the concept's superseded list in §0.4).
Tests (`CT`, `SYT`, `UT` and the rest) are not listed: a test follows its
requirement.

**A section row** disposes a whole section at once (`D15`). Its UID cell holds
one or more comma-separated terms, at least one a range such as
`SIM:SYS-0040..0063` (same set and kind at both ends, low not above high); the
other terms may be single UIDs. It stands for every live row of that one kind
that lies in one sim v2 section: the section is the nearest heading above the
row in its source document, a numbered section (`§13`) includes its
subsections (`§13.1`), and an unnumbered heading holds the rows directly under
it. The Why starts with the section's label and ` — `, then the reason; the
Disposition and Target follow the ordinary rules for the word. `IMP` rows are
never named in a section row; they inherit. The script expands the row, so each
row it covers is disposed once like a listed row, and a section row that does not
cover exactly one whole section is `C-RANGE`. Example line:
`| SIM:SYS-0040..0063 | superseded | ARCH §2.3 | §13 — run configuration is the run setup now |`.

**An implementation row (`IMP`, either set) inherits.** It is not listed when
every `SW` row it serves has the same word; it takes that word. It must be listed
when its `SW` rows disagree. Listing an `IMP` row whose `SW` rows agree is a
finding, because one fact belongs in one place (`D15`). The `IMP` rows of a
section are the ones that serve the `SW` rows of that section.

### 2.2 Code

| Word | Meaning | Target |
|---|---|---|
| `reused` | kept as it is, inside a Vantage part | the part, as `ARCH §3.n` (or the section that names it) |
| `corrected` | kept and changed | the part and what changes, citing `ARCH §n` |
| `replaced` | a new file takes its place | the new file in backticks, as `ARCH §11` names it, and the section |
| `retired` | no longer needed | the dash; the Why is never empty |

A code table has the columns `Path`, `Disposition`, `Target`, `Why`. Paths are
relative to `modules/vantage`; a directory ends in `/`. A row for a directory
covers everything under it unless a deeper row overrides it. New Vantage files
with no sim origin are not listed: `ARCH §11` already names them.

## 3. Sim code

The code universe is the tree at the tag `seed-from-sim`; a file added since is new and is not listed.
Every entry directly under `src/simcore/`, `src/simengine/`, `src/adas_sim/` and
`include/simcore/` (directories and files), and every file directly under
`scripts/`, is covered by exactly one row. `__pycache__` is not code. Deeper rows
appear only where a part differs from its directory.

Where `ARCH §11` names a file `(E)`, the row is `reused` or `corrected`. Where
`ARCH §11` calls a Python path legacy and gives it no part, the row is `retired`
or `replaced`. For the rest, `ARCH §11`'s last paragraph decides by one test:
Python that only authors or starts files and processes, or reads a recording or a
run setup, stays; Python that executes components, holds a `Session` or draws for
a viewer (`D13`) does not. Build and gate scripts sit outside the parts and follow
the standard recipe (`ARCH §11`).

| Path | Disposition | Target | Why |
|---|---|---|---|
| `include/simcore/abi/` | corrected | Resim engine, ARCH §11: `simcore.h` gains `simEngineSeek`, ABI version 3; `module_abi.h` is unchanged | the engine ABI keeps its shape and gains the jump |
| `include/simcore/bus.hpp` | corrected | Sample buffers, ARCH §3.4: `PortBus` holds one buffer per port | inputs are found by number, not by newest |
| `include/simcore/CMakeLists.txt` | corrected | Resim engine, ARCH §11 | the header list gains `orchestrator.hpp` |
| `include/simcore/diagnostics.hpp` | corrected | Diagnostics, ARCH §7: keyed by step number | the tick is retired |
| `include/simcore/errors.hpp` | reused | Resim engine, ARCH §11 | the closed error set is unchanged |
| `include/simcore/events.hpp` | reused | Orchestrator event log, ARCH §3.2 | the event vocabulary is unchanged |
| `include/simcore/io.hpp` | reused | Recording I/O, ARCH §11 | the recording reader and writer are unchanged |
| `include/simcore/module_host.hpp` | reused | Component host, ARCH §3.3 and §11 | components are loaded and called as today |
| `include/simcore/mutate.hpp` | reused | Mutations, ARCH §11 and §8 | the closed override verbs are unchanged; they run on the orchestrator thread |
| `include/simcore/runner.hpp` | corrected | Runner, ARCH §3.3 and §11: one `StepOnce` loop | the step loop replaces the cycle loop |
| `include/simcore/runspec.hpp` | corrected | Run setup loader, ARCH §2.3 and §11 | new keys, and refusal of `sampling` and `on_missing` |
| `include/simcore/scheduler.hpp` | replaced | `include/simcore/orchestrator.hpp`, ARCH §11 | no base grid; the orchestrator is event driven (`D10`) |
| `include/simcore/transport.hpp` | replaced | `include/vantage/livemeas_writer.h`, ARCH §10.1 | the live measurement writer is the only carrier out of the engine |
| `include/simcore/transport_publisher.hpp` | replaced | `include/vantage/livemeas_writer.h`, ARCH §10.1 | same as `transport.hpp` |
| `include/simcore/transport_shm.hpp` | replaced | `include/vantage/livemeas_writer.h`, ARCH §10.1 | same as `transport.hpp` |
| `src/simcore/CMakeLists.txt` | corrected | Resim engine, ARCH §11: orchestrator sources are added | `livemeas` is its own target, not part of `simcore` (ARCH §10.2) |
| `src/simcore/abi/` | corrected | Resim engine, ARCH §11: `simEngineSeek`, ABI version 3 | the jump is new; create, run and destroy keep their names |
| `src/simcore/bus/` | corrected | Sample buffers, ARCH §3.4 and §11 | `PortBus` holds a buffer per port; `Get` keeps its meaning |
| `src/simcore/bus/cycle.cpp` | replaced | `src/simcore/bus/identity.cpp`, ARCH §11 | its counter, gap and repeat logic moves to the identity tracker, which reads `measurement_counter` |
| `src/simcore/bus/header.cpp` | reused | Sample buffers, ARCH §3.4 | it names origins and port kinds only; the read at the door is the new `signal_header.cpp` (ARCH §11) |
| `src/simcore/diagnostics/` | corrected | Diagnostics, ARCH §7 and §11 | trace, breakpoints and reproducer are keyed by step number |
| `src/simcore/errors/` | reused | Resim engine, ARCH §11 | the event vocabulary is unchanged |
| `src/simcore/io/` | reused | Recording I/O, ARCH §11 | codecs are unchanged; the inspector reuses the descriptor pool of one codec |
| `src/simcore/module_host/` | reused | Component host, ARCH §3.3, §9 and §11 | loading, timeout, quarantine and the isolated stage are unchanged |
| `src/simcore/mutate/` | reused | Mutations, ARCH §8 and §11 | the verbs are unchanged; only the calling thread is fixed |
| `src/simcore/runner/` | corrected | Runner, ARCH §3.3, §7 and §11 | the loop becomes `StepOnce`; divergence compares equal outputs; checkpoint and slice are keyed by step |
| `src/simcore/runspec/` | corrected | Run setup loader, ARCH §2.3 and §11 | reads `trigger`, `previous_cycle`, `bulk`, `buffer_depth`, the live measurement keys and the `⊘` values |
| `src/simcore/scheduler/` | replaced | `src/simcore/orchestrator/orchestrator.cpp`, `src/simcore/orchestrator/event_queue.cpp`, ARCH §11 | the grid clock and the due test have no meaning when a step is an event |
| `src/simcore/scheduler/dump.cpp` | replaced | `src/simcore/orchestrator/plan_dump.cpp`, ARCH §11 | the schedule can no longer be predicted from the setup alone (ARCH §7) |
| `src/simcore/scheduler/reconcile.cpp` | retired | — | a run exists only for a ticket, so there is no due flag to reconcile (ARCH §7) |
| `src/simcore/third_party/` | reused | Run setup loader, ARCH §2.3 | the JSON library the loader uses |
| `src/simcore/transport/` | replaced | `src/livemeas/writer.cpp`, `src/livemeas/shared_region.hpp`, `src/inspector/attach.cpp`, ARCH §10 and §11 | the player transport is replaced by the writer, and its client attach by the inspector |
| `src/simcore/transport/inproc.cpp` | retired | — | an in-process transport for a viewer; the live measurement is the only carrier (ARCH §14, rejected options) |
| `src/simengine/CMakeLists.txt` | corrected | Resim engine, ARCH §11 | links the writer library |
| `src/simengine/main.cpp` | corrected | Supervisor, ARCH §3.7 and §9 | `--supervise`, `--threads` and `--wait-for-attach`; the seal call |
| `src/adas_sim/__init__.py` | reused | Launcher, ARCH §3.1 | the package root of the Python side |
| `src/adas_sim/check/` | corrected | Launcher, ARCH §3.1 and §11 | evaluates `expect:` blocks over results; drops its use of `session.tick`, and starts runs only through `engine/bridge.py` |
| `src/adas_sim/cli/` | reused | Launcher, ARCH §3.1 | the verbs only parse arguments and call the launcher or the batch loop |
| `src/adas_sim/cli/record.py` | replaced | `src/adas_sim/scenario/record.py`, ARCH §11 | making a recording from a scenario moves to the scenario-to-recording script (`D22`); the scripted source it drove is retired |
| `src/adas_sim/cli/run.py` | replaced | `src/simengine/main.cpp`, ARCH §2.3 and §3.3 | an engine run writes its own recording (`outputs.path`); the in-process loop of `sim run` is a Python run path (ARCH §11) |
| `src/adas_sim/config/` | reused | Launcher, ARCH §3.1 | the run setup is authored from YAML, includes and project files (`R-SIM-3`) |
| `src/adas_sim/core/` | retired | — | the Python run path (ARCH §11); the engine step replaces it |
| `src/adas_sim/diagnostics/console.py` | reused | Launcher, ARCH §3.1 | puts stdout and stderr in UTF-8 at each entry point; it holds no `Session` and no tick |
| `src/adas_sim/diagnostics/determinism.py` | corrected | Launcher, ARCH §13 | compares equal outputs and gains the thread-count axis (`R-SIM-24`) |
| `src/adas_sim/diagnostics/diagnostics.py` | corrected | Launcher, ARCH §3.1 | the `doctor` facts stay; it drops its `Session` feasible-cut query and the viewer plug-in report |
| `src/adas_sim/diagnostics/errors.py` | reused | Launcher, ARCH §3.1 | the closed error kinds and exit codes; the C++ set is its twin (`SW-0121`) |
| `src/adas_sim/diagnostics/estimate.py` | corrected | Launcher, ARCH §3.1 and §7 | the duration estimate for a batch counts steps, not ticks |
| `src/adas_sim/diagnostics/events.py` | reused | Launcher, ARCH §3.1 | the closed `event=` vocabulary, which the C++ set mirrors |
| `src/adas_sim/diagnostics/evidence.py` | retired | — | the evidence panel moves out with the viewer (ARCH §13, `R-SIM-25`) |
| `src/adas_sim/diagnostics/explain.py` | retired | — | `sim explain` reads a `Session` for the viewer, and moves out with it (ARCH §13) |
| `src/adas_sim/diagnostics/logging.py` | corrected | Launcher, ARCH §3.1 and §7 | the log line is kept; its `tick=` field becomes the step number |
| `src/adas_sim/diagnostics/suggest.py` | reused | Launcher, ARCH §3.1 | the "did you mean" ranking used by launcher errors |
| `src/adas_sim/diagnostics/summary.py` | reused | Launcher, ARCH §3.1 | counts warnings from the run's own log lines at the end of a run; no `Session`, no tick |
| `src/adas_sim/diagnostics/tap.py` | reused | Launcher, ARCH §3.1 | reads the `taps:` table and checks each against the component manifests, with no run state |
| `src/adas_sim/diagnostics/tolerance.py` | reused | Launcher, ARCH §3.1 | loads the per-component tolerance file for the measured determinism axes |
| `src/adas_sim/engine/` | corrected | Engine start from Python, ARCH §11 | the one place Python starts `simengine` |
| `src/adas_sim/engine/refrun.py` | retired | — | it drives two builds per tick in Python, a Python run path (ARCH §11); equal outputs are compared by engine runs |
| `src/adas_sim/graph/` | reused | Launcher, ARCH §3.1 | coherence, feasible cuts, modes and record policy are the launcher's checks; closing a severed chain is launcher advice (ARCH §13) |
| `src/adas_sim/graph/pipeline.py` | corrected | Run setup writer, ARCH §11 | feeds the new setup keys; stops writing `grid_step_ns`, `order` and `delay_steps` |
| `src/adas_sim/graph/grid.py` | retired | — | there is no base grid (ARCH §7, §11) |
| `src/adas_sim/ingest/` | reused | Launcher, ARCH §3.1 and §13 | the ingest map names the topics a recording provides; its `control` and `refSync` topics are declared in `provides:` |
| `src/adas_sim/io/` | corrected | Launcher, ARCH §3.1: reads only; `mcap.py`'s `McapWriter` gives way to the one Python writer in `interfaces` (`D22`) | it reads a recording's topic index and schemas for the launcher; the data of a run is read only by the C++ reader (ARCH §11) |
| `src/adas_sim/io/cycles.py` | retired | — | the Python cycle model is not carried as a run path (ARCH §7) |
| `src/adas_sim/launcher/` | corrected | Launcher, ARCH §3.1 and §11 | fills `trigger`, `previous_cycle` and the `⊘` values |
| `src/adas_sim/orchestrate/` | corrected | Launcher, ARCH §3.1 and §11 | the loop that starts one supervisor per recording and tallies exit codes stays Python; `progress.py` and `reopen.py` take the step number (ARCH §7) |
| `src/adas_sim/player/` | retired | — | a viewer panel; the viewer is out of this design (`D13`) |
| `src/adas_sim/plugins/` | reused | Launcher, ARCH §3.1 | the codec registry and its conformance kits serve the readers and writers the launcher uses |
| `src/adas_sim/pyapi/` | corrected | Launcher, ARCH §3.1 | the scripting surface reaches the closed verbs; it drops its `Session` and evidence calls |
| `src/adas_sim/pyapi/engine.py` | retired | — | an alias of the engine bridge, named a legacy path in ARCH §11 |
| `src/adas_sim/pyapi/live.py` | retired | — | it serves a running `Session` over a socket; the live measurement replaces the running session (ARCH §1) |
| `src/adas_sim/resolve/` | reused | Launcher, ARCH §3.1 | resolves libraries, bundles and the probe pass from the component libraries' file names |
| `src/adas_sim/resolve/component.py` | corrected | Launcher, ARCH §3.1 and §11 | it keeps loading a library to read its manifest; its exec path, which executes components in Python, is not carried |
| `src/adas_sim/resolve/plugins.py` | retired | — | viewer plug-ins move out with the viewer (ARCH §13, `R-SIM-20`) |
| `src/adas_sim/runspec/` | corrected | Run setup writer, ARCH §11 | `emit_run_spec` and the schema write the new keys |
| `src/adas_sim/session/` | retired | — | the Python cycle model and the viewer's `Session` (ARCH §7, §11, §13) |
| `src/adas_sim/sources/` | replaced | `src/adas_sim/scenario/record.py`, ARCH §11 | its job, a recording made from a scenario, moves to the scenario-to-recording script (`D22`); its in-process run path is retired (ARCH §11) |
| `scripts/build.py` | reused | Standard build, ARCH §11 | byte-identical stub (`R-BUILD-2`) |
| `scripts/build_gui.py` | reused | Standard build, ARCH §11 | byte-identical stub (`R-BUILD-4`) |
| `scripts/setup.py` | reused | Standard build, ARCH §11 | byte-identical stub |
| `scripts/check_anl_sw36.py` | corrected | Launcher, ARCH §3.1 | its rule stands (`R-SIM-23`, an ingest map renames and tags only), but it cites sim v2 ids; step 8 gives it a new id |
| `scripts/check_artifact_kinds.py` | reused | Launcher, ARCH §3.1 | artifact kinds still name their writers |
| `scripts/check_closed_sets.py` | reused | Resim engine, ARCH §11 | the closed vocabularies stay closed |
| `scripts/check_coverage_delta.py` | retired | — | the gate of the deletion of the earlier host, which is done |
| `scripts/check_engine_boundary.py` | reused | Resim engine, ARCH §10.2 | the I/O library pulls in no first-party package |
| `scripts/check_error_parity.py` | reused | Resim engine, ARCH §11 | the error set exists in both languages |
| `scripts/check_evidence_single_producer.py` | retired | — | it guards `evidence.py`, which is retired |
| `scripts/check_headers.py` | corrected | Standard build, ARCH §11 | the `COMPONENT:` token becomes `VANTAGE` (`R-NAME-6`) |
| `scripts/check_invariants.py` | corrected | Standard build, ARCH §11 | gates are re-scoped to the Vantage tree |
| `scripts/check_no_duplication.py` | reused | Standard build, ARCH §11 | no capability keeps two implementations |
| `scripts/check_no_graphical_toolkit.py` | reused | Standard build, ARCH §11 | Vantage has no viewer (`D13`) |
| `scripts/check_no_repeated_field_allocation.py` | reused | Mutations, ARCH §11 | an override never creates an entity (`R-SIM-15`) |
| `scripts/check_time_units.py` | reused | Resim engine, ARCH §11 | no time quantity inside the engine is floating point |
| `scripts/check_trace.py` | retired | — | it runs the checker of the retired sim v2 set; step 8 uses the module-agnostic checker |
| `scripts/ci_gate.py` | corrected | Standard build, ARCH §11 | the set of gates changes with this table |
| `scripts/ci_gate_config.yaml` | corrected | Standard build, ARCH §11 | the test floor is re-measured on the Vantage tree |
| `scripts/coverage_baseline.json` | retired | — | the baseline of the earlier host's deletion gate |
| `scripts/freeze.py` | retired | — | built the one-folder packaged viewer; went with the viz-dependent sub-package in Plan B (`D2`, `D13`) |
| `scripts/gui.py` | replaced | `src/adas_sim/launcher/window.py`, ARCH §11 | the launcher window (`D21`) takes its job; its viewer half went with the viz-dependent sub-package (`D2`, `D13`) |
| `scripts/measure.py` | reused | Standard build, ARCH §11 | records the provenance of a measured value |
| `scripts/prove_equal.py` | retired | — | the equivalence gate of the earlier host's deletion, which is done |
| `scripts/vantage_native.py` | retired | — | launched the native viewer from the command line; went with the viz-dependent sub-package in Plan B (`D2`, `D13`) |

## 4. Requirement rows

Each section holds one table with the columns of section 2.1, and each says what
it must dispose. **The numbers below are the check script's output at the time of
writing** (section 5), not a count kept by hand. Each section's `Scope:` line is
read by the script: a row belongs to the section whose scope covers its UID, and
an `IMP` row belongs to the section that holds the first `SW` row it serves.

### 4.1 SIM concept and system rows (6c)

Scope: SIM:CN, SIM:SYS

Filled by 6c. `CN` goes with `SYS`: a concept row and the system rows it
decomposes into are decided together, so a reader sees one answer for one idea.
To dispose: 659 rows (389 `CN`, 270 `SYS`).

| UID | Disposition | Target | Why |
|---|---|---|---|

### 4.2 SIM software rows, part 1 (6d)

Scope: SIM:SW-0001..0188

Filled by the first 6d worker: `SW-0001` to `SW-0188`, with the `IMP` rows that
serve them. The split is by UID range, so the two workers never meet in one row.
To dispose: 377 rows (188 `SW`, 189 `IMP`).

| UID | Disposition | Target | Why |
|---|---|---|---|

### 4.3 SIM software rows, part 2 (6d)

Scope: SIM:SW-0189..0429

Filled by the second 6d worker: `SW-0189` to `SW-0429`, with the `IMP` rows that
serve them. To dispose: 373 rows (187 `SW`, 186 `IMP`).

| UID | Disposition | Target | Why |
|---|---|---|---|

### 4.4 PARITY rows (6e)

Scope: PARITY:STK, PARITY:SYS, PARITY:SW

Filled by 6e: the parity set in `docs/v2/parity/`. To dispose: 163 rows (16 `STK`,
39 `SYS`, 54 `SW`, 54 `IMP`).

| UID | Disposition | Target | Why |
|---|---|---|---|

## 5. How to check

```
python modules/vantage/scripts/check_migration_register.py [--register <md>] [--selftest]
```

The script builds the universe from the two sets, takes the code universe from the tree at `seed-from-sim` (new files are not listed; a missing tag is `C-SEED`), reads section 3's code table and
section 4's row tables, and prints, per section, the universe count, the rows
listed, the rows inherited and the rows missing. Then it prints one line per
finding, `C-<NAME> <uid or path>: <what>`, and exits 0 only with no finding.

| Finding | Means |
|---|---|
| `C-MISSING` | a universe row is neither listed nor inherited |
| `C-DUPLICATE` | a row is listed twice |
| `C-UNKNOWN` | a UID is not in the universe, or is listed outside its section's scope |
| `C-WORD` | a disposition word is not in the closed list |
| `C-TARGET` | a Target has the wrong form for its word, or points at nothing |
| `C-WHY` | a retired row has an empty Why |
| `C-INHERIT` | an `IMP` row whose `SW` rows disagree is not listed |
| `C-REDUNDANT` | an `IMP` row is listed though its `SW` rows agree |
| `C-RANGE` | a section row is malformed or reversed, names an `IMP` row, expands to no row, has a Why without a section label, or does not cover exactly one whole section |
| `C-CODE` | a code entry is not covered, is covered twice, or a row names a path that does not exist |

Until 6c, 6d and 6e land, the four row tables are empty and every row is missing:
that is the starting point, not a fault of the script. `--selftest` plants one
violation per finding in a small in-memory universe and fails if any is not
caught.
