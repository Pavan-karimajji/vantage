# SIM v2 — Open Questions Register

**One place to answer everything.** Assembled 2026-08-11. This document holds
no questions of its own — it is a **view** over the four authored documents, so
that answering is one pass instead of four. Each row says where the question
lives, what it blocks, and what happens if it is left alone. **The source
documents remain authoritative**; when a row here is answered, the answer is
written back into the owning document and this row is marked closed.

**How to use it:** work down §1 first. Those are decisions with a default
already argued in writing — a *yes* is a one-word answer and unblocks a work
package. §2 and §3 need someone outside the SIM team.

| Marker | Meaning |
|---|---|
| `DEFAULT` | A default is stated and argued. Silence adopts it; that is safe but should be deliberate |
| `BLOCKS` | Something cannot be finished — usually a threshold that cannot be set, so a requirement cannot be failed |
| `EXTERNAL` | Not answerable inside this repository. Needs a recording owner, a module team, quality, or DevOps |

---

## 1. Needs your confirmation — defaults already argued

These are the design decisions in `SIM_Implementation_Design_v0.1.md`. Every
one is written with its reasoning and its cost; the status marker is that
document's own. **`CONFIRM·HARD` means expensive to reverse — read those three
first.**

| ID | Status | The decision, in one line | Where |
|---|---|---|---|
| `DD-03` | `CONFIRM·HARD` | `simcore` is C++17 inside and exposes a **flat C ABI** to every embedder; `simengine` and the Python binding consume that and nothing else | Design §2 |
| `DD-04` | `CONFIRM·HARD` | **Exactly one codec implementation**, in C++; the player reads recordings through the C ABI, not a second Python codec | Design §2 |
| `DD-12` | `CONFIRM·HARD` | The **live world-model client is removed entirely** — no `sources/`, no world-model plug-in, no live stimulus. Every input is a recording | Design §2 |
| `DD-01` | `ADOPTED` | Deliverables are siblings in `modules/sim`: `src/simcore/`, `src/simengine/`, `src/adas_sim/`, headers at `include/simcore/`. **No language folder.** Includes the one separator rule — C++ names carry no separator, Python names are snake_case | Design §2 |
| `DD-02` | `CONFIRM` | The Resolved Run Spec is **JSON**, canonically serialised | Design §2, §3.4 |
| `DD-05` | `CONFIRM` | Static parameter data is a port **kind**, not a concept beside ports | Design §2 |
| `DD-06` | `CONFIRM` | Description resolution produces **several typed artifacts**, each with its own accepted-version set | Design §2 |
| `DD-07` | `CONFIRM` | `SW-0230`'s *"a few lines"* is **three statements** — one import, one construction, one call | Design §2 |
| `DD-08` | `CONFIRM` | `check/` moves intact to `contrib/check/`, excluded from the package, offered onward | Design §2 |
| `DD-09` | `CONFIRM` | Per-stage isolation reuses the **module ABI over a pipe**, hosted by a second `simengine` in single-stage mode | Design §2 |
| `DD-10` | `CONFIRM` | The Python package is restructured so **a package name is a software item name** | Design §2 |
| `DD-11` | `CONFIRM` | The **signal header is built before the cycle ladder**, and both before anything is deleted | Design §2 |
| `DD-13` | `CONFIRM` | **MCAP is the only codec** in release one; the other two readers are built when a sample file exists | Design §2 |
| `DD-14` | `CONFIRM` | The producing-and-not-executing verb is **`convert`**, not `record`; `record` leaves the verb set | Design §2 |

**And one wording amendment that should not sit open** — Design §33 proposes
`CN-0282` change from *"driving a live simulator is a plug-in concern"* to
*"out of scope entirely"*, because `DD-12` is stronger than the concept
currently reads. **Proposed, not applied** — amending the concept is its
owner's act. Leaving the two in disagreement is the drift `CN-0287` forbids.

### 1.1 `SignalHeader` — new, 2026-08-11

From `docs/interfaces_signal_header_plan.md`, which is the contract-side input
to `DD-11`'s `WP-05`. All six carry a default.

| ID | Question | `DEFAULT` |
|---|---|---|
| `IFQ-01` | **`timestamp_ns` or `timestamp_us`?** Today's field is `uint32 time_stamp` with no unit — as nanoseconds it wraps in **4.3 seconds** | `timestamp_ns`, `uint64`, wire-compatible in place |
| `IFQ-02` | Is the stamp **monotonic within a run** — required, or best-effort? | Required; a violation is reported, never clamped |
| `IFQ-03` | Does `cycle_counter` wrap, and at what value? Rung 2 must not read a wrap as a gap | Wraps at `uint32`; the bus handles wrap explicitly |
| `IFQ-04` | Do `DetectionList` / `FreeSpaceContour` / `ProcessedFrame` have real producers today, or are they still structural? | Add the field now — one line, avoids a wire change later |
| `IFQ-05` | Should the schema check read every component's `conf/ports.yaml`, or should interfaces carry its own list of port-payload types? | Read `conf/ports.yaml` — no second copy to drift (`R-VAR-2`) |
| `IFQ-06` | **One timestamp or two?** `SW-0043` lists *source time* and *capture time* as different fields; the header has one stamp and no field for the measurement instant | One field now; capture time stays explicitly *unknown* |

---

## 2. Inherited from the System Requirements — the five that block baselining

`SIM_System_Requirements_v0.1.md` §26 lists twenty-two. These five are called
out there as *"should close before this document is baselined"*, and all five
are `EXTERNAL`.

| ID | Question | Why it matters | Owner |
|---|---|---|---|
| `OQ-01` | **Do the recordings in scope carry task/cycle marking?** | `SW-0050` rung 1. **Now half-answered:** for recordings *this platform produces* the answer becomes *yes by construction* once §1.1 lands — every payload carries a `sig_header`, so every port sits on rung 2. **Foreign recordings remain open**, and that half is `OQ-09` | SIM team + a recording owner |
| `OQ-11` | Does an internal **port model or signal catalogue** already exist that should be adopted rather than defined? | **Adopting beats defining.** Must be asked before `SI-19`'s port model is authored; changes `SW-0383`'s scope substantially. Design carries it as assumption `A-4` | SIM team |
| `OQ-14` | The **numbers** for per-cycle cost, campaign throughput and player frame time, and the configurations they are measured on | `BLOCKS` — `SW-0272`, `SW-0323`, `SW-0369` cannot be *failed* without them. The harnesses are built either way | SIM team |
| `OQ-16` | The stated set of **common configuration changes** and each one's time budget | `BLOCKS` — `SW-0348`, the requirement closest to the project's own success measure | SIM team + a customer team |
| `OQ-17` | Are there **tool qualification or functional-safety** process constraints? | Potentially the requirement style, the verification evidence and the whole document set. **Answer early** | Quality / safety |

## 3. Inherited — the other seventeen

Carried as documented assumptions. Grouped by who can answer.

**A recording owner**

| ID | Question | Blocks |
|---|---|---|
| `OQ-08` | Definitive **input format list** for release one, in priority order | `SYS-0011`, `SYS-0012`. `DD-13` already narrows release one to MCAP |
| `OQ-09` | What exactly does the **bench capture** write, and **does it preserve the signal header end to end**? | `SYS-0015`, `SYS-0029`, `SYS-0061` — and the foreign half of `OQ-01`. §1.1 raises this one's value: it is now the question that decides whether rung 2 works on non-native recordings |
| `OQ-22` | Licence and distribution situation for **proprietary format readers** | `SYS-0011` |

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

## 4. Closed since the Software Requirements were written

Recorded so they are not re-asked. All eight of `SIM_Software_Requirements_v0.1.md`
§34.2's `SWQ-nn` are closed by a design decision — which is what §1 is now
asking you to confirm.

| Was | Closed by |
|---|---|
| `SWQ-01` — where does the C++ subtree live? | `DD-01` (`ADOPTED`) |
| `SWQ-02` — is static data a port class? | `DD-05` |
| `SWQ-03` — one description artifact or several typed? | `DD-06` |
| `SWQ-04` — Resolved Run Spec serialisation? | `DD-02` |
| `SWQ-05` — C ABI or C++ with a shim? | `DD-03` |
| `SWQ-06` — the line budget for `SW-0230`? | `DD-07` |
| `SWQ-07` — who owns `check/`? | `DD-08` |
| `SWQ-08` — per-stage isolation mechanism? | `DD-09` |

**Also settled, without having been a numbered question:** the `simcore` /
`sim-engine` spelling split, resolved 2026-08-11 to `simcore` / `simengine`
and written into `DD-01` as a rule so it cannot drift back.

## 5. Assumptions this register does not turn into questions

`SIM_Implementation_Design_v0.1.md` §31 lists seven (`A-1`…`A-7`). They are
*stated* assumptions, not open items — each is a position taken deliberately
with its consequence named. They are listed here only so that "not in the open
questions register" is not read as "nobody thought about it". Read them
alongside §1; `A-4` in particular is `OQ-11` wearing different clothes, and if
`OQ-11` closes the other way, `A-4` is what has to change.
