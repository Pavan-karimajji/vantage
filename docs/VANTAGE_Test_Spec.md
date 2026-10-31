# VANTAGE — Test Specification

**One file, one layer.** `SYT-<area>-nn` and `ANL-nn` verify `VANTAGE_System_Requirements.md`
(areas declared there: `RUN`, `ORC`, `SEL`, `STP`, `THR`, `EQO`). A test cites its
requirement's `Accept` by UID and never restates it (`R-REQ-4`); every case states its FAIL
side (`R-REQ-5`). Part 8a: the orchestrator (`C1`). The lab cases named in the steps are those
of `VANTAGE_Lab_Design.md` §6, written topology, scenario (`base` unless named) and resim case.

## Fixture catalogue

| Fixture | What it is |
|---|---|
| `F-CAT` | Every topology of the lab catalogue built: each scenario's recording, each resim case's run setup, and the libraries, found by `tests/support/lab_cases.py`. An *exact case* is a resim case whose scenario expects `exact` and that is not `hang` or `crash` (they need the supervisor, part 8b) |
| `F-CASE` | One named lab case of `F-CAT` |
| `F-SETUP-EDIT` | An `F-CASE` run setup copied by the test with the one change its steps name (`edit_setup`) |
| `F-REC-EDIT` | An `F-CASE` recording rewritten by the test through the Python writer in `interfaces` with the one edit its steps name: a split into files, messages removed or changed, a cut (`edit_recording`) |
| `F-ENGINE` | `simengine` run as a process on a setup with `outputs.path` set: the engine-run recording, the event log lines, the printed plan and the exit code |
| `F-TAP` | `tests/support/step_tap` run on a setup: one line per engine step with its number, simulation time and badges; optionally one jump, at 500 ms to the case's `jump_to_ms` unless the steps say otherwise |
| `F-PROBE` | The exec probe (`tests/fixtures/exec_probe`) put by the test in place of named stages' libraries, one copy per path the steps name, and its call log |
| `F-COMPARE` | The lab's comparator, `lab_tools.compare.equal_outputs` (`VANTAGE_Lab_Design.md` §6.4), over two recordings; independent of Vantage's own comparison |
| `F-SRC` | `include/simcore`, `src/simcore` and `src/simengine` as checked in, and per check a copy with one planted violation |
| `F-RENUMBER-LIB` | `running_example` `renumber_lib` `shifted` (`VANTAGE_Lab_Design.md` `LAB-WP-10`): `A`'s bundle sets `LAB_A_RENUMBER`, so `A`'s own code writes its data outputs' `measurement_counter` shifted from its control's |

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
**Steps.** To copies of `running_example` `cut_c`'s setup add, one per copy, `delay_steps` to one input, `grid_step_ns` and `order` at the top level, and an unknown key `colour` to one stage; run each.
- `.c1` **PASS:** each retired key gives a load error naming the key and where it is, per `SYS-0046` Accept. **FAIL:** a run starts, or the message lacks the key or its place.
- `.c2` **PASS:** `colour` gives a load error naming it and its stage. **FAIL:** a run starts, or the key is ignored.

## 3. The orchestrator — `ORC`

**`SYT-ORC-01`** · T · fixture `F-CASE`, `F-ENGINE` — Rank order inside a step
**Serves.** `SYS-0009`
**Steps.** Run `running_example` `no_ref_sync`; for each step whose controls include both `A` and `B`, read `B`'s re-run refSync entry for `A` and `A`'s output of that step.
- `.c1` **PASS:** the entry names `A`'s output of that step, per `SYS-0009` Accept. **FAIL:** it names an older sample.

**`SYT-ORC-02`** · T · fixture `F-CASE`, `F-ENGINE` — A loop without a previous-cycle input refused
**Serves.** `SYS-0010`
**Steps.** Run `loop_no_edge`; then `feedback` `all_simulated`.
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
**Serves.** `SYS-0012`
**Steps.** For every exact case count each simulated stage's controls in the engine-run recording and in the recording; on `data_triggered` `by_data`, count `T`'s controls and the `in_X` samples.
- `.c1` **PASS:** equal counts in every exact case, per `SYS-0012` Accept. **FAIL:** any count differs.
- `.c2` **PASS:** `by_data`: one `T` control per `in_X` sample. **FAIL:** another count.

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
**Steps.** Cut `late_consumer`'s `base` recording just after a `Q` control whose recorded refSync names a `P` sample logged after it; run `all_simulated` on it on `F-TAP` and `F-ENGINE`.
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
**Steps.** Remove the first five `source.Y` samples from `running_example`'s `base` recording; run `all_simulated`; read the re-run entries for `Y` of every run before the first remaining `source.Y` sample.
- `.c1` **PASS:** every entry 0, per `SYS-0027` Accept. **FAIL:** a non-zero entry.

**`SYT-SEL-09`** · T · fixture `F-CAT`, `F-SETUP-EDIT`, `F-TAP` — Selection outcomes raise their badges
**Serves.** `SYS-0028`
**Steps.** Run `running_example` `missing_sample`, `missing_run` and `no_ref_sync`, `late_consumer` `all_simulated` with `readiness_limit_steps` 0, and every exact case; for each step derive the `KIND_FALLBACK` and `KIND_READINESS_TIMEOUT` badges the table of `VANTAGE_Architecture.md` §6 gives for its selections; compare with the step's badges.
- `.c1` **PASS:** equal in every step, per `SYS-0028` Accept. **FAIL:** a missing, extra or misplaced badge, naming case, step and port.

**`SYT-SEL-10`** · T · fixture `F-CAT`, `F-TAP` — Identity broken is badged
**Serves.** `SYS-0029`
**Steps.** Run `data_triggered` `renumber` `by_data` and every exact case; read every `KIND_IDENTITY_BROKEN` badge.
- `.c1` **PASS:** `renumber`: raised on `T`'s output port, per `SYS-0029` Accept. **FAIL:** not raised, or raised on another port.
- `.c2` **PASS:** exact cases: never raised. **FAIL:** any.

**`SYT-SEL-11`** · T · fixture `F-CASE`, `F-REC-EDIT`, `F-ENGINE`, `F-TAP` — Gaps and resets are counted
**Serves.** `SYS-0030`
**Steps.** Run `running_example` `counter_jump` `all_simulated`; read the `counter_gap` and `counter_reset` entries for `source.X`. In `running_example`'s `base` recording restart `source.X`'s `measurement_counter` and `cycle_counter` at 1 from its 100th sample; run `all_simulated` on `F-ENGINE` and `F-TAP`.
- `.c1` **PASS:** `counter_jump`: one gap and no reset on `source.X`, per `SYS-0030` Accept. **FAIL:** another count.
- `.c2` **PASS:** restarted: one reset on `source.X` and no `KIND_IDENTITY_BROKEN` on it. **FAIL:** another count, or the badge.

## 5. The engine step — `STP`

**`SYT-STP-01`** · T · fixture `F-CASE`, `F-SETUP-EDIT`, `F-TAP` — One step per instant
**Serves.** `SYS-0032`
**Steps.** Run `running_example` `cut_c` on `F-TAP`; list the recording's distinct reception times. Then set `E`'s trigger empty and `clock_period_ns` to 7 ms, and run again.
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
- `.c1` **PASS:** as `SYS-0045` Accept, `no_ref_sync`'s step count equal to the recording's distinct reception times. **FAIL:** a fail outcome, or fewer steps.

## 8. Analysis — `ANL`

**`ANL-01`** · A · fixture `F-SRC` — Decisions read no clock and no payload
**Serves.** `SYS-0017`
**Steps.** Run `scripts/check_engine_decisions.py` over the tree; then over a copy with a planted `std::chrono::steady_clock::now()` call in `src/simcore/orchestrator/orchestrator.cpp`, and over a copy with a planted `ParseFromArray` in `src/simcore/runner/select_inputs.cpp`.
- `.c1` **PASS:** no finding, per `SYS-0017` Accept. **FAIL:** any finding.
- `.c2` **PASS:** the planted clock call is reported with file and line. **FAIL:** the copy passes.
- `.c3` **PASS:** the planted payload parse is reported with file and line. **FAIL:** the copy passes.

**`ANL-02`** · A · fixture `F-SRC` — Counters compared only by `counterDistance`
**Serves.** `SYS-0031`
**Steps.** Run `scripts/check_counter_compare.py` over the tree; then over a copy with a planted `a.measurement_counter < b.measurement_counter` in `src/simcore/bus/sample_buffer.cpp`, and over a copy with a planted `a.measurement_counter == b.measurement_counter` in `src/simcore/orchestrator/orchestrator.cpp`.
- `.c1` **PASS:** no finding, per `SYS-0031` Accept. **FAIL:** any finding.
- `.c2` **PASS:** the planted `<` is reported with file and line. **FAIL:** the copy passes.
- `.c3` **PASS:** the planted `==` is reported with file and line. **FAIL:** the copy passes.

**`ANL-03`** · A · fixture `F-SRC` — No floating-point time in the engine
**Serves.** `SYS-0038`
**Steps.** Run `scripts/check_time_units.py` over the tree; then over a copy with a planted `double step_time = 0;` in `src/simcore/orchestrator/event_queue.cpp`.
- `.c1` **PASS:** no finding, per `SYS-0038` Accept. **FAIL:** any finding.
- `.c2` **PASS:** the planted declaration is reported. **FAIL:** the copy passes.

## 9. Thresholds not yet supplied

No pass bound here is a `⊘`: every pass is equality with the fake car's recording or a count the
recording gives. The `⊘` values of the run setup (`VANTAGE_Architecture.md` §4) are run inputs,
taken from the lab's provisional values (`VANTAGE_Lab_Design.md` §7), never pass bounds.

---

## What this document does not contain

- **Expected values** — they are the requirements' `Accept` clauses.
- **Verification status** — the execution record (`R-REQ-6`).
- **Coverage counts** — emitted by the checker.
