# VANTAGE — Test Specification

**One file, one layer.** `SYT-<area>-nn` and `ANL-nn` verify `VANTAGE_System_Requirements.md`
(areas declared there: `RUN`, `ORC`, `SEL`, `STP`, `THR`, `EQO`, `LMW`, `INS`, `SUP`). A test cites its
requirement's `Accept` by UID and never restates it (`R-REQ-4`); every case states its FAIL
side (`R-REQ-5`). Part 8a: the orchestrator (`C1`); part 8b: the live measurement writer, the
inspector and the supervisor (`C2`). The lab cases named in the steps are those
of `VANTAGE_Lab_Design.md` §6, written topology, scenario (`base` unless named) and resim case.

## Fixture catalogue

| Fixture | What it is |
|---|---|
| `F-CAT` | Every topology of the lab catalogue built: each scenario's recording, each resim case's run setup, and the libraries, found by `tests/support/lab_cases.py`. An *exact case* is a resim case whose scenario expects `exact` and that is not `hang` or `crash` (they need the supervisor, part 8b) |
| `F-CASE` | One named lab case of `F-CAT` |
| `F-SETUP-EDIT` | An `F-CASE` run setup copied by the test with the one change its steps name (`edit_setup`) |
| `F-REC-EDIT` | An `F-CASE` or `F-RUN-CONFIG` recording rewritten by the test through the Python writer in `interfaces` with the one edit its steps name: a split into files, messages removed or changed, a message's logging time moved, a `manifest` key changed or removed, a cut (`edit_recording`) |
| `F-ENGINE` | `simengine` run as a process on a setup with `outputs.path` set: the engine-run recording, the event log lines, the printed plan and the exit code |
| `F-TAP` | `tests/support/step_tap` run on a setup: one line per engine step with its number, simulation time and badges; optionally one jump, at 500 ms to the case's `jump_to_ms` unless the steps say otherwise |
| `F-PROBE` | The exec probe (`tests/fixtures/exec_probe`) put by the test in place of named stages' libraries, one copy per path the steps name, and its call log |
| `F-COMPARE` | The lab's comparator, `lab_tools.compare.equal_outputs` (`VANTAGE_Lab_Design.md` §6.4), over two recordings; independent of Vantage's own comparison |
| `F-RUN-CONFIG` | A run configuration (a pipeline file) for a stub chain on the generic ABI whose `run_setup:` block and stage keys give every run-setup value, copied by the test with the one change its steps name |
| `F-SRC` | `include/simcore`, `src/simcore` and `src/simengine` as checked in, and per check a copy with one planted violation |
| `F-TICK` | `tests/support/control_tick` (`IMP-0055`) run with a clock period and a tick number: the `measurement_counter` of the control `ControlWriter::Write` builds for that tick, with no run and no library |
| `F-RENUMBER-LIB` | `running_example` `renumber_lib` `shifted` (`VANTAGE_Lab_Design.md` `LAB-WP-10`): `A`'s bundle sets `LAB_A_RENUMBER`, so `A`'s own code writes its data outputs' `measurement_counter` shifted from its control's |
| `F-LM-TWICE` | The contract's fixture of that name (`RCT_Test_Spec.md`) made on `running_example`: `B`'s controls taken in pairs, the first of each pair logged at the instant of the second, so a step holds two `B` runs; run on `F-TAP` or `F-LM-HELD` |
| `F-CAM` | The contract's fixture of that name: the `camera` topology and its `base` recording, the case setting `bulk: [source.Cam]` unless a step says otherwise (`VANTAGE_Lab_Design.md` §6.3) |
| `F-LM-HELD` | An `F-CASE` run on `F-ENGINE` with `outputs.livemeas`, a ring that holds the whole run (the case's `livemeas: {cycle_slot_count: n}`, n at least its number of steps), and one more simulated stage: `held_probe` (`IMP-0088`), reading and triggered by a source port that already triggers a stage of the case, and read by no stage, so it adds no step and every other stage's outputs are the case's. Its first call returns only once the test writes its gate file. The test attaches while the run is held, releases it, and reads to the end: "the inspector is attached" means this |
| `F-INSPECT` | `vantage-inspect <verb>` run as a process on `F-LM-HELD` or `F-FLAWED-LM`: its standard output, standard error and exit code |
| `F-READER` | `tests/support/lm_reader.cpp`, a test reader built on the layout header alone: `--stall` attaches and reads nothing; `--kill-after N` reads N cycles and is then killed by the test; `--layout-version V` attaches claiming version V; `--write-byte` writes one byte into the mapping |
| `F-FLAWED-LM` | `tests/support/lm_flawed.cpp`, a test writer that makes a live measurement through `liveMeasOpen`, `liveMeasStep` and `liveMeasClose` from a lab case's description and recorded values, with at most one flaw named on its command line: `--drop-port`, `--skip-step`, `--drop-ref-sync`, `--alter-byte`, `--lower-badge` |
| `F-STRESS` | `tests/support/lm_stress.cpp`, the contract's `F-LM-STRESS`: a writer filling a 2-slot `MeasCycle` ring at full speed through the library, with a log of what it wrote, and one reader copying in a loop |
| `F-SUPERVISED` | `simengine --supervise --attempt-timeout-ms D` (optionally `--restart-on-crash N`) run on a lab case through `lab_tools.supervise` (`LAB-53`), with `F-LM-HELD`'s attached reader: the exit code, the attempt manifest, the reproducer folder and the outcome the reader reads after the end |
| `F-ISOLATE` | `tests/support/isolate_stage.cpp`, a test asker that hosts one stage of a lab case through `RunIsolatedStage` and reports the outcome, the exit code and the stage it names |
| `F-SRC-LM` | `src/simcore`, `src/simengine`, `src/inspector` and `src/livemeas` as checked in, and per check a copy with one planted violation |

---

## 1. Gate G3 — the test group

Gate `G3` (`VANTAGE_DEV_PLAN.md` §5) is green when both tests of this section pass. They live
in `tests/system/test_vnt_gate_g3.py`.

**`SYT-EQO-01`** · T · fixture `F-CAT`, `F-ENGINE`, `F-TAP`, `F-COMPARE` — Every exact case equals the fake car
**Serves.** `SYS-0042`
**Steps.** Run every exact case on `F-ENGINE`, and `running_example` `jump` on `F-TAP` with `outputs.path` set. Compare each simulated stage's data outputs and `compState` in the engine-run recording with the recorded ones through `F-COMPARE`, leaving out the outputs of steps `F-TAP` shows badged `KIND_WARMING_UP`. Run `running_example` `no_ref_sync` the same way.
- `.c1` **PASS:** every exact case equal, per `SYS-0042` Accept. **FAIL:** any difference, reported with topology, case, stage and step.
- `.c2` **PASS:** on `no_ref_sync` the comparison finds at least one difference. **FAIL:** it finds none, so the comparison could not have failed.

**`SYT-THR-01`** · T · fixture `F-CAT`, `F-ENGINE`, `F-TAP`, `F-COMPARE` — N threads give equal outputs to one
**Serves.** `SYS-0039`
**Steps.** For every exact case and every N from 2 to its number of simulated stages, run it with `--threads 1` and with `--threads N` (`running_example` `jump` on `F-TAP`); compare the two engine-run recordings through `F-COMPARE` on every port, and the two event logs line by line.
- `.c1` **PASS:** equal outputs and identical event logs, per `SYS-0039` Accept. **FAIL:** any difference, naming case, N, port and step.

## 1a. Gate G4 — the test group

Gate `G4` (`VANTAGE_DEV_PLAN.md` §5) is green when `SYT-INS-06` and every test of the drill table
below pass, with test readers and no viewer. They live in `tests/system/test_vnt_gate_g4.py`.
`G4`'s two halves are the two questions of `ARCH §10.3`: does the inspector find every item, and
does every failure end as described.

**`SYT-INS-06`** · T · fixture `F-CAT`, `F-LM-HELD`, `F-INSPECT`, `F-FLAWED-LM` — `check` finds every item of every topology
**Serves.** `SYS-0080`
**Steps.** For every topology of the catalogue, run its first exact case on `F-LM-HELD` and run `check --recording` on it. Then run `check` on `F-FLAWED-LM` made from `running_example` `cut_c` with `--drop-port` (one declared port left out of one step).
- `.c1` **PASS:** on every topology `check` reports no finding and exits 0, per `SYS-0080` Accept. **FAIL:** a finding, naming topology, step and port.
- `.c2` **PASS:** on the flawed one `check` names the dropped step and port. **FAIL:** it reports none, so `.c1` could not have failed.

**The drills.** Each is run once with test readers (`F-READER`, `F-STRESS`) and no viewer.

| Drill (`ARCH §10.3`) | Test that makes it | Passes when |
|---|---|---|
| a stalled reader | `RCT:SYT-LMS-04` and `SYT-INS-05` on Vantage | the run writes every step with byte-identical outputs, and the stalled reader's next read says how many steps it skipped |
| a stress writer | `RCT:SYT-LMS-03` on Vantage, on `F-STRESS` | every accepted cycle decodes and matches the writer's log |
| another layout version | `RCT:SYT-LMS-08` on Vantage and `SYT-INS-12` | the reader refuses, naming both versions, and reads no cycle |
| a killed writer | `SYT-INS-02` and `SYT-LMW-11` | `attach` says "writer gone at step N", and the next engine on the name replaces it |
| a killed reader | `SYT-LMW-16` | the run writes every step, and a later reader reads every cycle |
| a second engine with the same name | `SYT-LMW-10` | one warning, and the second run's outputs equal a run with no live measurement |
| an oversize port | `RCT:SYT-LMS-09` on Vantage, on the `camera` topology with `bulk` empty | that port is omitted in that step and the run completes |
| supervised `hang` | `SYT-SUP-02`, `SYT-SUP-07` | exit code 7, and the attached reader reads status finished with outcome `timeout` |
| supervised `crash` | `SYT-SUP-03`, `SYT-SUP-07`, `SYT-SUP-13` | exit code 8, outcome `crash`, and a reproducer naming `B` |

*The contract's live measurement tests on Vantage.* `RCT:SYT-LMS-01` to `RCT:SYT-LMS-09` are run
by `tests/system/test_vnt_lms.py` on `F-LM-HELD` (`F-LM`), `F-STRESS` (`F-LM-STRESS`) and the
`camera` topology (`F-CAM`), with `RCT:SYT-LMS-02.c2` on `F-LM-TWICE`; each id appears in that file.
They are cited here and never restated (`R-REQ-4`).

## 2. The run setup — `RUN`

**`SYT-RUN-01`** · T · fixture `F-CASE`, `F-ENGINE`, `F-COMPARE` — The run setup is the only input
**Serves.** `SYS-0001`
**Steps.** Run `running_example` `cut_c` from its setup's directory. Run it again from an empty working directory, with no Python on `PATH`, no YAML or ingest map under the working directory, and every library search path variable cleared. Compare the two engine-run recordings.
- `.c1` **PASS:** equal outputs on every port, per `SYS-0001` Accept. **FAIL:** any difference, or the second run fails to start.

**`SYT-RUN-02`** · T · fixture `F-SETUP-EDIT`, `F-ENGINE` — `sampling` and `on_missing` refused
**Serves.** `SYS-0002`
**Steps.** Add `sampling` to one port of `running_example` `cut_c`'s setup and run; then the same with `on_missing`.
- `.c1` **PASS:** with `sampling`, a load error as `SYS-0002` Accept. **FAIL:** the run starts, or the message lacks the key, the stage or the port.
- `.c2` **PASS:** with `on_missing`, the same. **FAIL:** as `.c1`.

**`SYT-RUN-03`** · T · fixture `F-SETUP-EDIT`, `F-ENGINE` — A missing `⊘` value refused
**Serves.** `SYS-0003`
**Steps.** From `running_example` `cut_c`'s setup, which carries `outputs.livemeas`, remove in turn `readiness_limit_steps`, `fallback_max_gap`, one port's `buffer_depth` and each of the four live measurement geometry values, and run each. Then remove `outputs.livemeas` whole and run.
- `.c1` **PASS:** each removal gives a load error naming the removed key before the first step, per `SYS-0003` Accept. **FAIL:** any run starts, or the error names another key.
- `.c2` **PASS:** with `outputs.livemeas` removed, the setup loads and runs. **FAIL:** a load error naming a geometry value.

**`SYT-RUN-04`** · T · fixture `F-SETUP-EDIT`, `F-ENGINE` — Only the accepted schema version loads
**Serves.** `SYS-0004`
**Steps.** Change the last character of `running_example` `cut_c`'s `schema` and run; then remove `schema` and run.
- `.c1` **PASS:** changed: a load error as `SYS-0004` Accept. **FAIL:** the run starts, or the message lacks either string.
- `.c2` **PASS:** removed: a load error naming the expected string. **FAIL:** the run starts.

**`SYT-RUN-05`** · T · fixture `F-REC-EDIT`, `F-SETUP-EDIT`, `F-TAP`, `F-COMPARE` — Two files, one recording
**Serves.** `SYS-0005`
**Steps.** Split `running_example`'s `base` recording by topic, the `source.*` topics into one file and every other topic into a second, and list both in `sources[]` of a copy of `cut_c`'s setup. Run both setups on `F-TAP` with `outputs.path` set; compare the recordings and the step counts.
- `.c1` **PASS:** equal outputs and equal step counts, per `SYS-0005` Accept. **FAIL:** any difference.

**`SYT-RUN-06`** · T · fixture `F-SETUP-EDIT`, `F-TAP`, `F-ENGINE` — A port keeps at most `buffer_depth` samples
**Serves.** `SYS-0006`
**Steps.** Run `running_example` `all_simulated` on `F-TAP` and `F-ENGINE` with `buffer_depth` 1 on every port; mark each run whose recorded refSync names a sample older than its port's newest at that step. Then run it with the lab's provisional depth.
- `.c1` **PASS:** depth 1: `KIND_FALLBACK` on that port in exactly the marked runs, per `SYS-0006` Accept. **FAIL:** a marked run without it, or an unmarked run with it.
- `.c2` **PASS:** provisional depth: no `KIND_FALLBACK`. **FAIL:** any.

**`SYT-RUN-07`** · T · fixture `F-REC-EDIT`, `F-ENGINE` — A `measured` stage without recorded outputs refused
**Serves.** `SYS-0007`
**Steps.** Remove `C`'s data output topic from `running_example`'s `base` recording; run `cut_c` on it.
- `.c1` **PASS:** a load error as `SYS-0007` Accept. **FAIL:** the run starts, or the message lacks `C` or the port.

**`SYT-RUN-08`** · T · fixture `F-SETUP-EDIT`, `F-PROBE`, `F-ENGINE` — A `measured` or `off` stage is never called
**Serves.** `SYS-0008`
**Steps.** Put the probe in place of `C`'s library in `running_example` `cut_c`; run with `C` `measured`, then `off`, then `simulate`; read the probe's log after each.
- `.c1` **PASS:** `measured`: no call, per `SYS-0008` Accept. **FAIL:** any call.
- `.c2` **PASS:** `off`: no call. **FAIL:** any call.
- `.c3` **PASS:** `simulate`: one call per recorded `C` control. **FAIL:** another count.

**`SYT-RUN-09`** · T · fixture `F-SETUP-EDIT`, `F-ENGINE` — Retired and unknown keys refused
**Serves.** `SYS-0046`
**Steps.** To copies of `running_example` `cut_c`'s setup add, one per copy, `delay_steps` to one input, `grid_step_ns` and `order` at the top level, `pattern` to one stage's `impl`, and an unknown key `colour` to one stage; run each.
- `.c1` **PASS:** each retired key gives a load error naming the key and where it is, per `SYS-0046` Accept. **FAIL:** a run starts, or the message lacks the key or its place.
- `.c2` **PASS:** `colour` gives a load error naming it and its stage. **FAIL:** a run starts, or the key is ignored.
- `.c3` **PASS:** `impl.pattern` gives a load error naming it and its stage. **FAIL:** a run starts, or the key is ignored.

**`SYT-RUN-10`** · T · fixture `F-RUN-CONFIG` — The launcher refuses a missing run-setup value
**Serves.** `SYS-0048`
**Steps.** Remove in turn `readiness_limit_steps`, `fallback_max_gap`, one simulated stage's `trigger` and one port's `buffer_depth`, and run `sim resim` on each copy. Then, with every value given, start the run through `sim resim`, the batch worker (`orchestrate/worker.py`) and `sim check`, and read each run setup written.
- `.c1` **PASS:** each removal gives an error naming the value and no run setup file, per `SYS-0048` Accept. **FAIL:** a setup is written, or the error names another value.
- `.c2` **PASS:** each of the three paths writes a setup carrying exactly the configured values. **FAIL:** a value missing, changed or filled by a default.

**`SYT-RUN-11`** · T · fixture `F-CASE`, `F-ENGINE` — An engine-run recording embeds the simulated stages' bundles
**Serves.** `SYS-0052`
**Steps.** Run `running_example` `cut_c` on `F-ENGINE`. Read the engine-run recording's `config_bundle` block, each stage's bundle folder (`config/` beside its library) and each stage's `config_bundle_sha256` in the setup.
- `.c1` **PASS:** the block names exactly the simulated stages, each with its folder's files and text, per `SYS-0052` Accept. **FAIL:** a stage missing or extra (`C` is `measured`), or a file missing, extra or different.
- `.c2` **PASS:** each stage's `bundle.sha256` text equals the setup's hash for it. **FAIL:** any differs.

**`SYT-RUN-12`** · T · fixture `F-CASE`, `F-ENGINE`, `F-RUN-CONFIG`, `F-REC-EDIT` — An engine-run recording names what made it
**Serves.** `SYS-0055`
**Steps.** Run `running_example` `cut_c` on `F-ENGINE` twice; read both recordings' `manifest` through Vantage's recording reader, each simulated stage's library file and the setup. Run `F-RUN-CONFIG` with `sim resim --save`; then run `sim resim --pin-builds` with it on the saved recording, on a copy whose `manifest` gives its stage another `library_sha256`, and on a copy that gives none.
- `.c1` **PASS:** `run_id` and `run_spec_sha256` are the setup's `run_id` and `spec_sha256`, `host` this machine's name, `process_nonce` not empty, and each simulated stage's `library_sha256` the SHA-256 of its library file, per `SYS-0055` Accept. **FAIL:** a key missing, empty or with another value, or a component entry for `C`.
- `.c2` **PASS:** the two manifests differ only in `process_nonce`, and `adas_sim.diagnostics.determinism.derive_axis` gives `fresh_process` for them. **FAIL:** another difference, equal nonces, or another axis.
- `.c3` **PASS:** `--pin-builds` passes on the saved recording, refuses the changed copy as a mismatch and the stripped copy as unpinnable. **FAIL:** a refusal of the saved recording, or a pass on either copy.

## 3. The orchestrator — `ORC`

**`SYT-ORC-01`** · T · fixture `F-CASE`, `F-ENGINE` — Rank order inside a step
**Serves.** `SYS-0009`
**Steps.** Run `running_example` `no_ref_sync`; for each step whose controls include both `A` and `B`, read `B`'s re-run refSync entry for `A` and `A`'s output of that step.
- `.c1` **PASS:** the entry names `A`'s output of that step, per `SYS-0009` Accept. **FAIL:** it names an older sample.

**`SYT-ORC-02`** · T · fixture `F-CASE`, `F-SETUP-EDIT`, `F-ENGINE` — A loop without a previous-cycle input refused
**Serves.** `SYS-0010`
**Steps.** Run `loop_no_edge`: the lab writes no run setup for a topology it refuses, so the test copies `feedback` `all_simulated`'s, drops `A`'s `previous_cycle` mark and points every library path at `loop_no_edge`'s build (the same stages, inputs and periods). Then run `feedback` `all_simulated`.
- `.c1` **PASS:** `loop_no_edge` as `SYS-0010` Accept. **FAIL:** it runs, or the error names another stage or none.
- `.c2` **PASS:** `feedback` runs to the recording's end. **FAIL:** a load error.

**`SYT-ORC-03`** · T · fixture `F-SETUP-EDIT`, `F-REC-EDIT`, `F-ENGINE` — Exactly one way to start
**Serves.** `SYS-0011`
**Steps.** From `data_triggered` `by_data`, make four setups and run each: `T` triggered by `control` on a recording with `T.control` removed; `T` triggered by an input it does not declare; `T` with no trigger and clock 0; `T` with its trigger and a 10 ms clock.
- `.c1` **PASS:** no recorded control: a load error naming `T` and `T.control`, per `SYS-0011` Accept. **FAIL:** the run starts.
- `.c2` **PASS:** undeclared input: a load error naming `T` and the input. **FAIL:** the run starts.
- `.c3` **PASS:** no trigger, clock 0: a load error naming `T`. **FAIL:** the run starts.
- `.c4` **PASS:** trigger and clock: a load error naming `T`. **FAIL:** the run starts.

**`SYT-ORC-04`** · T · fixture `F-CAT`, `F-ENGINE` — One run per trigger
**Serves.** `SYS-0012`, `SYS-0053`
**Steps.** For every exact case count each simulated stage's controls in the engine-run recording and in the recording; on `data_triggered` `by_data`, count `T`'s controls and the `in_X` samples. In every exact case and in `running_example` `all_simulated` with `buffer_depth` 1 on every port, read each simulated stage's `compState` messages in the engine-run recording.
- `.c1` **PASS:** equal counts in every exact case, per `SYS-0012` Accept. **FAIL:** any count differs.
- `.c2` **PASS:** `by_data`: one `T` control per `in_X` sample. **FAIL:** another count.
- `.c3` **PASS:** each stage's `compState` `cycle_counter`s are consecutive and as many as its controls, per `SYS-0053` Accept. **FAIL:** a gap, or another count.

**`SYT-ORC-05`** · T · fixture `F-RENUMBER-LIB`, `F-ENGINE` — An output not copying its control's counter is logged
**Serves.** `SYS-0013`
**Steps.** Run the case; in the engine-run recording, list `A`'s data outputs whose `measurement_counter` differs from their control's; read the event log's `output_counter_break` entries.
- `.c1` **PASS:** one entry per listed output, each with stage, port and step, and the run reaches the recording's end, per `SYS-0013` Accept. **FAIL:** a missing entry, or the run stops.

**`SYT-ORC-06`** · T · fixture `F-CASE`, `F-ENGINE` — A stage's runs strictly in order
**Serves.** `SYS-0014`
**Steps.** Run `late_consumer` `all_simulated`; read each stage's `control` and output messages in the engine-run recording in file order.
- `.c1` **PASS:** as `SYS-0014` Accept. **FAIL:** a control out of trigger order, or a control before the previous control's outputs.

**`SYT-ORC-07`** · T · fixture `F-CASE`, `F-SETUP-EDIT`, `F-ENGINE`, `F-TAP` — A run waits for its named sample
**Serves.** `SYS-0015`
**Steps.** Run `late_consumer` `all_simulated` and `cut_p` on `F-ENGINE`; compare every `Q` re-run entry for `P` with the recorded one. Run `all_simulated` with `readiness_limit_steps` 0 on `F-TAP`.
- `.c1` **PASS:** `all_simulated`: every entry equal, per `SYS-0015` Accept. **FAIL:** any difference.
- `.c2` **PASS:** `cut_p`: every entry equal. **FAIL:** any difference.
- `.c3` **PASS:** limit 0: at least one `Q` run raises `KIND_READINESS_TIMEOUT`. **FAIL:** none does.

**`SYT-ORC-08`** · T · fixture `F-REC-EDIT`, `F-TAP`, `F-ENGINE` — The recording's end runs every waiting ticket
**Serves.** `SYS-0016`
**Steps.** Cut `late_consumer`'s `base` recording just after a `Q` control whose recorded refSync names a `P` sample logged after it, keeping that run's own refSync (the car logs it after the control); run `all_simulated` on it on `F-TAP` and `F-ENGINE`.
- `.c1` **PASS:** that `Q` run is in the last step with `KIND_READINESS_TIMEOUT`, per `SYS-0016` Accept. **FAIL:** the run is missing, in another step, or not badged.

**`SYT-ORC-09`** · T · fixture `F-CASE`, `F-TAP` — A simulated stage nobody simulated consumes is badged
**Serves.** `SYS-0018`
**Steps.** Run `measured_middle` `cut_m` and `fan_out` `all_simulated`; read every `KIND_COMPUTED_NOT_CONSUMED` badge.
- `.c1` **PASS:** `cut_m`: on `A` once, on no other stage, per `SYS-0018` Accept. **FAIL:** missing, raised more than once, or on another stage.
- `.c2` **PASS:** `fan_out`: none. **FAIL:** any.

**`SYT-ORC-10`** · T · fixture `F-CAT`, `F-ENGINE` — The plan is printed without running
**Serves.** `SYS-0019`
**Steps.** For every lab setup, remove the component libraries, run, and read the printed plan; derive each simulated stage's rank, trigger, clock and previous-cycle inputs from its topology file.
- `.c1` **PASS:** the plan matches, per `SYS-0019` Accept. **FAIL:** a mismatch, a missing stage, or no plan before the load error for the missing library.

**`SYT-ORC-11`** · T · fixture `F-CASE`, `F-ENGINE` — A repeated trigger sample starts no run
**Serves.** `SYS-0047`
**Steps.** Run `data_triggered` `repeat_trigger` `by_data`; count `T`'s controls in the engine-run recording and the distinct `in_X` counters in the recording; read the event log's `stalled_trigger` entries. Then give the same count check a copy of the engine-run recording with one more `T` control at the repeat's reception time.
- `.c1` **PASS:** one `T` control per distinct counter and one `stalled_trigger` entry naming `T` and `in_X`, per `SYS-0047` Accept. **FAIL:** an extra or a missing run, or no entry.
- `.c2` **PASS:** the planted extra run is reported. **FAIL:** the copy passes.

**`SYT-ORC-12`** · T · fixture `F-TICK` — A clock-started control wraps to 1
**Serves.** `SYS-0050`
**Steps.** With a 1 ms clock period, read the `measurement_counter` of the control for ticks 0, 1, `0xFFFFFFFE`, `0xFFFFFFFF` and `0x100000000`.
- `.c1` **PASS:** 1, 2, `0xFFFFFFFF`, 1 and 2, per `SYS-0050` Accept. **FAIL:** a 0, or `0xFFFFFFFF` followed by anything but 1.

**`SYT-ORC-13`** · T · fixture `F-CASE`, `F-SETUP-EDIT`, `F-REC-EDIT`, `F-ENGINE` — Every run's overridden input is recorded
**Serves.** `SYS-0057`
**Steps.** Run `running_example` `all_simulated` with `buffer_depth` 1 on every port and one declared override on `source.Y` that leaves its `sig_header` unchanged, on a copy of its recording whose `B` controls are taken in pairs, the first of each pair logged at the instant of the second, so a step holds two `B` runs; read `B`'s `control` and re-run `refSync` messages and its `in_Y` topic in the engine-run recording.
- `.c1` **PASS:** as `SYS-0057` Accept, and at least one step holds two `B` runs. **FAIL:** a count other than the controls', a message carrying another run's counter, or no step with two `B` runs, so the case could not fail.

## 4. Input selection — `SEL`

**`SYT-SEL-01`** · T · fixture `F-CAT`, `F-ENGINE` — Inputs chosen by the recorded refSync
**Serves.** `SYS-0020`
**Steps.** For every exact case pair each re-run refSync with the recorded refSync of the same stage and `measurement_counter`; compare entry by entry.
- `.c1` **PASS:** as `SYS-0020` Accept. **FAIL:** any difference, naming case, stage, run and input.

**`SYT-SEL-02`** · T · fixture `F-REC-EDIT`, `F-TAP`, `F-ENGINE` — An entry 0 gives an empty input
**Serves.** `SYS-0021`
**Steps.** In `running_example`'s `base` recording set `B`'s recorded refSync entry for `Z` to 0 in one run at the middle; run `all_simulated` on `F-TAP` and `F-ENGINE`.
- `.c1` **PASS:** that run's re-run entry for `Z` is 0 and its step carries no badge on that port, per `SYS-0021` Accept. **FAIL:** a non-zero entry, or a badge.

**`SYT-SEL-03`** · T · fixture `F-CASE`, `F-ENGINE` — A sample not found falls back by counter
**Serves.** `SYS-0022`
**Steps.** Run `running_example` `missing_sample` `all_simulated`; for each run whose recorded entry names `source.Y` counter 20, 21 or 22, read its re-run entry.
- `.c1` **PASS:** the entry names counter 19, per `SYS-0022` Accept. **FAIL:** any other counter.

**`SYT-SEL-04`** · T · fixture `F-CASE`, `F-ENGINE` — Beyond `fallback_max_gap` the time rule picks
**Serves.** `SYS-0023`
**Steps.** Run `running_example` `missing_run` `all_simulated`; for each run whose wanted counter is more than `fallback_max_gap` past the newest present one, find in the recording the newest `source.Y` sample logged at or before the run's step whose time is not after its control's.
- `.c1` **PASS:** the re-run entry names that sample, per `SYS-0023` Accept. **FAIL:** any other sample.

**`SYT-SEL-05`** · T · fixture `F-CASE`, `F-ENGINE` — A fallback beyond the gap is logged
**Serves.** `SYS-0024`
**Steps.** In the run of `SYT-SEL-04`, read the event log's `fallback_beyond_gap` entries.
- `.c1` **PASS:** one per run of `SYT-SEL-04`, each with the values `SYS-0024` Accept names. **FAIL:** a missing, extra or wrong entry.

**`SYT-SEL-06`** · T · fixture `F-CASE`, `F-ENGINE` — No recorded refSync: the time rule
**Serves.** `SYS-0025`
**Steps.** Run `running_example` `no_ref_sync`; for every run and input, find in the recording the newest sample logged at or before the run's step whose time is not after the control's, or the newest logged when either time is 0.
- `.c1` **PASS:** each re-run entry names that sample, per `SYS-0025` Accept. **FAIL:** a sample logged after the step, or an older one.

**`SYT-SEL-07`** · T · fixture `F-REC-EDIT`, `F-ENGINE` — A previous-cycle input never sees the current step
**Serves.** `SYS-0026`
**Steps.** Remove every `refSync` topic from `feedback`'s `base` recording, listing them `excluded`; run `all_simulated`; for each `A` run, find the step that committed the `B` sample its re-run entry names.
- `.c1` **PASS:** always an earlier step, per `SYS-0026` Accept. **FAIL:** the same step.

**`SYT-SEL-08`** · T · fixture `F-REC-EDIT`, `F-ENGINE` — No sample found gives an empty input
**Serves.** `SYS-0027`
**Steps.** Remove the first five `source.Y` samples from `running_example`'s `base` recording; run `all_simulated`; read the re-run entry for `Y` of every run whose recorded entry for `Y` names a removed sample.
- `.c1` **PASS:** every entry 0, per `SYS-0027` Accept. **FAIL:** a non-zero entry.

**`SYT-SEL-09`** · T · fixture `F-CAT`, `F-SETUP-EDIT`, `F-TAP` — Selection outcomes raise their badges
**Serves.** `SYS-0028`
**Steps.** Run `running_example` `missing_sample`, `missing_run` and `no_ref_sync`, `late_consumer` `all_simulated` with `readiness_limit_steps` 0, and every exact case; for each step derive the `KIND_FALLBACK` and `KIND_READINESS_TIMEOUT` badges the table of `VANTAGE_Architecture.md` §6 gives for its selections; compare with the step's badges.
- `.c1` **PASS:** equal in every step, per `SYS-0028` Accept. **FAIL:** a missing, extra or misplaced badge, naming case, step and port.

**`SYT-SEL-10`** · T · fixture `F-CAT`, `F-REC-EDIT`, `F-TAP` — Identity broken is badged
**Serves.** `SYS-0029`
**Steps.** In `running_example`'s `base` recording lower `source.X`'s `measurement_counter` by 5 from its 100th sample on, its `cycle_counter` unchanged; run `all_simulated` on it on `F-TAP`. Run every exact case on `F-TAP`. Read every `KIND_IDENTITY_BROKEN` badge.
- `.c1` **PASS:** edited: one badge, on `source.X` at the step of its 100th sample, per `SYS-0029` Accept. **FAIL:** none, more than one, another step, or a badge on any other port (a downstream stage's input or output).
- `.c2` **PASS:** exact cases: never raised. **FAIL:** any.

**`SYT-SEL-11`** · T · fixture `F-CASE`, `F-REC-EDIT`, `F-ENGINE`, `F-TAP` — Gaps and resets are counted
**Serves.** `SYS-0030`
**Steps.** Run `running_example` `counter_jump` `all_simulated`; read the `counter_gap` and `counter_reset` entries for `source.X`. In `running_example`'s `base` recording restart `source.X`'s `measurement_counter` and `cycle_counter` at 1 from its 100th sample; run `all_simulated` on `F-ENGINE` and `F-TAP`.
- `.c1` **PASS:** `counter_jump`: one gap and no reset on `source.X`, per `SYS-0030` Accept. **FAIL:** another count.
- `.c2` **PASS:** restarted: one reset on `source.X` and no `KIND_IDENTITY_BROKEN` on it. **FAIL:** another count, or the badge.

**`SYT-SEL-12`** · T · fixture `F-CASE`, `F-ENGINE`, `F-TAP` — A counter wrap is consecutive
**Serves.** `SYS-0049`
**Steps.** Run `running_example` `counter_wrap` `all_simulated` on `F-ENGINE` and `F-TAP`; read the `counter_gap` and `counter_reset` entries for `source.X` and every `KIND_IDENTITY_BROKEN` badge. Then repeat on a copy of its recording whose `source.X` sample after `0xFFFFFFFF` is rewritten to carry 3 (`F-REC-EDIT`).
- `.c1` **PASS:** no gap and no reset on `source.X`, and no `KIND_IDENTITY_BROKEN`, per `SYS-0049` Accept. **FAIL:** any entry or badge, in particular a gap of 1 at the wrap.
- `.c2` **PASS:** the edited copy shows one gap on `source.X`. **FAIL:** none, so the check could not have failed.

**`SYT-SEL-13`** · T · fixture `F-CASE`, `F-REC-EDIT`, `F-SETUP-EDIT`, `F-ENGINE` — The counter fallback's gap counts the wrap as one step
**Serves.** `SYS-0051`
**Steps.** From `running_example` `counter_wrap`'s recording remove `source.X`'s samples with `measurement_counter` `0xFFFFFFFF`, 1 and 2 (`F-REC-EDIT`). Run `all_simulated` on it on `F-ENGINE` twice, its setup's `fallback_max_gap` set to 1 and then to 3 (`F-SETUP-EDIT`). For every run whose recorded entry names `source.X` counter 1 or 2, read its re-run entry and the event log's `fallback_beyond_gap` entries for it.
- `.c1` **PASS:** at 1, each such run has one entry, found `0xFFFFFFFE`, gap 2 when it wants 1 and 3 when it wants 2, per `SYS-0051` Accept. **FAIL:** a gap of 3 for 1 or of 4 for 2, a missing entry, or no such run at all.
- `.c2` **PASS:** at 3, no such run has an entry and each re-run entry names `0xFFFFFFFE`. **FAIL:** an entry (a run wanting 2 at gap 4), or another sample.

## 5. The engine step — `STP`

**`SYT-STP-01`** · T · fixture `F-CASE`, `F-SETUP-EDIT`, `F-TAP` — One step per instant
**Serves.** `SYS-0032`
**Steps.** Run `running_example` `cut_c` on `F-TAP`; list the distinct reception times of the recording's step-starting messages (`VANTAGE_Architecture.md` §7): here `source.X`, `source.Y`, `source.Z`, `C`'s `out`, `refSync` and `compState`, and the `control` of `A`, `B`, `D` and `E`. Then set `E`'s trigger empty and `clock_period_ns` to 7 ms, and run again.
- `.c1` **PASS:** steps are those times, numbered from 0 without a gap, per `SYS-0032` Accept. **FAIL:** a missing or extra step, a gap, or a wrong time.
- `.c2` **PASS:** with the clock, the steps are the union of those times and `E`'s ticks. **FAIL:** a tick instant without its step.

**`SYT-STP-02`** · T · fixture `F-SETUP-EDIT`, `F-ENGINE` — A run triggered in a step runs in that step
**Serves.** `SYS-0033`
**Steps.** Run `fan_out` `all_simulated` with `B`'s trigger set to its input from `A`; pair each `B` control in the engine-run recording with the `A` output carrying its `measurement_counter`.
- `.c1` **PASS:** same reception time in every pair, per `SYS-0033` Accept. **FAIL:** a later one.

**`SYT-STP-03`** · T · fixture `F-CASE`, `F-TAP` — After a jump no older sample
**Serves.** `SYS-0034`
**Steps.** Run `running_example` `jump` on `F-TAP` with `outputs.path` set; for every run after the jump, look up in the recording the samples its re-run entries name.
- `.c1` **PASS:** none logged before `jump_to_ms`, per `SYS-0034` Accept. **FAIL:** one is.

**`SYT-STP-04`** · T · fixture `F-CASE`, `F-TAP` — A jump keeps the engine run
**Serves.** `SYS-0035`
**Steps.** In the run of `SYT-STP-03`, read every step number.
- `.c1` **PASS:** consecutive from 0 to the last step across the jump, per `SYS-0035` Accept. **FAIL:** a restart at 0, a gap or a repeat.

**`SYT-STP-05`** · T · fixture `F-CASE`, `F-TAP`, `F-COMPARE` — Warming up is badged until equal
**Serves.** `SYS-0036`
**Steps.** In the run of `SYT-STP-03`, find for each simulated stage, through `F-COMPARE`, the first step after the jump at which its outputs equal the recorded ones; read its `KIND_WARMING_UP` badges. Run `running_example` `cut_c` on `F-TAP`.
- `.c1` **PASS:** `jump`: each stage badged from the jump to that step and not after, per `SYS-0036` Accept. **FAIL:** a missing badge, or one after that step.
- `.c2` **PASS:** `cut_c`: no stage badged. **FAIL:** any.

**`SYT-STP-06`** · T · fixture `F-CAT`, `F-ENGINE` — Every event log line has a listed kind and a step
**Serves.** `SYS-0037`
**Steps.** Parse every event log line of every lab case this specification runs on `F-ENGINE`. Then give the parser one line whose kind is `other`.
- `.c1` **PASS:** every line parses as `SYS-0037` Accept. **FAIL:** a line with another kind or no step.
- `.c2` **PASS:** the planted line is rejected. **FAIL:** it is accepted.

## 6. Threads — `THR`

`SYT-THR-01` is in §1.

**`SYT-THR-02`** · T · fixture `F-SETUP-EDIT`, `F-PROBE`, `F-ENGINE` — One thread by default
**Serves.** `SYS-0040`
**Steps.** Put a separate probe copy in place of each library of `diamond` `all_simulated`; run without `--threads`, then with `--threads 2`; read the thread ids in the probe's log.
- `.c1` **PASS:** without `--threads`, one id, per `SYS-0040` Accept. **FAIL:** two or more.
- `.c2` **PASS:** with `--threads 2`, at least two ids. **FAIL:** one, so the probe could not have seen a second thread.

**`SYT-THR-03`** · T · fixture `F-SETUP-EDIT`, `F-PROBE`, `F-ENGINE` — One library is never called twice at once
**Serves.** `SYS-0041`
**Steps.** Run `fan_out` `all_simulated` with `--threads 2`, first with one probe copy as both `B` and `C`, then with two copies at different paths; read entries and exits in the probe's log.
- `.c1` **PASS:** one copy: no entry while another call is inside, per `SYS-0041` Accept. **FAIL:** an overlap.
- `.c2` **PASS:** two copies: at least one overlap. **FAIL:** none.

## 7. Equal outputs and the first divergence — `EQO`

`SYT-EQO-01` is in §1.

**`SYT-EQO-02`** · T · fixture `F-CAT`, `F-ENGINE`, `F-COMPARE` — The first divergence is reported
**Serves.** `SYS-0043`
**Steps.** Run `running_example` `no_ref_sync`; find through `F-COMPARE` the first step, stage and port at which a RUN-run output differs from the recorded one; read the event log's `first_divergence` entry. Run every exact case without a jump and read the same.
- `.c1` **PASS:** `no_ref_sync`: the entry names that step, stage and port, per `SYS-0043` Accept. **FAIL:** missing, or naming another.
- `.c2` **PASS:** exact cases: no entry. **FAIL:** any.

**`SYT-EQO-03`** · T · fixture `F-CASE`, `F-REC-EDIT`, `F-TAP`, `F-ENGINE` — A re-run refSync is compared on counter and time only
**Serves.** `SYS-0044`
**Steps.** Run `diamond` `all_simulated` on `F-TAP` with a jump at 500 ms to the middle of its recording; read `first_divergence`. Change one recorded `B` refSync entry's `source_timestamp_us` in `running_example`'s `base` recording; run `cut_c` on `F-ENGINE`.
- `.c1` **PASS:** `diamond`: no divergence, per `SYS-0044` Accept. **FAIL:** one is reported.
- `.c2` **PASS:** edited: reported on `B`'s `refSync` at that run's step. **FAIL:** none, or another port first.

**`SYT-EQO-04`** · T · fixture `F-CASE`, `F-ENGINE` — A divergence does not fail the engine run
**Serves.** `SYS-0045`
**Steps.** Run `running_example` `no_ref_sync` and `cut_c`; read each exit code and step count.
- `.c1` **PASS:** as `SYS-0045` Accept, `no_ref_sync`'s step count equal to the number of distinct reception times of its recording's step-starting messages (`VANTAGE_Architecture.md` §7). **FAIL:** a fail outcome, or another number of steps.

**`SYT-EQO-05`** · T · fixture `F-CASE`, `F-TAP` — A lost input's divergence comes no earlier than the loss
**Serves.** `SYS-0054`
**Steps.** Run `running_example` `missing_sample` and `missing_run` `all_simulated` on `F-TAP` with `outputs.path` set. In each, find the run of `B` or `E` at the earliest step whose recorded refSync names a dropped `source.Y` sample; read the event log's `first_divergence` entry and that step's badges.
- `.c1` **PASS:** in each, as `SYS-0054` Accept. **FAIL:** no entry, an entry at an earlier step, or no `KIND_FALLBACK` on that run's `in_Y` at its step.

**`SYT-EQO-06`** · T · fixture `F-CASE`, `F-REC-EDIT`, `F-ENGINE` — The engine-run recording states its first divergence
**Serves.** `SYS-0056`
**Steps.** Run `running_example` `no_ref_sync` and `cut_c` on `F-ENGINE`; then `cut_c` on a copy of its recording with every topic of `A`, `B`, `D` and `E` except their `control` removed. Read each engine-run recording's `manifest` `divergence` and each event log's `first_divergence` entry.
- `.c1` **PASS:** as `SYS-0056` Accept, `no_ref_sync`'s value naming the entry's step, stage and port. **FAIL:** another value, `none` or `unknown` where an entry exists, or `none` where no output was compared.

## 8. The live measurement as the engine writes it — `LMW`

**`SYT-LMW-01`** · T · fixture `F-LM-HELD`, `F-SETUP-EDIT`, `F-INSPECT` — The setup names the live measurement
**Serves.** `SYS-0058`
**Steps.** Run `running_example` `cut_c` on `F-LM-HELD`; `attach` and `dump` it. Then remove `outputs.livemeas` and run again, listing the live measurements that exist while the probe is held.
- `.c1` **PASS:** name and geometry as the setup's, and a cycle for step 0, per `SYS-0058` Accept. **FAIL:** another name or geometry, or no cycle for step 0.
- `.c2` **PASS:** with the key removed no live measurement of that name exists. **FAIL:** one does.

**`SYT-LMW-02`** · T · fixture `F-CAT`, `F-LM-HELD`, `F-INSPECT` — The description equals the setup
**Serves.** `SYS-0059`, `SYS-0060`
**Steps.** For every lab case, decode the description through `dump --description`; compare its stages, ports, `bulk` flags, triggers, clocks, previous-cycle inputs, overrides, bundle hashes and readiness limit with the setup's, and read `C`'s and each simulated stage's `build_id` on `running_example` `cut_c`.
- `.c1` **PASS:** every field equal, and nothing extra, per `SYS-0059` Accept. **FAIL:** any difference, naming case and field.
- `.c2` **PASS:** `C`'s `build_id` is empty and each simulated stage's equals its manifest's, per `SYS-0060` Accept. **FAIL:** `C` non-empty, or a simulated stage's differing.

**`SYT-LMW-03`** · T · fixture `F-LM-HELD`, `F-INSPECT` — Every schema is in the descriptor set
**Serves.** `SYS-0061`
**Steps.** Run `running_example` `cut_c` on `F-LM-HELD` with `LAB_C`'s library path removed from the run (it is `measured`); `dump` every port.
- `.c1` **PASS:** every port decoded, `C`'s recorded output included, per `SYS-0061` Accept. **FAIL:** one undecodable port.

**`SYT-LMW-04`** · T · fixture `F-LM-HELD`, `F-TAP`, `F-INSPECT` — Held values and their age
**Serves.** `SYS-0062`
**Steps.** Run `running_example` `all_simulated` on `F-LM-HELD`; `dump` every cycle. For each port and step k, take the newest sample of that port arrived by k from the engine-run recording.
- `.c1` **PASS:** value equal and `age_ns` equal to k's time minus that sample's arrival time, per `SYS-0062` Accept. **FAIL:** another value or age.
- `.c2` **PASS:** a port with no sample by k is absent from step k. **FAIL:** a value or a default is present.

**`SYT-LMW-05`** · T · fixture `F-LM-HELD`, `F-SETUP-EDIT`, `F-INSPECT` — Origins
**Serves.** `SYS-0063`
**Steps.** Run `running_example` `cut_c` with one `const` override on `source.Y` on `F-LM-HELD`; `dump` and list each port's origin.
- `.c1` **PASS:** as `SYS-0063` Accept. **FAIL:** any other origin, or `overridden` on a port not overridden.

**`SYT-LMW-06`** · T · fixture `F-LM-HELD`, `F-TAP`, `F-INSPECT` — Badges in the step that raised them
**Serves.** `SYS-0064`
**Steps.** Run `missing_sample` `all_simulated` on `F-LM-HELD` and on `F-TAP` with the same setup; compare each cycle's badges with the tap's line of that step.
- `.c1` **PASS:** equal at every step, and `KIND_FALLBACK` first appears at the step the tap shows, per `SYS-0064` Accept. **FAIL:** any difference.

**`SYT-LMW-07`** · T · fixture `F-LM-TWICE`, `F-TAP`, `F-INSPECT` — Two runs of a stage in one step
**Serves.** `SYS-0065`
**Steps.** Run `F-LM-TWICE` on `F-TAP` and on `F-LM-HELD`; for each step the tap shows two `B` runs, read what `dump` prints on `B`'s `control`, `refSync`, output and overridden-input ports.
- `.c1` **PASS:** two values on each such port, each carrying its run's `measurement_counter`, in run order, per `SYS-0065` Accept. **FAIL:** one value, another order, or no step with two `B` runs, so the case could not fail.

**`SYT-LMW-08`** · T · fixture `F-CAM`, `F-SETUP-EDIT`, `F-INSPECT` — Only a flagged port goes to `MeasBulk`
**Serves.** `SYS-0066`
**Steps.** Run `camera` with `bulk: [source.Cam]`, then with `bulk` empty and the frames below the slot size.
- `.c1` **PASS:** only `source.Cam` is flagged and every image resolves, per `SYS-0066` Accept. **FAIL:** another port flagged, or an unresolved image.
- `.c2` **PASS:** with `bulk` empty, `dump` shows no `MeasBulk` frame. **FAIL:** a frame is written.

**`SYT-LMW-09`** · T · fixture `F-SUPERVISED`, `F-INSPECT` — The worker is the writer
**Serves.** `SYS-0067`
**Steps.** Run `running_example` `cut_c` on `F-SUPERVISED`; read `writerPid` through `attach`, the worker's and the supervisor's process ids from the process tree.
- `.c1` **PASS:** `writerPid` is the worker's and not the supervisor's, per `SYS-0067` Accept. **FAIL:** it is the supervisor's, or another process's.

**`SYT-LMW-10`** · T · fixture `F-LM-HELD`, `F-ENGINE` — A second engine on a held name
**Serves.** `SYS-0068`
**Steps.** With the first engine held on `F-LM-HELD`, start a second on the same name and run it to its end; run a third on the same setup with `outputs.livemeas` removed; compare the second's and third's recordings through `F-COMPARE`.
- `.c1` **PASS:** one warning naming the name and the cause, per `SYS-0068` Accept. **FAIL:** none, two, or a message without the name.
- `.c2` **PASS:** equal outputs, and the first engine's live measurement unchanged. **FAIL:** a difference, or the first run disturbed.

**`SYT-LMW-11`** · T · fixture `F-LM-HELD`, `F-INSPECT` — A dead writer's name is replaced
**Serves.** `SYS-0069`
**Steps.** Run `running_example` `cut_c` on `F-LM-HELD`, kill the engine process while it is held, then start a second engine on the same name.
- `.c1` **PASS:** the second opens, its run id differs from the first's, and a cycle for step 0 is read, per `SYS-0069` Accept. **FAIL:** an open refused, the same run id, or no cycle for step 0.

**`SYT-LMW-12`** · T · fixture `F-LM-HELD`, `F-SETUP-EDIT`, `F-INSPECT` — The worker's own outcomes
**Serves.** `SYS-0070`
**Steps.** Run `running_example` `cut_c`; run it with `held_probe`'s `PROBE_FAIL_AT_CALL: 3`; run `hang` with `limits.exec_timeout_ms` below the hang. Read the attached reader's status and outcome after each.
- `.c1` **PASS:** finished with `pass`, `fail`, `timeout` in that order, per `SYS-0070` Accept. **FAIL:** any other outcome, or a status other than finished.

**`SYT-LMW-13`** · T · fixture `F-LM-HELD`, `F-TAP`, `F-INSPECT` — A jump keeps one run id
**Serves.** `SYS-0071`
**Steps.** Run `running_example` `jump` on `F-TAP` with `outputs.livemeas`, the reader attached; read the run id before and after the jump and every cycle's step number.
- `.c1` **PASS:** one run id and consecutive steps across the jump, per `SYS-0071` Accept. **FAIL:** a new run id, a gap or a restart at 0.

**`SYT-LMW-14`** · T · fixture `F-LM-HELD`, `F-TAP`, `F-INSPECT` — The tap and the writer get the same step
**Serves.** `SYS-0072`
**Steps.** Run `running_example` `cut_c` on `F-TAP` with `outputs.livemeas`, the reader attached; compare each tap line's step, time and badges with the cycle of that step.
- `.c1` **PASS:** equal at every step, per `SYS-0072` Accept. **FAIL:** any difference.

**`SYT-LMW-15`** · T · fixture `F-CAT`, `F-ENGINE`, `F-SETUP-EDIT`, `F-COMPARE` — Writing the live measurement changes no output
**Serves.** `SYS-0073`
**Steps.** Run every exact case with `outputs.livemeas` and again with it removed; compare the two engine-run recordings through `F-COMPARE` on every port and the two event logs line by line.
- `.c1` **PASS:** equal outputs and identical event logs, per `SYS-0073` Accept. **FAIL:** any difference, naming case, port and step.

**`SYT-LMW-16`** · T · fixture `F-LM-HELD`, `F-READER`, `F-COMPARE` — A killed reader costs nothing
**Serves.** `SYS-0105`
**Steps.** Run `running_example` `cut_c` on `F-LM-HELD` with an `F-READER --kill-after 3` attached, killed by the test mid-copy once released; start a fresh reader before the end; run once more with no reader and compare recordings.
- `.c1` **PASS:** every step written, outputs equal, and the fresh reader reads every cycle, per `SYS-0105` Accept. **FAIL:** a missing step, a difference, or a cycle the fresh reader cannot read.

## 9. The inspector — `INS`

`SYT-INS-06` is in §1a.

**`SYT-INS-01`** · T · fixture `F-LM-HELD`, `F-INSPECT` — `attach` prints identity and state
**Serves.** `SYS-0075`
**Steps.** Run `running_example` `cut_c` on `F-LM-HELD`; `attach` while held, and again after the run finished.
- `.c1` **PASS:** while held, run id, geometry and status running as the writer's, and no cycle read, per `SYS-0075` Accept. **FAIL:** a value differing, or a cycle read.
- `.c2` **PASS:** after the run, status finished and the outcome. **FAIL:** status running.

**`SYT-INS-02`** · T · fixture `F-LM-HELD`, `F-INSPECT` — A stopped writer is reported as gone
**Serves.** `SYS-0076`
**Steps.** Run `cut_c` on `F-LM-HELD` started directly; `attach` while it lives, release it, kill it at step N, `attach` again.
- `.c1` **PASS:** no "writer gone" while it lives, "writer gone at step N" after, per `SYS-0076` Accept. **FAIL:** the line while it lives, or another N.

**`SYT-INS-03`** · T · fixture `F-LM-HELD`, `F-INSPECT`, `F-COMPARE` — `dump` prints one decoded line per value
**Serves.** `SYS-0077`
**Steps.** Run `cut_c` on `F-LM-HELD`; `dump`; decode the recording's message of each step with the lab's own decoder and compare field by field.
- `.c1` **PASS:** step order, every field equal, per `SYS-0077` Accept. **FAIL:** a line out of order, a field differing, or a value not printed.

**`SYT-INS-04`** · T · fixture `F-LM-HELD`, `F-INSPECT` — No bindings, checkout or library needed
**Serves.** `SYS-0078`
**Steps.** Run `attach`, `dump` and `check` from an empty directory with every search-path variable cleared, and again with the lab's libraries and `interfaces` build moved away; compare the outputs with a run with them present.
- `.c1` **PASS:** identical outputs, per `SYS-0078` Accept. **FAIL:** a difference or a start failure.

**`SYT-INS-05`** · T · fixture `F-LM-HELD`, `F-SETUP-EDIT`, `F-INSPECT` — Skipped steps are reported
**Serves.** `SYS-0079`
**Steps.** Run `cut_c` with `livemeas: {cycle_slot_count: 2}` and `dump --follow` paused by the test over M steps, then resumed; run it again with a ring holding the run.
- `.c1` **PASS:** after the pause "N steps skipped", N equal to the steps overwritten, per `SYS-0079` Accept. **FAIL:** no line, or another N.
- `.c2` **PASS:** with the ring holding the run, no such line. **FAIL:** one.

**`SYT-INS-07`** · T · fixture `F-FLAWED-LM`, `F-INSPECT` — A gap in the steps
**Serves.** `SYS-0081`
**Steps.** `check` the flawed live measurement made with `--skip-step 7`, and a clean one made from the same case.
- `.c1` **PASS:** a finding naming 6 and 8, per `SYS-0081` Accept. **FAIL:** none, or other numbers.
- `.c2` **PASS:** the clean one gives none. **FAIL:** a finding.

**`SYT-INS-08`** · T · fixture `F-FLAWED-LM`, `F-INSPECT` — A run without its control, refSync or compState
**Serves.** `SYS-0082`
**Steps.** `check` the flawed live measurement made with `--drop-ref-sync` (one `B` refSync), and a clean one.
- `.c1` **PASS:** a finding naming `B`, its step and `refSync`, per `SYS-0082` Accept. **FAIL:** none, or another stage or port.
- `.c2` **PASS:** the clean one gives none. **FAIL:** a finding.

**`SYT-INS-09`** · T · fixture `F-FLAWED-LM`, `F-LM-HELD`, `F-INSPECT` — A value that is not the recording's
**Serves.** `SYS-0083`
**Steps.** `check --recording` the flawed live measurement made with `--alter-byte`, and every exact case on `F-LM-HELD`.
- `.c1` **PASS:** a finding naming the step and port, per `SYS-0083` Accept. **FAIL:** none.
- `.c2` **PASS:** every exact case gives none. **FAIL:** a finding.

**`SYT-INS-10`** · T · fixture `F-FLAWED-LM`, `F-INSPECT` — A badge count that decreases
**Serves.** `SYS-0084`
**Steps.** `check` the flawed live measurement made with `--lower-badge` on a `missing_sample` case, and a clean one.
- `.c1` **PASS:** a finding naming the badge, its subject and both steps, per `SYS-0084` Accept. **FAIL:** none.
- `.c2` **PASS:** the clean one gives none. **FAIL:** a finding.

**`SYT-INS-11`** · T · fixture `F-FLAWED-LM`, `F-INSPECT` — Findings and the exit code
**Serves.** `SYS-0085`
**Steps.** `check` each flawed live measurement of `SYT-INS-06.c2` and `SYT-INS-07` to `SYT-INS-10`, and a clean lab run; count the printed finding lines.
- `.c1` **PASS:** exit 1 and as many lines as planted flaws, one per line, per `SYS-0085` Accept. **FAIL:** exit 0, or another number of lines.
- `.c2` **PASS:** the clean run exits 0 with no finding line. **FAIL:** any.

**`SYT-INS-12`** · T · fixture `F-LM-HELD`, `F-READER`, `F-INSPECT` — The other exits
**Serves.** `SYS-0086`
**Steps.** Run `vantage-inspect nosuchverb`; `attach` a name no writer holds; `attach` an `F-LM-HELD` run whose layout version the inspector, built one lower, does not read.
- `.c1` **PASS:** exit 2 for the verb, per `SYS-0086` Accept. **FAIL:** another code, or none naming the verb.
- `.c2` **PASS:** exit 6 naming the name, and exit 6 naming both versions with no cycle read. **FAIL:** another code, or a missing name or version.

## 10. The supervisor — `SUP`

**`SYT-SUP-01`** · T · fixture `F-SUPERVISED` — One worker, no grandchild
**Serves.** `SYS-0088`
**Steps.** Run `cut_c` with `--supervise` and without it, listing the process tree once while held.
- `.c1` **PASS:** one child and no grandchild with the flag, none without, per `SYS-0088` Accept. **FAIL:** two children, a grandchild, or a child without the flag.

**`SYT-SUP-02`** · T · fixture `F-SUPERVISED` — The deadline
**Serves.** `SYS-0089`, `SYS-0090`
**Steps.** Run `hang` with a deadline below the hang and `cut_c` with one above it; run `--supervise` without `--attempt-timeout-ms`.
- `.c1` **PASS:** `hang`: the worker gone after the deadline and exit 7, per `SYS-0089` Accept. **FAIL:** the worker alive, or another code.
- `.c2` **PASS:** `cut_c` exits 0. **FAIL:** another code.
- `.c3` **PASS:** no option: exit 2 naming it, no worker, no live measurement, per `SYS-0090` Accept. **FAIL:** a worker starts.

**`SYT-SUP-03`** · T · fixture `F-SUPERVISED`, `F-SETUP-EDIT` — Five outcomes, five endings
**Serves.** `SYS-0091`
**Steps.** Run a passing case, a setup refused at load, `crash`, `hang`, and `cut_c` with the worker binary renamed; collect the five exit codes.
- `.c1` **PASS:** 0, the worker's own non-zero code, 8, 7 and 6, all different, per `SYS-0091` Accept. **FAIL:** two outcomes sharing a code, or a code outside these.

**`SYT-SUP-04`** · T · fixture `F-SUPERVISED` — Never a raw platform code
**Serves.** `SYS-0092`
**Steps.** Run `cut_c` with `ADAS_SIM_TEST_FORCE_ABORT` set, and with the worker killed by the test through a signal or a process kill.
- `.c1` **PASS:** both exit 8, per `SYS-0092` Accept. **FAIL:** a platform status or any other code.

**`SYT-SUP-05`** · T · fixture `F-SUPERVISED`, `F-SETUP-EDIT` — A clean failure is not retried
**Serves.** `SYS-0093`
**Steps.** Run a setup refused at load with `--supervise --restart-on-crash 2`; read the attempt manifest.
- `.c1` **PASS:** one attempt and the worker's own code, per `SYS-0093` Accept. **FAIL:** two attempts, or code 0.

**`SYT-SUP-06`** · T · fixture `F-SUPERVISED` — Restarts are bounded and off by default
**Serves.** `SYS-0094`
**Steps.** Run `crash` with `--restart-on-crash 2`, with no restart option, and `hang` with `--restart-on-crash 2`; read the attempt manifest each time.
- `.c1` **PASS:** `crash` with 2: three attempts, exit 8, per `SYS-0094` Accept. **FAIL:** another count.
- `.c2` **PASS:** without the option, one attempt. **FAIL:** more.
- `.c3` **PASS:** `hang`: one attempt, exit 7. **FAIL:** a restart.

**`SYT-SUP-07`** · T · fixture `F-SUPERVISED` — The seal
**Serves.** `SYS-0095`
**Steps.** Run `crash` and `hang` on `F-SUPERVISED` with the reader attached; read status and outcome after the supervisor's exit, and the time of the first status change against the worker's end.
- `.c1` **PASS:** `crash`: finished with `crash`, per `SYS-0095` Accept. **FAIL:** status running, or another outcome.
- `.c2` **PASS:** `hang`: finished with `timeout`. **FAIL:** as `.c1`.
- `.c3` **PASS:** the status changes only after the worker has ended. **FAIL:** before.

**`SYT-SUP-08`** · T · fixture `F-SUPERVISED` — The seal writes two fields
**Serves.** `SYS-0096`
**Steps.** Run `cut_c` on `F-SUPERVISED`, the worker held (`F-LM-HELD`); copy both segments through the attached reader, kill the worker with a process kill, and copy them again after the supervisor's exit; compare byte for byte.
- `.c1` **PASS:** only `outcome` and `status` differ, `outcome` reading `crash`, per `SYS-0096` Accept. **FAIL:** any other byte differs, or another outcome.

**`SYT-SUP-09`** · T · fixture `F-SUPERVISED` — No seal of a live or self-closed run
**Serves.** `SYS-0097`
**Steps.** Run `cut_c` (passes) and `crash` on `F-SUPERVISED`; sample status and outcome while the worker lives and after.
- `.c1` **PASS:** `cut_c`: outcome stays `pass`, segments unchanged by the supervisor, per `SYS-0097` Accept. **FAIL:** a change.
- `.c2` **PASS:** `crash`: status not finished while the worker lives. **FAIL:** finished before its end.

**`SYT-SUP-10`** · T · fixture `F-SUPERVISED`, `F-SETUP-EDIT` — Nothing to seal
**Serves.** `SYS-0098`
**Steps.** Run `crash` with `outputs.livemeas` removed; list the live measurements that exist.
- `.c1` **PASS:** exit 8 and none created, per `SYS-0098` Accept. **FAIL:** one created, or another code.

**`SYT-SUP-11`** · T · fixture `F-SUPERVISED` — The attempt manifest
**Serves.** `SYS-0099`
**Steps.** Run `crash` with `--restart-on-crash 1`; read the attempt manifest.
- `.c1` **PASS:** two records numbered 1 and 2, outcome `crash` in both, the second marked last, per `SYS-0099` Accept. **FAIL:** another count, number, outcome or last mark.

**`SYT-SUP-12`** · T · fixture `F-SUPERVISED` — The stage in the record
**Serves.** `SYS-0100`
**Steps.** Run `crash`, `hang`, and `cut_c` with `ADAS_SIM_TEST_FORCE_ABORT`; read each record's stage.
- `.c1` **PASS:** `B` for `crash` and `hang`, per `SYS-0100` Accept. **FAIL:** another stage or none.
- `.c2` **PASS:** `unknown` for the abort before any call. **FAIL:** a stage.

**`SYT-SUP-13`** · T · fixture `F-SUPERVISED` — The reproducer
**Serves.** `SYS-0101`
**Steps.** Run `crash`, `hang` and a passing case on `F-SUPERVISED`; read the reproducer folder, and the highest step the attached reader read.
- `.c1` **PASS:** `crash`: setup equal to the run's, last step equal to the highest step read, run id, standard error, and `B`, per `SYS-0101` Accept. **FAIL:** a missing item or another value.
- `.c2` **PASS:** none after `hang` or a pass. **FAIL:** a package written.

**`SYT-SUP-14`** · T · fixture `F-ISOLATE` — An isolated stage's crash
**Serves.** `SYS-0102`
**Steps.** Host `B` of `crash` through `F-ISOLATE`; read its report and whether the asker's process lives when `B`'s ended.
- `.c1` **PASS:** outcome `crash`, exit 8, `B` named, the asker alive, per `SYS-0102` Accept. **FAIL:** the asker ends, or the stage is unnamed.

**`SYT-SUP-15`** · T · fixture `F-CAT`, `F-SUPERVISED`, `F-COMPARE` — Supervision changes no output
**Serves.** `SYS-0103`
**Steps.** Run every exact case with `--supervise` and started directly; compare the engine-run recordings through `F-COMPARE` and the event logs line by line.
- `.c1` **PASS:** equal outputs and identical event logs, per `SYS-0103` Accept. **FAIL:** any difference.

## 11. Analysis — `ANL`

**`ANL-01`** · A · fixture `F-SRC` — Decisions read no clock and no other payload
**Serves.** `SYS-0017`
**Steps.** Run `scripts/check_engine_decisions.py` over the tree; then over a copy with a planted `std::chrono::steady_clock::now()` call in `src/simcore/orchestrator/orchestrator.cpp`, and over a copy with a planted `ParseFromArray` on an `adas::common::VehDyn` in `src/simcore/runner/select_inputs.cpp`.
- `.c1` **PASS:** no finding, per `SYS-0017` Accept. **FAIL:** any finding.
- `.c2` **PASS:** the planted clock call is reported with file and line. **FAIL:** the copy passes.
- `.c3` **PASS:** the planted payload parse is reported with file and line. **FAIL:** the copy passes.

**`ANL-02`** · A · fixture `F-SRC` — Counters compared only by `counterDistance`
**Serves.** `SYS-0031`
**Steps.** Run `scripts/check_counter_compare.py` over the tree; then over a copy with a planted `a.measurement_counter < b.measurement_counter` in `src/simcore/bus/sample_buffer.cpp`, over a copy with a planted `a.measurement_counter == b.measurement_counter` in `src/simcore/orchestrator/orchestrator.cpp`, and over a copy with a planted `header.cycle_counter != 0` in `src/simcore/runner/run_stage.cpp`.
- `.c1` **PASS:** no finding, per `SYS-0031` Accept. **FAIL:** any finding.
- `.c2` **PASS:** the planted `<` is reported with file and line. **FAIL:** the copy passes.
- `.c3` **PASS:** the planted `==` is reported with file and line. **FAIL:** the copy passes.
- `.c4` **PASS:** the planted comparison with 0 is reported with file and line. **FAIL:** the copy passes.

**`ANL-03`** · A · fixture `F-SRC` — No floating-point time in the engine
**Serves.** `SYS-0038`
**Steps.** Run `scripts/check_time_units.py` over the tree; then over a copy with a planted `double step_time = 0;` in `src/simcore/orchestrator/event_queue.cpp`.
- `.c1` **PASS:** no finding, per `SYS-0038` Accept. **FAIL:** any finding.
- `.c2` **PASS:** the planted declaration is reported. **FAIL:** the copy passes.

**`ANL-04`** · A · fixture `F-SRC-LM` — One carrier of step values
**Serves.** `SYS-0074`
**Steps.** Run `scripts/check_single_carrier.py` over the tree; then over a copy with a planted `SetTransportPublisher(nullptr)` call in `src/simcore/abi/simcore.cpp`, and over a copy with a planted `#include "simcore/transport_shm.hpp"` in `src/simcore/runner/cycle_loop.cpp`.
- `.c1` **PASS:** no finding, per `SYS-0074` Accept. **FAIL:** any finding.
- `.c2` **PASS:** the planted call is reported with file and line. **FAIL:** the copy passes.
- `.c3` **PASS:** the planted include is reported with file and line. **FAIL:** the copy passes.

**`ANL-05`** · A · fixture `F-SRC-LM` — `check` holds no stage or port name
**Serves.** `SYS-0087`
**Steps.** Run `scripts/check_inspector_items.py` over `src/inspector`; then over a copy with a planted `"B.refSync"` string in `src/inspector/check.cpp`.
- `.c1` **PASS:** no finding, per `SYS-0087` Accept. **FAIL:** any finding.
- `.c2` **PASS:** the planted string is reported with file and line. **FAIL:** the copy passes.

**`ANL-06`** · A · fixture `F-SRC-LM` — The supervisor runs nothing and writes only the seal
**Serves.** `SYS-0104`
**Steps.** Run `scripts/check_supervisor_boundary.py` over `src/simengine`; then over a copy with a planted `liveMeasStep(handle, 0, 0, nullptr, 0, nullptr, 0)` in `RunWithSupervision`, and over a copy with a planted `Component::Exec` call there.
- `.c1` **PASS:** no finding, per `SYS-0104` Accept. **FAIL:** any finding.
- `.c2` **PASS:** the planted `liveMeasStep` is reported with file and line. **FAIL:** the copy passes.
- `.c3` **PASS:** the planted `Exec` call is reported with file and line. **FAIL:** the copy passes.

## 12. Thresholds not yet supplied

No pass bound here is a `⊘`: every pass is equality with the fake car's recording or a count the
recording gives. The `⊘` values of the run setup (`VANTAGE_Architecture.md` §4) are run inputs,
taken from the lab's provisional values (`VANTAGE_Lab_Design.md` §7), never pass bounds.

---

## What this document does not contain

- **Expected values** — they are the requirements' `Accept` clauses.
- **Verification status** — the execution record (`R-REQ-6`).
- **Coverage counts** — emitted by the checker.
