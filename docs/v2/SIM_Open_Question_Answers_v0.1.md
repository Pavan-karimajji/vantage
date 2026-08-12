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
| `G1` | **The clocks** | `IFQ-01` *(+ 3 written back)* | Time is declared in one unit, converted in one place, and degraded explicitly — never estimated |
| `G2` | **What the compiled contract can already do** | *(all 3 written back)* | Three questions addressed to module teams that the ABI in this repository answers without asking anyone |
| `G3` | **Recordings in, artifacts out** | `OQ-09` `OQ-22` *(+ 2 written back)* | A format is a codec of four methods, so naming one costs a table row; what is genuinely open is never *which format* but *whether a real sample exists* |
| `G4` | **Where the knobs are** | *(all 3 written back)* | All three ask "should the system do more here?" and all three were answered by an artifact that predates the question |
| `G5` | **Numbers nobody here can invent** | `OQ-14` `OQ-16` | An absolute threshold nobody can supply becomes a recorded baseline plus a regression bound — failable on day two without a guess on day one |
| `G6` | **Organisation** | `OQ-15` `OQ-17` `OQ-18` `OQ-19` | De-block by making the technical artifact independent of the organisational answer, then let the answer arrive late without cost |

### 0.3 Status board

Updated as each row concludes. **A row leaves this table when its answer has been written into the owning document** — the closed rows of `G1`–`G4` are gone because `docs/interfaces_signal_header_plan.md`, `SW-0043`/`SW-0044`/`SW-0050`/`SW-0410` and the register now carry them.

| Row | Group | Verdict | Write-back target |
|---|---|---|---|
| `IFQ-01` | `G1` | `NARROWED` — recommend `timestamp_ns`, reverses a stated default, needs one nod | `interfaces_signal_header_plan.md`; if ratified also `SW-0033` |
| `OQ-09` | `G3` | `NARROWED` — one 10-second sample; blocks no `WP`, keeps `MP-1` provisional | Plan risk `R-8`; `WP-18` |
| `OQ-22` | `G3` | `PROPOSED` — legal/commercial; contained by the codec seam; due per format | Register §2 → attach to format `WP`s |
| `OQ-14` | `G5` | `NARROWED` — budget file + reference config closable; absolute target stays with owner | `SW-0369`/`SW-0323` `Now.` lines |
| `OQ-16` | `G5` | `NARROWED` — set already written in `SW-0348`; structural gate proposed | `SW-0348` `Now.` line; register row |
| `OQ-15` | `G6` | `PROPOSED` — vendor is the org's; `WP-01` de-blocked by splitting harness from trigger | `WP-01` split; register §2 |
| `OQ-17` | `G6` | `PROPOSED` — replace with the one-sentence binary; blast radius bounded | `SYS` §26 fallback note |
| `OQ-18` | `G6` | `PROPOSED` — three shapes, third recommended; architecture already neutral | Register §3 |
| `OQ-19` | `G6` | `PROPOSED` — reframed to *inputs*; answer with `OQ-15`'s retention half | Register §3; merge with `OQ-15` |

---

## 1. `G1` — The clocks

**The pool was** `IFQ-01` (unit), `IFQ-02` (monotonicity), `IFQ-06` (one stamp
or two), `OQ-01` (does the data carry cycle marking). Read separately they
looked like four preferences. Read together they were one question — *what does
a producer know, and what may a reader infer from it?*

**The principle the group produced.** A time field exists on the wire **iff a
producer can fill it from its own knowledge**. Reception time fails that test
(reception happens after the producer is finished), which is why `SW-0044` puts
it in the envelope. Capture time passes it *conditionally*; source time passes
it unconditionally. That single test decided `IFQ-06`, removed `IFQ-06`'s
stated dependency on `OQ-09`, and reframed `IFQ-01` as a risk question rather
than a taste question.

**Three of the four are closed and written back** — `IFQ-06` and `IFQ-02` into
`docs/interfaces_signal_header_plan.md` §3/§9 and `SW-0043`/`SW-0044`/`SW-0050`;
`OQ-01` into `SW-0410` and the register's §4.7. One remains.

### 1.1 `IFQ-01` — microseconds or nanoseconds? · **`NARROWED` — recommend reversing to `timestamp_ns`; needs one ratification**

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

**One thing is settled either way and has already been written back:** the
field is **renamed** from `time_stamp` to a name that says which clock it is —
`SW-0044` requires the two clocks to differ in name at every surface, and
`time_stamp` named neither. That landed with `IFQ-06`
(`docs/interfaces_signal_header_plan.md` §3) and did not wait on the unit.

## 2. `G2` — What the compiled contract can already do · **all three closed and written back**

`OQ-05`, `OQ-06` and `OQ-12`. Written back 2026-08-12 into `SYS-0048`,
`SYS-0192`, `SYS-0071`, `SYS-0072`, Design `IMP-0379` and the register's §4.7.

**The principle is kept here because it applies to rows not yet worked.** All
three were addressed to *module teams*; all three were answered by one file in
this repository — `modules/interfaces/include/adas/adas_sil_abi.h`. *A question
about what modules do is a question about what the contract lets them do.* The
ABI has five exports and no per-module variation to survey, so asking eleven
teams would have produced eleven answers to a question the header answers once
— and would have invited a *"yes, through our own extra symbol"*, which is how
a generic ABI acquires a per-component special case.

**One correction it produced, carried forward because it changes planning:**
**three** modules carry `conf/ports.yaml` and a SIL C interface, not two —
`perception-core` as well as `df` and `vdy`, and it is the better `IT-22`
candidate because it sits upstream of `df` on a real data path.

## 3. `G3` — Recordings in, artifacts out

**The pool was** `OQ-11` (is there a port catalogue to adopt), `OQ-10`
(preferred export format), `OQ-22` (licences for proprietary readers), `OQ-09`
(what the bench capture writes). Two were about *naming things that cross the
boundary* and two about *formats crossing it*.

**The principle the group produced.** **A description that is generated cannot
drift; a description that is authored beside it will.** That single line closed
`OQ-11` outright and explains why `OQ-10` and `OQ-22` are so much cheaper than
they look: a format is a codec of four methods behind a registered interface
(`R-SIM-14`), so naming a format costs a table row and *choosing wrongly* costs
a week — whereas authoring a second description of our own ports would cost a
permanent maintenance obligation. Spend the caution where it belongs.

**Two are closed and written back** — `OQ-11` into `SW-0388` and Design `A-4`,
`OQ-10` into `SYS-0111`, both into the register's §4.7. Two remain, and
neither is answerable here.

### 3.1 `OQ-22` — licence and distribution for proprietary readers · **`PROPOSED` — not this document's call; contained, and not yet due**

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

### 3.2 `OQ-09` — what does the bench capture write? · **`NARROWED` — one small ask, and its cost is now one printed field**

**Not answerable here** — no bench capture file exists in this repository, and
no amount of reasoning substitutes for ten seconds of real data. What has
changed is how much rides on it.

**What `G1` removed from this question.** The register lists `OQ-09` as
blocking `SYS-0015`, `SYS-0029`, `SYS-0061`, the foreign half of `OQ-01`, and
`IFQ-06`. After §1:

- **`IFQ-06` no longer depends on it** (closed; register §4.5). The header carries two fields
  regardless of what the bench writes, because the decision rests on what a
  *producer* can know, not on what a *reader* receives.
- **`OQ-01` no longer depends on it** (closed; register §4.7). The highest supported rung is a
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
one of the two inputs to `IFQ-01` (§1.1).

**Cost of leaving it open:** `MP-1` stays provisional and `R-8` stays on the
risk list. **No work package is blocked**, because `DD-13` ships MCAP first and
the crafted fixture exercises every rung.

## 4. `G4` — Where the knobs are · **all three closed and written back**

`OQ-07`, `OQ-04` and `OQ-02`. Written back 2026-08-12 into `SYS-0177`,
`SYS-0082`, `SYS-0108` and the register's §4.7.

**The principle is kept here because it applies to rows not yet worked.** All
three were addressed to *algorithm teams* and all three read as *"should the
system do more here?"*. Each already had a written answer saying **no, and
naming what to do instead** — a deferral with two grounds, a closed verb list
with two alternatives, a bundle rule with an explicit ban on a second edit
site. So the work was not to decide but to **find the existing decision, check
it still holds, and state the condition under which it would be reopened**. A
question re-asked without noticing it was answered is how a closed list gets
quietly reopened, and every one of these three would have enlarged the build if
answered afresh.

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
| Module set | `df` alone for per-cycle cost (the only module with substantial algorithm code — `OQ-05`, register §4.7); `perception-core` → `df` for the multi-module figure |
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
| Change a calibration value | One key in one bundle (`OQ-07`, register §4.7). No rebuild, no code edit |
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
the same question as `OQ-19` (§6.2) and should be answered once, there, for
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

**Twenty rows worked: eleven `CLOSED`, four `NARROWED`, five `PROPOSED`.** The
eleven closed rows have been **written back into their owning documents and
removed from this one** — this document is a queue that drains, not a second
register. What is left below is what is genuinely still open.

**Nothing in the implementation plan is blocked by a question this document
could have answered.** `WP-01` is de-blocked by splitting the harness from the
trigger (§6.1); `SW-0369`/`SW-0323`/`SW-0348` become failable through a
baseline plus a bound (§5); `MP-1` stays provisional on one ten-second sample
file (§3.2) and blocks no package.

**Where the closures came from, which is the useful pattern.** Only three of
the eleven needed a genuinely new decision (`IFQ-06`, and the reframings that
closed `OQ-11` and produced §5's baseline-plus-bound). The other eight were
**already answered by an artifact nobody had re-read** — `adas_sil_abi.h`
answered three module-team questions, an acceptance criterion answered two, and
a `RecordingIndex` field answered one. That is the third time this pattern has
appeared in this project (`SWQ-12`, `OQ-13`, and now eight more), and it is
worth naming as a habit: **before asking anyone, check whether the artifact
already decided.**

**Two corrections the pass produced, both applied:**

1. **Three** modules carry `conf/ports.yaml` and a SIL C interface, not two —
   `perception-core` as well as `df` and `vdy`, and it is the better `IT-22`
   candidate because it sits upstream of `df` on a real data path. Applied to
   Design `IMP-0379`.
2. **The set of common configuration changes was never open** — `SW-0348`
   states it. Only the budget was, which halves `OQ-16`.

**One reversal applied and one recommended:** `IFQ-06` moved from one header
stamp to two and is in `docs/interfaces_signal_header_plan.md` §3. `IFQ-01` is
*recommended* to move from `timestamp_us` to `timestamp_ns` (§1.1) and is
**not** adopted — silence leaves the standing default in place.

---

## 8. Write-backs

### 8.1 Landed 2026-08-12

| Rows | Documents edited |
|---|---|
| `IFQ-06`, `IFQ-02` | `docs/interfaces_signal_header_plan.md` §3, §3.1, §5, §6, §8, §9 (two stamps, the rename, and the three monotonicity refinements); `SW-0043`, `SW-0044`, `SW-0050` |
| `OQ-01` | `SW-0410` (the highest-supported-rung field *is* the answer); register §4.7 |
| `OQ-05`, `OQ-06`, `OQ-12` | `SYS-0048`, `SYS-0192`, `SYS-0071`, `SYS-0072`, Design `IMP-0379`; register §3 module-teams block emptied |
| `OQ-10`, `OQ-11` | `SYS-0111`, `SW-0388`, Design `A-4` |
| `OQ-02`, `OQ-04`, `OQ-07` | `SYS-0108`, `SYS-0082`, `SYS-0177`; register §3 algorithm-teams block emptied |

### 8.2 Outstanding — these wait on a row that is not closed

- **`SW-0033`** — remove the "only unit conversion in the engine" carve-out
  rather than amending it. **Only if `IFQ-01` is ratified to ns** (§1.1).
- **`SW-0369` / `SW-0323` `Now.`** — budget file plus declared reference
  configuration; values as regression bounds seeded from the first measurement
  (§5.1). Held until the reference *host* is known, which is `OQ-15`.
- **`SW-0348` `Now.`** — add the structural gate (§5.2); the wall-clock budget
  stays open.
- **`WP-01`** — split into harness (vendor-independent, do now) and trigger
  (~10 lines, on the vendor answer), with the `contrib/` home per `DD-08`
  (§6.1).
- **`WP-18` / risk `R-8`** — restate the ask as the four-item minimum in §3.2.
- **Register hygiene** — move `OQ-22` out of the baselining gates and attach it
  to the two format work packages; merge `OQ-19` into `OQ-15`'s retention half.

---

## 9. What to ask, and of whom

The pass reduced twenty rows to **five asks**. Four are one sentence each.

| # | Ask | Of whom | Why it is worth asking now |
|---|---|---|---|
| 1 | *Does any output of this tool enter a safety argument?* | Quality / safety | One sentence; determines whether `OQ-17`'s fallback is ever exercised. Cheapest question here to ask, potentially the most expensive to leave (§6.4) |
| 2 | **Ten seconds of bench capture**, its channel list, and one sentence on re-stamping | A recording owner | Retires plan risk `R-8` and makes `MP-1`'s exit real rather than provisional (§3.2) |
| 3 | *Ratify `timestamp_ns`, or keep `timestamp_us`?* | Whoever owns the interfaces contract | Reverses a stated default, so it needs a nod rather than silence (§1.1) |
| 4 | Which CI system, and the retention policy for both CI artifacts and campaigns | DevOps + whoever owns storage/audit | One answer, two consumers (§6.1, §6.2). Only the ~10-line trigger waits on it |
| 5 | Wall-clock budgets for the five configuration changes — **after** we measure them once and show the numbers | A customer team | A number to react to gets an answer where an open question does not (§5.2) |

Everything else in the register is either closed and written back (§8.1) or
attached to the work package where it becomes real.
