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

Status column is what exists **today**: 🟢 works · 🟡 partly · 🔴 not built.
First measured 2026-08-27; re-measured 2026-08-28 after the step-zero fixes
(`F-1`…`F-4`), `F-7` and `F-8`; **re-measured again 2026-08-31** after `WP-22`
(video feed publishing shipped), the legacy-recording ingest fix, and the
author's scope change narrowing #20. Only the marks and lines that became false
were touched — no requirement was added, removed or reworded otherwise.

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
| **5** | Read recordings **we did not produce** — another team's, a supplier's, a foreign simulator's — by writing a mapping file that says *"this topic in the file feeds this input"*. Declared as data, never as code. | 🟢 wired 2026-08-28 — a legacy-vocabulary recording went from 218 empty ticks to 174 distinct object payloads |
| **6** | Before a run starts, the tool says what this recording **can and cannot** do — which modules it can feed, which it can't, and why. You never discover it by watching a run fail. | 🟡 the launcher answers, naming the missing ports (`F-7`); `sim probe` still reports nothing |

## C. Running our software (engine)

| # | In one sentence | Status |
|---|---|---|
| **7** | Per run, **every module is set to MEASURED (replayed from the file), SIMULATED (executed now), or OFF** — and a module downstream cannot tell which one it got. | 🟡 logic real, only one module to switch |
| **8** | You choose that **in the launcher when you open the tool** — not by hand-editing a YAML file beforehand. | 🟢 `WP-35`, 2026-08-28 — stage/mode row, both directions run and screenshotted |
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
| **16** | A recording carries its own **provenance** — which build, which calibration, which scenario — and every signal is tagged as measured, simulated, or mocked, so a report can never quietly claim a mock was a measurement. | 🟢 build and tags real (`F-2`, `F-8`); **calibration hash proven on the real path 2026-08-31** — a real `df_sil.dll` built for `vs2026` with its packed `config/bundle.sha256`, resim'd with `--save`, reads back a real, matching `config_bundle_sha256` both in the recording's own manifest and through `sim explain`'s evidence chain (the same formatter the player's evidence panel uses) — no longer `unknown` |
| **17** | Exports (CSV, video, plots) are **one-way and lossy**, clearly a different kind of artifact from a recording, and never accepted back as a run input. | 🟡 |

## E. Seeing it (viz)

| # | In one sentence | Status |
|---|---|---|
| **18** | **One shared drawing toolkit** that every component pulls in to draw itself, and the simulator shows all the components' pictures merged in a single window. | 🟢 |
| **19** | A component says **what** to draw, in metres and in meaning (*"this is a warning zone"*). The toolkit alone decides pixels and colour — which is what keeps the 2D BEV identical across components. | 🟢 |
| **20** | **It must not end at BEV** — video feed publishing, beside the BEV. (Driver view, lane/pedestrian markings, free space and semantic segmentation are out of #20 entirely — author's call: driver view 2026-08-31 (the chase camera is sufficient; driver view is not wanted), the other three 2026-08-30.) | 🟢 built and screenshotted (`WP-22`, 2026-08-30) — a real frame from `bsd_curve_r172_passby.mcap`'s `carla/chase_camera` decodes and draws live in `viz_player.exe`'s own "Camera" panel beside the BEV. Nothing left in this row to verify |
| **21** | Step, scrub and rewind freely — and stepping backwards **never invents** a state the software did not actually produce. | 🟢 |
| **22** | Click anything on screen and it tells you which signal, which tick, which file and which build produced it — and whether the software **published** that value or the drawing code **reconstructed** it. | 🟢 build answered since `F-8`; before it, this line was marked green while the build read `unknown` |

## F. How it is put together

| # | In one sentence | Status |
|---|---|---|
| **23** | **Skeleton in code, behaviour in configuration.** A new setup is a config file, not a code change. | 🟢 |
| **24** | Vehicle geometry, sensor poses and footprints come from the **project's own calibration**, never from constants inside the tool. Switching project must change the picture. | 🟡 |
| **25** | Anything the GUI can do, a **script can do headlessly** — same engine, for CI and for overnight batches. | 🟢 headless parity is real and proven (`GT-9`, `scripts/ci_gate.py` green by hand on both platforms). **"For CI"** names the engine property this row actually requires — one engine, scriptable, no GUI needed — not a hosted job watching it; hosted CI is out of scope by decision 2026-08-31 (`misc/START_HERE.md` Decision F). `.github/workflows/sim-ci.yml` exists, unmaintained and unobserved by that same decision, and was never the requirement — it was evidence this row no longer needs to wait for |

---

## What is NOT in scope

Recorded so it cannot quietly reappear.

- **No live co-simulation** — no running inside a foreign simulator's process. Foreign
  simulators arrive as *files* plus a mapping, never as a live connection.
- **No pass/fail KPI framework** — cut from v2 deliberately.
- **No expression language, scripting hook or user callable** inside any config file.
- **No second copy of anything** — one codec stack, one session model, one port
  resolver. (Today this is violated; see `memory.md`.)
- **No driver view.** Decided 2026-08-31, author's call: the chase camera
  (`#20`, shipped `WP-22`) is sufficient; a driver-view camera feed is not
  wanted. Recorded explicitly so this does not quietly reopen as a "gap"
  the next time someone reads `#20`'s row.

---

## The three questions this page exists to settle

**1. Is the concept right?** The lines above are the concept. If they are all
`AGREE`, then the design is not the problem and never was.

**2. Where is it?** **25 of 25 are green or amber, none red, none unverified.**
`#20` (everything past BEV) closed green 2026-08-31: video feed publishing
shipped (`WP-22`, 2026-08-30, a real frame decodes and draws live beside the
BEV), and all four of its other original items — driver view, lane/pedestrian
markings, free space, semantic segmentation — are out of scope entirely,
author's call (driver view 2026-08-31: the chase camera is sufficient and a
driver-view feed is not wanted; the other three, 2026-08-30). Nothing in `#20`
is left open to verify. `#25` closed green the same day for an unrelated
reason: headless parity (`GT-9`) was already real and proven, and hosted CI —
now explicitly out of scope — was only ever evidence for that, never the
requirement itself.

Two moved on 2026-08-28. **#8** — choose measured/simulated in the launcher —
went red → green and was the POC demo's last piece. **#5** went amber → red →
green in the same day: amber → red was a correction (its parser was real,
nothing called it, and a foreign-vocabulary recording fed the module nothing at
all, which is worse than "partly"), and red → green was the fix. Wiring it took
three legs, not the one the amber mark implied: the emitter, the engine's spec
parser, and a `Translator` that had existed for months with no caller anywhere.

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
