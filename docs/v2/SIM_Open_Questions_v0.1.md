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
reading the decomposition against itself); **five `OQ` closed** (`OQ-03`,
`OQ-08`, `OQ-13`, `OQ-20`, `OQ-21`); two of six `SignalHeader` questions closed
and the other three now carry argued answers rather than bare defaults.
**Nothing in the implementation plan is blocked by a design decision** — what
remains open is either external (§2, §3) or narrow (§1).

---

## 1. Open and answerable here

### 1.1 `SignalHeader` — three left, all now argued

From `docs/interfaces_signal_header_plan.md`, the contract-side input to
`DD-11`'s `WP-07`. All three carry a default, so silence is safe. What changed
on 2026-08-12 is that each default now rests on an argument that does not
depend on the missing input.

| ID | Question | Where it stands |
|---|---|---|
| `IFQ-01` | **Microseconds or nanoseconds?** The width is settled (`uint64`); only the unit is open. Today's `uint32 time_stamp` read as ns wraps in 4.3 s | **`timestamp_us`.** The decisive argument is **unit agreement**, and it needs no value file: the cycle period is already fixed as `<COMPONENT>_<FN>_PERIOD_US` in integer microseconds (`R-SIM-18`, `SYS-0072`) and a fractional one is refused, so a nanosecond stamp puts two units in adjacent fields of one contract. Width decides nothing — `uint64` µs is 584,000 years, `uint64` ns is 584 years. **Carry one consequence with it:** the bus stays integer nanoseconds (`SW-0046`), so the fixed ×1000 happens exactly once, at ingest, and is named in `SW-0033` as the only unit conversion in the engine — otherwise `ANL-SW-02`'s ban on unit arithmetic trips on it. **Still awaiting the value file**; a source finer than 1 µs flips it back |
| `IFQ-02` | Is the stamp **monotonic within a run** — required, or best-effort? | **Required; a violation is reported, never clamped.** Clamping turns a producer's timing bug into a plausible-looking zero. **One consequence added:** a present-but-non-monotonic source time is *worse* than an absent one, because the recovery ladder would otherwise claim rung-3 quality for data that cannot support it — so the violation **demotes that port to rung 4** (`SW-0050`) and reports the offending pair of stamps |
| `IFQ-06` | **One timestamp or two?** `SW-0043` lists *source time* and *capture time* as different fields; the header has one stamp and nothing for the measurement instant | **One field now** — but the answer is **conditional on `OQ-09`**, not independent of it, and saying so is the whole change. One field is safe only while the *recording* supplies reception time from its envelope, which MCAP does. If the bench capture carries no per-message reception stamp, this flips to two fields, because `SW-0044` forbids filling either clock from the other and there would be nothing else to fill it from |

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

## 2. Inherited from the System Requirements — the five baselining gates

`SIM_System_Requirements_v0.1.md` §26 lists twenty-two, of which five have
closed. Five of the remainder are **gates rather than rows**: that document is
not baselined until each has an answer or a written fallback.

| ID | Question | Why it matters | Owner |
|---|---|---|---|
| `OQ-01` | **Do the recordings in scope carry task/cycle marking?** | `SW-0050` rung 1. **Half-answered:** for recordings *this platform produces* the answer becomes *yes by construction* once §1.1 lands — every payload carries a `sig_header`, so every port sits on rung 2. **Foreign recordings remain open**, and that half is `OQ-09` | SIM team + a recording owner |
| `OQ-11` | Does an internal **port model or signal catalogue** already exist that should be adopted rather than defined? | **Adopting beats defining.** Must be asked before `SW-0388`'s catalogue is authored; changes its scope substantially. Design carries it as assumption `A-4` | SIM team |
| `OQ-14` | The **numbers** for per-cycle cost, campaign throughput and player frame time, and the configurations they are measured on | `BLOCKS` — `SW-0272`, `SW-0323`, `SW-0369` cannot be *failed* without them. The harnesses are built either way | SIM team |
| `OQ-16` | The stated set of **common configuration changes** and each one's time budget | `BLOCKS` — `SW-0348`, the requirement closest to the project's own success measure | SIM team + a customer team |
| `OQ-17` | Are there **tool qualification or functional-safety** process constraints? | Potentially the requirement style, the verification evidence and the whole document set. **Now carries a written fallback** (SYS §26): unanswered by the time the seam is built, the chain is developed in the present style and re-styling is accepted as a known, scoped cost. An unanswered question with a fallback is a managed risk; one without is a surprise arriving after 32 packages are cut | Quality / safety |

## 3. Inherited — the other twelve

Carried as documented assumptions. Grouped by who can answer.

**A recording owner**

| ID | Question | Blocks |
|---|---|---|
| `OQ-09` | What exactly does the **bench capture** write, and **does it preserve the signal header end to end**? | `SYS-0015`, `SYS-0029`, `SYS-0061`; the foreign half of `OQ-01`; and now `IFQ-06`, which is conditional on it. **Raised in value again on 2026-08-12:** `MP-1`'s exit is provisional against a crafted fixture until a real sample exists (`WP-18`), so ten seconds of real bench capture retires plan risk `R-8` outright |
| `OQ-22` | Licence and distribution situation for **proprietary format readers** | `SYS-0011` — now concrete: MDF4 and TDMS are the two |

**Module teams**

| ID | Question | Blocks |
|---|---|---|
| `OQ-05` | Which components have **real, functional libraries** today, and which are structural only? | What can actually be validated in `E2E-02`, `E2E-03`, `E2E-10`. **Narrowed 2026-08-12:** `df` and `vdy` are the two with generated port manifests and real libraries, so `IT-22`'s *"a second component completes the checklist unaided"* can be planned against them now. What is still open is which of the remaining nine are functional rather than structural |
| `OQ-06` | Do existing modules support **reset without destroy**? | `SYS-0048`, `SYS-0192` |
| `OQ-12` | Do any modules **change rate at run time**? | `SYS-0066`, `SYS-0071`, `SYS-0072` |

**Algorithm teams**

| ID | Question | Blocks |
|---|---|---|
| `OQ-02` | Is **ego re-integration** needed in release one? | `SYS-0108` |
| `OQ-04` | Is module-level staging plus per-port override **sufficient granularity**? | `SYS-0080`, `SYS-0082` |
| `OQ-07` | Should the system **inject parameters**, or point at a module's existing parameter file? | `SYS-0177`, `SYS-0179` |
| `OQ-10` | Preferred **exchange format** for outputs | `SYS-0111` |

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

### 4.5 `SignalHeader` — two of six

| ID | Answer |
|---|---|
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

## 5. Assumptions this register does not turn into questions

`SIM_Implementation_Design_v0.1.md` §31 lists seven (`A-1`…`A-7`). They are
*stated* assumptions, not open items — each is a position taken deliberately
with its consequence named. They are listed here only so that "not in the open
questions register" is not read as "nobody thought about it". `A-4` in
particular is `OQ-11` wearing different clothes: if `OQ-11` closes the other
way, `A-4` is what has to change.
