# Vantage — the player application

Status: **frozen 2026-07-28.** This document names the product, defines its two
workspaces, and specifies the window a developer actually sees. It is the
missing document: the architecture said *"the outcome is a player application"*
(`FR-SIM-70`) and then described a library.

Companions: [`sim_architecture.md`](sim_architecture.md) (master),
[`sim_visualization_spec.md`](sim_visualization_spec.md) (what is drawn),
[`sim_portability.md`](sim_portability.md) (Windows/Ubuntu),
[`sim_implementation_plan.md`](sim_implementation_plan.md) (build order).
Rules: root `.claude/rules/sim.md`, `R-SIM-16` above all.

---

## 1. Names

Three names were asked for: the master player, and its two faces — the
project-scale one and the developer-facing one.

| Name | What it is | Replaces the working name |
|---|---|---|
| **Vantage** | the application. One engine, one project file, one recording model. | — |
| **Bench** | the developer workspace: one run, permissive, poke at everything | `ltMB` |
| **Campaign** | the project workspace: many runs, locked, reportable | `ltMTS` |

### Why these

**Vantage** — a vantage point is the place you stand to see the whole scene.
It is one word, unambiguous in speech, has no meaning in the driving domain to
collide with, and does not describe a mechanism (so it does not go stale when
the mechanism changes). It is a *product* name, not a module name: the module
stays `modules/sim`, the package stays `adas-sim`, the CLI stays `sim`.

**Bench** — a workbench is where you put one thing and take it apart. Every
engineer already knows what a bench is for, and knows it is *theirs*. "Open it
on the bench" needs no glossary. It also correctly implies *temporary*: nothing
on a bench is a record of anything.

**Campaign** — a campaign is planned, large, and produces a result someone
reads. It carries the seriousness that "batch" does not, and the finiteness
that "fleet" does not. "Run the nightly campaign" says scale, repetition and
reporting in one word.

The pair is deliberately *plain English*. `R-SIM-16`'s whole argument is that
these are two faces of one thing, and a developer who has to learn two invented
words will assume they are two products.

### What each name is attached to, exactly

```
Vantage                        the application (GUI). Binary: vantage[.exe]
├── Bench      workspace       one recording / one live run, interactive
└── Campaign   workspace       many recordings, headless-equivalent, reported

sim                            the CLI. Unchanged, every verb as documented.
adas-sim                       the Python package. The library GT-9 protects.
```

**A workspace is a mode of one window, not a separate application.** Switching
is a toggle in the title bar (`Ctrl+Shift+M`), it does not reload the engine,
and **the open pipeline file survives the switch untouched** — which is
`R-SIM-16` made visible in one gesture. A developer who has just debugged a run
on the Bench presses one key and sees what a Campaign over 500 recordings of the
same pipeline would report.

### Naming rules that follow

| Rule | Consequence |
|---|---|
| The product name never appears in the package, module or import path | `import adas_sim`, never `import vantage`. A rename is a marketing change, not a refactor |
| No workspace name appears in `adas_sim/` outside `app/` | `Bench`/`Campaign` are UI arrangements. The engine has no idea which one is open — same discipline as `R-SIM-1` |
| The CLI never grows a `--bench` / `--campaign` flag | Workspaces are GUI arrangements over CLI verbs. `sim resim` is what Bench runs; `sim batch` is what Campaign runs |

Enforced by `UT-D5-4` (no workspace token outside `app/`) and `GT-9`.

---

## 2. The lean principle — stated as a testable rule

> *"UI and concept should be so lean that a developer looking at it understands
> what to do and does not get scared."*

That is not a decoration requirement; it is the requirement that decides whether
anyone uses this. It is made testable as three limits:

| Limit | Value | Why that number |
|---|---|---|
| **L-1** Controls visible at rest | **≤ 12** in the default Bench layout | More than a dozen affordances and the eye stops choosing and starts scanning |
| **L-2** Steps from launch to a moving picture | **≤ 3** (open file → press play) | Anything more and a developer writes a script instead |
| **L-3** Concepts before first use | **≤ 4** — *recording, pipeline, stage, layer* | Everything else (manifest, codec, bundle, provenance, origin tag) is discoverable **later**, never required first |

**L-3 is the one that matters most and is the easiest to lose.** This design set
contains ~40 concepts. A first-time user must meet four. The rest appear only
when the user asks a question that needs them — which is a UI obligation, not a
documentation one:

- provenance and origin tags appear in the HUD **only when something is not
  `simulated`** — the normal case shows nothing;
- the config bundle appears **only when it is missing or mismatched**;
- codec capabilities appear **only** in the error that a degrade produces;
- `impl:`/`legacy:` appear only in the pipeline panel's expert row, collapsed.

> **The design rule:** *a concept earns screen space by being wrong.* When
> everything is normal, the window shows a picture, a timeline and a layer list.

Enforced by `MC-5` (a named manual check with a stopwatch and a real newcomer)
and by `GT-8`'s ten-minute number.

### What "not scared" means concretely

The failure being designed against is a first launch that presents a
configuration tree, a component catalogue, a properties grid and an empty
viewport with a red status line. Three specific bans:

1. **No empty-state configuration.** Vantage never opens onto a form. It opens
   onto either a recording or a start page with recent files.
2. **No naked identifiers.** `Unknown MO`-class messages are banned. Every
   failure names what was expected, what was found, and where it looked
   (`§5.14`'s message contract).
3. **No modal setup.** Nothing must be configured before something is visible.
   A pipeline with a missing stage still renders the stages that resolve, with
   the broken one badged — degrade visibly, never refuse to draw.

---

## 3. The window

One window. Four regions. Both workspaces use the same shell; they differ in
which docks are present and what the centre shows.

```
┌───────────────────────────────────────────────────────────────────────┐
│ Vantage — sensor_fusion_urban.mcap                    [Bench|Campaign]│  title + workspace toggle
├───────────────────────────────────────────────────────────────────────┤
│ ▶ ‖  |◀ ▶|  ⏭50 ⏭100 ⏭200 ⏭…   1×    ⟲fit  ⌖follow      ⚙  ?        │  transport + view  (L-1: 12)
├────────────┬────────────────────────────────────────────┬─────────────┤
│  Pipeline  │                                            │   Layers    │
│            │              CENTRE                        │             │
│  ○ rsp     │        (BEV / camera / plot grid)          │  ☑ ego      │
│  ● percep  │                                            │  ☑ world    │
│  ● df      │                                            │  ☐ debug    │
│            │                                            │             │
├────────────┴────────────────────────────────────────────┴─────────────┤
│ ◀━━━━━━━━━━━━━━━━━━━━━━━━━●━━━━━━━┫head┃░░░░░░░░░░░░░░░░░░░░░░░━━━━▶ │  timeline + head
├───────────────────────────────────────────────────────────────────────┤
│ tick 412 · t=20.6s · project=base · bundle ✓ · 3 stages · 18 layers   │  status
└───────────────────────────────────────────────────────────────────────┘
```

Region contracts:

| Region | Contract |
|---|---|
| **Transport** | `R-SIM-17`. The head is drawn; ahead of it is visibly empty, not grey |
| **Pipeline dock** | one row per stage, `mode` toggle, severed-chain auto-close (`R-SIM-10`). Expert row (`impl:`, overrides) collapsed by default |
| **Centre** | a panel grid. One BEV by default; camera, plots and tables are peers, not children (viz §11.1) |
| **Layers dock** | derived entirely from the Scene. Nothing registers; a layer exists by being emitted (viz §6) |
| **Timeline** | events, expectation windows, bookmarks, and the head marker |
| **Status** | the four things that are always true: where you are, what config, what ran, what is drawn |

**Everything else is a dock that is closed by default**: inspector, signals,
log, manifest, diff. `Ctrl+K` opens a command palette listing every one — which
is how the tool stays lean without hiding features. A palette is the single
highest-value affordance for L-1: it removes the pressure to surface everything.

---

## 4. Bench — the developer workspace

**Purpose:** one run, understood completely.

Everything permissive is here and nowhere else:

- **Per-port overrides live in the pipeline dock** (`R-SIM-15`). Right-click a
  port → `const` / `hold` / `offset` / `scale`. An overridden port turns amber
  in every view it appears in, so a forgotten override cannot silently explain
  a result.
- **Mode toggles are immediate** — flipping a stage re-runs from the head, and
  the severed-chain auto-close happens visibly with a one-line undo bar.
- **`sim probe` is a panel**, not just a verb: drop a library on the window and
  Vantage prints its ports, types and schemas. This is the **day-one screen**
  for a new component (`arch §5.16.1`) and the answer to *"what do I do first?"*
- **The Python console is a dock** — `adas_sim` already loaded, `session`,
  `pipeline` and `scene` bound. This is `R-SIM-16`'s "library first" made
  reachable without leaving the window, and it is the pressure valve that stops
  someone forking the tool for one experiment.

**Bench never writes a report and never claims provenance.** A Bench run is
scratch by default; saving one is explicit and produces an ordinary recording
with its origin tags intact.

---

## 5. Campaign — the project workspace

**Purpose:** many runs, reported, reproducible by someone else.

```
┌───────────────────────────────────────────────────────────────────────┐
│ Vantage — nightly_regression                          [Bench|Campaign]│
├───────────────────────────────────────────────────────────────────────┤
│  ▶ Run   ⏸   ⟲ Re-run failures    │  312/500 · 18 failed · 6m12s left │
├────────────────────────┬──────────────────────────────────────────────┤
│  Recordings   (500)    │  Results                                     │
│  ✓ urban_001           │  ┌────────────────────────────────────────┐  │
│  ✓ urban_002           │  │  scenario   expect        got    Δ     │  │
│  ✗ urban_003    ◀──────┼──│  brake_ttc  ≤1.4s within  1.62s  +0.22 │  │
│  ✓ urban_004           │  └────────────────────────────────────────┘  │
│  …                     │  [ Open on Bench ]  ← one click, same file   │
├────────────────────────┴──────────────────────────────────────────────┤
│ pipeline: urban_l1.yaml · project base · 3 builds · bundle a3f9… ✓    │
└───────────────────────────────────────────────────────────────────────┘
```

Three properties, each load-bearing:

1. **Input is a pipeline file plus a recording set** — the *same* pipeline file
   Bench had open. Not a converted one, not an exported one. `ST-D7-3` is the
   test that keeps this true, and it is the single most important test in the
   plan for `R-SIM-16`.
2. **`Open on Bench` on any row** loads that one recording, that one pipeline,
   at the failing tick, in the interactive workspace. The round trip
   *Campaign → Bench → fix → Campaign* never passes through a file conversion
   or a re-authoring step. This is the loop the whole two-face design exists to
   make cheap.
3. **A Campaign is exactly `sim batch`.** The GUI builds the same invocation and
   shows it, copyable. Anything Campaign can do, CI can do, because it is the
   same command — `UT-D3-4` generalised.

Campaign is **locked**: no per-port overrides, no live mode toggles, no Python
console. Not because they are dangerous, but because a report whose inputs were
poked by hand is not a report. Editing anything offers to open it on the Bench.

---

## 6. First run — the three screens a new user meets

**L-2 says three steps.** These are them.

**Screen 1 — Start.** Recent files, `Open recording…`, `Probe a library…`, and
three sample pipelines that ship with the tool. No configuration. No settings
prompt. No project selection — the recording carries its bundle (`R-SIM-3a`).

**Screen 2 — Opened.** The BEV, populated, at tick 0, paused, with the layer
list filled in from what the Scene actually contains. **The user has configured
nothing.** If the recording carries stage outputs, the pipeline dock shows them
as `measured` and the picture is already complete.

**Screen 3 — Moving.** Press play, or press `⏭100`. That is the whole of the
first experience.

Everything after that is a question the user chose to ask: *what if this stage
were simulated?* (one toggle), *what does this port contain?* (click it), *why
does it differ from the recording?* (the free comparison, already computed).

> **The onboarding test (`MC-5`):** a developer who has never seen the tool
> reaches Screen 3 in under two minutes with no instructions, and can then
> explain, unprompted, what `measured` and `simulate` mean on the pipeline dock.
> If they cannot, the pipeline dock is wrong — not the developer.

---

## 7. What ships

Two delivery forms, one codebase (`arch §5.15`), now with the names attached:

| Form | Contains | For |
|---|---|---|
| `adas-sim` (Conan/pip package) | the library + `sim` CLI | developers with a checkout, and CI |
| `vantage` (frozen binary) | the above + the GUI, no Python needed | anyone; the audit/report audience |

The frozen binary keeps an **external plug-in path** so a component's layer
providers load without rebuilding it (`ST-D5-3`), and declares its compatibility
statement on `--version` (`NR-SIM-9`). Windows first; Ubuntu is a second
packaging target over the same codebase, and everything in
[`sim_portability.md`](sim_portability.md) exists so that it stays a *packaging*
target.

---

## 8. What is deliberately not in Vantage

Recorded so it is a decision, not an omission:

| Not included | Why | Would arrive as |
|---|---|---|
| A scenario **editor** | Scenarios are YAML in the component's repo, reviewed like code | a schema-aware text panel, if asked |
| A calibration editor | `R-VAR-4` — calibration is authored in `projects/`, and a GUI would become a second authoring home | sweeps already cover the experiment case (`§5.6`) |
| A 3D viewport | The Scene already exports to a 3D-capable viewer (viz §11.3) | a renderer, not an architecture change |
| A generic signal explorer over every topic | Large; nothing asks for it yet (`arch §5.16.3`) | a panel |
| Live human driving input | Every run is open-loop by choice (`FR-SIM-51`, parked) | a `stub:` stage plus a closed-loop decision |
| Multi-user / server mode | No requirement; a recording is already the sharing unit | — |

---

## 9. Traceability

| Requirement | Where answered here |
|---|---|
| `FR-SIM-70` — a player application | §3, §7 |
| `FR-SIM-46` — one tool, two faces | §1, §4, §5 |
| `FR-SIM-47` — lean, non-frightening UI | §2, §6 |
| `FR-SIM-17` — step-wise transport | §3 (transport row), `R-SIM-17` |
| `FR-SIM-15` — component ships a workspace | §3 (docks), viz §13b |
| `NR-SIM-21` — mass scale | §5 |
| `NR-SIM-9` — compatibility statement | §7 |
