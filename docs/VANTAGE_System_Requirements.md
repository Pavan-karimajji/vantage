# VANTAGE — the simulation tool
## System Requirements Specification — v0.1

**Owner:** Vantage program (vantage-dev, Plan C)
**Layer:** `SYS`, the top declared layer (`layers.yaml`), so every `Trace` is `—`.
**Status:** Draft for review. Not baselined. Part 8a of `VANTAGE_DEV_PLAN.md` §6 step 8: the
orchestrator (`C1`). Parts 8b and 8c add their sections after §6.
**Reader:** anyone holding a run setup, a recording and component libraries, with no source
access. What each part is for, every name and every rule: `VANTAGE_Architecture.md` (cited as
`ARCH §n`). What becomes of each sim requirement: `VANTAGE_Migration_Register.md`. The lab
cases named below: `VANTAGE_Lab_Design.md` §6. Tests: `VANTAGE_Test_Spec.md`.

**The contract is obeyed, never restated.** Vantage is *the scheduler* of the contract
(`modules/interfaces/docs/resim_contract/`), so `RCT:SYS-0009`..`RCT:SYS-0012` (the control
message it writes, amended by `D17 (1)`) bind it as written, and `RCT:IMP-0032` and
`RCT:IMP-0033` build its control writing and its input selection. **Equal outputs** is the term
of the `RCT_System_Requirements.md` preamble.

**Subjects.** *The engine* is `simengine` and the engine library it runs. *A lab case* is one
resim case of one scenario of one topology of the lab catalogue; *an exact case* is one whose
scenario expects `exact` and that needs no supervisor. *The re-run refSync* is the `refSync` a
simulated stage writes in the engine run, which names what the engine handed it
(`RCT:SYS-0014`).

**Test areas**, declared once: `RUN` the run setup · `ORC` the orchestrator and the six rules ·
`SEL` input selection · `STP` the engine step · `THR` threads · `EQO` equal outputs and the
first divergence.
Priority split: 23 `P0`, 24 `P1`, 0 `P2`; all `R1`. Without a `P0` row an engine run is not
exact against the car; a `P1` row makes a result easier to trust or diagnose.

---

# PART A — FUNCTIONAL REQUIREMENTS

## 1. The run setup (`RUN`)

The keys and their meaning: `ARCH §2.3`, `§4`. One engine run reads one recording; many
recordings are a batch of engine runs (`R-SIM-19`).

**`SYS-0001`** · `P0` · `R1` — The run setup is the engine's only input
**Shall.** The engine shall take every choice of an engine run from the run setup, the recording it names, `--threads` and `--wait-for-attach` only.
**Accept.** Run from another directory with no Python, YAML, ingest map or library search path reachable, a lab case gives equal outputs, on every port, to the same case run beside its setup.
**Binds.** `runSetup`, `recording`, `runRecording`
**Verify.** T · `SYT-RUN-01`   **Trace.** —

**`SYS-0002`** · `P0` · `R1` — `sampling` and `on_missing` are refused at load
**Shall.** The engine shall refuse at load a run setup in which any port carries `sampling` or `on_missing` (`D18 (4)`).
**Accept.** A lab setup with either key added to one port ends with a load error naming the key, the stage and the port, before the first step; a setup that runs fails.
**Binds.** `runSetup`, `exitStatus`
**Verify.** T · `SYT-RUN-02`   **Trace.** —

**`SYS-0003`** · `P0` · `R1` — A missing `⊘` value is refused at load
**Shall.** The engine shall refuse at load a run setup missing any value `ARCH §4` marks `⊘`, and supply no default.
**Accept.** With each such key removed in turn from a lab setup that has `outputs.livemeas`, the engine ends with a load error naming that key before the first step; one run that starts fails.
**Binds.** `runSetup`, `exitStatus`
**Verify.** T · `SYT-RUN-03`   **Trace.** —

**`SYS-0004`** · `P1` · `R1` — Only the accepted schema version is loaded
**Shall.** The engine shall load only a run setup whose `schema` is `adas.sim.runspec/2.0`.
**Accept.** A lab setup with `schema` changed to any other string, or removed, ends with a load error naming the string found and `adas.sim.runspec/2.0`; a run that starts fails.
**Binds.** `runSetup`, `exitStatus`
**Verify.** T · `SYT-RUN-04`   **Trace.** —

**`SYS-0005`** · `P0` · `R1` — The files of `sources[]` are one recording
**Shall.** An engine run shall read the files of `sources[]` as one recording, merged into one event stream by reception time.
**Accept.** A lab recording split by topic into two files listed in `sources[]` gives equal outputs, on every port, and the same number of steps as the unsplit recording.
**Binds.** `recording`, `runRecording`
**Verify.** T · `SYT-RUN-05`   **Trace.** —

**`SYS-0006`** · `P1` · `R1` — A port keeps at most `buffer_depth` samples
**Shall.** The engine shall keep no more than `buffer_depth` samples of a port, so an older sample is not found.
**Accept.** With `buffer_depth` 1 on every port of `running_example` `all_simulated`, each run whose recorded refSync names a sample older than its port's newest raises `KIND_FALLBACK` on that port; with the lab's provisional depth, the case raises none.
**Binds.** `runSetup`, `stageIn`, `stepRecord`
**Verify.** T · `SYT-RUN-06`   **Trace.** —

**`SYS-0007`** · `P0` · `R1` — A `measured` stage whose outputs are not recorded is refused
**Shall.** The engine shall refuse at load a `measured` stage whose outputs the recording does not hold, naming the stage and the ports.
**Accept.** `running_example` `cut_c` with `C`'s output topic removed from the recording ends with a load error naming `C` and that port, before the first step; a run that starts fails.
**Binds.** `runSetup`, `recording`, `exitStatus`
**Verify.** T · `SYT-RUN-07`   **Trace.** —

**`SYS-0008`** · `P0` · `R1` — A `measured` or `off` stage is never called
**Shall.** The engine shall never call the library of a `measured` or `off` stage.
**Accept.** With the exec probe as stage `C` of `running_example`, set `measured` and then `off`, the probe logs no call; set `simulate`, it logs one call per `C` control.
**Binds.** `stageIn`
**Verify.** T · `SYT-RUN-08`   **Trace.** —

**`SYS-0046`** · `P1` · `R1` — Retired and unknown run setup keys are refused at load
**Shall.** The engine shall refuse at load a run setup carrying `delay_steps`, `grid_step_ns`, `order` or any key its schema does not name.
**Accept.** A lab setup with any one such key added ends with a load error naming the key and where it is (top level, stage, port or input), before the first step; a run that starts fails.
**Binds.** `runSetup`, `exitStatus`
**Verify.** T · `SYT-RUN-09`   **Trace.** —

## 2. The orchestrator and the six rules (`ORC`)

The rules, why each exists and where it is kept: `ARCH §5`. What the orchestrator decides and
never does: `ARCH §3.2`. Ranks: `ARCH §2.2`.

**`SYS-0009`** · `P0` · `R1` — Runs of one step go in rank order
**Shall.** In each engine step the engine shall complete every run of a lower rank before it starts a run of a higher rank.
**Accept.** On `running_example` `no_ref_sync`, in every step where `A` and `B` both run, `B`'s re-run refSync entry for `A` names `A`'s sample of that step; an older sample fails.
**Binds.** `stageOut`, `stageIn`
**Verify.** T · `SYT-ORC-01`   **Trace.** —

**`SYS-0010`** · `P0` · `R1` — A loop without a previous-cycle input is refused
**Shall.** The engine shall refuse at load a run setup whose simulated stages form a loop not broken by a `previous_cycle` input, naming the stages of the loop.
**Accept.** `loop_no_edge` ends with a load error naming `A` and `B`, before the first step; `feedback` loads and runs to the end.
**Binds.** `runSetup`, `exitStatus`
**Verify.** T · `SYT-ORC-02`   **Trace.** —

**`SYS-0011`** · `P0` · `R1` — Every simulated stage has exactly one way to start
**Shall.** The engine shall refuse at load a simulated stage not started by exactly one of a recorded `control`, a declared trigger input or a clock above 0.
**Accept.** A stage given a `control` trigger the recording lacks, an undeclared trigger input, no trigger and clock 0, or both, each gives a load error naming the stage and what was expected.
**Binds.** `runSetup`, `recording`, `exitStatus`
**Verify.** T · `SYT-ORC-03`   **Trace.** —

**`SYS-0012`** · `P0` · `R1` — One run per trigger, and no other run
**Shall.** The engine shall start one run of a stage for each recorded control, new trigger-input `measurement_counter` or clock tick that starts it, and no other run.
**Accept.** In every exact case each simulated stage's control count in the engine-run recording equals its recorded control count; on `data_triggered` `by_data` it equals the number of `in_X` samples.
**Binds.** `recording`, `control`
**Verify.** T · `SYT-ORC-04`   **Trace.** —

**`SYS-0013`** · `P1` · `R1` — An output that does not copy its control's counter is logged
**Shall.** The engine shall log, with stage, port and step, every simulated output whose `measurement_counter` differs from its control's, and continue the engine run (`D18 (2)`).
**Accept.** With a lab component that renumbers its outputs, the event log has one such entry per affected output and the engine run reaches the recording's end; a missing entry or a stop fails.
**Binds.** `stageOut`, `eventLog`
**Verify.** T · `SYT-ORC-05`   **Trace.** —

**`SYS-0014`** · `P0` · `R1` — A stage's runs go strictly in order
**Shall.** The engine shall not start a run of a stage while an earlier run of that stage is not committed.
**Accept.** On `late_consumer` `all_simulated`, each stage's controls in the engine-run recording follow the order of their triggers, each followed by its own outputs before the next control; any other order fails.
**Binds.** `control`, `stageOut`, `runRecording`
**Verify.** T · `SYT-ORC-06`   **Trace.** —

**`SYS-0015`** · `P0` · `R1` — A run waits for a named sample up to the readiness limit
**Shall.** A run whose recorded refSync names a sample not yet present shall wait, in event order, until it is present or `readiness_limit_steps` steps have passed.
**Accept.** On `late_consumer`, `all_simulated` and `cut_p`, every `Q` re-run entry for `P` equals its recorded entry; with `readiness_limit_steps` 0, at least one `Q` run raises `KIND_READINESS_TIMEOUT` instead.
**Binds.** `recording`, `stageIn`, `stepRecord`
**Verify.** T · `SYT-ORC-07`   **Trace.** —

**`SYS-0016`** · `P1` · `R1` — The recording's end runs every waiting ticket
**Shall.** At the recording's end, the engine shall run every parked ticket in the last step with the readiness outcome of `ARCH §6`.
**Accept.** A `late_consumer` recording cut just after a `Q` control whose named `P` sample comes later gives that `Q` run in the last step with `KIND_READINESS_TIMEOUT`; a missing run fails.
**Binds.** `recording`, `control`, `stepRecord`
**Verify.** T · `SYT-ORC-08`   **Trace.** —

**`SYS-0017`** · `P0` · `R1` — Decisions come from the run setup and the headers alone
**Shall.** The orchestrator and input selection shall decide from the run setup and the samples' `sig_header` only, reading no clock, thread id, execution time or other payload field.
**Accept.** The source check over their files finds no clock, thread-id or timer call and no payload parse except `ReadSignalHeader`; with one such call planted, it fails.
**Binds.** `runSetup`, `control`, `stageIn`
**Verify.** A · `ANL-01`   **Trace.** —

**`SYS-0018`** · `P1` · `R1` — A simulated stage nobody simulated consumes is badged
**Shall.** The engine shall raise `KIND_COMPUTED_NOT_CONSUMED` once on a simulated stage that has declared consumers, none of them simulated.
**Accept.** On `measured_middle` `cut_m`, `A` carries the badge and no other stage does; on `fan_out` `all_simulated`, no stage carries it.
**Binds.** `stepRecord`
**Verify.** T · `SYT-ORC-09`   **Trace.** —

**`SYS-0019`** · `P1` · `R1` — The engine prints its plan without running
**Shall.** The engine shall print, from the run setup alone and calling no component, each simulated stage's rank, trigger or clock and previous-cycle inputs.
**Accept.** For every lab setup, with every component library removed, the printed plan gives each simulated stage the rank, trigger, clock and previous-cycle inputs its topology file implies; one mismatch fails.
**Binds.** `runSetup`, `plan`
**Verify.** T · `SYT-ORC-10`   **Trace.** —

**`SYS-0047`** · `P1` · `R1` — A repeated trigger sample starts no run and is logged as stalled
**Shall.** A trigger-input sample at `counterDistance` 0 from the last one that started a run, with the same content, shall start no run and be counted as a stalled trigger in the event log.
**Accept.** On `data_triggered` `repeat_trigger` `by_data`, `T` runs once per distinct `in_X` counter and the event log counts one stalled trigger on `T`; an extra `T` run fails.
**Binds.** `recording`, `control`, `eventLog`
**Verify.** T · `SYT-ORC-11`   **Trace.** —

## 3. Input selection (`SEL`)

The order of the rules and the table of outcomes: `ARCH §6`, `D18 (1)`. Matching is by
`measurement_counter` only; every comparison of two counters is `counterDistance`
(`RCT:SYS-0005`).

**`SYS-0020`** · `P0` · `R1` — Inputs are chosen by the recorded refSync
**Shall.** For a run with a recorded refSync, the engine shall hand each input the sample whose `measurement_counter` equals that refSync's entry for it.
**Accept.** In every exact case every re-run refSync entry equals the recorded one in `measurement_counter` and `source_timestamp_us`; one difference fails.
**Binds.** `recording`, `stageIn`
**Verify.** T · `SYT-SEL-01`   **Trace.** —

**`SYS-0021`** · `P1` · `R1` — An entry 0 gives an empty input and no badge
**Shall.** For a recorded refSync entry of 0, the engine shall hand that input empty and raise no badge for it.
**Accept.** With one recorded refSync entry set to 0, that run's re-run entry for the input is 0 and its step carries no badge on that port; any other result fails.
**Binds.** `recording`, `stageIn`, `stepRecord`
**Verify.** T · `SYT-SEL-02`   **Trace.** —

**`SYS-0022`** · `P0` · `R1` — A named sample not found falls back by counter
**Shall.** When the named sample is not found, the engine shall hand the newest sample on the port whose `measurement_counter` is not after the wanted one, within `fallback_max_gap`.
**Accept.** On `missing_sample`, every run whose recorded entry names a dropped `source.Y` counter gets the newest present `source.Y` sample below it, as its re-run entry shows; any other sample fails.
**Binds.** `recording`, `stageIn`
**Verify.** T · `SYT-SEL-03`   **Trace.** —

**`SYS-0023`** · `P0` · `R1` — Beyond `fallback_max_gap` the time rule picks
**Shall.** When the counter fallback's best sample is more than `fallback_max_gap` counter steps from the wanted one, the engine shall hand the sample the time rule picks.
**Accept.** On `missing_run`, every run whose wanted counter is more than `fallback_max_gap` past the newest present one gets the newest `source.Y` sample not after its control's time; any other sample fails.
**Binds.** `recording`, `stageIn`
**Verify.** T · `SYT-SEL-04`   **Trace.** —

**`SYS-0024`** · `P1` · `R1` — A fallback beyond the gap is written to the event log
**Shall.** For each input the time rule picks beyond `fallback_max_gap`, the engine shall write one event log entry with stage, port, wanted counter, found counter and gap.
**Accept.** On `missing_run`, the event log holds exactly one such entry per run of `SYS-0023`'s Accept, with the five values the recording gives; a missing, extra or wrong entry fails.
**Binds.** `eventLog`
**Verify.** T · `SYT-SEL-05`   **Trace.** —

**`SYS-0025`** · `P0` · `R1` — A stage with no recorded refSync uses the time rule
**Shall.** For a stage with no recorded refSync, the engine shall hand each input the newest arrived sample not after the trigger's `source_timestamp_us`, or, when either time is 0, the newest arrived.
**Accept.** On `no_ref_sync`, every re-run entry names that sample among the samples logged at or before the run's step; a sample logged later, or an older one, fails.
**Binds.** `recording`, `stageIn`
**Verify.** T · `SYT-SEL-06`   **Trace.** —

**`SYS-0026`** · `P1` · `R1` — A previous-cycle input never sees the current step
**Shall.** Under either fallback, the engine shall hand a `previous_cycle` input only samples committed in an earlier step.
**Accept.** On `feedback` `all_simulated` with its refSync topics removed, every `A` run's re-run entry for `B` names a `B` sample of an earlier step; one of the same step fails.
**Binds.** `stageIn`
**Verify.** T · `SYT-SEL-07`   **Trace.** —

**`SYS-0027`** · `P1` · `R1` — No sample found gives an empty input
**Shall.** When neither the counter fallback nor the time rule finds a sample, the engine shall hand the input empty.
**Accept.** With the first five `source.Y` samples removed from `running_example`'s `base` recording, every run before the first remaining one has re-run entry 0 for `Y`; a non-zero entry fails.
**Binds.** `recording`, `stageIn`
**Verify.** T · `SYT-SEL-08`   **Trace.** —

**`SYS-0028`** · `P0` · `R1` — Selection outcomes raise the badges `ARCH §6` names
**Shall.** For each input selection outcome of `ARCH §6`, the engine shall raise `KIND_FALLBACK` and `KIND_READINESS_TIMEOUT` exactly as that table names them, on its subject.
**Accept.** On `missing_sample`, `missing_run`, `no_ref_sync`, `late_consumer` with limit 0 and every exact case, each step's badges equal those the table gives for that step's selections; a missing, extra or misplaced badge fails.
**Binds.** `stepRecord`
**Verify.** T · `SYT-SEL-09`   **Trace.** —

**`SYS-0029`** · `P1` · `R1` — Identity broken is badged on the port
**Shall.** The engine shall raise `KIND_IDENTITY_BROKEN` on a port whose samples break identity as `D17 (3)` defines it.
**Accept.** On `data_triggered` `renumber`, the badge is raised on `T`'s output port as `VANTAGE_Lab_Design.md` §6.2 expects; in every exact case it is never raised.
**Binds.** `recording`, `stepRecord`
**Verify.** T · `SYT-SEL-10`   **Trace.** —

**`SYS-0030`** · `P1` · `R1` — Counter gaps and resets are counted in the event log
**Shall.** The engine shall count in the event log every counter gap and every counter reset (`D17 (3)`) on each port.
**Accept.** On `counter_jump`, it counts one gap on `source.X` and no reset; with `source.X`'s counters restarted at 1 mid-recording, one reset and no identity broken; a wrong count fails.
**Binds.** `recording`, `eventLog`
**Verify.** T · `SYT-SEL-11`   **Trace.** —

**`SYS-0031`** · `P1` · `R1` — Counters are compared only by `counterDistance`
**Shall.** The engine shall compare `measurement_counter` and `cycle_counter` values only through `counterDistance` (`RCT:SYS-0005`).
**Accept.** The source check over the engine finds no `==`, `!=`, `<`, `>`, `<=` or `>=` applied to either counter; with one planted comparison, it fails.
**Binds.** `stageIn`
**Verify.** A · `ANL-02`   **Trace.** —

## 4. The engine step (`STP`)

What one step is, the jump and warming up: `ARCH §7`. The word "tick" is retired; the step
number takes its place.

**`SYS-0032`** · `P0` · `R1` — One engine step per instant at which anything happens
**Shall.** The engine shall make one engine step for each instant at which a recorded message arrives or a clock ticks, numbered from 0 without a gap.
**Accept.** On `running_example` `cut_c`, the steps are the recording's distinct reception times, numbered consecutively from 0; with `E` started by a 7 ms clock instead, each tick instant adds its step.
**Binds.** `recording`, `stepRecord`
**Verify.** T · `SYT-STP-01`   **Trace.** —

**`SYS-0033`** · `P1` · `R1` — A run triggered by a committed output runs in the same step
**Shall.** A run triggered by an output committed in an engine step shall run in that same step.
**Accept.** On `fan_out` `all_simulated` with `B` triggered by its input from `A`, every `B` control in the engine-run recording has the reception time of the `A` output that triggered it.
**Binds.** `stageOut`, `control`
**Verify.** T · `SYT-STP-02`   **Trace.** —

**`SYS-0034`** · `P0` · `R1` — After a jump no stage sees a sample from before it
**Shall.** After a jump, the engine shall hand no stage a sample that arrived before the jump.
**Accept.** On `running_example` `jump`, no re-run refSync entry after the jump names a sample logged before `jump_to_ms`; one such entry fails.
**Binds.** `stageIn`
**Verify.** T · `SYT-STP-03`   **Trace.** —

**`SYS-0035`** · `P1` · `R1` — A jump keeps the engine run
**Shall.** A jump shall keep the engine run, its step numbers continuing from the step before the jump.
**Accept.** On `running_example` `jump`, the step numbers are consecutive across the jump, from 0 to the last step; a restart at 0 or a gap fails.
**Binds.** `stepRecord`
**Verify.** T · `SYT-STP-04`   **Trace.** —

**`SYS-0036`** · `P1` · `R1` — A stage started mid-recording is badged warming up
**Shall.** The engine shall raise `KIND_WARMING_UP` on a stage as `D17 (4)` and `ARCH §6` define it, until its outputs first equal the recorded ones.
**Accept.** On `running_example` `jump`, each simulated stage carries the badge from the jump to the first step its outputs equal the recorded ones, and not after; on `cut_c` no stage carries it.
**Binds.** `stageOut`, `stepRecord`
**Verify.** T · `SYT-STP-05`   **Trace.** —

**`SYS-0037`** · `P1` · `R1` — Every event log entry has a listed kind and its step
**Shall.** The engine shall write each event log entry as one line carrying an entry kind from one closed list and the step number.
**Accept.** Over every lab case the engine runs, every event log line parses to a kind of that list with a step number; a line with another kind or no step fails.
**Binds.** `eventLog`
**Verify.** T · `SYT-STP-06`   **Trace.** —

**`SYS-0038`** · `P1` · `R1` — No time inside the engine is floating point
**Shall.** No time quantity inside the engine shall be held in a floating-point type.
**Accept.** `check_time_units.py` over `include/simcore`, `src/simcore` and `src/simengine` reports nothing; with one planted `double` time, it reports it.
**Binds.** `stepRecord`
**Verify.** A · `ANL-03`   **Trace.** —

## 5. Threads (`THR`)

What may run side by side and why the result does not change: `ARCH §8`.

**`SYS-0039`** · `P0` · `R1` — N threads give equal outputs to one
**Shall.** An engine run with `--threads N` shall give equal outputs to the same engine run with `--threads 1`, on every port of every step.
**Accept.** For every exact case and every N from 2 to its number of simulated stages, the two engine-run recordings are equal outputs and the event logs are identical; one difference fails.
**Binds.** `runRecording`, `eventLog`
**Verify.** T · `SYT-THR-01`   **Trace.** —

**`SYS-0040`** · `P1` · `R1` — One thread by default
**Shall.** Started without `--threads`, the engine shall call every component on one thread.
**Accept.** With the exec probe as every stage of `diamond` `all_simulated`, the probe's log shows one thread id over the whole engine run; two ids fail.
**Binds.** `stageIn`
**Verify.** T · `SYT-THR-02`   **Trace.** —

**`SYS-0041`** · `P0` · `R1` — Two stages of one library are never called at the same time
**Shall.** The engine shall never call two stages loaded from the same library path at the same time.
**Accept.** With one exec probe loaded as `B` and `C` of `fan_out` and `--threads 2`, no call enters while another is inside; with two probe copies at different paths, at least one overlap is logged.
**Binds.** `stageIn`
**Verify.** T · `SYT-THR-03`   **Trace.** —

## 6. Equal outputs and the first divergence (`EQO`)

Where equal outputs apply: `ARCH §7`. Determinism axes: `R-SIM-24`, with thread count added
(`ARCH §13`).

**`SYS-0042`** · `P0` · `R1` — Re-run outputs equal the fake car's
**Shall.** Re-running a lab case shall give, for every simulated stage, data outputs and `compState` equal to the recorded ones.
**Accept.** In every exact case the lab's comparator finds every simulated output not badged `KIND_WARMING_UP` equal to the recorded one; one difference fails, naming topology, case, stage and step.
**Binds.** `recording`, `stageOut`, `runRecording`
**Verify.** T · `SYT-EQO-01`   **Trace.** —

**`SYS-0043`** · `P1` · `R1` — The first divergence is reported
**Shall.** The engine shall report in the event log the first step, stage and port at which a simulated output of a RUN run is not equal to the recorded one.
**Accept.** On `no_ref_sync`, the reported divergence is the first step, stage and port at which the lab's comparator finds a difference; in every exact case without a jump, none is reported.
**Binds.** `eventLog`
**Verify.** T · `SYT-EQO-02`   **Trace.** —

**`SYS-0044`** · `P1` · `R1` — A re-run refSync is compared only on counter and time
**Shall.** The divergence comparison shall compare a re-run `refSync` with the recorded one only on each entry's `measurement_counter` and `source_timestamp_us`.
**Accept.** On `diamond` `all_simulated` with a jump to its middle, no divergence is reported; on `running_example` `cut_c` with one recorded entry's `source_timestamp_us` changed, it is reported on that `refSync`.
**Binds.** `eventLog`
**Verify.** T · `SYT-EQO-03`   **Trace.** —

**`SYS-0045`** · `P1` · `R1` — A divergence does not fail the engine run
**Shall.** A divergence shall not change the engine run's outcome.
**Accept.** `running_example` `no_ref_sync` runs every step and ends with the same exit code as `cut_c`; a fail outcome fails.
**Binds.** `exitStatus`
**Verify.** T · `SYT-EQO-04`   **Trace.** —

---

## 7. Verification strategy

Every `T` row runs on **lab cases** (`VANTAGE_Lab_Design.md` §6): the fake car's recording is the
known right answer, so a pass is equality, not tolerance. **Gate `G3`** (`VANTAGE_DEV_PLAN.md`
§5) is the test group of `VANTAGE_Test_Spec.md` §1. Every `A` row ships a planted-violation
case (`R-REQ-9`).

| Method | Count | Notes |
|---|---|---|
| T | 44 | `simengine` on a lab case, the step tap, or the exec probe |
| A | 3 | source checks over the engine |

## 8. Superseded and retired UIDs

None yet.

## 9. Open decisions

None in this part. Closed and handed on (owner, 2026-10-31):

| # | Question | Answer |
|---|---|---|
| 1 | The run setup's schema version string | `adas.sim.runspec/2.0` (`SYS-0004`) |
| 2 | How the engine finds a stage's bundle built for another configuration when the setup carries only `config_bundle_sha256` | part 8c (configuration) |
| 3 | Where the grace after the first divergence lives, and how data after it is flagged informational | part 8c (diagnostics) |
| 4 | Whether the first divergence names the first differing field | part 8c (the comparison of two runs) |
