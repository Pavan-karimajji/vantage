# SIM v2 — Open Question Answers

**Working document.** Started 2026-08-12. The companion to
`SIM_Open_Questions_v0.1.md`: that document is the *register* (what is open,
who owns it, what it blocks); this one is the *worked answer* for each row.
The register stays the index — when a row here reaches `CLOSED`, the answer is
written back into the owning document and the register's row moves to its §4.

**This document does not move rows in the register.** It produces the argued
answer and names the write-back target. Moving the row is the last step, done
against the owning document, not here.

---

## 0. Method

### 0.1 The three verdicts

Every row below ends in exactly one of these. The distinction is not
politeness — it is who is allowed to be wrong.

| Verdict | Meaning |
|---|---|
| `CLOSED` | Answered here, from evidence in this repository or from an artifact that already decided it. The argument is written out so the answer can be attacked rather than merely quoted. Ready to write back |
| `NARROWED` | The answerable part is answered and the residue is named — what is still unknown, who can say, and **what it costs to leave it open**. A narrowed row does not block work; it carries a trigger |
| `PROPOSED` | **Deliberately not concluded.** Either the answer is a stakeholder's to give (organisational, commercial, legal, a number only the customer has), or every available answer enlarges the build. Options are laid out with a recommendation and the recommendation is *not* adopted by silence |

The rule that produced the split: **a question is answerable here if the
evidence is in the repository or in an artifact this project already
baselined.** A question is *not* answerable here if answering it would commit
someone else's budget, or would add a mechanism the plan does not have. Those
get `PROPOSED` however obvious the answer looks — an obvious answer adopted
without its owner is the same defect as no answer, discovered later.

### 0.2 Why the register's grouping was not reused

The register groups by **owner** (recording owner, module teams, algorithm
teams, process), which is the right shape for chasing people and the wrong
shape for answering. Answering wants questions that share a *mechanism*
grouped together, because the answer to one usually constrains the next: four
of the six groups below collapsed to a single argument once the questions were
read side by side, and two of them turned out to be already-answered by an
artifact nobody had re-read.

Six groups, twenty rows.

| # | Group | Rows | What the group turns on |
|---|---|---|---|
| `G1` | **The clocks** | `IFQ-01` `IFQ-02` `IFQ-06` `OQ-01` | Time is declared in one unit, converted in one place, and degraded explicitly — never estimated |
| `G2` | **What the compiled contract can already do** | `OQ-05` `OQ-06` `OQ-12` | Three questions addressed to module teams that the ABI in this repository answers without asking anyone |
| `G3` | **Recordings in, artifacts out** | `OQ-09` `OQ-10` `OQ-11` `OQ-22` | A format is a codec of four methods, so naming one costs a table row; what is genuinely open is never *which format* but *whether a real sample exists* |
| `G4` | **Where the knobs are** | `OQ-02` `OQ-04` `OQ-07` | All three ask "should the system do more here?" and all three were answered by an artifact that predates the question |
| `G5` | **Numbers nobody here can invent** | `OQ-14` `OQ-16` | An absolute threshold nobody can supply becomes a recorded baseline plus a regression bound — failable on day two without a guess on day one |
| `G6` | **Organisation** | `OQ-15` `OQ-17` `OQ-18` `OQ-19` | De-block by making the technical artifact independent of the organisational answer, then let the answer arrive late without cost |

### 0.3 Status board

Updated as each row concludes. `—` means not yet worked.

| Row | Group | Verdict | Write-back target |
|---|---|---|---|
| `IFQ-01` | `G1` | `NARROWED` — recommend `timestamp_ns`, reverses a stated default, needs one nod | `interfaces_signal_header_plan.md`; if ratified also `SW-0033` |
| `IFQ-02` | `G1` | `CLOSED` — required, non-decreasing, per port, binds source time | `SW-0050` accept text (3 refinements) |
| `IFQ-06` | `G1` | `CLOSED` — **two** fields, capture `optional`/unset | `interfaces_signal_header_plan.md`; `SW-0043`/`SW-0044` `Now.` lines |
| `OQ-01` | `G1` | `CLOSED` — measured per recording by `RecordingIndex`, not answered globally | Register §2; `SW-0410` |
| `OQ-05` | `G2` | `CLOSED` — a `sim probe` measurement; **three** ABI modules, not two | Register §3; `IT-22` candidate list |
| `OQ-06` | `G2` | `CLOSED` — no reset export; shutdown+init is exact, subprocess is exacter | `SYS-0048`, `SYS-0192` `Now.` lines |
| `OQ-12` | `G2` | `CLOSED` — unrepresentable over the ABI; residue is `SYS-0071` | `SYS-0066`/`SYS-0071`/`SYS-0072` notes |
| `OQ-09` | `G3` | `NARROWED` — one 10-second sample; blocks no `WP`, keeps `MP-1` provisional | Plan risk `R-8`; `WP-18` |
| `OQ-10` | `G3` | `CLOSED` — MCAP + write-only CSV; a preference is a codec row | `SYS-0111` `Now.`; drop from gate set |
| `OQ-11` | `G3` | `CLOSED` — derive the catalogue from manifests; adopt vocabulary only | `SW-0388` `Now.`; Design `A-4` |
| `OQ-22` | `G3` | `PROPOSED` — legal/commercial; contained by the codec seam; due per format | Register §2 → attach to format `WP`s |
| `OQ-02` | `G4` | `CLOSED` — no for `R1`; trigger restated as a per-recording rung condition | `SYS-0108` deferral note |
| `OQ-04` | `G4` | `CLOSED` — four levels exist, not two; the missing axis is closed on purpose | `SYS-0080`/`SYS-0082` notes; `R-SIM-15` |
| `OQ-07` | `G4` | `CLOSED` — pass a path, never a value; sweeps are bundle variants | `SYS-0177`/`SYS-0179` notes |
| `OQ-14` | `G5` | `NARROWED` — budget file + reference config closable; absolute target stays with owner | `SW-0369`/`SW-0323` `Now.` lines |
| `OQ-16` | `G5` | `NARROWED` — set already written in `SW-0348`; structural gate proposed | `SW-0348` `Now.` line; register row |
| `OQ-15` | `G6` | `PROPOSED` — vendor is the org's; `WP-01` de-blocked by splitting harness from trigger | `WP-01` split; register §2 |
| `OQ-17` | `G6` | `PROPOSED` — replace with the one-sentence binary; blast radius bounded | `SYS` §26 fallback note |
| `OQ-18` | `G6` | `PROPOSED` — three shapes, third recommended; architecture already neutral | Register §3 |
| `OQ-19` | `G6` | `PROPOSED` — reframed to *inputs*; answer with `OQ-15`'s retention half | Register §3; merge with `OQ-15` |

---

## 1. `G1` — The clocks

**The pool.** `IFQ-01` (unit), `IFQ-02` (monotonicity), `IFQ-06` (one stamp or
two), `OQ-01` (does the data carry cycle marking). Read separately they look
like four preferences. Read together they are one question — *what does a
producer know, and what may a reader infer from it?* — and answering it in that
form settles three of the four without the missing value file.

**The principle the group produced.** A time field exists on the wire **iff a
producer can fill it from its own knowledge**. Reception time fails that test
(reception happens after the producer is finished), which is why `SW-0044` puts
it in the envelope. Capture time passes it *conditionally* (a producer can
propagate it if its inputs carried one). Source time passes it
unconditionally. That single test decides `IFQ-06`, removes `IFQ-06`'s stated
dependency on `OQ-09`, and reframes `IFQ-01` as a risk question rather than a
taste question.

### 1.1 `IFQ-06` — one timestamp or two? · **`CLOSED` — two**

**Answer: two fields. `source_timestamp_*` is always filled;
`capture_timestamp_*` is `optional` and left unset when unknown.** This
reverses the register's *"one field now"* and, more usefully, removes its
conditionality on `OQ-09` — the bench capture no longer decides anything here.

Four reasons, in descending strength:

1. **`SW-0044` already requires it.** *"Validity time shall belong to the
   signal header and shall be explicitly unknown rather than defaulted."* A
   header with one stamp has nowhere to put validity, so the requirement is
   unsatisfiable as the schema stands. proto3 `optional` supplies exactly the
   presence semantics the requirement asks for: unset is distinguishable from
   zero, at no cost when unset.
2. **The two stamps have two different `R1` consumers.** Ladder rung 3
   (`SW-0050`) derives *cycle structure* and wants the producer's emit cadence
   — source time. `age_s` (`SW-0045`) asks *how old is this information* and
   wants validity — capture time. One field cannot serve both without one
   consumer silently reading the other's number, which is `SW-0044`'s
   "collapsed" failure arriving through the back door.
3. **`time_stamp`, today's name, is the name `SW-0044` forbids.** *"Never one
   name … the two names differ at every surface."* A field called `time_stamp`
   names neither clock, so whichever clock it turns out to hold, every reader
   has to be told out of band. Renaming it is not extra work — it is work the
   requirement already mandates, and it is free while the field is unproduced
   (`IFQ-04`: the three legacy messages are dummy).
4. **Adding the second field later is the expensive direction of a cheap
   change.** A new field number is wire-compatible, so "add it when needed"
   is technically available — but the schema check (`R-IFACE-4`), the eight-field
   `PortValue` (`SW-0043`), the evidence answer (`R-SIM-25`) and every export
   column would each move on that day. Declaring the shape now costs one
   `optional` field that most producers never set.

**What this does *not* claim.** It does not claim any component can fill
capture time in `R1`. Most cannot — propagating a measurement instant through a
fusion chain is component work nobody has scheduled. `R1` behaviour is
therefore: source filled, capture unset, `age_s` falling back to the hold
schedule exactly as `SW-0045` already permits (*"from validity time where
known and from the hold schedule otherwise"*). The fallback is written, so an
unset capture time is a declared state and not a gap.

**Trigger to revisit:** none. The field exists whether or not it is filled;
the day a producer can fill it, it fills it.

### 1.2 `IFQ-02` — is the stamp monotonic? · **`CLOSED`, with three refinements**

**Answer: required; a violation is reported and demotes the port to rung 4;
never clamped.** The register's answer stands and `SW-0050`'s acceptance text
already carries it, so this row is closed by an artifact rather than by a new
decision. Three refinements are added because each one prevents a check that
would be wrong in a way nobody would notice:

| # | Refinement | Why it matters |
|---|---|---|
| a | **Non-decreasing, not strictly increasing** | Two messages legitimately share a stamp — same cycle, two ports, or one port emitting twice within a period. A strict check fails correct data, and a check that cries wolf is a check that gets disabled |
| b | **Per port, never across ports** | Two producers share no clock discipline and owe each other no ordering. A cross-port check would flag a correct recording as broken and send someone hunting a producer bug that is not there |
| c | **It binds `source_timestamp_*`; an out-of-order `capture_timestamp_*` is reported but does not demote** | The demotion exists to protect *rung 3*, which is source time. Capture time feeds `age_s`, not cycle structure. Its failure mode is a **negative age**, and the answer to a negative age is to report it — never to clamp it to zero, which would manufacture the exact `0.0` that `R-SIM-14` and `NR-SIM-4` exist to keep distinguishable from a true one |

Refinement (c) is `IFQ-06`'s dividend: the question *"monotonic — which stamp?"*
was unanswerable while there was one field.

### 1.3 `OQ-01` — do the recordings carry task/cycle marking? · **`CLOSED` — it stopped being a question**

**Answer: it is not answered globally; it is *measured per recording*, by an
artifact that already exists.** `SW-0410`'s `RecordingIndex` reports, per topic,
*"the highest timing rung the data supports"*. So the question *"do the
recordings in scope carry task/cycle marking?"* is the value of a field that
`SI-13`'s probe pass computes before every run and that `sim probe` prints.

This is the same move that closed `SWQ-12` and `OQ-13`: the artifact answered
the question before it was asked, and nobody had re-read it. Three
consequences:

- **The register's "half-answered" framing dissolves.** There is no owned half
  and unowned half — there is one field, computed for our recordings and
  foreign ones alike.
- **Rung 1 being inert is now observable rather than assumed.** If no recording
  in scope carries a source cycle identifier, `RecordingIndex` says so on every
  file and rung 1 costs nothing. `SYS` §22 already argued the ladder's shape is
  right either way; this makes the claim checkable instead of reassuring.
- **The `SignalHeader` half is confirmed and dated:** once §1.1 lands, every
  platform-produced payload carries a header, so those recordings report rung 2
  by construction. The measurement will show it — it does not have to be
  believed.

**Residue, deliberately not carried as a question:** whether any *foreign*
recording reaches rung 1 or 2. That is `OQ-09`'s sample-file problem (§3.1),
and it now changes one printed field rather than a design.

### 1.4 `IFQ-01` — microseconds or nanoseconds? · **`NARROWED` — recommend reversing to `timestamp_ns`; needs one ratification**

**This row is deliberately not closed.** The register's standing default is
`timestamp_us` and it was argued on 2026-08-12. Reading it against the
repository weakens its decisive argument enough that adopting it *by silence*
would be adopting it for a reason that turns out not to hold — but reversing a
one-day-old, argued decision on a cross-component wire contract is a nod
somebody should give explicitly rather than something this document should take.

**The register's argument:** the period is fixed as `<COMPONENT>_<FN>_PERIOD_US`
in integer microseconds, so a nanosecond stamp "puts two units in adjacent
fields of one contract".

**What the repository shows:**

| Evidence | Where | Effect on the argument |
|---|---|---|
| `period_ns: 50000000` is a **live, consumed manifest field** | `modules/df/conf/ports.yaml:19` → `ComponentManifest.period_ns()`, read at `modules/df/src/platform/cm/src/host/cm_host.cpp:105` | The two units **already coexist** in a shipped contract. "One contract, one unit" is not a state being protected; it is a state that would have to be created, and creating it means changing the manifest field too |
| `period_us: 50000` per output port, declared as a fallback | `modules/df/conf/ports.yaml:40` | Both spellings sit in *one file*, by design (`OD-12`), each correct for its layer |
| *"Reception time and validity time as two distinct **integer-nanosecond** quantities … validity time shall belong to the signal header"* | `SW-0044` | The requirement that owns the header already calls its stamp a nanosecond quantity. A microsecond wire field is defensible only by reading that as *"after ingest"* |
| *"A period declared in configuration is integer microseconds and a fractional value is refused"* | `SW-0046` acceptance | Microseconds are mandated for **authored configuration**, which is a different kind of value from a measured stamp |

**The reframing that follows.** Unit agreement is worth having *within a kind of
value*, not across kinds. `PERIOD_US` is **authored** calibration whose
fractional values must be refusable. A timestamp is **measured**. Holding both
to one unit buys a slogan and costs a conversion — the ×1000 at ingest that the
register's own answer has to carve out in `SW-0033` and except in `ANL-SW-02`.
Nanoseconds delete the exception rather than documenting it.

**The risk asymmetry, which is the actual reason to prefer it.** The register
closes with *"still awaiting the value file; a source finer than 1 µs flips it
back"*. That is a dependency `timestamp_us` carries and `timestamp_ns` does
not: nanoseconds represent everything microseconds can, so the value file stops
being an input to this decision. Under an unresolved external input, the choice
that makes the input irrelevant is the cheaper one to be wrong about — and the
cost of being wrong is asymmetric too (µs wrong = truncated stamps in a shipped
wire contract; ns wrong = ~1 extra varint byte per message).

| | `timestamp_us` (standing default) | `timestamp_ns` (recommended) |
|---|---|---|
| Depends on the missing value file | **Yes** — a sub-µs source flips it | No |
| Conversions at ingest | ×1000, needing an `SW-0033` exception | None |
| Agrees with `SW-0044` as written | Only under a re-reading | Directly |
| Agrees with `PERIOD_US` | Yes | No — and, per above, need not |
| Cost of the wrong choice | Truncation in a wire contract | ≈1 byte per message |

**Recommendation: `source_timestamp_ns` / `capture_timestamp_ns`.**
**Ratification asked for, because this reverses a stated default** — silence
should leave `timestamp_us` standing, not adopt the reversal. If ratified, one
consequence travels with it: `SW-0033`'s "the only unit conversion in the
engine" carve-out is **removed**, not amended, and `ANL-SW-02`'s ban on unit
arithmetic needs no exception.

**One thing is settled either way and should be written back now:** the field
is **renamed** from `time_stamp` to a name that says which clock it is
(§1.1 reason 3). That is `SW-0044`'s explicit requirement and it does not wait
on the unit.

## 2. `G2` — What the compiled contract can already do

**The pool.** `OQ-05` (which modules are real), `OQ-06` (reset without
destroy), `OQ-12` (run-time rate change). The register addresses all three to
*module teams*. **All three are answered by one file in this repository** —
`modules/interfaces/include/adas/adas_sil_abi.h`, the generic ABI every SIL
library exports — plus a census that a command can reproduce.

**The principle the group produced.** *A question about what modules do is a
question about what the contract lets them do.* The ABI has exactly five
exports — `adasAbiVersion`, `adasManifest`, `adasInit`, `adasExec`,
`adasShutdown`. There is **no reset entry point and no rate-change entry
point**, and there is no per-module variation to survey, because a module
either speaks this ABI or is not a module. Asking eleven teams what their
libraries support would have produced eleven answers to a question the header
answers once — and, worse, would have invited a team to answer *"yes, through
our own extra symbol"*, which is how a generic ABI acquires a per-component
special case.

### 2.1 `OQ-05` — which components have real libraries? · **`CLOSED` — as a measurement, not a survey**

**Answer: the durable answer is `sim probe <lib>`, and the criterion is not
"functional" but "exports the ABI and a manifest".** `R-SIM-16` already makes a
component onboard itself by manifest; `SYS-0050` already forbids compile-time
linkage to any component. So the question *"what can `E2E-02`/`E2E-03`/`E2E-10`
and `IT-22` actually be planned against?"* is the output of a command, dated,
and it does not go stale in a document.

**Measured snapshot, 2026-08-12** (source lines exclude `build*/` and tests):

| Module | `src/` C++ lines | `conf/ports.yaml` | `sim/` plug-ins | Reading |
|---|---:|:---:|:---:|---|
| `df` | 9 215 | ✔ | ✔ | **Functional.** Two real functions (`aeb`, `bsd`), generated port shim, CarMaker host |
| `sil_host` | 1 155 | — | — | Functional, but it is the **host**, not a module under test |
| `perception-core` | 517 | ✔ | ✔ | **On the ABI**: `perception_core_interface_c.cpp` + three detector/tracker units |
| `vdy` | 409 | ✔ | — | **On the ABI**: `vdy_interface_c.cpp`, one component unit, manifest dump |
| `mathlib` | 52 | — | — | A library, not a module — no ports, correctly |
| `interfaces`, `shared_config` | 0 | — | — | Contract/data repos — no library by design |
| `isp`, `perception-lane`, `planning`, `platform-services` | 0 | — | — | **Structural only** — no C++ source at all |

**One correction to the register.** Its `OQ-05` row reads *"`df` and `vdy` are
the two with generated port manifests"*. **There are three** —
`perception-core` carries `conf/ports.yaml` and a SIL C interface as well. That
matters directly: `IT-22`'s *"a second component completes the checklist
unaided"* has a **third** candidate, and `perception-core` is the more
interesting one because it sits upstream of `df` on a real data path, so
`E2E-03`-style multi-module wiring can be planned without waiting for anything.

**What genuinely remains, and why it is not carried as a question.** Whether
the other four are *functional* rather than structural is not open — they have
**zero C++ source**, so the answer is structural, today, measurably. When one
gains a library it gains a manifest, and `sim probe` reports it the same day.
The only real judgement left is per test — *"does this assertion need a braking
decision, or just a port that moves?"* — and that belongs in the test's own
row, not in a global census.

### 2.2 `OQ-06` — do modules support reset without destroy? · **`CLOSED` — no, and it is an optimisation rather than a requirement**

**Answer: no module supports it and none can, because the ABI has no reset
export. Nothing depends on that, because `adasShutdown` + `adasInit` is an
exact reset for all handle-scoped state and needs zero module changes.**

`SYS-0048` names the lifecycle `create → configure → init → step (many) →
reset → destroy`, and `SYS-0192` defaults to *reset-and-init before each
entry*. Both are satisfiable **today**:

| Lifecycle transition | Implemented as | Cost |
|---|---|---|
| create · configure · init | `adasInit(configPath)` | Re-reads and re-parses the config bundle |
| step | `adasExec(handle, dtS, in, out)` | — |
| **reset** | `adasShutdown(handle)` then `adasInit(...)` | One bundle re-parse per batch entry |
| destroy | `adasShutdown(handle)` | — |

**The one real hazard, and the fact that it is already detected.** Shutdown +
init clears everything reachable from the handle. It does **not** clear
process-level state — a file-scope global or a function-local `static` inside a
component library survives, because the library stays loaded. That is exactly
the failure `SYS-0192`'s own acceptance criterion catches: *"with the default,
run order does not affect results — shuffling the list produces identical
per-run outputs"*. A surviving static makes a shuffled batch differ. So the
detector for the hazard is a test the requirement already mandates, and it
needs no new mechanism.

Where exactness must be guaranteed rather than tested, the design already has
the stronger tool: `DD-09`/`R-SIM-19` run **one subprocess per recording** in
batch, which resets process state by construction.

**The optimisation, named so nobody invents a different one.** If measurement
shows the per-entry bundle re-parse is material at campaign scale, the answer
is an **optional** `adasReset(void* handle)` export, bound by name like every
other symbol (`SYS-0050`), with *absent* meaning *fall back to shutdown+init*.
That is additive — a host binding it optionally works against old and new
libraries alike, and `ADAS_SIL_ABI_VERSION` does not move, since neither the
structs nor the existing call semantics change. **It is not proposed now:**
nobody has measured the re-parse, and adding an export to satisfy an
unmeasured cost is how a five-symbol ABI becomes a seven-symbol one.

**Trigger:** a campaign measurement (`G5`, `OQ-14`) showing init cost as a
material share of per-entry time.

### 2.3 `OQ-12` — do any modules change rate at run time? · **`CLOSED` — unrepresentable over this ABI**

**Answer: no, and the contract makes it impossible to answer otherwise.** A
module's period is read from its config bundle at manifest-build time
(`<COMPONENT>_<FN>_PERIOD_US`, `buildManifest()`'s `periodLookupUs`) and
reported through `adasManifest`, which is callable **before** `adasInit` and
returns a snapshot. `adasExec` takes `dtS` and no rate argument. There is no
export by which a module could announce a new period mid-run, and no host call
that would ask.

So `SYS-0066` (grid is the GCD), `SYS-0071` (the module's own update flag wins)
and `SYS-0072` (period declared by the module, calibrated in configuration) are
unaffected: the grid can be computed once at load, and it cannot go stale.

**The residue is already a requirement, not a question.** A module may still
*behave* at a rate other than the one it declares — internal sub-gating,
skipping a cycle under load, a stale calibration key. `SYS-0071` covers exactly
that: the module's own `updated` flag is authoritative over the predicted
schedule and any disagreement is *reported as a named finding in the run
manifest, never a silent value*. That is a stronger guarantee than an answer
from a module team would have been, because it holds for modules that answer
the survey wrongly.

**What would reopen this:** a module needing a genuinely variable rate would
need a new export, so it arrives as an ABI change request and cannot slip in
quietly. Nothing in the current eleven modules is heading that way.

## 3. `G3` — Recordings in, artifacts out

**The pool.** `OQ-11` (is there a port catalogue to adopt), `OQ-10` (preferred
export format), `OQ-22` (licences for proprietary readers), `OQ-09` (what the
bench capture writes). Two are about *naming things that cross the boundary*
and two are about *formats crossing it*.

**The principle the group produced.** **A description that is generated cannot
drift; a description that is authored beside it will.** That single line closes
`OQ-11` outright and explains why `OQ-10` and `OQ-22` are so much cheaper than
they look: a format is a codec of four methods behind a registered interface
(`R-SIM-14`), so naming a format costs a table row and *choosing wrongly* costs
a week — whereas authoring a second description of our own ports would cost a
permanent maintenance obligation. Spend the caution where it belongs.

### 3.1 `OQ-11` — is there a port catalogue to adopt? · **`CLOSED` — derive it; neither adopt nor define**

**Answer: the catalogue is the union of the `ModuleManifest`s present in the
run, computed at load. There is no authored catalogue file, and there must not
be one.**

`SW-0388` requires *"a versioned catalogue of named ports carrying typed
payloads"* against which every configured port resolves at load, with its
version in the run manifest. Its `Now.` line says no catalogue exists above the
manifests and asks `OQ-11` first, on the reasoning that *adopting beats
defining*. There is a third option and it is strictly better than both:

- **Defining one** creates a second description of a port set we own, free to
  drift from the manifests — which is precisely what `R-SIM-16` forbids:
  *"Hand-mapping a port set we own would create a second description free to
  drift from the manifest."*
- **Adopting an external one** as the *resolution authority* has the same
  defect and adds a dependency: an outside document would decide whether a port
  our compiler emitted is legal.
- **Deriving it** has neither. The manifest is already generated from
  `conf/ports.yaml` (`R-SIM-22`), which is already gated by `ENABLED_FUNCTIONS`
  (`R-VAR-5`), so the manifests are *by construction* a description of what
  compiled. Their union is a catalogue that cannot disagree with the binaries,
  because it is read out of them.

**How each of `SW-0388`'s clauses is met by the derived form:**

| `SW-0388` requires | Met by |
|---|---|
| A catalogue of named ports with typed payloads | The union of `adasManifest()` outputs for the modules named in the resolved run spec |
| Every configured port resolves at load | `SI-13`'s probe pass already produces a `ModuleManifest` per module (`SW-0411`) *before* emission — the resolution point exists already |
| Unresolvable port fails the load, naming near matches | `R-SIM-21`'s `AuthoringError`, which already lists every port the manifest declares |
| The catalogue's version is recorded | The set of `(module, manifest version, library hash)` triples, already in the run manifest |

**The external half, narrowed to something that changes names and nothing
else.** If an organisation-level signal catalogue does exist, adopt it as a
**naming source** — so our port names match the house vocabulary — and never as
a resolution authority. That keeps `R-IFACE-1`/`R-NAME-4` intact and means the
answer arriving late costs a rename, not a redesign. Assumption `A-4` in the
Design should be restated in those terms: *not* "we may have to adopt a
catalogue", but "we may have to adopt vocabulary".

### 3.2 `OQ-10` — preferred exchange format for outputs · **`CLOSED` — `R1` is already fixed; a preference is an addition, not a change**

**Answer: the `R1` set is decided by artifacts that predate the question.**
`SYS-0111` requires exports to *the interchange format, a columnar text format,
and a replayable recording the system can read back*; `DD-13` fixes the
interchange format as **MCAP only in `R1`**. So `R1` is: **MCAP** (interchange
and replayable — the same codec serves both, which is why `SYS-0112`'s chaining
is free) and **CSV/TSV** (columnar text, registered **write-only** per
`R-SIM-14`, because it cannot round-trip).

That set is not a guess about anyone's preference; it is the smallest set that
satisfies three separate requirements, and it is already implied by decisions
taken.

**Why a team's stated preference cannot block.** `R-SIM-14` makes a format a
codec of ~4 methods behind one registered interface, and `SYS-0110` makes every
exporter a plug-in of which *none is mandatory*. A team answering "we live in
MDF4" or "we want Parquet" therefore adds a row to the codec table — a bounded
piece of work, no design impact, no change to `Session`, the pipeline, the
Scene or any expectation. This is the same signal `OQ-08` produced: naming
three formats *changed the plan's shape not at all*, which is how you know the
seam is in the right place.

**Still worth asking, for adoption rather than for design.** An export nobody
opens is dead weight, and the question *"what do you actually load these into?"*
decides which optional codec is written first. It is a scheduling input, not a
gate. **It should be dropped from the baselining set and re-asked at the first
export review.**

**One line to write back, because it is the part that could be got wrong:** an
export is **lossy and terminal** and is never accepted as a resim input
(`R-SIM-14`), so a CSV of a run is not a smaller recording — it is a different
kind of artifact, and the loader refuses it **by capability, not by
convention**.

### 3.3 `OQ-22` — licence and distribution for proprietary readers · **`PROPOSED` — not this document's call; contained, and not yet due**

**Not concluded.** Licence acceptability and distribution terms are a legal and
commercial decision belonging to whoever ships the deliverable. What this
document can do is bound the exposure and say when the answer is needed.

**What `DD-04` already eliminates.** *Exactly one codec implementation, in
C++.* That removes the Python ecosystem from the *implementation* candidate set
entirely — those readers cannot be the single C++ codec, whatever their
licences. The candidate set is therefore three shapes, not a survey:

| Option | Shape | What it costs | What has to be checked |
|---|---|---|---|
| **A** | A C++ open-source reader per format | Least code | Licence class vs. how the deliverable ships. A copyleft reader **statically linked** into a delivered library is the case that bites; dynamic linkage is usually the mitigation and still needs sign-off |
| **B** | A vendor/consortium SDK | Least risk of format error | Redistribution terms, per-seat or per-deliverable cost, and platform coverage (`P-1`…`P-10` requires Windows **and** Ubuntu) |
| **C** | A clean-room reader from the published specification | No licence exposure at all; full control | The largest engineering cost, and it is only reasonable for the subset of the format actually present in our files |

**Why the exposure is contained however it resolves.** The reader sits behind
the codec interface, so it touches no engine code, appears in no other
component, and can be replaced without a caller changing. That is the reason
this question is a *procurement* question and not an architectural one.

**When it is due.** `DD-13` writes each non-MCAP reader *the week its first
sample file arrives*. So the licence answer is due then, per format — not
before, and not as a `R1` baselining gate. **Recommend moving `OQ-22` out of
the gate set and attaching it to the two format work packages**, which also
means it is asked by someone holding a real file rather than in the abstract.

**The one thing worth starting early, because it has a long lead time:** if
option B is even a candidate, the redistribution terms question should be
opened with the vendor now — a licence negotiation is the only item in this
whole register whose latency is measured in months.

### 3.4 `OQ-09` — what does the bench capture write? · **`NARROWED` — one small ask, and its cost is now one printed field**

**Not answerable here** — no bench capture file exists in this repository, and
no amount of reasoning substitutes for ten seconds of real data. What has
changed is how much rides on it.

**What `G1` removed from this question.** The register lists `OQ-09` as
blocking `SYS-0015`, `SYS-0029`, `SYS-0061`, the foreign half of `OQ-01`, and
`IFQ-06`. After §1:

- **`IFQ-06` no longer depends on it** (§1.1). The header carries two fields
  regardless of what the bench writes, because the decision rests on what a
  *producer* can know, not on what a *reader* receives.
- **`OQ-01` no longer depends on it** (§1.3). The highest supported rung is a
  measured field of `RecordingIndex`, computed per file. An unknown capture
  format means an unknown *value*, not an unanswered question.
- **`SYS-0015`/`SYS-0029`/`SYS-0061` are satisfiable without it** — they
  require the header to be *bound explicitly*, *present on every port value*,
  and the ladder to be *declared*. All three are about our own shape. What the
  bench writes decides which rung its files land on, which is the ladder
  working, not the ladder blocked.

**So what is genuinely left is verification evidence, not design input:**
`MP-1`'s exit is provisional against a crafted fixture until a real sample
exists (`WP-18`), and plan risk `R-8` stays open.

**The minimum ask, stated so it is easy to say yes to** — this is deliberately
much smaller than "specify the capture":

1. **One file, ten seconds**, from any routine bench run — no special
   configuration, no scenario.
2. **The channel/topic list** as the tool exports it.
3. **One sentence** on whether the capture chain re-stamps messages or passes
   the producer's stamp through.

**What we would check on receipt:** whether a per-message reception stamp
exists (decides rung 4 availability, and therefore whether `Capabilities`
degrades for that codec); whether the signal header survives end to end
(decides rungs 2 and 3); and the finest timestamp resolution present — which is
one of the two inputs to `IFQ-01` (§1.4).

**Cost of leaving it open:** `MP-1` stays provisional and `R-8` stays on the
risk list. **No work package is blocked**, because `DD-13` ships MCAP first and
the crafted fixture exercises every rung.

## 4. `G4` — Where the knobs are

**The pool.** `OQ-02` (ego re-integration in `R1`), `OQ-04` (is the override
granularity enough), `OQ-07` (inject parameters or point at a file). The
register addresses all three to *algorithm teams*, and all three read as
*"should the system do more here?"*.

**The principle the group produced.** Each of the three already has a written
answer that says **no, and names what to do instead** — a deferral with two
grounds, a closed verb list with two alternatives, a bundle rule with an
explicit ban on a second edit site. So the work here is not to decide; it is to
**find the existing decision, check it still holds, and state the condition
under which it would be reopened**. A question re-asked without noticing it was
answered is how a closed list gets quietly reopened, and every one of these
three would have enlarged the build if answered afresh.

### 4.1 `OQ-07` — inject parameters, or point at the module's parameter file? · **`CLOSED` — point at a bundle; injection is forbidden by name**

**Answer: the system passes a *path* and never a *value*.** `adasInit` takes
`configPath`, and `SYS-0177`/`R-SIM-3a` already settle the rest: one atomic
bundle per (project, build), packed beside the library, resolved module-relative
when the path is `NULL`, with an explicit path always winning.

**Why injection is not a close call.** `R-SIM-3a` states the ban directly — the
bundle is *"a build output, never a second place to edit a value"* — and gives
the failure it prevents: **the viewer must read the bundle the SUT was
initialised with**. Inject a value and there are two answers to *"what
wheelbase did this run use?"* — the file's and the injected one — with the
run and the picture free to disagree. That is the same class of defect as
back-filling a timestamp (`G1`): a plausible number with no single source.

**How a parameter sweep works without injection**, since that is the use case
behind the question. Generate a **bundle variant**: copy the bundle, change the
one key, re-hash, point `adasInit` at it, and record the hash in the run
manifest. This satisfies `SYS-0072`'s acceptance verbatim — *"a rate sweep
changes only a calibration value; no rebuild occurs and no host file is
edited"* — because producing a bundle variant is neither a rebuild nor a host
edit. The single reader stays single, the hash keeps the evidence chain intact
(`R-SIM-25`), and the viewer reads exactly what the SUT read.

**The one small thing this implies, named so it is not discovered late:** a
bundle-variant helper (copy · patch one key · re-hash) is needed beside the run
spec. It is a file, not a mechanism, and `SYS-0072`'s acceptance already
assumes something plays that role.

### 4.2 `OQ-04` — is module staging plus per-port override enough granularity? · **`CLOSED` — the granularity is already finer than the question assumes**

**Answer: yes — and the question understates what exists.** Addressability
today is four levels deep, not two:

| Level | Mechanism |
|---|---|
| Per module (stage) | `mode:` / `impl:`, two independent axes — `SYS-0080`, `R-SIM-10` |
| Per port | Per-port mode override — `SYS-0082` |
| **Per field path within a port** | `egoDyn.vx` — `R-SIM-15` |
| **Per element of a repeated field** | `[i]` and `[*]` — `R-SIM-15`'s closed index grammar |

So *"module-level staging plus per-port override"* describes the coarsest two
of four. The honest answer to "is it sufficient" is that nobody has yet needed
the two finer levels that already exist.

**The one axis that is missing is missing on purpose.** There is no
**time-varying** or **conditional** override — no predicate in the index
grammar, no expression language, no user-supplied callable. `R-SIM-15` closes
that list and gives the reason: *an override may destroy or attenuate
information; it may never create an entity*, and an open expression grammar is
*"how a flexible tool becomes an over-configured one"*. Two alternatives are
written for the cases that ask for it: **edit the scenario** (which is also
data, and is versioned and hashed) or **a `stub:` stage** (which is code, in
the open, and testable).

**This is the row in the register most likely to enlarge the build if answered
afresh**, which is why it is closed rather than re-opened. Answering *"is it
sufficient?"* by asking teams invites *"it would be nice if…"*, and each
nice-to-have is a predicate in a grammar that is closed for a written reason.

**Reopen condition, deliberately demanding:** a concrete case, with an example
recording, that **neither** editing the scenario **nor** a `stub:` stage
serves. That is a change request with evidence attached, not an open question —
and if one arrives, the answer is still more likely to be a fifth verb than a
predicate.

### 4.3 `OQ-02` — is ego re-integration needed in release one? · **`CLOSED` — no; already deferred on two grounds, only one of which was tied to `OQ-01`**

**Answer: no.** `SYS-0108` is already marked `P2 · DEF`, *off by default*, with
its deferral argued: *"it is an approximation whose validity envelope is
unknown, and shipping it before the divergence machinery (`SYS-0105`–`SYS-0107`)
is trusted would let it be used as though it removed the open-loop limit."*

**The revisit trigger needs restating, because `G1` moved it.** The deferral
note ends *"revisit once `OQ-01` is answered"*, and §1.3 has now closed
`OQ-01` — but into a **measurement**, not a global yes/no. The dependency was
never arbitrary: re-integrating ego pose means integrating over per-cycle `dt`,
which is only as sound as the timing rung the recording supports. So the
trigger becomes evaluable per recording rather than globally, and is worth
writing back in that form:

> Ego re-integration may be considered for a recording whose ports report
> rung 3 or better, and only once the divergence machinery is trusted. On a
> rung-4 recording the integration would run on reception time — the clock
> `SW-0044` exists to keep separate from validity — so the feature is not
> merely approximate there, it is measuring the wrong thing.

**Two grounds, and the second is untouched.** Even with perfect timing,
`SYS-0105`–`SYS-0107` must be trusted first. That has not moved, so `R1` is
unaffected whatever the timing evidence shows.

**The framework-side constraint worth recording alongside it.** Ego
re-integration is dead-reckoning, which `R-SIM-7` bans outright in a layer
provider: *"never integrating a time-varying signal … into information nobody
produced. That is an algorithm."* `SYS-0108` puts it in the engine rather than
in a provider, which is the right side of that line — but only while its
output stays *labelled an approximation everywhere*, which its acceptance
criterion already demands. **If it is ever implemented, the label is the
requirement, not the transform.**

## 5. `G5` — Numbers nobody here can invent

**The pool.** `OQ-14` (per-cycle cost, campaign throughput, player frame time,
and the configurations they are measured on) and `OQ-16` (the set of common
configuration changes and each one's time budget). Both are marked `BLOCKS`,
and the block is real in a specific way: **a requirement with no threshold
cannot be *failed***, which `CN-0356` warns about explicitly.

**The principle the group produced.** *A threshold nobody can supply becomes a
baseline plus a bound.* Every one of these requirements is written to catch a
**regression** — `SW-0369` and `SW-0323` both say a measurement exceeding its
budget is *"reported as a regression rather than silently re-baselined"*. A
regression is a comparison, and a comparison needs a **previous measurement**,
not an absolute target. So the first measurement on a declared reference
configuration supplies the number, and the requirement becomes failable on the
*second* run without anyone guessing on the first.

**The mechanism is not new and must not be built twice.** `R-SIM-24` already
defines exactly this discipline for determinism tolerance: declared per
component, **every row carrying a mandatory `why:`**, its hash in the run
manifest, and — the part that matters most — *"a passing report prints the
tolerance it used and the headroom consumed"*, described there as *"the only
anti-spiral mechanism that does not depend on someone choosing to look"*.
Performance budgets are the same artifact with a different unit. Reusing it
also imports the anti-spiral property for free, which is the thing that
usually goes wrong with baseline-derived budgets.

**What this does and does not answer.** A baseline-derived budget answers *"did
we get slower?"* — rigorously, and from the second run. It does **not** answer
*"is it fast enough?"*, which is an absolute and belongs to whoever knows how
many recordings must clear overnight. That half stays with its owner. It just
stops holding up the harness.

### 5.1 `OQ-14` — the performance numbers · **`NARROWED` — mechanism and reference configuration closable here; the absolute stays with its owner**

**Three sub-questions, and only one of them needs a stakeholder.**

| Sub-question | Verdict |
|---|---|
| **How is a budget expressed so a run can exceed it?** | `CLOSED` — a `budget.yaml` in the shape of `R-SIM-24`'s `tolerance.yaml`: one row per metric, a value, a mandatory `why:`, hashed into the run manifest, with the consumed headroom printed on **pass** as well as on fail |
| **What is it measured on?** | `CLOSED` for the software half (below); the hardware half is coupled to `OQ-15` |
| **What is the absolute number?** | `PROPOSED` — seed from the first measurement; the *target* belongs to whoever owns throughput expectations |

**The reference configuration, software half — declarable now, and it is the
half that actually causes trouble.** An unstated reference configuration is
worse than an unstated number, because two measurements taken on different
setups look like a regression and burn a day each time. Pin all five:

| Axis | Declared as |
|---|---|
| Module set | `df` alone for per-cycle cost (the only functional module, §2.1); `perception-core` → `df` for the multi-module figure |
| Recording | One named MCAP fixture, hash recorded, committed as a fixture rather than referenced by path |
| Tick count | Fixed and stated — `SW-0323` requires *"a stated tick count and layer count"*, so this is the requirement's own wording, not an addition |
| Layer count | Fixed and stated, per the same clause |
| Build configuration | `RelWithDebInfo`, matching the platform suffix already in use — never a debug build, and never left implicit |

**The hardware half is `OQ-15`'s dependency and should be recorded as one.**
The reference machine cannot be declared before the CI system is chosen (§6.1),
and a budget measured on a developer laptop will not survive the move. The
practical consequence: **express each budget with the host recorded beside it**,
exactly as `R-SIM-24` derives its determinism axis from the manifests' `host`
field rather than from a flag. Then the move to a CI runner is a visible
re-baseline with a stated reason, not a mystery.

**What to write back so the requirements stop being unfailable:** `SW-0369`
and `SW-0323`'s `Now.` lines change from *"the numbers are `OQ-14`, open"* to
*"the budget file and the reference configuration are declared; values are
seeded from the first measurement on the reference host and are regression
bounds until an absolute target is supplied"*. The requirement is then failable,
which is what `CN-0356` was asking for.

### 5.2 `OQ-16` — common configuration changes and their budgets · **`NARROWED` — the set is already written; propose a structural gate, leave the stopwatch to the customer**

**Correction to the register first.** Its `OQ-16` row asks for *"the stated set
of common configuration changes **and** each one's time budget"*, as though both
were open. **The set is already declared, in `SW-0348` itself:** *switch a
module's mode · change a calibration value · add a recording · change the
layout · add an export.* Five items, named in the requirement. Only the budget
is missing, which halves the question.

**Why the remaining half resists being answered as written.** `SW-0348` reads
*"completable by a representative engineer unaided within a declared time
budget"*. That measurement needs a representative engineer who has not seen the
system, a facilitator, and a repeat each release — an expensive instrument that
tends to be run once and then quoted for two years. It is the right *acceptance*
and the wrong *gate*.

**Proposal — gate structurally, measure the wall clock separately.** Each of
the five has an objective, mechanically checkable shape, and the shape is what
actually determines whether the task takes ten minutes or a day:

| Change | Structural gate (checkable in CI) |
|---|---|
| Switch a module's mode | One field in the run spec. No other file touched |
| Change a calibration value | One key in one bundle (`G4`, §4.1). No rebuild, no code edit |
| Add a recording | One entry in the recording list. No code edit; the ingest map is edited only for a *new family*, not a new file |
| Change the layout | One workspace file. No framework file touched |
| Add an export | One exporter entry. No engine file touched (`SYS-0110` — exporters are plug-ins) |

Each row is a **planted-violation test** in the sense `SW-0370` already
requires: make the change, assert the diff touches exactly the declared file
set. That is failable today, costs no facilitator, and catches the actual
regression — a change that used to be one file starting to need three.

**And keep the health metric, because it is the honest proxy.** `SW-0348`'s
acceptance already tracks *"lines of configuration per project … across
releases"*. That number needs no stakeholder, no stopwatch and no
representative engineer, and it moves in the right direction for the right
reasons.

**Not concluded, deliberately:** the wall-clock budgets themselves. *"Within
thirty minutes"* versus *"within a day"* is a statement about what the
customer's engineers are expected to absorb, and this document has no standing
to set it. **Recommendation: run the five tasks once, record the times as
observations rather than targets, and put those observations in front of the
customer team** — a number to react to gets an answer where an open question
does not.

## 6. `G6` — Organisation

**The pool.** `OQ-15` (which CI system, what retention), `OQ-17` (tool
qualification / functional safety), `OQ-18` (who maintains project
configuration after handover), `OQ-19` (campaign retention policy). **None of
these is this document's to answer** — each commits somebody else's budget,
infrastructure or process. All four are `PROPOSED`.

**The principle the group produced.** *Make the technical artifact independent
of the organisational answer, then the answer can arrive late at no cost.* For
three of the four this is achievable and the de-blocking is written below. For
`OQ-17` it is not fully achievable, which is exactly why that one carries a
written fallback and the others do not.

### 6.1 `OQ-15` — which CI system, and what artifact retention? · **`PROPOSED` — and `WP-01` should not wait for it**

**Repository state, 2026-08-12:** there is **no CI configuration of any kind** —
no `.github/`, no `.gitlab-ci.yml`, no `Jenkinsfile`, no
`azure-pipelines.yml`. Meanwhile `WP-01` — *CI and the check harness* — is the
**first** work package, on `CN-0351`'s reasoning that *manual verification is
the mechanism that fails first*. Read together those two facts look like the
plan is blocked at package one.

**It is not, and the reason is a pattern this repository already uses.** Split
`WP-01` in two:

| Half | Depends on the CI choice? | Precedent already in the tree |
|---|---|---|
| **The harness** — every check, runnable as one plain command, exit code and a printed scan count | **No** | `modules/sim/docs/py/run_all.py`, which this module's `CLAUDE.md` already requires before any docs commit; `scripts/check_invariants.py` for `GT-1`/`GT-11` |
| **The trigger** — the vendor file that runs that command on push | Yes | — |

The harness is where all the work and all the value are; the trigger is
roughly ten lines and is written the day the vendor is known. **So `WP-01` is
completable except for one small file**, and — the part that matters more —
every check stays runnable on a developer machine, which is what keeps checks
being run at all.

Two constraints to carry into whichever system is chosen, both already implied
by decisions taken: it must run **Windows and Ubuntu** (`P-1`…`P-10`), and the
harness lives in `contrib/` per `DD-08`.

**Not concluded:** the vendor, and the retention numbers. The retention half is
the same question as `OQ-19` (§6.4) and should be answered once, there, for
both.

### 6.2 `OQ-19` — campaign retention: baseline, regenerable, or deleted? · **`PROPOSED` — but the question is about *inputs*, not results**

**The reframing, which is the technical contribution here.** `R-SIM-5` makes
resim deterministic and `R-SIM-24` makes that determinism measured evidence. So
a campaign result is **regenerable if and only if its inputs still exist** —
recording, resolved spec, config bundle and the exact library binary. Inputs are
small (a spec is kilobytes; `R-SIM-6` already embeds the bundle's bytes in the
recording). Results are large. **Retaining inputs and regenerating results is
therefore the cheap direction, and it is available only because determinism was
designed in.**

**The one hard constraint, which no policy can wish away:** regeneration needs
the *binary*, not just its hash. A component build that can no longer be
obtained makes its results unregenerable, and at that moment the results become
the only evidence that run ever happened. So any policy needs a rule for the
case *"the binary is gone"* — either the outputs are kept, or the baseline is
knowingly abandoned. `R-SIM-24`'s *rebuilt-binary* axis exists precisely because
a rebuild is not guaranteed to reproduce.

**A three-tier shape to react to — offered, not adopted:**

| Tier | Kept | Rationale |
|---|---|---|
| Inputs (recording ref + hash, resolved spec, bundle bytes, library hash) | Long | Kilobytes; without them nothing is reproducible or auditable |
| Run manifests and reports | Long | The audit trail proper; small |
| Bulk per-tick outputs | Short, regenerable on demand | Large; recoverable while the binary is obtainable |
| Any run whose binary is no longer obtainable | Outputs promoted to long | The exception above |

**Not concluded:** the durations, and whether an audit obligation forces bulk
retention regardless. Those are a storage budget and a compliance question.
**Answer this together with `OQ-15`'s retention half** — one policy, two
consumers.

### 6.3 `OQ-18` — who maintains project configuration after handover? · **`PROPOSED` — organisational; the architecture is already neutral to the answer**

**Nothing technical is blocked**, and it is worth recording *why*, because it
is a property that was designed for rather than a happy accident: project
configuration is **data in versioned files with no code** — `R-VAR-2` (no
central roster; a project exists because a module's `conf/build.yml` declares
it), `R-VAR-4` (calibration in `projects/<name>/`), `R-SIM-3a` (the bundle is a
build output, never a second edit site). So "who maintains it" is a question
about repository access and review, not about capability.

**What actually determines the support model's cost, and is worth saying to
whoever chooses:** the diagnostics. `DG-1`…`DG-5` and `N-1`…`N-13` —
`sim explain`, `sim doctor`, an `AuthoringError` that names the plug-in, the
requested port and every port the manifest declares — are what let a customer
team answer its own questions. **A thin support model is viable in proportion
to how good those messages are**, which turns the choice from a headcount
argument into an engineering target.

**Three shapes to choose between, not chosen here:** customer team owns it with
the supplier on call for defects · supplier owns configuration as a service ·
joint, with the supplier owning the schema and the customer owning the values
(this last one matches the artifacts best, since the schema is `conf/*.yaml`
and the values are `projects/<name>/`). **Recommendation is the third**, and it
is a recommendation, not a conclusion.

### 6.4 `OQ-17` — tool qualification / functional-safety constraints? · **`PROPOSED` — but replace the question with a sharper one**

**Not answerable here, and the register is right that it is the highest-variance
item on the list** — it can reach requirement style, verification evidence and
the whole document set. It already carries a written fallback in `SYS` §26
(develop in the present style, accept re-styling as a known scoped cost). Two
things can be added without answering it.

**First: the blast radius is smaller than it looks, and it is worth recording
so the fallback is not over-provisioned.** The document set is *already* in
qualification-friendly shape: numbered `shall` statements, an `Accept`
criterion per requirement, a `Verify` method, a `Trace` link upward, and a
`Now.` line stating implementation status. That is most of the structure a
qualification argument asks for. The genuinely expensive parts — a tool
classification (impact and detection, hence a confidence level), the validation
evidence to support it, and a tool safety manual — are **process work
downstream of the documents**, not a rewrite of them. So the fallback's cost is
mostly *addition*, not *re-styling*, which makes it a much safer risk to carry.

**Second, and the actual recommendation: ask a different question, because this
one is hard to answer and its decisive input is one sentence.**

> Does any output of this tool enter a safety argument — as verification
> evidence for a safety requirement, or as the basis for a claim about a
> production component's behaviour?

If **no**, `OQ-17` closes with no qualification obligation and the fallback is
never exercised. If **yes**, the classification work begins and its scope is
determined by *which* outputs. Quality can answer that binary in a sentence,
where *"are there tool qualification constraints?"* invites a study. **Asking
the sharper question is the recommended next action on this row** — it is the
cheapest question in this register to ask and potentially the most expensive to
leave.

**One thing that should not wait for the answer, since it is cheap either way:**
keep the `Trace.` fields complete as requirements are written. Reconstructing
traceability after 32 packages are cut is the one part of the fallback that
would genuinely hurt.

---

## 7. Where this pass ended

**Twenty rows worked: eleven `CLOSED`, four `NARROWED`, five `PROPOSED`.**

**Nothing in the implementation plan is blocked by a question this document
could have answered.** `WP-01` is de-blocked by splitting the harness from the
trigger (§6.1); `SW-0369`/`SW-0323`/`SW-0348` become failable through a baseline
plus a bound (§5); `MP-1` stays provisional on one ten-second sample file
(§3.4) and blocks no package.

**Where the closures came from, which is the useful pattern.** Only three of
the eleven needed a genuinely new decision (`IFQ-06`, and the reframings in
§3.1 and §5). The other eight were **already answered by an artifact nobody had
re-read** — the ABI header answered three module-team questions (§2), an
acceptance criterion answered two (§4.2, §4.3), and a `RecordingIndex` field
answered one (§1.3). That is the third time this pattern has appeared in this
project (`SWQ-12`, `OQ-13`, and now eight more), and it is worth naming as a
habit: **before asking anyone, check whether the artifact already decided.**

**Two corrections the pass produced, both of which change planning:**

1. **`OQ-05`: three modules carry `conf/ports.yaml` and a SIL C interface, not
   two** — `perception-core` as well as `df` and `vdy`. `IT-22` and the
   multi-module `E2E` rows have a third candidate, and the more interesting one.
2. **`OQ-16`: the set of common configuration changes is already written**, in
   `SW-0348` itself. Only the budget was ever open, which halves the question.

**One reversal and one recommended reversal, flagged because they undo argued
positions:** `IFQ-06` moves from one header stamp to two (§1.1 — closed, the
argument does not depend on the missing input). `IFQ-01` is *recommended* to
move from `timestamp_us` to `timestamp_ns` (§1.4) — **not adopted**; silence
leaves the standing default in place.

---

## 8. Write-back list

One line per edit an owning document needs. Nothing here is applied yet — this
document produces answers; the owning documents remain authoritative.

**`interfaces_signal_header_plan.md`**

- `IFQ-06` → **two fields**: `source_timestamp_*` always filled,
  `capture_timestamp_*` `optional` and unset when unknown. Remove the stated
  dependency on `OQ-09`.
- Rename `time_stamp` to a name that says which clock it is — required by
  `SW-0044` regardless of the unit decision.
- `IFQ-01` → record the counter-evidence (§1.4) beside the standing default;
  mark that ratification, not silence, adopts `timestamp_ns`.

**`SIM_Software_Requirements_v0.1.md`**

- `SW-0043` / `SW-0044` `Now.` → the header's two stamps are decided; capture is
  explicit-unknown in `R1`, `age_s` uses `SW-0045`'s hold-schedule fallback.
- `SW-0050` accept → three refinements: non-decreasing (not strict), per port,
  binds source time; an out-of-order capture time is reported, never clamped.
- `SW-0388` `Now.` → the catalogue is **derived** as the union of the run's
  `ModuleManifest`s; no authored catalogue file. `OQ-11` no longer gates it.
- `SW-0369` / `SW-0323` `Now.` → budget file + declared reference configuration;
  values are regression bounds seeded from the first measurement.
- `SW-0348` `Now.` → the change set is already stated here; add the structural
  gate (§5.2); the wall-clock budget remains open.
- `SW-0033` → **only if `IFQ-01` is ratified to ns**: remove the
  "only unit conversion in the engine" carve-out rather than amending it.

**`SIM_System_Requirements_v0.1.md`**

- `SYS-0048` / `SYS-0192` `Now.` → reset is `adasShutdown` + `adasInit`; exact
  for handle-scoped state; the surviving-static hazard is detected by
  `SYS-0192`'s own shuffle criterion; subprocess isolation where exactness must
  be guaranteed.
- `SYS-0066` / `SYS-0071` / `SYS-0072` → run-time rate change is
  unrepresentable over the ABI; the grid cannot go stale; the residue is
  `SYS-0071`'s reported disagreement.
- `SYS-0108` deferral note → restate the revisit trigger as *rung 3 or better,
  per recording* plus the untouched `SYS-0105`–`SYS-0107` ground.
- `SYS-0080` / `SYS-0082` → note that addressability is four levels deep, and
  that the missing axis is closed by `R-SIM-15` with two written alternatives.
- `SYS-0177` / `SYS-0179` → the system passes a path, never a value; sweeps are
  bundle variants.
- `SYS-0111` → `R1` export set is fixed (MCAP + write-only CSV); an added format
  is a codec row.

**`SIM_Implementation_Design_v0.1.md`**

- `A-4` → restate as *"we may have to adopt vocabulary"*, not *"we may have to
  adopt a catalogue"*.

**`SIM_Implementation_Plan_v0.1.md`**

- `WP-01` → split into harness (vendor-independent, do now) and trigger (~10
  lines, on the vendor answer). Note the `contrib/` home per `DD-08`.
- `WP-18` / risk `R-8` → restate the ask as the four-item minimum in §3.4.

**`SIM_Open_Questions_v0.1.md`** (the register itself)

- Move eleven rows to §4 with the answers above.
- Correct the `OQ-05` row: **three** modules on the ABI, naming
  `perception-core`.
- Correct the `OQ-16` row: the change set is not open.
- Move `OQ-22` out of the baselining gates and attach it to the two format work
  packages.
- Merge `OQ-19` with `OQ-15`'s retention half into one policy question.

---

## 9. What to ask, and of whom

The pass reduced twenty rows to **five asks**. Four are one sentence each.

| # | Ask | Of whom | Why it is worth asking now |
|---|---|---|---|
| 1 | *Does any output of this tool enter a safety argument?* | Quality / safety | One sentence; determines whether `OQ-17`'s fallback is ever exercised. Cheapest question here to ask, potentially the most expensive to leave (§6.4) |
| 2 | **Ten seconds of bench capture**, its channel list, and one sentence on re-stamping | A recording owner | Retires plan risk `R-8` and makes `MP-1`'s exit real rather than provisional (§3.4) |
| 3 | *Ratify `timestamp_ns`, or keep `timestamp_us`?* | Whoever owns the interfaces contract | Reverses a stated default, so it needs a nod rather than silence (§1.4) |
| 4 | Which CI system, and the retention policy for both CI artifacts and campaigns | DevOps + whoever owns storage/audit | One answer, two consumers (§6.1, §6.2). Only the ~10-line trigger waits on it |
| 5 | Wall-clock budgets for the five configuration changes — **after** we measure them once and show the numbers | A customer team | A number to react to gets an answer where an open question does not (§5.2) |

Everything else in the register is either closed above or attached to the work
package where it becomes real.
