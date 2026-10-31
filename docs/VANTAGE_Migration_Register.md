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
| SIM:CN-0001..0007, SIM:CN-0281 | carried | VNT | §1.3 — the scope of what Vantage simulates is unchanged |
| SIM:CN-0008..0012, SIM:CN-0282 | carried | VNT | §1.4 — the limits of what Vantage is not are unchanged |
| SIM:CN-0013..0018, SIM:CN-0283 | carried | VNT | §2.2 — one product, project content from configuration and plug-ins only |
| SIM:CN-0019 | moved | RCT:SYS-0001, RCT:SYS-0002, RCT:SYS-0003 | the contract states which header fields every output carries |
| SIM:CN-0020 | superseded | ARCH §3.4, ARCH §6 | the header is read at the door of every sample buffer and drives selection by number |
| SIM:CN-0021 | moved | RCT:SYS-0037 | every port with its record policy is in the recording (RCT:SYS-0037); rate is the period each manifest declares (R-SIM-18); group and size are retired here, left to the open ECU-logging decision (RCT §13) |
| SIM:CN-0022 | carried | VNT | a stage may be measured only if the recording holds its outputs; the launcher model checks the cut before the run |
| SIM:CN-0023 | retired | — | volume is estimated before a run from the record policy, so no separate size budget is kept |
| SIM:CN-0024 | carried | VNT | the recording I/O keeps message bytes, header included, when it converts |
| SIM:CN-0025..0028 | carried | VNT | §3.1 — input, processing and output stay declared by the user, with a core that knows no project |
| SIM:CN-0029 | carried | VNT | the component library under test is still what Vantage loads |
| SIM:CN-0030 | superseded | D13 | a viewer plug-in is the viewer's design |
| SIM:CN-0031 | carried | VNT | the manifest and the ingest map stay with the component |
| SIM:CN-0032 | superseded | D13 | the rule on a viewer plug-in belongs to the viewer's design |
| SIM:CN-0033 | superseded | D13 | what a viewer renders is the viewer's design; the live measurement carries the same data for both |
| SIM:CN-0034 | superseded | D13 | drawing code is the viewer's design |
| SIM:CN-0035..0046, SIM:CN-0286..0287 | carried | VNT | §4 — the design principles still hold for Vantage |
| SIM:CN-0047 | carried | VNT | the engine stays a library with a stable C ABI, now version 3 |
| SIM:CN-0048 | carried | VNT | simengine stays the thin executable with no GUI dependency |
| SIM:CN-0049 | superseded | D13 | the player is a viewer process; any reader attaches to the live measurement |
| SIM:CN-0050 | superseded | ARCH §10, ARCH §14 | the live measurement is the only carrier out of the engine and the player transport was rejected |
| SIM:CN-0051 | superseded | D13 | no player is shipped; the launcher window starts the engine and is no viewer |
| SIM:CN-0052 | superseded | ARCH §10 | the live measurement is shared memory for control and bulk alike |
| SIM:CN-0053 | moved | RCT:SYS-0026 | the contract says the writer never waits for a reader, so a reader may come and go |
| SIM:CN-0063..0065 | superseded | D13 | §5.4 — which data a viewer reads straight from the recording is the viewer's design |
| SIM:CN-0066 | carried | VNT | ports stay named and found through the manifest |
| SIM:CN-0067 | carried | VNT | readers still produce port values and components still consume them |
| SIM:CN-0068 | carried | VNT | the mapping from source names to ports stays a file, the ingest map |
| SIM:CN-0069 | carried | VNT | the versioning rule of the port model stays; the contract states only its first instance (`RCT:SYS-0033`) |
| SIM:CN-0070 | carried | VNT | a missing input stays explicit: an empty input with unknown origin and a badge, never a zero fill |
| SIM:CN-0071 | carried | VNT | a project's own messages are decoded from the descriptors in the manifest without forking the core |
| SIM:CN-0072 | moved | RCT:SYS-0001, RCT:SYS-0002, RCT:SYS-0003 | the contract states the header fields each output carries |
| SIM:CN-0073 | superseded | ARCH §6, ARCH §13 | the header has one timestamp and inputs are chosen by number, so no choice of timestamp is recorded |
| SIM:CN-0074 | superseded | ARCH §6 | a sample with no number or time is a badged fallback of the time rule |
| SIM:CN-0078 | carried | VNT | a reader opens a source, indexes it, seeks and returns port values |
| SIM:CN-0079 | carried | VNT | a reader seeks by time or brings an index that makes it possible |
| SIM:CN-0080 | carried | VNT | the sidecar index is built on first open and reused by later runs |
| SIM:CN-0081 | carried | VNT | the index is keyed by port, so a run reads only the ports its graph needs |
| SIM:CN-0082 | carried | VNT | several readers in one run are merged on one time base |
| SIM:CN-0083 | retired | — | Vantage never corrects a recorded time: it matches by counter (D18) and uses the sender's time (C1) |
| SIM:CN-0084 | superseded | D18, ARCH §3.4 | samples are kept per port (`buffer_depth`) and picked by counter, so arrival order needs no sync buffer |
| SIM:CN-0085 | carried | VNT | readers are found by registration, so a new format needs no change to the core |
| SIM:CN-0086 | carried | VNT | a reader uses the format's own data description and allows an external override |
| SIM:CN-0087..0092, SIM:CN-0311..0312 | carried | VNT | §9.1 — components stay declarative, with a manifest and one producer per port |
| SIM:CN-0093 | carried | VNT | port kinds stay in the manifest; control is a conventional port |
| SIM:CN-0094 | superseded | ARCH §4 | who runs when is the trigger of each stage in the run setup |
| SIM:CN-0095 | superseded | ARCH §3.2 | start and restart reach a component as the op mode of its control message |
| SIM:CN-0096 | carried | VNT | the component host keeps loading and driving the lifecycle; reset is the RESTART run |
| SIM:CN-0097 | carried | VNT | a failing component is reported with its stage and step and a reproducer |
| SIM:CN-0098 | carried | VNT | conversion between port values and structs stays driven by the manifest |
| SIM:CN-0099 | superseded | ARCH §9 | the isolated stage runs one stage in a second process for bisecting a crash |
| SIM:CN-0100..0102, SIM:CN-0316 | carried | VNT | §9.4 — the component ABI stays small, versioned and free of clocks and threads |
| SIM:CN-0103..0106 | carried | VNT | §9.5 — composition and variables stay in the launcher's configuration |
| SIM:CN-0107 | carried | VNT | outputs stay optional: a recording and a live measurement, each may be absent |
| SIM:CN-0108 | carried | VNT | export formats and the replayable output stay with the recording I/O |
| SIM:CN-0109 | moved | RCT:SYS-0042 | the contract says Vantage's reader reads an engine-run recording as written |
| SIM:CN-0110 | carried | VNT | exports are still filtered by port and by time range |
| SIM:CN-0111 | carried | VNT | the run manifest in every artifact is Vantage's metadata on top of C6; step 8 states it |
| SIM:CN-0112 | carried | VNT | an export keeps the header bytes and carries origin from its source |
| SIM:CN-0113..0117 | carried | VNT | §10.2 — the run manifest, exit codes and logs stay; Vantage still reports and never judges |
| SIM:CN-0118..0121, SIM:CN-0320..0321 | carried | VNT | §11.1 — mode and implementation per stage stay the two independent fields of a stage |
| SIM:CN-0122..0128, SIM:CN-0324..0325 | carried | VNT | §11.3 — the launcher model keeps the broken-chain rule, waivers and promote choice, and the engine records the verdict |
| SIM:CN-0129..0131, SIM:CN-0326..0329 | carried | VNT | §11.4 — overrides and faults keep their closed verb lists and run in the mutator |
| SIM:CN-0132 | carried | VNT | the engine stays open-loop |
| SIM:CN-0133 | carried | VNT | the first divergence is still found and recorded, by step number |
| SIM:CN-0134 | carried | VNT | data after the divergence plus a grace is still flagged informational |
| SIM:CN-0135 | retired | — | R-SIM-7 puts integrating a signal into a component under test; no part of Vantage does it (open question) |
| SIM:CN-0136 | carried | VNT | closed-loop work stays out of scope; a simulator reaches Vantage as a recording |
| SIM:CN-0137 | superseded | ARCH §3.2 | a component sees the trigger's time in its control header and the orchestrator alone holds simulation time |
| SIM:CN-0138 | carried | VNT | execution time is still never used to decide anything |
| SIM:CN-0139 | carried | VNT | internal time stays integer nanoseconds |
| SIM:CN-0140..0142, SIM:CN-0330 | superseded | D10, ARCH §7 | §12.2 — a run is one recorded control message, so cycles are no longer reconstructed from a flat recording |
| SIM:CN-0143..0146, SIM:CN-0331..0334, SIM:CN-0392..0395 | superseded | D10, ARCH §7 | §12.3 — no base grid and no due tick; a step is an event and a run exists only for a ticket |
| SIM:CN-0148..0150 | superseded | D18 | §12.4 — input selection by number is the only policy; sampling and on_missing are refused at load |
| SIM:CN-0151 | carried | VNT | runs of one instant go in rank order, and the order is printed |
| SIM:CN-0152 | superseded | ARCH §2.3 | a previous_cycle input replaces delay_steps, which has no meaning when steps are events |
| SIM:CN-0153 | carried | VNT | a loop with no previous-cycle edge is a load error naming the loop |
| SIM:CN-0154 | carried | VNT | the previous-cycle inputs are recorded in the description of the live measurement |
| SIM:CN-0155..0158, SIM:CN-0335..0336 | superseded | D13 | §13.1 — the player is a viewer, out of this design; it reads the live measurement later |
| SIM:CN-0159..0163, SIM:CN-0337..0340 | superseded | D13 | §13.2 — layout, draw layers and primitives are the viewer's design |
| SIM:CN-0164..0168, SIM:CN-0341..0343 | superseded | D13 | §13.3 — transport, timeline, snapshot, plots and evidence belong to the viewer |
| SIM:CN-0170 | superseded | D13 | reading context signals straight from the recording is the viewer's work |
| SIM:CN-0171..0172, SIM:CN-0174..0177, SIM:CN-0344 | carried | VNT | §14 — the launcher window shows and enters the choices and the launcher model keeps the rules behind them (layout choice goes with the viewer) |
| SIM:CN-0173 | superseded | D13 | lazy decode and marking of display-only data is the viewer's work |
| SIM:CN-0178..0184, SIM:CN-0345..0347 | carried | VNT | §15.1 — run configuration layers, schema, validation at load and round trip stay with the launcher |
| SIM:CN-0185 | carried | VNT | a batch is still one run setup over a list of recordings |
| SIM:CN-0186 | carried | VNT | each recording runs in its own process under a supervisor |
| SIM:CN-0187 | carried | VNT | each run still writes its own artifact directory |
| SIM:CN-0188 | carried | VNT | a failing run still does not stop the batch |
| SIM:CN-0189 | carried | VNT | the batch still reports a status list with reason and duration |
| SIM:CN-0190 | carried | VNT | parameter sweeps stay with the batch loop |
| SIM:CN-0191 | carried | VNT | a batch is still resumable from the checkpoint files |
| SIM:CN-0192 | carried | VNT | index caches are still shared across a batch |
| SIM:CN-0193 | carried | VNT | per-run timeout and limits stay in the run setup |
| SIM:CN-0194..0197 | superseded | D17 | §16.2 — a stage restarts on its first run and after a jump and each recording has its own process, so no reset policy is chosen |
| SIM:CN-0198..0199 | carried | VNT | §16.3 — the read-error policies of a batch stay with the batch loop and the reader |
| SIM:CN-0200 | carried | VNT | the engine still needs no display or prompt |
| SIM:CN-0201 | carried | VNT | one engine binary serves the desktop and CI |
| SIM:CN-0202 | carried | VNT | the exit codes stay distinct and documented |
| SIM:CN-0203 | carried | VNT | an artifact directory stays self-contained, the config bundle being embedded |
| SIM:CN-0204 | carried | VNT | the optional watchdog stays as the execution timeout |
| SIM:CN-0205 | carried | VNT | the watchdog is still off when a debugger is attached |
| SIM:CN-0206 | carried | VNT | per-component timing statistics stay in the cost report |
| SIM:CN-0207 | carried | VNT | explain still does a dry run and prints the plan of ranks, triggers and clocks |
| SIM:CN-0208 | carried | VNT | tap points stay named in configuration |
| SIM:CN-0209 | superseded | D13 | the provenance query read a Session for the evidence panel, which goes with the viewer |
| SIM:CN-0210 | carried | VNT | the cycle trace stays, keyed by step number |
| SIM:CN-0211 | carried | VNT | comparing two runs port by port with first divergence stays |
| SIM:CN-0212 | carried | VNT | the warning summary at the end of a run stays |
| SIM:CN-0213 | carried | VNT | everything the command line does stays available from Python |
| SIM:CN-0214 | carried | VNT | algorithm modules load in-process, so one attach reaches them all |
| SIM:CN-0215 | carried | VNT | `--wait-for-debugger` prints the process id and pauses before the first cycle |
| SIM:CN-0216 | carried | VNT | break conditions: at a step, at a time, on entry to a module, on a port condition |
| SIM:CN-0217 | carried | VNT | the cycle loop is single-threaded and deterministic by default so breakpoints work |
| SIM:CN-0218 | carried | VNT | the watchdog and timeouts are off in debug mode |
| SIM:CN-0219 | carried | VNT | the engine launches without the Python layer from a resolved run spec |
| SIM:CN-0220 | carried | VNT | symbol resolution is documented and configurable on both platforms |
| SIM:CN-0221 | carried | VNT | ready-made debugger launch configurations ship for common IDEs |
| SIM:CN-0222 | retired | — | component state is not exposed by the ABI, the state snapshot is parked (RCT P1) and R-SIM-17 allows only recompute from the start; the checkpoint is progress, not state |
| SIM:CN-0223 | carried | VNT | a module crash writes a minimal reproducer package |
| SIM:CN-0224 | carried | VNT | only the ports the active stages need are read |
| SIM:CN-0225 | carried | VNT | a payload is decoded only when a simulated stage consumes it |
| SIM:CN-0226 | carried | VNT | the sidecar index is still built once and reused |
| SIM:CN-0227 | carried | VNT | iterating against an exported recording stays the way to avoid re-running perception |
| SIM:CN-0228 | superseded | ARCH §8 | runs of one rank may run in parallel inside a step, with a barrier after every rank |
| SIM:CN-0229 | carried | VNT | bulk data stays in buffers viewed without copying |
| SIM:CN-0230 | superseded | D13 | display-only data is read by the viewer, not the engine |
| SIM:CN-0231 | carried | VNT | a time slice is still a jump before the first step |
| SIM:CN-0232 | carried | VNT | the per-run report of time, steps and bytes stays |
| SIM:CN-0233 | carried | VNT | explain still estimates the duration, counting steps |
| SIM:CN-0234 | carried | VNT | the integrity check of a recording stays a gate |
| SIM:CN-0235 | carried | VNT | integrity results stay available as a gate |
| SIM:CN-0236 | carried | VNT | the content hash stays the recording's identity as sources[].sha256 |
| SIM:CN-0237 | carried | VNT | extract by time range and port stays |
| SIM:CN-0238 | carried | VNT | convert and index stay with the recording I/O |
| SIM:CN-0239 | carried | VNT | inspect stays the listing of ports, rates and time range |
| SIM:CN-0240 | carried | VNT | lineage of a derived recording is Vantage's metadata on top of C6; step 8 states it |
| SIM:CN-0241 | carried | VNT | the preparation tools stay usable without the engine and their output is engine input |
| SIM:CN-0242..0248, SIM:CN-0363 | carried | VNT | §24 — the same configuration and results on Windows and Linux stay required |
| SIM:CN-0249 | carried | VNT | the same inputs, setup and binaries still give equal outputs |
| SIM:CN-0250 | carried | VNT | no clock, unseeded randomness or thread dependence in the default mode |
| SIM:CN-0251 | superseded | ARCH §8 | parallelism is also allowed across same-rank runs of a step, with a one-thread against N-thread comparison |
| SIM:CN-0252 | carried | VNT | every run still writes a manifest of versions, hashes, modes and result |
| SIM:CN-0253 | carried | VNT | a run is still reproducible from its manifest |
| SIM:CN-0254 | carried | VNT | anything that breaks reproducibility is still declared |
| SIM:CN-0255 | carried | VNT | reader, exporter and module stay extension points; the visualization point goes with the viewer |
| SIM:CN-0256 | carried | VNT | codecs are still found by registration |
| SIM:CN-0257 | carried | VNT | each extension point keeps a versioned interface and a conformance kit |
| SIM:CN-0258 | carried | VNT | templates for the reader, exporter and module points stay in the delivery |
| SIM:CN-0259 | carried | VNT | Vantage is delivered as a versioned package for both systems |
| SIM:CN-0260 | carried | VNT | semantic versions and independent port-model and ABI versions stay |
| SIM:CN-0261 | carried | VNT | a project still pins a version range |
| SIM:CN-0262 | carried | VNT | the delivery list stays, without the player |
| SIM:CN-0263 | carried | VNT | every release still ships a self-test on a miniature recording |
| SIM:CN-0264 | carried | VNT | breaking changes still come with a migration guide |
| SIM:CN-0265 | carried | VNT | components stay shared libraries on a stable C layer |
| SIM:CN-0266 | carried | VNT | a component stays single-threaded or deterministic inside |
| SIM:CN-0267 | moved | RCT:SYS-0001, RCT:SYS-0002 | the contract states the header every output carries |
| SIM:CN-0268 | moved | RCT:SYS-0037 | the contract says a recording holds a topic for every declared port not excluded |
| SIM:CN-0269 | moved | RCT:SYS-0039 | the contract says a recording keeps one log_time clock in event order |
| SIM:CN-0270 | retired | — | a size fact about typical recordings, not an obligation; the live measurement sizes are fixed by measurement (ARCH §4) |
| SIM:CN-0271..0280, SIM:CN-0374..0376 | retired | — | §29 — a risk list is not an obligation; each mitigation is held by the row it cites |
| SIM:CN-0284 | superseded | D10, ARCH §2.3 | a period only survives as clock_period_ns of a stage no recording starts, and it no longer drives scheduling |
| SIM:CN-0285 | carried | VNT | ingest map and config bundle are deployed beside the library; the viewer plug-in part goes with D13 |
| SIM:CN-0288..0291 | carried | VNT | §6.1 — the split of per-message work in C++ and per-run work in Python is kept (ARCH §11 draws it) |
| SIM:CN-0292..0296, SIM:CN-0396..0398 | carried | VNT | §6.2 — the run setup is the only input of the engine, written by the launcher, as the Resolved Run Spec was |
| SIM:CN-0297 | carried | VNT | no generated bindings and no sibling checkout are needed to decode a port |
| SIM:CN-0298 | superseded | ARCH §13 | capture_time is not used to age a value and the header keeps one timestamp |
| SIM:CN-0299 | moved | RCT:SYS-0041 | a recording states its origin tags from the closed list (the list has no unknown; open question) |
| SIM:CN-0300 | carried | VNT | the reader marks a topic with no stated origin unknown (the contract does not state it; open question) |
| SIM:CN-0301 | carried | VNT | a value the engine did not read or compute is badged and never invented |
| SIM:CN-0302 | carried | VNT | a reader streams, so a recording never has to fit in memory |
| SIM:CN-0303 | carried | VNT | a codec declares its capabilities, and one that cannot round-trip is no input; the capture-time capability is dropped (D22) |
| SIM:CN-0304 | carried | VNT | the ingest map names each signal's port, type, origin and array shape; unit and scale are not carried (R-SIM-23, CN-0309) |
| SIM:CN-0305 | superseded | ARCH §3.4 | the header is read from the sig_header field of each message at the door, not bound by the map |
| SIM:CN-0306 | carried | VNT | absent: in the ingest map still names a port a family never recorded |
| SIM:CN-0307 | carried | VNT | recording families are still recognised by declared match rules |
| SIM:CN-0308 | carried | VNT | a port claimed by two maps is still an authoring error naming both |
| SIM:CN-0309 | retired | — | R-SIM-23 wins: an ingest map renames and tags only; a unit conversion is an unversioned algorithm between the recording and the component |
| SIM:CN-0310 | carried | VNT | ingest maps are still deployed beside the component library |
| SIM:CN-0313 | carried | VNT | exports are still bound by name at run time |
| SIM:CN-0314 | carried | VNT | an undersized output buffer still grows once, then is a contract error |
| SIM:CN-0315 | carried | VNT | the per-run execution timeout stays as limits.exec_timeout_ms |
| SIM:CN-0317 | carried | VNT | the record policy and the volume estimate before a run stay with the launcher and the run setup |
| SIM:CN-0318 | moved | RCT:SYS-0029 | the contract says bulk payloads are referenced, never inline |
| SIM:CN-0319 | carried | VNT | the merged output is Vantage's metadata on top of C6; step 8 states it |
| SIM:CN-0322..0323 | carried | VNT | §11.2 — the coherence classification stays with the launcher model, computed without running |
| SIM:CN-0348 | carried | VNT | ok, fail, crash and timeout stay four outcomes, judged from outside the worker |
| SIM:CN-0349 | carried | VNT | the worker still checkpoints progress, now by step number |
| SIM:CN-0350 | carried | VNT | every capability stays reachable from a short script |
| SIM:CN-0351 | retired | — | a rule for the order of the sim v2 build; this program's order and gates are in the plan section 5 |
| SIM:CN-0352 | carried | VNT | name resolution with did-you-mean stays for the launcher's names |
| SIM:CN-0353 | carried | VNT | the environment report (doctor) stays and never raises |
| SIM:CN-0354 | carried | VNT | the closed error taxonomy stays in both languages |
| SIM:CN-0355 | carried | VNT | the reader still streams and memory stays bounded by the working set |
| SIM:CN-0356 | carried | VNT | cost and throughput stay budgeted with a number and measured |
| SIM:CN-0357 | superseded | D13 | player frame time is a viewer budget |
| SIM:CN-0358 | carried | VNT | the engine keeps one implementation of each capability |
| SIM:CN-0359 | retired | — | evidence about the duplicate grid scheduler, which the event-driven orchestrator replaces (ARCH §11); the rule itself is `CN-0358` |
| SIM:CN-0360 | superseded | D3 | sim is untouched until Vantage replaces its content at migration |
| SIM:CN-0361 | superseded | D9 | Vantage is proven on the lab first and each gate leaves a working tool |
| SIM:CN-0362 | superseded | ARCH §11 | the Python run path is legacy and not carried, so no second engine exists |
| SIM:CN-0364 | carried | VNT | determinism is still measured per axis, with the thread count added (ARCH §13) |
| SIM:CN-0365 | carried | VNT | tolerance stays declared once per component with a written reason |
| SIM:CN-0366 | carried | VNT | a resim is still pinned to the library hash the recording carries |
| SIM:CN-0367 | superseded | D13 | a recording carries a viewer plug-in's identity, so this is the viewer's design |
| SIM:CN-0368 | superseded | D13 | the plug-in API version belongs to the viewer's plug-ins |
| SIM:CN-0369 | superseded | D13 | binding a plug-in to ports through the manifest belongs to the viewer's plug-ins |
| SIM:CN-0370 | superseded | D13 | a shipped player is a viewer |
| SIM:CN-0371 | carried | VNT | the documentation stays sized for a new maintainer |
| SIM:CN-0372 | carried | VNT | what a component owes Vantage stays a checklist, tried on the lab's components |
| SIM:CN-0373 | superseded | D10 | recordings now carry the control message of each run, so cycles are not reconstructed |
| SIM:CN-0377 | superseded | D5 | the Vantage set has no concept layer to trace to |
| SIM:CN-0378 | superseded | D5 | the register disposes every row; no deferred marks are kept |
| SIM:CN-0379 | superseded | D5 | open questions are recorded in the architecture and the plan, not in a concept layer |
| SIM:CN-0380 | retired | — | a rule for the old test spec; the section 4 principles are carried row by row |
| SIM:CN-0381 | retired | — | a rule on writing requirements, held by R-REQ-3 for every set |
| SIM:CN-0382 | retired | — | a rule on status, held by R-REQ-6 for every set |
| SIM:CN-0383 | retired | — | a rule on test identifiers, held by R-REQ-9 for every set |
| SIM:CN-0384..0386 | carried | VNT | Library loading splits in two — the run setup carries resolved library paths and the engine searches nothing |
| SIM:CN-0387 | retired | — | evidence of drift between the old ingest parsers; one parser is the rule of CN-0358 and CN-0287 |
| SIM:CN-0388 | carried | VNT | the executable keeps argument handling and lifecycle, and the engine's checks run in the library |
| SIM:CN-0389 | retired | — | main.cpp now holds the supervisor and isolated stage (ARCH §11), so a line count no longer shows leakage; CN-0388 stays |
| SIM:CN-0390 | carried | VNT | simcore stays usable without simengine |
| SIM:CN-0391 | superseded | ARCH §13 | the capture time is no longer kept, so it cannot be filled from reception |
| SIM:CN-0399 | retired | — | a rule on trace links, held by R-REQ-11 for every set |
| SIM:CN-0400..0402 | carried | VNT | §2.4 — the safety-evidence stance stays with the tool; the plan and the architecture say nothing else (open question) |
| SIM:CN-0403 | retired | — | a rule on progress marks, held by R-REQ-6a for every set |
| SIM:SYS-0001 | carried | VNT | readers stay plug-ins that open a source, index it, seek and return port values |
| SIM:SYS-0002 | carried | VNT | a reader streams, so a recording never has to fit in memory |
| SIM:SYS-0003 | carried | VNT | a reader seeks by time or brings an index that makes it possible |
| SIM:SYS-0004 | carried | VNT | the sidecar index is built on first open and reused by later runs |
| SIM:SYS-0005 | carried | VNT | the index is keyed by port, so a run reads only the ports its graph needs |
| SIM:SYS-0006 | carried | VNT | several readers in one run are still merged on one time base |
| SIM:SYS-0007 | retired | — | Vantage never corrects a recorded time (D18, C1), so a source declares no time domain or skew; the one recording clock is `RCT:SYS-0039` (held through SIM:CN-0269) |
| SIM:SYS-0008 | superseded | D18, ARCH §3.4 | samples are kept per port (`buffer_depth`) and picked by counter, so out-of-order arrival needs no sync buffer |
| SIM:SYS-0009 | carried | VNT | a reader uses the format's own data description and allows an external override |
| SIM:SYS-0010 | carried | VNT | a codec declares its capabilities and one that cannot round-trip is no input; the capture-time capability is dropped (D22) |
| SIM:SYS-0011 | carried | VNT | the release-one readers (vehicle measurement, bench capture, interchange) are still Vantage's |
| SIM:SYS-0012 | carried | VNT | the image-folder reader and the synthetic-scenario reader stay as recording readers |
| SIM:SYS-0013 | carried | VNT | the mapping from source names to ports stays a file, the ingest map |
| SIM:SYS-0014 | carried | VNT | the map names each signal's port, type, origin and array shape; unit, scale and offset are dropped (`R-SIM-23`, see SYS-0019) |
| SIM:SYS-0015 | superseded | ARCH §3.4, ARCH §6 | the header is read from `sig_header` at the door of every sample buffer, so the map binds no header field |
| SIM:SYS-0016 | carried | VNT | `absent:` in the ingest map still names a port a family never recorded |
| SIM:SYS-0017 | carried | VNT | recording families are still recognised by declared match rules |
| SIM:SYS-0018 | carried | VNT | a port claimed by two maps is still an authoring error naming both |
| SIM:SYS-0019 | retired | — | `R-SIM-23` wins: a map renames and tags only; a unit conversion is an unversioned algorithm between the recording and the component |
| SIM:SYS-0020 | carried | VNT | a type that does not match the port still means the recording does not support that cut |
| SIM:SYS-0021 | carried | VNT | ingest maps are still deployed beside the component library |
| SIM:SYS-0022 | carried | VNT | the launcher model computes the feasible cuts from the recording's index before any run (ARCH §3.1) |
| SIM:SYS-0023..0028 | carried | VNT | §6.1 — the versioned port catalogue, the missing-is-not-zero rule, project-local extension and manifest-carried schemas stay |
| SIM:SYS-0029 | carried | VNT | the header fields are the contract's (`RCT:SYS-0001`..`0003`); simulation time, producer, mode and repeat stay Vantage's bookkeeping of each sample (ARCH §3.4); capture time is retired (D22) |
| SIM:SYS-0030 | superseded | ARCH §13 | `R-SIM-14` now has one clock: a recording keeps one time per message and the measurement time is the header's `source_timestamp_us` |
| SIM:SYS-0031 | superseded | ARCH §6, ARCH §13 | the header has one timestamp and inputs are chosen by number, so no choice of timestamp is recorded |
| SIM:SYS-0032 | superseded | ARCH §6 | a sample with no number or time is a badged fallback of the time rule |
| SIM:SYS-0033..0036 | carried | VNT | §6.3 — origin tags, the marking of reconstructed values and the ban on estimating what nothing produced stay; the contract states only the recorded origins (`RCT:SYS-0041`) |
| SIM:SYS-0037..0043 | carried | VNT | §7.1 — manifests, the graph built from them, one producer per port and the generated shim stay with the component |
| SIM:SYS-0044 | carried | VNT | port kinds stay in the manifest and `control` is a conventional port; who runs when is the run setup's trigger |
| SIM:SYS-0045 | superseded | ARCH §3.2 | start and restart reach a component as the op mode of its control message, not as wired lifecycle events |
| SIM:SYS-0046 | carried | VNT | a unit is still a self-contained file exposing named ports that a top-level file composes |
| SIM:SYS-0047 | carried | VNT | paths and environment values still use variables resolved at load |
| SIM:SYS-0048 | carried | VNT | the component host keeps loading and driving the lifecycle; reset is the RESTART run |
| SIM:SYS-0049 | carried | VNT | a failing component is reported with its stage and step and a reproducer |
| SIM:SYS-0050 | carried | VNT | exports are still bound by name at run time, with no compile-time link |
| SIM:SYS-0051 | carried | VNT | an undersized output buffer still grows once, then is a contract error |
| SIM:SYS-0052 | carried | VNT | the host still refuses an unsupported ABI version, naming both |
| SIM:SYS-0053 | carried | VNT | a port set is still read from the manifest at probe time, with no hand mapping |
| SIM:SYS-0054 | carried | VNT | components still read no clock; time arrives in the control header and the port headers |
| SIM:SYS-0055 | carried | VNT | a component that affects determinism still declares it in its manifest |
| SIM:SYS-0056 | carried | VNT | the per-call execution timeout stays as `limits.exec_timeout_ms`, with outcome timeout |
| SIM:SYS-0057 | carried | VNT | conversion between port values and structs stays driven by the manifest |
| SIM:SYS-0058 | carried | VNT | the isolated stage hosts one stage in a second process (ARCH §9) |
| SIM:SYS-0059 | carried | VNT | source time, simulation time (the orchestrator's alone) and an advisory wall clock stay and the wall clock never decides; SIM:CN-0137 differs because it is about what a component sees |
| SIM:SYS-0060 | carried | VNT | internal time stays integer nanoseconds |
| SIM:SYS-0061..0063 | superseded | D10, ARCH §7 | §8.2 — a run is one recorded control message, so cycles and their rate are not reconstructed from a flat recording |
| SIM:SYS-0064..0072, SIM:SYS-0285..0286 | superseded | D10, ARCH §2.3, ARCH §7 | §8.3 — no base grid and no due tick; a step is an event, a stage starts by control, input or clock, and a period survives only as `clock_period_ns` |
| SIM:SYS-0073 | superseded | D18 | input selection by number is the only policy; `sampling` is refused at load |
| SIM:SYS-0074 | superseded | D18 | `on_missing` is refused at load; a missing sample is a badged fallback |
| SIM:SYS-0075 | superseded | D18 | inputs are picked by counter, so no repeat flag reaches a component |
| SIM:SYS-0076 | carried | VNT | runs of one instant go in rank order and the plan prints the order |
| SIM:SYS-0077 | superseded | ARCH §2.3 | a `previous_cycle` input replaces the delay counted in steps, which has no meaning when steps are events |
| SIM:SYS-0078 | carried | VNT | a loop with no previous-cycle edge is a load error naming the loop |
| SIM:SYS-0079 | carried | VNT | the previous-cycle inputs, the only latency left, are recorded in the description of the live measurement |
| SIM:SYS-0080..0086 | carried | VNT | §9.1 — mode and implementation per stage stay the two independent fields of a stage |
| SIM:SYS-0087..0096 | carried | VNT | §9.2 — the launcher model keeps the coherence classification, the broken-chain block, waivers and the closing of gaps |
| SIM:SYS-0097..0103 | carried | VNT | §9.3 — overrides and faults keep their closed verb lists and run in the mutator |
| SIM:SYS-0104 | carried | VNT | the engine stays open-loop |
| SIM:SYS-0105 | carried | VNT | the first divergence is still found and recorded, by step number |
| SIM:SYS-0106 | carried | VNT | data after the divergence plus a grace is still flagged informational |
| SIM:SYS-0107 | carried | VNT | the manifest keeps the coherence verdict and the divergence point |
| SIM:SYS-0108 | retired | — | `R-SIM-7` puts integrating a signal into a component under test; no part of Vantage does it |
| SIM:SYS-0109 | carried | VNT | closed-loop work stays out of scope; a world simulator reaches Vantage as a recording |
| SIM:SYS-0110 | carried | VNT | outputs stay optional: a recording and a live measurement may each be absent |
| SIM:SYS-0111 | carried | VNT | export formats and the replayable output stay with the recording I/O |
| SIM:SYS-0112 | moved | RCT:SYS-0042 | the contract says Vantage's reader reads an engine-run recording as written |
| SIM:SYS-0113 | carried | VNT | exports are still filtered by port and by time range |
| SIM:SYS-0114 | carried | VNT | the run manifest in every artifact is Vantage's metadata on top of C6; step 8 states it |
| SIM:SYS-0115 | carried | VNT | an export keeps the header bytes and the origin of its source |
| SIM:SYS-0116 | carried | VNT | the record policy of each port stays in the run setup and is recorded for every port |
| SIM:SYS-0117 | carried | VNT | the volume estimate before a run stays with the launcher |
| SIM:SYS-0118 | moved | RCT:SYS-0029 | the contract says bulk payloads are referenced, never inline; the scene budget belongs to the viewer |
| SIM:SYS-0119 | carried | VNT | a merged output loads alone; step 8 states it on top of C6 |
| SIM:SYS-0120 | moved | RCT:SYS-0037 | the contract says a recording holds a topic for every declared port not excluded, which the engine's writer follows (SIM:CN-0113 and CN-0317 hold only the manifest and the policy) |
| SIM:SYS-0121 | carried | VNT | the recording model and the codec split stay in the recording I/O; the two-clock part goes (ARCH §13) |
| SIM:SYS-0122 | carried | VNT | a recording round-trips and an export is lossy and terminal, refused as input by capability |
| SIM:SYS-0123 | carried | VNT | the run manifest stays; its timing model, reset policy and timing-recovery rung entries go with the grid and the ladder (D10, D17) |
| SIM:SYS-0124 | carried | VNT | a run is still reproducible from its manifest |
| SIM:SYS-0125 | carried | VNT | the exit codes stay distinct and documented |
| SIM:SYS-0126 | carried | VNT | log lines stay from a closed vocabulary, the step number replacing the tick |
| SIM:SYS-0127 | carried | VNT | Vantage still reports and never judges whether a run passed |
| SIM:SYS-0128..0131 | superseded | D13 | §11.1 — the player is a viewer; the engine side of attach and detach is `RCT:SYS-0026` (the writer never waits), which SIM:CN-0053 holds |
| SIM:SYS-0137..0138 | superseded | D13 | §11.2 — transport, advance-N and play speed belong to the viewer; the engine offers `simEngineSeek` only (ARCH §13) |
| SIM:SYS-0152..0155 | superseded | D13 | §11.4 — snapshots and the evidence panel belong to the viewer |
| SIM:SYS-0158 | carried | VNT | the launcher window shows and enters each stage's mode and implementation (D21) |
| SIM:SYS-0159 | carried | VNT | the launcher model classifies coherence at selection time and blocks a broken chain with the same remedies as the headless path |
| SIM:SYS-0160 | carried | VNT | the launcher writes the run setup and holds no state that is not in that file |
| SIM:SYS-0161 | carried | VNT | adding recordings and starting stay in the window; selecting a layout goes with the viewer (D13) |
| SIM:SYS-0162 | carried | VNT | the launcher shows which libraries are available, their versions and which lack a binary |
| SIM:SYS-0163 | carried | VNT | the launcher shows per recording which stages could be set to `measured` |
| SIM:SYS-0164 | carried | VNT | the four merge layers of configuration stay with the launcher |
| SIM:SYS-0165 | carried | VNT | the run setup stays the only input of the engine; "every period computed" no longer applies, there being no grid |
| SIM:SYS-0166 | carried | VNT | the run setup carries resolved library paths and the engine searches nothing |
| SIM:SYS-0167 | carried | VNT | the engine prints what it loaded; its plan of ranks, triggers and clocks replaces the schedule |
| SIM:SYS-0168 | carried | VNT | every configuration file is validated against a schema with locating errors |
| SIM:SYS-0169 | carried | VNT | an unknown key is an error; `sampling` and `on_missing` are now among them (D18) |
| SIM:SYS-0170 | carried | VNT | every file carries a schema version and an unknown one is refused |
| SIM:SYS-0171 | carried | VNT | references, modes and types are validated at load, naming both ends |
| SIM:SYS-0172 | carried | VNT | configuration still round-trips to a byte-identical file |
| SIM:SYS-0173 | carried | VNT | includes and fragments stay |
| SIM:SYS-0174 | carried | VNT | composition, connections and source-signal binding stay separate file kinds; the visual layout file goes with the viewer (D13) |
| SIM:SYS-0175 | carried | VNT | the common changes stay a declared file set; changing the active layout goes with the viewer (D13) |
| SIM:SYS-0176 | carried | VNT | configuration stays in the algorithm team's repository |
| SIM:SYS-0177 | carried | VNT | one config bundle per component and build is packed beside the library with its hash |
| SIM:SYS-0178 | carried | VNT | project agreement and ego-parameter agreement across bundles are still checked at load |
| SIM:SYS-0179 | carried | VNT | only a file some component reads at run time enters the bundle |
| SIM:SYS-0180 | carried | VNT | geometry still comes from per-project configuration, carried in the live measurement's bundles; drawing a fallback differently is the viewer's (open question) |
| SIM:SYS-0181 | carried | VNT | a batch is still one run setup over a list of recordings |
| SIM:SYS-0182 | carried | VNT | the runs of a batch stay separate processes; the threads of ARCH §8 live inside one engine run |
| SIM:SYS-0183 | carried | VNT | the developer face is `simengine` started directly, the batch face one supervised process per recording, plus the isolated stage (ARCH §9) |
| SIM:SYS-0184 | carried | VNT | each run still writes its own artifact directory |
| SIM:SYS-0185 | carried | VNT | a failing run still does not stop the batch |
| SIM:SYS-0186 | carried | VNT | ok, fail, crash and timeout stay four outcomes, judged from outside the worker |
| SIM:SYS-0187 | carried | VNT | the batch still reports a status list with reason and duration |
| SIM:SYS-0188 | carried | VNT | a crash still records its recording, setup, last step, stderr and run id, from the worker's checkpoint |
| SIM:SYS-0189 | carried | VNT | parameter sweeps stay with the batch loop |
| SIM:SYS-0190 | carried | VNT | a batch is still resumable from the checkpoint files |
| SIM:SYS-0191 | carried | VNT | per-run timeout and limits stay in the run setup |
| SIM:SYS-0192 | superseded | D17 | a stage restarts on its first run and after a jump and each recording has its own process, so no reset policy is chosen |
| SIM:SYS-0193 | carried | VNT | the read-error policies of a batch stay with the batch loop and the reader |
| SIM:SYS-0194 | carried | VNT | index caches are still shared across a batch |
| SIM:SYS-0195 | carried | VNT | the engine still needs no display, GUI library or prompt; the launcher window is a separate part (D21) |
| SIM:SYS-0196 | carried | VNT | one engine binary serves the desktop and CI |
| SIM:SYS-0197 | carried | VNT | an artifact directory stays self-contained, the config bundle being embedded; opening it in a viewer is that design's work (open question) |
| SIM:SYS-0198 | carried | VNT | the optional watchdog stays as the execution timeout and stays off under a debugger |
| SIM:SYS-0199 | carried | VNT | per-component timing statistics stay in the cost report |
| SIM:SYS-0200 | carried | VNT | every capability stays reachable from a short script |
| SIM:SYS-0201 | retired | — | a rule for the order of the sim v2 build; this program's order and gates are in the plan section 5 |
| SIM:SYS-0202 | carried | VNT | explain still does a dry run and prints the plan of ranks, triggers and clocks with an estimated duration |
| SIM:SYS-0203 | carried | VNT | tap points stay named in configuration |
| SIM:SYS-0204 | carried | VNT | the cycle trace stays, one entry per run, keyed by step number |
| SIM:SYS-0205 | carried | VNT | comparing two runs port by port with the first divergence stays |
| SIM:SYS-0206 | carried | VNT | the warning summary at the end of a run stays |
| SIM:SYS-0207 | carried | VNT | name resolution with did-you-mean stays for the launcher's names; layer and style-token names go with the viewer |
| SIM:SYS-0208 | carried | VNT | the environment report (doctor) stays and never raises; plug-in inspection goes with the viewer |
| SIM:SYS-0209 | carried | VNT | the closed error taxonomy stays in both languages |
| SIM:SYS-0210 | superseded | D13 | the provenance query read a Session for the evidence panel, which goes with the viewer |
| SIM:SYS-0211 | carried | VNT | everything the command line does stays available from Python |
| SIM:SYS-0212 | carried | VNT | components load in-process, so one attach reaches them all |
| SIM:SYS-0213 | carried | VNT | the engine can still print its process id and pause before its first step |
| SIM:SYS-0214 | carried | VNT | break conditions: at a step, at a time, on entry to a module, on a port condition |
| SIM:SYS-0215 | carried | VNT | the engine is single-threaded and deterministic by default (`--threads 1`, ARCH §8) so breakpoints work |
| SIM:SYS-0216 | carried | VNT | the engine launches without the Python layer from a run setup |
| SIM:SYS-0217 | carried | VNT | symbol resolution is documented and ready-made debugger configurations ship |
| SIM:SYS-0218 | retired | — | component state is not exposed by the ABI, the state snapshot is parked (RCT P1) and R-SIM-17 allows only recompute from the start |
| SIM:SYS-0219 | carried | VNT | a module crash writes a minimal reproducer package |
| SIM:SYS-0220 | carried | VNT | the integrity check of a recording stays a check before simulation |
| SIM:SYS-0221 | carried | VNT | integrity results stay available as a gate |
| SIM:SYS-0222 | carried | VNT | the content hash stays the recording's identity as `sources[].sha256` |
| SIM:SYS-0223 | carried | VNT | extract by time range and port stays |
| SIM:SYS-0224 | carried | VNT | convert and index stay with the recording I/O |
| SIM:SYS-0225 | carried | VNT | inspect stays the listing of ports, rates and time range |
| SIM:SYS-0226 | carried | VNT | lineage of a derived recording is Vantage's metadata on top of C6; step 8 states it |
| SIM:SYS-0227 | carried | VNT | the preparation tools stay usable without the engine |
| SIM:SYS-0228 | carried | VNT | the launcher model checks the cut against what the recording carries and refuses `measured` for a stage whose outputs are absent; what a recording holds is `RCT:SYS-0037` (SIM:CN-0268) |
| SIM:SYS-0229 | retired | — | volume is estimated before a run from the record policy, so no separate size budget is kept |
| SIM:SYS-0230 | carried | VNT | only the ports the active stages need are read |
| SIM:SYS-0231 | carried | VNT | a payload is decoded only when a simulated stage consumes it; the display half goes with the viewer |
| SIM:SYS-0232 | carried | VNT | a time slice is still a jump before the first step |
| SIM:SYS-0233 | carried | VNT | bulk data stays in buffers viewed without copying |
| SIM:SYS-0234 | carried | VNT | cost and throughput stay budgeted with a number and measured |
| SIM:SYS-0236 | superseded | ARCH §8 | runs of one rank may run in parallel inside a step, with a barrier after every rank |
| SIM:SYS-0237 | carried | VNT | the per-run report of time, steps and bytes stays |
| SIM:SYS-0238 | carried | VNT | explain still estimates the duration, counting steps |
| SIM:SYS-0239..0246 | carried | VNT | §19 — determinism is still measured per axis, with the thread count added (ARCH §13), tolerance declared once with a reason |
| SIM:SYS-0247..0251 | carried | VNT | §20 — the same configuration and results on Windows and Linux stay required |
| SIM:SYS-0252 | carried | VNT | reader, exporter and module stay extension points with a versioned interface and conformance kit; the visualization point goes with the viewer (D13) |
| SIM:SYS-0253 | superseded | D13 | a recording carrying a viewer plug-in's identity is the viewer's design |
| SIM:SYS-0254 | superseded | D13 | the plug-in API version belongs to the viewer's plug-ins |
| SIM:SYS-0255 | superseded | D13 | layer plug-ins are the viewer's; ingest maps and bundles beside the library stay under SYS-0021 and SYS-0177 |
| SIM:SYS-0256 | carried | VNT | a project still extends by plug-in on a public interface, never by fork |
| SIM:SYS-0257 | carried | VNT | Vantage is delivered as a versioned package for both systems, the delivery list without the player |
| SIM:SYS-0258 | carried | VNT | package, port-model and ABI versions stay independent with a compatibility matrix |
| SIM:SYS-0259 | carried | VNT | a project still pins a version range |
| SIM:SYS-0260 | carried | VNT | every release still ships a self-test on a miniature recording |
| SIM:SYS-0261 | carried | VNT | breaking changes still come with a migration guide |
| SIM:SYS-0262 | superseded | D3, D9, ARCH §11 | sim is untouched until Vantage replaces it, Vantage is proven on the lab first, and no second engine is carried |
| SIM:SYS-0263 | carried | VNT | the tool can still print what it will do before doing it |
| SIM:SYS-0264 | carried | VNT | invalid setups are still rejected before the run, naming what to change |
| SIM:SYS-0265 | carried | VNT | the documentation stays sized for a new maintainer |
| SIM:SYS-0266 | carried | VNT | what a component owes Vantage stays a checklist, tried on the lab's components |
| SIM:SYS-0267 | carried | VNT | names stay chosen for debugging; layer and style-token names go with the viewer |
| SIM:SYS-0268 | carried | VNT | the user-facing surface stays closed and countable; panel types go with the viewer |
| SIM:SYS-0269 | carried | VNT | per-message work stays C++ and per-run work Python (ARCH §11 draws the line) |
| SIM:SYS-0270 | carried | VNT | no concept keeps two implementations; the Python run path is not carried (ARCH §11) |
| SIM:SYS-0271 | carried | VNT | the engine never calls back into Python during a run |
| SIM:SYS-0272 | carried | VNT | the engine stays a library with a stable C ABI, now version 3, and the executable stays thin |
| SIM:SYS-0273 | superseded | D13, ARCH §10, ARCH §14 | the live measurement is the only carrier out of the engine and the player transport was rejected |
| SIM:SYS-0274 | carried | VNT | the framework names no function and no component (`R-SIM-1`) |
| SIM:SYS-0275 | carried | VNT | closed vocabularies stay closed; primitive kinds go with the viewer |
| SIM:SYS-0276 | retired | — | a rule on writing requirements, held by R-REQ-3 for every set |
| SIM:SYS-0277 | retired | — | a rule on status, held by R-REQ-6 for every set |
| SIM:SYS-0278 | retired | — | a rule on test identifiers, held by R-REQ-9 for every set |
| SIM:SYS-0279 | superseded | D5 | the Vantage set has no concept layer to trace to |
| SIM:SYS-0280 | carried | VNT | one package for all projects, project content from configuration and plug-ins only |
| SIM:SYS-0281 | carried | VNT | the SIM team still owns the configuration format and schema, the algorithm team the content |
| SIM:SYS-0282 | carried | VNT | a codec still moves bytes and nothing above it names a format or a tool |
| SIM:SYS-0283 | superseded | D10, ARCH §7 | there is no grid step; simulation time is the instant of an event |
| SIM:SYS-0284 | superseded | ARCH §13 | the header keeps one timestamp and the recording keeps reception as `log_time`, so no capture-versus-reception naming remains |
| SIM:SYS-0287 | carried | VNT | resolution is still two passes, probe then emit, through the interfaces the run uses |
| SIM:SYS-0288 | carried | VNT | the probe result is plain data passed as arguments to the graph, coherence and launcher functions |
| SIM:SYS-0289..0291 | carried | VNT | §23a — the safety-evidence stance stays with the tool; the plan and the architecture say nothing else (open question) |
| SIM:SYS-0292 | retired | — | a rule on progress marks, held by R-REQ-6a for every set |

### 4.2 SIM software rows, part 1 (6d)

Scope: SIM:SW-0001..0188

Filled by the first 6d worker: `SW-0001` to `SW-0188`, with the `IMP` rows that
serve them. The split is by UID range, so the two workers never meet in one row.
To dispose: 377 rows (188 `SW`, 189 `IMP`).

| UID | Disposition | Target | Why |
|---|---|---|---|
| SIM:SW-0001 | carried | VNT | the run setup stays flat and fully resolved, with absolute paths and one producer per port; no period is computed, there being no grid |
| SIM:SW-0002 | carried | VNT | the run setup stays the only input of the engine |
| SIM:SW-0003 | carried | VNT | the setup carries each library's resolved path, the pattern it matched and the search order |
| SIM:SW-0004 | carried | VNT | the setup is hashed as `spec_sha256` and the hash goes into the run artifacts |
| SIM:SW-0005 | carried | VNT | the setup keeps a schema version, moved to a new version string, and the engine refuses one outside its range |
| SIM:SW-0006 | superseded | D10, ARCH §2.3 | the setup carries each stage's `clock_period_ns` and no grid step |
| SIM:SW-0007 | carried | VNT | the setup keeps the resolved wiring, with `previous_cycle` marked on an input |
| SIM:SW-0008 | carried | VNT | overrides and faults stay resolved verbs in `mutations[]` |
| SIM:SW-0009 | carried | VNT | the record policy stays a key of each port in the setup |
| SIM:SW-0010 | superseded | D18 | `sampling` and `on_missing` are refused at load; input selection by number is the only policy |
| SIM:SW-0011 | carried | VNT | the setup keeps the resolved ingest table and the absent ports; unit factor, offset and header bindings are gone (`R-SIM-23`, ARCH §3.4) |
| SIM:SW-0012 | carried | VNT | the setup stays a text file with a stable, diffable serialisation |
| SIM:SW-0013 | carried | VNT | per-message work stays in C++ (ARCH §11 draws the line) |
| SIM:SW-0014 | carried | VNT | bulk data stays in engine-owned buffers that Python views without copying |
| SIM:SW-0015 | carried | VNT | a view onto a reused engine buffer is invalidated and access raises |
| SIM:SW-0016 | carried | VNT | the engine never calls back into Python during a run |
| SIM:SW-0017 | superseded | ARCH §3.1, ARCH §10 | the launcher starts an engine run only from a file it has written, and the live measurement replaces the player transport |
| SIM:SW-0018 | carried | VNT | the engine reads no YAML or ingest map and searches no library path; its own rank and loop checks (ARCH §3.2) are not the launcher's wiring validation (open question) |
| SIM:SW-0019 | superseded | D9, ARCH §11 | Vantage is proven on the lab first and no second engine is carried, so no duplicate waits for a proof of equality |
| SIM:SW-0020 | carried | VNT | the check that no capability keeps two implementations stays (`check_no_duplication.py`), run at each gate |
| SIM:SW-0021 | carried | VNT | a codec keeps its small fixed read and write method set |
| SIM:SW-0022 | carried | VNT | a codec still declares its capabilities as data; the capture-time capability is dropped (D22, ARCH §13) |
| SIM:SW-0023 | carried | VNT | codecs are found by registration and matched to a source by extension |
| SIM:SW-0024 | carried | VNT | conversion stays a consequence of the capability table |
| SIM:SW-0025..0027 | carried | VNT | §5.2 — readers stream in bounded batches and decode only when a consumer asks |
| SIM:SW-0028 | carried | VNT | the sidecar index is built on first open and reused |
| SIM:SW-0029 | carried | VNT | the index is keyed by topic |
| SIM:SW-0030 | carried | VNT | a seek is exact and reads nothing before its target |
| SIM:SW-0031 | carried | VNT | selection stays by source, instance and topic; the cycle-identifier axis goes with cycle reconstruction (D10) |
| SIM:SW-0032 | carried | VNT | the reader applies the resolved table to rename and tag only; the unit factor and offset are gone (`R-SIM-23`) |
| SIM:SW-0033 | retired | — | `R-SIM-23` wins: a unit correction is an unversioned algorithm between the recording and the component |
| SIM:SW-0034 | carried | VNT | a payload whose type does not match the port is refused, never coerced |
| SIM:SW-0035 | carried | VNT | several sources are merged under a declared policy; force-alignment is dropped (D18) |
| SIM:SW-0036 | retired | — | a recording has one clock (`RCT:SYS-0039`) and Vantage never re-stamps a message (D18), so a merge has no alignment basis to declare |
| SIM:SW-0037 | retired | — | Vantage never changes a recorded time (D18), so no message is ever marked as re-stamped |
| SIM:SW-0038 | carried | VNT | meta blocks stay declared kinds and unknown ones survive a round trip; plug-in identity goes with the viewer (D13) |
| SIM:SW-0039 | carried | VNT | a recording with no stated provenance reads as unknown (open question) |
| SIM:SW-0040 | moved | RCT:SYS-0040 | the contract says a writer reads no clock and the same arguments give the same bytes |
| SIM:SW-0041 | carried | VNT | the engine's writer writes each step's output as it is produced |
| SIM:SW-0042 | carried | VNT | a merged output loads alone; step 8 states it on top of C6 |
| SIM:SW-0043 | superseded | ARCH §3.4 | a sample holds the four header fields, its arrival time, origin and payload; capture time and the repeat flag are gone |
| SIM:SW-0044 | superseded | ARCH §13 | `R-SIM-14` now has one clock: `source_timestamp_us` in the header, with no capture time kept |
| SIM:SW-0045 | superseded | ARCH §13 | age is simulation time since the value was last written, not derived from a capture time |
| SIM:SW-0046 | carried | VNT | no time quantity inside the engine is floating point |
| SIM:SW-0047 | carried | VNT | a missing input is explicit: an empty input with unknown origin, never a zero fill |
| SIM:SW-0048 | carried | VNT | a value carries its origin from the closed set, including unknown; the contract states only the recorded origins |
| SIM:SW-0049 | superseded | D10, ARCH §7 | a run is one recorded control message, so no cycle is grouped from file timestamps |
| SIM:SW-0050 | superseded | D10, ARCH §7 | cycles are not reconstructed, so no recovery ladder is kept |
| SIM:SW-0051 | superseded | D10, ARCH §7 | there is no ladder to force a rung of |
| SIM:SW-0052 | superseded | ARCH §6 | a sample with no number or time is a badged fallback of the time rule, not a timing-approximated mark |
| SIM:SW-0053 | carried | VNT | a counter gap is detected and counted in the event log, never interpolated (ARCH §3.4, ARCH §6) |
| SIM:SW-0054 | superseded | D18 | inputs are picked by counter, so no repeat flag reaches a component |
| SIM:SW-0055 | superseded | D10, ARCH §7 | rate is not reconstructed from a flat recording, and a declared period no longer schedules |
| SIM:SW-0056 | superseded | D10, ARCH §3.4 | no stage is due or not due; the sample buffer gives the newest sample with its age |
| SIM:SW-0057 | carried | VNT | a component always receives its full port set, now with `control`; the car's empty entry gives an empty input |
| SIM:SW-0058 | carried | VNT | sample buffers are bounded by `buffer_depth` per port |
| SIM:SW-0059 | moved | RCT:SYS-0029 | the contract says bulk payloads are referenced from the cycle by slot and sequence, never inline |
| SIM:SW-0060 | carried | VNT | a static parameter port stays its own port kind in the manifest |
| SIM:SW-0061 | superseded | D10, ARCH §3.3 | the one step loop (`StepOnce`) is the only path; the grid scheduler is replaced |
| SIM:SW-0062 | superseded | D10, ARCH §2.3 | `grid_step_ns` is gone from the setup |
| SIM:SW-0063 | superseded | D10, ARCH §7 | with no grid there is no multiple-of-grid load error |
| SIM:SW-0064 | superseded | D10, ARCH §7 | there is no due test; a run exists only for a ticket |
| SIM:SW-0065 | superseded | D10, ARCH §2.3 | a stage starts by control, a named input port or a clock, set in the run setup |
| SIM:SW-0066 | superseded | D10, ARCH §7 | no schedule is predicted, so there is no disagreement to report; a component that sets no `updated` makes no sample |
| SIM:SW-0067 | superseded | D10, ARCH §2.3 | there is no grid whose size could be pathological |
| SIM:SW-0068..0071 | superseded | D18, ARCH §3.4 | §7.1 — input selection by number is the only policy; sampling and on_missing are refused at load |
| SIM:SW-0072 | carried | VNT | runs of one instant go in rank order, fixed by the setup alone |
| SIM:SW-0073 | superseded | ARCH §2.3 | a `previous_cycle` input replaces the delay counted in grid steps |
| SIM:SW-0074 | carried | VNT | a loop with no previous-cycle edge is a load error naming the loop |
| SIM:SW-0075 | carried | VNT | the orchestrator decides from sample headers and the setup and reads no payload beyond `sig_header` (ARCH §3.2, ARCH §3.4) |
| SIM:SW-0076 | carried | VNT | the engine prints its plan of ranks, triggers and clocks without executing; a step-by-step schedule can no longer be predicted (ARCH §7) |
| SIM:SW-0077 | carried | VNT | the orchestrator reads no wall clock to decide anything |
| SIM:SW-0078 | superseded | D13 | play-rate pacing belongs to the viewer; real-time pacing is parked (ARCH §14) |
| SIM:SW-0079..0083 | carried | VNT | §8.1 — the host opens a module by absolute path, binds its exports by name and checks the ABI version first |
| SIM:SW-0084 | carried | VNT | the host keeps driving the lifecycle, reset being the RESTART run |
| SIM:SW-0085 | superseded | ARCH §3.2 | a reset is a RESTART run, the op mode of a control message, not a separate host call |
| SIM:SW-0086 | superseded | ARCH §3.2 | start and restart reach a component as the op mode of its control message, not as wired lifecycle ports |
| SIM:SW-0087 | carried | VNT | the host passes the resolved bundle path and does not read the bundle |
| SIM:SW-0088..0091 | carried | VNT | §8.3 — conversion and the port set stay driven by the manifest, buffers grow once, a binary without a manifest is quarantined |
| SIM:SW-0092..0096 | carried | VNT | §8.4 — the execution timeout, the failure report, in-process loading and the isolated stage stay |
| SIM:SW-0097 | carried | VNT | the six override verbs stay a closed list |
| SIM:SW-0098 | carried | VNT | an override never creates an entity |
| SIM:SW-0099 | carried | VNT | the address grammar stays `[i]` and `[*]` with no predicate |
| SIM:SW-0100 | carried | VNT | a fixed-slot port is cleared in place and never compacted |
| SIM:SW-0101 | carried | VNT | the five fault verbs stay a closed list |
| SIM:SW-0102 | carried | VNT | a value is decoded and re-encoded once per step per overridden port |
| SIM:SW-0103 | carried | VNT | a value an override touched is tagged overridden at the value |
| SIM:SW-0104 | carried | VNT | the delay fault never writes a timestamp the source did not produce; the capture stamp is gone (ARCH §13) |
| SIM:SW-0105 | carried | VNT | the mutator touches only the ports the setup names |
| SIM:SW-0106 | carried | VNT | every closed vocabulary is compared with its schema on each build |
| SIM:SW-0107 | carried | VNT | an override contradicting the coherence classification is a waiver |
| SIM:SW-0108 | carried | VNT | a fault window is recorded, in steps or time, in the manifest and the event log (ARCH §4) |
| SIM:SW-0109 | carried | VNT | the runner is built from the setup and exposes one entry point that advances the run (`StepOnce`) |
| SIM:SW-0110 | carried | VNT | a measured stage emits its recorded outputs and is never executed |
| SIM:SW-0111 | carried | VNT | `measured` against a recording lacking those outputs is a startup error naming the stage and ports |
| SIM:SW-0112 | carried | VNT | an off stage contributes no ports |
| SIM:SW-0113 | carried | VNT | the ports crossing from measured into simulate are computed and logged before the first step |
| SIM:SW-0114 | moved | RCT:SYS-0037 | the contract says a recording holds a topic for every declared port not excluded, which the runner's offer to the writer must give |
| SIM:SW-0115 | carried | VNT | excluding or decimating a consumed input is a load error at record time |
| SIM:SW-0116 | carried | VNT | the first divergence is detected by step number and recorded with stage and port |
| SIM:SW-0117 | carried | VNT | data after the divergence plus a grace is flagged informational per message |
| SIM:SW-0118 | carried | VNT | a simulated output never changes what a reader returns; the engine stays open-loop |
| SIM:SW-0119 | carried | VNT | progress is checkpointed by step number as the run goes |
| SIM:SW-0120 | carried | VNT | a time slice is a jump before the first step, not a read from the start |
| SIM:SW-0121..0130 | carried | VNT | §11 — the closed error taxonomy, exit codes, structured log and warning summary stay |
| SIM:SW-0131 | carried | VNT | the engine states the ranks, triggers and clocks it loaded, apart from the configuration layer |
| SIM:SW-0132 | carried | VNT | the optional trace stays, one entry per run keyed by step; held is a property of a port value, not of a stage (ARCH §7) |
| SIM:SW-0133 | carried | VNT | the trace is off by default and changes no value |
| SIM:SW-0134 | carried | VNT | the per-run report of time, steps, per-module time and bytes read stays |
| SIM:SW-0135 | carried | VNT | bytes read are counted at the codec boundary per topic |
| SIM:SW-0136 | carried | VNT | no measured duration enters a decision, a value or an output |
| SIM:SW-0137 | carried | VNT | the engine reports each module's path, versions, build and bundle hash |
| SIM:SW-0138 | carried | VNT | break conditions at a step, at a time, on module entry and on a port condition stay |
| SIM:SW-0139 | carried | VNT | a crash writes a minimal reproducer package |
| SIM:SW-0140 | carried | VNT | no diagnostic raises or aborts a run |
| SIM:SW-0141 | carried | VNT | the executable stays thin; it now also holds the supervisor and the isolated stage (ARCH §3.7, ARCH §11) |
| SIM:SW-0142 | carried | VNT | the executable runs a complete simulation with no interpreter loaded |
| SIM:SW-0143 | carried | VNT | the executable prints its process id and pauses before the first step (`--wait-for-attach`) |
| SIM:SW-0144 | carried | VNT | the engine library stays usable without the executable |
| SIM:SW-0145 | carried | VNT | one engine binary serves desktop, batch and CI |
| SIM:SW-0146 | carried | VNT | the engine builds and runs with no graphical toolkit and never prompts |
| SIM:SW-0147 | carried | VNT | a restart after an abnormal end stays explicit, bounded and off by default |
| SIM:SW-0148 | carried | VNT | the executable returns the taxonomy's exit code, never a raw platform code |
| SIM:SW-0149 | carried | VNT | the four configuration layers stay, each value keeping its layer |
| SIM:SW-0150 | carried | VNT | composition, connections and source-signal binding stay separate file kinds; the visual layout file goes with the viewer (D13) |
| SIM:SW-0151 | carried | VNT | every configuration file is validated against a published schema with locating errors |
| SIM:SW-0152 | carried | VNT | an unknown key fails the load with near matches; `sampling` and `on_missing` are now among them (D18) |
| SIM:SW-0153 | carried | VNT | every file carries a schema version and an unknown or missing one is refused |
| SIM:SW-0154 | carried | VNT | references, types and modes are checked at load, never first at run time |
| SIM:SW-0155 | carried | VNT | configuration round-trips to a byte-identical file |
| SIM:SW-0156 | carried | VNT | includes and fragments stay and resolve identically |
| SIM:SW-0157 | carried | VNT | variables resolve at load and every resolution is reported |
| SIM:SW-0158 | carried | VNT | configuration stays in the algorithm team's repository |
| SIM:SW-0159 | carried | VNT | only a file some module reads at run time enters the bundle |
| SIM:SW-0160 | carried | VNT | project agreement (a warning) and ego-parameter agreement (an error) are checked at load |
| SIM:SW-0161 | carried | VNT | geometry comes from the project's configuration per run; drawing is the viewer's |
| SIM:SW-0162 | carried | VNT | a calibration value changes with no rebuild and no host edit |
| SIM:SW-0163 | superseded | D10, ARCH §2.3 | a period survives only as `clock_period_ns` of a stage no recording starts, and the setup holds it in integer nanoseconds |
| SIM:SW-0164 | carried | VNT | the configuration layer opens no payload, recording or binary; the probe pass hands it the data |
| SIM:SW-0165 | carried | VNT | a fast validation checks everything checkable with no recording and no binary |
| SIM:SW-0166 | carried | VNT | a resolved value keeps its file, layer and line for the dry run |
| SIM:SW-0167 | carried | VNT | the graph is built from manifests and the project's active module list |
| SIM:SW-0168 | carried | VNT | two producers for one port are refused at load, naming both |
| SIM:SW-0169 | carried | VNT | a required input with no producer is refused, naming what was considered |
| SIM:SW-0170 | carried | VNT | port types are matched at load |
| SIM:SW-0171 | carried | VNT | a data port never connects to a control port |
| SIM:SW-0172 | superseded | D10, ARCH §7 | there is no base grid to derive |
| SIM:SW-0173 | superseded | D10, ARCH §7 | there is no grid for a period to fit |
| SIM:SW-0174 | carried | VNT | the launcher model finds a stale measured stage over the transitive ancestors |
| SIM:SW-0175 | carried | VNT | the launcher model finds consumption over the transitive descendants |
| SIM:SW-0176 | carried | VNT | the classification stays exactly three outcomes: broken chain, orphan simulation, injection |
| SIM:SW-0177 | carried | VNT | the classification runs on the graph alone and is callable on its own |
| SIM:SW-0178 | carried | VNT | the launcher model blocks a broken chain by default, naming the path and the landing point |
| SIM:SW-0179 | carried | VNT | the launcher model computes remedies including the smallest change |
| SIM:SW-0180 | carried | VNT | a waiver needs a flag and a written reason and the manifest marks the run; "visibly in the player" goes with the viewer (D13) |
| SIM:SW-0181 | carried | VNT | a policy setting can forbid waivers |
| SIM:SW-0182 | carried | VNT | an orphan warns once and is badged `KIND_COMPUTED_NOT_CONSUMED` (ARCH §5) |
| SIM:SW-0183 | carried | VNT | the launcher model closes the gap by default, undoably, and a forced gap is badged |
| SIM:SW-0184 | carried | VNT | a mode change returns a new configuration and leaves the old one |
| SIM:SW-0185 | carried | VNT | the launcher model computes the feasible cuts from the recording's index before any run |
| SIM:SW-0186 | carried | VNT | a stage cannot be set to `measured` when the recording lacks its outputs |
| SIM:SW-0187 | carried | VNT | the bridge from a recording's signal names to ports stays a declared file, parsed once in Python |
| SIM:SW-0188 | carried | VNT | a map declares port, payload type, origin tag and array shape; unit, scale and offset are dropped (`R-SIM-23`) |

### 4.3 SIM software rows, part 2 (6d)

Scope: SIM:SW-0189..0429

Filled by the second 6d worker: `SW-0189` to `SW-0429`, with the `IMP` rows that
serve them. To dispose: 373 rows (187 `SW`, 186 `IMP`).

| UID | Disposition | Target | Why |
|---|---|---|---|
| SIM:SW-0189 | superseded | ARCH §3.4, ARCH §6 | the header is read from `sig_header` at the door of every sample buffer, so a map binds no header field (as SIM:SYS-0015) |
| SIM:SW-0190 | carried | VNT | `absent:` in the map still names a port a family never carries, and a cut that needs it is refused at load with the reason |
| SIM:SW-0191 | carried | VNT | recording families are still recognised by declared match rules |
| SIM:SW-0192 | carried | VNT | a port claimed by two maps is still an authoring error naming both |
| SIM:SW-0193 | retired | — | `R-SIM-23` wins: a map renames and tags only, and a unit conversion is an unversioned algorithm (as SIM:SW-0033) |
| SIM:SW-0194 | carried | VNT | ingest maps are still resolved from beside the component library, never from a checkout |
| SIM:SW-0195 | carried | VNT | applying a map still creates no value, element or entity the source did not carry |
| SIM:SW-0196 | carried | VNT | each source in a recording is still identified by its declared identity tuple before any interpretation is chosen |
| SIM:SW-0197 | carried | VNT | the description artifact is still resolved in a declared order and the tier used is reported per source |
| SIM:SW-0198 | carried | VNT | each description type still declares the versions it accepts and refuses others, naming both |
| SIM:SW-0199 | carried | VNT | static parameter data still comes from the recording first, then from a configured directory |
| SIM:SW-0200 | carried | VNT | a decision about a recording still goes to a sidecar and the recording stays byte-identical |
| SIM:SW-0201 | carried | VNT | the order in which sidecars apply is still declared and every applied one is reported |
| SIM:SW-0202 | carried | VNT | a map still admits no computation (`R-SIM-23`); the factor and offset it once allowed are gone with SIM:SW-0193 |
| SIM:SW-0203 | carried | VNT | one resolver still turns a stem and search directories into an absolute library path, in Python |
| SIM:SW-0204 | carried | VNT | the setup carries the search order, the pattern and the chosen path, so resolution still reports what it did |
| SIM:SW-0205 | carried | VNT | the launcher still tells whether a library exists for the running platform without loading it |
| SIM:SW-0206 | carried | VNT | one configuration bundle per component and build is still packed beside the library with its hash |
| SIM:SW-0207 | carried | VNT | a bundle still resolves beside its library, an explicit path wins and a project mismatch warns |
| SIM:SW-0208 | superseded | D13 | which bundle a viewer reads is the viewer's design; the live measurement lists each bundle with its hash |
| SIM:SW-0209 | superseded | D13 | visualization plug-ins are the viewer's; ingest maps and bundles beside the library stay (as SIM:SYS-0255) |
| SIM:SW-0210 | carried | VNT | the configuration bundle's bytes stay embedded in an artifact (SIM:SYS-0197); a plug-in's identity goes with the viewer (D13) |
| SIM:SW-0211 | superseded | D13 | reading a plug-in's API version before import is the viewer's plug-in rule |
| SIM:SW-0212 | carried | VNT | every artifact is still resolved once per run and the resolved value is what everything uses |
| SIM:SW-0213 | carried | VNT | a re-execution is still pinned to a library hash, and a locally built library is reported as unpinnable |
| SIM:SW-0214 | carried | VNT | every ordered resolution still uses one implementation of the ordered tier with the tier reported; the plug-in tier goes with the viewer (D13) |
| SIM:SW-0215 | carried | VNT | the run manifest stays; its timing model, reset policy and timing-recovery rung entries go with the grid and the ladder (D10, D17) |
| SIM:SW-0216 | carried | VNT | a past run is still reproducible from its manifest alone |
| SIM:SW-0217 | carried | VNT | every artifact still embeds the run manifest |
| SIM:SW-0218 | carried | VNT | the manifest still carries each reproducibility dimension as its own field |
| SIM:SW-0219 | carried | VNT | every override, fault and bundle-value override in force is still a structured record in the manifest |
| SIM:SW-0220 | carried | VNT | a manifest field that cannot be filled still reads `unknown` |
| SIM:SW-0221 | carried | VNT | the run identifier is still derived from the run's own inputs |
| SIM:SW-0222 | carried | VNT | a manifest is still written for a run that failed, crashed or timed out, with the last completed step |
| SIM:SW-0223 | carried | VNT | a run with every exporter disabled still writes its manifest |
| SIM:SW-0224 | carried | VNT | the manifest keeps the coherence verdict and the divergence point |
| SIM:SW-0225 | carried | VNT | the volume estimate before a run stays with the launcher, computed from the record policy |
| SIM:SW-0226 | carried | VNT | the hash of the tolerance declaration in force stays in the manifest |
| SIM:SW-0227 | carried | VNT | a manifest still appears complete or not at all |
| SIM:SW-0228 | carried | VNT | the manifest schema stays versioned and published |
| SIM:SW-0229 | carried | VNT | command-line modules still parse arguments and delegate only |
| SIM:SW-0230 | carried | VNT | every capability stays reachable from a short script |
| SIM:SW-0231 | carried | VNT | every verb keeps a scripted equivalent producing the same artifacts |
| SIM:SW-0232 | carried | VNT | the verb set stays closed, published and counted per release |
| SIM:SW-0233 | carried | VNT | produce, execute-an-existing-recording and do-both stay distinct verbs; only `sim run` in-process is not carried (open question) |
| SIM:SW-0234 | carried | VNT | every verb that executes keeps a dry-run path that prints the plan |
| SIM:SW-0235 | carried | VNT | a long operation still reports progress and accepts cancellation |
| SIM:SW-0236 | carried | VNT | each run still writes its own artifact directory |
| SIM:SW-0237 | carried | VNT | an artifact directory stays self-contained; opening it in a viewer is that design's work |
| SIM:SW-0238 | carried | VNT | the interactive, batch and CI paths still start the engine through one code path with one setup format |
| SIM:SW-0239 | carried | VNT | the scripting API keeps its own version, independent of the recording format and the ABI |
| SIM:SW-0240 | carried | VNT | no scripted use needs generated bindings or a checkout (`R-SIM-11`) |
| SIM:SW-0241 | carried | VNT | batch runs stay separate processes; the threads of ARCH §8 live inside one engine run |
| SIM:SW-0242 | carried | VNT | ok, fail, crash and timeout stay four outcomes, judged from outside the worker |
| SIM:SW-0243 | carried | VNT | a failing run still does not stop the batch |
| SIM:SW-0244 | carried | VNT | the batch aggregate still reconciles with the individual manifests |
| SIM:SW-0245 | carried | VNT | a crash still records its recording, setup, last step, stderr and run id |
| SIM:SW-0246 | carried | VNT | the processing watchdog stays as the per-call execution timeout with its own threshold |
| SIM:SW-0247 | carried | VNT | the supervisor's deadline and the live measurement's heartbeat stay the separate check that the worker still responds (ARCH §9) |
| SIM:SW-0248 | carried | VNT | per-run wall-time and memory limits stay in the run setup and are reported distinctly |
| SIM:SW-0249 | carried | VNT | a batch is still resumable and re-executes no completed run |
| SIM:SW-0250 | carried | VNT | a sweep over N values still gives N runs differing in exactly the swept value |
| SIM:SW-0251 | superseded | D17 | a stage restarts on its first run and after a jump and each recording has its own process, so no reset mode or timing is chosen |
| SIM:SW-0252 | carried | VNT | the read-error behaviours of a batch stay a closed set with skipped packages counted |
| SIM:SW-0253 | carried | VNT | a read retry stays bounded and recorded |
| SIM:SW-0254 | carried | VNT | an index built for a recording is still reused by every batch entry |
| SIM:SW-0255 | carried | VNT | the developer face, the supervised batch face and the isolated stage stay (ARCH §9) |
| SIM:SW-0256 | carried | VNT | a batch is still one run setup plus a recording list, with no format of its own |
| SIM:SW-0257 | carried | VNT | a recording's content hash stays its identity as `sources[].sha256` |
| SIM:SW-0258 | carried | VNT | the file and group identifiers are read by the preparation tools where the format has them; no contract row states them (open question) |
| SIM:SW-0259 | carried | VNT | the integrity check still covers time, counter continuity, checksums and rate stability |
| SIM:SW-0260 | carried | VNT | integrity results stay available as a gate that refuses a damaged recording |
| SIM:SW-0261 | carried | VNT | checksum verification stays selectable and its cost is reported |
| SIM:SW-0262 | carried | VNT | recovery of a damaged recording stays explicit and marks everything derived from it |
| SIM:SW-0263 | carried | VNT | extract by time range and by port or source stays |
| SIM:SW-0264 | carried | VNT | extracting several sections keeps a declared naming rule and the complement |
| SIM:SW-0265 | carried | VNT | conversion stays a consequence of the capability table and refuses naming the missing capability |
| SIM:SW-0266 | carried | VNT | inspect stays the listing of ports, rates, sources and time range, equal to what a run reads |
| SIM:SW-0267 | carried | VNT | lineage of a derived recording is Vantage's metadata on top of C6 (as SIM:SYS-0226); step 8 states it |
| SIM:SW-0268 | carried | VNT | the preparation tools stay usable with no library and no engine |
| SIM:SW-0269 | retired | — | its parent SIM:SYS-0229 is retired: volume is estimated from the record policy, so no per-cycle size budget is kept |
| SIM:SW-0270 | carried | VNT | no preparation operation modifies its input recording |
| SIM:SW-0271 | carried | VNT | the dry run stays: it prints the resolved setup with each value's layer, and the plan of ranks, triggers and clocks, loading nothing |
| SIM:SW-0272 | carried | VNT | the duration estimate stays reported with the factor it was measured to fall within |
| SIM:SW-0273 | superseded | D13 | the one evidence producer read a `Session` for the evidence panel, which goes with the viewer (as SIM:SYS-0154) |
| SIM:SW-0274 | superseded | D13 | the evidence record of a primitive, layer or plotted sample belongs to the viewer (R-SIM-25 is moved out, ARCH §13) |
| SIM:SW-0275 | superseded | D13 | the evidence chain from a layer to its ports belongs to the viewer |
| SIM:SW-0276 | superseded | D13 | where the evidence chain stops is the viewer's rule |
| SIM:SW-0277 | carried | VNT | the environment report (doctor) stays and never raises; plug-in inspection goes with the viewer |
| SIM:SW-0278 | carried | VNT | name resolution with did-you-mean stays for the launcher's names; layer and style-token names go with the viewer |
| SIM:SW-0279 | carried | VNT | a probe still reads a library's ports, types, periods and schemas from its manifest |
| SIM:SW-0280 | carried | VNT | comparing two runs still names the first diverging step, port and field and the bound in force |
| SIM:SW-0281 | carried | VNT | the comparison axis is still derived from the two manifests, and a pair differing in more than one dimension is inconclusive |
| SIM:SW-0282 | carried | VNT | a reproducibility comparison is still over decoded port values, now called equal outputs |
| SIM:SW-0283 | carried | VNT | two axes stay exact gates and two stay measured; the thread-count axis joins the gates (ARCH §13) |
| SIM:SW-0284 | carried | VNT | tolerance is still declared once per component and field with a mandatory reason, default exact |
| SIM:SW-0285 | carried | VNT | an internal port still becomes recorded output by being named in configuration |
| SIM:SW-0286 | carried | VNT | every diagnostic stays callable as a function returning data |
| SIM:SW-0298 | moved | RCT:SYS-0026 | the contract says the writer never waits for a reader, so a reader may attach, detach and re-attach with no effect on the run |
| SIM:SW-0334 | carried | VNT | the launcher window offers `measured` only for a stage whose outputs the recording holds; the rule is the launcher model's (SIM:SW-0186) |
| SIM:SW-0341 | carried | VNT | the launcher window shows a stage's mode and implementation and lets both be chosen (D21) |
| SIM:SW-0342 | carried | VNT | the launcher model classifies coherence as the selection changes and blocks a broken chain; the window shows the remedies (D21) |
| SIM:SW-0343 | carried | VNT | the launcher writes the run setup and holds no state that is not in that file |
| SIM:SW-0344 | carried | VNT | the launcher window shows which libraries are available, their versions and which lack a binary for the platform |
| SIM:SW-0345 | carried | VNT | the launcher window shows per recording which stages could be set to `measured`; the rule is the launcher model's (ARCH §3.1) |
| SIM:SW-0346 | carried | VNT | adding recordings and starting stay in the window; selecting a layout goes with the viewer (D13) |
| SIM:SW-0347 | carried | VNT | the launcher and the command line still share one configuration schema, with no launcher-only fields |
| SIM:SW-0348 | carried | VNT | the common changes stay a declared set completable within a time budget; changing the layout goes with the viewer (D13) |
| SIM:SW-0349 | superseded | D13, ARCH §10, ARCH §14 | the player-to-engine transport is replaced by the live measurement, and the in-process transport was rejected |
| SIM:SW-0350 | superseded | D13, ARCH §10 | a player reaching into engine memory is moot: a reader maps the live measurement read-only (RCT:SYS-0027) |
| SIM:SW-0351 | superseded | ARCH §10 | the live measurement is shared memory for control and bulk alike, with no separate channel |
| SIM:SW-0352 | moved | RCT:SYS-0026 | the contract says a run with a reader suspended gives the same steps and byte-identical outputs as one with none |
| SIM:SW-0353 | moved | RCT:SYS-0026 | the contract says the writer completes every step without waiting on any reader; dropping frames is the viewer's (D13) |
| SIM:SW-0354 | superseded | ARCH §10 | the live measurement carries its own descriptor set and a reader names no codec, world model or component |
| SIM:SW-0355 | moved | RCT:SYS-0030 | the contract says a reader of another layout version refuses to attach, naming both versions |
| SIM:SW-0356 | superseded | ARCH §9, ARCH §10 | a reader sees the heartbeat stop and reports the writer gone at its last step, and the supervisor seals the outcome |
| SIM:SW-0357 | carried | VNT | the framework's shipped source still names no component and no function (`R-SIM-1`) |
| SIM:SW-0358 | carried | VNT | reader, exporter and module stay extension points with a versioned interface and kit; the visualization point goes with the viewer (D13) |
| SIM:SW-0359 | carried | VNT | adding a plug-in of a kept kind still needs no edit to a framework file |
| SIM:SW-0360 | carried | VNT | package, port-model and ABI versions stay independent with a generated matrix; the plug-in API version goes with the viewer (D13) |
| SIM:SW-0361 | carried | VNT | every closed set stays enumerable and is compared with its schema on every build |
| SIM:SW-0362 | carried | VNT | the package stays identical across projects, with project content from configuration and plug-ins only |
| SIM:SW-0363 | carried | VNT | one configuration set still runs unchanged on both operating systems |
| SIM:SW-0364 | carried | VNT | path handling and dynamic loading stay abstracted at one place each |
| SIM:SW-0365 | carried | VNT | floating-point flag expectations stay declared and a library built outside them warns at load |
| SIM:SW-0366 | carried | VNT | the reference suite still runs on both platforms and a difference is a defect |
| SIM:SW-0367 | carried | VNT | every measured claim still names its platform and shell |
| SIM:SW-0368 | superseded | ARCH §8 | runs of one rank may run in parallel inside a step; the thread count must not change a result, which ARCH §8 keeps by five facts |
| SIM:SW-0369 | carried | VNT | per-step cost and per-worker throughput stay budgeted with a number (as SIM:SYS-0234) |
| SIM:SW-0370 | retired | — | a rule that every check ships a planted-violation test, held by R-REQ-9 for every set |
| SIM:SW-0371 | retired | — | a rule that a cited test identifier appears in its test, held by R-REQ-9 for every set |
| SIM:SW-0372 | superseded | D5 | the Vantage set has SYS and IMP layers only, so no software requirement exists to trace |
| SIM:SW-0373 | retired | — | a rule on status, held by R-REQ-6 for every set |
| SIM:SW-0374 | carried | VNT | every new source file still carries the file-header block; the gate is `check_headers.py` with the token `VANTAGE` |
| SIM:SW-0375 | carried | VNT | a name stays the same string in the log, the configuration and the launcher window |
| SIM:SW-0376 | retired | — | a rule for the order of the sim v2 build; this program's order and gates are in the plan section 5 (as SIM:SYS-0201) |
| SIM:SW-0377 | carried | VNT | every release still ships a self-test on a bundled miniature recording through a stub chain |
| SIM:SW-0378 | carried | VNT | a stub implementation on the generic ABI stays so the suite runs with no compiled component |
| SIM:SW-0379 | carried | VNT | what a component owes Vantage stays a checklist, tried on the lab's components |
| SIM:SW-0380 | carried | VNT | the documentation set's size is still measured and reported per release |
| SIM:SW-0381 | carried | VNT | the release-one readers (vehicle measurement, bench capture, interchange) are still Vantage's (as SIM:SYS-0011) |
| SIM:SW-0382 | carried | VNT | the image-folder reader and the synthetic-scenario reader stay as recording readers |
| SIM:SW-0383 | carried | VNT | a reader produces port values and a component consumes them, and neither addresses the other |
| SIM:SW-0384 | carried | VNT | export to the interchange format, a columnar text and a replayable recording stays with the recording I/O |
| SIM:SW-0385 | carried | VNT | an export keeps every header field and carries origin from its source |
| SIM:SW-0386 | carried | VNT | an export still selects ports by manifest name and time range and flattens to a declared schema |
| SIM:SW-0387 | superseded | ARCH §6, ARCH §13 | the header has one timestamp and inputs are chosen by number, so no choice of timestamp is recorded per port |
| SIM:SW-0388 | carried | VNT | the versioned port catalogue stays, and every port in a configuration resolves against it at load |
| SIM:SW-0389 | carried | VNT | a port's identity stays independent of the component that produces it |
| SIM:SW-0390 | carried | VNT | a project still extends the catalogue in its own namespace without a clash |
| SIM:SW-0391 | carried | VNT | the checked-in manifest stays the authority, and regeneration reports and never overwrites |
| SIM:SW-0392 | carried | VNT | the generic-ABI shim stays generated from declared data and never checked in (`R-SIM-22`) |
| SIM:SW-0393 | carried | VNT | a component still reads no wall clock; time arrives in the control header and the port headers |
| SIM:SW-0394 | carried | VNT | a component declares non-deterministic behaviour in its manifest and a declared one marks the run non-reproducible |
| SIM:SW-0395 | retired | — | `R-SIM-7` puts integrating a signal into a component under test; no part of Vantage re-integrates the ego pose (as SIM:SYS-0108) |
| SIM:SW-0396 | retired | — | component state is not exposed by the ABI and the state snapshot is parked (RCT P1), so no cycle restarts from a saved state (as SIM:SYS-0218) |
| SIM:SW-0397 | carried | VNT | symbol resolution stays documented and ready-made debugger launch configurations ship |
| SIM:SW-0398 | carried | VNT | a unit configuration stays self-contained, exposing named ports that a top-level file composes |
| SIM:SW-0399 | carried | VNT | the SIM team still owns the configuration format and the algorithm team the content |
| SIM:SW-0400 | carried | VNT | mode stays overridable per output port, a port of a simulate stage being sourced from the recording |
| SIM:SW-0401 | carried | VNT | a component stays instantiable more than once, with distinct port namespaces per instance |
| SIM:SW-0402 | carried | VNT | the previous-cycle inputs, the only latency left, stay recorded in the manifest and the description (as SIM:SYS-0079) |
| SIM:SW-0403 | superseded | D13 | the provenance query is the evidence producer, which goes with the viewer |
| SIM:SW-0406 | carried | VNT | a project still pins a package version range and the tool refuses to run outside it |
| SIM:SW-0407 | carried | VNT | a breaking change still ships a migration guide and, where possible, a migration command |
| SIM:SW-0408 | retired | — | a rule on writing requirements, held by R-REQ-3 for every set |
| SIM:SW-0409 | carried | VNT | the probe pass stays the one place the configuration layer opens a library or a recording, bounded by symbol |
| SIM:SW-0410 | carried | VNT | the probe pass still hands the recording index and the manifests on as plain data; the timing rung is gone with the ladder (D10) |
| SIM:SW-0411 | carried | VNT | the graph, coherence and ingest matching still take the index and manifests as arguments and open nothing |
| SIM:SW-0412 | carried | VNT | the setup keeps the hash of each recording read and the engine refuses a recording whose hash differs |
| SIM:SW-0413 | superseded | D10, ARCH §7 | simulation time is the instant of an event, not a count of grid steps |
| SIM:SW-0414 | superseded | D10, ARCH §7 | no rate is reconstructed from a recording and no declared period schedules a run, so no rate disagreement exists to report |
| SIM:SW-0415..0417 | carried | VNT | §29.1 — the artifact-kind declaration, the generated use-constraints statement and the check that a named detecting check exists stay with the tool |
| SIM:SW-0418 | retired | — | a rule on progress marks, held by R-REQ-6a for every set |
| SIM:SW-0419 | carried | VNT | the I/O library stays linkable alone with no first-party package beyond it (`check_engine_boundary.py`) |
| SIM:SW-0420 | carried | VNT | the port catalogue's version stays semantic and a major mismatch refuses to load |
| SIM:SW-0421 | carried | VNT | a codec for a scalar-per-field format still rebuilds the real message by reflection on a supplied descriptor |
| SIM:SW-0422 | carried | VNT | the embeddable ABI still builds its runner with a real writer when the setup declares recording output |
| SIM:SW-0423 | carried | VNT | the embeddable ABI still applies the declared overrides and never ignores them |
| SIM:SW-0424 | carried | VNT | an override's address is still the port name every other consumer of a port value uses |
| SIM:SW-0425 | superseded | D13, ARCH §10 | the in-process viewer pump is the viewer's, and the live measurement writer replaces the transport publisher; `simEngineStepOnce` keeps its name (ARCH §7) |
| SIM:SW-0426 | superseded | D13 | turning engine frames into the viewer's own ticks is the viewer's design |
| SIM:SW-0427 | superseded | D13 | the windowed viewer on its own engine thread is the viewer's design |
| SIM:SW-0428 | superseded | D2, D13 | the viz-dependent app and its launcher script are not carried over |
| SIM:SW-0429 | carried | VNT | the launcher window lets a stage be set to `measured`, `simulate` or `off`, and the engine runs the setup file written from that choice (D21) |

### 4.4 PARITY rows (6e)

Scope: PARITY:STK, PARITY:SYS, PARITY:SW

Filled by 6e: the parity set in `docs/v2/parity/`. To dispose: 163 rows (16 `STK`,
39 `SYS`, 54 `SW`, 54 `IMP`).

| UID | Disposition | Target | Why |
|---|---|---|---|
| PARITY:STK-0001..0002, PARITY:STK-0016 | carried | VNT | §1 — feeding a port from ordered recorded names, saying which name fed it, and taking ports from more than one recording stay with the ingest map and the run setup |
| PARITY:STK-0003 | carried | VNT | a build is still compared with a reference and the first divergence shown (as SIM:SYS-0205); two engine runs on one recording do it, not two builds in one process |
| PARITY:STK-0004 | carried | VNT | the launcher window keeps one action that sets a chosen stage to `simulate` and every other to `measured` (D21) |
| PARITY:STK-0011 | carried | VNT | the launcher window keeps a computed mixed state for a group whose stages disagree (D21) |
| PARITY:STK-0005 | carried | VNT | the launcher window keeps the copied command line, which does exactly what start does (D21) |
| PARITY:STK-0012 | superseded | D13, ARCH §10 | a running engine run is read through the live measurement and the inspector; playback and marks on a running session are the viewer's design |
| PARITY:STK-0006, PARITY:STK-0008..0009, PARITY:STK-0013, PARITY:STK-0015 | superseded | D13 | §4 — transport, speed, step units, named ranges and marks are the viewer's design |
| PARITY:STK-0007 | carried | VNT | the log keeps one counted entry for a message repeating every step, so earlier messages stay visible |
| PARITY:STK-0010 | superseded | D13 | a plug-in is a viewer plug-in; its identity is the viewer's design (as SIM:SW-0210) |
| PARITY:STK-0014 | carried | VNT | a recording the engine writes still carries the configuration it ran with (as SIM:SYS-0197); rendering with it is the viewer's |
| PARITY:SYS-0001..0003, PARITY:SYS-0005, PARITY:SYS-0029..0030, PARITY:SYS-0034 | carried | VNT | §1 — ordered addresses per port, the matched address in the manifest, named sources with a default, a refused unknown source and an unresolved port stay with the ingest map and the run setup |
| PARITY:SYS-0006 | superseded | ARCH §14 | two builds stepped in one process are parked (ARCH §14); comparing two builds is two engine runs over one recording, compared by port values (R-SIM-24) |
| PARITY:SYS-0007 | carried | VNT | the first diverging step, port and field is still reported, or none (as SIM:SYS-0205) |
| PARITY:SYS-0008 | superseded | ARCH §14 | a reference build staged for a side-by-side run is parked with it (ARCH §14); each build is its own engine run, compared by port values (R-SIM-24) |
| PARITY:SYS-0038 | superseded | ARCH §14 | both builds' outputs under one recording's topics belong to the parked side-by-side run (ARCH §14); each engine run writes its own recording (R-SIM-24) |
| PARITY:SYS-0009 | carried | VNT | the launcher window keeps the one action that isolates a stage (D21) |
| PARITY:SYS-0010 | carried | VNT | the launcher window keeps the unselectable mixed state of a group (D21) |
| PARITY:SYS-0011 | carried | VNT | the launcher window keeps the copyable command line for the setup it wrote (D21) |
| PARITY:SYS-0012 | carried | VNT | the setup file written from the selection and the selection resolve to the same run setup; the launcher holds no state outside the file (as SIM:SYS-0160) |
| PARITY:SYS-0013 | superseded | D13, ARCH §10 | a script reads a running engine run through the live measurement; playback and marks on a session are the viewer's |
| PARITY:SYS-0014 | superseded | D13, ARCH §10 | the live control surface it constrains is retired with `pyapi/live.py`; the live measurement replaces the running session |
| PARITY:SYS-0015 | superseded | D13 | the nine transport actions are the viewer's design; the engine offers `simEngineSeek` only (ARCH §14) |
| PARITY:SYS-0031 | superseded | D13 | the choice of the step count of a transport action is the viewer's design |
| PARITY:SYS-0016 | superseded | D13 | play speed and the achieved rate are the viewer's; real-time pacing is parked (ARCH §14) |
| PARITY:SYS-0032 | superseded | D13 | showing requested against achieved speed is the viewer's design |
| PARITY:SYS-0017 | superseded | D13 | the five step granularities belong to the viewer's transport |
| PARITY:SYS-0033 | superseded | D13 | refusing a step granularity the recording cannot support belongs to the viewer's transport |
| PARITY:SYS-0018 | superseded | D13 | showing the selected cycle belongs to the viewer |
| PARITY:SYS-0019 | superseded | D13 | landing a cycle step on one run's inputs belongs to the viewer's transport |
| PARITY:SYS-0020 | superseded | D13 | naming a range of a recording is the viewer's act (open question: where it is stored) |
| PARITY:SYS-0039 | superseded | D13 | the timebase of a named range belongs with the viewer's ranges (open question: where it is stored) |
| PARITY:SYS-0021 | superseded | D13 | named ranges are the viewer's; the engine keeps only the time slice (SIM:SYS-0232) |
| PARITY:SYS-0022 | superseded | D13 | annotations and classifications are marks made in a viewer (open question: where they are stored) |
| PARITY:SYS-0023 | carried | VNT | the batch loop chooses which recordings to run by their tags; step 8 decides where the tags come from (recording metadata or later viewer marks) |
| PARITY:SYS-0040 | superseded | D13 | author and time of a mark belong with the viewer's marks (open question) |
| PARITY:SYS-0024 | carried | VNT | the log keeps one counted entry for an identical repeated message above a flood threshold |
| PARITY:SYS-0035 | carried | VNT | the log keeps one entry saying that counting began, naming the message and the threshold |
| PARITY:SYS-0025 | superseded | D13 | a plug-in is a viewer plug-in; its identity is the viewer's design (as SIM:SW-0210) |
| PARITY:SYS-0036 | superseded | D13 | the identity of the deployed viewer plug-in copy goes with the viewer |
| PARITY:SYS-0026 | superseded | D13 | where a viewer plug-in's identity is shown is the viewer's design |
| PARITY:SYS-0027 | carried | VNT | a recording the engine writes still embeds the configuration bundle's bytes (as SIM:SYS-0197) |
| PARITY:SYS-0037 | carried | VNT | the embedded bundle's hash is recorded and a mismatch reported |
| PARITY:SYS-0028 | superseded | D13 | reporting a missing bundle instead of reading a local one is a rule for the reader that draws the recording |
| PARITY:SW-0001..0003 | carried | VNT | §1 — the ingest map keeps a port-keyed entry with an ordered address list, names the port and field of a bad entry and parses declared holes beside provided ports |
| PARITY:SW-0004..0007 | carried | VNT | §2 — the resolver keeps trying candidates in order, retains the chosen one, skips a type mismatch without converting and tells unresolved from absent |
| PARITY:SW-0008..0010, PARITY:SW-0054 | carried | VNT | §3 — named sources with one default, one source per port, an explicit assignment over the default and a refused unknown name stay with the run setup |
| PARITY:SW-0011 | carried | VNT | the run setup is still the same whatever order the choices were made in |
| PARITY:SW-0012 | carried | VNT | `spec_sha256` stays unchanged by re-emission and changes with any field |
| PARITY:SW-0013 | superseded | ARCH §14 | the setup's reference build identity belongs to the parked side-by-side run (ARCH §14) |
| PARITY:SW-0014 | carried | VNT | the manifest still records, per port, the address the ingest matched |
| PARITY:SW-0015 | carried | VNT | the manifest still records the bundle's hash as packed and the hash of the embedded bytes |
| PARITY:SW-0016 | superseded | ARCH §14 | the manifest's reference build hash belongs to the parked side-by-side run (ARCH §14) |
| PARITY:SW-0017..0021 | carried | VNT | §5 — the isolate operation, the computed group state, one setup from file or selection, and their display in the window stay with the launcher model and window (D21) |
| PARITY:SW-0022..0026 | superseded | D13 | §6 — transport actions, step counts and measured play rate are the viewer's design (pacing is parked, ARCH §14) |
| PARITY:SW-0027..0032 | superseded | D13, ARCH §7 | §7 — step granularity and cycles are the viewer's, and the Python cycle model is not carried (`io/cycles.py`) |
| PARITY:SW-0033..0038 | superseded | D13 | §8 — named ranges and the two kinds of mark are the viewer's design (open question: where they are stored) |
| PARITY:SW-0039..0041 | carried | VNT | §9 — the log keeps a dedupe key, a count per key and one entry when the flood threshold is crossed |
| PARITY:SW-0042..0044, PARITY:SW-0053 | superseded | D13 | §10 — plug-in identity belongs to the viewer plug-ins, which move out with the viewer (as SIM:SW-0210) |
| PARITY:SW-0045 | carried | VNT | the bundle's bytes are still written into the recording the engine makes (as SIM:SW-0210) |
| PARITY:SW-0046 | carried | VNT | the hash of the embedded bytes is stored and a mismatch reported |
| PARITY:SW-0047 | superseded | D13 | representing a missing bundle instead of reading a disk copy is a rule for the reader that draws the recording |
| PARITY:SW-0048 | superseded | ARCH §14 | one input set fed to two builds each step is the parked side-by-side run (ARCH §14); the retired `engine/refrun.py` was its Python form |
| PARITY:SW-0049 | carried | VNT | the first difference is still kept with step, port and field (as SIM:SW-0116); the divergence latch does it |
| PARITY:SW-0050 | superseded | ARCH §14 | recording two builds' outputs side by side belongs to the parked side-by-side run (ARCH §14) |
| PARITY:SW-0051..0052 | superseded | D13, ARCH §10 | §13 — script control of a running session ended with `pyapi/live.py`; the live measurement replaces it |

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
