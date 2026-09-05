# PARITY — Test Specification

**One file, both layers.** A test's layer comes from its identifier prefix,
declared in `layers.yaml`: `STT`/`E2E` → `STK`, `SYT`/`INSP`/`ANL` → `SYS`.

**A test never restates an `Accept` clause** (`R-REQ-4`) — its expected value
*is* the served requirement's `Accept`, cited by UID. What a test contributes
is only what the requirement cannot know: `Serves`, `Fixture`, `Steps` and its
cases. **Every case states its FAIL side** (`R-REQ-5`), because a pass
criterion with no stated contradiction lets the operator decide at execution
time what "didn't really fail" means.

## Fixture catalogue

Named, never ad-hoc. An ad-hoc fixture is how two tests come to disagree about
what "a run" means.

| Fixture | What it is |
|---|---|
| `F-UNIT` | A direct call into the engine, no recording and no library |
| `F-TWO-GEN` | Two recordings of one drive, the second using an older topic vocabulary |
| `F-SPLIT` | A stage-1 output recording, plus the original measurement it came from |
| `F-TWO-BUILD` | A candidate library and a staged reference library built from identical source |
| `F-TWO-BUILD-DIV` | `F-TWO-BUILD` with one deliberate difference injected into the reference |
| `F-LAUNCH` | The launcher open on a pipeline of several stages |
| `F-LIVE` | A session already running, reachable from a script |
| `F-PLAY` | The player open on a self-produced recording |
| `F-CYCLES` | A recording carrying at least two declared cycles at different periods |
| `F-RANGES` | A recording with named ranges, annotations and classifications stored |
| `F-CORPUS` | A set of recordings carrying classifications |
| `F-FLOOD` | A run whose component emits one identical warning on every tick |
| `F-PLUGIN-OK` | A plug-in bundle declaring all four identity fields |
| `F-PLUGIN-BAD` | `F-PLUGIN-OK` with one identity field removed |
| `F-BUNDLE-EMBED` | A recording produced by a run with a packed configuration bundle |
| `F-NO-BUNDLE` | A recording carrying no configuration bundle |
| `F-SRC` | The `modules/sim` source tree as checked in |

## Named checklist — `CL-PLUGIN-IDENTITY`

`R-REQ-8`: an inspection cites a **named** checklist, or "inspected" comes to
mean "someone read it". Used by `INSP-01`.

| # | Surface | Question |
|---|---|---|
| 1 | Plug-in listing | Are description, version, author and supported projects all shown? |
| 2 | Inspection view | Are the same four shown, with the same values? |
| 3 | Refusal message | Does a refused plug-in still name all four it did declare? |
| 4 | All three | Is an undeclared field shown as absent rather than blank? |

---

## 1. Stakeholder validation — `STT`

**`STT-01`** · T · fixture `F-TWO-GEN` — A renamed topic still feeds the port
**Serves.** `STK-0001`
**Steps.** Run both recordings against one unchanged map; compare the ports fed and the reported match.
- `.c1` **PASS:** both runs feed the same ports, per `STK-0001` Accept. **FAIL:** the older recording feeds fewer.
- `.c2` **PASS:** each run reports which address matched. **FAIL:** either run reports none.

**`STT-02`** · T · fixture `F-SPLIT` — A run draws from two recordings
**Serves.** `STK-0002`
**Steps.** Run with the front end replayed from the stage-1 output and calibration from the original.
- `.c1` **PASS:** the run completes and each port read from its assigned recording, per `STK-0002` Accept. **FAIL:** any port read from the other.

**`STT-03`** · T · fixture `F-TWO-BUILD-DIV` — Two builds are compared and the divergence located
**Serves.** `STK-0003`
**Steps.** Run candidate against reference; read the divergence report.
- `.c1` **PASS:** the reported tick, port and field match the injected difference, per `STK-0003` Accept. **FAIL:** no divergence reported, or a different one.

**`STT-04`** · D · fixture `F-LAUNCH` — One action isolates a stage
**Serves.** `STK-0004`
**Steps.** Invoke the isolate action on one stage; screenshot the resulting selection.
- `.c1` **PASS:** that stage executes and all others replay, per `STK-0004` Accept. **FAIL:** any other stage still executes.

**`STT-05`** · T · fixture `F-LAUNCH` — The screen's selection reproduces headlessly
**Serves.** `STK-0005`
**Steps.** Resolve the run spec from the screen; run the displayed invocation; compare resolved specs.
- `.c1` **PASS:** the two resolved run specs are identical, per `STK-0005` Accept. **FAIL:** they differ in any field.

**`STT-06`** · D · fixture `F-PLAY` — Transport controls move the position as named
**Serves.** `STK-0006`
**Steps.** Exercise each transport control in turn; record the displayed position before and after.
- `.c1` **PASS:** every control moves the position as its name states, per `STK-0006` Accept. **FAIL:** any control does nothing or moves the wrong way.

**`STT-07`** · T · fixture `F-FLOOD` — The log survives a repeating message
**Serves.** `STK-0007`
**Steps.** Run to completion; read the log; count entries for the repeating message and check earlier ones.
- `.c1` **PASS:** one entry with a count, and earlier messages still present, per `STK-0007` Accept. **FAIL:** one entry per tick, or earlier messages displaced.

**`STT-08`** · T · fixture `F-RANGES` — A named range survives and drives a batch
**Serves.** `STK-0008`
**Steps.** Reopen the recording; read the ranges; run a batch with play-only set.
- `.c1` **PASS:** the range is present with its original name and bounds, per `STK-0008` Accept. **FAIL:** absent or altered.
- `.c2` **PASS:** the batch executes no tick outside the range. **FAIL:** any tick outside it executes.

**`STT-09`** · T · fixture `F-CYCLES` — Stepping by a cycle lands on a coherent set
**Serves.** `STK-0009`
**Steps.** Select a cycle; step once; inspect every input belonging to that cycle.
- `.c1` **PASS:** all of them come from one run of the cycle, per `STK-0009` Accept. **FAIL:** any carries a value from an earlier run.
- `.c2` **PASS:** the selected cycle is named on screen. **FAIL:** it is not identified.

**`STT-10`** · T · fixture `F-PLUGIN-OK` — A plug-in can be identified without its source
**Serves.** `STK-0010`
**Steps.** List the installed plug-ins; read the fields shown for one.
- `.c1` **PASS:** description, version, author and supported projects are all shown, per `STK-0010` Accept. **FAIL:** any of the four missing.

**`STT-11`** · D · fixture `F-LAUNCH` — A disagreeing group is shown as disagreeing
**Serves.** `STK-0011`
**Steps.** Set two stages of one group to different modes; screenshot the group control.
- `.c1` **PASS:** the group shows a state reporting the disagreement, per `STK-0011` Accept. **FAIL:** it shows one member's mode as if it were the group's.

**`STT-12`** · T · fixture `F-LIVE` — A running session answers a script
**Serves.** `STK-0012`
**Steps.** Attach a script; read the position and one property; start and stop playback; add a mark.
- `.c1` **PASS:** all four operations succeed against the live session, per `STK-0012` Accept. **FAIL:** any is refused or requires the screen.

**`STT-13`** · T · fixture `F-RANGES` — Annotations and classifications stay distinct
**Serves.** `STK-0013`
**Steps.** List each kind separately; select a corpus by one classification.
- `.c1` **PASS:** each listing returns only its own kind, per `STK-0013` Accept. **FAIL:** either returns the other's entries.
- `.c2` **PASS:** the corpus selection returns exactly the recordings carrying that classification. **FAIL:** any missing or extra.

**`STT-14`** · T · fixture `F-BUNDLE-EMBED` — A recording opens correctly with no build present
**Serves.** `STK-0014`
**Steps.** Copy the recording to a machine with no build; open it; compare the rendered geometry against the producing run.
- `.c1` **PASS:** it renders with the configuration it carries, per `STK-0014` Accept. **FAIL:** it renders differently, or reads a bundle from disk.

## 2. System verification — `SYT`

**`SYT-ING-01`** · T · fixture `F-TWO-GEN` — An ordered address list resolves on the second entry
**Serves.** `SYS-0001`
**Steps.** Map one port to two addresses in order; run against the recording carrying only the second.
- `.c1` **PASS:** the port resolves, per `SYS-0001` Accept. **FAIL:** the port is unresolved.

**`SYT-ING-02`** · T · fixture `F-TWO-GEN` — The matched address is reported per port
**Serves.** `SYS-0002`
**Steps.** Run; read the run manifest's per-port match report.
- `.c1` **PASS:** every resolved port names one matched address, per `SYS-0002` Accept. **FAIL:** any resolved port names none or more than one.
- `.c2` **PASS:** an unresolved port names no address. **FAIL:** it names one.

**`SYT-ING-03`** · T · fixture `F-SPLIT` — Each port reads from its assigned recording
**Serves.** `SYS-0003`
**Steps.** Run with two named sources and a per-port assignment; trace each port's bytes to a source.
- `.c1` **PASS:** every port's bytes come from the recording it was assigned, per `SYS-0003` Accept. **FAIL:** any port reads from the other.

**`SYT-ENG-01`** · T · fixture `F-SPLIT` — No port reads from two sources
**Serves.** `SYS-0005`
**Steps.** Attempt to bind one port to both named sources; run every reachable configuration.
- `.c1` **PASS:** no configuration produces a port with values from more than one recording, per `SYS-0005` Accept. **FAIL:** any does.

**`SYT-ENG-02`** · T · fixture `F-TWO-BUILD` — Both builds see the same inputs
**Serves.** `SYS-0006`
**Steps.** Run side by side; capture both builds' input port values on every tick.
- `.c1` **PASS:** the captured values are byte-identical on every tick, per `SYS-0006` Accept. **FAIL:** they differ on any tick.

**`SYT-ENG-03`** · T · fixture `F-TWO-BUILD-DIV` — The first divergence is located
**Serves.** `SYS-0007`
**Steps.** Run side by side against a reference carrying a known injected difference.
- `.c1` **PASS:** the reported tick, port and field match the injection, per `SYS-0007` Accept. **FAIL:** any of the three is wrong, or nothing is reported.

**`SYT-ENG-04`** · T · fixture `F-RANGES` — A batch honours or ignores named ranges
**Serves.** `SYS-0021`
**Steps.** Run the batch twice, once with play-only set and once with ignore set; record executed ticks.
- `.c1` **PASS:** with play-only, no tick outside a named range executes, per `SYS-0021` Accept. **FAIL:** any does.
- `.c2` **PASS:** with ignore, every tick executes. **FAIL:** any is skipped.

**`SYT-RUN-01`** · T · fixture `F-TWO-BUILD` — The reference build is identified, or the run refuses
**Serves.** `SYS-0008`
**Steps.** Run with a staged reference and read the manifest; then run with none staged.
- `.c1` **PASS:** the manifest names the reference build's hash, per `SYS-0008` Accept. **FAIL:** the field is absent or empty.
- `.c2` **PASS:** with no reference staged the run refuses to start. **FAIL:** it starts anyway.

**`SYT-RUN-02`** · T · fixture `F-LAUNCH` — Written and in-memory selections resolve alike
**Serves.** `SYS-0012`
**Steps.** For each selection the launcher can express, resolve from memory and from the written file; hash both.
- `.c1` **PASS:** the hashes are equal for every selection, per `SYS-0012` Accept. **FAIL:** any pair differs.

**`SYT-RUN-03`** · T · fixture `F-LIVE` — A live session exposes read and control
**Serves.** `SYS-0013`
**Steps.** From a script with no screen, read position and a property, start and stop playback, add a mark.
- `.c1` **PASS:** all five operations succeed, per `SYS-0013` Accept. **FAIL:** any is unavailable without the screen.

**`SYT-LNC-01`** · T · fixture `F-LAUNCH` — Isolate changes only the modes
**Serves.** `SYS-0009`
**Steps.** Capture the full selection; invoke isolate on one stage; capture and diff.
- `.c1` **PASS:** the chosen stage executes and all others replay, per `SYS-0009` Accept. **FAIL:** any other stage still executes.
- `.c2` **PASS:** no field outside the stage modes changed. **FAIL:** anything else moved.

**`SYT-LNC-02`** · D · fixture `F-LAUNCH` — The mixed state is computed and not selectable
**Serves.** `SYS-0010`
**Steps.** Set members to differing modes, screenshot, attempt to select the third state, then set all alike.
- `.c1` **PASS:** the group reads mixed and the state cannot be selected, per `SYS-0010` Accept. **FAIL:** it is selectable.
- `.c2` **PASS:** setting all members alike removes the state. **FAIL:** it persists.

**`SYT-LNC-03`** · D · fixture `F-LAUNCH` — The reproducing invocation is displayed
**Serves.** `SYS-0011`
**Steps.** Screenshot the displayed invocation; copy it as one command; compare with the run spec path written.
- `.c1` **PASS:** it names the written run spec and copies as a single command, per `SYS-0011` Accept. **FAIL:** it names something else, or spans several commands.

**`SYT-PLY-01`** · D · fixture `F-PLAY` — Every named transport action is present and correct
**Serves.** `SYS-0015`
**Steps.** Exercise all nine actions; record the displayed position before and after each.
- `.c1` **PASS:** all nine are present. **FAIL:** any is missing.
- `.c2` **PASS:** each moves the position in the direction and by the amount its name states, per `SYS-0015` Accept. **FAIL:** any does not.

**`SYT-PLY-02`** · T · fixture `F-PLAY` — Unbounded speed reports a measured rate
**Serves.** `SYS-0016`
**Steps.** Run unbounded; compare the displayed rate against ticks divided by elapsed wall time.
- `.c1` **PASS:** the displayed rate matches the measurement, per `SYS-0016` Accept. **FAIL:** it reports a fixed or requested multiplier.

**`SYT-PLY-03`** · T · fixture `F-CYCLES` — All five step granularities advance by their unit
**Serves.** `SYS-0017`
**Steps.** Select each granularity in turn and step once; measure the advance.
- `.c1` **PASS:** each of the five is selectable, per `SYS-0017` Accept. **FAIL:** any cannot be selected.
- `.c2` **PASS:** each advances by the unit it names. **FAIL:** any advances by a different unit.

**`SYT-PLY-04`** · D · fixture `F-CYCLES` — The selected cycle is identified three ways
**Serves.** `SYS-0018`
**Steps.** Screenshot the cycle display; select a second cycle; screenshot again.
- `.c1` **PASS:** name, index and period are all shown, per `SYS-0018` Accept. **FAIL:** any of the three is missing.
- `.c2` **PASS:** all three change with the selection. **FAIL:** any is stale.

**`SYT-PLY-05`** · T · fixture `F-CYCLES` — A cycle step leaves no input from an earlier run
**Serves.** `SYS-0019`
**Steps.** Step by the chosen cycle; for each of its inputs, read which run of that cycle produced it.
- `.c1` **PASS:** all come from one run, per `SYS-0019` Accept. **FAIL:** any comes from an earlier one.

**`SYT-PLY-06`** · T · fixture `F-RANGES` — A named range round-trips
**Serves.** `SYS-0020`
**Steps.** Name a range, close the recording, reopen it, read the range back.
- `.c1` **PASS:** name and bounds are unchanged, per `SYS-0020` Accept. **FAIL:** absent, renamed or moved.

**`SYT-REC-01`** · T · fixture `F-RANGES` — The two mark kinds are stored apart
**Serves.** `SYS-0022`
**Steps.** Store one of each kind; list each kind; read the fields of each entry.
- `.c1` **PASS:** each listing returns only its own kind, per `SYS-0022` Accept. **FAIL:** either returns the other's.
- `.c2` **PASS:** each entry carries the fields its kind defines. **FAIL:** the two share one field set.

**`SYT-REC-02`** · T · fixture `F-CORPUS` — Selection by classification is exact
**Serves.** `SYS-0023`
**Steps.** Query by one classification; compare the result against the known carriers.
- `.c1` **PASS:** every carrier is returned and no non-carrier is, per `SYS-0023` Accept. **FAIL:** any missing or extra.

**`SYT-REC-03`** · T · fixture `F-BUNDLE-EMBED` — The bundle travels in the recording
**Serves.** `SYS-0027`
**Steps.** Open the recording where no build exists; compare rendered geometry against the producing run.
- `.c1` **PASS:** it renders from the carried bundle, per `SYS-0027` Accept. **FAIL:** geometry differs, or a bundle is read from disk.

**`SYT-REC-04`** · T · fixture `F-NO-BUNDLE` — A missing bundle is stated, not filled in
**Serves.** `SYS-0028`
**Steps.** Open a recording carrying no bundle beside a source checkout that has one; read the report and the values used.
- `.c1` **PASS:** the absence is stated, per `SYS-0028` Accept. **FAIL:** it is not mentioned.
- `.c2` **PASS:** no value is read from the checkout. **FAIL:** any is.

**`SYT-DIA-01`** · T · fixture `F-FLOOD` — A repeated message collapses with a count
**Serves.** `SYS-0024`
**Steps.** Run to completion; count entries for the repeating message; check messages issued before it.
- `.c1` **PASS:** one entry carrying a count equal to its occurrences, per `SYS-0024` Accept. **FAIL:** one entry per tick, or a wrong count.
- `.c2` **PASS:** earlier messages remain present. **FAIL:** any was displaced.

**`SYT-PLG-01`** · T · fixture `F-PLUGIN-BAD` — An incomplete identity is refused by name
**Serves.** `SYS-0025`
**Steps.** Load the bundle with one identity field removed; read the refusal.
- `.c1` **PASS:** the plug-in is refused, per `SYS-0025` Accept. **FAIL:** it loads.
- `.c2` **PASS:** the refusal names the missing field. **FAIL:** it is generic.

## 3. Inspection — `INSP`

**`INSP-01`** · I · fixture `F-PLUGIN-BAD` — Identity is shown on all three surfaces
**Serves.** `SYS-0026`
**Steps.** Walk checklist `CL-PLUGIN-IDENTITY`, recording an answer and a screenshot for each of its four rows.
- `.c1` **PASS:** every checklist row answers yes, per `SYS-0026` Accept. **FAIL:** any row answers no, or is unanswered.

## 4. Static analysis — `ANL`

**`ANL-01`** · A · fixture `F-SRC` — Live control has no second implementation
**Serves.** `SYS-0014`
**Steps.** Resolve every live control operation to the function it calls; check each against the headless interface's exported set.
- `.c1` **PASS:** every live operation resolves to a function the headless interface already exposes, per `SYS-0014` Accept. **FAIL:** any resolves to a function only the live path has.
- `.c2` **PASS:** the planted violation is reported — a copy of the source with one live-only operation added is flagged. **FAIL:** the check passes it, which means it is blind.
