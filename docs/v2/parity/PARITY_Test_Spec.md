# PARITY — Test Specification

**One file, all three layers.** A test's layer comes from its identifier
prefix, declared in `layers.yaml`: `STT`/`E2E` → `STK`, `SYT`/`INSP`/`ANL` →
`SYS`, `UT`/`IT` → `SW`. Three separate documents would be three files to keep
in agreement; the prefix already carries the layer.

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
| `F-MAP-DOC` | An ingest-map document held in memory, edited per case |
| `F-REC-STUB` | A recording stub whose topic set and payload types are set per case |
| `F-EXEC-STUB` | A tick source that counts calls into the software under test |
| `F-STORE` | An in-memory store that can be written, closed and reopened |
| `F-MODEL` | A launcher selection model — three stages in two groups |
| `F-CLOCK` | A controllable clock, so an achieved rate can be forced |

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

**`STT-15`** · T · fixture `F-PLAY` — Playback speed is honoured, and honestly reported
**Serves.** `STK-0015`
**Steps.** Set a sustainable speed and hold it; then set an unsustainable one and read requested against achieved.
- `.c1` **PASS:** the sustainable speed is held, per `STK-0015` Accept. **FAIL:** it drifts with nothing said.
- `.c2` **PASS:** the unbounded mode reports a measured rate. **FAIL:** it echoes the requested value.

**`STT-16`** · T · fixture `F-TWO-GEN` — Every port says what fed it
**Serves.** `STK-0016`
**Steps.** Run; read the per-port report; compare against the recording's actual topic set.
- `.c1` **PASS:** each fed port names the one address that supplied it, per `STK-0016` Accept. **FAIL:** any names none, or more than one.
- `.c2` **PASS:** an unfed port names no address. **FAIL:** it names one.

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

**`SYT-ING-05`** · T · fixture `F-SPLIT` — An assigned port leaves its neighbours on the default
**Serves.** `SYS-0029`
**Steps.** Assign one port to the second source; run; trace every port's bytes to a source.
- `.c1` **PASS:** the assigned port reads from its assignment and its neighbours from the default, per `SYS-0029` Accept. **FAIL:** any neighbour follows the assignment.

**`SYT-ING-06`** · T · fixture `F-SPLIT` — An unknown source name refuses the run
**Serves.** `SYS-0030`
**Steps.** Assign a port to a source the run does not declare; start the run.
- `.c1` **PASS:** the run refuses at load and names both the port and the unknown source, per `SYS-0030` Accept. **FAIL:** it starts, or the message names neither.
- `.c2` **PASS:** no tick executed. **FAIL:** any did.

**`SYT-ING-07`** · T · fixture `F-TWO-GEN` — An unresolved port is not a declared hole
**Serves.** `SYS-0034`
**Steps.** Run against a recording carrying neither candidate for one port and a declared-absent entry for another; read both reports.
- `.c1` **PASS:** the two are reported differently, per `SYS-0034` Accept. **FAIL:** they read the same.
- `.c2` **PASS:** neither is silent. **FAIL:** either produces no report at all.

**`SYT-ENG-05`** · T · fixture `F-TWO-BUILD-DIV` — Both builds' outputs reach the recording
**Serves.** `SYS-0038`
**Steps.** Run side by side with `--save`; reopen the recording; recompute the divergence from it alone.
- `.c1` **PASS:** both builds' outputs are present under distinguishable topics, per `SYS-0038` Accept. **FAIL:** only one build's are.
- `.c2` **PASS:** the recomputed divergence matches the live one. **FAIL:** it differs, or cannot be recomputed.

**`SYT-PLY-07`** · D · fixture `F-PLAY` — The step count is chosen and shown
**Serves.** `SYS-0031`
**Steps.** Step with each declared preset and one custom value; screenshot the displayed count each time.
- `.c1` **PASS:** each advances by exactly that many units, per `SYS-0031` Accept. **FAIL:** any advances by a different amount.
- `.c2` **PASS:** the value in force is displayed. **FAIL:** it is not shown anywhere.

**`SYT-PLY-08`** · T · fixture `F-PLAY` — An unsustainable speed is shown as unsustained
**Serves.** `SYS-0032`
**Steps.** Request a speed the machine cannot hold; read both the requested and the achieved value.
- `.c1` **PASS:** the two are displayed distinctly, per `SYS-0032` Accept. **FAIL:** only the requested one is shown.

**`SYT-PLY-09`** · T · fixture `F-CYCLES` — An absent cycle cannot be selected
**Serves.** `SYS-0033`
**Steps.** Select a cycle the recording does not carry; read the refusal and the granularity still in force.
- `.c1` **PASS:** the refusal names that cycle, per `SYS-0033` Accept. **FAIL:** it is generic, or the selection succeeds.
- `.c2` **PASS:** the previous granularity is unchanged. **FAIL:** it was reset.

**`SYT-PLY-10`** · T · fixture `F-RANGES` — A range means the same ticks anywhere
**Serves.** `SYS-0039`
**Steps.** Name a range; reopen the recording under a different timezone and host clock; compare the ticks covered.
- `.c1` **PASS:** the same ticks are covered, per `SYS-0039` Accept. **FAIL:** the covered set shifts.

**`SYT-DIA-02`** · T · fixture `F-FLOOD` — Crossing the threshold is said once
**Serves.** `SYS-0035`
**Steps.** Run once above the flood threshold and once below it; count entries announcing de-duplication.
- `.c1` **PASS:** exactly one such entry above the threshold, naming message and threshold, per `SYS-0035` Accept. **FAIL:** none, or more than one.
- `.c2` **PASS:** none below the threshold. **FAIL:** any.

**`SYT-PLG-02`** · T · fixture `F-PLUGIN-OK` — Identity survives the copy
**Serves.** `SYS-0036`
**Steps.** Read the four fields from the authoring directory and from the deployed copy; compare.
- `.c1` **PASS:** all four read identically, per `SYS-0036` Accept. **FAIL:** any differs or is dropped.

**`SYT-REC-05`** · T · fixture `F-BUNDLE-EMBED` — The embedded bundle proves itself
**Serves.** `SYS-0037`
**Steps.** Read the stored hash and hash the embedded bytes; then alter the bytes and read again.
- `.c1` **PASS:** the two agree for an unmodified recording, per `SYS-0037` Accept. **FAIL:** they differ.
- `.c2` **PASS:** an altered recording reports the mismatch. **FAIL:** it is ignored.

**`SYT-REC-06`** · T · fixture `F-RANGES` — A mark says who and when
**Serves.** `SYS-0040`
**Steps.** Create one mark of each kind; reopen; read author and creation time; then change the file's timestamp and re-read.
- `.c1` **PASS:** both fields are present on every mark and survive reopening, per `SYS-0040` Accept. **FAIL:** either is absent.
- `.c2` **PASS:** neither changes with the file timestamp. **FAIL:** either tracks it, which means it was inferred.

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

## 5. Software verification — `UT`

Every case below runs against one item with its collaborators stubbed. A case
cites its requirement's `Accept` rather than restating it (`R-REQ-4`).

### 5.1 `mapschema`

**`UT-mapschema-01`** · T · fixture `F-MAP-DOC` — Port key with an ordered list parses
**Serves.** `SW-0001`
**Steps.** Parse a document with one port and two ordered addresses; then parse the same content keyed by topic.
- `.c1` **PASS:** the port-keyed document parses with the order preserved, per `SW-0001` Accept. **FAIL:** it is rejected, or the order is lost.
- `.c2` **PASS:** the topic-keyed document is rejected. **FAIL:** it parses.

**`UT-mapschema-02`** · T · fixture `F-MAP-DOC` — A bad field is named
**Serves.** `SW-0002`
**Steps.** Parse an entry carrying an unknown key; read the rejection message.
- `.c1` **PASS:** the message contains the port name and the offending key, per `SW-0002` Accept. **FAIL:** it contains neither, or only one.

**`UT-mapschema-03`** · T · fixture `F-MAP-DOC` — Declared holes coexist with provided ports
**Serves.** `SW-0003`
**Steps.** Parse a document with both kinds; then parse one whose absent entry carries an address.
- `.c1` **PASS:** the mixed document parses, per `SW-0003` Accept. **FAIL:** it is rejected.
- `.c2` **PASS:** the absent-with-address entry is rejected. **FAIL:** it parses.

### 5.2 `resolver`

**`UT-resolver-01`** · T · fixture `F-REC-STUB` — First present candidate wins
**Serves.** `SW-0004`
**Steps.** Resolve with both candidates present, then with only the second present.
- `.c1` **PASS:** the first is chosen when present, per `SW-0004` Accept. **FAIL:** the second is.
- `.c2` **PASS:** the second is chosen when the first is absent. **FAIL:** resolution fails.

**`UT-resolver-02`** · T · fixture `F-REC-STUB` — The choice is retained per port
**Serves.** `SW-0005`
**Steps.** Resolve a set of ports, some resolvable and some not; read the retained choices.
- `.c1` **PASS:** each resolved port reports one chosen address, per `SW-0005` Accept. **FAIL:** any reports none or several.
- `.c2` **PASS:** each unresolved port reports none. **FAIL:** any reports one.

**`UT-resolver-03`** · T · fixture `F-REC-STUB` — A type mismatch is skipped, not coerced
**Serves.** `SW-0006`
**Steps.** Resolve with a first candidate of the wrong payload type and a matching second.
- `.c1` **PASS:** the second is chosen, per `SW-0006` Accept. **FAIL:** the first is chosen.
- `.c2` **PASS:** no value is converted. **FAIL:** a conversion occurs.

**`UT-resolver-04`** · T · fixture `F-REC-STUB` — Unresolved and absent are different results
**Serves.** `SW-0007`
**Steps.** Resolve a port with no candidate present and a port the map declares absent; compare the result types.
- `.c1` **PASS:** the two differ in type, per `SW-0007` Accept. **FAIL:** they are the same value.
- `.c2` **PASS:** neither is an empty success. **FAIL:** either reads as resolved.

### 5.3 `sourceset`

**`UT-sourceset-01`** · T · fixture `F-UNIT` — Exactly one default
**Serves.** `SW-0008`
**Steps.** Build sets with one, zero and two defaults.
- `.c1` **PASS:** the one-default set is accepted, per `SW-0008` Accept. **FAIL:** it is rejected.
- `.c2` **PASS:** the zero- and two-default sets are rejected. **FAIL:** either is accepted.

**`UT-sourceset-02`** · T · fixture `F-UNIT` — One source per port
**Serves.** `SW-0009`
**Steps.** Resolve every port of a run and count the sources each yields.
- `.c1` **PASS:** every port yields exactly one, per `SW-0009` Accept. **FAIL:** any yields none or two.

**`UT-sourceset-03`** · T · fixture `F-UNIT` — An unknown name raises before reading
**Serves.** `SW-0010`
**Steps.** Assign a port to an undeclared name; resolve; inspect when the raise occurred and what it said.
- `.c1` **PASS:** the message names the port and the name, per `SW-0010` Accept. **FAIL:** it names neither.
- `.c2` **PASS:** no recording was opened. **FAIL:** one was.

**`UT-sourceset-04`** · T · fixture `F-UNIT` — Assignment beats default
**Serves.** `SW-0054`
**Steps.** Declare a default, assign one port elsewhere, resolve all ports.
- `.c1` **PASS:** the assigned port follows its assignment and the rest the default, per `SW-0054` Accept. **FAIL:** the default wins, or the assignment leaks.

### 5.4 `specasm` and `manifest`

**`UT-specasm-01`** · T · fixture `F-UNIT` — Order of selection does not matter
**Serves.** `SW-0011`
**Steps.** Apply the same selections in two different orders; compare the assembled specs.
- `.c1` **PASS:** the two are equal, per `SW-0011` Accept. **FAIL:** they differ in any field.

**`UT-specasm-02`** · T · fixture `F-UNIT` — The hash is stable and sensitive
**Serves.** `SW-0012`
**Steps.** Hash a spec, re-emit and hash again, then alter one field and hash once more.
- `.c1` **PASS:** re-emission leaves the hash unchanged, per `SW-0012` Accept. **FAIL:** it changes.
- `.c2` **PASS:** altering any field changes it. **FAIL:** any field leaves it unchanged.

**`UT-specasm-03`** · T · fixture `F-UNIT` — A side-by-side spec needs its reference
**Serves.** `SW-0013`
**Steps.** Assemble with a staged reference, then without one.
- `.c1` **PASS:** the identity is carried when staged, per `SW-0013` Accept. **FAIL:** it is absent.
- `.c2` **PASS:** assembly fails with none staged. **FAIL:** it succeeds.

**`UT-manifest-01`** · T · fixture `F-UNIT` — Chosen addresses are written
**Serves.** `SW-0014`
**Steps.** Write a manifest from a resolution containing resolved and unresolved ports; read it back.
- `.c1` **PASS:** every resolved port appears once with its address, per `SW-0014` Accept. **FAIL:** any is missing or duplicated.
- `.c2` **PASS:** unresolved ports appear with none. **FAIL:** any carries an address.

**`UT-manifest-02`** · T · fixture `F-UNIT` — Both bundle hashes are written
**Serves.** `SW-0015`
**Steps.** Write a manifest for an unmodified bundle; read both hash fields.
- `.c1` **PASS:** both are present and equal, per `SW-0015` Accept. **FAIL:** either is absent, or they differ.

**`UT-manifest-03`** · T · fixture `F-UNIT` — The reference hash is written only when there is one
**Serves.** `SW-0016`
**Steps.** Write manifests for a side-by-side run and an ordinary one.
- `.c1` **PASS:** the side-by-side manifest carries the staged reference's hash, per `SW-0016` Accept. **FAIL:** it is absent or wrong.
- `.c2` **PASS:** the ordinary manifest omits the field. **FAIL:** it carries an empty one.

### 5.5 `selmodel` and `selview`

**`UT-selmodel-01`** · T · fixture `F-MODEL` — Isolate touches only the modes
**Serves.** `SW-0017`
**Steps.** Snapshot the model, isolate one stage, snapshot again and diff.
- `.c1` **PASS:** the chosen stage executes and all others replay, per `SW-0017` Accept. **FAIL:** any other executes.
- `.c2` **PASS:** no other field changed. **FAIL:** anything else moved.

**`UT-selmodel-02`** · T · fixture `F-MODEL` — A group state cannot be assigned
**Serves.** `SW-0018`
**Steps.** Change a member and observe the group; then attempt every available way to set the group directly.
- `.c1` **PASS:** the group state follows its members, per `SW-0018` Accept. **FAIL:** it does not update.
- `.c2` **PASS:** no assignment path to it exists. **FAIL:** one does.

**`UT-selmodel-03`** · T · fixture `F-MODEL` — File and memory agree
**Serves.** `SW-0019`
**Steps.** For every selection the model can express, build from memory and from the written spec; compare.
- `.c1` **PASS:** the two compare equal for every selection, per `SW-0019` Accept. **FAIL:** any pair differs.

**`UT-selview-01`** · D · fixture `F-MODEL` — The computed state is visibly not choosable
**Serves.** `SW-0020`
**Steps.** Put a group into disagreement; screenshot; direct input at the computed state.
- `.c1` **PASS:** it is shown and rejects the input, per `SW-0020` Accept. **FAIL:** it accepts input.

**`UT-selview-02`** · T · fixture `F-MODEL` — The invocation comes from the model
**Serves.** `SW-0021`
**Steps.** Change a model field and re-render; then change only a display label and re-render.
- `.c1` **PASS:** the model change alters the invocation, per `SW-0021` Accept. **FAIL:** it does not.
- `.c2` **PASS:** the label change does not. **FAIL:** it does, which means the text was scraped.

### 5.6 `transport`

**`UT-transport-01`** · T · fixture `F-UNIT` — One action, one transform
**Serves.** `SW-0022`
**Steps.** From a known position, apply each named action and read the resulting position.
- `.c1` **PASS:** each produces the position its name states, per `SW-0022` Accept. **FAIL:** any produces another.

**`UT-transport-02`** · T · fixture `F-EXEC-STUB` — Going back executes nothing
**Serves.** `SW-0023`
**Steps.** Move forward, then backward; read the stub's call count across the backward move.
- `.c1` **PASS:** the count is unchanged by the backward move, per `SW-0023` Accept. **FAIL:** it rises.

**`UT-transport-03`** · T · fixture `F-UNIT` — The step count is bounded to its sources
**Serves.** `SW-0024`
**Steps.** Step with each preset, with a supplied custom value, and with a value from neither.
- `.c1` **PASS:** presets and the custom value advance by exactly that many, per `SW-0024` Accept. **FAIL:** any advances differently.
- `.c2` **PASS:** a value from neither source is refused. **FAIL:** it is accepted.

**`UT-transport-04`** · T · fixture `F-CLOCK` — The rate is measured
**Serves.** `SW-0025`
**Steps.** Force a slow tick through the clock; read the computed rate against ticks over elapsed time.
- `.c1` **PASS:** the computed rate falls with the slowed tick, per `SW-0025` Accept. **FAIL:** it is unchanged, which means it was assumed.

**`UT-transport-05`** · T · fixture `F-CLOCK` — Requested and achieved are separate
**Serves.** `SW-0026`
**Steps.** Request a rate the clock cannot sustain; read both values.
- `.c1` **PASS:** the two differ and both are readable, per `SW-0026` Accept. **FAIL:** reading one returns the other.

### 5.7 `stepping` and `cycles`

**`UT-stepping-01`** · T · fixture `F-UNIT` — Five kinds, and no sixth
**Serves.** `SW-0027`
**Steps.** Construct each of the five; attempt to construct a sixth.
- `.c1` **PASS:** all five construct, per `SW-0027` Accept. **FAIL:** any cannot.
- `.c2` **PASS:** a sixth cannot be expressed. **FAIL:** one can.

**`UT-stepping-02`** · T · fixture `F-REC-STUB` — A cycle step lands on the boundary
**Serves.** `SW-0028`
**Steps.** From a mid-cycle position, step by the selected cycle; read the landing position.
- `.c1` **PASS:** it lands on that cycle's next boundary, per `SW-0028` Accept. **FAIL:** it advances by one message.

**`UT-stepping-03`** · T · fixture `F-REC-STUB` — An unsupported granularity is refused
**Serves.** `SW-0029`
**Steps.** Select a cycle absent from the stub; read the refusal and the granularity still in force.
- `.c1` **PASS:** the refusal names the missing cycle, per `SW-0029` Accept. **FAIL:** it is generic.
- `.c2` **PASS:** the previous selection is retained. **FAIL:** it was cleared.

**`UT-cycles-01`** · T · fixture `F-REC-STUB` — Cycles come from the recording
**Serves.** `SW-0030`
**Steps.** Read the cycle set; change the stub's recording; read again; then vary configuration and read once more.
- `.c1` **PASS:** the set follows the recording, per `SW-0030` Accept. **FAIL:** it does not change.
- `.c2` **PASS:** configuration has no effect on it. **FAIL:** it changes.

**`UT-cycles-02`** · T · fixture `F-REC-STUB` — Name, index and period
**Serves.** `SW-0031`
**Steps.** Read all three for every discovered cycle.
- `.c1` **PASS:** all three are present for each, per `SW-0031` Accept. **FAIL:** any is missing.
- `.c2` **PASS:** the period is an integer time unit. **FAIL:** it is a float.

**`UT-cycles-03`** · T · fixture `F-REC-STUB` — A value names its cycle run
**Serves.** `SW-0032`
**Steps.** Read the run identity for two values from different runs of the same cycle.
- `.c1` **PASS:** the identities differ, per `SW-0032` Accept. **FAIL:** they are the same.

### 5.8 `ranges` and `marks`

**`UT-ranges-01`** · T · fixture `F-STORE` — Bounds are in recording time
**Serves.** `SW-0033`
**Steps.** Store a range; change the host clock and timezone; read the bounds.
- `.c1` **PASS:** the bounds are unchanged, per `SW-0033` Accept. **FAIL:** either shifts.

**`UT-ranges-02`** · T · fixture `F-STORE` — Ranges round-trip
**Serves.** `SW-0034`
**Steps.** Write a range, close the store, reopen, read it back.
- `.c1` **PASS:** name and bounds compare equal, per `SW-0034` Accept. **FAIL:** either differs.

**`UT-ranges-03`** · T · fixture `F-UNIT` — Membership is exact at the edges
**Serves.** `SW-0035`
**Steps.** Query membership for ticks inside, outside, and exactly on both bounds.
- `.c1` **PASS:** every tick is classified correctly including both boundaries, per `SW-0035` Accept. **FAIL:** either boundary is misclassified.

**`UT-marks-01`** · T · fixture `F-STORE` — Two kinds, two stores
**Serves.** `SW-0036`
**Steps.** Store one of each; query each kind; attempt to give one the other's fields.
- `.c1` **PASS:** each query returns only its own kind, per `SW-0036` Accept. **FAIL:** either returns the other's.
- `.c2` **PASS:** neither type accepts the other's fields. **FAIL:** either does.

**`UT-marks-02`** · T · fixture `F-STORE` — Author and time are recorded, not inferred
**Serves.** `SW-0037`
**Steps.** Create marks; reopen; read both fields; then alter the file's own timestamp and re-read.
- `.c1` **PASS:** both are present on every mark, per `SW-0037` Accept. **FAIL:** either is absent.
- `.c2` **PASS:** neither follows the file timestamp. **FAIL:** either does.

**`UT-marks-03`** · T · fixture `F-STORE` — Classification selects exactly
**Serves.** `SW-0038`
**Steps.** Query by one classification value against a set with known carriers.
- `.c1` **PASS:** every carrier and no non-carrier is returned, per `SW-0038` Accept. **FAIL:** any missing or extra.

### 5.9 `diaglog`

**`UT-diaglog-01`** · T · fixture `F-UNIT` — The key distinguishes what differs
**Serves.** `SW-0039`
**Steps.** Key two identical messages, then two differing in each field in turn.
- `.c1` **PASS:** identical messages share a key, per `SW-0039` Accept. **FAIL:** they do not.
- `.c2` **PASS:** a difference in any field yields a different key. **FAIL:** any field is ignored.

**`UT-diaglog-02`** · T · fixture `F-UNIT` — The count equals the occurrences
**Serves.** `SW-0040`
**Steps.** Issue one message N times; read the emitted entries and the count.
- `.c1` **PASS:** one entry whose count reads N, per `SW-0040` Accept. **FAIL:** N entries, or a wrong count.

**`UT-diaglog-03`** · T · fixture `F-UNIT` — The crossing is announced once
**Serves.** `SW-0041`
**Steps.** Drive a key across the threshold and count announcements; then stay below it and count again.
- `.c1` **PASS:** exactly one entry naming the message and threshold, per `SW-0041` Accept. **FAIL:** none, or one per occurrence.
- `.c2` **PASS:** none below the threshold. **FAIL:** any.

### 5.10 `plugmeta`

**`UT-plugmeta-01`** · T · fixture `F-UNIT` — Four fields, all required
**Serves.** `SW-0042`
**Steps.** Parse a complete declaration, then one missing each field in turn.
- `.c1` **PASS:** the complete declaration parses, per `SW-0042` Accept. **FAIL:** it is rejected.
- `.c2` **PASS:** each incomplete one is rejected. **FAIL:** any parses.

**`UT-plugmeta-02`** · T · fixture `F-UNIT` — The refusal names the field
**Serves.** `SW-0043`
**Steps.** Remove each field in turn; read each refusal message.
- `.c1` **PASS:** each names the removed field and no other, per `SW-0043` Accept. **FAIL:** any is generic or names the wrong one.

**`UT-plugmeta-03`** · T · fixture `F-UNIT` — The copy is unchanged
**Serves.** `SW-0044`
**Steps.** Read the four fields from the authoring declaration and the deployed copy; compare.
- `.c1` **PASS:** all four are identical, per `SW-0044` Accept. **FAIL:** any is altered or dropped.

**`UT-plugmeta-04`** · T · fixture `F-UNIT` — One accessor feeds every surface
**Serves.** `SW-0053`
**Steps.** Change the accessor's output; read the listing, the inspection view and a refusal message.
- `.c1` **PASS:** the change appears in all three, per `SW-0053` Accept. **FAIL:** any shows the old value, which means a second read path.

### 5.11 `bundle`

**`UT-bundle-01`** · T · fixture `F-STORE` — The bytes go in unchanged
**Serves.** `SW-0045`
**Steps.** Embed a known bundle; read the bytes back; compare with the source.
- `.c1` **PASS:** the bytes are identical, per `SW-0045` Accept. **FAIL:** they differ in any position.

**`UT-bundle-02`** · T · fixture `F-STORE` — The hash catches an alteration
**Serves.** `SW-0046`
**Steps.** Read the stored hash against the embedded bytes; then alter one byte and read again.
- `.c1` **PASS:** unmodified bytes read back matching, per `SW-0046` Accept. **FAIL:** they do not.
- `.c2` **PASS:** the altered recording reports the mismatch. **FAIL:** it is ignored.

**`UT-bundle-03`** · T · fixture `F-STORE` — Absence consults nothing
**Serves.** `SW-0047`
**Steps.** Read a recording with no bundle, with a valid bundle present on disk beside it; watch every filesystem access.
- `.c1` **PASS:** the absent value is returned, per `SW-0047` Accept. **FAIL:** a bundle is returned.
- `.c2` **PASS:** no path was consulted. **FAIL:** any was.

### 5.12 `refrun` and `livectl`

**`UT-refrun-01`** · T · fixture `F-EXEC-STUB` — One input set, two builds
**Serves.** `SW-0048`
**Steps.** Run both builds through the stub; capture what each received per tick; compare.
- `.c1` **PASS:** the received values are equal on every tick, per `SW-0048` Accept. **FAIL:** they differ on any.

**`UT-refrun-02`** · T · fixture `F-EXEC-STUB` — The first difference is kept
**Serves.** `SW-0049`
**Steps.** Inject one known difference; read the retained tick, port and field.
- `.c1` **PASS:** all three match the injection, per `SW-0049` Accept. **FAIL:** any is wrong, or a later difference was kept instead.

**`UT-refrun-03`** · T · fixture `F-STORE` — Both builds' outputs are separable
**Serves.** `SW-0050`
**Steps.** Record a side-by-side run; read both builds' outputs; recompute the comparison from the recording alone.
- `.c1` **PASS:** the two are separable and the comparison recomputes, per `SW-0050` Accept. **FAIL:** they are merged, or the recomputation is impossible.

**`UT-livectl-01`** · T · fixture `F-LIVE` — Reachable without a display
**Serves.** `SW-0051`
**Steps.** Attach from a script with no display; invoke every exposed operation.
- `.c1` **PASS:** every operation completes, per `SW-0051` Accept. **FAIL:** any requires a display.

**`UT-livectl-02`** · T · fixture `F-SRC` — Every operation delegates
**Serves.** `SW-0052`
**Steps.** Resolve each live operation's target by reflection; check membership of the headless interface's exported set.
- `.c1` **PASS:** every target is in that set, per `SW-0052` Accept. **FAIL:** any is not.
- `.c2` **PASS:** no operation carries a body beyond transport handling. **FAIL:** any does.
