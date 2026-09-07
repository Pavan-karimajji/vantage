# PARITY — Implementation Design

**One document, not two.** The build order is on top; the design rows are
below. `R-REQ`'s layer table says `IMP-nnnn` → `WP-nn` and nothing about how
many files that takes — the split was inherited from `sim`'s v2 set, where 379
rows genuinely need their own file. At 54 rows one document is 200 lines, and
keeping the order and the detail apart would mean two files to hold in
agreement for no reader's benefit.

**A package row says only what it alone knows** — the checkbox, the headline,
and why it sits where it does in the order. **What it lands is not written
there**: that mapping is the `WP` column of the table below, one place, beside
the artifact it describes, so a package and a row cannot disagree about what
belongs to it. `--status` derives the contents.

**The design rows' boxes are the only hand-maintained progress state in this
set** (`R-REQ-6a`). **The row is the atom, not the package**: a design row is
one buildable artifact — one file, one symbol — whereas a package is a bag of
them, so a package-level box can only ever say *some of this happened*. The
`Box` column of the table below is what a person types; **a package's own box is
recomputed from the rows it lands** and the checker fails on disagreement
(`C-WPROLL`) — all rows `[x]` → `[x]`, all `[ ]` → `[ ]`, anything between →
`[~]`. No requirement document carries a progress mark. Three states, and no
others:

| Box | Means |
|---|---|
| `[ ]` | not started |
| `[~]` | started — **and the row must say `closed by <command or condition>`** |
| `[x]` | done — the tests the requirements name pass |

A bare `[~]` is a finding — `C-ROWMARK` on a design row, `C-PLANMARK` on a
package — and a design row carrying no box at all is `C-ROWBOX`. Its whole value
is telling the next session where to resume.

**Progress is not verification** (`R-REQ-6`). A ticked box says the work was
done; whether the requirement is met is a Test Execution Record's answer, one
per campaign, and none exists yet.

---

## Prerequisite, owned elsewhere

**The `Source`/`Feed` interface — register item `C-16`, allocated to
`modules/viz`.** It is unwritten, and every transport control is a call on it.
If it ships offering message granularity only, the fifth step kind in `WP-09`
becomes impossible to add later without changing the interface.

**Blocks `WP-08` and `WP-09`, and nothing else.** Eleven of the thirteen
packages are independent of it, so it gates breadth rather than progress.

---

## Order, and why

Ingest first: it is the foundation everything reads through, it is contained,
and it is the highest-value thing in the register. The launcher and the
self-describing artifacts follow because they are independent of everything.
The player packages wait on the prerequisite above. The two `R2` packages —
the side-by-side run and live control — are last because nothing depends on
them.

## A. Getting data in

- [x] **WP-01** — Ingest map keyed by port, with an ordered address list · Invert the key, resolve in order, report what matched. `absent:` is untouched.
- [x] **WP-02** — Named sources and per-port binding · Several complete recordings in one run; each port bound to exactly one, with a declared default. Not multi-source merging.

## B. Setting a run up

- [ ] **WP-03** — Launcher: isolate, and the computed mixed state · One action to isolate a stage; a third group state that is computed and has no setter to reach.
- [ ] **WP-04** — Headless reproduction, and the test that proves it · Display the reproducing invocation, and make both paths resolve through one construction. The test matters more than the line.

## C. Saying what things are

- [ ] **WP-05** — Diagnostics: occurrence counting · Collapse an identical repeated message into one entry with a count, and say once when that began.
- [ ] **WP-06** — Plug-in identity · Four mandatory fields, refused by name when incomplete, carried into the deployed copy, read through one accessor.
- [ ] **WP-07** — The bundle travels in the recording · Embed the bytes, store their hash, and make absence a value rather than a reason to look on disk.

## D. Moving through a recording

- [ ] **WP-08** — Transport controls and play speed · The nine named actions, and a rate that is measured rather than requested. **Blocked by the prerequisite.**
- [ ] **WP-09** — Step granularity and cycles · Five kinds of step, cycles discovered from the recording, and a cycle step that lands on a coherent input set. **Blocked by the prerequisite.**
- [ ] **WP-10** — Named ranges · Bounds in the recording's own timebase, travelling with the file, inclusive at both ends.
- [ ] **WP-11** — Marks, in two kinds · Annotation and classification as separate types in separate blocks, each stamped with author and time at creation.

## E. Trusting the answer

- [ ] **WP-12** — Side-by-side reference run · Two builds sharing one resolved input set; the first divergence located; both builds' outputs recorded separably.
- [ ] **WP-13** — Live session control · Read and control a running session from a script, over an operation table built from the headless API's own exports.

---

# The design rows

**A path here is a promise: the code goes at that path under that name.** Every
directory named below exists today, so a `NEW` row names a file that does not
exist yet inside a package that does.

**A symbol marked `new` does not exist yet; every other named symbol does.**
Verified against the code on 2026-09-05, row by row — 14 were corrected, and
three of those pointed at the wrong module entirely. An `EXTEND` row means the
*file* exists and gains something; it does not mean every symbol in it already
does, and saying which is which is the difference between a promise and a
guess.

**What a design row is not.** It is not its `SW` reworded with a filename
attached. The value it adds is exactly one of: *where the code goes*, *what the
symbol is called*, *what its signature is*, or *what has to be deleted first*.

**One row per software requirement, as a table** (`layers.yaml`,
`row_style: table`). Seven columns, fixed and positional, because the value of a
design is that every row answers the same questions. The first is `Box` — the
one hand-typed progress state in the set (`R-REQ-6a`, above).

**`Change` is derived from what exists today, never asserted.** A row claiming
`NEW` for code already present is a design error a reviewer can see without
opening the file. The vocabulary is closed and checked by `C-CHANGE`:

| Class | Means |
|---|---|
| `KEEP` | Code exists at the right path; its body is not touched |
| `MOVE` | Code exists and is reusable; the file moves |
| `DEDUPE` | Two implementations; one survives, one is deleted |
| `EXTEND` | Code exists and is narrower than the requirement; logic is added, not rewritten |
| `NEW` | Nothing exists |
| `DROP` | The behaviour leaves the product |

**This layer declares no tests of its own** (`layers.yaml`, `tests: []`). It is
verified by the tests of the `SW` it serves — repeated in the last column so a
row is self-contained — plus the build gates. Giving it separate test ids would
create a second, weaker copy of the same checks.

**Length is expected here** (`R-REQ-14`). What is capped in an implementation
document is execution narration, not design. The test is tense: a row below
says what *will* be true of the code. A row in the past tense is in the wrong
document.

---

| Box | UID | Serves | WP | Change | Artifact · Design | Tests |
|---|---|---|---|---|---|---|
| `[x]` | `IMP-0001` | `SW-0001` | `WP-01` | `EXTEND` | `ingest/map.py::_parse_ingest_map` + `_ALLOWED_PROVIDES_KEYS` — the `provides:` mapping is keyed by port and its value becomes a `from:` sequence. The topic-keyed form is rejected rather than accepted for compatibility, so the two shapes cannot coexist in one file. | `UT-mapschema-01` |
| `[x]` | `IMP-0002` | `SW-0002` | `WP-01` | `EXTEND` | `ingest/map.py::_parse_ingest_map` — **one new raise site** carrying the port and the offending key, beside the existing `_require_reason_keys`, so no caller composes its own message. | `UT-mapschema-02` |
| `[x]` | `IMP-0003` | `SW-0003` | `WP-01` | `KEEP` | `ingest/map.py`'s existing `absent:` block is untouched. Only its validation gains one rule: an absent entry carrying a `from:` list is rejected. | `UT-mapschema-03` |
| `[x]` | `IMP-0004` | `SW-0004` | `WP-01` | `NEW` | `ingest/resolve.py::resolve_port(port, candidates, index) -> Resolution` — a pure function over the recording's topic index, so ordering is testable without opening a file. | `UT-resolver-01` |
| `[x]` | `IMP-0005` | `SW-0005` | `WP-01` | `NEW` | `ingest/resolve.py::Resolution` carries `chosen: str | None`. Resolution returns one per port; nothing downstream re-derives it. | `UT-resolver-02` |
| `[x]` | `IMP-0006` | `SW-0006` | `WP-01` | `NEW` | `ingest/resolve.py::resolve_port` compares the candidate's `proto_type` against the port's before accepting it, and continues on mismatch. No conversion path exists to reach. | `UT-resolver-03` |
| `[x]` | `IMP-0007` | `SW-0007` | `WP-01` | `NEW` | `ingest/resolve.py::Unresolved` and `Absent` are distinct types, not two spellings of `None`, so a caller cannot conflate them by accident. | `UT-resolver-04` |
| `[x]` | `IMP-0008` | `SW-0008` | `WP-02` | `NEW` | `runspec/sources.py::SourceSet` — a name-to-recording mapping validating exactly one `default: true` at construction. | `UT-sourceset-01` |
| `[x]` | `IMP-0009` | `SW-0009` | `WP-02` | `NEW` | `runspec/sources.py::SourceSet.for_port(port) -> str` returns one name, always. There is no multi-source return type to misuse. | `UT-sourceset-02` |
| `[x]` | `IMP-0010` | `SW-0010` | `WP-02` | `NEW` | `runspec/sources.py::UnknownSource` raised from `for_port` during spec assembly, before `graph/build.py` opens anything. | `UT-sourceset-03` |
| `[x]` | `IMP-0011` | `SW-0054` | `WP-02` | `NEW` | `runspec/sources.py::SourceSet.for_port` consults the explicit assignment map first, the default second. Two lookups, in that order. | `UT-sourceset-04` |
| `[ ]` | `IMP-0012` | `SW-0011` | `WP-04` | `EXTEND` | `runspec/canon.py` gains source and per-port assignment canonicalisation, so assembly order cannot reach the emitted bytes. | `UT-specasm-01` |
| `[ ]` | `IMP-0013` | `SW-0012` | `WP-04` | `KEEP` | `runspec/canon.py::canonical` + `compute_spec_sha` already give a stable serialisation and its hash; both are taken unchanged. The new fields ride the existing path. | `UT-specasm-02` |
| `[ ]` | `IMP-0014` | `SW-0013` | `WP-12` | `EXTEND` | `runspec/emit.py::emit_run_spec` refuses when `reference:` is configured without a staged identity, alongside its existing `unresolved()` refusal. | `UT-specasm-03` |
| `[x]` | `IMP-0015` | `SW-0014` | `WP-01` | `EXTEND` | `runspec/manifest.py` gains `ports[].matched_address`, filled from `Resolution.chosen` and left null when unresolved. | `UT-manifest-01` |
| `[ ]` | `IMP-0016` | `SW-0015` | `WP-07` | `EXTEND` | `runspec/manifest.py` gains `config_bundle_embedded_sha256` beside the existing `config_bundle_sha256`. Two fields, because one cannot show a mismatch. | `UT-manifest-02` |
| `[ ]` | `IMP-0017` | `SW-0016` | `WP-12` | `EXTEND` | `runspec/manifest.py` gains `reference_build_sha256`, absent rather than empty for an ordinary run. | `UT-manifest-03` |
| `[ ]` | `IMP-0018` | `SW-0017` | `WP-03` | `EXTEND` | `launcher/model.py::Selection.isolate(stage)` — **new method** on the existing `Selection`, mutating only the mode field of every stage. | `UT-selmodel-01` |
| `[ ]` | `IMP-0019` | `SW-0018` | `WP-03` | `EXTEND` | `launcher/model.py` — a **new** read-only `group_state` property over a group's members. No setter is defined, so the third state is unreachable by assignment. | `UT-selmodel-02` |
| `[ ]` | `IMP-0020` | `SW-0019` | `WP-04` | `EXTEND` | `launcher/model.py::Selection` gains a **new** `from_spec`, made the only construction path; the interactive path builds a spec via `write.py::to_run_config` and reads it back. | `UT-selmodel-03` |
| `[ ]` | `IMP-0021` | `SW-0020` | `WP-03` | `EXTEND` | `launcher/model.py`'s view binding renders the computed group state disabled. The control has no enabled variant for that value. | `UT-selview-01` |
| `[ ]` | `IMP-0022` | `SW-0021` | `WP-04` | `EXTEND` | `launcher/write.py` — a **new** `reproduce_line(model)` beside `to_run_config`, rendering from the model and returning one line. No display string is read back to build it. | `UT-selview-02` |
| `[ ]` | `IMP-0023` | `SW-0022` | `WP-08` | `NEW` | `viz/cpp/viz/player/transport.hpp::Transport` — one enum of actions and one `Apply(Action, Position)`, so an action cannot exist without a transform. | `UT-transport-01` |
| `[ ]` | `IMP-0024` | `SW-0023` | `WP-08` | `NEW` | `viz/cpp/viz/player/transport.cpp` serves a backward move from `SceneHistory` only; it holds no handle on which to call the software under test. | `UT-transport-02` |
| `[ ]` | `IMP-0025` | `SW-0024` | `WP-08` | `NEW` | `viz/cpp/viz/player/transport.hpp::kStepPresets` plus a custom slot. `Apply` takes the resolved count, never a free integer from the UI. | `UT-transport-03` |
| `[ ]` | `IMP-0026` | `SW-0025` | `WP-08` | `NEW` | `viz/cpp/viz/player/transport.cpp::AchievedRate` divides executed ticks by elapsed time from the injected clock. The requested value is not an input to it. | `UT-transport-04` |
| `[ ]` | `IMP-0027` | `SW-0026` | `WP-08` | `NEW` | `viz/cpp/viz/player/transport.hpp::PlaybackRate` holds `requested` and `achieved` as separate members, so no accessor can return one for the other. | `UT-transport-05` |
| `[ ]` | `IMP-0028` | `SW-0027` | `WP-09` | `NEW` | `viz/cpp/viz/player/stepping.hpp::Granularity` — a scoped enum of five, with no open integer variant. | `UT-stepping-01` |
| `[ ]` | `IMP-0029` | `SW-0028` | `WP-09` | `NEW` | `viz/cpp/viz/player/stepping.cpp::NextCycleBoundary` reads the cycle index rather than the message stream, so a boundary is found without scanning. | `UT-stepping-02` |
| `[ ]` | `IMP-0030` | `SW-0029` | `WP-09` | `NEW` | `viz/cpp/viz/player/stepping.cpp::Select` validates against the loaded recording's cycle set and returns the prior selection on refusal. | `UT-stepping-03` |
| `[ ]` | `IMP-0031` | `SW-0030` | `WP-09` | `NEW` | `io/cycles.py::discover(reader) -> list[Cycle]` takes only a reader. No configuration parameter exists to pass it. | `UT-cycles-01` |
| `[ ]` | `IMP-0032` | `SW-0031` | `WP-09` | `NEW` | `io/cycles.py::Cycle` carries `name`, `index` and `period_ns` as an integer, matching the two-clock discipline the recording model already uses. | `UT-cycles-02` |
| `[ ]` | `IMP-0033` | `SW-0032` | `WP-09` | `NEW` | `io/cycles.py::run_of(topic, log_time_ns) -> int` numbers each run of a cycle, so attribution is a lookup rather than a reconstruction. | `UT-cycles-03` |
| `[ ]` | `IMP-0034` | `SW-0033` | `WP-10` | `NEW` | `io/ranges.py::Range` stores `start_ns`/`end_ns` in the recording's timebase. No wall-clock field is defined to be tempted by. | `UT-ranges-01` |
| `[ ]` | `IMP-0035` | `SW-0034` | `WP-10` | `NEW` | `io/ranges.py::read`/`write` use the recording's existing meta-block mechanism, so ranges travel with the file rather than beside it. | `UT-ranges-02` |
| `[ ]` | `IMP-0036` | `SW-0035` | `WP-10` | `NEW` | `io/ranges.py::contains(tick_ns)` is inclusive at both bounds, stated here because the boundary case is the one that gets decided by accident. | `UT-ranges-03` |
| `[ ]` | `IMP-0037` | `SW-0036` | `WP-11` | `NEW` | `io/marks.py::Annotation` and `Classification` are separate dataclasses in separate meta blocks. Neither accepts the other's fields. | `UT-marks-01` |
| `[ ]` | `IMP-0038` | `SW-0037` | `WP-11` | `NEW` | `io/marks.py::_stamp` fills `author` and `created_ns` at construction from the session identity, never from file metadata at read time. | `UT-marks-02` |
| `[ ]` | `IMP-0039` | `SW-0038` | `WP-11` | `NEW` | `io/marks.py::select(recordings, classification)` filters on the stored value only, with no fuzzy or prefix matching to explain later. | `UT-marks-03` |
| `[ ]` | `IMP-0040` | `SW-0039` | `WP-05` | `EXTEND` | `diagnostics/logging.py` — a **new** `_dedupe_key` over the closed vocabulary's fields (`_WARN_EVENTS`/`_ERROR_EVENTS`), so a key cannot silently ignore a field added later. | `UT-diaglog-01` |
| `[ ]` | `IMP-0041` | `SW-0040` | `WP-05` | `EXTEND` | `diagnostics/logging.py` — a **new** entry record with an `occurrences` count, accumulated per key by `log()` and emitted once at flush rather than per occurrence. | `UT-diaglog-02` |
| `[ ]` | `IMP-0042` | `SW-0041` | `WP-05` | `EXTEND` | `diagnostics/logging.py` — a **new** `FLOOD_THRESHOLD` and one `dedup_started` event added to the declared vocabulary, emitted once per key. | `UT-diaglog-03` |
| `[ ]` | `IMP-0043` | `SW-0042` | `WP-06` | `EXTEND` | `resolve/plugins.py::PluginBundle` gains `description`, `version`, `author` and `projects`, required in `_from_yaml` rather than defaulted. **Not `plugins/registry.py`** — that is the codec registry. | `UT-plugmeta-01` |
| `[ ]` | `IMP-0044` | `SW-0043` | `WP-06` | `EXTEND` | `resolve/plugins.py` — a **new** `MissingIdentityField` naming the absent field, raised from `_read_plugin_yaml`'s single validation site. | `UT-plugmeta-02` |
| `[ ]` | `IMP-0045` | `SW-0044` | `WP-06` | `EXTEND` | `interfaces/scripts/pack_plugin_bundle.py` copies the four fields into the deployed `plugin.yaml` beside the existing `sha256:` stamp, unchanged. | `UT-plugmeta-03` |
| `[ ]` | `IMP-0046` | `SW-0053` | `WP-06` | `EXTEND` | `resolve/plugins.py::PluginBundle` gains a **new** `identity()`, the single accessor the listing, the inspection view and the refusal message all call. | `UT-plugmeta-04` |
| `[ ]` | `IMP-0047` | `SW-0045` | `WP-07` | `EXTEND` | `config/bundle.py` — a **new** `embed(writer, bundle_dir)` beside `may_enter_bundle`, writing the packed bytes into a recording meta block, reusing the mechanism the manifest already uses. | `UT-bundle-01` |
| `[ ]` | `IMP-0048` | `SW-0046` | `WP-07` | `EXTEND` | `config/bundle.py` — `embed` stores the digest it computed; a **new** `read` recomputes and compares, returning a mismatch rather than raising. | `UT-bundle-02` |
| `[ ]` | `IMP-0049` | `SW-0047` | `WP-07` | `NEW` | `config/bundle.py::BundleAbsent` is a returned value, not an exception and not `None`, so no caller can treat it as a path to fall back from. | `UT-bundle-03` |
| `[ ]` | `IMP-0050` | `SW-0048` | `WP-12` | `NEW` | `engine/refrun.py::RefRun.tick` resolves inputs once and passes the same objects to both libraries, so equality is structural rather than checked. | `UT-refrun-01` |
| `[ ]` | `IMP-0051` | `SW-0049` | `WP-12` | `NEW` | `engine/refrun.py::first_divergence` walks ports in manifest order and returns on the first difference, carrying tick, port and field. | `UT-refrun-02` |
| `[ ]` | `IMP-0052` | `SW-0050` | `WP-12` | `NEW` | `engine/refrun.py` records each build under a topic prefix derived from its role, so the two are separable without a side-car index. | `UT-refrun-03` |
| `[ ]` | `IMP-0053` | `SW-0051` | `WP-13` | `NEW` | `pyapi/live.py::LiveSession` over a local socket, attachable while a run is in progress and requiring no display. | `UT-livectl-01` |
| `[ ]` | `IMP-0054` | `SW-0052` | `WP-13` | `NEW` | `pyapi/live.py` builds its operation table from the headless API's exported names, so an operation with no headless twin cannot be registered. | `UT-livectl-02` |

---

## Not in this plan

**The five `AMEND` register items land in the v2 set, not here** — one clause
each on a requirement that already exists (`C-03`, `C-04`, `C-17`, `C-20`,
`C-28`). Tracking them as work packages here would make this plan the second
place their obligation lives, which is the thing `R-REQ-1` forbids. They are
Stage 7's handoff.

**The two `ALLOCATE` items land in `modules/viz`** (`C-16`, `C-18`), and the
first of them is this plan's prerequisite.

**The two `PARK` items have triggers, not schedules** (`C-05`, `C-07`). A
parked item with a date is a plan; a parked item with a trigger is a decision.