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
