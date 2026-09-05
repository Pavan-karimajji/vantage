# PARITY — Handoff

**What this is.** Where every register row that is *not* a requirement in this
set actually lands. Fifteen of the twenty-nine were disposed of as `AMEND`,
`ALLOCATE`, `PARK` or `NO CHANGE`, and this document names the destination for
each, so a disposition is a decision with an address rather than a decision to
do nothing.

**Why it comes last.** It could not be written before the system layer settled,
because that is what fixed which obligations stay here (`R-REQ-1`).

**Nothing in this document is a requirement.** It allocates no UID and traces
to nothing. Where it names a clause, that clause is written in the v2 set or in
`modules/viz`, never here — a second copy would be free to drift, which is the
whole reason these rows are not `KEEP`.

---

## 1. `AMEND` — one clause on a requirement that already exists

Every target below was read before being named. Two did not say what the
register assumed, and those findings are the useful part of this section.

| Register | Target | What the clause adds |
|---|---|---|
| `C-03` | `SIM:SYS-0081` | A `measured` stage resolves its ports through the same ingest map a source uses. There is no second recording-to-port reader. |
| `C-04` | `SIM:SYS-0084` | **Conflict — see §1.1.** |
| `C-17` | `SIM:SYS-0192` | **Already satisfied at this layer — see §1.2.** |
| `C-20` | `SIM:SYS-0049` | The report carries the fully-qualified instance path of the reporter, not only the module and the cycle. |
| `C-28` | `SIM:SYS-0022` | Feasibility is computed per named source, once a run can name more than one. |

### 1.1 `C-04` conflicts with `SYS-0084`, and the author decides

`SYS-0084` — *"`off` needs no special case"* — says an unused stage's ports
**shall simply be absent**, using the same absent-port convention a missing
input already uses, and that no code path may distinguish "absent because off"
from "absent because unmapped".

`C-04` wants the opposite mechanism: when a stage flips to replayed, its
request ports **bind to a declared, typed, inert sink**, so an upstream
producer keeps writing into something legal.

Both keep the graph whole; they are different designs, and only one can be the
convention. Written down rather than quietly resolved, because picking either
silently would leave the other requirement standing and wrong.

- **Keep absence** — `C-04` becomes `NO CHANGE`, and the upstream producer's
  writes go nowhere by the existing convention.
- **Adopt the sink** — `SYS-0084` is amended, and the absent-port convention
  stops being the answer for a replayed stage's inputs.

### 1.2 `C-17` is already satisfied at the system layer

`SYS-0192` already reads: *"Reset mode shall be configurable as none / reset /
reset-and-init, and reset timing as before the whole batch / before each entry
/ before each section."*

That is the two-axis vocabulary in full. The register said the requirement
*"gains this vocabulary"*; it already had it, and the register was written from
the study's summary rather than from the row. What is genuinely missing is the
**presentation** — two independent controls rather than one merged list — and
that is a player concern, not a system one.

**Disposition:** `C-17` is re-marked `NO CHANGE` at the system layer. The
presentation half is a `viz` player item, listed in §2.

## 2. `ALLOCATE` — written in another module

| Register | Destination | What it is |
|---|---|---|
| `C-16` | `modules/viz`, `IF-06` | The `Source`/`Feed` interface — `open`, `next_tick`, `seek` — written so *next tick* can mean *advance to the next boundary of the chosen cycle*. **This set's only hard prerequisite**, blocking `WP-08` and `WP-09`. |
| `C-18` | `VIZ:SYS-0064`, `VIZ:SYS-0075` | Layer visibility defaults to **off**; the searchable list explicitly covers the layer list. One function can declare twenty layers, so everything-on is unreadable on the first frame. |
| `C-17` (part) | `modules/viz` player | Reset action and reset timing as two independent controls rather than one merged list. The vocabulary is already `SIM:SYS-0192`'s; only the presentation is open. |

## 3. `PARK` — a trigger, not a schedule

A parked item with a date is a plan; a parked item with a trigger is a
decision. Both triggers are observations someone will actually make.

| Register | Unparks when |
|---|---|
| `C-05` | A recording arrives whose task graph cannot be expressed as declared periods plus the data triggers `SIM:SYS-0064` already provides. |
| `C-07` | A calibration-like port is first reported stale and someone is tempted to widen a tolerance to hide it. The field then goes in that component's `conf/ports.yaml` beside `optional:`. |

## 4. What this work does *not* invalidate — a correction

**The restart's budget entry claimed that `SIM:SW-0011` and `SIM:SW-0032` would
become "actively wrong". Both rows were read afterwards, and that claim is too
strong.** It is corrected here and in `layers.yaml` rather than left standing.

Both specify *"the resolved topic-to-port table"*, and the word doing the work
is **resolved**. Resolution happens before the spec is written: the resolver
picks **one** address per port, so what the spec carries downstream is still a
topic-to-port table — for the chosen topics. Inverting the *map*'s key does not
invert the *spec*'s table.

| Row | Verdict | Why |
|---|---|---|
| `SIM:SW-0011` | **Survives, wants one addition** | The spec should also carry which candidate matched, so a reader can answer `SYS-0002` without re-resolving. |
| `SIM:SW-0032` | **Survives unchanged** | A reader applies a resolved table and interprets nothing. That is unaffected by how the table was produced. |
| `SIM:SW-0029` | **Unaffected** | *"The index is keyed by topic"* is about the recording's own index, in the recording's own vocabulary. It was a false positive in the original grep. |

**What remains true, and is the whole reason for the restart:** the new
behaviour had **no software coverage at all**. That was never about existing
rows being wrong; it was about rows that did not exist. The corrected claim is
weaker and still sufficient.

## 5. Open, and the author's to close

| # | Question | Blocks |
|---|---|---|
| 1 | `C-04`: absent ports, or a typed null sink? (§1.1) | Nothing here — `WP-02` proceeds either way |
| 2 | Does `SIM:SW-0011` take the matched-candidate addition, or does the manifest alone carry it? (§4) | Nothing — `IMP-0015` already writes it to the manifest |
| 3 | Who writes `IF-06`, and when? (§2) | `WP-08` and `WP-09`, and nothing else |

None of the three blocks the first seven work packages.
