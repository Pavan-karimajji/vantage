# What we are actually building — the whole thing on one page

**Written:** 2026-08-27
**Purpose:** a plain-English checklist so the author and the assistant can confirm
they mean the same thing. **This is not a requirement document.** It allocates no
IDs, traces to nothing, and is not governed by `R-REQ-*`. It is a mirror held up
to three existing document sets (`sim/docs/v1`, `sim/docs/v2`, `viz/docs`) plus
what the author said out loud on 2026-08-27.

**How to use it:** read each line and mark it. `AGREE` / `WRONG` / `NOT MINE`.
Anything marked `WRONG` or `NOT MINE` is a scope error that has been sitting
inside 41,000 lines of specification without being visible.

Status column is what exists **today**, measured 2026-08-27:
🟢 works · 🟡 partly · 🔴 not built

---

## A. What this thing is

| # | In one sentence | Status |
|---|---|---|
| **1** | One tool that takes recorded driving data, runs our own software against it, and shows you what our software decided. | 🟢 |
| **2** | It is built as three separable pillars — **readers** get data in, the **engine** runs our modules, **writers** get results out. Changing one must not touch the other two. | 🟡 |
| **3** | The same tool serves two faces: a developer clicking through one recording, and a batch job grinding hundreds overnight. One engine underneath, never two. | 🟡 |

## B. Getting data in (readers)

| # | In one sentence | Status |
|---|---|---|
| **4** | Read many recording formats — mcap, ERG, MDF, rosbag and more later — and adding a new format means writing one small reader, never changing the engine. | 🟡 mcap + ERG real; MDF/rosbag absent |
| **5** | Read recordings **we did not produce** — another team's, a supplier's, a foreign simulator's — by writing a mapping file that says *"this topic in the file feeds this input"*. Declared as data, never as code. | 🟡 |
| **6** | Before a run starts, the tool says what this recording **can and cannot** do — which modules it can feed, which it can't, and why. You never discover it by watching a run fail. | 🟡 |

## C. Running our software (engine)

| # | In one sentence | Status |
|---|---|---|
| **7** | Per run, **every module is set to MEASURED (replayed from the file), SIMULATED (executed now), or OFF** — and a module downstream cannot tell which one it got. | 🟡 logic real, only one module to switch |
| **8** | You choose that **in the launcher when you open the tool** — not by hand-editing a YAML file beforehand. | 🔴 |
| **9** | Modules are **discovered, not hard-coded**. A new component or a new function adds a line of configuration; the tool itself never changes. | 🟢 |
| **10** | Each module declares its own cycle rate. The tool schedules them, and an input that is being held between updates is *shown* as held and ageing — exactly what the real vehicle sees. | 🟢 |
| **11** | If your measured/simulated mix is **incoherent** — e.g. recorded perception fed into a live function after the ego motion has changed — the tool refuses and tells you what to fix, **before** it runs. | 🟢 |
| **12** | A module that crashes or hangs must not take the whole run with it, and **crash, fail and timeout are three different results**, never merged into one. | 🟡 |
| **13** | Running the same recording twice gives the same answer, and the tool can **demonstrate** that rather than assert it. | 🟡 |
| **14** | You can nudge an input by hand — hold it, offset it, scale it, blank it — from a **short fixed list of verbs**. No scripting language inside a config file, ever. | 🟢 |

## D. Getting results out (writers)

| # | In one sentence | Status |
|---|---|---|
| **15** | Record **every module's inputs *and* outputs**, so a later run can be started from any point in the chain instead of only from the front. | 🟢 |
| **16** | A recording carries its own **provenance** — which build, which calibration, which scenario — and every signal is tagged as measured, simulated, or mocked, so a report can never quietly claim a mock was a measurement. | 🟢 |
| **17** | Exports (CSV, video, plots) are **one-way and lossy**, clearly a different kind of artifact from a recording, and never accepted back as a run input. | 🟡 |

## E. Seeing it (viz)

| # | In one sentence | Status |
|---|---|---|
| **18** | **One shared drawing toolkit** that every component pulls in to draw itself, and the simulator shows all the components' pictures merged in a single window. | 🟢 |
| **19** | A component says **what** to draw, in metres and in meaning (*"this is a warning zone"*). The toolkit alone decides pixels and colour — which is what keeps the 2D BEV identical across components. | 🟢 |
| **20** | **It must not end at BEV** — driver view, lane and pedestrian markings, free space, semantic segmentation, and video feed publishing. Probably a different approach for each. | 🔴 **none built** |
| **21** | Step, scrub and rewind freely — and stepping backwards **never invents** a state the software did not actually produce. | 🟢 |
| **22** | Click anything on screen and it tells you which signal, which tick, which file and which build produced it — and whether the software **published** that value or the drawing code **reconstructed** it. | 🟢 |

## F. How it is put together

| # | In one sentence | Status |
|---|---|---|
| **23** | **Skeleton in code, behaviour in configuration.** A new setup is a config file, not a code change. | 🟢 |
| **24** | Vehicle geometry, sensor poses and footprints come from the **project's own calibration**, never from constants inside the tool. Switching project must change the picture. | 🟡 |
| **25** | Anything the GUI can do, a **script can do headlessly** — same engine, for CI and for overnight batches. | 🟡 no CI exists |

---

## What is NOT in scope

Recorded so it cannot quietly reappear.

- **No live co-simulation** — no running inside a foreign simulator's process. Foreign
  simulators arrive as *files* plus a mapping, never as a live connection.
- **No pass/fail KPI framework** — cut from v2 deliberately.
- **No expression language, scripting hook or user callable** inside any config file.
- **No second copy of anything** — one codec stack, one session model, one port
  resolver. (Today this is violated; see `memory.md`.)

---

## The three questions this page exists to settle

**1. Is the concept right?** The lines above are the concept. If they are all
`AGREE`, then the design is not the problem and never was.

**2. Where is it?** 20 of 25 are green or amber. **The red ones are #8 (choose
measured/simulated in the launcher) and #20 (everything past BEV)** — and those
two are the two things the author described first and most often when asked what
this is for.

**3. Why does it feel endless?** Not because the concept is wrong or the work is
behind. See `memory.md` in this folder — it is a tracking and proportion failure,
and it is specific and fixable.

---

## The proportion problem, in one comparison

An external reference tool the author pointed to expresses **most of this whole
page** — reader, component under test, per-port measured-vs-simulated, wiring,
and the visualization variant — in **three INI files totalling about 5 KB**.
Swapping a module from simulated to measured there is not a feature, a mode flag
or a scheduler concern: it is *a second config file* in which that module's output
ports point at the reader instead of at the component.

This project has produced **41,341 lines of specification** for the same concept.

That is not an argument that the specification was worthless — much of it is
genuinely good, and several of its ideas are better than the reference's. It is
an argument about **how much writing a concept of this size can absorb before the
writing becomes the work**. That threshold was crossed, and the documents said so
themselves before anyone noticed.
