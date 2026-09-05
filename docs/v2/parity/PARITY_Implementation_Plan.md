# PARITY — Implementation Plan

**What this is.** The build order. Thirteen work packages, each landing a named
set of design rows, ordered by what genuinely blocks what.

**The detail is not here, and that is deliberate.** A package row says *what it
lands* and *what it is for*, in one line. *Which file, which symbol* is
`PARITY_Implementation_Design.md`'s answer, one row per software requirement.
A plan whose rows grow a paragraph each time someone touches them stops being a
build order and becomes a diary (`R-REQ-6a`).

**The checkboxes here are the only hand-maintained progress state in this set.**
No requirement document carries a progress mark, so there is nothing to roll up
and nothing to drift. Three states, and no others:

| Box | Means |
|---|---|
| `[ ]` | not started |
| `[~]` | started — **and the row must say `closed by <command or condition>`** |
| `[x]` | done — the tests the requirements name pass |

A bare `[~]` is a finding (`C-PLANMARK`). Its whole value is telling the next
session where to resume.

**Progress is not verification** (`R-REQ-6`). A ticked box says the work was
done; whether the requirement is met is a Test Execution Record's answer, one
per campaign, and none exists yet.

## Prerequisite, owned elsewhere

**The `Source`/`Feed` interface — register item `C-16`, allocated to
`modules/viz`.** It is unwritten, and every transport control is a call on it.
If it ships offering message granularity only, the fifth step kind in `WP-09`
becomes impossible to add later without changing the interface.

**Blocks `WP-08` and `WP-09`, and nothing else.** Eleven of the thirteen
packages are independent of it, so it gates breadth rather than progress.

---

## Order, and why

Ingest first: it is the foundation everything reads through, it is contained,
and it is the highest-value thing in the register. The launcher and the
self-describing artifacts follow because they are independent of everything.
The player packages wait on the prerequisite above. The two `R2` packages —
the side-by-side run and live control — are last because nothing depends on
them.

## A. Getting data in

- [ ] **WP-01** — Ingest map keyed by port, with an ordered address list · lands `IMP-0001`, `IMP-0002`, `IMP-0003`, `IMP-0004`, `IMP-0005`, `IMP-0006`, `IMP-0007`, `IMP-0015` · Invert the key, resolve in order, report what matched. `absent:` is untouched.
- [ ] **WP-02** — Named sources and per-port binding · lands `IMP-0008`, `IMP-0009`, `IMP-0010`, `IMP-0011` · Several complete recordings in one run; each port bound to exactly one, with a declared default. Not multi-source merging.

## B. Setting a run up

- [ ] **WP-03** — Launcher: isolate, and the computed mixed state · lands `IMP-0018`, `IMP-0019`, `IMP-0021` · One action to isolate a stage; a third group state that is computed and has no setter to reach.
- [ ] **WP-04** — Headless reproduction, and the test that proves it · lands `IMP-0012`, `IMP-0013`, `IMP-0020`, `IMP-0022` · Display the reproducing invocation, and make both paths resolve through one construction. The test matters more than the line.

## C. Saying what things are

- [ ] **WP-05** — Diagnostics: occurrence counting · lands `IMP-0040`, `IMP-0041`, `IMP-0042` · Collapse an identical repeated message into one entry with a count, and say once when that began.
- [ ] **WP-06** — Plug-in identity · lands `IMP-0043`, `IMP-0044`, `IMP-0045`, `IMP-0046` · Four mandatory fields, refused by name when incomplete, carried into the deployed copy, read through one accessor.
- [ ] **WP-07** — The bundle travels in the recording · lands `IMP-0016`, `IMP-0047`, `IMP-0048`, `IMP-0049` · Embed the bytes, store their hash, and make absence a value rather than a reason to look on disk.

## D. Moving through a recording

- [ ] **WP-08** — Transport controls and play speed · lands `IMP-0023`, `IMP-0024`, `IMP-0025`, `IMP-0026`, `IMP-0027` · The nine named actions, and a rate that is measured rather than requested. **Blocked by the prerequisite.**
- [ ] **WP-09** — Step granularity and cycles · lands `IMP-0028`, `IMP-0029`, `IMP-0030`, `IMP-0031`, `IMP-0032`, `IMP-0033` · Five kinds of step, cycles discovered from the recording, and a cycle step that lands on a coherent input set. **Blocked by the prerequisite.**
- [ ] **WP-10** — Named ranges · lands `IMP-0034`, `IMP-0035`, `IMP-0036` · Bounds in the recording's own timebase, travelling with the file, inclusive at both ends.
- [ ] **WP-11** — Marks, in two kinds · lands `IMP-0037`, `IMP-0038`, `IMP-0039` · Annotation and classification as separate types in separate blocks, each stamped with author and time at creation.

## E. Trusting the answer

- [ ] **WP-12** — Side-by-side reference run · lands `IMP-0014`, `IMP-0017`, `IMP-0050`, `IMP-0051`, `IMP-0052` · Two builds sharing one resolved input set; the first divergence located; both builds' outputs recorded separably.
- [ ] **WP-13** — Live session control · lands `IMP-0053`, `IMP-0054` · Read and control a running session from a script, over an operation table built from the headless API's own exports.

---

## Not in this plan

**The five `AMEND` register items land in the v2 set, not here** — one clause
each on a requirement that already exists (`C-03`, `C-04`, `C-17`, `C-20`,
`C-28`). Tracking them as work packages here would make this plan the second
place their obligation lives, which is the thing `R-REQ-1` forbids. They are
Stage 7's handoff.

**The two `ALLOCATE` items land in `modules/viz`** (`C-16`, `C-18`), and the
first of them is this plan's prerequisite.

**The two `PARK` items have triggers, not schedules** (`C-05`, `C-07`). A
parked item with a date is a plan; a parked item with a trigger is a decision.
