# VANTAGE — the simulation tool
## System Requirements Specification — v0.1

**Owner:** Vantage program (vantage-dev, Plan C)
**Layer:** `SYS`, the top declared layer (`layers.yaml`), so every `Trace` is `—`.
**Status:** Draft for review. Not baselined. Parts 8a and 8b of `VANTAGE_DEV_PLAN.md` §6 step 8:
the orchestrator (`C1`), then the live measurement writer, the inspector and the supervisor
(`C2`). Part 8c adds its sections after §9.
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
`SUP` the supervisor.
Priority split: 53 `P0`, 52 `P1`, 0 `P2`; all `R1`. Without a `P0` row an engine run is not
exact against the car; a `P1` row makes a result easier to trust or diagnose.

---

# PART A — FUNCTIONAL REQUIREMENTS

## 1. The run setup (`RUN`)

The keys and their meaning: `ARCH §2.3`, `§4`. One engine run reads one recording; many
recordings are a batch of engine runs (`R-SIM-19`).

**`SYS-0001`** · `P0` · `R1` — The run setup is the engine's only input
**Shall.** The engine shall take every choice of an engine run from the run setup, its recording, `--threads`, `--wait-for-attach`, `--supervise`, `--restart-on-crash` and `--attempt-timeout-ms` only.
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

## 10. Verification strategy

Every `T` row runs on **lab cases** (`VANTAGE_Lab_Design.md` §6): the fake car's recording is the
known right answer, so a pass is equality, not tolerance. **Gate `G3`** (`VANTAGE_DEV_PLAN.md`
§5) is the test group of `VANTAGE_Test_Spec.md` §1 and **gate `G4`** the group of its §1a. Every `A` row ships a planted-violation
case (`R-REQ-9`).

| Method | Count | Notes |
|---|---|---|
| T | 99 | `simengine` on a lab case, the step tap, the exec probe, the control tick probe, a test reader, a flawed-writer or a supervised run |
| A | 6 | source checks over the engine, the inspector and the supervisor |

## 11. Superseded and retired UIDs

None yet.

## 12. Open decisions

None in this part. Closed and handed on (owner, 2026-10-31):

| # | Question | Answer |
|---|---|---|
| 1 | The run setup's schema version string | `adas.sim.runspec/2.0` (`SYS-0004`) |
| 2 | How the engine finds a stage's bundle built for another configuration when the setup carries only `config_bundle_sha256` | part 8c (configuration) |
| 3 | Where the grace after the first divergence lives, and how data after it is flagged informational | part 8c (diagnostics) |
| 4 | Whether the first divergence names the first differing field | part 8c (the comparison of two runs) |
