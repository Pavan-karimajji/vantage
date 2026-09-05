# PARITY — Change Register

**What this is.** The complete list of changes proposed for `sim` and
*Vantage* in this pass, one row each, written in plain English before any
requirement UID exists. It is the input to the requirement layers, not a
requirement document itself: it allocates no IDs, traces to nothing, and is
not governed by `R-REQ-*`.

**Why it exists separately.** The last large set in this module grew because
the thinking happened inside the specification. Here the thinking happens in
this file and the specification carries only the result. When a row is
disposed of as `AMEND`, `ALLOCATE` or `PARK`, **no requirement is written for
it here** — that is how `R-REQ-1` (one obligation, in exactly one place) is
held while still leaving a record that the question was asked and answered.

**Where the current-state claims come from.** Each *Today* line is a statement
about our own code and documents as read on **2026-08-29**. Re-check the
specific file before implementing the row — a fortnight of commits sits
between that read and this register.

---

## How to read a disposition

| Mark | Meaning |
|---|---|
| **KEEP** | A new requirement is written for it in this set. Counts toward the budget. |
| **AMEND** | The obligation already exists in the v2 set; it gains a clause. Tracked as a work package, never re-stated here. |
| **ALLOCATE** | It belongs to another module's namespace. Recorded here, written there. |
| **PARK** | Right, but not now. The row states the **trigger** that unparks it, so the diagnosis takes minutes rather than a day. |
| **NO CHANGE** | Examined and deliberately left alone. Recorded so nobody re-derives it as a good idea. |

Counts over 29 rows: **14 KEEP** · 4 AMEND · 2 ALLOCATE · 2 PARK · 7 NO CHANGE.
`C-17` moved from AMEND to NO CHANGE once its target was read — see its row.
The 14 KEEP rows are the `count:` in `layers.yaml`'s budget basis.

---

## KEEP — the fourteen that became requirements

**These rows have done their job and are compressed to one line each.** Each
argued that something deserved a requirement; each won, and the requirement now
carries the obligation. The argument is history — `git log -- <this file>` has
it in full if a decision is ever questioned.

The `KEEP` count is `layers.yaml`'s `budget_basis.count`, so this table is also
the derivation of the budget.

| | What it wanted | Became |
|---|---|---|
| **C-01** | A port names several source addresses, tried in order | `STK-0001`, `STK-0016` |
| **C-02** | One run reads more than one recording | `STK-0002` |
| **C-06** | Candidate and reference run side by side in one process | `STK-0003` |
| **C-09** | One click isolates a single stage | `STK-0004` |
| **C-10** | A group whose members disagree shows a derived mixed state | `STK-0011` |
| **C-11** | The launcher shows what reproduces it, and a test proves it does | `STK-0005` |
| **C-12** | The full transport control set, with an honest unbounded speed | `STK-0006`, `STK-0015` |
| **C-13** | Step granularity, including a complete cycle | `STK-0009` |
| **C-14** | Named sections inside a recording | `STK-0008` |
| **C-15** | Markers, in two families | `STK-0013` |
| **C-19** | A repeated message collapses to one entry with a count | `STK-0007` |
| **C-21** | Every plug-in carries an identity block | `STK-0010` |
| **C-22** | A recording carries the configuration bundle's bytes | `STK-0014` |

---

## The other fifteen — still live, and stated in full

Every row below is the **only** place its content lives. A `NO CHANGE` row is
what stops the idea being re-derived in a year; a `PARK` row's trigger is
written nowhere else; an `AMEND` or `ALLOCATE` row names a clause nobody has
written yet.

### C-03 · A replayed stage resolves through the same ingest map — **AMEND**
**Want.** One sentence stating that a stage in *measured* mode resolves its
ports through the same ingest map a source uses, and that there is no second
recording-to-port reader anywhere.
**Why.** Without the sentence, a plausible implementation grows a separate
injection reader, and the two then disagree about which fallback name matched
— which is precisely the bug `C-01` is about to make possible.
**Disposition.** **AMEND `SIM:SYS-0081`** — *"executed and injected are
indistinguishable to a consumer"*. It gains one clause: a `measured` stage
resolves its ports through the same ingest map a source uses, and there is no
second recording-to-port reader. Plus a test that fails if one appears. No new
id.
**Touches.** `ingest`, `engine`

### C-04 · An injected stage's unread inputs end on a declared sink — **AMEND**
**Want.** When a stage flips to replayed, its request ports bind to a
declared, typed, inert sink rather than being left unbound, so an upstream
producer keeps writing into something legal and the graph never tears.
**Why.** Leaving them unbound makes the situation harmless but silent. We want
harmless **and** visible — the sink keeps the graph whole, our existing orphan
badge keeps it honest.
**Disposition.** **Blocked on a real conflict, not deferred.** Its intended
target, `SIM:SYS-0084` (*"`off` needs no special case"*), says an unused
stage's ports **shall simply be absent**, and that no code path may distinguish
*absent because off* from *absent because unmapped*. This row wants the
opposite mechanism: request ports **bound to a declared, typed, inert sink**.

Both keep the graph whole. Only one can be the convention, and picking either
silently would leave the other requirement standing and wrong — so it is the
author's call, recorded in `misc/START_HERE.md` as open question 1.

- **Keep absence** — this row becomes `NO CHANGE`.
- **Adopt the sink** — `SIM:SYS-0084` is amended and stops being the answer
  for a replayed stage's inputs.
**Touches.** `engine`

### C-28 · Feasible cuts are reported per named source — **AMEND**
**Want.** The report of which cuts a recording supports is computed per named
source once a run can name more than one.
**Today.** Feasible cuts are already computed before any run and reported by
`probe` — that obligation exists, is marked done, and is not in question. What
it does not yet know about is `C-02`'s several sources.
**Why it is an amendment and not a row here.** The obligation is one sentence
about a capability that already exists; a second row stating it would be a copy
free to drift (`R-REQ-1`). **Caught late, 2026-09-05:** it was written as a new
row at the system layer before this register had disposed of it at all, which is
exactly how scope creeps in — a system row with no register entry behind it. The
row was retired to that document's disposition table the same day.
**Disposition.** **AMEND `SIM:SYS-0022`** — *"feasible cuts are computed, not
discovered"*, which is marked done. It gains one clause: feasibility is
computed per named source, once a run can name more than one. No new id.
**Touches.** `ingest`, `runspec`

### C-05 · Executing on a recorded cycle boundary — **PARK**
**Want.** A stage runs when the recording says a named cycle ended, not only
on a derived period.
**Why not now.** Our schedule is derived from declared periods, and that is
the safer design — a hand-wired schedule can silently never run a component.
The data-driven trigger requirement already reaches most of the way.
**Unpark when.** A recording arrives whose task graph cannot be expressed as
periods plus the data triggers we already have.
**Touches.** `engine`, `ingest`

---

### C-07 · A port says whether it is cyclic or latched — **PARK**
**Want.** A port declares `cyclic` or `latched`, so a static calibration-like
value is never reported stale.
**Why not now.** Dueness derived per function from one declared period is
cleaner, and nothing has failed yet.
**Unpark when.** The first time a calibration-like port is reported stale and
someone is tempted to widen a tolerance to hide it. It then goes in the
component's own `conf/ports.yaml` beside `optional:`, and the schema change
touches the port-shim generator plus one line per affected port.
**Touches.** `engine`

### C-08 · Declared control ports and a lifecycle ordering slot — **NO CHANGE**
**Want (rejected for now).** Data in, data out, control in and control out as
four declared port sets, so *who runs when* becomes configuration.
**Why not.** Our lifecycle is fixed in the C ABI at init / exec / shutdown,
which is simpler and has been enough. Declared control ports would be real
complexity for a capability nothing currently needs.
**Recorded because.** The day a component needs a second entry point — a debug
tick, a calibration hook, a mid-run reset — this is the decision that has to be
revisited, and re-deriving it from scratch is a week. One detail is worth
taking cheaply even without control ports: an **ordering slot**, so one event
can fan out to several targets in a defined order. Reset-then-init is not the
same as init-then-reset.
**Touches.** `engine`

---

### C-16 · A feed interface that can step to a cycle boundary — **ALLOCATE (viz)**
**Want.** The `Source`/`Feed` interface — open, next tick, seek — written so
that *next tick* can mean *"advance to the next boundary of the chosen
cycle"*, not only *"advance by one message"*.
**Why it is listed here.** It is unwritten today, and `C-12`..`C-15` are all
calls on it. If it ships offering message granularity only, the fifth step kind
in `C-13` becomes impossible to add later without changing the interface.
**Disposition.** **ALLOCATE to `modules/viz`, `IF-06`.** Written there,
tracing up to this set's stepping outcome. **The one hard ordering constraint
in the whole pass** — it blocks `WP-08` and `WP-09`, and nothing else. Who
writes it, and when, is open question 3 in `misc/START_HERE.md`.
**Touches.** `player`

### C-17 · Reset action and reset timing as two controls — **NO CHANGE**
**Want.** Two independent dropdowns, not one merged list: **what** happens
(nothing · reset · reset and re-initialise) and **when** (before the whole
batch · before each entry · before each played section).
**Why.** They are genuinely independent axes, and merging them produces a list
where most entries are unreachable. Nine combinations, seven of them
meaningful once *nothing* collapses across the timing axis.
**Disposition.** **Already satisfied at the system layer — no clause.**
`SIM:SYS-0192` reads: *"Reset mode shall be configurable as none / reset /
reset-and-init, and reset timing as before the whole batch / before each entry
/ before each section."* That is both axes in full.

This row originally said the requirement *"gains this vocabulary"* — written
from the study's summary rather than from the requirement itself, and wrong.
Corrected after reading the target. What is genuinely open is the
**presentation** — two independent controls rather than one merged list — and
that is a `viz` player item, not a system one.
**Touches.** `player`

### C-18 · Layers default to off, are named by producer, and scale — **ALLOCATE (viz)**
**Want.** Three things the layer panel must hold: a layer's identity includes
the component that produced it; visibility is session state saved with the
layout, not a runtime-only toggle; and **the default default is off**.
**Why.** One function can reasonably declare twenty layers. Five functions
across three components is a panel with a hundred rows, and everything-on is
unreadable on the first frame. The searchable-list requirement is the right
answer to the scale and should say explicitly that it covers the layer list.
**Disposition.** **ALLOCATE to `modules/viz`** — clauses on `VIZ:SYS-0064`
(per-layer default visibility, which should say the default default is *off*)
and `VIZ:SYS-0075` (the searchable list, which should say explicitly that it
covers the layer list). Written there.
**Touches.** `player`

---

### C-20 · Every message names exactly where it came from — **AMEND**
**Want.** A fully-qualified instance path in every diagnostic — bus, composite,
component, leaf — so you can go from any message straight to the configuration
that produced it.
**Today.** The module and the cycle are required. This is one level more
precise.
**Disposition.** **AMEND `SIM:SYS-0049`** — *"failures name the module and
the cycle"*. It gains one clause: the report also carries the fully-qualified
instance path of the reporter. No new id.
**Touches.** `diag`

### C-23 · A running session is controllable from a script — **KEEP, then park**
**Want.** A running session exposes control: open and close a configuration,
read and write a property, start and stop playback, read the current time, add
a marker, take a snapshot, read statistics and logs.
**Today.** Everything the CLI does is callable from Python, but nothing can
touch a session that is already running.
**Why allocate it now.** It is real capability with no home in the set, so it
cannot be scheduled or counted. Allocating an id and parking it immediately is
the difference between *deferred* and *forgotten*.
**Park state.** Written, allocated, not scheduled. Nowhere near the current
demo.
**Touches.** `runspec`, `player`

---

Recorded so nobody re-derives them.

### C-24 · Drawing payload budgets — **NO CHANGE**
Our scene builder already refuses an over-budget layer by name and count, and
the history cache is bounded in bytes. Worth recording that a production
system of this class ships **five** separate caps — total scene, single
packet, points per polyline, texture size, popup text length — because the
first time a point cloud or a full-resolution texture reaches a scene, someone
will propose raising ours.

### C-25 · The pixel-space exception — **NO CHANGE, but verify before v1**
Geometry is in metres, with exactly two exceptions: line weight and label
offset, because legibility is not physical. The narrow version is the right
call. But screen-space markers and badges pinned near a world position turn up
constantly in practice, so check that the two exceptions actually cover what a
real layer wants — and if they do not, widen deliberately and **once**, rather
than one exception at a time.

### C-26 · Uniform wiring for exporters and stages — **NO CHANGE**
An exporter, a reader and a stage could all be one kind of node with one wiring
syntax, and uniformity is why such a session file stays small. Our separation
of codecs from sources is deliberate and right — a codec that is also a
scheduler is how a design rots. Re-read our exporter configuration against this
idea once the export work unparks; do not restructure for it now.

### C-29 · One library declaring several units — **NO CHANGE**
**Want (not now).** One library that declares more than one independently
addressable unit, rather than one component per library.
**Why not.** It has never come up, and our ABI is one component per library.
Running the same library twice is already covered; one library declaring two
different units is not, and nothing needs it.
**Recorded because.** If a supplier ever delivers one binary containing two
functions, this should be recognised as a known shape with a known cost rather
than as a surprise mid-integration.
**Touches.** `plugin`, `engine`

### C-27 · Things that must not come back — **NO CHANGE**
- **Encoding a mode in a filename suffix.** Mode is a field. The alternative
  puts character arithmetic in production code to parse it back.
- **A hand-kept dependency-closure table.** Ours is derived from the graph, so
  it cannot go stale. A hand-kept one is 10% covered on its first day.
- **Mode selection that silently rewrites a calibration value.** If a derived
  parameter is ever needed, derive it visibly and put the derivation in the run
  manifest.
- **Auto-binding a new plug-in to every compatible source.** It produces a
  viewer wired to two dozen channels nobody asked for.
- **Automatic restart after a crash with the same arguments.** Unrecorded, it
  turns a crash into a pass and merges two outcomes we have said never to
  merge.
- **A raw byte-copy escape hatch into the drawing channel.** It is how a clean
  interface stops being one.
- **A component choosing its own colours.** Semantic tokens are the clearest
  single place this design is ahead. Never trade it away to make a port easier.

---

## What this work does *not* invalidate — a correction

The restart's budget entry claimed `SIM:SW-0011` and `SIM:SW-0032` would become
*actively wrong*. Both were read afterwards and **that claim is too strong**.
It is corrected here and in `layers.yaml` rather than left standing.

Both specify the *"resolved topic-to-port table"*, and the word doing the work
is **resolved**. Resolution happens before the spec is written: the resolver
picks **one** address per port, so what the spec carries downstream is still a
topic-to-port table, for the chosen topics. Inverting the *map*'s key does not
invert the *spec*'s table.

| Row | Verdict | Why |
|---|---|---|
| `SIM:SW-0011` | **Survives, wants one addition** | The spec should also carry which candidate matched, so a reader answers `SYS-0002` without re-resolving. Open question 2. |
| `SIM:SW-0032` | **Survives unchanged** | A reader applies a resolved table and interprets nothing. Unaffected by how the table was produced. |
| `SIM:SW-0029` | **Unaffected** | *"The index is keyed by topic"* is the recording's own index in its own vocabulary. A false positive in the original grep. |

**What remains true, and is the whole reason for the restart:** the new
behaviour had **no software coverage at all**. That was never about existing
rows being wrong; it was about rows that did not exist. The corrected claim is
weaker and still sufficient.

## What the register does not contain

- **No performance requirements.** The bench is a developer tool, not a
  vehicle feature — nobody buys it and nobody ships it, so it carries no
  performance target a stakeholder could hold us to. The stakeholder layer
  declares the `feature` category alone and is never asked for a KPI it does
  not have (`R-REQ-16`, author's call 2026-09-05). Any row here that reads as
  a speed or a latency is a *behaviour* — for example, reporting the rate
  actually achieved rather than a requested one — not a bound.
- **No status marks.** Whether a row is done is derived by the checker and by
  the implementation plan, never typed here (`R-REQ-6`).
