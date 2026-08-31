# What actually went wrong

**Written:** 2026-08-27, from a full read of `sim/docs/v1` (1.04 MB),
`sim/docs/v2` (1.54 MB), `viz/docs` (0.75 MB), and the code and git history
underneath them.

**Read this before starting any replan.** It exists because the author's own
description of the problem — *"it's never coming to an end, I could never see or
understand what's happening"* — turned out to have a precise, measurable cause
that is **not** the one it feels like.

---

## 0. Start here: the work is not behind. It is invisible.

| | |
|---|---|
| Hand-written source across sim + viz + df plug-ins | **~69,000 lines** |
| sim work packages closed | **28 of 43** (~79% by design item) |
| viz sync-plan work items closed | **38 of 43** |
| Tests that exist | **1,520** in sim, **49** in viz |
| End-to-end path from launcher to a real picture | **works, photographed, tick 96** |

Two months of work produced a working system. Nothing in this document says
otherwise, and the despair that prompted it is not proportionate to the state of
the code. What follows is why none of that is visible from inside the project.

---

## 1. The resume pointer says "start at the beginning" — always

`modules/sim/CLAUDE.md` instructs every session to begin by running
`trace_check.py --status`, calling it *the* resume pointer.

It reports **`WP-01` — the first work package — as "next."**

It says that because two of WP-01's eighteen boxes are `[~]` (started), and the
rule is *lowest-numbered unticked package wins*. It has therefore said "WP-01"
for weeks while completion went from 20% to 79%.

**This single defect explains the felt experience completely.** Every session
opens, asks where it stopped, is told *the beginning*, and finds unfinished work
everywhere it looks. There is no session in which the tool says "you are nearly
done." A person running that command daily for a month would correctly conclude
the thing never ends.

The irony is exact: 43 work packages were subdivided into **416 checkboxes**
precisely because 43 could not answer *"where did I stop"* — and the replacement
still cannot.

---

## 2. The remaining 21% is the part that makes it useful

The unfinished work is not scattered. It is concentrated, and it is load-bearing:

| Package | What it is | Boxes ticked |
|---|---|---|
| **WP-17 / WP-18** | the io index, **the codecs**, export | **0** |
| **WP-19** | preparation | **0** |
| **WP-30** | images | **0** |
| **WP-31** | *"make it a product"* / packaging | **0** |

WP-17/18 **are the readers and writers.** The three-pillar concept — readers,
engine, writers — has two pillars built and the third untouched.

Meanwhile **WP-32, 33, 34 and 34a were appended *after* WP-31 and are all done.**
New work was added past the "ship it" package while the ship-it package stayed
empty. That is the mechanism by which a project stops converging: the end of the
list stopped being the end.

Consistent with this, the layer with the largest gap between written and built is
the **concept layer** — 192 done, 90 started, 45 open — i.e. the top of the V is
less converged than the bottom. Design kept moving while implementation chased it.

---

## 3. The same mistake has now happened three times: building the replacement and never deleting the original

This is the deepest pattern, and it is still running today.

**v1.** Built its entire replacement stack, then stalled at retirement —
**Phase E: 7 boxes done of 49**, 15 of 15 open in *"delete the private tooling"*.
The claim *this replaces that* was never proven, **because deleting the old thing
was the proof.** Two stacks coexisted forever.

**v2.** `modules/sim/src/` now contains **two parallel stacks**: Python
`adas_sim/` (26,272 lines) and C++ `simcore/` (31,064 lines), with overlapping
sub-packages — `io`, `runspec`, `diagnostics`, `session`, `abi` exist in both.
Mid-migration, both halves live, neither deletable.

**viz — corrected 2026-08-30, both claims below were wrong.** `modules/df/src/platform/df_viz/`
is not old toolkit; it's df's real CarMaker viz plug-in (`sil_viz`/`cm_viz`
build and deploy it, `PushHost` loads it) — verified against a real build,
not the line count that originally called it "~4,900 lines of the old
toolkit." The "~6,300 lines of superseded tooling `df/tools/carla/`,
`replay/viz.py`, `df_sim_gui.py`, `bsdviz/` — all still present" claim was
also wrong: all four are active (recent commits, or live imports through the
current GUI, or both), not leftovers the R-SIM rules were written to replace.
**Why:** this section was written from a day-one measurement sweep — line
counts and directory listings — without reading the build config or the git
log. The pattern this section names *is* real, just not here: sim's own
Python scene/render/player stack really was a superseded copy left standing
for months, and really was deleted, 2026-08-29 (`B1`/`SM-12`). Full audit:
`docs/v2/SIM_Test_Execution_2026-08-30_movement_b_plan_audit.md` and
`..._b2_execute_b3_rescope.md`.

**Corrected 2026-08-30 — this used to say deletion had never once been executed.
It has now been, once.** Every migration in this project was a **copy**, never
a **move**, for three attempts running: v1's retirement stalled at 7 of 49
boxes, v2's two stacks still coexist, and sim's own Python scene/render/player
stack — the pattern's real instance in "viz," above — sat undeleted for months.
**`B1` broke the pattern, 2026-08-29: the first executed deletion in this
project's history**, not a copy left standing beside its replacement. The
warning still holds for everything not yet deleted — v1's private tooling,
v2's real remaining overlap (one item, `io`; see `B4`'s re-measure), the
cross-module Session duplication `MOVEMENT_B_PLAN.md` now tracks — one
deletion is a proof of capability, not yet a habit.

---

## 4. Specification became the deliverable

| | |
|---|---|
| Specification (sim v1 + sim v2 + viz) | **41,341 lines / 3.3 MB** |
| Requirements in sim v2 alone | **~1,437** across four layers |
| Test identifiers in sim v2 | **742** |
| Single checkbox rows that are now essays | **2,400–4,375 characters each** |
| The `.claude` rule layer on top | 61 files; `rules/sim.md` is **42 KB in 87 lines** |

**The documents predicted this about themselves.** The v2 concept document lists
as a *High* risk:

> the document set outgrows the product it describes

and leaves permanently open:

> how large should the derived document set be?

while the open-questions register simultaneously declares itself *"effectively
drained."* v1 said it more bluntly — *"documents larger than the code they
describe."* The project diagnosed its own failure mode in writing, filed it, and
then continued.

Corroborating symptoms found in the text: **WP-26b exists purely to undo a
bookkeeping error**; two traceability gaps are hardcoded as `KNOWN_UNDECOMPOSED`
so the checker prints PASS; work items now correct themselves in place (*"this
paragraph was stale by the time anyone re-read it"*); and the viz sync plan's §9
still asserts *"it writes no source, moves no file and bumps no submodule
pointer"* after doing all three.

**Roughly a third of every git log in both modules is requirement bookkeeping
rather than code.**

---

## 5. viz did not contradict sim — it absorbed sim

The author's suspicion was contradiction. That is not what happened, and the
distinction changes the fix.

The sync plan is **not** divergent: it defines its end conditions, deletes itself
when done, and is ~90% closed. What it did was **re-home sim's work by
negotiation** — sim's entire player milestone (of which **16 of 17 rows were
already DONE in Python**), the Session model, recording opening, codec
registration, plug-in discovery, config-bundle resolution, scrub semantics, and
`sim explain` → `viz_player --explain`.

Port/manifest resolution now exists **twice, deliberately** — viz wrote its own,
different from sim's.

So a large amount of finished Python was superseded by C++ that had to be written
again, and both still exist. This was reasoned, documented and agreed. It was
also, in effect, a second rewrite of a thing that already worked — the same
decision as v1→v2, one layer down.

---

## 6. Nothing tells you it is alive — *as written 2026-08-27. Answered since, by two different means, and this section is corrected rather than left standing.*

- **There is no CI anywhere** in the project. WP-01, the CI package, is the
  perpetual "next work package" from §1.
- The last **recorded** sim test run is `693 passed`, dated **Aug 5** — 22 days
  stale, and under half of the 1,520 tests that exist today.
- `modules/sim` has **no test execution record at all**. The only one in the repo
  is viz's, written the day viz was created.
- Later green runs exist **only as prose inside checkbox rows** — which is exactly
  what an execution record exists to prevent.

A project with 1,520 tests, no CI, and no dated evidence of them passing cannot
tell its author that it works. So it doesn't feel like it works.

**Corrected 2026-08-31.** The two bullets above were one diagnosis wearing two
symptoms, and they were answered by two different, unrelated fixes — neither of
which was "get hosted CI running":

- **"No dated evidence it passes"** was answered by the *records*, not by CI.
  Starting 2026-08-27 this module began writing a
  `docs/v2/SIM_Test_Execution_<date>[_<campaign>].md` per real campaign;
  eighteen exist as of this section's own edit (eighteen dated files under
  `docs/v2/`, this session's own CI-descope record making nineteen), each
  naming its pass/fail counts, the date and the commit they were run against.
  That is what makes *"is it alive"* answerable today: read the newest record,
  not the absence of a hosted job.
- **"No CI anywhere"** is, as of 2026-08-31, a closed question rather than an
  open one: hosted CI is **out of scope by decision** (`misc/START_HERE.md`
  Decision F), not missing for lack of time. The thing CI was actually standing
  in for — *a check harness that runs the same way every time, on both
  platforms sim ships for* — exists and runs green by hand
  (`scripts/ci_gate.py`, `WP-01`, `IMP-0366` closed against this same decision).
  What a hosted runner would have added on top — an unattended trigger and an
  audit trail nobody here was going to watch — was never the part of "alive"
  this section was actually measuring; the records above are.

Net: the felt absence this section named was real, and is gone — answered by a
habit of writing records, plus a decision that stopped treating an unbuilt
hosted job as the thing standing between this project and being verifiably
alive.

---

## 7. The proportion test

An external reference tool expresses the *entire* reader / component / per-port
measured-vs-simulated / wiring / visualization concept in **three INI files,
about 5 KB.** Switching a module from simulated to measured there is a *second
config file* in which that module's ports point at the reader. Not a feature, not
a mode, not a scheduler concern.

That is the yardstick. Not because the reference is better — several ideas in
this project's design are genuinely stronger — but because **5 KB is proof that
the concept is small.** When the description of a small concept reaches 3.3 MB,
the description has become the project.

---

## 8. What is genuinely good and must survive any replan

Do not throw these away. They are the real output of two months:

1. **Two independent per-module switches** (executed-vs-injected, and by what),
   with the invariant that both produce the same port set. The strongest idea in
   the whole set.
2. **Incoherence detection before the run** — transitive, with printed fix
   options, and waivers that stamp `coherent=false` everywhere.
3. **Geometry and pixels strictly separated** — components emit metres and
   meaning, the toolkit owns colour. This is why the BEV is consistent.
4. **Named, discovered ports** instead of a growing function signature.
5. **A recording is a model; a file format is a codec** — so conversion falls out
   for free.
6. **Record inputs *and* outputs** — a few kB per tick buys every later cut point.
7. **Two clocks per message**, never collapsed into one.
8. **Every drawn value traceable to the bytes that produced it**, with one
   producer and two formatters so the GUI and the CLI cannot disagree.
9. **`unknown` is printed, never a plausible default.**
10. **Closed lists with written reasons** — *"an override may destroy or attenuate
    information; it may never create an entity."*

---

## 9. The one-line diagnosis

> The concept was right, the code largely got built, and the project lost the
> ability to see that — because the only instrument it had for measuring progress
> always pointed at the starting line, nothing was ever deleted after being
> replaced, and the writing about the work grew until it outweighed the work.

Nothing here requires re-designing the system. It requires being able to *see* it.
