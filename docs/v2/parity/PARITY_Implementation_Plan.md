# PARITY — Implementation Plan

> **Superseded pending Stage 6, and kept deliberately.** This was written for
> the two-layer set, so its packages land `SYS` rows. Work packages land the
> *lowest* declared layer, which is now `SW`, so every `lands` list here is
> re-pointed at Stage 6 — the ordering, the grouping and the prerequisite below
> all survive that pass unchanged. It is kept rather than deleted because
> `selftest_mutations.yaml` plants four checks against it (`C-UNLANDED`,
> `C-DUPLAND`, `C-PLANUID`, `C-PLANMARK`) and nothing else in this repo
> declares a plan, so deleting it would leave those four checks unproven
> anywhere (`R-REQ-9`).

**What this is.** The build order. Thirteen work packages, each landing a
named set of `SYS` rows, ordered by what genuinely blocks what.

**The checkboxes here are the only hand-maintained progress state in this set**
(`R-REQ-6a`). No requirement document carries a progress mark, so there is
nothing to roll up and nothing to drift. Three states, and no others:

| Box | Means |
|---|---|
| `[ ]` | not started |
| `[~]` | started — **and the row must say `closed by <command or condition>`** |
| `[x]` | done — the tests the requirements name pass |

A bare `[~]` is a finding. Its whole value is telling the next session where to
resume, and a mark with no resume condition does not do that.

**Progress is not verification** (`R-REQ-6`). A ticked box says the work was
done; whether the requirement is met is decided by a Test Execution Record,
one per campaign, and no such record exists yet.

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

- [ ] **WP-01** — Ingest map keyed by port, with an ordered address list · lands `SYS-0001`, `SYS-0002` · Invert the key, accept a priority list, report which entry matched. Keep `absent:` exactly as it is.
- [ ] **WP-02** — Named sources and per-port binding · lands `SYS-0003`, `SYS-0005` · Several complete recordings in one run; each port bound to exactly one, with a declared default. Not multi-source merging.

## B. Setting a run up

- [ ] **WP-03** — Launcher: isolate, and the computed mixed state · lands `SYS-0009`, `SYS-0010` · One action to isolate a stage; a third group state that is computed and cannot be selected.
- [ ] **WP-04** — Headless reproduction, and the test that proves it · lands `SYS-0011`, `SYS-0012` · Display the reproducing invocation, and check both paths resolve to the same run spec. The test matters more than the line.

## C. Saying what things are

- [ ] **WP-05** — Diagnostics: occurrence counting · lands `SYS-0024` · Collapse an identical repeated message into one entry with a count, above a declared flood threshold.
- [ ] **WP-06** — Plug-in identity · lands `SYS-0025`, `SYS-0026` · Four mandatory fields, refused by name when incomplete, shown wherever a plug-in is listed, inspected or refused.
- [ ] **WP-07** — The bundle travels in the recording · lands `SYS-0027`, `SYS-0028` · Embed the configuration bundle's bytes; report its absence rather than substituting one from a checkout.

## D. Moving through a recording

- [ ] **WP-08** — Transport controls and play speed · lands `SYS-0015`, `SYS-0016` · The nine named actions, plus an unbounded mode that reports the rate achieved rather than one requested. **Blocked by the prerequisite.**
- [ ] **WP-09** — Step granularity · lands `SYS-0017`, `SYS-0018`, `SYS-0019` · Five kinds of step, the chosen cycle identified three ways, and a cycle step that lands on a coherent input set. **Blocked by the prerequisite.**
- [ ] **WP-10** — Named ranges · lands `SYS-0020`, `SYS-0021` · Ranges stored with the recording and restored; a batch told to play only them or ignore them.
- [ ] **WP-11** — Marks, in two kinds · lands `SYS-0022`, `SYS-0023` · Annotation of a moment and classification of a stretch, stored and listed apart; a corpus selectable by classification.

## E. Trusting the answer

- [ ] **WP-12** — Side-by-side reference run · lands `SYS-0006`, `SYS-0007`, `SYS-0008` · Two builds in one process on the same tick from the same inputs; the first divergence located; the reference staged as a declared artifact.
- [ ] **WP-13** — Live session control · lands `SYS-0013`, `SYS-0014` · Read and control a running session from a script, over the engine's own operations rather than a second implementation.

---

## Not in this plan

**The five `AMEND` register items land in the v2 set, not here** — one clause
each on a requirement that already exists (`C-03`, `C-04`, `C-17`, `C-20`,
`C-28`). Tracking them as work packages here would make this plan the second
place their obligation lives, which is the thing `R-REQ-1` forbids. They are
Stage 6's handoff.

**The two `ALLOCATE` items land in `modules/viz`** (`C-16`, `C-18`), and the
first of them is this plan's prerequisite.

**The two `PARK` items have triggers, not schedules** (`C-05`, `C-07`). A
parked item with a date is a plan; a parked item with a trigger is a decision.
