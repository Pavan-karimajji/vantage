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
