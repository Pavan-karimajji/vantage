# SIM v2 — Open Questions Register

**One place to answer everything.** Assembled 2026-08-11, last updated
2026-08-11. This document holds no questions of its own — it is a **view** over
the authored documents, so that answering is one pass instead of four. Each row
says where the question lives, what it blocks, and what happens if it is left
alone. **The source documents remain authoritative**; when a row is answered,
the answer is written back into the owning document and the row moves to §5.

| Marker | Meaning |
|---|---|
| `DEFAULT` | A default is stated and argued. Silence adopts it; that is safe but should be deliberate |
| `BLOCKS` | Something cannot be finished — usually a threshold that cannot be set, so a requirement cannot be failed |
| `EXTERNAL` | Not answerable inside this repository. Needs a recording owner, a module team, quality, or DevOps |

**Where it stands after the 2026-08-11 pass:** all fourteen design decisions
confirmed, `OQ-08` closed, the `CN-0282` concept amendment applied, two of six
`SignalHeader` questions closed. **Nothing in the implementation plan is now
blocked by a design decision** — what remains open is either external (§2, §3)
or narrow (§1).

---

## 1. Open and answerable here

### 1.1 `SignalHeader` — three left

From `docs/interfaces_signal_header_plan.md`, the contract-side input to
`DD-11`'s `WP-05`. All three carry a default, so silence is safe.

| ID | Question | Where it stands |
|---|---|---|
| `IFQ-01` | **Microseconds or nanoseconds?** The width is settled (`uint64`); only the unit is open. Today's `uint32 time_stamp` read as ns wraps in 4.3 s | **Leaning `timestamp_us`**, which reverses the plan's first draft: if the sources are µs, a ns header makes every *producer* multiply by 1000 rather than the *recorder* multiplying once, and a ns field fed from µs sources carries three trailing zeros that read as false precision. **Awaiting the value file.** A source finer than 1 µs flips it back |
| `IFQ-02` | Is the stamp **monotonic within a run** — required, or best-effort? | Default: **required; a violation is reported, never clamped.** Clamping turns a producer's timing bug into a plausible-looking zero |
| `IFQ-06` | **One timestamp or two?** `SW-0043` lists *source time* and *capture time* as different fields; the header has one stamp and nothing for the measurement instant | Default: **one field now**; capture time stays explicitly *unknown*. The second is one field number later, not a wire change |

**`IFQ-05` is reframed rather than open** — see that plan's §8.1. The question
was whether the schema check should read every component's `conf/ports.yaml`
(common, nothing drifts) or interfaces should keep its own list (standalone, but
a second copy). The recommendation is a third shape that takes both wins: the
check reads **whichever `ports.yaml` files are present** — none in a bare
interfaces clone, all in CI — so there is no second list and interfaces never
*requires* a sibling. One thing to confirm: the standalone case must **report
what it saw**, because a check that silently passes on zero inputs dies quietly.

---

## 2. Inherited from the System Requirements — the four that block baselining

`SIM_System_Requirements_v0.1.md` §26 lists twenty-two. Five were called out
there as *"should close before this document is baselined"*; `OQ-08` has since
closed, leaving four, and all four are `EXTERNAL`.

| ID | Question | Why it matters | Owner |
|---|---|---|---|
| `OQ-01` | **Do the recordings in scope carry task/cycle marking?** | `SW-0050` rung 1. **Half-answered:** for recordings *this platform produces* the answer becomes *yes by construction* once §1.1 lands — every payload carries a `sig_header`, so every port sits on rung 2. **Foreign recordings remain open**, and that half is `OQ-09` | SIM team + a recording owner |
| `OQ-11` | Does an internal **port model or signal catalogue** already exist that should be adopted rather than defined? | **Adopting beats defining.** Must be asked before `SI-19`'s port model is authored; changes `SW-0383`'s scope substantially. Design carries it as assumption `A-4` | SIM team |
| `OQ-14` | The **numbers** for per-cycle cost, campaign throughput and player frame time, and the configurations they are measured on | `BLOCKS` — `SW-0272`, `SW-0323`, `SW-0369` cannot be *failed* without them. The harnesses are built either way | SIM team |
| `OQ-16` | The stated set of **common configuration changes** and each one's time budget | `BLOCKS` — `SW-0348`, the requirement closest to the project's own success measure | SIM team + a customer team |
| `OQ-17` | Are there **tool qualification or functional-safety** process constraints? | Potentially the requirement style, the verification evidence and the whole document set. **Answer early** | Quality / safety |

## 3. Inherited — the other sixteen

Carried as documented assumptions. Grouped by who can answer.

**A recording owner**

| ID | Question | Blocks |
|---|---|---|
| `OQ-09` | What exactly does the **bench capture** write, and **does it preserve the signal header end to end**? | `SYS-0015`, `SYS-0029`, `SYS-0061` — and the foreign half of `OQ-01`. §1.1 raises this one's value: with the format now known to be TDMS, this is the question that decides whether rung 2 works on non-native recordings |
| `OQ-22` | Licence and distribution situation for **proprietary format readers** | `SYS-0011` — now concrete: MDF4 and TDMS are the two |

**Module teams**

| ID | Question | Blocks |
|---|---|---|
| `OQ-05` | Which components have **real, functional libraries** today, and which are structural only? | What can actually be validated in `E2E-02`, `E2E-03`, `E2E-10`. Design assumption `A-5` names `df` and `vdy` as the two |
| `OQ-06` | Do existing modules support **reset without destroy**? | `SYS-0048`, `SYS-0192` |
| `OQ-12` | Do any modules **change rate at run time**? | `SYS-0066`, `SYS-0071`, `SYS-0072` |
| `OQ-03` | How many **instances of one module** must a run support? | `SYS-0043` |

**Algorithm teams**

| ID | Question | Blocks |
|---|---|---|
| `OQ-02` | Is **ego re-integration** needed in release one? | `SYS-0108` |
| `OQ-04` | Is module-level staging plus per-port override **sufficient granularity**? | `SYS-0080`, `SYS-0082` |
| `OQ-13` | Is **same-step execution** acceptable as default, or must transport delays be modelled from day one? | `SYS-0077` |
| `OQ-07` | Should the system **inject parameters**, or point at a module's existing parameter file? | `SYS-0177`, `SYS-0179` |
| `OQ-10` | Preferred **exchange format** for outputs | `SYS-0111` |

**SIM team / process**

| ID | Question | Blocks |
|---|---|---|
| `OQ-15` | Which **CI system**, and what artifact retention? | `SYS-0201`, `SYS-0184` |
| `OQ-18` | Who **maintains project configuration** after handover, and what is the support model? | `SYS-0281` |
| `OQ-19` | **Campaign retention** policy — baseline, regenerable, or deleted | `SYS-0117`, `SYS-0184` |
| `OQ-20` | Product and workspace **naming** — adopt v1's names, or the concept's neutral role names | Nothing technical. Documentation and UI strings only |
| `OQ-21` | **Build or adopt** the interactive viewer surface | `SYS-0128`–`SYS-0157` implementation cost, not their content |

---

## 4. Answered 2026-08-11

### 4.1 All fourteen design decisions — confirmed

Every `DD-nn` in `SIM_Implementation_Design_v0.1.md` §1 now reads `ADOPTED`; the
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

### 4.2 `OQ-08` — the format list

**MCAP** (the system's own interchange format) · **MDF4** (vehicle measurement)
· **TDMS** (bench capture). Priority order is moot: `DD-13` ships MCAP now and
writes each other reader the week its first sample file arrives.

**Naming them changed the plan's shape not at all**, which is the useful signal.
`R-SIM-14` makes a format a codec of ~4 methods behind one registered interface,
so three names is three rows in the codec table — `io/codecs/{mcap,mdf4,tdms}`
and one conditional exit gate at `WP-18`. Had naming the formats propagated
further than that, the codec seam would have been wrong.

### 4.3 `CN-0282` — concept amendment applied

`CN-0282` read *"driving a live simulator is a plugin concern, never a core
one."* With `DD-12` confirmed it now reads *"out of scope entirely — a foreign
simulator reaches the system only as a recording, through the ordinary codec and
ingest-map path."* Design §33 records the change and its date; the Design's §32
row for it is closed. This was the one item the Design said *"should not sit
open"*, because the next reader of the concept would have believed the weaker
wording.

### 4.4 `SignalHeader` — two of six

| ID | Answer |
|---|---|
| `IFQ-03` | **Wrap at `uint32`.** The bus handles wrap explicitly, so rung 2 never reads a wrap as a gap |
| `IFQ-04` | **The three legacy messages are dummy**, so they are left untouched — no field added, `adas.common.Header` not deprecated. This *reverses* the plan's draft ("add it while the field is free"): wire compatibility protects encoded bytes that exist, and for a message nobody produces there are none. `R-IFACE-4` is scoped by *"can be a port payload"*, so the schema check demands a header the day one gains a real producer — the obligation is enforced when it becomes real, with no list to remember |

### 4.5 Earlier in the same pass

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
