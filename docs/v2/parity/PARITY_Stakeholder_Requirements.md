# PARITY — Stakeholder Requirements

**Layer:** `STK` (top declared layer — see `layers.yaml`).
**Reader:** the developer who uses the bench.

A row here is false only if a developer sitting at the bench could observe it
being false. It says what they get, never how it is built.

**One category, `feature`.** The bench is a tool, not a vehicle feature:
nobody buys it and nobody ships it, so it carries no performance target of its
own that a stakeholder could hold us to. `kpi` is therefore not declared
(`R-REQ-16`, author's call 2026-09-05). If a performance bound is ever
supplied, the category is added to `layers.yaml` and the checker names every
row that has to be re-pointed. Declaring it now and leaving it empty would be
a finding; not declaring it is honest.

**One obligation per row** (`R-REQ-1`). This document has been split twice for
that reason: ten rows became fourteen when four of them turned out to carry two
obligations each, and fourteen became sixteen when two more did. Both times the
budget was re-derived from the count the work needs, never the other way round
(`layers.yaml`, `budget_history`).

> **The top declared layer is unparented by definition** (`R-REQ-12`), so every
> `Trace` below reads `—`. That is a finding only for a layer with something
> declared above it.

## Anatomy

```
**`STK-nnnn`** · priority · release — headline
**Shall.**    one obligation
**Accept.**   the observation that decides pass or fail, written so it can be false
**Category.** feature
**Verify.**   method · test-id   **Trace.** — at the top declared layer
```

## Where these came from

One row per `KEEP` item in `PARITY_Change_Register.md`. The register carries
the reasoning; a requirement carries the obligation and nothing else.

**UIDs are in creation order, not document order** (`R-REQ-2`). `STK-0011`
onwards were split out of rows that held two obligations, so they appear beside
the rows they came from rather than at the end. Two change items therefore own
two rows each — `C-01` (feed it, and know what fed it) and `C-12` (move
through it, and control how fast) — because each pair is separately
falsifiable and separately useful.

| Row | Register item | Row | Register item |
|---|---|---|---|
| `STK-0001` | `C-01` | `STK-0008` | `C-14` |
| `STK-0002` | `C-02` | `STK-0009` | `C-13` |
| `STK-0003` | `C-06` | `STK-0010` | `C-21` |
| `STK-0004` | `C-09` | `STK-0011` | `C-10` |
| `STK-0005` | `C-11` | `STK-0012` | `C-23` |
| `STK-0006` | `C-12` | `STK-0013` | `C-15` |
| `STK-0007` | `C-19` | `STK-0014` | `C-22` |
| `STK-0015` | `C-12` | `STK-0016` | `C-01` |

Nothing here restates an item disposed of as `AMEND`, `ALLOCATE`, `PARK` or
`NO CHANGE` — those obligations live in exactly one place, and it is not this
document.

---

## 1. Getting data into the bench

**`STK-0001`** · `P0` · `R1` — Feed the bench from recordings whose names changed between generations
**Shall.** The bench shall feed a port from a recording whose topic names differ from the ones it was first mapped against, without a second map file.
**Accept.** A recording using a renamed topic feeds the same ports as the recording the map was written against.
**Category.** `feature`
**Verify.** T · `STT-01`   **Trace.** —

**`STK-0016`** · `P0` · `R1` — Know which recorded name actually fed each port
**Shall.** A developer shall be able to see, per port, which recorded name supplied it.
**Accept.** After a run, each fed port names the one address that supplied it, and each unfed port names none.
**Category.** `feature`
**Verify.** T · `STT-16`   **Trace.** —

**`STK-0002`** · `P0` · `R1` — Compose one run from more than one recording
**Shall.** A developer shall be able to take some ports of a run from one recording and the rest from another.
**Accept.** A run naming two recordings executes, and each port reads from the source the run assigned it.
**Category.** `feature`
**Verify.** T · `STT-02`   **Trace.** —

## 2. Trusting the answer

**`STK-0003`** · `P2` · `R2` — Prove two builds agree, and see where they first do not
**Shall.** A developer shall be able to run a candidate build against a reference build on identical inputs and see where they first diverge.
**Accept.** A run of two builds reports either no divergence, or the first tick, port and field at which they differ.
**Category.** `feature`
**Verify.** T · `STT-03`   **Trace.** —

## 3. Setting a run up

**`STK-0004`** · `P1` · `R1` — Isolate one stage for execution in a single action
**Shall.** The bench shall set one stage to execute and every other stage to replay in a single action.
**Accept.** One action on a chosen stage leaves that stage executing and every other replaying, with no other change to the selection.
**Category.** `feature`
**Verify.** D · `STT-04`   **Trace.** —

**`STK-0011`** · `P1` · `R1` — Never be shown a selection state the stages underneath contradict
**Shall.** The bench shall not display a group state that the stages under it contradict.
**Accept.** A group whose stages disagree shows a third state that reports the disagreement and that the user cannot choose.
**Category.** `feature`
**Verify.** D · `STT-11`   **Trace.** —

**`STK-0005`** · `P1` · `R1` — Reproduce headlessly exactly what was set up at the screen
**Shall.** The bench shall state the invocation that reproduces its current selection.
**Accept.** Running the stated invocation produces a resolved run spec identical to the one the screen's selection produces.
**Category.** `feature`
**Verify.** T · `STT-05`   **Trace.** —

**`STK-0012`** · `P2` · `R2` — Drive a session that is already running, from a script
**Shall.** A developer shall be able to control and query a running session from a script, without the screen.
**Accept.** A script attached to a running session reads the current position and a property, starts and stops playback, and adds a mark.
**Category.** `feature`
**Verify.** T · `STT-12`   **Trace.** —

## 4. Moving through a recording

**`STK-0006`** · `P0` · `R1` — Move through a recording with ordinary transport controls
**Shall.** A developer shall jump, scrub, step, play and reverse through a recording.
**Accept.** Every named control moves the displayed position in the direction and by the amount its name states.
**Category.** `feature`
**Verify.** D · `STT-06`   **Trace.** —

**`STK-0015`** · `P1` · `R1` — Control playback speed, and be told what was achieved
**Shall.** A developer shall set the playback speed, including asking for the fastest the machine can manage.
**Accept.** A set speed is held while it is achievable, and the unbounded mode reports the rate actually reached rather than one requested.
**Category.** `feature`
**Verify.** T · `STT-15`   **Trace.** —

**`STK-0009`** · `P0` · `R1` — Step by a unit that means something
**Shall.** A developer shall choose what one step advances by, including advancing to the end of a chosen cycle.
**Accept.** Stepping by a chosen cycle lands on a tick whose inputs for that cycle all come from one run of it, and the chosen cycle is named on screen.
**Category.** `feature`
**Verify.** T · `STT-09`   **Trace.** —

**`STK-0008`** · `P1` · `R2` — Name the interesting part of a long recording and come back to it
**Shall.** A developer shall be able to name a time range inside a recording and reuse it later.
**Accept.** A named range survives saving and reopening, and a batch run can be told to play only the named ranges or to ignore them.
**Category.** `feature`
**Verify.** T · `STT-08`   **Trace.** —

**`STK-0013`** · `P1` · `R2` — Mark a moment and classify a stretch, as two different things
**Shall.** A developer shall be able to annotate a moment in a recording and, separately, to classify a stretch of it by type.
**Accept.** Annotations and classifications are stored and listed separately, and a corpus can be selected by classification alone.
**Category.** `feature`
**Verify.** T · `STT-13`   **Trace.** —

## 5. Understanding what happened

**`STK-0007`** · `P1` · `R1` — Read the log after a failure without hunting for the message that mattered
**Shall.** A repeated diagnostic shall not displace the others in the log.
**Accept.** A message repeating every tick appears once carrying an occurrence count, and messages issued before it are still present.
**Category.** `feature`
**Verify.** T · `STT-07`   **Trace.** —

**`STK-0010`** · `P1` · `R1` — Tell what a plug-in is without opening its source
**Shall.** A plug-in shall state what it is, well enough to be identified among many.
**Accept.** A listed plug-in shows a description, a version, an author and its supported projects, and a refused plug-in is named the same way.
**Category.** `feature`
**Verify.** T · `STT-10`   **Trace.** —

**`STK-0014`** · `P1` · `R1` — Open a colleague's recording on a machine with no build
**Shall.** A recording shall carry the configuration it ran with.
**Accept.** A recording opened on a machine with no build renders with its own configuration, and one missing that configuration says so rather than substituting another.
**Category.** `feature`
**Verify.** T · `STT-14`   **Trace.** —
