# VANTAGE — the simulation tool
## System Requirements Specification — v0.1

**Owner:** Vantage program (vantage-dev, Plan C)
**Layer:** `SYS`, the top declared layer (`layers.yaml`), so every `Trace` is `—`.
**Status:** Draft for review. Not baselined. Parts 8a and 8b of `VANTAGE_DEV_PLAN.md` §6 step 8:
the orchestrator (`C1`), then the live measurement writer, the inspector and the supervisor
(`C2`). Part 8c, the launcher and its window, the scenario script, batch, configuration, diagnostics, delivery, determinism and the Python side, is §10 to §18.
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
first divergence · `LMW` the live measurement as the engine writes it · `INS` the inspector ·
`SUP` the supervisor · `LCH` the launcher · `WIN` the launcher window · `SCN` the scenario script · `BAT` batch · `CFG` configuration · `DIA` diagnostics · `DLV` delivery · `DET` determinism · `PYR` the Python side.
Priority split: 82 `P0`, 125 `P1`, 0 `P2`; all `R1`. Without a `P0` row an engine run is not
exact against the car; a `P1` row makes a result easier to trust or diagnose.


**What a Vantage result is evidence of.** A Vantage run on a lab case shows that the scheduler, the selection
and the comparison reproduce a known right answer; on a car recording it shows that the code under test, given
the samples the car gave it, produced these outputs and whether they equal the car's. It is evidence about the
code and the recording, not about the function: equal outputs on a lab case are not a validated function, and
Vantage reports a result and never judges whether it passed (`R-SIM-19`).

---

# PART A — FUNCTIONAL REQUIREMENTS

## 1. The run setup (`RUN`)

The keys and their meaning: `ARCH §2.3`, `§4`. One engine run reads one recording; many
recordings are a batch of engine runs (`R-SIM-19`).

**`SYS-0001`** · `P0` · `R1` — The run setup is the engine's only input
**Shall.** The engine shall take every choice of an engine run from the run setup, its recording, `--threads`, `--wait-for-attach`, `--plan-only`, `--supervise`, `--restart-on-crash` and `--attempt-timeout-ms` only.
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
**Shall.** The engine shall refuse at load a run setup carrying `delay_steps`, `grid_step_ns`, `order`, `impl.pattern`, `impl.search` or any key its schema does not name.
**Accept.** A lab setup with any one such key added ends with a load error naming the key and where it is (top level, stage, port or input), before the first step; a run that starts fails.
**Binds.** `runSetup`, `exitStatus`
**Verify.** T · `SYT-RUN-09`   **Trace.** —

**`SYS-0048`** · `P0` · `R1` — The launcher refuses a run configuration missing a run-setup value
**Shall.** The launcher shall write a run setup only from a run configuration that gives every `⊘` value of `ARCH §4` and each simulated stage's trigger, supplying no default.
**Accept.** With each such value removed in turn, `sim resim` exits with an error naming it and writes no run setup; with all given, the setup carries exactly the configured values.
**Binds.** `runSetup`
**Verify.** T · `SYT-RUN-10`   **Trace.** —

**`SYS-0052`** · `P1` · `R1` — An engine-run recording embeds each simulated stage's config bundle
**Shall.** An engine run shall write into its recording's `config_bundle` block (`RCT:SYS-0044`) the bundle folder each simulated stage was initialised with (`R-SIM-6`).
**Accept.** On `running_example` `cut_c` the block names exactly the simulated stages, holds each one's files with their text as on disk, and each stage's `bundle.sha256` equals the setup's `config_bundle_sha256` for it; anything else fails.
**Binds.** `runSetup`, `runRecording`
**Verify.** T · `SYT-RUN-11`   **Trace.** —

**`SYS-0055`** · `P1` · `R1` — The engine-run recording names the run, process, setup and libraries that made it
**Shall.** An engine run shall write in its recording's `manifest` its `run_id`, `host`, `process_nonce`, `run_spec_sha256` and each simulated stage's `library_sha256` (`R-SIM-6`, `D29 (1)`).
**Accept.** On `running_example` `cut_c` each `library_sha256` is the SHA-256 of the library loaded and `run_spec_sha256` the setup's `spec_sha256`; a second run's `manifest` differs only in `process_nonce`.
**Binds.** `runRecording`
**Verify.** T · `SYT-RUN-12`   **Trace.** —

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

**`SYS-0017`** · `P0` · `R1` — Decisions come from the run setup, the headers and the two messages that drive them
**Shall.** The orchestrator and input selection shall decide only from the run setup, `sig_header`s and the two contract messages that drive them: the recorded `refSync` (C3) for selection, the recorded control (C2) for RESTART.
**Accept.** Their source check finds no clock, thread-id or timer call and parses no type but `RefSync` and `CycleControl` besides `ReadSignalHeader`; a planted call or parse fails.
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

**`SYS-0050`** · `P1` · `R1` — A clock-started stage's controls are numbered from 1 and wrap to 1
**Shall.** The engine shall number the controls of a clock-started stage 1, 2, 3 … from its first tick, `0xFFFFFFFF` being followed by 1 and never 0 (`RCT:SYS-0004`, `D24`).
**Accept.** The control of tick k carries `measurement_counter` (k mod `0xFFFFFFFF`) + 1: ticks 0, 1, `0xFFFFFFFE` and `0xFFFFFFFF` carry 1, 2, `0xFFFFFFFF` and 1; a 0 or any other value fails.
**Binds.** `control`
**Verify.** T · `SYT-ORC-12`   **Trace.** —

**`SYS-0053`** · `P0` · `R1` — Every run's control and outputs are recorded
**Shall.** An engine run shall write every run's `control` and outputs to its recording, none dropped or overwritten (`R-SIM-6`).
**Accept.** In every exact case and in `running_example` `all_simulated` with `buffer_depth` 1 on every port, each simulated stage's `compState` messages in the engine-run recording carry consecutive `cycle_counter`s and equal its controls in number.
**Binds.** `control`, `stageOut`, `runRecording`
**Verify.** T · `SYT-ORC-04`   **Trace.** —

**`SYS-0057`** · `P1` · `R1` — Every run's overridden inputs are recorded
**Shall.** An engine run shall record each run's overridden inputs as that run was handed them, a stage run twice in one step leaving both (`R-SIM-15`, `D29 (4)`).
**Accept.** In `running_example` `all_simulated` with `buffer_depth` 1 on every port and an override on `source.Y`, `B`'s `in_Y` topic holds one message per `B` control, each with the counter its run's re-run refSync names.
**Binds.** `stageIn`, `runRecording`
**Verify.** T · `SYT-ORC-13`   **Trace.** —

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
**Accept.** With the first five `source.Y` samples removed from `running_example`'s `base` recording, every run whose recorded entry for `Y` names a removed sample has re-run entry 0 for `Y`; a non-zero entry fails.
**Binds.** `recording`, `stageIn`
**Verify.** T · `SYT-SEL-08`   **Trace.** —

**`SYS-0028`** · `P0` · `R1` — Selection outcomes raise the badges `ARCH §6` names
**Shall.** For each input selection outcome of `ARCH §6`, the engine shall raise `KIND_FALLBACK` and `KIND_READINESS_TIMEOUT` exactly as that table names them, on its subject.
**Accept.** On `missing_sample`, `missing_run`, `no_ref_sync`, `late_consumer` with limit 0 and every exact case, each step's badges equal those the table gives for that step's selections; a missing, extra or misplaced badge fails.
**Binds.** `stepRecord`
**Verify.** T · `SYT-SEL-09`   **Trace.** —

**`SYS-0029`** · `P1` · `R1` — Identity broken is badged on the port
**Shall.** The engine shall raise `KIND_IDENTITY_BROKEN` on a port whose samples break identity as `D17 (3)` defines it.
**Accept.** On `running_example` `base` with `source.X`'s `measurement_counter` lowered by 5 from its 100th sample on, its `cycle_counter` unchanged, the badge is raised once, on `source.X` and no other port; in every exact case it is never raised.
**Binds.** `recording`, `stepRecord`
**Verify.** T · `SYT-SEL-10`   **Trace.** —

**`SYS-0030`** · `P1` · `R1` — Counter gaps and resets are counted in the event log
**Shall.** The engine shall count in the event log every counter gap and every counter reset (`D17 (3)`) on each port.
**Accept.** On `counter_jump`, it counts one gap on `source.X` and no reset; with `source.X`'s counters restarted at 1 mid-recording, one reset and no identity broken; a wrong count fails.
**Binds.** `recording`, `eventLog`
**Verify.** T · `SYT-SEL-11`   **Trace.** —

**`SYS-0031`** · `P1` · `R1` — Counters are compared only by `counterDistance`; unknown is tested by one helper
**Shall.** The engine shall compare `measurement_counter` and `cycle_counter` values only through `counterDistance` (`RCT:SYS-0005`), and test a `measurement_counter` for unknown (0) only through `bus::IsUnknownMeasurementCounter`.
**Accept.** The source check over the engine finds no `==`, `!=`, `<`, `>`, `<=` or `>=` applied to either counter, a comparison with 0 included; with one planted comparison, it fails.
**Binds.** `stageIn`
**Verify.** A · `ANL-02`   **Trace.** —

**`SYS-0049`** · `P1` · `R1` — A measurement counter going from `0xFFFFFFFF` to 1 is consecutive
**Shall.** The engine shall read a `measurement_counter` going from `0xFFFFFFFF` to 1 as the next one, so it counts no gap, no reset and no identity broken there (`D24`).
**Accept.** On `running_example` `counter_wrap`, with `source.X`'s counter going `0xFFFFFFFF` then 1, the event log counts no gap and no reset on `source.X` and no `KIND_IDENTITY_BROKEN` is raised; any count or badge fails.
**Binds.** `recording`, `eventLog`, `stepRecord`
**Verify.** T · `SYT-SEL-12`   **Trace.** —

**`SYS-0051`** · `P1` · `R1` — A counter fallback's gap counts `0xFFFFFFFF` → 1 as one step
**Shall.** The engine shall count the counter fallback's gap by `SYS-0049`'s distance, `0xFFFFFFFF` → 1 being one step (`D24`).
**Accept.** On `running_example` `counter_wrap` with `source.X`'s `0xFFFFFFFF`, 1 and 2 removed, a run wanting 1 or 2 falls back to `0xFFFFFFFE` at gap 2 or 3: logged beyond `fallback_max_gap` 1, not logged within 3; a gap one larger fails.
**Binds.** `recording`, `stageIn`, `eventLog`
**Verify.** T · `SYT-SEL-13`   **Trace.** —

## 4. The engine step (`STP`)

What one step is, the jump and warming up: `ARCH §7`. The word "tick" is retired; the step
number takes its place.

**`SYS-0032`** · `P0` · `R1` — One engine step per instant a step-starting message arrives or a clock ticks
**Shall.** The engine shall make one step per instant at which a step-starting message (`ARCH §7`) arrives or a clock ticks, numbered from 0 without a gap.
**Accept.** On `running_example` `cut_c`, the steps are its step-starting messages' distinct reception times, numbered from 0 without a gap; with `E` on a 7 ms clock instead, each tick instant adds its step.
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

**`SYS-0054`** · `P1` · `R1` — A lost input's divergence comes no earlier than the run that lost it
**Shall.** The engine shall report no divergence before the first run that lost an input the recording lacks.
**Accept.** On `missing_sample` and `missing_run` the first divergence is reported at or after the first run whose recorded refSync names a dropped sample, and that run carries `KIND_FALLBACK` on that input.
**Binds.** `eventLog`, `stepRecord`
**Verify.** T · `SYT-EQO-05`   **Trace.** —

**`SYS-0056`** · `P1` · `R1` — The engine-run recording states its first divergence
**Shall.** An engine run shall write in its recording's `manifest` a `divergence`: the first divergence's step, stage and port; `none` when outputs were compared and none diverged; else `unknown`.
**Accept.** On `no_ref_sync` it names the event log's `first_divergence` entry; on `cut_c` it is `none`; on `cut_c` with the simulated stages' outputs removed from the recording, `unknown`.
**Binds.** `runRecording`, `eventLog`
**Verify.** T · `SYT-EQO-06`   **Trace.** —

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

**`SYS-0202`** · `P1` · `R1` — The first divergence names the first differing field
**Shall.** The engine's `first_divergence` entry shall also name the first field, in the message definition's order, in which the recorded and the re-run message differ.
**Accept.** On `no_ref_sync` the entry names the field a field-by-field comparison of the two decoded messages finds first; its step, stage and port are unchanged.
**Binds.** `eventLog`
**Verify.** T · `SYT-EQO-07`   **Trace.** —

## 7. The live measurement as the engine writes it (`LMW`)

What the live measurement is, and what its writer and readers do: `RCT:SYS-0023` to
`RCT:SYS-0031` and `RCT:SYS-0036`, obeyed as written. What the engine hands the writer, and when
it writes at all: `ARCH §10.1`, `§9`. The inspector is attached for the whole engine run in
every `Accept` below.

**`SYS-0058`** · `P0` · `R1` — An engine run creates the live measurement its setup names
**Shall.** With `outputs.livemeas` in the run setup, the engine shall create the live measurement of that name and geometry before step 0; without the key, none.
**Accept.** On `running_example` `cut_c`, the inspector reads the setup's name and geometry and a cycle for step 0; with the key removed, no live measurement of that name appears.
**Binds.** `runSetup`, `liveMeas`
**Verify.** T · `SYT-LMW-01`   **Trace.** —

**`SYS-0059`** · `P0` · `R1` — The description is built from the run setup and the loaded components
**Shall.** The engine shall build the `MeasDescription` from the run setup, the loaded manifests and the recording's topic index as `ARCH §4` maps it.
**Accept.** On every lab case, each stage, port, `bulk` flag, trigger, clock, previous-cycle input, override, bundle hash and the readiness limit in the description equals the setup's; one difference fails.
**Binds.** `runSetup`, `liveMeas`
**Verify.** T · `SYT-LMW-02`   **Trace.** —

**`SYS-0060`** · `P1` · `R1` — A stage that is not loaded has an empty build id
**Shall.** The description shall give an empty `build_id` to every stage whose library the engine did not load (`R-SIM-25`).
**Accept.** On `running_example` `cut_c`, `C`, `measured`, has an empty `build_id` and every simulated stage's equals its loaded manifest's; any other value for `C` fails.
**Binds.** `liveMeas`
**Verify.** T · `SYT-LMW-02`   **Trace.** —

**`SYS-0061`** · `P0` · `R1` — The descriptor set holds every schema the recording and the manifests name
**Shall.** The description's `descriptor_set` shall be the union of every loaded manifest's descriptor set and the recording's topic schemas.
**Accept.** On `running_example` `cut_c`, the inspector decodes `C`'s recorded output, whose library is not loaded, and every simulated stage's port; one undecodable port fails.
**Binds.** `liveMeas`
**Verify.** T · `SYT-LMW-03`   **Trace.** —

**`SYS-0062`** · `P0` · `R1` — Each step holds every declared port's held value and its age
**Shall.** Each `MeasCycle` shall hold, for every declared port that has had a sample, the newest sample with `age_ns`: simulation time since that sample was written.
**Accept.** On `running_example` `all_simulated`, each port's value in step k is the newest the engine holds at k and `age_ns` is k's time minus its arrival time; a port with no sample yet is absent.
**Binds.** `stepRecord`, `liveMeas`
**Verify.** T · `SYT-LMW-04`   **Trace.** —

**`SYS-0063`** · `P0` · `R1` — Each value carries its origin
**Shall.** Each port value shall carry its origin: the recording's tag for a recorded port, `simulated` for a simulated stage's output, `overridden` for an overridden input.
**Accept.** On `running_example` `cut_c` with one override on `source.Y`, every value of `C` and of the sources carries the recording's tag, every other stage's output `simulated`, and `B`'s `in_Y` `overridden`.
**Binds.** `stepRecord`, `liveMeas`
**Verify.** T · `SYT-LMW-05`   **Trace.** —

**`SYS-0064`** · `P0` · `R1` — Every badge with a count is in the step that raised it
**Shall.** Each `MeasCycle` shall hold every badge whose count is above 0, with its count since the engine run started.
**Accept.** On `missing_sample` `all_simulated`, `KIND_FALLBACK` and its count appear from the first step that raised it and equal the step tap's badges at every step; a missing or differing badge fails.
**Binds.** `stepRecord`, `liveMeas`
**Verify.** T · `SYT-LMW-06`   **Trace.** —

**`SYS-0065`** · `P0` · `R1` — A stage run twice in one step hands the writer both runs' values (`D30`)
**Shall.** For a stage run twice in one step, the engine shall hand the writer two values on each of its `control`, `refSync`, output and overridden-input ports, in run order (`D30`).
**Accept.** On `F-LM-TWICE`, each step with two `B` runs hands the writer two values on each such `B` port, each with its run's counter, in run order; one value fails.
**Binds.** `stepRecord`, `liveMeas`
**Verify.** T · `SYT-LMW-07`   **Trace.** —

**`SYS-0066`** · `P1` · `R1` — Only a port the setup flags `bulk` goes to `MeasBulk`
**Shall.** The engine shall send the values of a port to `MeasBulk` when its `bulk` flag is set in the run setup, and of no other port.
**Accept.** On the `camera` topology with `bulk: [source.Cam]`, the description flags exactly `source.Cam` and every image resolves in `MeasBulk`; with `bulk` empty, no `MeasBulk` frame is written.
**Binds.** `runSetup`, `liveMeas`
**Verify.** T · `SYT-LMW-08`   **Trace.** —

**`SYS-0067`** · `P1` · `R1` — The live measurement is written by the worker
**Shall.** The live measurement shall be written only by the worker, the process that holds the runner and the components.
**Accept.** On a supervised `running_example` `cut_c`, the `writerPid` the inspector reads equals the worker's process id and differs from the supervisor's.
**Binds.** `liveMeas`
**Verify.** T · `SYT-LMW-09`   **Trace.** —

**`SYS-0068`** · `P0` · `R1` — An open that fails or meets a live writer gives a warning and the run goes on
**Shall.** When the live measurement cannot be opened, or its name is held by a live writer, the engine shall print one warning and run to its end without one.
**Accept.** A second engine started on a name a first still writes prints one warning naming name and cause, and gives equal outputs to a run with no `outputs.livemeas`.
**Binds.** `liveMeas`, `eventLog`, `runRecording`
**Verify.** T · `SYT-LMW-10`   **Trace.** —

**`SYS-0069`** · `P1` · `R1` — A dead writer's name is replaced by the next open
**Shall.** The engine shall replace a live measurement of its name whose writer is dead, and give the new engine run a new run id.
**Accept.** After a worker killed mid-run, an engine started on the same name opens it, the inspector reads a run id different from the killed one's and a cycle for step 0.
**Binds.** `liveMeas`
**Verify.** T · `SYT-LMW-11`   **Trace.** —

**`SYS-0070`** · `P0` · `R1` — The worker writes the outcome of an engine run that ends itself
**Shall.** The worker shall close the live measurement with `pass` at the end of the recording or slice, `fail` on its own error, and `timeout` when a call exceeds `limits.exec_timeout_ms` (`ARCH §9`).
**Accept.** On `running_example` `cut_c`, on it with `held_probe` failing its third call, and on `hang` with `limits.exec_timeout_ms` set, the inspector reads status finished with `pass`, `fail` and `timeout`.
**Binds.** `liveMeas`, `exitStatus`
**Verify.** T · `SYT-LMW-12`   **Trace.** —

**`SYS-0071`** · `P1` · `R1` — A jump keeps the live measurement and its run id
**Shall.** A jump shall keep the live measurement open under one run id, its step numbers continuing.
**Accept.** On `running_example` `jump`, the run id the inspector reads is the same before and after the jump and the cycle step numbers are consecutive across it; a new run id or a restart at 0 fails.
**Binds.** `liveMeas`, `stepRecord`
**Verify.** T · `SYT-LMW-13`   **Trace.** —

**`SYS-0072`** · `P1` · `R1` — The step tap and the writer get the same step
**Shall.** The engine shall hand the step tap and the live measurement writer the same step report.
**Accept.** On `running_example` `cut_c`, the step tap's step number, time and badges equal those of the cycle the inspector reads, at every step; one difference fails.
**Binds.** `stepRecord`, `liveMeas`
**Verify.** T · `SYT-LMW-14`   **Trace.** —

**`SYS-0073`** · `P0` · `R1` — Writing the live measurement changes no output
**Shall.** An engine run with `outputs.livemeas` shall give equal outputs to the same engine run without it.
**Accept.** For every exact case, the two engine-run recordings are equal outputs on every port, and their event logs are identical; one difference fails.
**Binds.** `runRecording`, `eventLog`, `liveMeas`
**Verify.** T · `SYT-LMW-15`   **Trace.** —

**`SYS-0074`** · `P1` · `R1` — The live measurement writer is the only carrier of step values out of the engine
**Shall.** The engine's source shall hold one carrier of step values out of the process: the live measurement writer's calls.
**Accept.** `check_single_carrier.py` over `src/simcore` and `src/simengine` reports no use of the player transport publisher; with one planted `SetTransportPublisher` call, it reports it.
**Binds.** `stepRecord`
**Verify.** A · `ANL-04`   **Trace.** —

**`SYS-0105`** · `P1` · `R1` — A reader that ends abnormally changes nothing for the engine run or a later reader
**Shall.** A reader killed while it copies a cycle shall leave the engine run's steps, outputs and live measurement unchanged for every other reader.
**Accept.** On `running_example` `cut_c`, with one reader killed mid-copy, the run writes every step with outputs equal to a run with no reader, and a reader attached afterwards reads every cycle.
**Binds.** `liveMeas`, `runRecording`
**Verify.** T · `SYT-LMW-16`   **Trace.** —

## 8. The inspector (`INS`)

The three verbs and what each reads: `ARCH §10.3`. The inspector reads and never writes
(`RCT:SYS-0027`); a layout mismatch is `RCT:SYS-0030`'s, on this reader `SYT-LMS-08`.

**`SYS-0075`** · `P1` · `R1` — `attach` prints the live measurement's identity and state
**Shall.** `vantage-inspect attach` shall print the status, run id, heartbeat, outcome and geometry of a live measurement and read no cycle.
**Accept.** On a running lab case, the printed run id, geometry and status equal the setup's and the writer's; a second attach after the run finished prints `finished` and the outcome.
**Binds.** `inspectorReport`, `liveMeas`
**Verify.** T · `SYT-INS-01`   **Trace.** —

**`SYS-0076`** · `P0` · `R1` — A writer that stopped is reported as gone
**Shall.** `attach` shall state "writer gone at step N" when the heartbeat has stopped, the status is running and the writer's process no longer exists.
**Accept.** After a worker started directly is killed at step N, `attach` states "writer gone at step N" with N the last step the heartbeat counted; no such line while the worker lives.
**Binds.** `inspectorReport`
**Verify.** T · `SYT-INS-02`   **Trace.** —

**`SYS-0077`** · `P0` · `R1` — `dump` prints one line per port value, decoded from the description
**Shall.** `dump` shall print one line per port value of every cycle, decoded with dynamic messages built from the description's `descriptor_set`.
**Accept.** On `running_example` `cut_c`, the lines are in step order and each port's decoded fields equal the recording's decoded message of that step; a value not decoded fails.
**Binds.** `inspectorReport`, `liveMeas`
**Verify.** T · `SYT-INS-03`   **Trace.** —

**`SYS-0078`** · `P1` · `R1` — The inspector needs no bindings, checkout or component library
**Shall.** The inspector shall run with no generated protobuf bindings, no source checkout and no component library present (`R-SIM-11`).
**Accept.** Run from an empty directory with every search-path variable cleared and the lab's libraries and `interfaces` build absent, `attach`, `dump` and `check` give the same output as with them present.
**Binds.** `inspectorReport`
**Verify.** T · `SYT-INS-04`   **Trace.** —

**`SYS-0079`** · `P1` · `R1` — `dump --follow` reports the steps it skipped
**Shall.** `dump --follow` shall keep its own read position and print "N steps skipped" when the writer has overwritten steps it had not read.
**Accept.** With a 2-slot ring and the reader paused over M steps, the next line is "N steps skipped" with N the number of steps overwritten; with a ring holding the run, no such line.
**Binds.** `inspectorReport`
**Verify.** T · `SYT-INS-05`   **Trace.** —

**`SYS-0080`** · `P0` · `R1` — `check` finds a value or an omission for every declared port at every step
**Shall.** `check` shall report, for every port the description declares and every step after that port's first value, a missing value not marked omitted, enumerating ports from the description only.
**Accept.** On a flawed live measurement with one declared port left out of one step, `check` names that step and port; on every lab topology's run it reports none.
**Binds.** `inspectorReport`, `liveMeas`
**Verify.** T · `SYT-INS-06`   **Trace.** —

**`SYS-0081`** · `P0` · `R1` — `check` finds a step number that is not consecutive
**Shall.** `check` shall report a step whose number is not the previous step's plus one, naming both numbers.
**Accept.** On a flawed live measurement with step 7 left out, `check` names 6 and 8; on every lab topology's engine run it reports none.
**Binds.** `inspectorReport`
**Verify.** T · `SYT-INS-07`   **Trace.** —

**`SYS-0082`** · `P0` · `R1` — `check` finds a run without its `control`, `refSync` or `compState`
**Shall.** `check` shall report each run of a simulated stage that lacks its `control`, `refSync` or `compState` value, naming stage, step and port.
**Accept.** On a flawed live measurement with one `B` `refSync` removed, `check` names `B`, its step and `refSync`; on every lab topology's engine run it reports none.
**Binds.** `inspectorReport`
**Verify.** T · `SYT-INS-08`   **Trace.** —

**`SYS-0083`** · `P0` · `R1` — `check` finds a measured value that is not the recording's
**Shall.** With `--recording`, `check` shall report each value of a measured port that does not equal the recording's value of its step on `measurement_counter` and payload bytes, naming step and port.
**Accept.** On a flawed live measurement with one payload byte changed, `check` names that step and port; on every exact case against its recording it reports none.
**Binds.** `inspectorReport`, `recording`
**Verify.** T · `SYT-INS-09`   **Trace.** —

**`SYS-0084`** · `P1` · `R1` — `check` finds a badge count that decreases
**Shall.** `check` shall report a badge whose count is lower than in an earlier step, naming badge, subject and both steps.
**Accept.** On a flawed live measurement with one `KIND_FALLBACK` count lowered by 1, `check` names that badge and its two steps; on every lab topology's engine run it reports none.
**Binds.** `inspectorReport`
**Verify.** T · `SYT-INS-10`   **Trace.** —

**`SYS-0085`** · `P0` · `R1` — `check` names every finding and exits 1 on any
**Shall.** `check` shall print each finding on one line and exit 1 when it found any, 0 when it found none.
**Accept.** On the flawed live measurements of `SYS-0080` to `SYS-0084`, the exit code is 1 and the findings printed equal those planted in number; on a clean lab run it is 0 with no finding line.
**Binds.** `inspectorReport`, `exitStatus`
**Verify.** T · `SYT-INS-11`   **Trace.** —

**`SYS-0086`** · `P1` · `R1` — Every other end of the inspector has its own documented exit code
**Shall.** The inspector shall exit 2 on a usage error and 6 when it cannot attach, each with a message naming the cause, and never with a platform code.
**Accept.** `vantage-inspect` with an unknown verb exits 2; `attach` on a name no writer holds, and on a layout version it does not read, exits 6 naming the name or both versions.
**Binds.** `inspectorReport`, `exitStatus`
**Verify.** T · `SYT-INS-12`   **Trace.** —

**`SYS-0087`** · `P1` · `R1` — `check` holds no stage or port name of its own
**Shall.** The inspector's `check` shall hold no stage name and no port name, so it finds an item that a topology adds without a source change.
**Accept.** `check_inspector_items.py` over `src/inspector` reports no stage or port name literal; with a planted `"B.refSync"` string in `check.cpp`, it reports file and line.
**Binds.** `inspectorReport`
**Verify.** A · `ANL-05`   **Trace.** —

## 9. The supervisor (`SUP`)

What the supervisor does and never does, the faces and the seal: `ARCH §3.7`, `§9`. The outcomes
are the four of `R-SIM-19` and a fifth, *failed to start*; the exit codes are `SimExitCode` of
`include/simcore/abi/simcore.h`.

**`SYS-0088`** · `P0` · `R1` — `--supervise` starts one worker and the worker supervises nothing
**Shall.** Started with `--supervise`, `simengine` shall start exactly one worker, itself with the worker flag, and wait for it; a worker shall start no process.
**Accept.** On `running_example` `cut_c`, the process tree under a `--supervise` start holds one child and no grandchild; started without the flag, no child.
**Binds.** `runSetup`, `exitStatus`
**Verify.** T · `SYT-SUP-01`   **Trace.** —

**`SYS-0089`** · `P0` · `R1` — A worker still running at the deadline is killed and the outcome is timeout
**Shall.** The supervisor shall kill a worker still running when `--attempt-timeout-ms` has passed and end with outcome `timeout`.
**Accept.** On `running_example` `hang` with a deadline shorter than the hang, the worker no longer exists after the deadline and the exit code is `7`; with a longer deadline and a case that passes, `0`.
**Binds.** `exitStatus`, `attemptManifest`
**Verify.** T · `SYT-SUP-02`   **Trace.** —

**`SYS-0090`** · `P1` · `R1` — A supervised start with no deadline is refused
**Shall.** The supervisor shall refuse to start a worker without `--attempt-timeout-ms`, as the deadline has no default (`⊘`).
**Accept.** `--supervise` without the option exits 2 naming `--attempt-timeout-ms`, starts no worker and writes no live measurement; with the option, it starts one.
**Binds.** `exitStatus`
**Verify.** T · `SYT-SUP-02`   **Trace.** —

**`SYS-0091`** · `P0` · `R1` — Pass, fail, crash, timeout and failed-to-start end differently
**Shall.** The supervisor shall end with one exit code per outcome: 0 pass, the worker's own code on fail, 8 crash, 7 timeout, 6 failed to start.
**Accept.** A passing case gives 0, a setup refused at load gives its own non-zero code, `crash` 8, `hang` 7, a missing worker binary 6; any two outcomes sharing a code fail.
**Binds.** `exitStatus`
**Verify.** T · `SYT-SUP-03`   **Trace.** —

**`SYS-0092`** · `P1` · `R1` — Every exit code of `simengine` is one of the closed set
**Shall.** `simengine` shall exit only with a `SimExitCode` value, never a raw platform code.
**Accept.** A worker ended by `abort()` and one ended by a kill signal both give `8`; neither gives the platform's raw status, and the code is in `{0, 2` to `8}`.
**Binds.** `exitStatus`
**Verify.** T · `SYT-SUP-04`   **Trace.** —

**`SYS-0093`** · `P0` · `R1` — A clean failure is never retried into a pass
**Shall.** The supervisor shall never start a second worker after a worker's clean non-zero exit.
**Accept.** A setup refused at load under `--supervise --restart-on-crash 2` ends with one attempt and the worker's own exit code; two attempts or code 0 fails.
**Binds.** `exitStatus`, `attemptManifest`
**Verify.** T · `SYT-SUP-05`   **Trace.** —

**`SYS-0094`** · `P1` · `R1` — A crash is restarted at most N times, and by default never
**Shall.** The supervisor shall start a new worker after a crash at most `--restart-on-crash N` times, and none when the option is absent.
**Accept.** `running_example` `crash` under `--restart-on-crash 2` makes three attempts and ends `8`; without the option, one attempt; with `hang`, one attempt.
**Binds.** `exitStatus`, `attemptManifest`
**Verify.** T · `SYT-SUP-06`   **Trace.** —

**`SYS-0095`** · `P0` · `R1` — The supervisor seals the live measurement once the worker is confirmed dead
**Shall.** Once the worker has ended and its `writerPid` is confirmed gone, the supervisor shall call `sealAbandoned` once with `crash` or `timeout`.
**Accept.** After `crash` and after `hang` under supervision, the inspector reads status finished and outcome `crash` and `timeout`; a seal call before the worker's end, or none, fails.
**Binds.** `liveMeas`, `exitStatus`
**Verify.** T · `SYT-SUP-07`   **Trace.** —

**`SYS-0096`** · `P0` · `R1` — The seal writes the outcome and the status and nothing else
**Shall.** `sealAbandoned` shall write `outcome` and then `status`, and no other byte of either segment (`D18 (3)`).
**Accept.** On a supervised lab run whose worker is killed while held, the two segments copied before the kill and after the seal differ only in `outcome` and `status`; any other byte changed fails.
**Binds.** `liveMeas`
**Verify.** T · `SYT-SUP-08`   **Trace.** —

**`SYS-0097`** · `P0` · `R1` — A live worker's or a self-closed live measurement is never sealed
**Shall.** The supervisor shall not seal a live measurement while its writer lives, nor one the worker closed.
**Accept.** On a case that passes under supervision, the outcome stays `pass`, and the segments are unchanged by the supervisor; on `crash`, status is not finished before the worker's end.
**Binds.** `liveMeas`
**Verify.** T · `SYT-SUP-09`   **Trace.** —

**`SYS-0098`** · `P1` · `R1` — A worker with no live measurement leaves nothing to seal
**Shall.** When the worker has opened no live measurement, the supervisor shall create none and report the outcome by exit code only.
**Accept.** `crash` on a setup without `outputs.livemeas` ends `8`, with no live measurement of any name created by the supervisor.
**Binds.** `liveMeas`, `exitStatus`
**Verify.** T · `SYT-SUP-10`   **Trace.** —

**`SYS-0099`** · `P0` · `R1` — Every attempt is written to the attempt manifest
**Shall.** The supervisor shall write one record per attempt to the attempt manifest: the attempt number, the outcome, the exit code or signal and whether it was the last.
**Accept.** After `crash` under `--restart-on-crash 1`, the manifest holds two records, numbered 1 and 2, outcome `crash` in both, the second marked last; a missing or mislabelled record fails.
**Binds.** `attemptManifest`
**Verify.** T · `SYT-SUP-11`   **Trace.** —

**`SYS-0100`** · `P1` · `R1` — The attempt manifest names the stages a crashed worker was running
**Shall.** The record of a crash or timeout shall name each stage whose call was in progress, or `unknown` when none was.
**Accept.** For `crash` and `hang`, the record names `B` and no other stage; for a worker aborted before any call began, it reads `unknown`, never a stage.
**Binds.** `attemptManifest`
**Verify.** T · `SYT-SUP-12`   **Trace.** —

**`SYS-0101`** · `P0` · `R1` — A crash writes a reproducer and a clean end does not
**Shall.** After a crash the supervisor shall write a reproducer package holding the run setup, the worker's standard error, the last completed step, the run id and the crashed stage.
**Accept.** After `crash`, the package's setup equals the run's, its last step equals the highest step the inspector read, and it names `B`; after `hang` or a pass, none is written.
**Binds.** `reproducer`, `attemptManifest`
**Verify.** T · `SYT-SUP-13`   **Trace.** —

**`SYS-0102`** · `P1` · `R1` — A crash in an isolated stage leaves the asking engine alive
**Shall.** An isolated stage shall run in a second engine process whose crash, timeout or failure the asking engine classifies as the supervisor does and survives.
**Accept.** A test asker that hosts `B` of `crash` through `RunIsolatedStage` gets outcome `crash` and exit code `8` naming `B`, and is still running when `B`'s process has ended.
**Binds.** `stageIn`, `exitStatus`
**Verify.** T · `SYT-SUP-14`   **Trace.** —

**`SYS-0103`** · `P0` · `R1` — Supervision changes no output
**Shall.** An engine run started with `--supervise` shall give equal outputs to the same run started directly.
**Accept.** For every exact case, the two engine-run recordings are equal outputs on every port and their event logs are identical; one difference fails.
**Binds.** `runRecording`, `eventLog`
**Verify.** T · `SYT-SUP-15`   **Trace.** —

**`SYS-0104`** · `P0` · `R1` — The supervisor runs no component and writes nothing but the seal
**Shall.** The supervisor's code shall call no component and no `liveMeas` call but `sealAbandoned`, and shall write no step.
**Accept.** `check_supervisor_boundary.py` over the supervisor's files reports no call of `Component::Exec`, `RunStage`, `liveMeasStep` or `liveMeasClose`; with one planted `liveMeasStep`, it reports it.
**Binds.** `liveMeas`
**Verify.** A · `ANL-06`   **Trace.** —

---

## 10. The launcher (`LCH`)

What the launcher is and never does: `ARCH §3.1`. The run setup it writes is read by the engine alone (`SYS-0001`); the keys it fills are `ARCH §2.3`.

**`SYS-0106`** · `P0` · `R1` — The launcher writes the run setup and keeps no state outside it
**Shall.** The launcher shall keep every choice only in the run setup it writes.
**Accept.** A lab selection written, read back with `Selection.from_spec` and written again gives a byte-identical run setup; one differing byte fails.
**Binds.** `launcherChoice`, `runSetup`
**Verify.** T · `SYT-LCH-01`   **Trace.** —

**`SYS-0107`** · `P0` · `R1` — An engine run starts only from a run setup file just written
**Shall.** Each launcher function that starts an engine run shall write the run setup it starts from, in the same call, before the start.
**Accept.** `check_one_engine_start.py` finds a write of the setup before every start; with a planted start from a `Selection` argument it reports file and line.
**Binds.** `commandLine`, `runSetup`
**Verify.** A · `ANL-07`   **Trace.** —

**`SYS-0108`** · `P0` · `R1` — One place starts `simengine`
**Shall.** `src/adas_sim/engine/bridge.py::run_engine` shall be the only code in `src/adas_sim` that starts `simengine`.
**Accept.** `check_one_engine_start.py` finds no other process start naming the engine executable; with a planted second one in `cli/` it reports file and line.
**Binds.** `commandLine`
**Verify.** A · `ANL-07`   **Trace.** —

**`SYS-0109`** · `P0` · `R1` — A supervised start with no deadline is refused before any process starts
**Shall.** `run_engine` shall refuse a supervised start whose caller gave no deadline, naming it, and start no process (`SYS-0090`).
**Accept.** With supervision and no deadline it raises an error naming `attempt_timeout_ms` and no `simengine` process exists; with one, the command line holds `--attempt-timeout-ms` equal to it.
**Binds.** `commandLine`, `exitStatus`
**Verify.** T · `SYT-LCH-02`   **Trace.** —

**`SYS-0110`** · `P1` · `R1` — The developer face starts the engine directly, the batch face under `--supervise`
**Shall.** The launcher shall start `simengine` with the setup path and `--threads` or `--wait-for-attach` when asked, and add `--supervise` and the deadline only for the batch face.
**Accept.** On a lab case the two command lines differ exactly so, and the two runs give equal outputs on every port.
**Binds.** `commandLine`
**Verify.** T · `SYT-LCH-02`   **Trace.** —

**`SYS-0111`** · `P1` · `R1` — The exit code's meaning is printed from the closed set
**Shall.** The launcher shall print the name and one line of meaning of an engine run's exit code from the set of `SYS-0092`.
**Accept.** Each of the eight codes prints its name and meaning; a code outside the set prints as unknown and never as a name.
**Binds.** `exitStatus`
**Verify.** T · `SYT-LCH-03`   **Trace.** —

**`SYS-0112`** · `P0` · `R1` — The feasible cuts of a recording are reported from its index alone
**Shall.** The launcher shall report from a recording's topic index, opening no payload, which stages can be `measured` and which hold a `control` and a `refSync`.
**Accept.** For each exact lab case the report names every stage's three answers; a copy of the recording with every payload zeroed gives the same report.
**Binds.** `recording`, `launcherChoice`
**Verify.** T · `SYT-LCH-04`   **Trace.** —

**`SYS-0113`** · `P0` · `R1` — `measured` is refused for a stage whose outputs the recording lacks
**Shall.** The launcher shall refuse to set a stage `measured` when the recording lacks its outputs, naming the stage and the ports, and write no setup.
**Accept.** On `running_example` `cut_c` with `C`'s output topic removed, selecting `C` `measured` ends with an error naming `C` and that port and no file; with the topic present it is accepted.
**Binds.** `launcherChoice`, `recording`, `runSetup`
**Verify.** T · `SYT-LCH-04`   **Trace.** —

**`SYS-0114`** · `P1` · `R1` — A trigger is offered only as the recording and the stage allow
**Shall.** The launcher shall offer `control` as a stage's trigger only when the recording holds that stage's `control` topic, and an input only when the stage declares it.
**Accept.** On `data_triggered` the offer for `T` is `in_X`, `in_Y` and, with `T`'s control topic in the recording, `control`; with that topic removed, `control` is not offered.
**Binds.** `launcherChoice`, `recording`
**Verify.** T · `SYT-LCH-05`   **Trace.** —

**`SYS-0115`** · `P0` · `R1` — A broken chain is blocked
**Shall.** The launcher shall refuse a selection with a `measured` stage between two `simulate` stages on one data path, naming the path, the landing stage and the remedies.
**Accept.** On `measured_middle` with `A` and `B` `simulate` and `M` `measured` the error names the path and a remedy; with `M` `simulate` it passes; any setup written for the blocked selection fails.
**Binds.** `launcherChoice`, `runSetup`
**Verify.** T · `SYT-LCH-07`   **Trace.** —

**`SYS-0116`** · `P1` · `R1` — A waiver needs a flag and a written reason and marks the setup
**Shall.** The launcher shall accept a broken chain only with a waiver flag and a written reason, and shall write both into the setup's `coherence_verdict`.
**Accept.** Waiver and reason: the setup's verdict names the waiver and the reason; either missing, or a policy that forbids waivers: refused and no file.
**Binds.** `launcherChoice`, `runSetup`
**Verify.** T · `SYT-LCH-07`   **Trace.** —

**`SYS-0117`** · `P1` · `R1` — An orphan simulation warns once
**Shall.** The launcher shall warn once, naming the stage, when a `simulate` stage's outputs are read by no simulated stage.
**Accept.** A selection with an orphan prints one warning naming it however often it is validated; one without prints none.
**Binds.** `launcherChoice`
**Verify.** T · `SYT-LCH-07`   **Trace.** —

**`SYS-0118`** · `P1` · `R1` — A change of the selection returns a new selection
**Shall.** Every change of a selection (`set_mode`, `set_impl`, `isolate`, `add_recording`) shall return a new selection and leave the one it was given unchanged.
**Accept.** After each change the original written as a setup is byte-identical to before; a mutated original fails.
**Binds.** `launcherChoice`
**Verify.** T · `SYT-LCH-01`   **Trace.** —

**`SYS-0119`** · `P0` · `R1` — Each library is resolved to one absolute path before the setup is written
**Shall.** The launcher shall resolve each simulated stage's implementation to the absolute path of one library file for the running platform and write it as `impl.path`.
**Accept.** Every written lab setup holds absolute `impl.path` values naming existing files; a stage with no library ends the launcher naming the stage and the stem searched, before a file is written.
**Binds.** `launcherChoice`, `runSetup`
**Verify.** T · `SYT-LCH-06`   **Trace.** —

**`SYS-0120`** · `P1` · `R1` — Whether a library exists for the platform is told without loading it
**Shall.** The launcher shall tell for each stage whether a library exists for the running platform without loading it.
**Accept.** A file of garbage bytes with a library's name is reported as present and no library load is made; a missing file is reported absent with the reason.
**Binds.** `launcherChoice`
**Verify.** T · `SYT-LCH-06`   **Trace.** —

**`SYS-0121`** · `P1` · `R1` — The dry run prints the resolved setup with each value's layer
**Shall.** The launcher's dry run shall print the resolved run setup with the configuration layer of each value, call no component and start no engine run.
**Accept.** On a lab configuration it prints every setup key with its layer and no engine run starts; a key printed without a layer fails.
**Binds.** `launcherChoice`, `runSetup`
**Verify.** T · `SYT-LCH-08`   **Trace.** —

**`SYS-0193`** · `P1` · `R1` — The setup names each source file by its content hash
**Shall.** The launcher shall write each `sources[]` entry's `sha256` as the SHA-256 of that file's bytes.
**Accept.** For each lab case the setup's `sha256` equals the file's computed hash; a recording edited after the setup was written no longer matches it.
**Binds.** `launcherChoice`, `runSetup`, `recording`
**Verify.** T · `SYT-LCH-06`   **Trace.** —

**`SYS-0197`** · `P1` · `R1` — The run setup does not depend on the order of the choices
**Shall.** The launcher shall write the same run setup for the same final choices, whatever order they were made in.
**Accept.** Two lab selections reaching one state by different orders of `set_mode`, `set_impl` and `add_recording` write byte-identical setups.
**Binds.** `launcherChoice`, `runSetup`
**Verify.** T · `SYT-LCH-01`   **Trace.** —

**`SYS-0198`** · `P1` · `R1` — `spec_sha256` is the hash of the setup's content
**Shall.** The launcher shall write `spec_sha256` as the hash of the setup's content, unchanged by writing it again and changed by any one field.
**Accept.** Writing a lab setup twice gives one `spec_sha256`; changing any one field of it, in turn, gives another each time.
**Binds.** `runSetup`
**Verify.** T · `SYT-LCH-01`   **Trace.** —

**`SYS-0205`** · `P1` · `R1` — The dry run also prints the engine's plan
**Shall.** The launcher's dry run shall print, after the resolved setup, the plan `simengine --plan-only` prints for that setup, and start no other engine process.
**Accept.** On a lab configuration the printed plan equals `simengine --plan-only`'s output on that setup, and by process spy exactly one `--plan-only` process starts.
**Binds.** `launcherChoice`, `runSetup`, `plan`, `commandLine`
**Verify.** T · `SYT-LCH-09`   **Trace.** —

## 11. The launcher window (`WIN`)

`D21`: a thin window over the launcher model, on the standard-library toolkit. Nothing here decides; each row is a call of the model.

**`SYS-0122`** · `P0` · `R1` — Every window action is one launcher-model call
**Shall.** The window shall hold no logic: each action shall be one call of the launcher model.
**Accept.** `check_window_boundary.py` finds in `window.py` no file access, process start or rule of its own; planted violations of each are reported with file and line.
**Binds.** `launcherChoice`
**Verify.** A · `ANL-08`   **Trace.** —

**`SYS-0123`** · `P0` · `R1` — *Copy command line* does exactly what *start* does
**Shall.** The command line the window copies shall be the one it starts, built by one function from the setup just written.
**Accept.** On a lab selection the copied text run in a shell and *start* give equal outputs on every port; a different command line fails.
**Binds.** `commandLine`, `runSetup`
**Verify.** T · `SYT-WIN-01`   **Trace.** —

**`SYS-0124`** · `P1` · `R1` — The window offers `measured` only where the recording allows it
**Shall.** The window shall offer `measured` for a stage only when the launcher model finds the recording holds the stage's outputs.
**Accept.** With `C`'s outputs removed from the recording the window's choices for `C` are `simulate` and `off`; with them present, `measured` is also offered.
**Binds.** `launcherChoice`, `recording`
**Verify.** T · `SYT-WIN-02`   **Trace.** —

**`SYS-0125`** · `P1` · `R1` — The window shows each stage's libraries and what the recording can feed
**Shall.** The window shall show each stage's mode and implementation, which libraries are available for the platform and, per recording, which stages could be `measured`.
**Accept.** For a lab selection the three lists equal the launcher model's answers for the same selection; one difference fails.
**Binds.** `launcherChoice`, `recording`
**Verify.** T · `SYT-WIN-02`   **Trace.** —

**`SYS-0126`** · `P1` · `R1` — The window adds recordings and starts runs
**Shall.** The window shall let recordings be added and a run be started and shall write no file but the run setup.
**Accept.** Adding two lab recordings and *start* give one run setup naming both in `sources[]`; the only file the window created is that setup.
**Binds.** `launcherChoice`, `runSetup`
**Verify.** T · `SYT-WIN-01`   **Trace.** —

**`SYS-0127`** · `P1` · `R1` — The window uses only the standard-library toolkit
**Shall.** The window shall import no graphical package but the standard library's toolkit.
**Accept.** `check_no_graphical_toolkit.py` over `src/adas_sim` finds only `tkinter` in `window.py`; a planted third-party import is reported.
**Binds.** `launcherChoice`
**Verify.** A · `ANL-08`   **Trace.** —

**`SYS-0194`** · `P1` · `R1` — The window isolates one stage
**Shall.** The window shall offer one action that sets a chosen stage `simulate` and every other stage `measured`, as `Selection.isolate` does.
**Accept.** On `running_example` `cut_c` the action on `B` leaves `B` `simulate` and every other stage whose outputs the recording holds `measured`; a stage without recorded outputs is not set `measured`.
**Binds.** `launcherChoice`, `recording`
**Verify.** T · `SYT-WIN-03`   **Trace.** —

**`SYS-0195`** · `P1` · `R1` — A group whose stages disagree shows a mixed state that cannot be chosen
**Shall.** The window shall show a group whose stages are in different modes as mixed, and refuse to choose the mixed state as a mode.
**Accept.** With `A` `simulate` and `B` `measured` the group's state is mixed and choosing it is refused; with both `simulate` it shows `simulate`.
**Binds.** `launcherChoice`
**Verify.** T · `SYT-WIN-03`   **Trace.** —

## 12. The scenario-to-recording script (`SCN`)

`D22`: a scenario file of explicit values in, a recording of real interface messages out, through the one Python writer in `interfaces`; the conventions are the contract's (`RCT:SYS-0039`, `RCT:SYS-0044`).

**`SYS-0128`** · `P0` · `R1` — A scenario's messages are written with exactly its values
**Shall.** `sim record` shall write each message a scenario file lists as one message of the stated interface type holding the listed values and no other.
**Accept.** For a scenario of N messages of two types the recording holds N messages that decode to the listed values, every unlisted field its default; one extra or changed value fails.
**Binds.** `scenarioFile`, `runRecording`
**Verify.** T · `SYT-SCN-01`   **Trace.** —

**`SYS-0129`** · `P0` · `R1` — The recording follows the recording conventions
**Shall.** The recording `sim record` writes shall follow the contract's recording conventions: topics, schemas, order, `manifest` and provenance.
**Accept.** `check_recording.py` passes it, and Vantage's reader opens it and returns its `manifest`; either failing fails.
**Binds.** `runRecording`
**Verify.** T · `SYT-SCN-02`   **Trace.** —

**`SYS-0130`** · `P1` · `R1` — A scenario is written through the one Python writer
**Shall.** `src/adas_sim/scenario` shall write a recording only through `adas_recording.writer.McapRecorder`.
**Accept.** `check_one_recording_writer.py` finds no other writer call in `src/adas_sim/scenario`; with a planted `mcap.McapWriter` it reports file and line.
**Binds.** `runRecording`
**Verify.** A · `ANL-09`   **Trace.** —

**`SYS-0131`** · `P1` · `R1` — A scenario value the type does not have is refused
**Shall.** `sim record` shall refuse a scenario naming a type or a field the interface schemas do not have, naming it, and write no file.
**Accept.** A scenario with an unknown type, and one with an unknown field, each end with an error naming it and no file; a valid one writes.
**Binds.** `scenarioFile`, `exitStatus`
**Verify.** T · `SYT-SCN-03`   **Trace.** —

**`SYS-0132`** · `P1` · `R1` — One scenario gives one recording
**Shall.** `sim record` shall give, for one scenario file, recordings that are equal outputs on every topic, in the same order.
**Accept.** Two runs on one scenario give the same message count, order and equal messages on every topic; a difference fails.
**Binds.** `scenarioFile`, `runRecording`
**Verify.** T · `SYT-SCN-01`   **Trace.** —

**`SYS-0133`** · `P0` · `R1` — A scenario's recording is an engine input like any other
**Shall.** An engine run shall read a scenario's recording as it reads a car's.
**Accept.** `data_triggered` `by_data` on a scenario's `source.X` and `source.Y` exits 0 and `T` has one control per distinct `in_X` counter of the scenario.
**Binds.** `scenarioFile`, `recording`
**Verify.** T · `SYT-SCN-04`   **Trace.** —

**`SYS-0134`** · `P1` · `R1` — `sim record` produces and executes nothing else
**Shall.** `sim record` shall start no engine and call no component, and write only the recording.
**Accept.** A run of the verb with a process spy sees no `simengine` start and creates one file; any other file or start fails.
**Binds.** `scenarioFile`, `runRecording`
**Verify.** T · `SYT-SCN-05`   **Trace.** —

## 13. Batch (`BAT`)

A batch is one run setup over a list of recordings: one supervised engine run per recording (`R-SIM-19`, `SYS-0088`). The loop that does it stays Python (`ARCH §11`).

**`SYS-0135`** · `P0` · `R1` — A batch runs one supervised engine run per recording
**Shall.** A batch shall start one `simengine --supervise` per recording, each from a run setup written for it.
**Accept.** On three lab recordings three attempt records exist; the three setups differ only in `sources[]`, `outputs.path` and `run_id`.
**Binds.** `runSetup`, `attemptManifest`, `commandLine`
**Verify.** T · `SYT-BAT-01`   **Trace.** —

**`SYS-0136`** · `P0` · `R1` — A failing recording never stops the batch
**Shall.** A crash, a timeout or a failure of one recording shall not stop the batch.
**Accept.** A batch of `cut_c`, `crash`, `hang` and `cut_c` runs all four and reports 0, 8, 7 and 0; fewer than four entries fails.
**Binds.** `batchReport`, `exitStatus`
**Verify.** T · `SYT-BAT-02`   **Trace.** —

**`SYS-0137`** · `P0` · `R1` — The batch tallies the exit codes
**Shall.** The batch shall report, per recording, the exit code, its name, the reason and the duration, and a total per code.
**Accept.** The totals sum to the number of recordings and each entry's code equals its attempt record's last outcome; a mismatch fails.
**Binds.** `batchReport`, `attemptManifest`
**Verify.** T · `SYT-BAT-02`   **Trace.** —

**`SYS-0138`** · `P1` · `R1` — Each run has its own self-contained directory
**Shall.** Each recording's run shall write one directory holding its setup, its recording, its event log, its attempt record and any reproducer.
**Accept.** Two entries' directories share no file; the directory of a passed entry opens with no other path.
**Binds.** `batchReport`, `runRecording`
**Verify.** T · `SYT-BAT-03`   **Trace.** —

**`SYS-0139`** · `P1` · `R1` — A batch is resumable and runs no completed recording again
**Shall.** A batch started again over the same directory shall start no recording whose attempt record is complete.
**Accept.** After a batch stopped halfway, the second run starts only the unfinished recordings, by process spy; one repeated start fails.
**Binds.** `batchReport`, `attemptManifest`
**Verify.** T · `SYT-BAT-03`   **Trace.** —

**`SYS-0140`** · `P1` · `R1` — A sweep of N values gives N runs differing in exactly the value swept
**Shall.** A sweep shall give one run setup per value, differing from the base only in the swept value and the names derived from it.
**Accept.** A sweep of three values gives three setups whose pairwise difference is that key, `run_id` and `outputs.path`.
**Binds.** `runSetup`, `batchReport`
**Verify.** T · `SYT-BAT-04`   **Trace.** —

**`SYS-0141`** · `P1` · `R1` — A recording that does not finish by its deadline is reported as timeout
**Shall.** The batch shall pass each recording's deadline to the supervisor and report an overrun as timeout, not as a failure.
**Accept.** A `hang` entry with a deadline below the hang is reported with code 7 and the reason `timeout`; any other name fails.
**Binds.** `batchReport`, `exitStatus`
**Verify.** T · `SYT-BAT-02`   **Trace.** —

**`SYS-0142`** · `P1` · `R1` — A read error follows a closed policy and skipped recordings are counted
**Shall.** The batch shall treat a recording the engine ends with exit 5 by one policy of `skip`, `abort` or `retry N`, and count each skip.
**Accept.** A cut-off recording: `skip` counts it and the batch goes on; `abort` ends the batch; `retry 2` makes two further attempts, recorded; another name is refused.
**Binds.** `batchReport`, `exitStatus`
**Verify.** T · `SYT-BAT-05`   **Trace.** —

**`SYS-0143`** · `P1` · `R1` — The duration estimate counts steps
**Shall.** A dry batch shall print the estimated number of engine steps from the recording's index and the clocks, with its factor.
**Accept.** For each exact lab case the printed estimate lies within the factor `⊘` of the step tap's count, and the factor is printed.
**Binds.** `batchReport`, `recording`
**Verify.** T · `SYT-BAT-06`   **Trace.** —

**`SYS-0207`** · `P1` · `R1` — A batch without a deadline is refused
**Shall.** The batch shall refuse a configuration without `attempt_timeout_ms`, naming it, and start nothing; with it, pass that value to each supervised start.
**Accept.** Without the key no `simengine` process and no entry directory exist; with it each command line holds `--attempt-timeout-ms` equal to it.
**Binds.** `batchReport`, `commandLine`, `exitStatus`
**Verify.** T · `SYT-BAT-07`   **Trace.** —

## 14. Configuration (`CFG`)

Configuration is authored in YAML and resolved by the launcher; the engine reads only the run setup. The bundle rules are `R-SIM-3a`, the override rules `R-SIM-15`, the ingest rules `R-SIM-23`. A stage's bundle folder is a key of the run setup (`D32 (2)`, `SYS-0200`).

**`SYS-0144`** · `P0` · `R1` — A stage's bundle with another hash than the setup names is refused
**Shall.** The engine shall refuse a run whose bundle for a stage holds another hash than that stage's `config_bundle_sha256`, naming the stage and both hashes.
**Accept.** A lab case with one bundle file edited ends with exit 2 naming the stage and both hashes, before the first step; the unedited case runs.
**Binds.** `runSetup`, `configBundle`, `exitStatus`
**Verify.** T · `SYT-CFG-01`, `SYT-CFG-11`   **Trace.** —

**`SYS-0145`** · `P0` · `R1` — One bundle per component and build is packed beside the library with its hash
**Shall.** Each component's build shall hold one `config/` folder beside its library with `bundle.sha256` computed by `bundle_sha256`.
**Accept.** For every built lab component the recomputed hash equals `bundle.sha256`; one changed byte in a bundle file fails.
**Binds.** `configBundle`
**Verify.** T · `SYT-CFG-01`   **Trace.** —

**`SYS-0146`** · `P1` · `R1` — A project mismatch between bundles warns
**Shall.** The launcher shall warn, naming both, when the bundles of the selected stages are for different projects.
**Accept.** Two bundles of different projects give one warning naming both; with `allow_mixed_projects` it is recorded in the setup, not raised.
**Binds.** `launcherChoice`, `configBundle`
**Verify.** T · `SYT-CFG-02`   **Trace.** —

**`SYS-0147`** · `P0` · `R1` — Ego parameters that disagree between bundles are an error
**Shall.** The launcher shall refuse a selection whose stages' bundles hold different ego parameters, with no escape.
**Accept.** Two bundles whose `ego_params.yaml` differ in one value end the launcher naming both files and the key; identical files pass.
**Binds.** `launcherChoice`, `configBundle`
**Verify.** T · `SYT-CFG-02`   **Trace.** —

**`SYS-0148`** · `P1` · `R1` — A calibration value changes with no rebuild
**Shall.** A value changed in a bundle file beside a library shall change the stage's output on the next run with no rebuild and no host edit.
**Accept.** `renumber_lib` `shifted`: with `LAB_A_RENUMBER` 0 and 1 in `A`'s bundle, `A`'s data outputs differ, from the same library file.
**Binds.** `configBundle`, `runRecording`
**Verify.** T · `SYT-CFG-03`   **Trace.** —

**`SYS-0149`** · `P1` · `R1` — Each resolved value keeps its layer
**Shall.** The launcher shall resolve configuration in its four layers and keep for each value the layer, file and line it came from.
**Accept.** A key given in two layers resolves to the later and its record names both; a value with no record fails.
**Binds.** `launcherChoice`
**Verify.** T · `SYT-CFG-04`   **Trace.** —

**`SYS-0150`** · `P1` · `R1` — Includes and variables resolve at load and are reported
**Shall.** The launcher shall resolve includes and `${var}` at load, identically for equal content, and report every resolution.
**Accept.** A configuration split by includes writes a byte-identical setup to the same configuration unsplit; each variable resolved is listed.
**Binds.** `launcherChoice`, `runSetup`
**Verify.** T · `SYT-CFG-04`   **Trace.** —

**`SYS-0151`** · `P1` · `R1` — A configuration file is validated against its published schema with a location
**Shall.** The launcher shall validate each configuration file against its kind's schema and name the file and key path of each error.
**Accept.** Four planted errors each end `sim validate` with an error naming the file and key path, with no recording and no library needed.
**Binds.** `launcherChoice`, `exitStatus`
**Verify.** T · `SYT-CFG-05`   **Trace.** —

**`SYS-0152`** · `P1` · `R1` — An unknown or missing schema version is refused
**Shall.** The launcher shall refuse a configuration file whose schema version is missing or not one it accepts, naming both.
**Accept.** A file with another version, and one with none, each end with an error naming the version found and those accepted.
**Binds.** `launcherChoice`, `exitStatus`
**Verify.** T · `SYT-CFG-05`   **Trace.** —

**`SYS-0153`** · `P1` · `R1` — Two producers for one port are refused
**Shall.** The launcher shall refuse a wiring in which two stages produce one port, naming both.
**Accept.** A lab wiring with a second producer of `D.in_C` ends with an error naming both stages and the port.
**Binds.** `launcherChoice`, `exitStatus`
**Verify.** T · `SYT-CFG-06`   **Trace.** —

**`SYS-0154`** · `P1` · `R1` — A required input with no producer is refused
**Shall.** The launcher shall refuse a wiring that leaves a required input with no producer, naming the input and what it considered.
**Accept.** A lab wiring with `D`'s input unwired ends with an error naming `D.in_C` and the candidates it looked at.
**Binds.** `launcherChoice`, `exitStatus`
**Verify.** T · `SYT-CFG-06`   **Trace.** —

**`SYS-0155`** · `P1` · `R1` — Port types are matched and a data port never feeds a control port
**Shall.** The launcher shall refuse a wiring whose producer and consumer types differ, or that wires a data port to a `control` port.
**Accept.** A wiring of an output to an input of another type, and one to a `control` port, each end with an error naming both ports.
**Binds.** `launcherChoice`, `exitStatus`
**Verify.** T · `SYT-CFG-06`   **Trace.** —

**`SYS-0156`** · `P1` · `R1` — A configuration round-trips to a byte-identical file
**Shall.** A configuration read and written again by the launcher shall give a byte-identical file.
**Accept.** For each lab configuration read and written, the output equals the input byte for byte; one differing byte fails.
**Binds.** `launcherChoice`
**Verify.** T · `SYT-CFG-04`   **Trace.** —

**`SYS-0157`** · `P0` · `R1` — The override verbs are the closed list of six
**Shall.** The engine shall accept in `mutations[]` only `const`, `hold`, `offset`, `scale`, `select` and `drop`, and refuse another verb at load, naming it.
**Accept.** Each verb applied to a lab port changes that port and no other; a seventh verb name ends with a load error naming it.
**Binds.** `runSetup`, `exitStatus`, `stageIn`
**Verify.** T · `SYT-CFG-07`   **Trace.** —

**`SYS-0158`** · `P0` · `R1` — An override never creates an entity
**Shall.** No override shall add an element; an index is `[i]` or `[*]` and never a predicate, and a `fixed_slots` port is cleared in place.
**Accept.** A predicate index is refused at load; `drop` on a `fixed_slots` port leaves the element count; no override raises it.
**Binds.** `runSetup`, `exitStatus`, `stageIn`
**Verify.** T · `SYT-CFG-07`   **Trace.** —

**`SYS-0159`** · `P1` · `R1` — The recording's manifest lists every override and fault in force
**Shall.** An engine run shall write into its recording's `manifest` one record per override and fault in force, with its address, verb and its window in steps.
**Accept.** A setup with two overrides and one fault gives three records equal to the setup's, windows in steps included; a missing or extra record fails.
**Binds.** `runSetup`, `runRecording`
**Verify.** T · `SYT-CFG-08`   **Trace.** —

**`SYS-0160`** · `P0` · `R1` — An ingest map renames and tags and computes nothing
**Shall.** Applying an ingest map shall change only a message's topic name and origin tag, and create no value, element or entity the source did not carry.
**Accept.** A recording read through a map equals the same recording renamed by hand, payload bytes included; a changed byte fails.
**Binds.** `recording`, `runSetup`
**Verify.** T · `SYT-CFG-09`   **Trace.** —

**`SYS-0161`** · `P1` · `R1` — A port the recording never carried is named and a cut that needs it is refused
**Shall.** A setup's `absent` list shall name each port its family never recorded, and a stage that needs one shall be refused at load, naming it.
**Accept.** A `cut_c` setup whose `absent` lists `C.out` ends with a load error naming it before the first step; without the entry the case runs.
**Binds.** `runSetup`, `recording`, `exitStatus`
**Verify.** T · `SYT-CFG-09`   **Trace.** —

**`SYS-0162`** · `P1` · `R1` — A payload whose type does not match its port is refused
**Shall.** The engine shall refuse a recorded payload whose type is not its port's declared type, and never coerce it.
**Accept.** A lab recording with one `A.out` message retyped ends the run with an error naming the port and both types; a coerced value fails.
**Binds.** `recording`, `exitStatus`
**Verify.** T · `SYT-CFG-09`   **Trace.** —

**`SYS-0163`** · `P1` · `R1` — A port claimed by two ingest maps is refused
**Shall.** The launcher shall refuse two ingest maps that claim one port, naming both maps and the port.
**Accept.** Two maps claiming `source.X` end the launcher with an error naming both files and the port; one map passes.
**Binds.** `launcherChoice`, `exitStatus`
**Verify.** T · `SYT-CFG-09`   **Trace.** —

**`SYS-0164`** · `P1` · `R1` — Ingest maps are resolved from beside the component library
**Shall.** The launcher shall resolve a component's ingest map from beside its library and never from a source checkout.
**Accept.** With the library copied alone to a new folder with its `ingest/`, the launcher resolves the map; with the map absent, no checkout path is searched.
**Binds.** `launcherChoice`
**Verify.** T · `SYT-CFG-09`   **Trace.** —

**`SYS-0165`** · `P1` · `R1` — The record policy of every port is in the setup and the recording
**Shall.** Each port's record policy shall be a key of the setup and be written into the recording's `manifest` for every port.
**Accept.** The manifest's `record_policies` lists every port of every stage with the setup's value; a missing port fails.
**Binds.** `runSetup`, `runRecording`
**Verify.** T · `SYT-CFG-08`   **Trace.** —

**`SYS-0166`** · `P1` · `R1` — Excluding or decimating an input a simulated stage consumes is refused
**Shall.** The engine shall refuse at load a `record` policy of `excluded` or `decimate` on a port a simulated stage consumes.
**Accept.** A lab setup with `excluded` on `A.in_X` ends with a load error naming the port; on an unconsumed output it runs.
**Binds.** `runSetup`, `exitStatus`
**Verify.** T · `SYT-CFG-08`   **Trace.** —

**`SYS-0199`** · `P1` · `R1` — A source file whose hash differs from the setup's is refused
**Shall.** The engine shall refuse a run whose `sources[]` file hashes to a value other than that entry's `sha256`, naming the file and both hashes.
**Accept.** A lab case with one recording byte changed ends with a load error naming the file and both hashes before the first step; the unchanged case runs.
**Binds.** `runSetup`, `recording`, `exitStatus`
**Verify.** T · `SYT-CFG-10`   **Trace.** —

**`SYS-0200`** · `P1` · `R1` — A stage is initialised from the bundle folder the setup names
**Shall.** The engine shall initialise each simulated stage from the folder its optional `config_bundle_path` names, and from `config/` beside its library when the key is absent.
**Accept.** On `renumber_lib` `shifted`, a folder with `LAB_A_RENUMBER` 1 gives `A` the outputs of a library copy with that bundle beside it; with the key absent, the other outputs.
**Binds.** `runSetup`, `configBundle`
**Verify.** T · `SYT-CFG-11`   **Trace.** —

**`SYS-0206`** · `P1` · `R1` — A wiring is ordered by its edges, not by the order the stages are declared
**Shall.** The launcher shall accept a stage reading a port of a stage declared after it, ordered by the wiring, and refuse a loop without a previous-cycle input, naming its stages.
**Accept.** `feedback`, and `running_example` declared in reverse, load and run with the lab case's outputs; `loop_no_edge` is refused naming `A` and `B`.
**Binds.** `launcherChoice`, `exitStatus`
**Verify.** T · `SYT-CFG-12`   **Trace.** —

## 15. Diagnostics (`DIA`)

Errors, the environment report, the log vocabulary and the run report. Vantage reports and never judges (`R-SIM-19`). The divergence rows add to `SYS-0043`; the grace is a key of the run setup (`D32 (3)`, `SYS-0201`).

**`SYS-0167`** · `P0` · `R1` — The error kinds and exit codes are one set in both languages
**Shall.** The Python error kinds and exit codes shall be the C++ set, name for name and value for value.
**Accept.** `check_error_parity.py` finds no difference; with one planted in `diagnostics/errors.py` it reports it.
**Binds.** `exitStatus`
**Verify.** A · `ANL-10`   **Trace.** —

**`SYS-0168`** · `P1` · `R1` — The environment report never raises
**Shall.** `sim doctor` shall report the engine, libraries, bundles and versions found, and an unknown for any it cannot read, and raise nothing.
**Accept.** With the engine missing, one library unreadable and one bundle absent it exits 0 and names each as unknown or absent.
**Binds.** `doctorReport`
**Verify.** T · `SYT-DIA-01`   **Trace.** —

**`SYS-0169`** · `P1` · `R1` — A wrong name is answered with the nearest name
**Shall.** The launcher shall answer a name it does not know with the nearest known names.
**Accept.** `sim` with a stage named `Dd` in a lab selection answers with `D` among its suggestions; a name with no near one gives none.
**Binds.** `launcherChoice`, `exitStatus`
**Verify.** T · `SYT-DIA-02`   **Trace.** —

**`SYS-0170`** · `P1` · `R1` — The log vocabulary is closed and carries the step number
**Shall.** Each log line the Python side writes shall use an `event=` name of the closed set the C++ set mirrors, with the step number where it has one.
**Accept.** `check_closed_sets.py` finds the two sets equal; a line with an unlisted name, or a `tick=` field, is reported.
**Binds.** `eventLog`
**Verify.** A · `ANL-10`   **Trace.** —

**`SYS-0171`** · `P1` · `R1` — A run ends with a summary of its warnings
**Shall.** A run started by the launcher shall end by printing the count of its warnings by kind from its own log lines.
**Accept.** A lab case with two fallbacks ends with a summary naming that kind and the count 2; a case with none prints none.
**Binds.** `eventLog`
**Verify.** T · `SYT-DIA-03`   **Trace.** —

**`SYS-0172`** · `P1` · `R1` — The run report names steps, time, modules and bytes read
**Shall.** An engine run shall print its steps, wall time, each simulated stage's time, library path, version, build and bundle hash, and bytes read per topic.
**Accept.** On `cut_c` steps equal the step tap's, bytes per topic equal the payload bytes read, and each simulated stage is listed with its time.
**Binds.** `eventLog`, `exitStatus`
**Verify.** T · `SYT-DIA-04`   **Trace.** —

**`SYS-0173`** · `P1` · `R1` — A diagnostic never raises or aborts a run
**Shall.** No diagnostic of the engine or the launcher shall raise or end an engine run.
**Accept.** With the trace on an unwritable path, the byte counter and the report each failing, a lab run still exits 0 with equal outputs.
**Binds.** `eventLog`, `exitStatus`
**Verify.** T · `SYT-DIA-05`   **Trace.** —

**`SYS-0174`** · `P1` · `R1` — Data after the first divergence and a grace is flagged informational
**Shall.** The engine shall flag as informational every message it writes after the first divergence plus the grace `⊘`, and none before.
**Accept.** On a diverging lab case with the lab's provisional grace, messages from the first divergence plus the grace are flagged and earlier ones are not.
**Binds.** `runRecording`, `eventLog`
**Verify.** T · `SYT-DIA-06`   **Trace.** —

**`SYS-0175`** · `P1` · `R1` — The engine prints its process id and waits when asked
**Shall.** With `--wait-for-attach` the engine shall print its process id before any step and run no step until released.
**Accept.** The id is printed and the engine's step count stays 0 until released; without the option no wait occurs.
**Binds.** `exitStatus`, `stepRecord`
**Verify.** T · `SYT-DIA-07`   **Trace.** —

**`SYS-0192`** · `P1` · `R1` — The trace is off by default, keyed by step and changes no value
**Shall.** The optional trace shall be off by default, write one entry per run keyed by step number, and change no value.
**Accept.** With the trace on, its entries equal the case's runs, each with its step; the outputs equal those of a run without it.
**Binds.** `eventLog`, `runRecording`
**Verify.** T · `SYT-DIA-05`   **Trace.** —

**`SYS-0196`** · `P1` · `R1` — A message repeating every step is logged once with a count
**Shall.** The log shall write a message that repeats beyond the flood threshold `⊘` as one counted entry, with one entry saying counting began, naming the message and the threshold.
**Accept.** A lab case repeating one warning every step logs it once with its total count and the entry naming message and threshold; other messages stay visible.
**Binds.** `eventLog`
**Verify.** T · `SYT-DIA-08`   **Trace.** —

**`SYS-0201`** · `P1` · `R1` — The grace after the first divergence is a key of the run setup
**Shall.** The engine shall read the grace of `SYS-0174` from the run setup's optional `divergence_grace_steps` (value `⊘`), flag nothing when it is absent, and hold no default in code.
**Accept.** On `renumber_lib` `shifted`, changing the key by one moves the first flagged message by one step; with the key absent none is flagged.
**Binds.** `runSetup`, `runRecording`
**Verify.** T · `SYT-DIA-06`   **Trace.** —

**`SYS-0203`** · `P1` · `R1` — `--plan-only` prints the plan and ends
**Shall.** With `--plan-only` the engine shall load the run setup, print its plan, run no stage, write no file and exit 0.
**Accept.** On every lab setup with `outputs.path` set, the exec probe sees no call, no file is created and the exit code is 0; a call, a file or another code fails.
**Binds.** `runSetup`, `plan`, `exitStatus`
**Verify.** T · `SYT-DIA-09`   **Trace.** —

**`SYS-0204`** · `P1` · `R1` — The plan names each input's producer and selection policy and the limits
**Shall.** The plan shall list the stages in run order, each with its inputs, their producers and selection policy, its trigger or clock, and the setup's limits.
**Accept.** On every lab setup the order is that of each step's calls in a real run (exec probe), and each producer, policy and limit equals the setup's.
**Binds.** `runSetup`, `plan`
**Verify.** T · `SYT-DIA-09`   **Trace.** —

## 16. Delivery (`DLV`)

What `adas-vantage` ships and how a consumer resolves it (`R-SIM-11`, `R-BUILD-1`).

**`SYS-0176`** · `P0` · `R1` — The package ships the engine, the inspector, the writer library and the Python package
**Shall.** `adas-vantage` shall ship `simengine`, `vantage-inspect`, the `livemeas` library with its headers, and the `adas_sim` package.
**Accept.** A fresh install tree holds each of the four; one missing fails.
**Binds.** `deliveredPackage`
**Verify.** T · `SYT-DLV-01`   **Trace.** —

**`SYS-0177`** · `P0` · `R1` — A consumer resolves each part from the package alone
**Shall.** A consumer shall resolve the engine, the inspector, the writer and the Python package from the installed package, with no sibling checkout and no path outside it.
**Accept.** From the install tree alone, with the source tree hidden, the launcher finds the engine and a lab case runs to exit 0.
**Binds.** `deliveredPackage`, `commandLine`
**Verify.** T · `SYT-DLV-02`   **Trace.** —

**`SYS-0178`** · `P1` · `R1` — The recording writer package is the one the engine was linked with
**Shall.** The Python side shall find the recording writer in the `adas-interfaces` package the engine was linked with, named by a file beside the engine.
**Accept.** `recording_writer()` returns a module under the folder `adas_recording.path` names; with that file removed it ends naming it.
**Binds.** `deliveredPackage`
**Verify.** T · `SYT-DLV-02`   **Trace.** —

**`SYS-0179`** · `P1` · `R1` — The package, port-model and ABI versions are independent and listed
**Shall.** The package shall state its own version, the port-model version and the ABI version separately, with a compatibility list.
**Accept.** The installed version file names the three; changing one in a copy does not change the other two.
**Binds.** `deliveredPackage`
**Verify.** T · `SYT-DLV-03`   **Trace.** —

**`SYS-0180`** · `P1` · `R1` — A release ships a self-test on a miniature recording
**Shall.** The package shall ship a self-test that runs the engine on a miniature recording and ends 0 or non-zero.
**Accept.** The self-test run from the install tree exits 0; with the engine's library renamed it exits non-zero.
**Binds.** `deliveredPackage`, `exitStatus`
**Verify.** T · `SYT-DLV-03`   **Trace.** —

**`SYS-0181`** · `P1` · `R1` — The shipped source names no component and no function
**Shall.** The framework's shipped source shall name no component and no function (`R-SIM-1`).
**Accept.** `check_invariants.py`'s `GT-1` finds none in `src`; with a planted component name in `src/adas_sim` it reports it.
**Binds.** `deliveredPackage`
**Verify.** A · `ANL-11`   **Trace.** —

**`SYS-0182`** · `P1` · `R1` — The same configuration runs on both operating systems
**Shall.** One configuration and run setup shall run unchanged on Windows and Linux, path handling and library loading each done in one place.
**Accept.** Every lab setup holds only `/` paths and runs to its expected exit code on the machine under test; `check_paths_one_place.py` finds one place for each.
**Binds.** `runSetup`, `deliveredPackage`
**Verify.** A · `ANL-11`   **Trace.** —

**`SYS-0183`** · `P1` · `R1` — Every new source file carries the file header
**Shall.** Every new source file shall carry the file header block with the token `VANTAGE`.
**Accept.** `check_headers.py` finds none missing; with a planted file without one it reports it.
**Binds.** `deliveredPackage`
**Verify.** A · `ANL-11`   **Trace.** —

## 17. Determinism (`DET`)

`R-SIM-24` as `ARCH §13` amends it. The comparison is over port values, never file bytes.

**`SYS-0184`** · `P0` · `R1` — Same-process, fresh-process and thread-count runs are exact
**Shall.** Runs of one setup in the same process, a fresh process and with `--threads N` shall be equal outputs on every port, and any difference blocks.
**Accept.** On every exact lab case the three comparisons are equal; one differing byte outside `cycle_counter` fails and is named by port and step.
**Binds.** `compareReport`, `runRecording`
**Verify.** T · `SYT-DET-01`   **Trace.** —

**`SYS-0185`** · `P1` · `R1` — Rebuilt-binary and other-machine runs are measured and declared
**Shall.** A comparison across a rebuilt binary or another machine shall report its differences and the tolerance in force, and never fail the gate.
**Accept.** A pair differing in `library_sha256` reports its differences with the declared tolerance and exits 0; the report names the axis.
**Binds.** `compareReport`
**Verify.** T · `SYT-DET-02`   **Trace.** —

**`SYS-0186`** · `P0` · `R1` — The comparison axis is derived from the two manifests
**Shall.** The comparison axis shall be derived from the two recordings' manifests, and a pair differing in more than one dimension shall say so.
**Accept.** A pair differing in `process_nonce` only is the fresh-process axis; one also differing in `library_sha256` is reported as more than one.
**Binds.** `compareReport`, `runRecording`
**Verify.** T · `SYT-DET-03`   **Trace.** —

**`SYS-0187`** · `P0` · `R1` — The comparison is over decoded port values
**Shall.** The comparison of two runs shall be over decoded port values by equal outputs, never over file bytes.
**Accept.** Two recordings of one run differing in `run_id` and nonce compare equal; one changed port value is reported with step, port and first differing field.
**Binds.** `compareReport`, `runRecording`
**Verify.** T · `SYT-DET-03`   **Trace.** —

**`SYS-0188`** · `P1` · `R1` — A tolerance is declared once per component and field, with its reason
**Shall.** A tolerance shall be declared once per component and field in its tolerance file with a written reason, default exact, and its hash recorded.
**Accept.** A tolerance with no reason is refused naming the file; the manifest of a compared run carries the hash of the file in force.
**Binds.** `compareReport`, `runRecording`
**Verify.** T · `SYT-DET-02`   **Trace.** —

**`SYS-0189`** · `P1` · `R1` — A re-run is pinned to the library hash the recording carries
**Shall.** A re-run shall be pinned to each `library_sha256` the recording carries, and report a library it cannot pin.
**Accept.** With `--pin-builds` and a different library, the run ends naming the stage and both hashes; a locally built library is reported unpinnable.
**Binds.** `runSetup`, `runRecording`, `exitStatus`
**Verify.** T · `SYT-DET-04`   **Trace.** —

## 18. The Python side never runs a component (`PYR`)

The Python run path is retired (`ARCH §11`, the register's code table). Only the obligation that remains is a row.

**`SYS-0190`** · `P0` · `R1` — Python never runs a component
**Shall.** No Python module of `adas-vantage` shall load a component library for execution or call its `adasExec`.
**Accept.** `check_no_python_run.py` finds no `adasExec` or component execution in `src/adas_sim`, and `check_no_retired_imports.py` no import of a retired module; a planted one of each is reported.
**Binds.** `stageIn`
**Verify.** A · `ANL-12`, `ANL-13`   **Trace.** —

**`SYS-0191`** · `P1` · `R1` — The engine never calls back into Python
**Shall.** The engine and its libraries shall contain no call into Python.
**Accept.** `check_no_python_run.py` finds no Python header or embedding call in `src/simcore`, `src/simengine`, `src/livemeas` or `src/inspector`; a planted include is reported.
**Binds.** `stageIn`
**Verify.** A · `ANL-12`   **Trace.** —

---

## 19. Verification strategy

Every `T` row runs on **lab cases** (`VANTAGE_Lab_Design.md` §6): the fake car's recording is the
known right answer, so a pass is equality, not tolerance. **Gate `G3`** (`VANTAGE_DEV_PLAN.md`
§5) is the test group of `VANTAGE_Test_Spec.md` §1 and **gate `G4`** the group of its §1a. Every `A` row ships a planted-violation
case (`R-REQ-9`).

| Method | Count | Notes |
|---|---|---|
| T | 189 | `simengine` on a lab case, the step tap, the exec probe, the control tick probe, a test reader, a flawed-writer, a supervised run, the launcher driven from Python, the window, a batch, a scenario, an install tree or a pair of runs |
| A | 18 | source checks over the engine, the inspector, the supervisor, the launcher, the window, the scenario script, the Python side and the delivery |

## 20. Superseded and retired UIDs

None yet.

## 21. Open decisions

None open. Closed and handed on (owner, 2026-10-31):

| # | Question | Answer |
|---|---|---|
| 1 | The run setup's schema version string | `adas.sim.runspec/2.0` (`SYS-0004`) |
| 2 | How the engine finds a stage's bundle built for another configuration when the setup carries only `config_bundle_sha256` | `D32 (2)` |
| 3 | Where the grace after the first divergence lives, and how data after it is flagged informational | `D32 (3)` |
| 4 | Whether the first divergence names the first differing field | `D32 (4)` |

Closed by `D32` (orchestrator, under the owner's latitude, 2026-11-04; the owner may overturn):

| # | Question | Answer |
|---|---|---|
| 2 | How the engine finds a stage's bundle | the setup carries each stage's resolved bundle folder, `stages[].config_bundle_path`; a hash mismatch is refused (`SYS-0200`, `SYS-0144`) |
| 3 | Where the grace after the first divergence lives | the setup's optional `divergence_grace_steps`, value `⊘`, read by the engine; no constant in code (`SYS-0201`) |
| 4 | Whether the first divergence names the first differing field | yes: step, stage, port and the first differing field (`SYS-0202`) |
| 5 | Fault windows in steps or in time | in steps (`SYS-0159`) |
| 6 | Where a supervised start's deadline comes from | a required key of the batch configuration and a required argument of the launcher's supervised start; never a default (`SYS-0207`, `SYS-0109`) |
| 7 | The fate of `progress.json` and the C++ `Checkpoint` | the batch reads the attempt record and the supervision cell, not `progress.json` (`SYS-0137`, `SYS-0139`); the C++ `Checkpoint` and the setup's `checkpoint.path` stay, optional and off by default |
| 8 | A gate before migration | none: `G5` is migration itself; the test groups of `WP-19` to `WP-27` run in the full suite |
| 9 | The dry run's plan | `simengine --plan-only` prints the engine's plan (`SYS-0001` amended, `SYS-0203`, `SYS-0204`); the dry run prints it beside the resolved setup (`SYS-0205`) |
