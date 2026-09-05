# PARITY — Software Requirements

**Layer:** `SW`. **Parent layer:** `SYS`.
**Reader:** a developer holding one software item, with its collaborators
stubbed.

**`Item.` is mandatory** (`layers.yaml`, `requires_item: true`). Every row names
one of the 17 declared software items; a name invented here is a finding.

**This layer says what an item must do, never where its code lives.** File
paths and symbol names are the implementation design's, not this document's. A
row that reads like its `SYS` parent with an item name attached has added
nothing.

## Anatomy

```
**`SW-nnnn`** · priority · release — headline
**Shall.**  one obligation, internal to one item
**Accept.** the falsifiable observation, checkable with collaborators stubbed
**Item.**   declared software item
**Verify.** method · test-id   **Trace.** parent SYS UIDs
```

---

## 1. Ingest — schema and parsing

**`SW-0001`** · `P0` · `R1` — The schema keys an entry by port and takes an ordered list
**Shall.** The `mapschema` item shall accept an entry keyed by port name whose value carries an ordered sequence of recorded addresses.
**Accept.** A document with one port and two ordered addresses parses; the same document keyed by topic is rejected.
**Item.** `mapschema`
**Verify.** T · `UT-mapschema-01`   **Trace.** `SYS-0001`

**`SW-0002`** · `P0` · `R1` — A malformed entry is rejected by name
**Shall.** The `mapschema` item shall reject an entry it cannot parse, naming the port and the field at fault.
**Accept.** An entry with an unknown key is rejected, and the message contains both the port name and that key.
**Item.** `mapschema`
**Verify.** T · `UT-mapschema-02`   **Trace.** `SYS-0001`

**`SW-0003`** · `P0` · `R1` — A declared hole parses alongside the provided ports
**Shall.** The `mapschema` item shall parse declared-absent ports in the same document as provided ports, and shall reject an absent entry that carries addresses.
**Accept.** A document with both kinds parses; an absent entry carrying an address is rejected.
**Item.** `mapschema`
**Verify.** T · `UT-mapschema-03`   **Trace.** `SYS-0034`

## 2. Ingest — resolution

**`SW-0004`** · `P0` · `R1` — Candidates are tried in declared order
**Shall.** The `resolver` item shall try a port's candidate addresses in the order declared and stop at the first present in the recording.
**Accept.** With both candidates present, the first is chosen; with only the second present, the second is chosen.
**Item.** `resolver`
**Verify.** T · `UT-resolver-01`   **Trace.** `SYS-0001`

**`SW-0005`** · `P0` · `R1` — The chosen candidate is retained per port
**Shall.** The `resolver` item shall retain, per port, which candidate it chose.
**Accept.** After resolution, each resolved port reports exactly one chosen address and each unresolved port reports none.
**Item.** `resolver`
**Verify.** T · `UT-resolver-02`   **Trace.** `SYS-0002`

**`SW-0006`** · `P0` · `R1` — A type mismatch skips the candidate, never coerces it
**Shall.** The `resolver` item shall skip a candidate whose payload type differs from the port's declared type, and shall continue with the next.
**Accept.** With a mismatched first candidate and a matching second, the second is chosen and no value is converted.
**Item.** `resolver`
**Verify.** T · `UT-resolver-03`   **Trace.** `SYS-0001`

**`SW-0007`** · `P0` · `R1` — Exhausted candidates yield unresolved, not absent
**Shall.** The `resolver` item shall return an unresolved result when no candidate is present, distinct in type from a declared-absent result.
**Accept.** The two results are distinguishable without inspecting text, and neither is an empty success.
**Item.** `resolver`
**Verify.** T · `UT-resolver-04`   **Trace.** `SYS-0034`

## 3. Named sources

**`SW-0008`** · `P0` · `R1` — Sources are a named set with one default
**Shall.** The `sourceset` item shall hold recordings under declared names with exactly one marked default.
**Accept.** A set with two names and one default is accepted; a set with none or two defaults is rejected.
**Item.** `sourceset`
**Verify.** T · `UT-sourceset-01`   **Trace.** `SYS-0003`

**`SW-0009`** · `P0` · `R1` — A port resolves to exactly one source
**Shall.** The `sourceset` item shall resolve every port to exactly one source, using the default where no assignment exists.
**Accept.** Every port in a run yields one source name, and no port yields two.
**Item.** `sourceset`
**Verify.** T · `UT-sourceset-02`   **Trace.** `SYS-0005`

**`SW-0010`** · `P0` · `R1` — An unknown source name raises at load
**Shall.** The `sourceset` item shall raise when a port is assigned to a name it does not hold, naming the port and the name.
**Accept.** The raise happens during resolution, before any recording is read, and its message contains both names.
**Item.** `sourceset`
**Verify.** T · `UT-sourceset-03`   **Trace.** `SYS-0030`

**`SW-0054`** · `P0` · `R1` — An explicit assignment overrides the default
**Shall.** The `sourceset` item shall prefer an explicit per-port assignment over the default.
**Accept.** With a default declared and one port assigned elsewhere, that port resolves to its assignment and its neighbours to the default.
**Item.** `sourceset`
**Verify.** T · `UT-sourceset-04`   **Trace.** `SYS-0029`

## 4. Run spec and manifest

**`SW-0011`** · `P1` · `R1` — Assembly is independent of input order
**Shall.** The `specasm` item shall produce the same resolved spec regardless of the order in which selections were made.
**Accept.** Two assemblies from the same selections applied in different orders are equal.
**Item.** `specasm`
**Verify.** T · `UT-specasm-01`   **Trace.** `SYS-0012`

**`SW-0012`** · `P1` · `R1` — The spec hash is stable and sensitive
**Shall.** The `specasm` item's hash shall be unchanged by re-emission and changed by any field change.
**Accept.** Re-emitting an unmodified spec yields the same hash; altering any one field yields a different one.
**Item.** `specasm`
**Verify.** T · `UT-specasm-02`   **Trace.** `SYS-0012`

**`SW-0013`** · `P2` · `R2` — The spec carries the reference build identity
**Shall.** The `specasm` item shall record the reference build's identity when a side-by-side run is configured, and refuse to assemble when it is missing.
**Accept.** A configured side-by-side spec carries the identity; one with no staged reference fails assembly.
**Item.** `specasm`
**Verify.** T · `UT-specasm-03`   **Trace.** `SYS-0008`

**`SW-0014`** · `P0` · `R1` — The manifest records each port's chosen address
**Shall.** The `manifest` item shall write, per port, the address the resolver chose.
**Accept.** Every resolved port appears once with its chosen address, and unresolved ports appear with none.
**Item.** `manifest`
**Verify.** T · `UT-manifest-01`   **Trace.** `SYS-0002`

**`SW-0015`** · `P1` · `R1` — The manifest records both bundle hashes
**Shall.** The `manifest` item shall write the configuration bundle's hash as packed, and the hash of the bytes embedded in the recording.
**Accept.** Both fields are present and equal for an unmodified bundle.
**Item.** `manifest`
**Verify.** T · `UT-manifest-02`   **Trace.** `SYS-0037`

**`SW-0016`** · `P2` · `R2` — The manifest records the reference build hash
**Shall.** The `manifest` item shall write the reference build's hash for a side-by-side run.
**Accept.** The field is present and matches the staged reference; it is absent for an ordinary run.
**Item.** `manifest`
**Verify.** T · `UT-manifest-03`   **Trace.** `SYS-0008`

## 5. Launcher

**`SW-0017`** · `P1` · `R1` — Isolate is one operation on the model
**Shall.** The `selmodel` item shall provide one operation setting a chosen stage to execute and every other to replay.
**Accept.** After the operation, the chosen stage reads execute, all others replay, and no other model field changed.
**Item.** `selmodel`
**Verify.** T · `UT-selmodel-01`   **Trace.** `SYS-0009`

**`SW-0018`** · `P1` · `R1` — A group's state is computed and has no setter
**Shall.** The `selmodel` item shall derive a group's state from its members and shall expose no way to assign it.
**Accept.** The group state changes only when a member changes, and no assignment path to it exists.
**Item.** `selmodel`
**Verify.** T · `UT-selmodel-02`   **Trace.** `SYS-0010`

**`SW-0019`** · `P1` · `R1` — File and memory yield the same model
**Shall.** The `selmodel` item shall produce an identical model whether built from a written spec or from the in-memory selection.
**Accept.** For every selection the model can express, the two constructions compare equal.
**Item.** `selmodel`
**Verify.** T · `UT-selmodel-03`   **Trace.** `SYS-0012`

**`SW-0020`** · `P1` · `R1` — A computed group state renders unselectable
**Shall.** The `selview` item shall render a computed group state as present and not choosable.
**Accept.** The control shows the state and rejects input directed at it.
**Item.** `selview`
**Verify.** D · `UT-selview-01`   **Trace.** `SYS-0010`

**`SW-0021`** · `P1` · `R1` — The invocation is rendered from the model
**Shall.** The `selview` item shall render the reproducing invocation from the model rather than composing it from displayed text.
**Accept.** Changing any model field changes the rendered invocation; changing only a label does not.
**Item.** `selview`
**Verify.** T · `UT-selview-02`   **Trace.** `SYS-0011`

## 6. Transport

**`SW-0022`** · `P0` · `R1` — Each action is one position transform
**Shall.** The `transport` item shall map each named action to exactly one transform of the current position.
**Accept.** Every action produces the position its name states from a known starting position.
**Item.** `transport`
**Verify.** T · `UT-transport-01`   **Trace.** `SYS-0015`

**`SW-0023`** · `P0` · `R1` — Backward motion re-executes nothing
**Shall.** The `transport` item shall satisfy a backward move from recorded state, never by executing the software under test.
**Accept.** A backward move issues no execution call, verified against a counting stub.
**Item.** `transport`
**Verify.** T · `UT-transport-02`   **Trace.** `SYS-0015`

**`SW-0024`** · `P1` · `R1` — The step count comes from a declared list or a custom value
**Shall.** The `transport` item shall take its step-N count from a declared preset list or an explicitly supplied value.
**Accept.** Each preset and one custom value advance by exactly that many units; a value from neither source is refused.
**Item.** `transport`
**Verify.** T · `UT-transport-03`   **Trace.** `SYS-0031`

**`SW-0025`** · `P1` · `R1` — Achieved rate is measured, never assumed
**Shall.** The `transport` item shall compute the achieved rate from elapsed ticks and elapsed time.
**Accept.** With a deliberately slowed tick, the computed rate falls; it never returns the requested value unchanged.
**Item.** `transport`
**Verify.** T · `UT-transport-04`   **Trace.** `SYS-0016`

**`SW-0026`** · `P1` · `R1` — Requested and achieved are separate values
**Shall.** The `transport` item shall hold the requested speed and the achieved rate as distinct values.
**Accept.** Reading one never returns the other, and both are available when they differ.
**Item.** `transport`
**Verify.** T · `UT-transport-05`   **Trace.** `SYS-0032`

## 7. Stepping and cycles

**`SW-0027`** · `P0` · `R1` — Granularity is a closed enumeration
**Shall.** The `stepping` item shall represent step granularity as a closed set of five kinds.
**Accept.** All five are constructible and a sixth cannot be expressed.
**Item.** `stepping`
**Verify.** T · `UT-stepping-01`   **Trace.** `SYS-0017`

**`SW-0028`** · `P0` · `R1` — A cycle step advances to the next boundary
**Shall.** The `stepping` item shall advance to the next boundary of the selected cycle, not by one message.
**Accept.** From a position mid-cycle, one step lands on that cycle's next boundary.
**Item.** `stepping`
**Verify.** T · `UT-stepping-02`   **Trace.** `SYS-0019`

**`SW-0029`** · `P1` · `R1` — An unsupported granularity is refused at selection
**Shall.** The `stepping` item shall refuse a granularity the loaded recording cannot support, naming what is missing and retaining the previous selection.
**Accept.** Selecting an absent cycle is refused, names it, and leaves the prior granularity in force.
**Item.** `stepping`
**Verify.** T · `UT-stepping-03`   **Trace.** `SYS-0033`

**`SW-0030`** · `P0` · `R1` — Cycles are discovered, never configured
**Shall.** The `cycles` item shall derive the cycle set from the recording alone.
**Accept.** The set changes with the recording and is unaffected by any configuration input.
**Item.** `cycles`
**Verify.** T · `UT-cycles-01`   **Trace.** `SYS-0018`

**`SW-0031`** · `P1` · `R1` — Each cycle carries name, index and period
**Shall.** The `cycles` item shall expose a name, an index and a period for every discovered cycle.
**Accept.** All three are present for each cycle, and the period is in integer time units.
**Item.** `cycles`
**Verify.** T · `UT-cycles-02`   **Trace.** `SYS-0018`

**`SW-0032`** · `P0` · `R1` — A value is attributable to one cycle run
**Shall.** The `cycles` item shall report, for a value at a tick, which run of its cycle produced it.
**Accept.** Two values from different runs of one cycle report different run identities.
**Item.** `cycles`
**Verify.** T · `UT-cycles-03`   **Trace.** `SYS-0019`

## 8. Ranges and marks

**`SW-0033`** · `P1` · `R2` — Bounds are held in the recording's timebase
**Shall.** The `ranges` item shall store bounds in the recording's own time units.
**Accept.** A stored range's bounds are unchanged by the host clock, the timezone or the reading machine.
**Item.** `ranges`
**Verify.** T · `UT-ranges-01`   **Trace.** `SYS-0039`

**`SW-0034`** · `P1` · `R2` — Ranges round-trip
**Shall.** The `ranges` item shall restore every stored range with its name and bounds unchanged.
**Accept.** A range written and read back compares equal in both fields.
**Item.** `ranges`
**Verify.** T · `UT-ranges-02`   **Trace.** `SYS-0020`

**`SW-0035`** · `P1` · `R2` — Membership drives batch selection
**Shall.** The `ranges` item shall answer whether a tick falls inside any named range.
**Accept.** Ticks inside and outside a range are classified correctly at both boundaries.
**Item.** `ranges`
**Verify.** T · `UT-ranges-03`   **Trace.** `SYS-0021`

**`SW-0036`** · `P1` · `R2` — The two mark kinds are separate types
**Shall.** The `marks` item shall represent annotations and classifications as distinct types with distinct stores.
**Accept.** A query for one kind returns no instance of the other, and neither type accepts the other's fields.
**Item.** `marks`
**Verify.** T · `UT-marks-01`   **Trace.** `SYS-0022`

**`SW-0037`** · `P2` · `R2` — Every mark carries author and creation time
**Shall.** The `marks` item shall record an author and a creation time on every mark, taken at creation.
**Accept.** Both fields are present on every stored mark and are not derived from file metadata.
**Item.** `marks`
**Verify.** T · `UT-marks-02`   **Trace.** `SYS-0040`

**`SW-0038`** · `P1` · `R2` — Classification filters a set
**Shall.** The `marks` item shall select recordings by classification value.
**Accept.** A query returns every recording carrying the value and none that does not.
**Item.** `marks`
**Verify.** T · `UT-marks-03`   **Trace.** `SYS-0023`

## 9. Diagnostics

**`SW-0039`** · `P1` · `R1` — Identical messages share a key
**Shall.** The `diaglog` item shall derive a key under which identical messages collapse.
**Accept.** Two identical messages share a key; two differing in any field do not.
**Item.** `diaglog`
**Verify.** T · `UT-diaglog-01`   **Trace.** `SYS-0024`

**`SW-0040`** · `P1` · `R1` — Occurrences accumulate per key
**Shall.** The `diaglog` item shall maintain an occurrence count per key and emit one entry carrying it.
**Accept.** A message issued N times yields one entry whose count reads N.
**Item.** `diaglog`
**Verify.** T · `UT-diaglog-02`   **Trace.** `SYS-0024`

**`SW-0041`** · `P1` · `R1` — Crossing the threshold is itself an entry
**Shall.** The `diaglog` item shall emit one entry when a key first crosses the declared flood threshold, naming the message and the threshold.
**Accept.** A run crossing the threshold produces exactly one such entry; a run below it produces none.
**Item.** `diaglog`
**Verify.** T · `UT-diaglog-03`   **Trace.** `SYS-0035`

## 10. Plug-in identity

**`SW-0042`** · `P1` · `R1` — Four fields are required at parse
**Shall.** The `plugmeta` item shall require a description, a version, an author and a supported-project list.
**Accept.** A declaration carrying all four parses; one missing any of them does not.
**Item.** `plugmeta`
**Verify.** T · `UT-plugmeta-01`   **Trace.** `SYS-0025`

**`SW-0043`** · `P1` · `R1` — A refusal names the missing field
**Shall.** The `plugmeta` item's refusal shall name the field that was absent.
**Accept.** Removing each field in turn produces a refusal naming that field and no other.
**Item.** `plugmeta`
**Verify.** T · `UT-plugmeta-02`   **Trace.** `SYS-0025`

**`SW-0044`** · `P1` · `R1` — Identity is copied unchanged into the deployed bundle
**Shall.** The `plugmeta` item shall carry the four fields into the deployed copy without alteration.
**Accept.** The fields read identically from the authoring declaration and the deployed one.
**Item.** `plugmeta`
**Verify.** T · `UT-plugmeta-03`   **Trace.** `SYS-0036`

**`SW-0053`** · `P1` · `R1` — One accessor serves every display of identity
**Shall.** The `plugmeta` item shall expose the identity through one accessor used by every surface that displays it.
**Accept.** A change to the accessor's output appears in the listing, the inspection view and the refusal message alike.
**Item.** `plugmeta`
**Verify.** T · `UT-plugmeta-04`   **Trace.** `SYS-0026`

## 11. Configuration bundle

**`SW-0045`** · `P1` · `R1` — The bundle's bytes are embedded
**Shall.** The `bundle` item shall write the configuration bundle's bytes into the recording.
**Accept.** The bytes read back from the recording are identical to those packed beside the library.
**Item.** `bundle`
**Verify.** T · `UT-bundle-01`   **Trace.** `SYS-0027`

**`SW-0046`** · `P1` · `R1` — The embedded bytes carry their own hash
**Shall.** The `bundle` item shall compute and store the hash of the bytes it embedded, and report a mismatch on read.
**Accept.** An unmodified recording reads back matching; a recording with altered bytes reports the mismatch.
**Item.** `bundle`
**Verify.** T · `UT-bundle-02`   **Trace.** `SYS-0037`

**`SW-0047`** · `P1` · `R1` — Absence is a value, not a fallback
**Shall.** The `bundle` item shall represent a missing bundle explicitly and shall read no substitute from disk.
**Accept.** Reading a recording with no bundle yields the absent value, and no filesystem path is consulted.
**Item.** `bundle`
**Verify.** T · `UT-bundle-03`   **Trace.** `SYS-0028`

## 12. Side-by-side execution

**`SW-0048`** · `P2` · `R2` — One input set feeds both builds
**Shall.** The `refrun` item shall pass the same input values to both builds on each tick.
**Accept.** Both builds' received values compare equal on every tick, checked against a recording stub.
**Item.** `refrun`
**Verify.** T · `UT-refrun-01`   **Trace.** `SYS-0006`

**`SW-0049`** · `P2` · `R2` — Comparison is field-wise and stops at the first difference
**Shall.** The `refrun` item shall compare outputs field by field and retain the first tick, port and field that differ.
**Accept.** With one injected difference, all three are reported and match the injection.
**Item.** `refrun`
**Verify.** T · `UT-refrun-02`   **Trace.** `SYS-0007`

**`SW-0050`** · `P2` · `R2` — Both builds' outputs are recorded distinguishably
**Shall.** The `refrun` item shall record each build's outputs under a distinguishable identity.
**Accept.** The recording yields both builds' outputs separately, and the comparison recomputes from it alone.
**Item.** `refrun`
**Verify.** T · `UT-refrun-03`   **Trace.** `SYS-0038`

## 13. Live control

**`SW-0051`** · `P2` · `R2` — Control is reachable without the screen
**Shall.** The `livectl` item shall expose its operations over a transport a script can reach while a session runs.
**Accept.** A script with no display attaches to a running session and completes every exposed operation.
**Item.** `livectl`
**Verify.** T · `UT-livectl-01`   **Trace.** `SYS-0013`

**`SW-0052`** · `P2` · `R2` — Every operation delegates to the headless interface
**Shall.** Each `livectl` operation shall delegate to a function the headless interface already exposes.
**Accept.** Every operation resolves to such a function; none has a body of its own beyond transport handling.
**Item.** `livectl`
**Verify.** T · `UT-livectl-02`   **Trace.** `SYS-0014`
