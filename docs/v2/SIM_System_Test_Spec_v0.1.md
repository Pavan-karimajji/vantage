# SIM — Replay & Simulation Engine
## System Test Specification — v0.1

**Owner:** SIM Team (tool supplier)
**Derived from:** `SIM_System_Requirements_v0.1.md` (identifiers and acceptance criteria).
**Status:** Draft for review. Not baselined. **§6 carries a defect found while writing this document and must be read before the identifiers below are relied on.**
**Scope:** **Verification only** — *does the system behave as specified at its boundary?* Validation (`CT-*`, `E2E-*`) is `SIM_Concept_Test_Spec_v0.1.md`; the software level (`UT-*`, `IT-*`, `ANL-SW-*`, `INSP-SW-*`) is `SIM_Software_Test_Spec_v0.1.md`.

> **The master is `SIM_Concept_Document_v0.3.1.md`.** Where anything here appears to disagree with it, the concept wins and this document is wrong. Where this appears to disagree with the System Requirements, they win.

---

## 0. How to read this document

### 0.1 Scope, and the one rule that keeps it lean

`SIM_Software_Test_Spec_v0.1.md` §0.1 fixes the discipline this document inherits:

> *Every row gives a **fixture** and **steps**, and its expected value is the `Accept` clause of the requirement it serves, cited rather than paraphrased. A row that reworded an `Accept` clause would create a second copy free to drift from the first.*

That is `CN-0287` at test granularity, and it is why 312 test requirements fit in
one readable document. **The assertion already exists, once, in
`SIM_System_Requirements_v0.1.md`.** If a row here needs different words to say
what it asserts, the requirement is wrong and is edited there — never patched
here.

### 0.2 Levels and identifiers

Every identifier below is **cited by a `Verify` clause in the System
Requirements**; none is invented here. `SYS-0278` requires the identifier to
appear literally inside the test that implements it, so the link is found by
`grep` and not by a sentence in a plan.

| Prefix | Level | Proves | Count |
|---|---|---|---|
| `SYT-<area>-nn` | System | One capability of the assembled system through its external interfaces | 245 |
| `ANL-nn` | Analysis | A measurement or static check over the codebase or artifacts | 55 |
| `INSP-nn` | Inspection | A checklist review where no execution is possible | 12 |

**Areas** — the token is the requirement's own section, never invented at the
point of use:

`INP` input and ingest · `DAT` data model · `PRC` processing and module
lifecycle · `TIM` time and scheduling · `STG` staged simulation · `OUT` output
and artifacts · `PLR` player and visualization · `CFG` launcher and
configuration · `BAT` batch, campaigns and headless · `REC` recording
preparation · `DIA` diagnostics and debugging · `NFR` performance, determinism,
portability, usability · `CON` extensibility, packaging, constraints.

**Counts are emitted by `docs/v2/py/trace_check.py --counts`, not maintained
here.** The three above are stated once, in this table, because a reader needs a
sense of scale before §1; they are the only numbers typed in this document and
the checker contradicts them if they drift.

### 0.3 Test cases and pass criteria

A **test requirement** is the unit specified. A **test case** is the unit that
passes or fails (`R-REQ-5`), identified `<test-id>.cN`.

```
`SYT-INP-16` · serves `SYS-0016` · fixture `S-MAP`
Steps: request a cut needing a declared-absent port
  .c1  PASS refused at load, the declared reason quoted  ·  FAIL refused at the first cycle, or quoted without the reason
```

**One observable outcome → one case.** Cases are enumerated separately only
where the outcomes are genuinely independent — a positive and its
planted-violation twin, or one case per rung of a declared ladder.

**Every case states its FAIL side.** A pass criterion with no stated
contradiction is where falsifiability leaks back out: at execution time the
operator decides what *"didn't really fail"* means, and the case becomes
unfalsifiable in practice while still looking rigorous on the page.

### 0.4 Rules this document is held to

| # | Rule | Enforced by |
|---|---|---|
| TV-1 | Every `SYS` requirement has ≥1 test here; every test here serves ≥1 requirement. | `ANL-50`, `trace_check.py` |
| TV-1b | **Every row's `Serves` column agrees with that requirement's own `Verify` clause, in both directions** (`R-REQ-11`). The two are a deliberate second copy — a row that did not say what it verifies would be unreviewable — so the checker is what stops them drifting. Until it existed, a row could claim to serve one requirement while that requirement cited a different test, and both documents passed review separately. | `trace_check.py` |
| TV-2 | A test identifier appears verbatim inside its implementing test. | `ANL-52` |
| TV-3 | **Every `ANL-*` ships a planted-violation case** proving it fails when it should. A check nobody has seen fail is a check nobody should believe. | `ANL-48`, `.c2` rows below |
| TV-4 | A measurement names its platform, shell, CPU and build type beside its number. | `SYS-0251`, `SYT-NFR-19` |
| TV-5 | No test restates an `Accept` clause. | `INSP-08` |
| TV-6 | Verification status lives in the execution record, never in a column here. | `ANL-51`, `INSP-08` |
| TV-7 | **A test identifier is allocated once and never reused.** | `trace_check.py` — **currently failing, see §6** |

### 0.5 Thresholds not yet supplied — `⊘`

`⊘` means the harness is specified and buildable but the bound is the
customer's (`R-REQ-10`). **A requirement nobody can fail is a requirement that
will be declared satisfied**, so these are marked rather than given a plausible
number.

| Marked | Waiting on |
|---|---|
| `SYT-NFR-03.c1`, `ANL-32` | The "declared factor" for slice-cost scaling |
| ~~`ANL-34`~~ | **Supplied 2026-08-13** (`OQ-14`): ≥ 10.4 recordings/hour per worker, ≤ 5 min 46 s per recording, ≤ 4 GB peak per worker, on SysReq §18.0's reference configuration |
| ~~`ANL-35`~~, ~~`ANL-37`~~, ~~`ANL-40`~~ | **Resolved 2026-08-13** (`OQ-14`): no absolute was supplied for these, so each is **seeded from its first measurement** on the reference configuration and is failable from the second run. A seeded row is not an unsupplied row — it has a number, a reason and printed headroom |
| ~~`SYT-CFG-18`, `ANL-25`~~ | **Resolved 2026-08-13** (`OQ-16`): the gate is **structural** — each change touches exactly its declared file set — and is failable today. The wall clock is recorded as an observation, not a bound |
| ~~`SYT-NFR-22`~~ | **Resolved 2026-08-13** with `ANL-40`, same mechanism |
| `SYT-PLR-18` | The figure/live pixel tolerance |
| `SYT-OUT-07` | The volume-estimate factor and the campaign budget |

**On seeding, so `⊘` keeps meaning something.** A baseline-seeded budget is
*not* the same as an unsupplied one, and collapsing the two would empty this
marker of content. `⊘` means **no observation could fail this row today**. A
seeded row has a number the second run can exceed, a written reason, and its
consumed headroom printed on pass (`SYS-0243`'s device, reused rather than
rebuilt). What a seeded row does **not** answer is *"is it fast enough?"* —
that is an absolute and it stays with whoever owns throughput expectations. It
just no longer holds up the harness.

---

## 1. Fixture catalogue

Named once, reused everywhere. A test needing a fixture not listed here needs a
new row here **first** — an ad-hoc fixture is how two tests come to disagree
about what "a recording" means.

System fixtures are **assembled systems**, one level above the software
suite's `F-*` fixtures. Where a system fixture is the same artifact, it says so.

| Fixture | What it is | Used by |
|---|---|---|
| **`S-TINY`** | A framework-produced recording, every message of a cycle sharing a `log_time_ns`. The case that works today. | input, data, output |
| **`S-FOREIGN`** | A recording in which **no two messages share a timestamp**, each carrying its own counter, source time and status. **The case `SYS-0062` exists for**, and the most important fixture here. | `SYT-TIM-*`, `SYT-INP-*` |
| **`S-LADDER`** | Five variants of `S-FOREIGN`, one per rung of `SYS-0061`'s recovery ladder, plus one whose source time is present but not monotonic. | `SYT-TIM-03` |
| **`S-LONG`** | One content at 1×, 5× and 20× duration, for streaming and memory claims. | `SYT-INP-02`, `ANL-01` |
| **`S-BULK`** | A recording carrying images and point clouds beside small signals. | `SYT-INP-05`, `SYT-OUT-08`, `SYT-NFR-01`/`02` |
| **`S-MULTI`** | Three sources, different time domains, one pair sharing a capture-group identity, one arriving out of order. | `SYT-INP-06`…`08` |
| **`S-DAMAGED`** | `S-FOREIGN` with a truncated tail, a counter gap, one bad checksum and an unstable rate — **one injected defect per class in `SYS-0220`**. | `SYT-REC-01`…`03` |
| **`S-MAP`** | An ingest map set: units, array shape, header bindings, an `absent:` block, a second map claiming one of the same ports, and one map with a construct outside the closed vocabulary. | `SYT-INP-13`…`22` |
| **`S-STUB`** | The stub implementation `SYS-0085` requires. **Lets the whole suite run with no compiled component present.** | almost everything |
| **`S-STUB2`** | A second stub at a different declared period, for base-grid, hold and age tests. | `SYT-TIM-*` |
| **`S-STUB-SLOW`** | A stub that sleeps past the per-cycle timeout on a nominated cycle. | `SYT-PRC-19`, `SYT-BAT-16` |
| **`S-STUB-CRASH`** | A stub that segfaults on a nominated cycle. | `SYT-PRC-13`, `SYT-BAT-02`/`06`/`08` |
| **`S-STUB-CLOCK`** | A stub that reads wall-clock time — the negative case for `SYS-0054`. | `SYT-PRC-17`, `INSP-03` |
| **`S-CHAIN4`** | A four-module graph `vdy → perception → fusion → aeb`, every mode combination reachable, **including `simulate → measured → measured → simulate`**. | `SYT-STG-*`, `SYT-CFG-*` |
| **`S-CFGSET`** | A four-kind configuration set across all four merge layers, with includes, fragments and variables. | `SYT-CFG-07`…`17` |
| **`S-LIBDIR`** | A deployed library directory — binary + `config/` + `sim/` + `bundle.sha256` — with **no source checkout reachable**. | `SYT-INP-21`, `SYT-CON-04`, `SYT-CFG-20` |
| **`S-RUNPAIR`** | Two completed runs of one spec, differing in **exactly one** manifest dimension — one pair per determinism axis, plus one pair differing in two. | `SYT-NFR-07`…`14` |
| **`S-TWOHOST`** | Windows and Ubuntu, different CPUs, the same declared toolchain. | `SYT-NFR-15`…`19` |
| **`S-DIVERGE`** | A recording where the function commands a brake the recorded vehicle did not apply. | `SYT-STG-24`…`26` |
| **`S-PLANTED`** | Per `ANL-*` check, a copy of the tree with exactly one deliberate violation. **`TV-3`.** | every `ANL-*` |
| **`S-BROKENENV`** | A deliberately broken environment: missing library, corrupt bundle, unreadable recording, incompatible plugin. | `SYT-DIA-07` |

---

## 2. `ANL-nn` — analysis

The mechanised checks, and the highest-leverage tests here: each turns a rule
that would otherwise be reviewed into a rule that fails a build. **Every row
ships its `S-PLANTED` variant** (`TV-3`), stated once as the universal `.c2`:

> **`.c2` (every row)** — PASS the check fails on the `S-PLANTED` copy, naming
> the planted violation · FAIL it passes, or fails without naming it.

| ID | Serves | What it scans | `.c1` PASS / FAIL |
|---|---|---|---|
| `ANL-01` | `SYS-0002` | Peak RSS over `S-LONG` at 1×/5×/20× | variation < 20% and no container sized by message count / above 20%, or a length-scaled allocation |
| `ANL-02` | `SYS-0005` | Bytes read for a graph with and without an image consumer | difference ≥ the image channels' share / below it |
| `ANL-03` | `SYS-0024` | Reader sources for module names, module sources for reader names | neither names the other, in code or configuration / either does |
| `ANL-04` | `SYS-0033` | The origin enum against the published schema | six members, both directions / a seventh reachable by any path |
| `ANL-05` | `SYS-0035` | Cross-tick state held for the purpose of emitting an unpublished port value | none / any integration, filter or history-dependent estimate |
| `ANL-06` | `SYS-0038` | Every source file for an enumerated processing chain | none / any file naming a chain |
| `ANL-07` | `SYS-0050` | Engine symbol dump | only the fixed ABI set / any component symbol name |
| `ANL-08` | `SYS-0053` | Diff of onboarding a module | no framework file changed / any changed, outside the declared legacy kind |
| `ANL-09` | `SYS-0057` | Per-module conversion source files | none / any exists |
| `ANL-10` | `SYS-0060` | Type scan of engine time members | all integer / any floating-point time member |
| `ANL-11` | `SYS-0069` | Per-cycle execution routes | exactly one / a second route or a single-rate fast path |
| `ANL-12` | `SYS-0086` | Reader outputs against reader inputs | no reader emits an absent value / any manufactures module output |
| `ANL-13` | `SYS-0104` | Back edges from module output to reader return | none / any configuration closes the loop |
| `ANL-14` | `SYS-0117` | Estimate against actual on a known recording | within the stated factor, labelled an upper bound / unlabelled, or outside the factor |
| `ANL-15` | `SYS-0121` | Consumer files for a format, codec or producing-tool name | none / any consumer can learn its format |
| `ANL-16` | `SYS-0127` | Artifact schemas and the exit-code table | no verdict field, no code encoding a functional verdict / any |
| `ANL-17` | `SYS-0128` | View sources for engine pointers; engine link map | no view holds one, no GUI toolkit linked / either |
| `ANL-18` | `SYS-0131` | Player sources for codec, world-model and library names | none / any |
| `ANL-19` | `SYS-0132` | Player sources for component and function tokens | none / any — **this is `GT-1` at system level** |
| `ANL-20` | `SYS-0146` | Layer-provider imports | no renderer, plotting library or GUI toolkit / any |
| `ANL-21` | `SYS-0148` | Layer callback registrations; double-render equality | none, and identical output / any callback, or differing output |
| `ANL-22` | `SYS-0154` | Code paths capable of producing an evidence answer | exactly one / a second exists |
| `ANL-23` | `SYS-0156` | Engine-boundary bytes with context video active vs inactive | equal / display-only data crosses the engine |
| `ANL-24` | `SYS-0165` | Engine for a configuration parser, inference, validation, search-path logic | none present / any |
| `ANL-25` | `SYS-0175` | Each of the five changes made on a reference project, then the resulting diff; plus lines-of-configuration per project | each diff touches exactly the declared file set, with no rebuild and no source edit, and the metric is tracked / any change touches a file outside its set, needs a rebuild, or the metric is untracked |
| `ANL-26` | `SYS-0194` | Index build cost across a batch of N | once per recording / once per run |
| `ANL-27` | `SYS-0196` | Engine binary hash, CI path vs desktop path | identical / differing |
| `ANL-28` | `SYS-0201` | The first delivered increment's pipeline | a running pipeline accompanies it / manual verification is the sole evidence for any requirement |
| `ANL-29` | `SYS-0209` | Every emittable error against the taxonomy | four kinds, four fields, one shape / any error outside it |
| `ANL-30` | `SYS-0216` | Engine process symbols under a debugger | no interpreter frames / any |
| `ANL-31` | `SYS-0230` | Image bytes decoded by a signal-only run | zero, and bytes-read reported against the theoretical minimum / any image decode |
| `ANL-32` | `SYS-0232` | ⊘ Wall time for a 6 s slice of a 20 min recording | scales with slice within the declared factor / with file length — **factor not supplied** |
| `ANL-33` | `SYS-0233` | Per-message path profile | no scripting-layer frame, no per-element conversion / any |
| `ANL-34` | `SYS-0234` | Per-worker throughput, per-recording wall time and peak resident memory over the reference campaign, on SysReq §18.0's host | ≥ 10.4 recordings/hour per worker, ≤ 5 min 46 s per recording, ≤ 4 GB peak per worker, aggregate derived and reported / any bound exceeded, or the host not recorded beside the measurement |
| `ANL-35` | `SYS-0235` | Player frame time at the stated tick and layer count, against the seeded budget | within the seeded budget with headroom printed / above it, or the budget re-seeded without the seeding run being marked |
| `ANL-36` | `SYS-0236` | Intra-run thread pools; outputs across core counts | none, and outputs invariant / any pool, or core-count-dependent output or order |
| `ANL-37` | `SYS-0238` | Estimated vs measured duration on the reference configuration, against the factor declared from the first campaign | within the declared factor, factor reported alongside the estimate / outside it, or the factor claimed in prose rather than measured |
| `ANL-38` | `SYS-0240` | Reproducibility across the four axes of `S-RUNPAIR` | each reported separately; same-process divergence blocks; a passing far axis prints headroom / any axis merged, or a pass printing no headroom |
| `ANL-39` | `SYS-0262` | Each phase boundary: retired implementation, and its tests | retired one gone, replacement carries its tests / either survives, or coverage decreases |
| `ANL-40` | `SYS-0265` | The recorded onboarding demonstration against the seeded budget; documentation size per release | completed unaided within the seeded budget, size reported / above it, or size untracked |
| `ANL-41` | `SYS-0267` | A sampled name in log, configuration and display | the identical string in all three / any surface renames for presentation |
| `ANL-42` | `SYS-0268` | CLI verbs, file kinds, panel types, extension points | each enumerable, size reported per release / a member added without a requirement |
| `ANL-43` | `SYS-0269` | Every module against the per-tick/per-run rule | every one classifiable with no judgement call / any per-message path in the scripting layer |
| `ANL-44` | `SYS-0270` | The four historically duplicated subsystems | exactly one implementation each / any concept in both languages |
| `ANL-45` | `SYS-0271` | Callback registrations crossing the boundary; a run with no interpreter | none, and it completes / any callback, or the run requires an interpreter |
| `ANL-46` | `SYS-0272` | Engine library embedded by a non-`simengine` host; executable contents | it embeds and runs; executable has argument handling and lifecycle only / the library is unusable alone, or the executable holds parser, validation, search or inference |
| `ANL-47` | `SYS-0273` | Two transports against one unchanged interface | both work, interface unchanged, no view reads an engine pointer / the interface changed, or a view reads one |
| `ANL-48` | `SYS-0274` | Framework source directories for function and component tokens | clean on every build / any hit |
| `ANL-49` | `SYS-0275` | Every closed set against its published schema | all match, both directions, checked every build / any member in code but absent from the schema |
| `ANL-50` | `SYS-0276` | Every `SYS` entry for an `Accept` line and a resolvable `Verify` identifier | all present and resolvable / any missing or dangling |
| `ANL-51` | `SYS-0277` | Every document in the set for a hand-maintained status column | none — **including this document** / any |
| `ANL-52` | `SYS-0278` | Every `Verify` identifier against the test suite | each resolves to ≥1 literal occurrence / any resolves to none, or a docstring claims one without implementing it |
| `ANL-53` | `SYS-0279` | Every `SYS` `Trace` field; every live `CN` UID | all trace to a live `CN`, and uncovered `CN` UIDs are reported / any unparented, or the reverse report missing |
| `ANL-54` | `SYS-0280` | Delivered artifact hash across projects | identical / any project-specific code path |
| `ANL-55` | `SYS-0282` | Codec sources for port/module/graph/tool names; files above the codec layer for format names | neither direction hits; adding a format changes codec + registry only / any hit, or a third file changes |
| `ANL-56` | `SYS-0289` | Every artifact writer in the tree, against the artifact-kind declaration | every kind written appears once, marked cited or not-cited, and the scanned-writer count is printed / a kind is written that the declaration does not carry, or the count is zero and the row reads `PASSED` rather than `SKIPPED` |
| `ANL-57` | `SYS-0290` | The delivered package for the use-constraints statement, against the cited kinds `ANL-56` found | every cited kind has an entry carrying a limit or a dated *none known* / a cited kind is missing, or an entry is blank |
| `ANL-59` | `SYS-0292` | Every generated progress mark in the requirement documents, against the implementation plan's checkboxes | every mark matches its derived value, and a hand-edited mark fails naming both / any mark disagrees without failing, or a requirement document is the source of its own mark |
| `ANL-58` | `SYS-0291` | Each cited kind's named detecting check, resolved against the test suite | each resolves to a test that exists or to `undetected`, and the `undetected` count is printed on pass / an identifier resolves to nothing, or the cell is blank |

---

## 3. `INSP-nn` — inspection

Only where no execution is possible. Each names its checklist; *"inspected"* may
never mean *"someone read it"*. Every row's `.c1` is **PASS** the checklist
completes with no finding · **FAIL** any item unanswered or answered "unclear".

| ID | Serves | Checklist question | Reviewer |
|---|---|---|---|
| `INSP-01` | `SYS-0019` | Each unit-correction construct, against *"does this compute, or only rename and rescale?"* | SIM team + one recording owner |
| `INSP-02` | `SYS-0035` | Each reconstruction site, against *"does this integrate, filter, or depend on history?"* | SIM team + the owning component team |
| `INSP-03` | `SYS-0054` | The delivery contract, against *"does it state the wall-clock prohibition where a module author will read it?"* | SIM team + one algorithm team |
| `INSP-04` | `SYS-0097` | Each override verb's written form, against *"could this create an entity?"* | SIM team |
| `INSP-05` | `SYS-0127` | Every artifact field and exit code, against *"could a reader take this as a functional verdict?"* | SIM team + one automation-framework owner |
| `INSP-06` | `SYS-0155` | The evidence chain's terminus, against *"does any field answer **why** rather than **where**?"* | SIM team |
| `INSP-07` | `SYS-0174` | The four file kinds' key sets, against *"would two teams change this file for unrelated reasons?"* | SIM team + one algorithm team |
| `INSP-08` | `SYS-0200` | The document set, against *"is verification status stored anywhere by hand?"* and *"does any test restate an `Accept` clause?"* — **including this document** | SIM team |
| `INSP-09` | `SYS-0252` | The four extension points and their conformance kits, against *"could a fifth be added without a requirement?"* | SIM team |
| `INSP-10` | `SYS-0256` | Every project-specific behaviour in the reference projects, against *"is this a plugin or a fork?"* | SIM team + each project owner |
| `INSP-11` | `SYS-0269` | Every module's language assignment, against *"did this need judgement?"* | SIM team |
| `INSP-12` | `SYS-0281` | The format/content boundary, against *"can a schema change ship without touching project content, and vice versa?"* | SIM team + one algorithm team |
| `INSP-13` | `SYS-0290` | Each use-constraints entry, against *"could a reader take this limit as narrower than it is?"* and *"is a limit stated here that no requirement or test governs?"* — the second catches a constraint invented for the document | SIM team + quality/safety |

---

## 4. `SYT-<area>-nn` — system tests

Expected values are the served requirement's `Accept` clause (§0.1). Each row
gives the fixture, the steps and the cases.

### 4.1 `INP` — input and ingest

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-INP-01` | `SYS-0001` | `S-TINY` | Implement a throwaway reader against the plugin interface; count files changed outside it and its registration. | `.c1` PASS zero · FAIL any `simcore` file changed |
| `SYT-INP-02` | `SYS-0002` | `S-LONG` | Run to completion at 1×, 5×, 20×; sample peak resident bytes. | `.c1` PASS variation < 20% · FAIL memory scales with recording length |
| `SYT-INP-03` | `SYS-0003` | `S-LONG` | Seek to an arbitrary time; count messages read before the target. | `.c1` PASS correct first message, none read before it · FAIL a linear scan |
| `SYT-INP-04` | `SYS-0004` | `S-LONG` | Open once; open again unmodified; then run a batch of N entries. | `.c1` PASS second open performs no full scan · FAIL it rescans<br>`.c2` PASS build cost appears once in the batch · FAIL N times |
| `SYT-INP-05` | `SYS-0005` | `S-BULK` | Run a graph needing no image port; then one with an image consumer. Compare bytes read. | `.c1` PASS zero image bytes decoded · FAIL any<br>`.c2` PASS difference ≥ the image share · FAIL below it |
| `SYT-INP-06` | `SYS-0006` | `S-MULTI` | Activate two readers in one run. | `.c1` PASS one ordered tick stream · FAIL interleaving errors<br>`.c2` PASS each port's origin source named in the manifest · FAIL any unattributed |
| `SYT-INP-07` | `SYS-0007` | `S-MULTI` | Combine two sources with different time domains and no declared relationship. | `.c1` PASS rejected at load naming both · FAIL accepted, or naming one |
| `SYT-INP-08` | `SYS-0008` | `S-MULTI` | Configure the sync buffer to the declared window; then to zero. | `.c1` PASS monotonic tick stream at the declared window · FAIL out-of-order output<br>`.c2` PASS at zero, reported as out of order · FAIL silently accepted |
| `SYT-INP-09` | `SYS-0009` | `S-TINY` | Load a recording carrying an embedded description; then supply an external one. | `.c1` PASS loads with no external file · FAIL one is required<br>`.c2` PASS the override wins and the manifest records which was used · FAIL unrecorded |
| `SYT-INP-10` | `SYS-0010` | `S-TINY` | Register a codec declaring no round-trip; offer it as a simulation input. | `.c1` PASS refused by capability check, naming the missing capability · FAIL refused by a special case in the loader, or accepted |
| `SYT-INP-11` | `SYS-0011` | real files | Open one real file per format from its owning team; run `E2E-01` against each. | `.c1` PASS all three open · FAIL any<br>`.c2` PASS `E2E-01` completes against each · FAIL any |
| `SYT-INP-12` | `SYS-0012` | real files | As `SYT-INP-11`, for the two second-tier formats. | `.c1` PASS both open and complete `E2E-01` · FAIL either |
| `SYT-INP-13` | `SYS-0013` | `S-MAP` | Onboard a new recording family. Record every artifact rebuilt and every module edited. | `.c1` PASS no compiled artifact rebuilt, no Python module edited · FAIL either |
| `SYT-INP-14` | `SYS-0014` | `S-MAP` | Load a map omitting each mandatory field in turn. | `.c1` PASS refused, naming the field **and the line** · FAIL accepted, or the line omitted |
| `SYT-INP-15` | `SYS-0015` | `S-FOREIGN`, `S-MAP` | Load a map binding none of the header fields. | `.c1` PASS it loads · FAIL it is refused — *this is deliberately permitted*<br>`.c2` PASS every port it feeds is marked *timing approximated* and a warning names them · FAIL unmarked, or a warning naming no ports |
| `SYT-INP-16` | `SYS-0016` | `S-MAP` | Request a cut requiring a declared-absent port. | `.c1` PASS refused at load with the declared reason quoted · FAIL refused at the first cycle, or without the reason |
| `SYT-INP-17` | `SYS-0017` | `S-MAP` | Present two maps with disjoint match rules; then a recording matching neither. | `.c1` PASS both coexist · FAIL a shared namespace is required<br>`.c2` PASS unmapped, naming the maps considered · FAIL an unnamed failure |
| `SYT-INP-18` | `SYS-0018` | `S-MAP` | Make two applicable maps claim one port. | `.c1` PASS an authoring error naming both maps, the port and both source signals · FAIL a precedence rule resolves it silently |
| `SYT-INP-19` | `SYS-0019` | `S-MAP` | Load a map containing a construct outside the closed vocabulary. | `.c1` PASS refused at load · FAIL accepted<br>`.c2` PASS the vocabulary is enumerable from the published schema · FAIL it is not |
| `SYT-INP-20` | `SYS-0020` | `S-MAP` | Bind a source signal whose type differs from the port's, including a narrower numeric width. | `.c1` PASS refused, naming both types · FAIL any coercion, **including between numeric widths** |
| `SYT-INP-21` | `SYS-0021` | `S-LIBDIR` | Delete the source checkout; run. | `.c1` PASS every ingest map resolves from the deployed directory · FAIL any read from a checkout |
| `SYT-INP-22` | `SYS-0022` | `S-MAP`, `S-CHAIN4` | Run `probe`; then attempt every cut it reports and every cut it excludes. | `.c1` PASS every reported cut runs · FAIL any fails<br>`.c2` PASS every excluded cut is refused at load with a reason · FAIL any fails at cycle 0 instead |

### 4.2 `DAT` — data model

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-DAT-01` | `SYS-0023` | `S-CFGSET` | Reference a port that does not exist in the catalogue. | `.c1` PASS load fails naming the port and listing near matches · FAIL no near matches offered |
| `SYT-DAT-02` | `SYS-0025` | `S-CFGSET` | Pin a configuration to one major version; load against another. | `.c1` PASS refused naming both versions · FAIL accepted<br>`.c2` PASS adding an optional field is a minor change · FAIL it forces a major |
| `SYT-DAT-03` | `SYS-0026` | `S-FOREIGN` | Present a port value with an absent field; read it through export, player and evidence query. | `.c1` PASS absent through all three surfaces · FAIL any renders `0`, `0.0` or `[]` |
| `SYT-DAT-04` | `SYS-0027` | `S-CFGSET` | Define a project-local port; use it in configuration, export and visualization; then attempt a name colliding with a core port. | `.c1` PASS usable in all three · FAIL any rejects it<br>`.c2` PASS the collision is impossible · FAIL it is permitted |
| `SYT-DAT-05` | `SYS-0028` | `S-LIBDIR` | Remove every generated binding from the environment; decode every port from the manifest's embedded schema set. | `.c1` PASS every port decodes · FAIL any requires a binding<br>`.c2` PASS removal changes nothing · FAIL behaviour differs |
| `SYT-DAT-06` | `SYS-0029` | `S-FOREIGN` | Read every port value in an export and in an evidence answer. | `.c1` PASS all eight header fields present, each a value or explicit *unknown* · FAIL any missing or defaulted |
| `SYT-DAT-07` | `SYS-0030` | `S-FOREIGN`, `S-TINY` | Present a message with unknown capture time; then one where capture and reception genuinely coincide. | `.c1` PASS the first reads *unknown* · FAIL it is defaulted to reception<br>`.c2` PASS the second's zero age is distinguishable from unknown in every surface · FAIL they render alike |
| `SYT-DAT-08` | `SYS-0031` | `S-LADDER` | Run over a recording where some ports carry source time and some do not. | `.c1` PASS the manifest names the timestamp basis for **every** port · FAIL any omitted |
| `SYT-DAT-09` | `SYS-0032` | `S-FOREIGN` | Remove both source time and counter for one port; run. | `.c1` PASS a warning is emitted · FAIL silent<br>`.c2` PASS the mark appears in the manifest, in every export carrying the port, and in the player · FAIL any of the three omits it |
| `SYT-DAT-10` | `SYS-0033` | `S-TINY` | Attempt to produce a seventh origin value; load a recording with no provenance metadata. | `.c1` PASS no seventh value is reachable · FAIL any path produces one<br>`.c2` PASS the unprovenanced recording yields `unknown` · FAIL it yields `measured` |
| `SYT-DAT-11` | `SYS-0034` | `S-CHAIN4` | Render, export and explain a reconstructed value beside a published value of the same port. | `.c1` PASS distinguishable visually **and** textually without opening the configuration · FAIL either surface renders them alike |
| `SYT-DAT-12` | `SYS-0036` | `S-CHAIN4` | Split a two-function component into two, port names unchanged; re-open existing artifacts. | `.c1` PASS every existing recording readable, every plugin bound, every ingest map valid · FAIL any breaks |

### 4.3 `PRC` — processing and module lifecycle

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-PRC-01` | `SYS-0037` | `S-STUB` | Remove each mandatory manifest field in turn and load. | `.c1` PASS refused, naming the field · FAIL accepted<br>`.c2` PASS the engine reads no module property from any other source · FAIL any is read elsewhere |
| `SYT-PRC-02` | `SYS-0038` | `S-CHAIN4` | Reorder, then replace, the chain by configuration only. | `.c1` PASS both are configuration-only · FAIL any code change needed<br>`.c2` PASS no file enumerates a chain · FAIL any does |
| `SYT-PRC-03` | `SYS-0039` | `S-CHAIN4` | Configure two active producers for one port. | `.c1` PASS refused at load, naming both · FAIL one wins silently |
| `SYT-PRC-04` | `SYS-0040` | `S-CHAIN4` | Leave a required input with neither producer nor source. | `.c1` PASS refused naming consumer, port, **and every candidate considered with why each failed** · FAIL a bare "unfed input" |
| `SYT-PRC-05` | `SYS-0041` | `S-STUB` | Regenerate a manifest that disagrees with the checked-in one. | `.c1` PASS the difference is reported · FAIL silent<br>`.c2` PASS the checked-in file is not overwritten without an explicit instruction · FAIL it is |
| `SYT-PRC-06` | `SYS-0042` | `S-STUB` | Delete the generated shim and rebuild; then hand-edit it and rebuild. | `.c1` PASS reproduced byte-identically · FAIL any difference<br>`.c2` PASS the hand edit is overwritten · FAIL it survives |
| `SYT-PRC-07` | `SYS-0043` | `S-STUB` | Instantiate one module twice with renaming. | `.c1` PASS two distinct port namespaces and two distinct provenance sets · FAIL any sharing |
| `SYT-PRC-08` | `SYS-0044` | `S-CHAIN4` | Connect a data port to a control port. | `.c1` PASS refused, naming both kinds · FAIL accepted |
| `SYT-PRC-09` | `SYS-0045` | `S-CHAIN4` | Change which modules receive a reset, and which cycle-end event triggers which consumer. | `.c1` PASS configuration edit only, no rebuild · FAIL either needs one<br>`.c2` PASS same file kind and syntax as data connections · FAIL a separate mechanism |
| `SYT-PRC-10` | `SYS-0046` | `S-CFGSET` | Reuse one unit file in two different top-level compositions. | `.c1` PASS no edit required · FAIL the unit names its context |
| `SYT-PRC-11` | `SYS-0047` | `S-CFGSET`, `S-TWOHOST` | Run one configuration set on two machines with different install roots. | `.c1` PASS unchanged on both · FAIL any edit needed<br>`.c2` PASS every resolution reported by `explain` · FAIL any silent |
| `SYT-PRC-12` | `SYS-0048` | `S-STUB` | Drive the full lifecycle; then fail each transition in turn. | `.c1` PASS every transition observable in the cycle trace · FAIL any invisible<br>`.c2` PASS each failure reported with the transition named · FAIL a generic error |
| `SYT-PRC-13` | `SYS-0049` | `S-STUB-CRASH` | Crash a module at a nominated cycle; take only the report to a debugger. | `.c1` PASS module, cycle and input snapshot present · FAIL any missing<br>`.c2` PASS the failing cycle re-executes **without re-running preceding cycles** · FAIL a full replay is required |
| `SYT-PRC-14` | `SYS-0051` | `S-STUB` | Present an undersized output buffer; then one still undersized after the retry. | `.c1` PASS grown once and retried · FAIL no retry, or more than one<br>`.c2` PASS contract error naming port, size requested and size provided · FAIL an unbounded retry loop |
| `SYT-PRC-15` | `SYS-0052` | `S-STUB` | Load a module with a deliberately mismatched ABI version. | `.c1` PASS refused, message contains **both** numbers · FAIL loaded, or only one number |
| `SYT-PRC-16` | `SYS-0053` | `S-STUB` | Onboard a module; then onboard one via the legacy implementation kind. | `.c1` PASS no framework file edited · FAIL any<br>`.c2` PASS legacy stages individually identifiable in the run manifest · FAIL indistinguishable |
| `SYT-PRC-17` | `SYS-0054` | `S-STUB-CLOCK` | Run the clock-reading stub across the determinism axes. | `.c1` PASS detected by the axes · FAIL it survives<br>`.c2` PASS the delivery contract states the prohibition · FAIL unstated |
| `SYT-PRC-18` | `SYS-0055` | `S-STUB` | Run a thread-spawning module undeclared, then declared. | `.c1` PASS undeclared fails the fresh-process axis · FAIL it passes<br>`.c2` PASS declared marks the run non-reproducible in the manifest · FAIL unmarked |
| `SYT-PRC-19` | `SYS-0056` | `S-STUB-SLOW` | Set a per-cycle timeout; hang a module past it. | `.c1` PASS aborts within the bound, cycle named · FAIL it hangs<br>`.c2` PASS reported as `timeout`, distinct from `fail` and `crash` · FAIL merged |
| `SYT-PRC-20` | `SYS-0058` | `S-STUB` | Host one module out of process; compare port values against in-process. | `.c1` PASS identical · FAIL any difference |

### 4.4 `TIM` — time and scheduling

`SYT-TIM-21`…`24` are the renumbered identifiers of `SYS-0283`…`SYS-0286` — see
**§6**. `SYT-TIM-10` is an unallocated gap and is deliberately left unused
(`R-REQ-2` — a gap is free; backfilling one is a mild form of reuse).

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-TIM-01` | `SYS-0059` | `S-STUB`, `S-TWOHOST` | Run one spec on a fast and a ~10× slower machine. | `.c1` PASS identical port values · FAIL any difference<br>`.c2` PASS only the performance report differs · FAIL wall clock reaches a result |
| `SYT-TIM-02` | `SYS-0060` | `S-CFGSET` | Type-scan engine time members; declare a fractional period. | `.c1` PASS all integer nanoseconds internally · FAIL any float time member<br>`.c2` PASS the fractional period is refused · FAIL rounded |
| `SYT-TIM-03` | `SYS-0061` | `S-LADDER` | Run each ladder rung; then force a lower rung on a recording supporting a higher one. | `.c1` PASS the rung used is reported per port in the manifest · FAIL unreported<br>`.c2` PASS forcing is possible, recorded **and** warned · FAIL silent, or forbidden |
| `SYT-TIM-04` | `SYS-0062` | `S-FOREIGN` | Build cycles over a recording in which no two messages share a timestamp. | `.c1` PASS cycles carry the correct multi-port input sets · FAIL one port per cycle — *the defect this fixture exists to catch* |
| `SYT-TIM-05` | `SYS-0063` | `S-STUB2` | Record a port at 22 ms against a declared 20 ms. | `.c1` PASS a warning quoting both numbers **and** the sample count · FAIL silent, or missing the sample count |
| `SYT-TIM-06` | `SYS-0064` | `S-STUB2` | Feed a 20 ms input with repeats; then two arrivals inside one grid step. | `.c1` PASS runs once per new value, not on repeats · FAIL it runs on repeats<br>`.c2` PASS never executes between ticks · FAIL an independent clock<br>`.c3` PASS two arrivals in one step yield one execution with the later value, **reported as coalesced** · FAIL silently dropped |
| `SYT-TIM-07` | `SYS-0065` | `S-STUB2` | Run a periodic module with period and offset over 60 s. | `.c1` PASS fires on exactly the expected ticks, zero drift · FAIL any drift |
| `SYT-TIM-08` | `SYS-0066` | `S-STUB`, `S-STUB2` | Declare 20 ms and 30 ms; then 19.99 ms beside 20 ms; then attempt to configure a tolerance. | `.c1` PASS grid is 10 ms and both fire correctly · FAIL a rounded grid<br>`.c2` PASS 19.99 ms refused naming both numbers · FAIL snapped to nearest<br>`.c3` PASS no configured tolerance can make it accepted · FAIL one can |
| `SYT-TIM-09` | `SYS-0067` | `S-STUB2` | Declare a period set producing a 1 µs grid. | `.c1` PASS warns **before executing**, quoting the step count and estimated cost · FAIL it runs first |
| `SYT-TIM-11` | `SYS-0070` | `S-STUB2` | Run a 50 ms consumer of a 10 ms producer. | `.c1` PASS a value on every tick, never a gap · FAIL any absent port<br>`.c2` PASS not-updated flag and elapsed time correct **to the nanosecond** · FAIL any rounding |
| `SYT-TIM-12` | `SYS-0071` | `S-STUB2` | Run a module whose internal rate gating disagrees with its declared period. | `.c1` PASS a named finding in the run manifest · FAIL a silent value, or the prediction overriding the module |
| `SYT-TIM-13` | `SYS-0072` | `S-LIBDIR` | Sweep the period by editing the config bundle only. | `.c1` PASS no rebuild, no host file edited · FAIL either<br>`.c2` PASS the period is integer microseconds from the bundle, reported through the manifest · FAIL the host sets it |
| `SYT-TIM-14` | `SYS-0073` | `S-FOREIGN` | Exercise each sampling policy on one crafted input; then request interpolate on a non-continuous type. | `.c1` PASS each policy individually demonstrable · FAIL any indistinguishable<br>`.c2` PASS interpolate refused, naming the type · FAIL accepted |
| `SYT-TIM-15` | `SYS-0074` | `S-FOREIGN` | Exercise each missing-data behaviour. | `.c1` PASS each demonstrable, default is hold · FAIL any<br>`.c2` PASS the warning count appears in the end-of-run summary · FAIL uncounted |
| `SYT-TIM-16` | `SYS-0075` | `S-STUB2` | Consume a held value. | `.c1` PASS the repeat flag reaches the module · FAIL it does not<br>`.c2` PASS it appears in the export · FAIL dropped |
| `SYT-TIM-17` | `SYS-0076` | `S-CHAIN4` | Run one spec twice; run `explain`. | `.c1` PASS identical topological order · FAIL any variation<br>`.c2` PASS `explain` prints it before executing anything · FAIL after, or not at all |
| `SYT-TIM-18` | `SYS-0077` | `S-CHAIN4` | Declare a one-step transport delay on an edge. | `.c1` PASS the consumed value shifts by exactly one grid step, observable in the export · FAIL any other shift |
| `SYT-TIM-19` | `SYS-0078` | `S-CHAIN4` | Construct a zero-delay cycle. | `.c1` PASS rejected, listing every module in the loop **in order** · FAIL accepted, or an unordered list |
| `SYT-TIM-20` | `SYS-0079` | `S-CHAIN4` | Record a run with declared delays; reproduce it from the manifest. | `.c1` PASS every declared delay appears in the manifest · FAIL any missing<br>`.c2` PASS the reproduction reproduces the delays · FAIL they differ |
| `SYT-TIM-21` | `SYS-0283` | `S-FOREIGN`, `S-BULK` | Run over a recording dense in one interval and sparse in another; compare the simulation-time sequence against a uniform recording's. | `.c1` PASS an arithmetic sequence of the grid step, independent of the recording's timestamps and of which modules ran · FAIL any arrival, reconstructed boundary or module output moves it<br>`.c2` PASS both recordings produce the same tick sequence · FAIL they differ |
| `SYT-TIM-22` | `SYS-0284` | `S-FOREIGN` | Inspect every header field for a value filled from reception time; read a value whose describing instant is unknown. | `.c1` PASS no header field filled from reception · FAIL any<br>`.c2` PASS unknown reported as unknown, age derived from the hold schedule · FAIL age computed against reception |
| `SYT-TIM-23` | `SYS-0285` | `S-STUB2` | Add a data-driven 5 ms module to a graph of 20 ms modules. | `.c1` PASS the grid becomes 5 ms · FAIL the declared period is excluded because the module is data-triggered<br>`.c2` PASS each arrival observed on its own tick · FAIL coalesced |
| `SYT-TIM-24` | `SYS-0286` | `S-FOREIGN`, `S-STUB2` | Declare a port at 20 ms; record it at 25 ms; run it `measured`. | `.c1` PASS delivered on the **recorded** cadence · FAIL resampled, interpolated or dropped to match the declared rate<br>`.c2` PASS the manifest carries both rates and the disagreement is reported · FAIL either omitted |

### 4.5 `STG` — staged simulation

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-STG-01` | `SYS-0080` | `S-CHAIN4` | Set every valid mode/implementation combination; then set one module `measured`. | `.c1` PASS all combinations expressible, axes independent · FAIL setting one changes the other<br>`.c2` PASS implementation retained on a `measured` module · FAIL discarded, making the toggle irreversible |
| `SYT-STG-02` | `SYS-0081` | `S-CHAIN4` | Toggle a producer between executed and injected; diff the consumer's configuration entry and inputs. | `.c1` PASS byte-identical entry · FAIL any difference<br>`.c2` PASS the consumer cannot determine its producer's mode from its inputs · FAIL any metadata reveals it |
| `SYT-STG-03` | `SYS-0082` | `S-CHAIN4` | Source one port of a simulated module from the recording while siblings compute. | `.c1` PASS it works · FAIL refused<br>`.c2` PASS the exception is listed explicitly in the run manifest · FAIL implicit |
| `SYT-STG-04` | `SYS-0083` | `S-CHAIN4` | Run a mixed-mode graph. | `.c1` PASS every injection-boundary port listed by name with its source **before the first cycle** · FAIL logged later, or incomplete |
| `SYT-STG-05` | `SYS-0084` | `S-CHAIN4` | Set a module `off`; compare the consumer's view against an unmapped port. | `.c1` PASS no code path distinguishes them at the consumer · FAIL a special case exists |
| `SYT-STG-06` | `SYS-0085` | `S-STUB` | Run the full suite on a machine with no component library installed. | `.c1` PASS it passes · FAIL any test requires a compiled component |
| `SYT-STG-07` | `SYS-0087` | `S-CHAIN4` | Classify `simulate → measured → measured → simulate`. | `.c1` PASS classified a broken chain · FAIL passed — **a direct-neighbour-only implementation fails here, which is why this case exists**<br>`.c2` PASS consumption evaluated over the transitive descendant set · FAIL neighbours only |
| `SYT-STG-08` | `SYS-0088` | `S-CHAIN4` | Craft a configuration for each outcome; then search for a fourth. | `.c1` PASS exactly three outcomes producible · FAIL a fourth or an unclassified state |
| `SYT-STG-09` | `SYS-0089` | `S-CHAIN4` | Run the classification standalone in a lint job over a ten-module graph. | `.c1` PASS completes in under one second with no recording opened · FAIL slower, or it opens one |
| `SYT-STG-10` | `SYS-0090` | `S-CHAIN4` | Attempt a run with a broken chain. | `.c1` PASS it does not execute · FAIL it starts<br>`.c2` PASS the message names every stale module, the path, and the consumer where corruption would land · FAIL any of the three missing |
| `SYT-STG-11` | `SYS-0091` | `S-CHAIN4` | Apply the suggested remedy verbatim. | `.c1` PASS classification then passes · FAIL it does not<br>`.c2` PASS the auto-promote option prints exactly what changed · FAIL a silent promotion |
| `SYT-STG-12` | `SYS-0092` | `S-CHAIN4` | Waive with flag only; with reason only; with both. Then export, convert and re-import. | `.c1` PASS waived only with **both** · FAIL either alone suffices<br>`.c2` PASS the incoherent mark survives export, conversion and re-import, and shows in manifest, exports and player · FAIL lost anywhere |
| `SYT-STG-13` | `SYS-0093` | `S-CHAIN4` | Enable the no-waivers policy; attempt a waived run. | `.c1` PASS exits with the coherence-violation exit code · FAIL it executes |
| `SYT-STG-14` | `SYS-0094` | `S-CHAIN4` | Run ten ticks with an orphan simulation. | `.c1` PASS exactly one warning, naming every affected module · FAIL ten, or an unnamed warning<br>`.c2` PASS badged *computed, not consumed* in player and headless summary · FAIL either omits it<br>`.c3` PASS it never blocks · FAIL it blocks |
| `SYT-STG-15` | `SYS-0095` | `S-CHAIN4` | Set a stage to `simulate` with a gap; then force the gap open. | `.c1` PASS intervening stages flip by default, undoably · FAIL not closed, or not undoable<br>`.c2` PASS forcing open is possible and badges the orphan · FAIL forbidden, or silent |
| `SYT-STG-16` | `SYS-0096` | `S-CHAIN4` | Toggle N times, then recover the original. | `.c1` PASS recovered exactly · FAIL any drift<br>`.c2` PASS the configuration round-trips byte-identically · FAIL reformatting |
| `SYT-STG-17` | `SYS-0097` | `S-CHAIN4` | Use a verb outside the closed list; enumerate the set from the schema. | `.c1` PASS refused at load · FAIL accepted<br>`.c2` PASS the set is enumerable and has not grown without a requirement · FAIL it has |
| `SYT-STG-18` | `SYS-0098` | `S-CHAIN4` | Attempt to insert, move and duplicate a repeated element. | `.c1` PASS each is a load error · FAIL any expressible — *an override may destroy or attenuate, never create* |
| `SYT-STG-19` | `SYS-0099` | `S-CHAIN4` | Address by port, field, `[i]` and `[*]`; then attempt a predicate. | `.c1` PASS all four forms work · FAIL any<br>`.c2` PASS the predicate is a load error · FAIL accepted |
| `SYT-STG-20` | `SYS-0100` | `S-CHAIN4` | Clear index 3 of a 10-slot fixed-slot port. | `.c1` PASS 0–2 and 4–9 unchanged, 3 explicitly empty · FAIL compaction renumbers — *which breaks object association silently* |
| `SYT-STG-21` | `SYS-0101` | `S-CHAIN4` | Apply an override; inspect manifest, player and topic tags. | `.c1` PASS present in the manifest · FAIL an override invisible there is producible<br>`.c2` PASS badged in the player and tagged `overridden` on its topic · FAIL either missing |
| `SYT-STG-22` | `SYS-0102` | `S-CHAIN4` | Apply an override contradicting the coherence classification. | `.c1` PASS treated exactly like a waiver — marked incoherent, written reason required · FAIL accepted as an ordinary override |
| `SYT-STG-23` | `SYS-0103` | `S-CHAIN4` | Inject each of the five fault verbs; search for a sixth. | `.c1` PASS each individually observable in the consumer's header · FAIL any invisible<br>`.c2` PASS no sixth verb exists · FAIL one does |
| `SYT-STG-24` | `SYS-0105` | `S-DIVERGE` | Run; then re-run. | `.c1` PASS the divergence tick is reported · FAIL undetected<br>`.c2` PASS recorded in manifest **and** on the player timeline · FAIL either<br>`.c3` PASS stable across re-runs · FAIL it moves |
| `SYT-STG-25` | `SYS-0106` | `S-DIVERGE` | Export past the divergence point plus the grace window; read a slice from the middle. | `.c1` PASS the flag is present **per row/message**, not only in a header · FAIL a header-only flag, which a slice reader would miss |
| `SYT-STG-26` | `SYS-0107` | `S-DIVERGE` | Read only the run manifest as a downstream consumer. | `.c1` PASS both coherence classification and divergence point present · FAIL either missing<br>`.c2` PASS physical validity and its time bound are determinable from the manifest alone · FAIL the artifact must be opened |
| `SYT-STG-27` | `SYS-0108` | `S-DIVERGE` | Enable ego re-integration; inspect the transformed data and the default. | `.c1` PASS marked approximate everywhere · FAIL any surface omits it<br>`.c2` PASS off by default · FAIL on |
| `SYT-STG-28` | `SYS-0109` | `S-MAP` | Ingest a synthetic-scenario tool's output. | `.c1` PASS through the same reader and ingest-map path as a measurement · FAIL any privileged code path |

### 4.6 `OUT` — output and artifacts

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-OUT-01` | `SYS-0110` | `S-CHAIN4` | Disable every exporter and run. | `.c1` PASS completes successfully · FAIL it errors<br>`.c2` PASS a run manifest is still written · FAIL none |
| `SYT-OUT-02` | `SYS-0111` | `S-TINY` | Export to each of the three formats; attempt to re-read each. | `.c1` PASS each round-trips or is registered write-only · FAIL any non-round-trip format is readable as an input |
| `SYT-OUT-03` | `SYS-0113` | `S-BULK` | Export two named ports over a ten-second window. | `.c1` PASS exactly those ports and that window · FAIL any extra or missing |
| `SYT-OUT-04` | `SYS-0114` | `S-LIBDIR` | Take each artifact alone to another machine. | `.c1` PASS it identifies the run that produced it · FAIL any artifact is anonymous |
| `SYT-OUT-05` | `SYS-0115` | `S-FOREIGN` | Export and re-import. | `.c1` PASS every field of `SYS-0029` survives, including origin and mode · FAIL any lost |
| `SYT-OUT-06` | `SYS-0116` | `S-CHAIN4` | Set mixed record policies; then exclude an input a simulated stage consumes. | `.c1` PASS a reader of the artifact alone answers *"was this complete?"* for **every** port · FAIL any port has no policy entry<br>`.c2` PASS excluding a consumed input is a load error at record time · FAIL accepted |
| `SYT-OUT-07` | `SYS-0117` | `S-LONG` | ⊘ Estimate before a run; compare against actual; then set a budget the estimate exceeds. | `.c1` PASS within the stated factor · FAIL outside — **factor not supplied**<br>`.c2` PASS the campaign refuses to start over budget · FAIL it starts |
| `SYT-OUT-08` | `SYS-0118` | `S-BULK` | Build a scene containing an image; then exceed the per-scene budget. | `.c1` PASS the image is referenced by topic and time, not inlined · FAIL inlined<br>`.c2` PASS exceeding the budget is an error **naming the layer** · FAIL an unnamed error |
| `SYT-OUT-09` | `SYS-0119` | `S-CHAIN4` | Produce a merged output; open it with the source recording absent. | `.c1` PASS it opens · FAIL it needs the source<br>`.c2` PASS origin tags distinguish passed-through from simulated per port · FAIL indistinguishable |
| `SYT-OUT-10` | `SYS-0120` | `S-CHAIN4` | Record a run; compare the topic list against the pipeline's port manifests. | `.c1` PASS no declared port absent without an explicit policy entry · FAIL any silently missing |
| `SYT-OUT-11` | `SYS-0121` | `S-TINY` | Add a new format; count consumer files changed. | `.c1` PASS one reader, one writer, no consumer file changed · FAIL any consumer changes<br>`.c2` PASS no consumer can learn the format · FAIL any branches on it |
| `SYT-OUT-12` | `SYS-0122` | `S-TINY` | Attempt to re-execute an export. | `.c1` PASS refused by capability check, naming the missing capability · FAIL refused by convention, or accepted |
| `SYT-OUT-13` | `SYS-0123` | `S-CHAIN4` | Read every manifest field across a set of runs, including ones where a field cannot be filled. | `.c1` PASS every listed field present, each a value or explicit *unknown* · FAIL any missing<br>`.c2` PASS an unfillable field never carries a plausible default · FAIL any does |
| `SYT-OUT-14` | `SYS-0125` | `S-TWOHOST` | Craft a case per exit code on both platforms. | `.c1` PASS each produced, the set closed and published · FAIL any collision or undocumented code<br>`.c2` PASS the same case yields the same code on both platforms · FAIL any differs |
| `SYT-OUT-15` | `SYS-0126` | `S-TWOHOST` | Capture console and structured output on both platforms. | `.c1` PASS every event is a member of the published vocabulary · FAIL any outside it<br>`.c2` PASS byte-comparable across platforms after normalising line endings · FAIL any encoding difference |

### 4.7 `PLR` — player and visualization

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-PLR-01` | `SYS-0128` | `S-LIBDIR` | Inspect views for engine pointers; build and run the engine with no GUI toolkit present. | `.c1` PASS no view holds one · FAIL any<br>`.c2` PASS the engine builds and runs · FAIL it requires a toolkit |
| `SYT-PLR-02` | `SYS-0129` | `S-CHAIN4` | Attach, detach and re-attach mid-run; compare against a control run with no player. | `.c1` PASS the run never stops · FAIL it does<br>`.c2` PASS port values unchanged from the control · FAIL the player perturbs the run |
| `SYT-PLR-03` | `SYS-0132` | `S-PLANTED` | Grep the player's source for component and function tokens. | `.c1` PASS clean, re-run every build · FAIL any hit<br>`.c2` PASS the grep fails on the planted violation · FAIL it passes |
| `SYT-PLR-04` | `SYS-0133` | `S-CHAIN4` | Behind the head: seek, scrub, step back, re-render. Count module invocations in the cycle trace. | `.c1` PASS zero · FAIL any re-execution |
| `SYT-PLR-05` | `SYS-0134` | `S-CHAIN4` | Rewind, then attempt to resume forward by every available input sequence. | `.c1` PASS exactly two named choices offered — skip to head, or recompute from the start · FAIL a third path<br>`.c2` PASS neither silent continuation nor interpolation is reachable · FAIL either is |
| `SYT-PLR-06` | `SYS-0135` | `S-CHAIN4` | Exercise play, pause, step forward, step backward, jump to time, jump to marker. | `.c1` PASS each lands on the exact target tick · FAIL any off-by-one |
| `SYT-PLR-07` | `SYS-0136` | `S-FOREIGN` | Exercise each of the five step granularities. | `.c1` PASS each lands on its stated boundary · FAIL any<br>`.c2` PASS the cycle granularity lands on a tick whose input set is complete · FAIL a partial cycle |
| `SYT-PLR-08` | `SYS-0137` | `S-CHAIN4` | Start advance-N; cancel mid-way. | `.c1` PASS the session sits at a well-defined tick, never mid-tick · FAIL a partial tick<br>`.c2` PASS progress and cancel are both available · FAIL either missing |
| `SYT-PLR-09` | `SYS-0138` | `S-LONG` | Request a speed the machine cannot sustain. | `.c1` PASS the **achieved** speed is displayed · FAIL the requested one is shown |
| `SYT-PLR-10` | `SYS-0139` | `S-CHAIN4` | Mark a section; replay it; then reproduce headlessly from the saved configuration. | `.c1` PASS boundaries are exact ticks · FAIL approximate<br>`.c2` PASS reproducible headlessly · FAIL GUI-only |
| `SYT-PLR-11` | `SYS-0140` | `S-DIVERGE` | Open a run carrying markers, a divergence point and a coherence violation. | `.c1` PASS all three appear on the timeline · FAIL any missing<br>`.c2` PASS each is clickable and lands on its tick · FAIL any inert |
| `SYT-PLR-12` | `SYS-0141` | `S-CFGSET` | Two engineers open the same layout file; then save an interactive change back. | `.c1` PASS identical arrangement · FAIL any difference<br>`.c2` PASS the change saves back to a layout file · FAIL it is lost |
| `SYT-PLR-13` | `SYS-0142` | `S-CHAIN4` | Toggle a registered layer. | `.c1` PASS no player code required · FAIL the player must know the layer<br>`.c2` PASS re-renders without re-executing any module · FAIL it re-executes |
| `SYT-PLR-14` | `SYS-0143` | `S-LIBDIR` | Register the same short layer name from two plugins; then register outside a declared namespace. | `.c1` PASS both coexist with no central registry · FAIL a collision<br>`.c2` PASS the out-of-namespace registration is refused, naming both · FAIL accepted |
| `SYT-PLR-15` | `SYS-0144` | `S-CFGSET` | Set a layer default-off; set a parameter scoped to one view. | `.c1` PASS default-off holds on first open · FAIL it opens visible<br>`.c2` PASS the parameter does not affect the same layer in another view · FAIL it leaks |
| `SYT-PLR-16` | `SYS-0145` | `S-LIBDIR` | Open a recording with no user layout; then reset after customising. | `.c1` PASS a populated arrangement, not an empty grid · FAIL empty<br>`.c2` PASS the user's layout wins, and reset returns to the default · FAIL either |
| `SYT-PLR-17` | `SYS-0146` | `S-PLANTED` | Static-check layer-provider imports; change the token table. | `.c1` PASS a provider importing a renderer, plotting library or GUI toolkit fails the check · FAIL it passes<br>`.c2` PASS the token change propagates to every rendered surface consistently · FAIL any surface diverges |
| `SYT-PLR-18` | `SYS-0147` | `S-CHAIN4` | ⊘ Regenerate a specification figure from a recording; compare against the live rendering. | `.c1` PASS pixel-comparable within the declared tolerance · FAIL outside — **tolerance not supplied** |
| `SYT-PLR-19` | `SYS-0148` | `S-CHAIN4` | Inspect layers for callbacks; render one twice with identical inputs. | `.c1` PASS no layer registers a callback · FAIL any<br>`.c2` PASS identical output, and the layer is unit-testable in isolation · FAIL differing output |
| `SYT-PLR-20` | `SYS-0149` | `S-LIBDIR` | Author a plugin naming a port relative to its own component; then one whose reference resolves against no manifest. | `.c1` PASS resolution happens once, at load · FAIL per-tick resolution, or a spelled raw address<br>`.c2` PASS an unresolvable reference is an authoring error naming the plugin, the requested port and every port the manifest declares · FAIL **an empty layer — which on screen is indistinguishable from "the algorithm did not fire"** |
| `SYT-PLR-21` | `SYS-0150` | `S-CHAIN4` | Render one visualization over simulated data, then over replayed data. | `.c1` PASS identical rendering with no branch on origin · FAIL any branch<br>`.c2` PASS the plugin reads no algorithm-library memory · FAIL it does |
| `SYT-PLR-22` | `SYS-0151` | `S-CHAIN4` | Address one port in a plot panel, an export, an override and an evidence query. | `.c1` PASS identical addressing in all four · FAIL plots use a separate mechanism |
| `SYT-PLR-23` | `SYS-0152` | `S-CHAIN4` | Take two snapshots of one cycle; then interrupt a snapshot write. | `.c1` PASS the two hash equal · FAIL any difference<br>`.c2` PASS the interruption leaves **neither** file · FAIL a partial frame or an orphaned sidecar |
| `SYT-PLR-24` | `SYS-0153` | `S-CHAIN4` | For a sampled set of prims, layers and plotted samples, ask for evidence in one action. | `.c1` PASS port, topic, tick, origin, source timestamp, bundle, build, and published-vs-reconstructed all present · FAIL any missing<br>`.c2` PASS a field it cannot fill reads *unknown* · FAIL any plausible-looking default — *on the one surface whose whole purpose is being believed* |
| `SYT-PLR-25` | `SYS-0154` | `S-CHAIN4` | Query a sampled set of addresses through the panel and the command line; then search for a second producer. | `.c1` PASS field-for-field identical · FAIL any difference<br>`.c2` PASS no second code path can produce an evidence answer · FAIL one exists |
| `SYT-PLR-26` | `SYS-0156` | `S-BULK` | Measure engine-boundary bytes with context video active and inactive. | `.c1` PASS equal · FAIL display-only data is routed through the engine |
| `SYT-PLR-27` | `SYS-0157` | `S-BULK` | Seek past 1,000 frames; inspect the visual treatment of display-only data. | `.c1` PASS only rendered frames decoded · FAIL all 1,000<br>`.c2` PASS visually distinguished without opening a menu · FAIL indistinguishable from simulation data |

### 4.8 `CFG` — launcher and configuration

`SYT-CFG-24`/`25` are the renumbered identifiers of `SYS-0287`/`SYS-0288` — see **§6**.

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-CFG-01` | `SYS-0158` | `S-CHAIN4` | Enumerate every mode/implementation combination in the UI and in configuration. | `.c1` PASS every configuration-expressible combination is reachable in the UI · FAIL any missing<br>`.c2` PASS nothing in the UI is inexpressible in configuration · FAIL a GUI-only capability |
| `SYT-CFG-02` | `SYS-0159` | `S-CHAIN4` | Select a broken chain in the launcher. | `.c1` PASS blocked **on selection, before launch is pressed** · FAIL blocked at launch<br>`.c2` PASS remedies textually identical to the headless message · FAIL reworded |
| `SYT-CFG-03` | `SYS-0160` | `S-CHAIN4` | Start a run from the GUI; re-run headlessly from the saved file. | `.c1` PASS identical port values · FAIL any difference — *which would prove hidden state* |
| `SYT-CFG-04` | `SYS-0161` | `S-CHAIN4` | From an empty state, add a recording, select a layout, start a run. Count interactions. | `.c1` PASS within the bounded count, recorded in the demonstration · FAIL above it |
| `SYT-CFG-05` | `SYS-0162` | `S-TWOHOST` | Present a module with no binary for the running platform. | `.c1` PASS shown unavailable **before launch** · FAIL surfaced as a load failure after |
| `SYT-CFG-06` | `SYS-0163` | `S-CHAIN4` | Compare the launcher's per-recording feasible set against headless `probe`. | `.c1` PASS the sets are equal · FAIL any difference |
| `SYT-CFG-07` | `SYS-0164` | `S-CFGSET` | Set one value in each of the four layers; resolve. | `.c1` PASS later wins in every pair · FAIL any precedence inversion<br>`.c2` PASS `explain` reports the source layer of every resolved value · FAIL any unattributed |
| `SYT-CFG-08` | `SYS-0165` | `S-SPEC`, `S-STUB` | Emit a spec; run the engine with the configuration tree deleted; re-run the same spec hash. | `.c1` PASS the engine needs no configuration-language parser, no inference, no validation, no search-path logic · FAIL any is required<br>`.c2` PASS the same spec hash produces the same results · FAIL divergence |
| `SYT-CFG-09` | `SYS-0166` | `S-LIBDIR` | Resolve; then change the search path and re-run. | `.c1` PASS paths absolute and pre-resolved, the choice recorded · FAIL any stem or relative path<br>`.c2` PASS the search-path change cannot alter which binary loads · FAIL it can |
| `SYT-CFG-10` | `SYS-0167` | `S-CHAIN4` | Introduce a deliberate disagreement between the engine's loaded graph and the configuration layer's prediction. | `.c1` PASS detected by automated comparison · FAIL only a reader could notice |
| `SYT-CFG-11` | `SYS-0168` | `S-CFGSET` | Trigger every class of schema error. | `.c1` PASS file, line, wrong value and allowed values present in **every** message · FAIL any element missing |
| `SYT-CFG-12` | `SYS-0169` | `S-CFGSET` | Introduce a typo'd key. | `.c1` PASS the load fails · FAIL a warning<br>`.c2` PASS near matches offered · FAIL none |
| `SYT-CFG-13` | `SYS-0170` | `S-CFGSET` | Load a file with a future version; then one with none. | `.c1` PASS the future version is refused naming both · FAIL best-guessed<br>`.c2` PASS the missing version is refused naming the omission · FAIL defaulted |
| `SYT-CFG-14` | `SYS-0171` | `S-CFGSET`, `S-CHAIN4` | Craft one invalid configuration per entry in the error catalogue; attempt each. | `.c1` PASS every one fails **before the first cycle** · FAIL any first observable during execution<br>`.c2` PASS every failure names both ends · FAIL any names one |
| `SYT-CFG-15` | `SYS-0172` | `S-CFGSET` | Read then write every file in the corpus. | `.c1` PASS byte-identical, including comments and ordering where the format preserves them · FAIL any reformatting |
| `SYT-CFG-16` | `SYS-0173` | `S-CFGSET` | Reference one fragment from two configurations. | `.c1` PASS identical resolved values in both · FAIL divergence<br>`.c2` PASS `explain` names the fragment as the source layer · FAIL it names the including file |
| `SYT-CFG-17` | `SYS-0174` | `S-CFGSET` | Swap the layout; then swap the ingest map. | `.c1` PASS swapping the layout touches no composition file · FAIL it does<br>`.c2` PASS swapping the ingest map touches no connections file · FAIL it does |
| `SYT-CFG-18` | `SYS-0175` | `S-CHAIN4` | A representative engineer performs each change in the stated set, unaided; the diff is captured and the elapsed time recorded as an observation. | `.c1` PASS each completed unaided, with the diff touching exactly its declared file set and no rebuild · FAIL assistance or a framework edit needed, or the diff reaches a file outside the set<br>`.c2` PASS lines-of-configuration per project is tracked across releases · FAIL untracked<br>`.c3` PASS the elapsed times are recorded and reported as observations · FAIL not recorded — **an observation, deliberately not a bound (`OQ-16`)** |
| `SYT-CFG-19` | `SYS-0176` | `S-LIBDIR` | Run a project from a read-only installation of the package. | `.c1` PASS it runs · FAIL anything must be added to the installation |
| `SYT-CFG-20` | `SYS-0177` | `S-LIBDIR` | Edit a calibration value in the bundle and re-run; then compare what the viewer read against what the module was initialised with. | `.c1` PASS no rebuild required · FAIL configuration is compiled in<br>`.c2` PASS the viewer reads the same bundle and **states which** · FAIL the two agree only by coincidence |
| `SYT-CFG-21` | `SYS-0178` | `S-LIBDIR`, `S-CHAIN4` | Make two modules disagree about a shared vehicle parameter; separately, use modules from two projects. | `.c1` PASS the shared-parameter disagreement is a hard error with no escape · FAIL a warning or an escape exists<br>`.c2` PASS the project disagreement warns and records the escape · FAIL it errors, or the escape is unrecorded |
| `SYT-CFG-22` | `SYS-0179` | `S-LIBDIR` | Craft a bundle containing a simulation-only file. | `.c1` PASS refused, naming the file · FAIL accepted<br>`.c2` PASS what a module believes about a sensor and what the tooling feeds it stay separately addressable · FAIL merged |
| `SYT-CFG-23` | `SYS-0180` | `S-LIBDIR` | Switch project; then render a fallback footprint. | `.c1` PASS the picture changes · FAIL geometry comes from a module constant<br>`.c2` PASS the fallback is identifiable on screen without opening a file · FAIL drawn as a measurement |
| `SYT-CFG-24` | `SYS-0287` | `S-CFGSET`, `S-LIBDIR` | Emit a spec; trace every content-dependent field to its source. Then approve a configuration against a probe and change the file underneath. | `.c1` PASS every content-dependent field filled from the probe pass and no other source · FAIL any inferred or defaulted<br>`.c2` PASS both index and manifest are read through the same interfaces the run uses · FAIL a second reader exists |
| `SYT-CFG-25` | `SYS-0288` | `S-INDEX` | Run coherence classification, cut feasibility, ingest-family matching and mode validation against a hand-written index and manifest set. | `.c1` PASS all four run with no file opened and no library loaded · FAIL any opens one<br>`.c2` PASS each receives the structures as arguments · FAIL any fetches them itself |

### 4.9 `BAT` — batch, campaigns and headless

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-BAT-01` | `SYS-0181` | `S-CHAIN4` | Wrap a scenario list around the developer's own run configuration. | `.c1` PASS it is the batch input unchanged · FAIL a second configuration format exists for batch |
| `SYT-BAT-02` | `SYS-0182` | `S-STUB-CRASH` | Segfault a module in one of ten runs. | `.c1` PASS the other nine are unaffected and the batch continues · FAIL any is disturbed<br>`.c2` PASS runs are separate processes, never threads · FAIL threads |
| `SYT-BAT-03` | `SYS-0183` | `S-STUB-CRASH` | Select each of the three isolation modes. | `.c1` PASS interactive yields an attachable debugger and a stack · FAIL neither<br>`.c2` PASS per-tick cost of batch isolation is zero · FAIL measurable per-tick overhead<br>`.c3` PASS per-stage isolated mode bisects which stage crashes · FAIL unavailable |
| `SYT-BAT-04` | `SYS-0184` | `S-CHAIN4` | Run concurrent runs; inspect artifact paths; open one directory alone. | `.c1` PASS no two write to the same path · FAIL a collision<br>`.c2` PASS a run's directory opens standalone · FAIL it needs siblings |
| `SYT-BAT-05` | `SYS-0185` | `S-STUB-CRASH` | Run ten with two failures. | `.c1` PASS ten results produced · FAIL the batch stops |
| `SYT-BAT-06` | `SYS-0186` | `S-STUB-CRASH`, `S-STUB-SLOW` | Produce each of the four outcomes, including a segfault that cannot report its own death. | `.c1` PASS all four individually producible and never collapsed · FAIL any two merge<br>`.c2` PASS the segfault is reported `crash`, judged from outside the worker · FAIL reported `fail` or lost |
| `SYT-BAT-07` | `SYS-0187` | `S-CHAIN4` | Produce the aggregate; reconcile against the individual manifests. | `.c1` PASS machine-readable and reconciling exactly · FAIL any row disagrees |
| `SYT-BAT-08` | `SYS-0188` | `S-STUB-CRASH` | Crash a run; reopen it in process on a developer machine from the crash record alone. | `.c1` PASS recording, configuration, last completed cycle, stderr and run id all present · FAIL any missing<br>`.c2` PASS the failure reopens from the record alone · FAIL the CI machine is needed |
| `SYT-BAT-09` | `SYS-0189` | `S-CHAIN4` | Sweep one parameter over three values. | `.c1` PASS three runs whose manifests differ in exactly the swept value · FAIL any other difference |
| `SYT-BAT-10` | `SYS-0190` | `S-CHAIN4` | Interrupt after k of N; resume. | `.c1` PASS N results · FAIL fewer<br>`.c2` PASS no completed run re-executes · FAIL any does |
| `SYT-BAT-11` | `SYS-0191` | `S-STUB-SLOW` | Exceed the per-run timeout; separately, exceed the memory limit. | `.c1` PASS terminated and reported `timeout` · FAIL merged with the resource failure<br>`.c2` PASS the memory case reports a resource failure, distinctly · FAIL merged |
| `SYT-BAT-12` | `SYS-0192` | `S-CHAIN4` | Run with the default policy and a shuffled list; then with `none`. | `.c1` PASS default: identical per-run outputs under shuffling · FAIL order dependence<br>`.c2` PASS `none`: order dependence is demonstrable · FAIL it is not — **without this the first case has no power**<br>`.c3` PASS the chosen policy is recorded in the manifest · FAIL unrecorded |
| `SYT-BAT-13` | `SYS-0193` | `S-DAMAGED` | Exercise each of the four read-error behaviours. | `.c1` PASS each demonstrable · FAIL any<br>`.c2` PASS skipped packages counted, reported, and the run flagged · FAIL a skipping run is mistakable for a clean one |
| `SYT-BAT-14` | `SYS-0194` | `S-LONG` | Run a batch of N over one recording. | `.c1` PASS index build cost appears once · FAIL once per run |
| `SYT-BAT-15` | `SYS-0195` | `S-CHAIN4` | Run in a container with no GUI toolkit and no display variable. | `.c1` PASS it completes · FAIL any prompt, GUI library or display requirement |
| `SYT-BAT-16` | `SYS-0198` | `S-STUB-SLOW` | Hang a module with the watchdog on; then attach a debugger. | `.c1` PASS the watchdog fires · FAIL it does not<br>`.c2` PASS attaching suppresses it **without a configuration edit** · FAIL it fires during a debugging session |
| `SYT-BAT-17` | `SYS-0199` | `S-CHAIN4` | Read the per-module timing report. | `.c1` PASS wall time attributed per module and reconciling with total run time · FAIL unattributed time |
| `SYT-BAT-18` | `SYS-0200` | `S-CHAIN4` | Exercise each capability in the stated list from a plain script. | `.c1` PASS each within the declared line count, no command line and no window · FAIL any above it<br>`.c2` PASS no capability is GUI-only · FAIL one is |

### 4.10 `REC` — recording preparation

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-REC-01` | `SYS-0220` | `S-DAMAGED` | Run the integrity check over the four injected defect classes. | `.c1` PASS each class detected · FAIL any missed<br>`.c2` PASS each individually reported · FAIL collapsed into one finding |
| `SYT-REC-02` | `SYS-0221` | `S-DAMAGED` | Use the integrity result as a gate. | `.c1` PASS the damaged recording is refused **before producing any result** · FAIL it produces one first |
| `SYT-REC-03` | `SYS-0222` | `S-TINY` | Run twice over one file; then modify the file and run again. | `.c1` PASS the same hash twice · FAIL differing<br>`.c2` PASS the modified file records a different hash and is not accepted as the same input · FAIL silently accepted |
| `SYT-REC-04` | `SYS-0223` | `S-BULK` | Extract by time range and port selection; use the extract as input. | `.c1` PASS exactly the requested range and ports · FAIL any extra or missing<br>`.c2` PASS directly usable as input · FAIL it needs conversion |
| `SYT-REC-05` | `SYS-0224` | `S-TINY` | Convert between a permitted codec pair; then attempt a pair whose capabilities forbid it. | `.c1` PASS conversion follows from the capability table · FAIL a special-cased feature<br>`.c2` PASS the forbidden pair refuses, naming the missing capability · FAIL it proceeds lossily |
| `SYT-REC-06` | `SYS-0225` | `S-FOREIGN` | Inspect a recording; then run over it and compare. | `.c1` PASS the listing matches what the run actually reads · FAIL any disagreement |
| `SYT-REC-07` | `SYS-0226` | `S-TINY` | Derive twice in a chain; read the third artifact. | `.c1` PASS lineage survives both derivations · FAIL broken at the second<br>`.c2` PASS the original is identifiable from the third · FAIL it is not |
| `SYT-REC-08` | `SYS-0227` | `S-DAMAGED` | Run every preparation verb with no module library installed. | `.c1` PASS each runs · FAIL any requires the engine<br>`.c2` PASS its output is directly usable as engine input · FAIL a conversion step is needed |
| `SYT-REC-09` | `SYS-0228` | `S-FOREIGN` | Declare a module traced whose outputs are absent from the file; set it `measured`. | `.c1` PASS refused at load, naming the module and the missing ports · FAIL it fails at cycle 0 |
| `SYT-REC-10` | `SYS-0229` | `S-BULK` | Declare a per-cycle size budget; measure a port family that exceeds it. | `.c1` PASS reported **before a test drive** · FAIL discovered after |

### 4.11 `DIA` — diagnostics and debugging

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-DIA-01` | `SYS-0202` | `S-CHAIN4` | Run `explain`; instrument module loads and message decodes. | `.c1` PASS no module loaded, no message decoded · FAIL either<br>`.c2` PASS resolved spec with source layers, graph, schedule, injection boundary, coherence result and estimated duration all present · FAIL any missing |
| `SYT-DIA-02` | `SYS-0203` | `S-CHAIN4` | Tap an internal port by naming it; then untap. | `.c1` PASS it appears with full provenance, no code change · FAIL a code change is needed<br>`.c2` PASS untapping has no other effect · FAIL residue remains |
| `SYT-DIA-03` | `SYS-0204` | `S-STUB2` | Enable the cycle trace over a multi-rate graph. | `.c1` PASS every module accounted for on every tick, **including held ones** · FAIL held modules omitted<br>`.c2` PASS timing reconciles with `SYS-0199` · FAIL disagreement |
| `SYT-DIA-04` | `SYS-0205` | `S-RUNPAIR` | Diff two runs; then a run against a recording. | `.c1` PASS first diverging tick, port, field and the bound in force all reported · FAIL any missing<br>`.c2` PASS a bare pass/fail is never produced · FAIL it is |
| `SYT-DIA-05` | `SYS-0206` | `S-DAMAGED` | Complete a run producing warnings in several categories. | `.c1` PASS counts reconcile exactly with the structured log · FAIL any disagreement |
| `SYT-DIA-06` | `SYS-0207` | `S-CHAIN4` | Misspell one name of each kind. | `.c1` PASS the correct suggestion for each kind · FAIL any bare failure |
| `SYT-DIA-07` | `SYS-0208` | `S-BROKENENV` | Run the environment report against each of the four faults. | `.c1` PASS each fault reported · FAIL any missed<br>`.c2` PASS it exits normally in **every** case · FAIL it raises — *a diagnostic that crashes on a broken environment is useless exactly when it is needed* |
| `SYT-DIA-08` | `SYS-0209` | `S-BROKENENV` | Enumerate every emittable error. | `.c1` PASS each is a taxonomy member carrying expected, found, where and hint · FAIL any missing a field<br>`.c2` PASS an error outside the taxonomy fails a static check · FAIL it passes |
| `SYT-DIA-09` | `SYS-0210` | `S-CHAIN4` | Ask for a value's provenance from the command line and from a script. | `.c1` PASS both answer, identically to `SYT-PLR-24`/`25` · FAIL any divergence |
| `SYT-DIA-10` | `SYS-0211` | `S-CHAIN4` | For each CLI verb, invoke the scripted equivalent. | `.c1` PASS an equivalent exists for every verb · FAIL any gap<br>`.c2` PASS the same artifacts are produced · FAIL any difference |
| `SYT-DIA-11` | `SYS-0212` | `S-STUB`, `S-TWOHOST` | Attach to the engine; break inside a module. | `.c1` PASS the breakpoint is hit on **both** platforms · FAIL either |
| `SYT-DIA-12` | `SYS-0213` | `S-STUB` | Start with wait-for-debugger. | `.c1` PASS the printed process id is attachable · FAIL it is not<br>`.c2` PASS execution does not begin until attach · FAIL it starts |
| `SYT-DIA-13` | `SYS-0214` | `S-CHAIN4` | Set each of the four break conditions. | `.c1` PASS each halts at the correct point · FAIL any overshoots or misses |
| `SYT-DIA-14` | `SYS-0215` | `S-CHAIN4` | Step through a cycle in a debugger; compare results against an unstepped run. | `.c1` PASS identical · FAIL stepping changes results |
| `SYT-DIA-15` | `SYS-0216` | `S-SPEC` | Launch the engine from a Resolved Run Spec; inspect the process. | `.c1` PASS no interpreter frames in the debugging session · FAIL any<br>`.c2` PASS the executable holds no parser, validation, search or inference · FAIL any present |
| `SYT-DIA-16` | `SYS-0217` | `S-TWOHOST` | A new engineer attaches a debugger using only shipped material, on both platforms. | `.c1` PASS succeeds on both, recorded · FAIL either requires local knowledge<br>`.c2` PASS launch configurations ship for common environments on both · FAIL any missing |
| `SYT-DIA-17` | `SYS-0218` | `S-CHAIN4` | Re-execute one cycle from a saved state. | `.c1` PASS identical outputs to that cycle in the full run · FAIL any difference |
| `SYT-DIA-18` | `SYS-0219` | `S-STUB-CRASH` | Crash a module; take the reproducer package to another machine. | `.c1` PASS the crash reproduces with nothing else from the original environment · FAIL it needs more |

### 4.12 `NFR` — performance, determinism, portability, usability

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-NFR-01` | `SYS-0230` | `S-BULK` | Run a function alone over a recording containing camera data. | `.c1` PASS zero image bytes decoded · FAIL any<br>`.c2` PASS bytes-read reported and compared against the theoretical minimum · FAIL unreported |
| `SYT-NFR-02` | `SYS-0231` | `S-BULK` | Run a signal-only graph over a multi-camera recording. | `.c1` PASS no image decode · FAIL eager decoding |
| `SYT-NFR-03` | `SYS-0232` | `S-LONG` | ⊘ Run a six-second slice of a twenty-minute recording. | `.c1` PASS wall time scales with slice within the declared factor · FAIL with file length — **factor not supplied** |
| `SYT-NFR-04` | `SYS-0233` | `S-BULK` | Profile a representative run's per-message path. | `.c1` PASS no per-element conversion · FAIL any<br>`.c2` PASS no scripting-layer frame inside the per-message path · FAIL any |
| `SYT-NFR-05` | `SYS-0236` | `S-CHAIN4` | Run one spec at several core counts. | `.c1` PASS outputs and execution order invariant · FAIL either varies<br>`.c2` PASS no intra-run thread pool exists · FAIL one does |
| `SYT-NFR-06` | `SYS-0237` | `S-CHAIN4` | Read the run cost report. | `.c1` PASS all five figures present · FAIL any missing<br>`.c2` PASS they reconcile with each other and with the cycle trace · FAIL any disagreement |
| `SYT-NFR-07` | `SYS-0239` | `S-RUNPAIR`, `S-TWOHOST` | Repeat one run on both platforms. | `.c1` PASS byte-identical port values · FAIL any difference<br>`.c2` PASS no wall-clock dependency, no unseeded randomness, no thread-scheduling dependence · FAIL any |
| `SYT-NFR-08` | `SYS-0240` | `S-RUNPAIR` | Compare across all four axes. | `.c1` PASS each axis separately reported · FAIL any merged<br>`.c2` PASS a same-process divergence blocks · FAIL it is tolerated<br>`.c3` PASS a passing far axis prints headroom consumed · FAIL a bare pass |
| `SYT-NFR-09` | `SYS-0241` | `S-RUNPAIR` | Compare a pair differing in host **and** build. | `.c1` PASS reported inconclusive for both axes, naming both differences · FAIL accepted as evidence for the narrower axis<br>`.c2` PASS the axis is derived from the manifests · FAIL a flag declares it |
| `SYT-NFR-10` | `SYS-0242` | `S-RUNPAIR` | Compare two recordings of one deterministic run, differing in run id and timestamp. | `.c1` PASS they compare equal · FAIL a byte comparison reports a difference |
| `SYT-NFR-11` | `SYS-0243` | `S-RUNPAIR` | Declare a tolerance row with no reason; then an integer override; then pass a far axis. | `.c1` PASS the reasonless row is refused · FAIL accepted<br>`.c2` PASS integers and enumerations are exact and not overridable · FAIL overridable<br>`.c3` PASS a passing report prints tolerance used and headroom consumed · FAIL silent<br>`.c4` PASS the first two axes have no tolerance field at all · FAIL one exists to widen |
| `SYT-NFR-12` | `SYS-0244` | `S-RUNPAIR` | Force a divergence. | `.c1` PASS first diverging tick, port, field and bound reported · FAIL a bare pass/fail |
| `SYT-NFR-13` | `SYS-0245` | `S-STUB-CLOCK` | Introduce an undeclared source of non-determinism; then declare it. | `.c1` PASS caught by the fresh-process axis · FAIL it survives to a campaign<br>`.c2` PASS declaring it marks the run non-reproducible · FAIL unmarked |
| `SYT-NFR-14` | `SYS-0246` | `S-RUNPAIR` | Pin a re-execution to a build, then run against a different build; then against a local build. | `.c1` PASS refused, naming both hashes · FAIL accepted<br>`.c2` PASS a local build is reported unpinnable · FAIL silently accepted as pinned |
| `SYT-NFR-15` | `SYS-0247` | `S-TWOHOST` | Run the reference project's configuration set on both. | `.c1` PASS byte-identical files, same results · FAIL any platform-specific configuration<br>`.c2` PASS manifests declare a binary per platform and no configuration file names a platform · FAIL any does |
| `SYT-NFR-16` | `SYS-0248` | `S-TWOHOST` | Write a configuration on one platform; load on the other. | `.c1` PASS loads with no edit · FAIL a separator or case difference surfaces<br>`.c2` PASS no user-facing surface exposes a platform difference · FAIL any does |
| `SYT-NFR-17` | `SYS-0249` | `S-TWOHOST` | Load a library built with a non-conforming floating-point flag set. | `.c1` PASS a load-time warning naming the flag, **before its results are used** · FAIL silent, or warned after |
| `SYT-NFR-18` | `SYS-0250` | `S-TWOHOST` | Run the reference suite on both and compare. | `.c1` PASS differences are reported as defects · FAIL any tolerated as an environment difference |
| `SYT-NFR-19` | `SYS-0251` | `S-TWOHOST` | Submit a measurement with no platform attribution. | `.c1` PASS rejected by the reporting tooling · FAIL it depends on a reviewer noticing |
| `SYT-NFR-20` | `SYS-0263` | `S-CHAIN4` | Enumerate every execution path and look for its dry-run path. | `.c1` PASS every path has one · FAIL any capability executes without an explainable plan |
| `SYT-NFR-21` | `SYS-0264` | `S-BROKENENV` | Trigger every entry in the error catalogue. | `.c1` PASS every message contains an actionable instruction, verified by test · FAIL any verified only by review, or stating only what is wrong |
| `SYT-NFR-22` | `SYS-0265` | — | An engineer who did not build the tool completes the named onboarding path, unaided, recorded. | `.c1` PASS completed unaided within the seeded budget · FAIL assistance needed, or above the budget<br>`.c2` PASS documentation size per release measured and reported · FAIL untracked |

### 4.13 `CON` — extensibility, packaging and constraints

| ID | Serves | Fixture | Steps | Cases |
|---|---|---|---|---|
| `SYT-CON-01` | `SYS-0252` | `S-LIBDIR` | Exercise each template plugin against its conformance kit; then attempt a fifth extension point. | `.c1` PASS each of the four passes its kit · FAIL any<br>`.c2` PASS a fifth cannot be added without a requirement change · FAIL one can |
| `SYT-CON-02` | `SYS-0253` | `S-LIBDIR` | Open a recording produced elsewhere; then remove the plugin it names. | `.c1` PASS no code from the recording executes · FAIL any does<br>`.c2` PASS the missing plugin degrades to *these layers unavailable*, naming the expected hashes · FAIL a silent absence |
| `SYT-CON-03` | `SYS-0254` | `S-LIBDIR` | Present a plugin outside the declared version range. | `.c1` PASS refused, **not half-loaded** · FAIL partially imported<br>`.c2` PASS the decision is made without importing the plugin's code · FAIL the import happens first |
| `SYT-CON-04` | `SYS-0255` | `S-LIBDIR` | Point the player at a folder of installed libraries. | `.c1` PASS layers render with no sibling checkout, no interpreter path variable, no player rebuild · FAIL any is needed<br>`.c2` PASS plugins are authored in the component and copied by the build, with bundle-hash discipline · FAIL the checkout is the delivery mechanism |
| `SYT-CON-05` | `SYS-0257` | `S-TWOHOST` | Install the artifact on a clean machine; run `E2E-01`. | `.c1` PASS completes with nothing else fetched · FAIL any dependency is pulled<br>`.c2` PASS every listed component is present on both platforms · FAIL any missing |
| `SYT-CON-06` | `SYS-0258` | `S-LIBDIR` | Generate the compatibility matrix; then load a combination outside it. | `.c1` PASS the matrix is generated from the enforced constants · FAIL hand-maintained<br>`.c2` PASS the out-of-matrix combination is refused naming all three versions · FAIL accepted |
| `SYT-CON-07` | `SYS-0259` | `S-LIBDIR` | Run an out-of-range package against a pinned project. | `.c1` PASS refused, naming both · FAIL it runs |
| `SYT-CON-08` | `SYS-0260` | — | Run the shipped self-test on a clean machine. | `.c1` PASS passes with no project, no component library and no user recording · FAIL any is required |
| `SYT-CON-09` | `SYS-0261` | `S-CFGSET` | Migrate the previous release's reference configuration set. | `.c1` PASS the migrated set produces identical results · FAIL any difference<br>`.c2` PASS a migration guide ships · FAIL absent |
| `SYT-CON-10` | `SYS-0273` | `S-CHAIN4` | Implement two transports against one interface; inspect views for engine pointers. | `.c1` PASS both work with the interface unchanged · FAIL it changed<br>`.c2` PASS no view reads an engine pointer under any circumstance · FAIL any does |
| `SYT-CON-11` | `SYS-0274` | `S-PLANTED` | Run the framework-source check; then run it against the planted violation. | `.c1` PASS clean on every build · FAIL any hit<br>`.c2` PASS it fails on the planted violation · FAIL it passes — **a check nobody has seen fail is a check nobody should believe** |

---

## 5. Coverage

Bidirectional (`TV-1`): every `SYS` requirement has ≥1 test here or in the
Concept Test Specification; every test here serves ≥1 requirement.

**Counts are emitted by the checker, not maintained here** — a number derivable
from the document is a second stored copy, and a second copy drifts.

```
python docs/py/trace_check.py --counts
python docs/py/trace_check.py --matrix
```

---

## 6. Finding: six duplicate test identifiers in the System Requirements

**Found while deriving this document; not yet accepted.** It is recorded here
rather than fixed silently because renumbering a cited identifier is a change to
`SIM_System_Requirements_v0.1.md`, and `R-REQ-2` makes identifier allocation a
decision, not a formatting matter.

Six requirements cite a test identifier **already allocated to a different,
unrelated requirement**:

| Test id | Held by | Also claimed by | Related? |
|---|---|---|---|
| `SYT-TIM-14` | `SYS-0073` Sampling policy per port | `SYS-0283` Simulation time advances by one grid step | no |
| `SYT-TIM-15` | `SYS-0074` Missing-data policy per port | `SYS-0284` Reception time is not a header field | no |
| `SYT-TIM-16` | `SYS-0075` A repeat is visible to the consumer | `SYS-0285` Every declared period enters the grid | no |
| `SYT-TIM-17` | `SYS-0076` Topological order, printed | `SYS-0286` A recorded rate that contradicts a declared period | no |
| `SYT-CFG-14` | `SYS-0171` Validation at load | `SYS-0287` Resolution is two passes | no |
| `SYT-CFG-15` | `SYS-0172` Configuration round-trips | `SYS-0288` What the probe returns is data | no |

**Cause.** `SYS-0283`…`SYS-0288` are the six highest UIDs in the document — a
later insertion pass. Each was inserted into §8.1, §8.3 or §13 and took *the
next test number local to that subsection*, which had already been allocated by
§8.4 and §13's earlier rows. This is the precise failure
`skills/requirements_management.md` §2 step 1 warns about: allocate from the
highest identifier **across the module**, never from the highest in the section
being edited.

**Resolution applied in this document,** per `R-REQ-2` (allocated once, never
reused — so the *earlier* allocation stands and the later claimant moves):

| Requirement | Cited | Renumbered to |
|---|---|---|
| `SYS-0283` | `SYT-TIM-14` | **`SYT-TIM-21`** |
| `SYS-0284` | `SYT-TIM-15` | **`SYT-TIM-22`** |
| `SYS-0285` | `SYT-TIM-16` | **`SYT-TIM-23`** |
| `SYS-0286` | `SYT-TIM-17` | **`SYT-TIM-24`** |
| `SYS-0287` | `SYT-CFG-14` | **`SYT-CFG-24`** |
| `SYS-0288` | `SYT-CFG-15` | **`SYT-CFG-25`** |

`SIM_System_Requirements_v0.1.md`'s six `Verify` clauses are updated to match.
No `SYS` UID changes; no test identifier is deleted or reused.

**`SYT-TIM-10` is an unallocated gap** and is left unused. A gap costs nothing;
backfilling one is a mild form of reuse and would make a future reader's `grep`
for `SYT-TIM-10` ambiguous between "never existed" and "means this now".

**`E2E-08` is not part of this finding.** It is cited by `SYS-0124`, `SYS-0130`
and `SYS-0197`, and all three `Accept` clauses literally read *"`E2E-08`
completes…"* — one scenario is deliberately the acceptance vehicle for three
requirements. That is a shared test, not a collision.

**Prevention.** `TV-7` and the checker's duplicate-identifier check (added with
this document) make the next occurrence a build failure rather than a discovery.

---

## 7. What this document does not contain

- **Expected values** — they are the requirements' `Accept` clauses (§0.1).
- **Validation** — `SIM_Concept_Test_Spec_v0.1.md`. A row here that asks *"can
  the user do their job"* rather than *"does the boundary behave as specified"*
  was written at the wrong level and moves there.
- **Software-level tests** — `SIM_Software_Test_Spec_v0.1.md`.
- **Verification status** — `SIM_Test_Execution_<date>.md` (`R-REQ-6`,
  `ANL-51`). No status column appears here, deliberately.
- **Test code** — `SYS-0278` binds the identifier to the implementation; this
  document does not restate it.
