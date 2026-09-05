# PARITY — System Requirements

**Layer:** `SYS`. **Parent layer:** `STK`.
**Reader:** anyone using the bench from outside, with no source access.

**`Item.` is mandatory here** (`layers.yaml`, `requires_item: true`). `sim` is
not a component and has no `conf/ports.yaml`, so a row names the declared
**surface** it constrains rather than a port. The purpose is `R-REQ-15`'s: a
requirement that binds to nothing is scope creep.

## Declared tokens

Surfaces come from `layers.yaml`. Test areas are declared here, once, and are
never invented at the point of use.

| Surface | Area | What it is |
|---|---|---|
| `ingest` | `ING` | The ingest map and how a port resolves to recorded data |
| `engine` | `ENG` | The run graph — stages, modes, wiring and scheduling |
| `runspec` | `RUN` | The resolved run spec and the run manifest it writes |
| `launcher` | `LNC` | The pre-run selection face |
| `player` | `PLY` | Vantage's interactive face — transport, panels, layers |
| `diag` | `DIA` | The diagnostic log and how an error is reported |
| `plugin` | `PLG` | Plug-in discovery, identity and loading |
| `record` | `REC` | The recording model, its codecs and its provenance |

## Anatomy

```
**`SYS-nnnn`** · priority · release — headline
**Shall.**  one boundary-observable obligation
**Accept.** the falsifiable observation
**Item.**   declared surface(s)
**Verify.** method · test-id   **Trace.** parent STK UIDs
```

---

## 1. Getting data in

**`SYS-0001`** · `P0` · `R1` — A port names its source addresses in priority order
**Shall.** The ingest map shall key each entry by port and accept an ordered list of recorded addresses for it.
**Accept.** A map listing two addresses for one port resolves against a recording carrying only the second.
**Item.** `ingest`
**Verify.** T · `SYT-ING-01`   **Trace.** `STK-0001`

**`SYS-0002`** · `P0` · `R1` — Report which address fed each port
**Shall.** The run shall report, per port, which of its candidate addresses matched.
**Accept.** The run manifest names one matched address for every port the map resolved, and names none for a port it did not.
**Item.** `ingest`, `runspec`
**Verify.** T · `SYT-ING-02`   **Trace.** `STK-0016`

**`SYS-0003`** · `P0` · `R1` — A run names several recordings and a default among them
**Shall.** A run shall name several recordings and declare which of them a port reads from unless told otherwise.
**Accept.** With two recordings named and a default declared, every port not otherwise assigned reads from the default.
**Item.** `ingest`, `engine`
**Verify.** T · `SYT-ING-03`   **Trace.** `STK-0002`

**`SYS-0029`** · `P0` · `R1` — A port is assigned to a named source individually
**Shall.** A run shall assign an individual port to a named source other than the default.
**Accept.** A port assigned to the second recording reads its bytes from that recording while its neighbours read the default.
**Item.** `ingest`, `engine`
**Verify.** T · `SYT-ING-05`   **Trace.** `STK-0002`

**`SYS-0030`** · `P0` · `R1` — A port assigned to an undeclared source is a load error
**Shall.** A run assigning a port to a source it does not declare shall be refused before execution.
**Accept.** The run refuses at load, names the port and the unknown source, and executes no tick.
**Item.** `ingest`, `runspec`
**Verify.** T · `SYT-ING-06`   **Trace.** `STK-0002`

**`SYS-0034`** · `P0` · `R1` — No candidate matching is reported, and is not a declared hole
**Shall.** A port whose candidate addresses all fail to match shall be reported unresolved, distinctly from one the map declares absent.
**Accept.** The two cases produce different reports, and neither is silent.
**Item.** `ingest`
**Verify.** T · `SYT-ING-07`   **Trace.** `STK-0016`

**`SYS-0005`** · `P0` · `R1` — A port reads exactly one source
**Shall.** Each port shall read from exactly one named source for the whole run.
**Accept.** No run configuration causes a single port's values to originate from more than one recording.
**Item.** `engine`
**Verify.** T · `SYT-ENG-01`   **Trace.** `STK-0002`

## 2. Trusting the answer

**`SYS-0006`** · `P2` · `R2` — Two builds execute on the same tick from the same inputs
**Shall.** The bench shall execute a candidate and a reference build in one process, on each tick, from the same input values.
**Accept.** Both builds receive byte-identical input port values on every tick of the run.
**Item.** `engine`
**Verify.** T · `SYT-ENG-02`   **Trace.** `STK-0003`

**`SYS-0007`** · `P2` · `R2` — Report the first divergence, or none
**Shall.** A side-by-side run shall report either no divergence, or the first tick, port and field at which the two builds differ.
**Accept.** With a deliberately altered reference build, the reported tick, port and field match the injected difference.
**Item.** `engine`
**Verify.** T · `SYT-ENG-03`   **Trace.** `STK-0003`

**`SYS-0008`** · `P2` · `R2` — Reference binaries are a declared artifact
**Shall.** The reference build used by a side-by-side run shall be a declared artifact with a recorded identity.
**Accept.** The run manifest names the reference build's hash, and a run with no staged reference refuses to start.
**Item.** `runspec`
**Verify.** T · `SYT-RUN-01`   **Trace.** `STK-0003`

**`SYS-0038`** · `P2` · `R2` — A side-by-side run records both builds' outputs
**Shall.** A side-by-side run shall record each build's output ports separately.
**Accept.** The resulting recording carries both builds' outputs under distinguishable topics, and the divergence report can be recomputed from it alone.
**Item.** `engine`, `record`
**Verify.** T · `SYT-ENG-05`   **Trace.** `STK-0003`

## 3. Setting a run up

**`SYS-0009`** · `P1` · `R1` — One action isolates a stage
**Shall.** The launcher shall provide one action that sets a chosen stage to execute and every other stage to replay.
**Accept.** After the action, the chosen stage reads execute, every other reads replay, and nothing else in the selection changed.
**Item.** `launcher`
**Verify.** T · `SYT-LNC-01`   **Trace.** `STK-0004`

**`SYS-0010`** · `P1` · `R1` — A disagreeing group shows a computed state
**Shall.** A group control shall show a computed third state when its members disagree, and that state shall not be selectable.
**Accept.** With members in different modes the group reads mixed and is disabled; setting all members alike removes it.
**Item.** `launcher`
**Verify.** D · `SYT-LNC-02`   **Trace.** `STK-0011`

**`SYS-0011`** · `P1` · `R1` — The reproducing invocation is displayed
**Shall.** The launcher shall display the invocation that reproduces its current selection headlessly.
**Accept.** The displayed text names the run spec the launcher writes and is copyable as a single command.
**Item.** `launcher`
**Verify.** D · `SYT-LNC-03`   **Trace.** `STK-0005`

**`SYS-0012`** · `P1` · `R1` — Screen and script resolve to the same run spec
**Shall.** Launching from the written run spec and from the in-memory selection shall produce identical resolved run specs.
**Accept.** The two resolved run specs hash equal for every selection the launcher can express.
**Item.** `runspec`
**Verify.** T · `SYT-RUN-02`   **Trace.** `STK-0005`

**`SYS-0013`** · `P2` · `R2` — A running session accepts commands
**Shall.** A running session shall expose read and control operations to a script without the screen.
**Accept.** A script reads the current position and one property, starts and stops playback, and adds a mark, on a live session.
**Item.** `runspec`, `player`
**Verify.** T · `SYT-RUN-03`   **Trace.** `STK-0012`

**`SYS-0014`** · `P2` · `R2` — Live control is the same engine surface
**Shall.** The live control operations shall be the engine's own, never a second implementation.
**Accept.** Every live operation resolves to a function the headless interface already exposes.
**Item.** `runspec`
**Verify.** A · `ANL-01`   **Trace.** `STK-0012`

## 4. Moving through a recording

**`SYS-0015`** · `P0` · `R1` — The transport actions are all present
**Shall.** The player shall provide jump to start, fast reverse, step back N, step back, pause, step, step forward N, fast forward and jump to end.
**Accept.** Each named action moves the displayed position in the direction and by the amount its name states.
**Item.** `player`
**Verify.** D · `SYT-PLY-01`   **Trace.** `STK-0006`

**`SYS-0031`** · `P1` · `R1` — The N of a step-N action is chosen, not fixed
**Shall.** The player shall offer a declared set of step counts and a custom value for the step-N actions.
**Accept.** Each declared preset and one custom value advance by exactly that many units, and the value in force is displayed.
**Item.** `player`
**Verify.** D · `SYT-PLY-07`   **Trace.** `STK-0006`

**`SYS-0016`** · `P0` · `R1` — Unbounded speed reports what it achieved
**Shall.** The player shall offer a play speed and an unbounded mode that reports the rate achieved.
**Accept.** In unbounded mode the displayed rate is measured from elapsed ticks, never a requested multiplier.
**Item.** `player`
**Verify.** T · `SYT-PLY-02`   **Trace.** `STK-0015`

**`SYS-0032`** · `P1` · `R1` — A requested speed that cannot be held is shown as not held
**Shall.** The player shall report when the achieved rate is below the requested speed.
**Accept.** With a speed the machine cannot sustain, the display distinguishes the requested value from the achieved one.
**Item.** `player`
**Verify.** T · `SYT-PLY-08`   **Trace.** `STK-0015`

**`SYS-0017`** · `P0` · `R1` — Five step granularities, chosen explicitly
**Shall.** The player shall offer stepping by one message, N messages, a fixed time interval, the next message of a chosen source, and the next complete run of a chosen cycle.
**Accept.** Each of the five is selectable and advances the position by the unit it names.
**Item.** `player`
**Verify.** T · `SYT-PLY-03`   **Trace.** `STK-0009`

**`SYS-0033`** · `P1` · `R1` — A granularity the recording cannot support is refused
**Shall.** Selecting a step granularity the loaded recording cannot support shall be refused, naming what is missing.
**Accept.** Choosing a cycle the recording does not carry is refused and names that cycle; the previous granularity stays in force.
**Item.** `player`
**Verify.** T · `SYT-PLY-09`   **Trace.** `STK-0009`

**`SYS-0018`** · `P1` · `R1` — The chosen cycle is identified
**Shall.** The player shall show the selected cycle's name, index and period.
**Accept.** All three are displayed for the selected cycle and change when a different cycle is chosen.
**Item.** `player`
**Verify.** D · `SYT-PLY-04`   **Trace.** `STK-0009`

**`SYS-0019`** · `P0` · `R1` — A cycle step lands on a coherent input set
**Shall.** Stepping by a chosen cycle shall land on a tick where that cycle's inputs all come from one run of it.
**Accept.** After such a step, no input belonging to the chosen cycle carries a value from an earlier run of that cycle.
**Item.** `player`
**Verify.** T · `SYT-PLY-05`   **Trace.** `STK-0009`

**`SYS-0020`** · `P1` · `R2` — Named ranges persist
**Shall.** A named time range shall be stored with the recording and restored when it is reopened.
**Accept.** A range named in one session is present, with the same name and bounds, in the next.
**Item.** `player`, `record`
**Verify.** T · `SYT-PLY-06`   **Trace.** `STK-0008`

**`SYS-0039`** · `P1` · `R2` — A range's bounds are in the recording's own timebase
**Shall.** A named range shall record its bounds in the recording's timebase, never in wall-clock time.
**Accept.** A range reopened on a different machine, in a different timezone, covers the same ticks.
**Item.** `record`
**Verify.** T · `SYT-PLY-10`   **Trace.** `STK-0008`

**`SYS-0021`** · `P1` · `R2` — A batch run honours named ranges
**Shall.** A batch run shall be configurable to play only the named ranges or to ignore them.
**Accept.** With play-only set, ticks outside every named range are not executed; with ignore set, all ticks are.
**Item.** `engine`
**Verify.** T · `SYT-ENG-04`   **Trace.** `STK-0008`

**`SYS-0022`** · `P1` · `R2` — Annotations and classifications are stored apart
**Shall.** Annotations of a moment and classifications of a stretch shall be stored and listed as separate kinds.
**Accept.** Listing one kind returns none of the other, and each carries the fields its own kind defines.
**Item.** `record`
**Verify.** T · `SYT-REC-01`   **Trace.** `STK-0013`

**`SYS-0023`** · `P1` · `R2` — A corpus is selectable by classification
**Shall.** A set of recordings shall be selectable by classification alone.
**Accept.** A query naming one classification returns every recording carrying it and no recording that does not.
**Item.** `record`
**Verify.** T · `SYT-REC-02`   **Trace.** `STK-0013`

**`SYS-0040`** · `P2` · `R2` — A mark records who made it and when
**Shall.** Every annotation and classification shall record its author and the time it was made.
**Accept.** Both fields are present on every stored mark and survive reopening; neither is inferred from file timestamps.
**Item.** `record`
**Verify.** T · `SYT-REC-06`   **Trace.** `STK-0013`

## 5. Understanding what happened

**`SYS-0024`** · `P1` · `R1` — A repeated message collapses to one entry
**Shall.** The diagnostic log shall record identical repeated messages as one entry carrying an occurrence count, above a declared flood threshold.
**Accept.** A message issued on every tick appears once with a count equal to its occurrences, and messages issued earlier remain present.
**Item.** `diag`
**Verify.** T · `SYT-DIA-01`   **Trace.** `STK-0007`

**`SYS-0035`** · `P1` · `R1` — Reaching the flood threshold is itself reported
**Shall.** The log shall record that de-duplication began, naming the message and the threshold reached.
**Accept.** A run crossing the threshold carries one entry saying so; a run below it carries none.
**Item.** `diag`
**Verify.** T · `SYT-DIA-02`   **Trace.** `STK-0007`

**`SYS-0025`** · `P1` · `R1` — Every plug-in declares its identity
**Shall.** Every plug-in shall declare a description, a version, an author and its supported projects.
**Accept.** A plug-in missing any of the four is refused at load, and the refusal names the missing field.
**Item.** `plugin`
**Verify.** T · `SYT-PLG-01`   **Trace.** `STK-0010`

**`SYS-0036`** · `P1` · `R1` — Identity survives into the deployed copy
**Shall.** The declared identity shall be carried unchanged into the copy deployed beside the library.
**Accept.** The four fields read identically from the authoring directory and from the deployed copy.
**Item.** `plugin`
**Verify.** T · `SYT-PLG-02`   **Trace.** `STK-0010`

**`SYS-0026`** · `P1` · `R1` — Identity is shown wherever a plug-in appears
**Shall.** The declared identity shall be shown wherever a plug-in is listed, inspected or refused.
**Accept.** The same four fields appear in the listing, in the inspection view and in a refusal message.
**Item.** `plugin`
**Verify.** I · `INSP-01`   **Trace.** `STK-0010`

**`SYS-0027`** · `P1` · `R1` — A recording carries its configuration bundle
**Shall.** A recording shall embed the bytes of the configuration bundle the run was initialised with.
**Accept.** A recording opened on a machine with no build renders using the bundle it carries, not one found on disk.
**Item.** `record`
**Verify.** T · `SYT-REC-03`   **Trace.** `STK-0014`

**`SYS-0037`** · `P1` · `R1` — The embedded bundle carries the hash it was packed with
**Shall.** A recording embedding a configuration bundle shall also record that bundle's hash.
**Accept.** The recorded hash equals the hash of the embedded bytes, and a mismatch is reported rather than ignored.
**Item.** `record`, `runspec`
**Verify.** T · `SYT-REC-05`   **Trace.** `STK-0014`

**`SYS-0028`** · `P1` · `R1` — A missing bundle is reported, never substituted
**Shall.** A recording carrying no configuration bundle shall be reported as such and shall not be given another.
**Accept.** Opening such a recording states the bundle is absent, and no value is read from a local checkout.
**Item.** `record`
**Verify.** T · `SYT-REC-04`   **Trace.** `STK-0014`

---

## 6. Disposition

`R-REQ-2`: a UID is allocated once and never reused. A retired row moves here
naming its replacement, so a dead link lands on an explanation rather than a
gap.

| UID | Was | Disposition |
|---|---|---|
| `SYS-0004` | Feasible cuts are computed per source | **Retired 2026-09-05, never implemented.** The obligation already exists as `SIM:SYS-0022` — *"feasible cuts are computed, not discovered"* — which is marked done. Writing it again here would be a second copy free to drift. The per-source qualifier this pass needs is a **clause on that row**, tracked as register item `C-28`. |
