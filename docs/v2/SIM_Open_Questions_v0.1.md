# SIM v2 — Open Questions Register

**One place to answer everything.** Assembled 2026-08-11, last updated
2026-08-13. This document holds no questions of its own — it is a **view** over
the authored documents, so that answering is one pass instead of four. Each row
says where the question lives, what it blocks, and what happens if it is left
alone. **The source documents remain authoritative**; when a row is answered,
the answer is written back into the owning document and the row moves to §4.

| Marker | Meaning |
|---|---|
| `DEFAULT` | A default is stated and argued. Silence adopts it; that is safe but should be deliberate |
| `BLOCKS` | Something cannot be finished — usually a threshold that cannot be set, so a requirement cannot be failed |
| `EXTERNAL` | Not answerable inside this repository. Needs a recording owner, a module team, quality, or DevOps |

---

## 0. Where it stands after the 2026-08-13 pass

**The register is effectively drained.** All fourteen design decisions
confirmed; **fourteen `SWQ` closed**; **twenty of twenty-two `OQ` closed**; **all
six `SignalHeader` questions closed**. **All five baselining gates are clear**,
so the System Requirements have no remaining barrier to baselining.

**Two rows survive, and neither is a decision.**

| Row | What it is | Why it does not block |
|---|---|---|
| `OQ-09` | A ten-second real bench capture | **Evidence, not design.** The codec and the recovery ladder are specified and buildable either way. What the file changes is whether `MP-1`'s exit rests on a fixture the team wrote itself. **A sample was confirmed obtainable on 2026-08-13**, so this is scheduled rather than open |
| `OQ-15` | Which CI system | **Ten lines.** The check harness is vendor-independent and completes `WP-01`; the trigger file is written the day the vendor is known. Jenkins is likely, not committed |

**What the 2026-08-13 answers cost, which is the interesting number.** Nine
items were answered. They produced **three new concept statements, three new
system requirements, three new software requirements, three new design rows and
one ratified word** — and changed no interface, no seam and no requirement
style. Two risks retired outright (`R-4`, and `R-8` scheduled).

> **A seam that absorbs an answer without deforming is a seam drawn in the right
> place.** That has now held four times: naming three formats changed the plan's
> shape not at all; naming the export formats likewise; naming the performance
> absolute changed no interface; and answering the qualification question — the
> one row that could have invalidated the *form* of every other answer — added
> requirements and re-styled nothing. The converse was the real test and it was
> passed: had `OQ-17` demanded a different requirement style, **that** would have
> been the finding.

**The recurring finding, now confirmed for the fourth time and worth carrying
forward as a working habit: most of what was open had already been answered by
an artifact nobody had re-read.** The C ABI header closed three module-team
questions without anyone being asked. Two acceptance criteria closed two more.
`SW-0348`'s own `Shall` contained the change list `OQ-16` was asking for.
And `IFQ-01` — argued over two days across two documents — was settled by
`CN-0019`, which has said *"internal timestamp (µs)"* in the concept baseline
the whole time.

---

## 1. Open and answerable here

*Empty. `IFQ-01`, the last row in this section, was ratified 2026-08-13 — see
§4.5.*

**`IFQ-05` is reframed rather than open** — see the signal-header plan's §8.1.
The question was whether the schema check should read every component's
`conf/ports.yaml` (common, nothing drifts) or interfaces should keep its own
list (standalone, but a second copy). The recommendation is a third shape that
takes both wins: the check reads **whichever `ports.yaml` files are present** —
none in a bare interfaces clone, all in CI — so there is no second list and
interfaces never *requires* a sibling. One thing to confirm: the standalone case
must **report what it saw**, because a check that silently passes on zero inputs
dies quietly. That is now a general rule rather than one question's answer:
`WP-01`'s exit requires every check to report its scan count and to read
`SKIPPED` rather than `PASSED` when it scanned nothing.

---

## 2. Inherited from the System Requirements — the baselining gates

**All five are closed.** `SIM_System_Requirements_v0.1.md` §26 listed
twenty-two questions, of which five were gates: that document was not baselined
until each had an answer or a written fallback.

| ID | Closed | Answer in one line |
|---|---|---|
| `OQ-01` | 2026-08-12 | It stopped being a global question — the supported rung is measured per recording |
| `OQ-11` | 2026-08-12 | Derive the catalogue from the manifests present; neither adopt nor define |
| `OQ-14` | 2026-08-13 | 1000 recordings overnight on 8 cores / 32 GB, derived to per-worker budgets |
| `OQ-16` | 2026-08-13 | The set was never open; the gate is structural, the stopwatch is an observation |
| `OQ-17` | 2026-08-13 | **Yes** — outputs enter a safety argument. Cost: addition, not re-styling |

SYS §26.1 records the closure and one thing worth keeping: **`OQ-17`'s written
fallback was never exercised, and it had over-provisioned.** The fallback said
*re-styling is accepted as a known, scoped cost*. The answer arrived first, and
the yes cost three concept statements, three system requirements and three
design rows — because the set was already written in the shape a qualification
argument asks for, and was written that way because *a requirement nobody can
fail is worthless*, not in anticipation of an auditor. **That is precisely what
makes it usable as evidence.**

---

## 3. Inherited — what remains

| ID | Question | State |
|---|---|---|
| `OQ-09` | What exactly does the **bench capture** write, and does it preserve the signal header end to end? | **Scheduled.** A sample is obtainable (2026-08-13). It is verification evidence, not design input — no work package is blocked; `MP-1`'s exit is *provisional* until `WP-18` re-runs the ladder against a real file, which retires plan risk `R-8`. The minimum ask is in §6.3 |
| `OQ-15` | Which **CI system**, and what artifact retention? | **Vendor undecided; Jenkins likely.** Does not block `WP-01` — see §6.8. The retention half was answered with `OQ-19` |

Closed from this section on 2026-08-13: `OQ-18` (algorithm test manager or
product owner), `OQ-19` (customer retains results), `OQ-22` (licences agreed in
principle, moved onto the format work packages). **Module teams** and
**algorithm teams** were emptied outright on 2026-08-12 — seven questions, every
one already answered by an artifact.

---

## 4. Answered

### 4.1 All fourteen design decisions — confirmed 2026-08-11

Every `DD-nn` in `SIM_Implementation_Design_v0.1.md` §1 reads `ADOPTED`; the
`CONFIRM` / `CONFIRM·HARD` marks are gone rather than left standing stale. The
three that had been marked `CONFIRM·HARD` — expensive to reverse — are worth
naming, because they are the ones whose reversal would now cost a restructure
rather than an edit:

| ID | The decision |
|---|---|
| `DD-03` | `simcore` is C++17 inside and exposes a **flat C ABI** to every embedder |
| `DD-04` | **Exactly one codec implementation**, in C++; the player reads through the C ABI, not a second Python codec |
| `DD-12` | The **live world-model client is removed entirely** — no `sources/`, no world-model plug-in, no live stimulus. Every input is a recording |

The other eleven: `DD-01` (deliverable layout and the separator rule),
`DD-02` (JSON run spec), `DD-05` (static data is a port kind), `DD-06` (typed
description artifacts), `DD-07` (three statements), `DD-08` (`check/` moves to
`contrib/`), `DD-09` (isolation over a pipe), `DD-10` (package name = item
name), `DD-11` (header before ladder), `DD-13` (MCAP only in R1),
`DD-14` (`convert`, not `record`).

### 4.2 The six the decomposition raised against itself — closed 2026-08-12

SwReq §34.3 holds the full text. Each was invisible while only one document was
open, and **five of the six are one question wearing different clothes**: *what
does the configuration layer know, and how did it find out?*

| ID | Question | Answer |
|---|---|---|
| `SWQ-09` | How does **simulation time advance**? Three requirements decide that a module runs and none says what one tick is | One grid step per tick from the run start, moved by nothing else (`SW-0413`). The data-driven trigger becomes a **predicate on a tick** rather than a second clock (`SW-0065`), and where a recorded rate contradicts a declared period the recording wins and both numbers are reported (`SW-0414`) |
| `SWQ-10` | Does a **data-driven module's period enter the base grid**? | Yes — every module's, whatever triggers it; no static port's (`SW-0006`). Otherwise the grid can be coarser than that module's own data and the predicate coalesces arrivals it should have seen separately |
| `SWQ-11` | Is a near-equal period **snapped** to fit the grid, or refused? | Refused, naming both integers, with no tolerance key anywhere (`SW-0173`). Two requirements had answered this in opposite directions, and one of them contradicted `R-SIM-18` |
| `SWQ-12` | **Who reads what is inside a recording**, before the run? Three obligations need a file's topic list and all three live in items forbidden to open a file | `SI-13` produces a `RecordingIndex` and a `ModuleManifest` as plain data through the interfaces the run itself uses; every consumer receives them as arguments (`SW-0410`, `SW-0411`) |
| `SWQ-13` | Is the spec emitted in **one pass or two**? | Two — probe, then emit — with every probed recording's hash in the spec so a spec cannot be executed against a file it was not emitted against (`SW-0412`, Design §3.3a) |
| `SWQ-14` | May the configuration layer **bind the C interface** at all? | Yes, in `SI-13` only, bounded **by symbol**: manifest, version and describe may be called; initialise, execute, shutdown and step may not (`SW-0409`). Forbidding execution by symbol is stricter than forbidding the binding by folder, and it is the only form that survives the probe pass existing |

### 4.3 Five `OQ` closed early

| ID | Answer |
|---|---|
| `OQ-08` | **The format list.** MCAP (the system's own interchange format) · MDF4 (vehicle measurement) · TDMS (bench capture). Priority order is moot: `DD-13` ships MCAP now and writes each other reader the week its first sample file arrives. **Naming them changed the plan's shape not at all**, which is the useful signal — a format is a codec of ~4 methods behind one registered interface, so three names is three rows in the codec table. Had it propagated further, the codec seam would have been wrong |
| `OQ-03` | **Module instances: declared unbounded, exercised at two, shipped at one.** `SYS-0043` already requires instance renaming and `SYS-0036` makes port identity independent of which component produces it, so an additional instance costs a name prefix and nothing else. Asking the module teams for a number invites an answer that becomes a limit |
| `OQ-13` | **Same-step execution is the default, and the per-edge delay is carried from day one with a value of zero.** The Resolved Run Spec already declares `delay_steps` per edge and `SYS-0077` is `R1`, so the field costs nothing to carry and the modelling becomes data rather than a later redesign. The question was answered by the artifact before it was asked |
| `OQ-20` | **Naming: the requirement documents use neutral role names — player, launcher, batch; the product and its user interface keep their own.** Two vocabularies for one thing is only a problem when both claim to be normative, and this settles which is. It was blocking in exactly one place: the module's context file cannot be corrected while it is open, and `WP-02` corrects it |
| `OQ-21` | **The interactive viewer: keep what exists.** The scene layer is the strongest area of the current codebase and `WP-26` is a split of a working surface, not a rewrite. Adopting a third-party surface would discard the one part of the previous effort that is unambiguously right, to solve a problem nobody has reported |

### 4.4 `CN-0282` — concept amendment applied

`CN-0282` read *"driving a live simulator is a plugin concern, never a core
one."* With `DD-12` confirmed it now reads *"out of scope entirely — a foreign
simulator reaches the system only as a recording, through the ordinary codec and
ingest-map path."* Design §33 records the change and its date. This was the one
item the Design said *"should not sit open"*, because the next reader of the
concept would have believed the weaker wording.

### 4.5 `SignalHeader` — all six closed

| ID | Answer |
|---|---|
| `IFQ-01` | **Microseconds — ratified 2026-08-13**, an explicit act by the contract owner rather than a default adopted by silence. `source_timestamp_us` / `capture_timestamp_us`, `uint64`. The 2026-08-12 counter-evidence recommending `_ns` was considered and not adopted, and **the argument that settled it had been sitting in the baseline the whole time: `CN-0019` requires *"internal timestamp (µs)"* on every module output interface.** Ratifying `_ns` would have put the wire contract in contradiction with the document every other document derives from, needing a concept amendment to be correct rather than merely different. Two consequences, both now written down rather than assumed: `SW-0033`'s coarser-unit clause is **load-bearing rather than vestigial** — the ×1000 to the engine's nanosecond timebase happens once, at ingest, in the one component that owns that timebase — and `SW-0044`'s *"integer-nanosecond"* wording describes the **engine's internal representation, not the wire**, which is stated in that requirement because it was cited during the argument as evidence for the opposite conclusion. **The accepted residual risk is named, dated and triggered:** a sub-microsecond source would be silently truncated inside shipped bytes, so the finest resolution observed in `OQ-09`'s bench sample is measured at `WP-18`, **before any producer encodes** |
| `IFQ-06` | **Two fields, not one** (2026-08-12, *reversing* the previous day's "one field now" — and removing its stated dependency on `OQ-09`). `source_timestamp_*` is always filled; `capture_timestamp_*` is proto3 `optional` and unset when unknown. The decision rests on **what a producer can know**, not on what a reader receives, which is why the bench capture no longer decides it. `SW-0044` requires validity time *in this header* as an explicit unknown, which one field cannot satisfy; ladder rung 3 and `age_s` are two `R1` consumers wanting two different stamps; and `time_stamp` was exactly the ambiguous name `SW-0044` forbids |
| `IFQ-02` | **Required; a violation is reported and demotes the port to rung 4; never clamped** — clamping turns a producer's timing bug into a plausible-looking zero. `SW-0050`'s acceptance already carried this; closing it added three refinements, each preventing a check that would be wrong unnoticeably: **non-decreasing, not strictly increasing** (two messages legitimately share a stamp); **per port, never across ports** (two producers share no clock discipline); and **it binds source time** — an out-of-order capture time is reported but does not demote, since it yields a negative `age_s` that must surface rather than be clamped |
| `IFQ-03` | **Wrap at `uint32`.** The bus handles wrap explicitly, so rung 2 never reads a wrap as a gap |
| `IFQ-04` | **The three legacy messages are dummy**, so they are left untouched — no field added, `adas.common.Header` not deprecated. This *reverses* the plan's draft ("add it while the field is free"): wire compatibility protects encoded bytes that exist, and for a message nobody produces there are none. `R-IFACE-4` is scoped by *"can be a port payload"*, so the schema check demands a header the day one gains a real producer — the obligation is enforced when it becomes real, with no list to remember |
| `IFQ-05` | **Reframed, not open** — §1 above. The check reads whichever `conf/ports.yaml` files are present, so there is no second list and interfaces never requires a sibling checkout |

### 4.6 The eight `SWQ` from the decomposition

| Was | Closed by |
|---|---|
| `SWQ-01` — where does the C++ subtree live? | `DD-01` |
| `SWQ-02` — is static data a port class? | `DD-05` |
| `SWQ-03` — one description artifact or several typed? | `DD-06` |
| `SWQ-04` — Resolved Run Spec serialisation? | `DD-02` |
| `SWQ-05` — C ABI or C++ with a shim? | `DD-03` |
| `SWQ-06` — the line budget for `SW-0230`? | `DD-07` |
| `SWQ-07` — who owns `check/`? | `DD-08` |
| `SWQ-08` — per-stage isolation mechanism? | `DD-09` |

**Also settled, without having been a numbered question:** the `simcore` /
`sim-engine` spelling split, resolved to `simcore` / `simengine` and written
into `DD-01` as a rule so it cannot drift back.

### 4.7 Closed by the 2026-08-12 answers pass

Worked in `SIM_Open_Question_Answers_v0.1.md`, which groups the register's rows
by shared mechanism rather than by owner and argues each to a verdict.

| ID | Answer |
|---|---|
| `OQ-07` | **The system passes a *path*, never a *value*.** `adasInit` takes `configPath`; `SYS-0177`/`R-SIM-3a` settle the rest. Injection is forbidden by name — the bundle is *"a build output, never a second place to edit a value"* — and `SYS-0177`'s own acceptance (*the viewer reads the same bundle the module was initialised with, and states which one*) is unsatisfiable if a value can arrive from elsewhere, since there would be two answers to *"what wheelbase did this run use?"*, free to disagree. **A sweep is a bundle variant**: copy, patch one key, re-hash, record the hash |
| `OQ-04` | **Yes — and the question understates what exists.** Addressability is four levels deep, not two: per module (`SYS-0080`), per port (`SYS-0082`), **per field path** (`egoDyn.vx`) and **per repeated element** (`[i]`, `[*]`). The one missing axis — time-varying or conditional overrides — is missing **on purpose**, because *an override may destroy or attenuate information, never create an entity*. **This was the row most likely to enlarge the build if answered afresh**: asking teams *"is it sufficient?"* invites *"it would be nice if…"*, and each nice-to-have is a predicate in a list that is closed for a written reason. Reopen only on a concrete case, with a recording, that neither alternative serves |
| `OQ-02` | **No — already deferred, on two grounds, only one of which was tied to `OQ-01`.** `SYS-0108` is `P2 · DEF` and off by default. The revisit trigger is **restated**: ego re-integration may be considered for a recording whose ports report **rung 3 or better**, and only once the divergence machinery is trusted. The timing dependency was never arbitrary — integrating over per-cycle `dt` is only as sound as the rung — and on a rung-4 recording the integration would run on *reception* time, so it would be measuring the wrong thing rather than merely approximating |
| `OQ-11` | **Derive it — neither adopt nor define.** The catalogue `SW-0388` requires is the union of the `ModuleManifest`s present in the run, computed at load. *Defining* one creates a second description of a port set we own, free to drift; *adopting* an external one as the **resolution authority** has the same defect and lets an outside document decide whether a port our compiler emitted is legal. Deriving has neither defect. **If an organisation catalogue exists, adopt its vocabulary and never its authority**, so a late answer costs a rename rather than a redesign |
| `OQ-10` | **`R1` is already fixed by `SYS-0111` + `DD-13`: MCAP** (interchange *and* replayable) **and CSV/TSV** as the columnar text export, registered **write-only** because it cannot round-trip. A team's preference **cannot block**, because a format is ~4 methods behind a registered interface and no exporter is mandatory. **Re-ask it at the first export review as a scheduling input, not as a gate** — an export nobody opens is dead weight |
| `OQ-05` | **A measurement, not a survey — and the criterion is not "functional".** What `E2E-02`/`E2E-03`/`E2E-10`/`IT-22` can be planned against is the output of `sim probe <lib>`, dated, rather than a document that goes stale. **Measured 2026-08-12: three** modules carry `conf/ports.yaml` and a SIL C interface — `df` (9 215 `src/` C++ lines, two real functions), `perception-core` (517) and `vdy` (409) — **correcting this register's earlier "df and vdy are the two"**. `perception-core` is the most useful `IT-22` candidate: it sits upstream of `df` on a real data path |
| `OQ-06` | **No module supports it, none can, and nothing depends on it.** The ABI has five exports and no reset entry point, so this was never a module-team question. `adasShutdown` + `adasInit` is an **exact** reset for all handle-scoped state and needs zero module changes. The one hazard it does not cover — a surviving process-level `static` — is detected by `SYS-0192`'s *own* acceptance criterion (a shuffled batch differs), and `DD-09`'s one-subprocess-per-recording guarantees exactness where it must be guaranteed rather than tested |
| `OQ-12` | **No — unrepresentable over this ABI.** The period is read from the config bundle at manifest-build time and reported through `adasManifest`, which is callable before `adasInit` and returns a snapshot; `adasExec` takes `dtS` and no rate argument. The residue — a module that *behaves* at a rate other than the one it declares — is already `SYS-0071`, and that is a **stronger** guarantee than a survey answer, because it also holds for modules that would have answered wrongly |
| `OQ-01` | **It stopped being a question.** *"Do the recordings in scope carry task/cycle marking?"* is not answered globally for a corpus nobody has enumerated — `SW-0410`'s `RecordingIndex` reports, per topic, *"the highest timing rung the data supports"*, computed before every run and printed by `sim probe`. A capture format nobody has seen yields an unknown **value**, never an unanswered question, and rung 1 being inert becomes observable rather than assumed |

### 4.8 Closed by the 2026-08-13 answers pass

The nine that §6 had been written to explain. Each is recorded here in one row
and told at length in §6.

| ID | Answer | Landed in |
|---|---|---|
| `IFQ-01` | **Microseconds**, ratified — §4.5 above carries the full entry | Signal-header plan §3 and its §8 table · `R-IFACE-4` · `SW-0033` and `SW-0044` notes |
| `OQ-09` | **A sample is obtainable.** Scheduled, not open. Retires `R-8` at `WP-18`; also carries `IFQ-01`'s truncation check | SYS §26 · Design §32 · Plan `R-8` |
| `OQ-22` | **Agreed in principle**, and **moved off the gates onto the two format work packages** — asked per format by somebody holding a real file. Procurement, not architecture. The copyleft-statically-linked case is the one that bites; the vendor-SDK redistribution conversation is the only item in the register with a months-long latency, so it starts now | `SYS-0011` note · SYS §26 |
| `OQ-14` | **1000 recordings overnight, 8 cores, 32 GB, lean `df`.** Derived in SYS §18.0 to **per-worker** budgets — ≥ 10.4 recordings/hour, ≤ 5 min 46 s per recording, ≤ 4 GB peak — plus a six-axis reference configuration. Frame time and estimate accuracy had no absolute and are **seeded** from their first measurement | `SYS-0234`/`0235`/`0238` · `SW-0272`/`0323`/`0369` · `ANL-34`/`35`/`37`/`40` · `ANL-SW-43`/`52`/`63` · `R-4` retired |
| `OQ-16` | **Structural gate agreed.** The change set was never open — it was in `SW-0348`'s own `Shall`. CI asserts the **diff**; the wall clock is measured once and carried to the customer as an observation | `SYS-0175` · `SW-0348` · `ANL-25` · `ANL-SW-57` · `UT-LNC-07` · `SYT-CFG-18` · `CT-15` |
| `OQ-17` | **Yes — tool outputs will be cited in a safety argument.** First-level goals embedded at all four layers, naming no standard and no confidence level | Concept §2.4 (`CN-0400`…`CN-0402`) · SYS §23a (`SYS-0289`…`SYS-0291`) · SwReq §29.1 (`SW-0415`…`SW-0417`) · `IMP-0415`…`IMP-0417` · `ANL-56`…`58`, `INSP-13`, `ANL-SW-76`…`78`, `INSP-SW-11` |
| `OQ-15` | **Undecided; Jenkins likely.** Harness/trigger split adopted so `WP-01` completes regardless | `SYS-0201` note · `SW-0376` · `WP-01` |
| `OQ-19` | **The customer retains results**, in the format named in the run configuration, on storage they own. Durations are not this system's to set; what it owes is that a retained result is self-describing | `SYS-0184` note |
| `OQ-18` | **Algorithm test manager or product owner.** No requirement changed — `SYS-0281`'s split is already the one the answer names | `SYS-0281` note |

## 5. Assumptions this register does not turn into questions

`SIM_Implementation_Design_v0.1.md` §31 lists seven (`A-1`…`A-7`). They are
*stated* assumptions, not open items — each is a position taken deliberately
with its consequence named. They are listed here only so that "not in the open
questions register" is not read as "nobody thought about it". `A-4` was `OQ-11`
wearing different clothes, and `OQ-11` closed the way `A-4` assumed.

---

## 6. Plain-language record — the nine answered on 2026-08-13

**Why this section still exists.** It was written to explain nine open items to
somebody who had to decide them. They are decided, and it is now the record of
*what was decided and why* — which is the more valuable of the two, because the
reasoning is what a reader in six months needs and is exactly what a one-cell
table loses. Each item is told from the start: what was asked, how the question
arose, what the answer causes downstream, and what — if anything — is left.

### 6.0 Six words you need first

| Word | What it means, plainly |
|---|---|
| **Port** | One named input or output of a software module — `df.bsd.outputs`. The tool never addresses data by position, only by name, because a name survives a code change and a position does not. |
| **Recording** | A file of timestamped messages. Ours, another team's, a bench tool's, a foreign simulator's — the tool treats all of them as the same shape. |
| **Resim** | Re-running the *real* algorithm library against a recording. Not a replay: a replay draws what was already computed, a resim executes the code again and can therefore disagree with the file. This is the thing that goes in CI. |
| **Cycle recovery ladder** | The hard part of reading somebody else's recording is not parsing bytes — it is working out **which messages belong to the same computation step**. Our own files say so outright. A foreign file may not, so there is a declared ordered ladder of four fallbacks: (1) a cycle id the source wrote, (2) the cycle counter in our signal header, (3) source time, (4) reception time from the file envelope. **Rung 4 is the bad one** — it groups messages by when a logger happened to receive them, which is approximately right and quietly wrong at the edges. Which rung a file supports is *measured per file*, not assumed. |
| **Codec** | A reader/writer for one file format, about four methods, behind one registered interface. This is why "which formats?" is a cheap question: naming a format adds a table row, not a design. |
| **Work package (`WP-nn`) / milestone (`MP-n`)** | The unit of build work in the implementation plan, and the phase it belongs to. `MP-1` — *"fix the clock"* — is the phase whose entire purpose is making foreign recordings reconstruct into correct cycles. |

### 6.1 The nine at a glance

| # | Row | Answer given | Consequence |
|---|---|---|---|
| 1 | `IFQ-01` | **Microseconds** | One word ratified; the µs↔ns conversion stays at ingest, where it was already written |
| 2 | `OQ-09` | **A sample is possible** | `R-8` becomes scheduled; `MP-1`'s exit stops being permanently provisional |
| 3 | `OQ-22` | **Yes, pursue the readers** | Moves off the baselining gates onto the two format work packages |
| 4 | `OQ-14` | **1000 recordings overnight, 8 cores, 32 GB** | Three performance requirements become failable; `R-4` retires |
| 5 | `OQ-16` | **Structural gate agreed** | The success measure becomes checkable in CI today |
| 6 | `OQ-17` | **Yes — safety argument** | Three statements per layer added; **no re-styling** |
| 7 | `OQ-15` | **Undecided, Jenkins likely** | `WP-01` proceeds on the harness half |
| 8 | `OQ-19` | **Customer retains results** | No requirement changed; one note added |
| 9 | `OQ-18` | **Algo test manager / product owner** | No requirement changed; one note added |

---

### 6.2 `IFQ-01` — microseconds, ratified

**What was asked.** One word. Every message crossing a component boundary
carries a small header saying who produced it and when. The question was the
*unit* of that "when": millionths of a second, or billionths.

**How it arose.** The header that exists today has a 32-bit `time_stamp`. Two
defects in it were found and fixed before this question: **32 bits of
nanoseconds wraps to zero every 4.29 seconds** (widened to 64), and **the name
did not say which clock it was** — there are genuinely two. *Source time* is
"when the producer computed this", always knowable. *Capture time* is "the
instant the data actually describes" — when the shutter opened, when the radar
swept — which a producer often does not know, and which must then read *unknown*
rather than be filled with something plausible. Both were settled: two
differently-named fields, capture optional. **Only the unit remained**, and it
remained because it is the one piece that must be right before anything is
encoded.

**The argument, and how it ended.** A day earlier, a careful case had been built
for reversing to nanoseconds: the two units already coexist in a shipped
contract so "one unit per contract" was not a property being protected; a
configured value and a measured value are different kinds of thing; nanoseconds
represent everything microseconds can, so the choice that makes a missing input
file irrelevant is the cheaper one to be wrong about. That case was real, and it
was not what settled the question.

> **`CN-0019` had said microseconds the whole time.** It is an entry condition
> on the customer in the concept baseline: *every module output interface shall
> carry a signal header with at least: internal timestamp (µs)*. Ratifying
> nanoseconds would have put the wire contract in contradiction with the
> document every other document derives from — it would have needed a **concept
> amendment** to be correct rather than merely different, and nobody arguing the
> question had noticed. This is the register's recurring finding for the fourth
> time, and the clearest instance of it: two days of argument across two
> documents, settled by a line that had been baselined for weeks.

**What it causes, and what is now written down rather than assumed.** Two
things, both of which were cited *during* the argument as evidence and so will
be re-encountered by the next reader:

- **`SW-0033`'s coarser-unit clause is load-bearing, not vestigial.** The engine
  keeps all internal time in integer nanoseconds (`SW-0046`), so the ×1000
  happens once, at ingest, descriptor-driven, in the one component that owns the
  nanosecond timebase. Had `IFQ-01` gone the other way this clause would have
  been deleted. It was not, so the exception `ANL-SW-02` grants that one site
  stays and is exercised on every run rather than sitting unused.
- **`SW-0044`'s "integer-nanosecond" wording describes the engine's internal
  representation, not the wire.** That sentence was quoted as an argument *for*
  a nanosecond wire field. A note now says so in the requirement itself, because
  a reader arriving cold would make the same inference. **The two clauses do not
  conflict: one fixes a unit at the boundary, the other inside it.**

**The accepted residual risk, named rather than swallowed.** A source that
genuinely reports finer than a microsecond would be **truncated** by this
contract — silent loss inside shipped bytes, the worst shape a wire defect can
take. That risk is now managed rather than merely accepted: the **trigger** is
the finest timestamp resolution observed in `OQ-09`'s bench sample, measured at
`WP-18`; the **window** is before any producer encodes, while the fix is a
rename rather than a migration; and if it fires, `IFQ-01` reopens **together
with** `CN-0019`, since the two must not disagree. An accepted risk with a
trigger, a window and a stated consequence is managed; the same risk accepted
silently is the one that surfaces after N components have encoded.

---

### 6.3 `OQ-09` — the bench capture sample

**What was asked.** Not a specification, not a format document. One real file,
its channel list, and one sentence.

**Why it mattered.** `MP-1` is the milestone whose whole purpose is making
foreign recordings reconstruct into correct cycles. Its exit criterion is
currently tested against a fixture **we wrote ourselves**, and the plan states
the hazard bluntly as risk `R-8`: *a fixture the team wrote encodes the same
assumptions the recovery ladder does, so it validates the guess rather than the
data.* That is the kind of thing that passes every test for six months and then
fails on the first customer file.

**The answer: a sample is obtainable.** So `R-8` moves from *open* to
*scheduled*, and `MP-1`'s exit stops being permanently provisional. Nothing was
blocked in the meantime — by the time this was answered, the row had been
deliberately stripped of everything that depended on it: the header decision no
longer rested on it (it rests on what a *producer* can know, not on what a
*reader* receives), and the cycle-marking question had stopped being a global
yes/no (every recording is probed and reports its supported rung per topic). So
what remained was verification evidence, which is exactly what arrived.

**The ask, kept small so it stays easy to say yes to.**

1. One file, **ten seconds**, from any routine bench run — no special
   configuration, nothing staged.
2. The **channel/topic list** as the tool exports it.
3. **One sentence**: does the capture chain re-stamp messages as it records
   them, or pass the producer's own stamp through?

**Three things are measured on arrival**, and the third has grown in importance
since the ask was first written: whether a per-message reception stamp exists
(decides whether rung 4 is available for that format at all, and therefore
whether the codec must declare a degraded capability); whether our signal header
survives end to end (decides rungs 2 and 3); and **the finest timestamp
resolution present**, which is now `IFQ-01`'s truncation trigger (§6.2) rather
than an input to a choice already made.

---

### 6.4 `OQ-22` — licences for the third-party format readers

**What was asked.** Two of the three formats in scope are not ours. Reading them
means an open-source reader, a vendor SDK, or a clean-room implementation — and
somebody has to say which is acceptable to ship.

**The answer: yes, pursue them — and the row moves off the baselining gates onto
the two format work packages.** It is asked per format in the week its first
sample file arrives, by somebody holding a real file rather than in the
abstract, which is the only way that question gets a precise answer.

**Why moving it is safe, and not just convenient.** One decision bounds this
completely: **exactly one codec implementation, in C++, behind a registered
interface of about four methods.** A reader touches no engine code, appears in
no other component, and can be replaced without a single caller changing. That
makes this **procurement, not architecture** — the third instance of the signal
that says the codec seam was drawn in the right place.

**What to check when each is asked.**

| Option | What it costs | What must be checked |
|---|---|---|
| An open-source C++ reader per format | Least code | The licence class against how the deliverable ships. **The case that bites is a copyleft reader statically linked into a delivered library.** Dynamic linkage is the usual mitigation and still needs sign-off |
| A vendor or consortium SDK | Least risk of misreading the format | Redistribution terms, per-seat or per-deliverable cost, and platform coverage — the portability contract requires **both** Windows and Ubuntu |
| A clean-room reader from the published specification | No licence exposure, full control | The largest engineering cost, and only reasonable for the subset of the format actually present in our files |

**The one thing that does not wait.** If a vendor SDK is even a candidate, the
redistribution-terms conversation opens now. It is the only item in this entire
register whose latency is measured in **months** rather than days, and it is the
one way this row could still become a schedule problem after being closed.

---

### 6.5 `OQ-14` — the performance numbers

**What was asked.** Three numbers — the cost of one simulation cycle, how many
recordings a batch campaign clears per hour, and how long the player takes to
draw one frame — plus the configuration each is measured on.

**Why an absent number was a real defect.** The concept says it directly: *a
performance requirement with no threshold cannot be **failed***. A requirement
nobody can fail will be declared satisfied, which is worse than not having one,
because it occupies the slot where a real check should be.

**The answer supplied.** *A campaign of **1000 recordings** must finish
**overnight** on a **PC with 8 cores and 32 GB of RAM** running a **lean `df`
library**. On a server it goes higher, because more runs can be executed at
once.*

**One interpretation was added and it is the only invented number.** *Overnight*
is read as **12 hours**, declared as a constant in the budget file rather than
folded into the requirements — so correcting it to 8 h or 16 h is one edit and
every figure below moves with it.

**The derivation.** Parallelism is across runs and never inside one, and batch
runs one subprocess per recording. So the campaign figure is not a property of
the system — it is `workers × per-worker rate`, and only the second factor is
ours:

| Quantity | Value | From |
|---|---|---|
| Aggregate throughput | ≥ 83.3 recordings / hour | 1000 ÷ 12 |
| **Per-worker throughput** | **≥ 10.4 recordings / hour** | 83.3 ÷ 8 workers |
| **Wall time per recording** | **≤ 5 min 46 s** | 3600 ÷ 10.4 |
| **Peak resident memory per worker** | **≤ 4 GB** | 32 GB ÷ 8, so eight workers fit |

**The structural point, and the reason it is written this way.** Budgeting **per
worker** is what makes *"on a server it goes higher"* a **derived figure rather
than a second requirement**. A campaign throughput stated as an absolute would
have to be re-negotiated on every host — which is how a performance budget
quietly becomes advisory. Stated per worker, a 64-core server changes the
derived aggregate and nothing else.

**The half that actually causes trouble is not the number — it is the reference
configuration.** Two measurements on different setups look like a regression and
burn a day every time. All six axes are pinned in SYS §18.0: host (recorded
*beside* every budget, so moving to CI hardware is a visible re-baseline rather
than a mystery), module set, recording fixture with its hash, tick and layer
count, build configuration, and worker count.

**Where no absolute existed — frame time, estimate accuracy — the budget is the
first measurement.** Both requirements are written to catch a *regression*, and
a regression is a comparison, so the first measurement supplies the number and
the requirement becomes failable from the second run. This reuses the mechanism
determinism tolerance already defines — a row, a value, a mandatory `why:`, its
hash in the run manifest, and **the consumed headroom printed on pass as well as
on fail**, which is the only anti-spiral device that does not depend on somebody
choosing to look. **Seeded is not unsupplied**, and the test specifications now
say so explicitly, so the `⊘` marker keeps meaning *"no observation could fail
this today"* rather than quietly widening to cover both.

**What a baseline-derived budget still does not answer:** *"is it fast
enough?"* — an absolute, which stays with whoever owns throughput expectations.
For the campaign figure that owner has now answered; for the other two they have
not, and the harness no longer waits on them.

---

### 6.6 `OQ-16` — how long may a common configuration change take?

**Half of it was never open.** The register asked for *"the set of common
configuration changes **and** each one's budget"*, as if both were missing. The
set is written into the requirement itself — **switch a module's mode · change a
calibration value · add a recording · change the layout · add an export.** Five
items, named. Only the budget was missing, which halved the question before
anyone answered anything.

**Why the remaining half resisted being answered as written.** The requirement
says each change is *"completable by a representative engineer unaided within a
declared time budget"*. Measuring that properly needs an engineer who has not
seen the system, a facilitator to observe, and a repeat every release — an
expensive instrument, and expensive instruments get run once and then quoted for
two years. It is the right **acceptance criterion** and the wrong **gate**.

**The answer: gate structurally, measure the clock separately.** Each of the
five has an objective, mechanically checkable shape, and the shape is what
actually decides whether the task takes ten minutes or a day:

| Change | The structural gate |
|---|---|
| Switch a module's mode | One field in the run spec. No other file touched |
| Change a calibration value | One key in one config bundle. No rebuild, no code edit |
| Add a recording | One entry in the recording list. No code edit — the ingest map is edited for a new *family*, never for a new file |
| Change the layout | One workspace file. No framework file touched |
| Add an export | One exporter entry. No engine file touched |

Each is now a planted-violation test of the kind the requirements already demand
generally: make the change, assert the diff touches exactly the declared file
set. That is **failable today**, costs no facilitator, and catches the actual
regression this requirement exists to prevent — *a change that used to be one
file starting to need three.* The health metric that already existed — lines of
configuration per project, tracked across releases — stays, because it needs no
stakeholder, no stopwatch and no representative engineer.

**The wall clock is not gone; it is demoted to an observation.** The five tasks
are run once, the times recorded as **observations rather than targets**, and
put in front of the customer team then. A number to react to gets an answer
where an open question gets silence.

---

### 6.7 `OQ-17` — does this tool need functional-safety qualification?

**The answer is yes.** Outputs of this tool will be cited as evidence in a
safety argument; a functional-safety concept for the tool will be asked for; and
how rigid the tool is will have to be **proven**, not asserted.

**This was the highest-variance row in the register** — the only one that could
invalidate the **form** of every other answer, reaching the requirement style,
the verification evidence and the shape of the whole document set. So the size
of what it actually cost is the headline:

> **Three concept statements, three system requirements, three software
> requirements and three design rows. No re-styling of anything.**

**Why the blast radius was that small.** The set was already in the shape a
qualification argument asks for — numbered `shall` statements, a falsifiable
`Accept` per requirement, a `Verify` naming a test that exists, a `Trace` link
upward, derived rather than stored status, and a planted-violation twin for
every negative check. **It was built that way because a requirement nobody can
fail is worthless, not in anticipation of an auditor — which is exactly what
makes it usable as evidence.** The genuinely expensive parts of qualification —
classifying the tool, producing the validation evidence for that
classification, and writing the tool safety manual — are process work
**downstream** of these documents.

**What was added, and why exactly these three.** Every tool-confidence scheme
asks the same two questions before it asks anything else: *how bad is it if this
tool is wrong* (impact) and *would we notice* (detection). So:

| Layer | What was added |
|---|---|
| **Concept §2.4** | `CN-0400` a confidence claim must be **evidenced, not asserted**, and the evidence is a by-product of the ordinary build · `CN-0401` the tool states **what it may be relied on for and what it may not**, shipped with the release · `CN-0402` for every citable output, **the check that would catch a wrong value is named**, or its absence is declared |
| **System §23a** | `SYS-0289` every artifact kind declares whether it may be cited · `SYS-0290` use constraints and known limits ship with the release · `SYS-0291` every cited kind names what would catch a wrong value, or the literal `undetected` |
| **Software §29.1** | `SW-0415`…`SW-0417` — the declaration is data and every writer is checked against it; the constraints statement is **generated, never typed**; a named detecting check must resolve to a test that exists |
| **Design** | `IMP-0415`…`IMP-0417` — `conf/artifact_kinds.yaml` + a writer check at `WP-01`; `USE_CONSTRAINTS.md` generated at `WP-31`; the detection table resolved by the **same** resolver the `Verify` links already use |

**No standard and no confidence level is named**, deliberately. The
classification is quality's to make, and a concept that pre-empted it would be
rewritten rather than used. `CN-0401` is the input to the impact question and
`CN-0402` to the detection question, so whichever scheme is eventually named,
the two things it asks for first already exist.

**Two of the four obligations were already discharged, and are deliberately not
restated.** Any scheme also asks that a cited result identify the tool version,
configuration and binaries that produced it. `SYS-0123` already fixes the run
manifest's contents *"each either a value or an explicit unknown"*, and
`SYS-0114` already requires every artifact to embed it so that *"any artifact,
taken alone to another machine, identifies the run that produced it."* Writing a
fifth requirement saying that in qualification vocabulary would be the second
copy this document set exists to prevent — **and the copy that drifts is always
the one written for a review rather than for a build.** The natural reflex on
receiving a qualification obligation is one requirement per clause of the
obligation; half the clauses were already met before the question was asked.

**The one discipline that must not lapse** while the classification is pending:
keep `Trace` fields complete as requirements are written. Reconstructing
traceability after thirty-two work packages are cut is the only part of this
that would genuinely hurt. Everything else is additive.

---

### 6.8 `OQ-15` — which CI system?

**Undecided. Jenkins is likely, not committed.** And it does not matter yet,
which is the point of how this was arranged.

**Why it looked like it blocked everything.** There is **no CI configuration of
any kind** in the repository. Meanwhile the *first* work package in the plan is
CI and the check harness, on the stated reasoning that *manual verification is
the mechanism that fails first* — checks that depend on somebody remembering to
run them stop being run, quietly, at exactly the moment the project gets busy.
Read together those two facts look like the plan is stuck at package one.

**The split that unblocks it.**

| Half | Depends on the vendor? | Precedent already in the tree |
|---|---|---|
| **The harness** — every check runnable as one plain command, returning an exit code and printing how many things it scanned | **No** | `docs/py/run_all.py`, already required before any docs commit; `scripts/check_invariants.py` for the grep-based invariants |
| **The trigger** — the vendor file that runs that command on push | Yes | — |

All the work and all the value are in the harness; the trigger is roughly ten
lines, written the day the vendor is known. `WP-01` is therefore completable
except for one small file — and the property that matters more than the
schedule: **every check stays runnable on a developer machine**, which is what
keeps checks being run at all. That is now a clause in `SYS-0201`'s and
`SW-0376`'s `Accept`, not just an intention, because a check that only ever runs
in a pipeline stops being runnable the moment the pipeline moves.

**One detail inside the harness, because it is the failure it prevents.** A
check that scans a path that has been renamed, or a tree that does not exist
yet, **passes** — silently, forever, catching nothing. So every check reports
its scan count, and a check that scanned nothing reads `SKIPPED` rather than
`PASSED`. That is why the harness half is not trivial work despite being
vendor-independent.

**Two constraints travel to whichever system is chosen**, both already implied
by decisions taken: it must run **Windows and Ubuntu**, and the harness lives in
the contributed-tooling directory rather than in the shipped source tree.

---

### 6.9 `OQ-19` — are campaign results kept, or regenerated?

**The answer: the customer keeps them.** Campaign results are written in the
result format named in the run configuration and retained on storage the
customer owns. Retention durations are therefore not this system's to set, and
no requirement here states one.

**What the tool owes instead, and why that is the right division.** A retained
result must be **self-describing** — which `SYS-0114` and `SYS-0123` already
require. That is what makes this answer safe rather than merely convenient: a
result kept for years, on storage the tool never sees, still identifies the run,
the binaries and the configuration that produced it. Had the identity chain not
already existed, "the customer keeps them" would have meant "the customer keeps
files nobody can later interpret".

**The one constraint no policy can wish away, recorded where the owner will read
it.** Because resim is deterministic *by design* and that determinism is
**measured** rather than asserted, a campaign result is regenerable **if and
only if its inputs still exist** — recording, resolved spec, config bundle and
the exact library binary. Inputs are kilobytes; results are large. So keeping
inputs and regenerating results is the cheap direction, and it is available only
because determinism was designed in from the start.

But **regeneration needs the binary, not merely its hash.** A component build
that can no longer be obtained makes its results unregenerable — and at that
moment the stored results become the only evidence the run ever happened. Any
retention policy therefore needs an explicit rule for *"the binary is gone"*:
either the outputs are promoted to long retention, or the baseline is knowingly
abandoned. Both are acceptable; leaving it unstated is not.

---

### 6.10 `OQ-18` — who maintains project configuration after handover?

**The answer: the algorithm test manager or the product owner** — a named role
in the customer organisation, not a team to be formed.

**No requirement changed, and that is the finding.** `SYS-0281` already splits
format and schema (supplier) from content (customer), which is exactly the split
the answer names. It fits because project configuration is **data in versioned
files with no code**: there is no central project roster (a project exists
because some module's build file declares it), calibration lives in per-project
directories, and the config bundle is a build *output* rather than a second
place anyone edits a value. So *"who maintains it"* was always a question about
repository access and review, never about capability — **nobody needs to be able
to program to own it.**

**What actually sizes the support model — worth saying to whoever staffs it.**
The **diagnostics**. `sim explain`, `sim doctor`, and an authoring error that
names the plug-in, the port it asked for, and every port the manifest actually
declares. Those are what let a customer team answer its own questions instead of
raising a ticket. **A thin support model is viable in proportion to how good
those messages are** — which turns a headcount argument into an engineering
target, and is the reason the diagnostics rules are normative rather than
nice-to-have.

---

### 6.11 What the answers unlocked

| Answer | Unlocked |
|---|---|
| `IFQ-01` ratified | The header work package can encode. The µs↔ns conversion stays where it was already written, and its truncation risk has a named trigger |
| `OQ-09` sample obtainable | `MP-1`'s exit stops being permanently provisional; `R-8` retires at `WP-18` |
| `OQ-22` agreed | Off the baselining gates, onto the format work packages. Start the vendor-SDK conversation now |
| `OQ-14` supplied | Three performance requirements became failable; `R-4` retired |
| `OQ-16` agreed | The project's own success measure is checkable in CI today |
| `OQ-17` answered **yes** | A scoped obligation with first-level goals at all four layers, instead of an open-ended risk. The fallback was never needed |
| `OQ-15` + `OQ-19` | `WP-01` proceeds on the harness; retention is the customer's, and their results are self-describing |
| `OQ-18` chosen | A named role, and no code changes either way |

**And the state, honestly.** Nothing in the implementation plan is blocked by a
design decision, and nothing is blocked by an unanswered question. What remains
is one file somebody has offered to send and one vendor choice worth ten lines.
