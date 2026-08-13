# SIM v2 — Open Questions Register

**One place to answer everything.** Assembled 2026-08-11, last updated
2026-08-12. This document holds no questions of its own — it is a **view** over
the authored documents, so that answering is one pass instead of four. Each row
says where the question lives, what it blocks, and what happens if it is left
alone. **The source documents remain authoritative**; when a row is answered,
the answer is written back into the owning document and the row moves to §4.

| Marker | Meaning |
|---|---|
| `DEFAULT` | A default is stated and argued. Silence adopts it; that is safe but should be deliberate |
| `BLOCKS` | Something cannot be finished — usually a threshold that cannot be set, so a requirement cannot be failed |
| `EXTERNAL` | Not answerable inside this repository. Needs a recording owner, a module team, quality, or DevOps |

**Where it stands after the 2026-08-12 pass:** all fourteen design decisions
confirmed; **fourteen `SWQ` closed** (eight from the decomposition, six from
reading the decomposition against itself); **fourteen `OQ` closed** — five
earlier (`OQ-03`, `OQ-08`, `OQ-13`, `OQ-20`, `OQ-21`) and **nine in the answers
pass** (`OQ-01`, `OQ-02`, `OQ-04`, `OQ-05`, `OQ-06`, `OQ-07`, `OQ-10`, `OQ-11`,
`OQ-12`, §4.7); **four of six `SignalHeader` questions closed**, one reframed,
one open and now carrying counter-evidence as well as its default.
**Nothing in the implementation plan is blocked by a design decision** — what
remains open is either external (§2, §3) or narrow (§1).

**Eight `OQ` remain**, and the answers pass reduced them to **five asks** —
one sentence each except the sample file and the measured budgets. The working
document is `SIM_Open_Question_Answers_v0.1.md`; it drains as rows are written
back here, so a row present in both is a row not yet landed. The recurring
finding, worth carrying: **most of what was open had already been answered by
an artifact nobody had re-read** — the C ABI header closed three module-team
questions without anyone being asked, and two acceptance criteria closed two
more.

> **If you are here to give an opinion rather than to look up a row, read
> §6 — the plain-language briefing.** It explains the nine still-open items
> (eight `OQ` plus `IFQ-01`) from the beginning: what is being asked, how the
> question arose, what each answer causes downstream, what silence adopts, and
> the one thing each row actually needs from you. §1–§3 are the index; §6 is
> the reading copy. The two never disagree — §6 adds background, never a
> different answer.

---

## 1. Open and answerable here

### 1.1 `SignalHeader` — one left

From `docs/interfaces_signal_header_plan.md`, the contract-side input to
`DD-11`'s `WP-07`. `IFQ-02` and `IFQ-06` closed on 2026-08-12 and are recorded
in §4.5. The one that remains carries a default, so silence is safe — but it is
the default whose argument has weakened, so silence should be deliberate.

| ID | Question | Where it stands |
|---|---|---|
| `IFQ-01` | **Microseconds or nanoseconds?** The width is settled (`uint64`); only the unit is open. Today's `uint32 time_stamp` read as ns wraps in 4.3 s | **`timestamp_us` stands as the default; `timestamp_ns` is recommended and needs ratification** (`SIM_Open_Question_Answers_v0.1.md` §1.1). The **unit-agreement** argument for µs is weaker than it read: the two units *already* coexist in a shipped contract — `ComponentManifest.period_ns`, consumed at `modules/df/src/platform/cm/src/host/cm_host.cpp:105`, sits beside `period_us` in the same `conf/ports.yaml` — so one-unit-per-contract is a state that would have to be **created**, not one being protected. Against it: `SW-0044` calls validity time an integer-**nanosecond** quantity *belonging to this header*; `PERIOD_US` is **authored** calibration whose fractional values must be refusable (`SW-0046`) while a stamp is **measured**, and unit agreement is worth having within a kind of value rather than across kinds; and — decisively — **µs depends on the missing value file and ns does not**, since nanoseconds represent everything microseconds can. Ratifying ns also *deletes* the ×1000 carve-out in `SW-0033` rather than documenting it. Cost of being wrong: µs truncates a shipped wire contract, ns costs ≈1 varint byte per message. **One thing is settled either way and has already landed:** the field is renamed so it says which clock it is (`SW-0044`) |

**`IFQ-05` is reframed rather than open** — see that plan's §8.1. The question
was whether the schema check should read every component's `conf/ports.yaml`
(common, nothing drifts) or interfaces should keep its own list (standalone, but
a second copy). The recommendation is a third shape that takes both wins: the
check reads **whichever `ports.yaml` files are present** — none in a bare
interfaces clone, all in CI — so there is no second list and interfaces never
*requires* a sibling. One thing to confirm: the standalone case must **report
what it saw**, because a check that silently passes on zero inputs dies quietly.
That is now a general rule rather than one question's answer: `WP-01`'s exit
requires every check to report its scan count and to read `SKIPPED` rather than
`PASSED` when it scanned nothing.

---

## 2. Inherited from the System Requirements — the baselining gates

`SIM_System_Requirements_v0.1.md` §26 lists twenty-two. **Three** remain that
are **gates rather than rows**: that document is not baselined until each has
an answer or a written fallback. (`OQ-01` and `OQ-11` were two of the five and
closed on 2026-08-12 — §4.7. Of the three left, two are `BLOCKS` only for a
*number*, and §5 of the answers document proposes a baseline-plus-bound that
makes both requirements failable without one.)

| ID | Question | Why it matters | Owner |
|---|---|---|---|
| `OQ-14` | The **numbers** for per-cycle cost, campaign throughput and player frame time, and the configurations they are measured on | `BLOCKS` — `SW-0272`, `SW-0323`, `SW-0369` cannot be *failed* without them. The harnesses are built either way | SIM team |
| `OQ-16` | The stated set of **common configuration changes** and each one's time budget | `BLOCKS` — `SW-0348`, the requirement closest to the project's own success measure | SIM team + a customer team |
| `OQ-17` | Are there **tool qualification or functional-safety** process constraints? | Potentially the requirement style, the verification evidence and the whole document set. **Now carries a written fallback** (SYS §26): unanswered by the time the seam is built, the chain is developed in the present style and re-styling is accepted as a known, scoped cost. An unanswered question with a fallback is a managed risk; one without is a surprise arriving after 32 packages are cut | Quality / safety |

## 3. Inherited — the five that remain

Carried as documented assumptions. Grouped by who can answer. Seven of the original twelve closed on 2026-08-12 (§4.7), which emptied two of the four groups outright.

**A recording owner**

| ID | Question | Blocks |
|---|---|---|
| `OQ-09` | What exactly does the **bench capture** write, and **does it preserve the signal header end to end**? | **Much less than it did.** `IFQ-06` no longer depends on it (the header carries two stamps regardless of what a reader receives) and neither does `OQ-01` (the supported rung is a measured per-recording field). `SYS-0015`/`SYS-0029`/`SYS-0061` are satisfiable without it — they are about *our* shape, and what the bench writes decides which rung its files land on, which is the ladder working rather than the ladder blocked. **What is left is verification evidence, not design input:** `MP-1`'s exit is provisional against a crafted fixture until a real sample exists (`WP-18`), so ten seconds of real bench capture retires plan risk `R-8` outright. The minimum ask is four items, listed in the answers document §3.2 |
| `OQ-22` | Licence and distribution situation for **proprietary format readers** | `SYS-0011` — now concrete: MDF4 and TDMS are the two |

**Module teams** — *none left. All three closed on 2026-08-12 (§4.7): the ABI
answered them, so nobody was asked.*

**Algorithm teams** — *none left. All four closed on 2026-08-12 (§4.7): each
already had a written answer that said "no, and here is what to do instead",
and nobody had re-read it.*

**SIM team / process**

| ID | Question | Blocks |
|---|---|---|
| `OQ-15` | Which **CI system**, and what artifact retention? | `SYS-0201`, `SYS-0184` |
| `OQ-18` | Who **maintains project configuration** after handover, and what is the support model? | `SYS-0281` |
| `OQ-19` | **Campaign retention** policy — baseline, regenerable, or deleted | `SYS-0117`, `SYS-0184` |

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

### 4.3 Five `OQ` closed

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

### 4.5 `SignalHeader` — four of six

| ID | Answer |
|---|---|
| `IFQ-06` | **Two fields, not one** (2026-08-12, *reversing* the previous day's "one field now" — and removing its stated dependency on `OQ-09`). `source_timestamp_*` is always filled; `capture_timestamp_*` is proto3 `optional` and unset when unknown. The decision rests on **what a producer can know**, not on what a reader receives, which is why the bench capture no longer decides it. `SW-0044` requires validity time *in this header* as an explicit unknown, which one field cannot satisfy; ladder rung 3 and `age_s` are two `R1` consumers wanting two different stamps; and `time_stamp` was exactly the ambiguous name `SW-0044` forbids. Most producers leave capture unset in `R1` — a declared state, with `SW-0045`'s hold-schedule fallback already written. Argued in `SIM_Open_Question_Answers_v0.1.md` §1.1 |
| `IFQ-02` | **Required; a violation is reported and demotes the port to rung 4; never clamped** — clamping turns a producer's timing bug into a plausible-looking zero. `SW-0050`'s acceptance already carried this; closing it added three refinements, each preventing a check that would be wrong unnoticeably: **non-decreasing, not strictly increasing** (two messages legitimately share a stamp); **per port, never across ports** (two producers share no clock discipline); and **it binds source time** — an out-of-order capture time is reported but does not demote, since it yields a negative `age_s` that must surface rather than be clamped. §1.2 there |
| `IFQ-03` | **Wrap at `uint32`.** The bus handles wrap explicitly, so rung 2 never reads a wrap as a gap |
| `IFQ-04` | **The three legacy messages are dummy**, so they are left untouched — no field added, `adas.common.Header` not deprecated. This *reverses* the plan's draft ("add it while the field is free"): wire compatibility protects encoded bytes that exist, and for a message nobody produces there are none. `R-IFACE-4` is scoped by *"can be a port payload"*, so the schema check demands a header the day one gains a real producer — the obligation is enforced when it becomes real, with no list to remember |

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
by shared mechanism rather than by owner and argues each to a verdict. The
recurring finding is worth stating once: **most of these were already answered
by an artifact nobody had re-read.**

| ID | Answer |
|---|---|
| `OQ-07` | **The system passes a *path*, never a *value*.** `adasInit` takes `configPath`; `SYS-0177`/`R-SIM-3a` settle the rest. Injection is forbidden by name — the bundle is *"a build output, never a second place to edit a value"* — and `SYS-0177`'s own acceptance (*the viewer reads the same bundle the module was initialised with, and states which one*) is unsatisfiable if a value can arrive from elsewhere, since there would be two answers to *"what wheelbase did this run use?"*, free to disagree. **A sweep is a bundle variant**: copy, patch one key, re-hash, record the hash — which meets `SYS-0072`'s acceptance verbatim, because a variant is neither a rebuild nor a host edit. Implies one small helper beside the run spec, a file rather than a mechanism. §4.1 there |
| `OQ-04` | **Yes — and the question understates what exists.** Addressability is four levels deep, not two: per module (`SYS-0080`), per port (`SYS-0082`), **per field path** (`egoDyn.vx`) and **per repeated element** (`[i]`, `[*]`) — the last two from `R-SIM-15`. Nobody has yet needed the two finer levels already present. The one missing axis — time-varying or conditional overrides — is missing **on purpose**, because *an override may destroy or attenuate information, never create an entity*, with two written alternatives (edit the scenario; a `stub:` stage). **This was the row most likely to enlarge the build if answered afresh**: asking teams *"is it sufficient?"* invites *"it would be nice if…"*, and each nice-to-have is a predicate in a list that is closed for a written reason. Reopen only on a concrete case, with a recording, that neither alternative serves. §4.2 there |
| `OQ-02` | **No — already deferred, on two grounds, only one of which was tied to `OQ-01`.** `SYS-0108` is `P2 · DEF` and off by default. The revisit trigger is **restated**, since `OQ-01` closed into a measurement rather than a yes/no: ego re-integration may be considered for a recording whose ports report **rung 3 or better**, and only once the divergence machinery is trusted. The timing dependency was never arbitrary — integrating over per-cycle `dt` is only as sound as the rung — and on a rung-4 recording the integration would run on *reception* time, so it would not be merely approximate but measuring the wrong thing. `SYS-0105`–`SYS-0107` is the untouched second ground, so `R1` is unaffected either way. Recorded alongside: this is dead-reckoning, which `R-SIM-7` bans in a layer provider; in the engine it is on the right side of that line **only while the approximation label holds**. §4.3 there |
| `OQ-11` | **Derive it — neither adopt nor define.** The catalogue `SW-0388` requires is the union of the `ModuleManifest`s present in the run, computed at load. *Defining* one creates a second description of a port set we own, free to drift, which `R-SIM-16` forbids in those words; *adopting* an external one as the **resolution authority** has the same defect and lets an outside document decide whether a port our compiler emitted is legal. Deriving has neither defect, because the manifest is generated from `conf/ports.yaml` (`R-SIM-22`) gated by `ENABLED_FUNCTIONS` (`R-VAR-5`) and is therefore *by construction* a description of what compiled — and every one of `SW-0388`'s clauses is already met by machinery that exists (`SW-0411`'s probe pass, `R-SIM-21`'s `AuthoringError`, the run manifest's identity triples). **If an organisation catalogue exists, adopt its vocabulary and never its authority**, so a late answer costs a rename rather than a redesign. Design `A-4` restated accordingly. §3.1 there |
| `OQ-10` | **`R1` is already fixed by `SYS-0111` + `DD-13`: MCAP** (interchange *and* replayable — one codec for both, which is why `SYS-0112`'s chaining is free) **and CSV/TSV** as the columnar text export, registered **write-only** because it cannot round-trip. Not a guess about preference: the smallest set satisfying three requirements. A team's preference **cannot block**, because a format is ~4 methods behind a registered interface (`R-SIM-14`) and no exporter is mandatory (`SYS-0110`) — so "we live in MDF4" adds a codec row, not a design change. This is `OQ-08`'s signal again: naming formats changes the plan's shape not at all, which is how you know the seam is right. **Re-ask it at the first export review as a scheduling input, not as a gate** — an export nobody opens is dead weight. §3.2 there |
| `OQ-05` | **A measurement, not a survey — and the criterion is not "functional".** `R-SIM-16` already makes a component onboard itself by manifest and `SYS-0050` forbids compile-time linkage, so what `E2E-02`/`E2E-03`/`E2E-10`/`IT-22` can be planned against is the output of `sim probe <lib>`, dated, rather than a document that goes stale. **Measured 2026-08-12: three** modules carry `conf/ports.yaml` and a SIL C interface — `df` (9 215 `src/` C++ lines, two real functions), `perception-core` (517, three detector/tracker units) and `vdy` (409) — **correcting this register's earlier "df and vdy are the two"**. `sil_host` is functional but is the host, not a module under test; `mathlib` is a library with no ports, correctly; `interfaces` and `shared_config` have no library by design; and `isp`, `perception-lane`, `planning`, `platform-services` have **zero C++ source**, so "structural" is measured rather than assumed. `perception-core` is the most useful `IT-22` candidate: it sits upstream of `df` on a real data path. §2.1 there |
| `OQ-06` | **No module supports it, none can, and nothing depends on it.** The ABI has five exports and no reset entry point, so this was never a module-team question. `adasShutdown` + `adasInit` is an **exact** reset for all handle-scoped state and needs zero module changes; its only cost is a config-bundle re-parse. The one hazard it does not cover — a surviving process-level `static` — is detected by `SYS-0192`'s *own* acceptance criterion (a shuffled batch differs), and `DD-09`'s one-subprocess-per-recording guarantees exactness where it must be guaranteed rather than tested. An optional `adasReset` export is the named optimisation **if a measurement ever justifies one**; it is not proposed now, because adding an export against an unmeasured cost is how a five-symbol ABI becomes a seven-symbol one. §2.2 there |
| `OQ-12` | **No — unrepresentable over this ABI.** The period is read from the config bundle at manifest-build time and reported through `adasManifest`, which is callable before `adasInit` and returns a snapshot; `adasExec` takes `dtS` and no rate argument. No export exists by which a module could announce a new period mid-run, so `SYS-0066`'s grid can be computed once at load and cannot go stale. The residue — a module that *behaves* at a rate other than the one it declares — is already `SYS-0071`, and that is a **stronger** guarantee than a survey answer, because it also holds for modules that would have answered wrongly. §2.3 there |
| `OQ-01` | **It stopped being a question.** *"Do the recordings in scope carry task/cycle marking?"* is not answered globally for a corpus nobody has enumerated — `SW-0410`'s `RecordingIndex` already reports, per topic, *"the highest timing rung the data supports"*, computed by `SI-13`'s probe pass before every run and printed by `sim probe`. So the register's owned/foreign split dissolves: one field, measured on our files and foreign ones alike. A capture format nobody has seen yields an unknown **value**, never an unanswered question, and rung 1 being inert becomes observable rather than assumed. The `SignalHeader` half is confirmed and dated — once §1.1 lands every platform-produced payload reports rung 2 by construction, and the measurement will *show* it rather than it having to be believed. §1.3 there |

## 5. Assumptions this register does not turn into questions

`SIM_Implementation_Design_v0.1.md` §31 lists seven (`A-1`…`A-7`). They are
*stated* assumptions, not open items — each is a position taken deliberately
with its consequence named. They are listed here only so that "not in the open
questions register" is not read as "nobody thought about it". `A-4` in
particular is `OQ-11` wearing different clothes: if `OQ-11` closes the other
way, `A-4` is what has to change.

---

## 6. Plain-language briefing — the nine that are still open

**Why this section exists.** The rows above are written for someone who already
knows the design; they compress the argument into one cell. This section
un-compresses it. Each of the nine open items is told from the start: what is
being asked, why the question came up at all, what happens downstream if it goes
one way or the other, what is *already* decided so that the damage is bounded,
what happens if nobody answers, and the one thing the row actually needs from
you. No new decisions are taken here — where §1–§3 and §6 both speak, they say
the same thing.

**How to use it.** Read the item, then say your opinion in one line. Where a row
already has a recommendation, *"agreed"* is a complete answer; a *"no, because…"*
is more valuable than a long alternative, because the reason is what gets written
into the requirement.

### 6.0 Six words you need first

The nine rows keep reaching for the same six ideas. They are explained once here
so the rows themselves stay short.

| Word | What it means, plainly |
|---|---|
| **Port** | One named input or output of a software module — `df.bsd.outputs`. The tool never addresses data by position, only by name, because a name survives a code change and a position does not. |
| **Recording** | A file of timestamped messages. Ours, another team's, a bench tool's, a foreign simulator's — the tool treats all of them as the same shape. |
| **Resim** | Re-running the *real* algorithm library against a recording. Not a replay: a replay just draws what was already computed, a resim actually executes the code again and can therefore disagree with the file. This is the thing that goes in CI. |
| **Cycle recovery ladder** | The hard part of reading somebody else's recording is not parsing bytes — it is working out **which messages belong to the same computation step**. Our own files say so outright. A foreign file may not, so there is a declared ordered ladder of four fallbacks: (1) a cycle id the source itself wrote, (2) the cycle counter in our signal header, (3) source time, (4) reception time from the file envelope. **Rung 4 is the bad one** — it groups messages by when a logger happened to receive them, which is approximately right and quietly wrong at the edges. Which rung a file supports is *measured per file*, not assumed. |
| **Codec** | A reader/writer for one file format, about four methods, sitting behind one registered interface. This is why "which formats?" is a cheap question: naming a format adds a table row, not a design. |
| **Work package (`WP-nn`) / milestone (`MP-n`)** | The unit of build work in the implementation plan, and the phase it belongs to. `MP-1` — *"fix the clock"* — is the phase whose entire purpose is making foreign recordings reconstruct into correct cycles. |

### 6.1 The nine at a glance

| # | Row | In one sentence | Who can actually answer | What silence costs |
|---|---|---|---|---|
| 1 | `IFQ-01` | Do message timestamps count microseconds or nanoseconds? | You (contract owner) | Keeps `µs` — the option whose main argument no longer holds |
| 2 | `OQ-09` | Can somebody send ten seconds of real bench capture? | A recording owner | One milestone stays *provisionally* finished, forever |
| 3 | `OQ-22` | Are the licences of third-party format readers acceptable to ship? | Legal / commercial | Nothing now; it becomes urgent the week a real file arrives |
| 4 | `OQ-14` | What are the performance numbers, measured on what? | You + whoever owns throughput | Three performance requirements that cannot be failed |
| 5 | `OQ-16` | How long may a common configuration change take? | You + a customer team | The project's own success measure stays unmeasurable |
| 6 | `OQ-17` | Does this tool need functional-safety qualification? | Quality / safety | A fallback is already written; risk is managed, not zero |
| 7 | `OQ-15` | Which CI system, and how long are artifacts kept? | DevOps | ~10 lines of the first work package wait; nothing else |
| 8 | `OQ-19` | Are campaign results kept, or regenerated on demand? | Storage / audit owner | Answer it with row 7 — one policy, two consumers |
| 9 | `OQ-18` | Who maintains project configuration after handover? | Organisation | Nothing technical; it is a staffing shape |

Rows 1, 4, 5 are the ones **you** can move today. Rows 2, 3, 6, 7, 8, 9 need
somebody outside this repository, and every one of them has already been
de-blocked so that the wait costs nothing.

---

### 6.2 `IFQ-01` — do timestamps count microseconds or nanoseconds?

**What is being asked.** One word. Every message that crosses a component
boundary carries a small header saying who produced it and when. The question is
the *unit* of that "when": millionths of a second, or billionths.

**How we got here.** The header that exists today has a field called
`time_stamp`, 32 bits wide. Two defects in it were found and are already fixed:

- **32 bits of nanoseconds wraps to zero every 4.29 seconds.** Widened to 64 bits.
  Not controversial, already settled.
- **The name did not say which clock it was.** There are genuinely *two* clocks
  in play. **Source time** is *"when the producer computed this"* — always
  knowable, because the producer is the one filling the field. **Capture time**
  is *"the instant the data actually describes"* — when the camera shutter
  opened, when the radar swept. A producer often does not know that, and when it
  does not, the field must read *unknown* rather than being quietly filled with
  something plausible. That is also already settled: two separate, differently
  named fields, capture optional.

So the width is fixed, the naming is fixed, the two-clock question is fixed.
**Only the unit remains**, and it remains because it is the one piece that has to
be right before anything is encoded.

**Why one word gets this much attention.** This is a wire contract. Every
component fills it, every consumer reads it, every recording stores it, the age
of a held value is computed from it, and rung 3 of the cycle ladder is literally
this field. Changing the unit after recordings exist means either re-encoding
every stored file or carrying a version flag forever. It costs one word now and
a migration later.

**The original argument for microseconds, and why it weakened.** We decided
elsewhere that a module's sample period is written in configuration as integer
microseconds (`<COMPONENT>_<FN>_PERIOD_US`), because a YAML floating-point number
rounds badly and a rounded period accumulates into drift that reads like an
algorithm bug. From there, *"keep one unit across the contract"* sounded obviously
right. Reading it against the repository weakens it in three places:

1. **The two units already coexist, in shipped code.** `period_ns` is a live
   manifest field consumed by real host code, and it sits in the same
   `conf/ports.yaml` as `period_us`. So *"one contract, one unit"* is not a
   property being protected — it is a property that would have to be **created**,
   and creating it would mean changing the manifest field too.
2. **A configured value and a measured value are different kinds of thing.**
   Microseconds are mandated for the period because a *person types it* and a
   fractional entry must be refusable. Nobody types a timestamp. Unit agreement
   is worth having *within* a kind of value, not across kinds.
3. **The requirement that owns the header already calls its stamp a nanosecond
   quantity** (`SW-0044`). A microsecond wire field is defensible only by
   re-reading that as *"after ingest"*.

**The decisive argument, which is about risk rather than taste.** Nanoseconds can
represent everything microseconds can. So:

- If a data source turns out to have finer than 1 µs resolution, **microseconds
  truncate** — silent data loss inside a shipped contract.
- If nanoseconds are the "wrong" choice, the cost is roughly **one extra byte per
  message**.
- And microseconds' correctness *depends on a file we have not received yet*
  (`OQ-09`, the bench sample, which is one of the two things that would tell us
  the finest resolution in play). Nanoseconds do not depend on it at all.

Under an unresolved external input, the choice that makes the input irrelevant is
the cheaper one to be wrong about.

**A small bonus, worth naming because it removes a rule rather than adding one.**
If nanoseconds are ratified, `SW-0033`'s carve-out — *"the engine performs exactly
one unit conversion"*, the ×1000 — is **deleted**, and `ANL-SW-02`'s ban on unit
arithmetic needs no exception. Microseconds require both to be written down and
maintained.

**What silence does.** Keeps `timestamp_us`. That is precisely why this is being
asked out loud instead of assumed: the standing default was argued in good faith
one day earlier, and reversing an argued cross-component decision should be a nod
somebody gives, not something a document takes.

**Recommendation.** `source_timestamp_ns` / `capture_timestamp_ns`.

**What is needed from you.** One word: *ratify ns*, or *keep µs*.

---

### 6.3 `OQ-09` — ten seconds of real bench capture

**What is being asked.** Not a specification, not a format document. One real
file, its channel list, and one sentence.

**How we got here.** The tool must read recordings it did not produce — three
formats are in scope: our own interchange format, a vehicle measurement format,
and a bench capture format. Parsing bytes is the easy half. The hard half is the
cycle ladder (§6.0): grouping messages into the computation step they belong to.
Our own files answer that directly. A foreign file may only support rung 4 —
grouping by when the logger received things — which produces a picture that looks
right and is wrong in exactly the places that matter.

**The chain of effect.** `MP-1` is the milestone whose whole purpose is making
foreign recordings reconstruct correctly. Its exit criterion is currently tested
against a fixture **we wrote ourselves**. The implementation plan states the
problem in blunt terms as risk `R-8`: *a fixture the team wrote encodes the same
assumptions the recovery ladder does, so it validates the guess rather than the
data.* That is a real hazard — it is the kind of thing that passes every test
for six months and then fails on the first customer file. Ten seconds of real
capture retires it outright.

**What has already been removed from this question, so nobody over-weights it.**
`OQ-09` used to block two other decisions, and it now blocks neither:

- **The header decision** no longer depends on it, because that decision rests on
  what a *producer can know*, not on what a *reader receives*. What the bench
  writes cannot change what a producer knows.
- **The "do recordings carry cycle marking?" question** no longer depends on it,
  because that stopped being a global yes/no. Every recording is probed before
  every run and reports, per topic, the highest rung its data supports. A capture
  format nobody has seen yields an unknown **value**, not an unanswered question.

So what is left is **verification evidence, not design input**. No work package
is blocked; the design does not move either way.

**The ask, kept deliberately small so it is easy to say yes to.**

1. One file, **ten seconds**, from any routine bench run — no special
   configuration, no scenario, nothing staged.
2. The **channel/topic list** as the tool exports it.
3. **One sentence**: does the capture chain re-stamp messages as it records them,
   or pass the producer's own stamp through?

**What we would do with it on arrival.** Check whether a per-message reception
stamp exists (decides whether rung 4 is even available for that format, and
therefore whether the codec has to declare a degraded capability); whether our
signal header survives end to end (decides rungs 2 and 3); and the finest
timestamp resolution present (one of the two inputs to `IFQ-01`, §6.2).

**What silence costs.** `MP-1`'s exit stays *provisional* and `R-8` stays on the
risk list — permanently, if the file never arrives. Nothing stops, nothing is
blocked, and no schedule moves. It is a quality-of-evidence cost, not a progress
cost.

**What is needed from you.** Either a name — someone who can drop one file — or
an explicit *"no such file will be available"*, in which case we record the
provisional exit as permanent and stop carrying the ask.

---

### 6.4 `OQ-22` — licences for the third-party format readers

**What is being asked.** Two of the three formats in scope are not ours. Reading
them means one of three things, and somebody has to say which is acceptable to
ship.

**Why it is much smaller than it sounds.** One decision already taken bounds it
completely: **exactly one codec implementation, in C++, behind a registered
interface of about four methods.** A reader therefore touches no engine code,
appears in no other component, and can be replaced without a single caller
changing. That is what makes this a **procurement** question rather than an
architectural one — and it is the same signal seen twice before in this register:
naming a format changed the plan's shape not at all, which is how you know the
seam was drawn in the right place.

**The three shapes.**

| Option | What it costs | What must be checked |
|---|---|---|
| An open-source C++ reader per format | Least code | The licence class against how the deliverable ships. **The case that bites is a copyleft reader statically linked into a delivered library.** Dynamic linkage is the usual mitigation and still needs a sign-off |
| A vendor or consortium SDK | Least risk of misreading the format | Redistribution terms, per-seat or per-deliverable cost, and platform coverage — the portability contract requires **both** Windows and Ubuntu |
| A clean-room reader from the published specification | No licence exposure at all, full control | The largest engineering cost, and only reasonable for the subset of the format actually present in our files |

**When it is due.** Per format, the week its first sample file arrives — because
each non-primary reader is written then, not before. This is the reason the
recommendation is to **move this row out of the baselining gates** and attach it
to the two format work packages: it is then asked by someone holding a real file
rather than in the abstract, which is the only way that question gets a precise
answer.

**The one thing worth starting early.** If a vendor SDK is even a candidate, open
the redistribution-terms conversation now. It is the only item in this entire
register whose latency is measured in **months** rather than days.

**What is needed from you.** Two things: agreement to attach this to the format
work packages rather than treat it as a gate; and whether any standing
organisational rule about licence classes and static linking already exists that
we should simply apply rather than re-ask.

---

### 6.5 `OQ-14` — the performance numbers

**What is being asked.** Three numbers — the cost of one simulation cycle, how
many recordings a batch campaign clears per hour, and how long the player takes
to draw one frame — plus the configuration each is measured on.

**Why an absent number is a real defect and not a formality.** The concept says
it directly: *a performance requirement with no threshold cannot be **failed***.
Two requirements are in exactly that state today. A requirement nobody can fail
is a requirement that will be declared satisfied, which is worse than not having
one, because it occupies the slot where a real check should be.

**The reframe that unblocks it — read the requirements' own words.** Both say
that a measurement exceeding its budget is *"reported as a regression rather than
silently re-baselined"*. A regression is a **comparison**. A comparison needs a
**previous measurement**, not an absolute target. So:

> Declare the reference configuration → take the first measurement → the
> requirement is failable from the **second** run onward, with nobody having
> guessed a number on the first.

**Do not build this mechanism twice.** The determinism rule already defines this
exact discipline for numerical tolerance: a file of rows, each carrying a
mandatory `why:`, its hash recorded in the run manifest, and — the part that
matters most — **a passing report prints the budget it used and the headroom
consumed**. That is described there as *the only anti-spiral mechanism that does
not depend on someone choosing to look*: it is what stops a budget being widened
by 10% each release until it means nothing. A performance budget is the same
artifact with a different unit.

**The half that actually causes the trouble is not the number.** It is the
**reference configuration**. Two measurements taken on different setups look like
a regression and burn a day of investigation every single time. The software half
can be pinned today, and should be:

| Axis | Pinned as |
|---|---|
| Which modules | `df` alone for per-cycle cost — it is the only module with substantial algorithm code; `perception-core` → `df` for the multi-module figure |
| Which recording | One named fixture, committed to the repository with its hash recorded — never referenced by a path that can change underneath |
| Tick count and layer count | Fixed and stated — this is the requirement's own wording, not an addition |
| Build configuration | Release-with-debug-info, matching the platform suffix already in use. Never a debug build, and never left implicit |

**The hardware half is genuinely coupled to `OQ-15`** and should be recorded as
such: a budget measured on a developer laptop will not survive the move to a
build runner. The mitigation is the same one the determinism rule uses — **record
the host beside each budget**, so that moving to CI hardware becomes a visible
re-baseline with a stated reason rather than a mystery regression.

**What stays with an owner regardless.** A baseline-derived budget answers
*"did we get slower?"* rigorously, from the second run. It does **not** answer
*"is it fast enough?"* — that is an absolute, and it belongs to whoever knows how
many recordings must clear overnight. That half does not block the harness; it
only blocks the claim.

**What is needed from you.** Two things: agreement that baseline-plus-bound is
the mechanism (which makes the requirements failable without inventing numbers);
and any absolute you already know — *"a campaign of N recordings must finish
overnight"* is exactly the shape that would be useful.

---

### 6.6 `OQ-16` — how long may a common configuration change take?

**A correction first: half of this was never open.** The register asked for *"the
set of common configuration changes **and** each one's budget"*, as if both were
missing. The set is already written into the requirement itself — **switch a
module's mode · change a calibration value · add a recording · change the layout ·
add an export.** Five items, named. Only the budget is missing, which halves the
question before anyone answers anything.

**Why this row matters more than its size suggests.** It is the closest thing the
project has to its own success measure. The whole point of the tool is that a
routine change is a routine change; if adding a recording takes a day, the tool
has failed regardless of how good its internals are.

**Why the remaining half resists being answered as written.** The requirement
says each change is *"completable by a representative engineer unaided within a
declared time budget"*. Measuring that properly needs an engineer who has not
seen the system, a facilitator to observe, and a repeat every release. That is an
expensive instrument, and expensive instruments get run once and then quoted for
two years. It is the right **acceptance criterion** and the wrong **gate**.

**The proposal: gate structurally, measure the clock separately.** Each of the
five has an objective, mechanically checkable shape — and the shape is what
actually decides whether the task takes ten minutes or a day:

| Change | The structural gate |
|---|---|
| Switch a module's mode | One field in the run spec. No other file touched |
| Change a calibration value | One key in one config bundle. No rebuild, no code edit |
| Add a recording | One entry in the recording list. No code edit — the ingest map is edited for a new *family* of recordings, never for a new file |
| Change the layout | One workspace file. No framework file touched |
| Add an export | One exporter entry. No engine file touched |

Each becomes a planted-violation test of the kind the requirements already demand
generally: make the change, assert the diff touches exactly the declared set of
files. That is **failable today**, costs no facilitator, and catches the actual
regression this requirement exists to prevent — *a change that used to be one file
starting to need three.*

**And keep the health metric that already exists:** lines of configuration per
project, tracked across releases. It needs no stakeholder, no stopwatch and no
representative engineer, and it moves in the right direction for the right
reasons.

**What is deliberately not concluded.** The wall-clock budgets themselves.
*"Within thirty minutes"* versus *"within a day"* is a statement about what a
customer's engineers are expected to absorb, and this document has no standing to
set it. **The recommendation is a sequence, not a number:** run the five tasks
once, record the times as **observations rather than targets**, and put those
observations in front of the customer team. A number to react to gets an answer
where an open question gets silence.

**What is needed from you.** Agreement that the structural gate is what CI
enforces, and that the wall-clock question is asked *after* we have measured
ourselves once — not before.

---

### 6.7 `OQ-17` — does this tool need functional-safety qualification?

**What is being asked.** Whether the tool falls under a tool-qualification
regime, i.e. whether its correctness has to be *argued and evidenced* rather than
merely tested.

**Why this is the highest-variance row in the register.** It is the only one that
can invalidate the **form** of every other answer. It can reach the requirement
style, the verification evidence, and the shape of the whole document set — so
answering it late is not like answering the others late.

**Why the blast radius is nonetheless smaller than it looks — and this is worth
knowing so the fallback is not over-provisioned.** The document set is *already*
in qualification-friendly shape: numbered `shall` statements, an `Accept`
criterion per requirement, a `Verify` method naming the test, a `Trace` link
upward, and a `Now.` line stating implementation status. That is most of the
structure a qualification argument asks for, and it was not built for that reason
— it was built because a requirement nobody can fail is worthless. The genuinely
expensive parts of qualification — classifying the tool (how bad is an error, how
likely are we to catch it, hence what confidence level is required), producing
the validation evidence for that classification, and writing a tool safety manual
— are **process work downstream of the documents**, not a rewrite of them. So the
fallback's cost is mostly **addition**, not **re-styling**, which makes it a much
safer risk to carry than the register's *"potentially everything"* suggests.

**The fallback already written.** If it is unanswered by the time the seam is
built, the chain is developed in the present style and re-styling is accepted as a
known, scoped cost recorded against this row. *An unanswered question with a
written fallback is a managed risk; one without is a surprise arriving after
thirty-two work packages are cut.*

**The actual recommendation: replace the question with a sharper one.** *"Are
there tool qualification constraints?"* invites a study, and a study takes a
quarter. The decisive input is a single sentence:

> **Does any output of this tool enter a safety argument — as verification
> evidence for a safety requirement, or as the basis for a claim about a
> production component's behaviour?**

If **no**, this row closes with no qualification obligation and the fallback is
never exercised. If **yes**, the classification work begins, and its scope is set
by *which* outputs — which is a much smaller investigation than the general
question. This is the cheapest question in the register to ask and potentially
the most expensive to leave unasked.

**One thing that should not wait for the answer, because it is cheap either way.**
Keep the `Trace.` fields complete as requirements are written. Reconstructing
traceability after thirty-two packages are cut is the one part of the fallback
that would genuinely hurt — everything else in it is additive.

**What is needed from you.** Whether you can answer that binary yourself, or
whether it needs a quality/safety function; and, as today's working position,
whether this tool's output is intended as a development aid only.

---

### 6.8 `OQ-15` — which CI system, and how long are artifacts kept?

**What is being asked.** Which continuous-integration system runs our checks on
every push, and how long its artifacts are retained.

**Why it looks like it blocks everything, and does not.** There is **no CI
configuration of any kind** in the repository today. Meanwhile the *first* work
package in the plan is CI and the check harness, on the stated reasoning that
*manual verification is the mechanism that fails first* — checks that depend on
somebody remembering to run them stop being run, quietly, at exactly the moment
the project gets busy. Read together, those two facts look like the plan is stuck
at package one.

**The split that unblocks it.**

| Half | Does it depend on the vendor? | Precedent already in the tree |
|---|---|---|
| **The harness** — every check runnable as one plain command, returning an exit code and printing how many things it scanned | **No** | `docs/py/run_all.py`, already required before any docs commit; `scripts/check_invariants.py` for the grep-based invariants |
| **The trigger** — the vendor file that runs that command on push | Yes | — |

All the work and all the value are in the harness; the trigger is roughly ten
lines and is written the day the vendor is known. So the first work package is
completable except for one small file. And the property that matters more than
the schedule: **every check stays runnable on a developer machine**, which is
what keeps checks being run at all.

**One detail inside the harness worth knowing about, because it is the failure it
prevents.** A check that scans a path that has been renamed, or a tree that does
not exist yet, **passes** — silently, forever, catching nothing. So every check
reports its scan count, and a check that scanned nothing reads `SKIPPED` rather
than `PASSED`. That is why the harness half is not trivial work despite being
vendor-independent.

**Two constraints to carry into whichever system is chosen**, both already implied
by decisions taken: it must run **Windows and Ubuntu** (the portability contract
is normative for every stage), and the harness lives in the contributed-tooling
directory rather than in the shipped source tree.

**What is needed from you.** Whether there is an existing CI system we are
expected to use or whether it is our choice; and who owns storage and retention —
because the retention half of this row is the same question as `OQ-19` below and
should be answered once, for both.

---

### 6.9 `OQ-19` — are campaign results kept, or regenerated?

**What is being asked.** After a batch campaign runs hundreds of recordings, are
its results kept as a baseline, deleted, or regenerated on demand?

**The reframe, which is this row's real contribution.** Because resim is
deterministic *by design*, and because that determinism is **measured** rather
than asserted, a campaign result is **regenerable if and only if its inputs still
exist** — the recording, the resolved run spec, the config bundle, and the exact
library binary. Inputs are kilobytes; the recording already embeds the config
bundle's bytes. Results are large. **So keeping inputs and regenerating results is
the cheap direction — and it is available only because determinism was designed
in from the start.** This is one of the places where an early architectural
decision pays a storage bill years later.

**The one hard constraint no policy can wish away.** Regeneration needs the
**binary**, not merely its hash. A component build that can no longer be obtained
makes its results unregenerable — and at that moment the stored results become
the only evidence that the run ever happened. The determinism work has a
*rebuilt-binary* axis precisely because rebuilding is not guaranteed to reproduce
bit-for-bit. So any retention policy needs an explicit rule for *"the binary is
gone"*: either the outputs are promoted to long retention, or the baseline is
knowingly abandoned. Both are acceptable; leaving it unstated is not.

**A three-tier shape to react to — offered, not adopted.**

| Tier | Kept | Why |
|---|---|---|
| Inputs — recording reference and hash, resolved spec, bundle bytes, library hash | Long | Kilobytes. Without them nothing is reproducible or auditable |
| Run manifests and reports | Long | This is the audit trail proper, and it is small |
| Bulk per-tick outputs | Short, regenerated on demand | Large, and recoverable while the binary is obtainable |
| Any run whose binary can no longer be obtained | Outputs promoted to long | The exception above |

**What is deliberately not concluded.** The actual durations, and whether an audit
obligation forces bulk retention regardless of regenerability. Those are a storage
budget and a compliance question, in that order.

**What is needed from you.** Whether any audit or customer obligation forces us
to keep the results themselves; and confirmation that this is answered together
with `OQ-15`'s retention half — one policy, two consumers.

---

### 6.10 `OQ-18` — who maintains project configuration after handover?

**What is being asked.** Once the tool is handed to a customer team, who owns the
per-project configuration — the calibration values, the pipelines, the layouts —
and what support model comes with it?

**Nothing technical is blocked, and it is worth recording *why*, because this is a
property that was designed for rather than a happy accident.** Project
configuration is **data in versioned files with no code**: there is no central
project roster (a project exists because some module's build file declares it),
calibration lives in per-project directories, and the config bundle is a build
*output* rather than a second place anyone edits a value. So *"who maintains it"*
is a question about repository access and review, not about capability. Nobody
needs to be able to program to own it.

**What actually determines the support model's cost — and this is worth saying to
whoever chooses.** The **diagnostics**. The explain and doctor commands, and an
authoring error that names the plug-in, the port it asked for, and every port the
manifest actually declares. Those are what let a customer team answer its own
questions instead of raising a ticket. **A thin support model is viable in
proportion to how good those messages are** — which turns this from a headcount
argument into an engineering target, and is the reason the diagnostics rules are
normative rather than nice-to-have.

**Three shapes, not chosen here.**

1. The customer team owns configuration, with the supplier on call for defects.
2. The supplier owns configuration as a service.
3. **Joint — the supplier owns the schema, the customer owns the values.**

**Recommendation is the third**, because it matches the artifacts exactly: the
schema *is* `conf/*.yaml` and the values *are* the per-project directories, so the
split follows a line that already exists in the repository rather than one drawn
across it.

**What is needed from you.** Which shape; and whether handover is even in scope
within the timeframe currently being planned — if it is not, this row can be
parked with the recommendation recorded rather than carried as open.

---

### 6.11 What answering these actually unlocks

So the state is honest about itself: **nothing in the implementation plan is
blocked by a design decision.** What remains is one contract word, one file, and
seven organisational answers, each already de-blocked so that its lateness costs
nothing.

| Answer | Immediately unlocks |
|---|---|
| `IFQ-01` ratified | The header work package can encode; one carve-out rule is deleted rather than written |
| `OQ-09` file arrives | `MP-1`'s exit becomes real instead of provisional; plan risk `R-8` retires |
| `OQ-14` mechanism agreed | Three performance requirements become failable, from the second run |
| `OQ-16` gate agreed | The project's own success measure becomes checkable in CI |
| `OQ-17` binary answered | Either no qualification obligation at all, or a scoped one — instead of an open-ended risk |
| `OQ-15` + `OQ-19` answered | Ten lines of the first work package, and one retention policy serving both |
| `OQ-18` shape chosen | A staffing answer; no code changes either way |
