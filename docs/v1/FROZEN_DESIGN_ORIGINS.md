# Frozen Design Origins

**Extracted 2026-08-31 (Step 7 document-set shrink), per
`misc/STEP_7_SHRINK_PLAN.md` §5.** This file holds exactly the fragments of
two now-retired `docs/v1/` documents that real, live external readers cite by
content rather than by index — `df`'s and `viz`'s own requirement/concept
documents, and one live C++ header. Everything else in
`sim_visualization_spec.md` and `sim_player.md` (viewport, transport, layer
panel, keymap, feature checklist, and the rest) had no live external reader
and was retired as evidence only — full text at
`git show 1e2bb5b:docs/v1/sim_visualization_spec.md` and
`git show 1e2bb5b:docs/v1/sim_player.md`.

Each fragment below keeps its original section number and heading.

---

## From `sim_visualization_spec.md` §2 — The Scene primitive catalogue

*(extracted from `sim_visualization_spec.md`, retired 2026-08-31, full text
at `1e2bb5b`)*

Closed set. Adding a primitive is a framework change and needs a reason; a
layer provider that wants something new composes it from these.

| Prim | Fields (all metres / radians) | Typical use |
|---|---|---|
| `Polyline` | `points[]`, `closed=False`, `width_px` | lane markings, trajectories, corridor edges |
| `Polygon` | `points[]`, `filled`, `hatch` | zone, free space, occlusion region |
| `Box` | `cx, cy, length, width, yaw`, `height=None` | ego body, object footprint, sensor housing |
| `Circle` | `cx, cy, r` | range rings, uncertainty radius |
| `Ellipse` | `cx, cy, a, b, yaw` | covariance / uncertainty |
| `Points` | `xy[]`, `marker` | radar detections, sampled grid |
| `Arrow` | `x, y, dx, dy` | velocity, acceleration, axis triad |
| `Text` | `x, y, text, anchor, offset_px` | labels, values |
| `Grid` | `spacing_m, extent` | distance grid |
| `Heatmap` | `x0, y0, dx, dy, values[][]` | η coverage, occupancy, cost |
| `Image` | `frame="image:<cam>"`, `data`, `format` | camera frame (renderer-specific) |

Every prim also carries:

```python
frame:   str          # "ego" (default) | "world" | "sensor:<id>" | "image:<cam>"
style:   str          # semantic token — never a colour
pick_id: str | None   # selectable; the owning layer resolves it to inspector fields
z:       int          # within-layer ordering
alpha:   float = 1.0
```

**Deliberate design choices:**

- **`width_px` is the one pixel quantity a prim may carry.** Line weight is a
  legibility property, not a physical one — a 0.05 m-wide line is invisible at
  1 px/m and a slab at 50 px/m. Everything else is metres.
- **`offset_px` on `Text` for the same reason** — a label must sit a constant
  distance from its anchor regardless of zoom.
- **`Box` has an optional `height`.** Ignored by the BEV renderer, used by the
  image renderer to build a 3D box for projection, and by Foxglove's 3D panel.
  One primitive, three consumers — this is the 2.5D compromise.
- **`Heatmap` exists because BSD needs it** — one array the renderer blits,
  rather than hundreds of per-cell rectangle draws, which is both faster and
  correct at any zoom.

---

## From `sim_visualization_spec.md` §3 — Style tokens and themes

*(extracted from `sim_visualization_spec.md`, retired 2026-08-31, full text
at `1e2bb5b`)*

### 3.1 The rule

A layer provider writes `style="zone.entry"`. It never writes a colour, a line
style, a hatch, a dash pattern or an alpha. One theme table per output medium
resolves tokens to appearance.

### 3.2 Token taxonomy

Tokens are namespaced. A component's layer provider may only use tokens in the
framework namespaces plus its own.

```
frame.*      origin, axis, grid, grid_label, scale_legend
ego.*        body, body_edge, rear_axle, wheel, mirror
object.*     default, selected, ghost, assumed_geometry, label
             classification.{car,truck,two_wheeler,pedestrian,unknown}
status.*     good, warning, serious, critical, inactive, unknown
sensor.*     fov, range_ring, blind, housing
truth.*      body, track, trace          (ground truth — always distinguishable)
measure.*    ruler, cursor, annotation
<fn>.*       aeb.corridor, bsd.zone.entry, bsd.zone.exit, lca.zone, …
```

Four rules on top of the taxonomy:

1. **`status.*` is reserved.** `good` / `warning` / `serious` / `critical` /
   `inactive` are *state* colours and are never reused as "the fourth series"
   or "another function's colour". A warning therefore looks the same
   whichever function raised it.
2. **Never colour-alone.** Every `status.*` mark ships with a shape or a label
   as well.
3. **Colour follows the entity, not its rank.** An object's colour must not
   change because another object left the scene.
4. **Dark mode is a selected theme, not an inverted one.** The interactive
   viewer's dark theme and the print theme are two independently chosen tables
   over the same tokens, each validated against its own surface.

### 3.3 Themes shipped

| Theme | Surface | Used by |
|---|---|---|
| `dark` | near-black | interactive viewer (default) |
| `light` | white | interactive viewer, screenshots for slides |
| `print` | white, higher contrast, hatches on every fill | matplotlib figure renderer, requirement documents |
| `forced` | high-contrast, texture-first | accessibility / forced-colors |

### 3.4 Acceptance criterion for the token table

The token table is not frozen by taste. Before it is called done:

- every categorical set (object classifications, function namespaces, timeline
  signal lanes) is run through the palette validator for the lightness band,
  chroma floor, adjacent-pair colour-vision-deficiency separation, the
  normal-vision floor and contrast, in **both** `dark` and `light` surfaces;
- any pair that lands in the 6–8 ΔE floor band is legal only because it already
  carries a secondary encoding (hatch/marker/label), named in the table, not
  assumed;
- a contrast warning obligates a visible label, and the label is added.

This is a computable check, so it is computed, not argued.

---

## From `sim_player.md` §1 — Names

*(extracted from `sim_player.md`, retired 2026-08-31, full text at `1e2bb5b`)*

Three names were asked for: the master player, and its two faces — the
project-scale one and the developer-facing one.

| Name | What it is | Replaces the working name |
|---|---|---|
| **Vantage** | the application. One engine, one project file, one recording model. | — |
| **Bench** | the developer workspace: one run, permissive, poke at everything | *(internal working name)* |
| **Campaign** | the project workspace: many runs, locked, reportable | *(internal working name)* |

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

---

## From `sim_player.md` §10 — What shipped — reconciled 2026-08-06 (audit run 3)

*(extracted from `sim_player.md`, retired 2026-08-31, full text at `1e2bb5b`
— historical record of the Python `app/` implementation, itself since
deleted by `7d4c626` "SM-12: delete the Python scene/render/player
implementation", Decision B, 2026-08-29. Kept for the texture of what was
promised vs. shipped at the time; not a description of any code that exists
today.)*

**This section exists because everything above it was frozen on 2026-07-28 and
the application it specifies was built on 2026-08-06, and nothing in between
brought the two together**. `S-D8` landed the shell, the workspaces,
the start page, the palette and the Campaign widget. Every name S-D8 created
(`VantageWindow`, `StartPage`, `CampaignWidget`, `ConsolePanel`, `ProbePanel`,
`CommandPalette`) appeared nowhere in the design set until this section.

The point of the table is not the ticks. It is the two rows that are **not**
ticked, which nobody could have found from the plan alone, because the plan
records what was *built* and this document records what was *promised*.

| §  | Promised | Shipped | Where |
|---|---|---|---|
| §1 | Vantage / Bench / Campaign as one window, `Ctrl+Shift+M` toggles | ✅ | `app/shell/window.py`, `app/shell/workspace.py` |
| §1 | No workspace token in `adas_sim/` outside `app/` | ✅ mechanised | `scripts/check_invariants.py::check_ut_d8_9` |
| §2 | `L-1` ≤12 controls · `L-2` ≤3 steps · `L-3` ≤4 concepts | ✅ measured 8 / 2 / asserted | `UT-D8-5`, `ST-D8-2`, `UT-D8-6` |
| §2 | `MC-5` — a real newcomer, a stopwatch | ❌ **never run** | `S-D8`'s one open gate item. See `FR-SIM-47` |
| §3 | Transport · pipeline dock · centre · layers dock · timeline · status | ✅ (all `S-B3`/`S-D3`'s, reused unmodified) | `render/viewer.py` |
| §3 | `Ctrl+K` palette over every action incl. closed docks | ✅ | `app/shell/palette.py` |
| §3 | Docks closed by default: inspector, signals, log, manifest, diff | ⚠️ **partial** — `inspector` and `evidence` exist; `signals`, `log`, `manifest` and `diff` were never built and are not scheduled by any stage | `render/viewer.py` |
| §4 | Per-port overrides, amber badge, mode toggle, severed-chain undo | ✅ (`S-D6`'s, confirmed present) | `view/pipeline_panel.py` |
| §4 | **`sim probe` is a panel — the day-one screen** | ❌ **built and unreachable** — see below | `app/panels/probe.py` |
| §4 | **The Python console is a dock** | ❌ **built and unreachable** — see below | `app/panels/console.py` |
| §5 | Campaign: recording list, results table, real `run_batch` off the GUI thread | ✅ | `app/shell/campaign.py` |
| §5 | `Open on Bench` — same recording, same pipeline | ⚠️ at tick 0, not the failing tick (`S-D8` states this) | `VantageWindow._on_open_on_bench_requested` |
| §5 | Copyable equivalent `sim batch` invocation | ✅ | `campaign.batch_invocation_text` |
| §5 | Campaign locked: no overrides, no mode toggles, no console | ✅ **by omission** — see the note below | `app/shell/campaign.py` |
| §5 | *"Editing anything offers to open it on the Bench"* | ❌ **not built, not scheduled** | — |
| §6 | Screen 1 (start page, no form) → Screen 2 (opened) → Screen 3 (moving) | ✅ | `app/shell/startpage.py` |
| §6 | Three sample pipelines that ship with the tool | ⚠️ mechanism real, **content empty** (needs a compiled demo component) | `StartPage`'s own docstring |
| §7 | Frozen `vantage` binary with an external plug-in path | ⚠️ `S-D5`, 3 boxes partial | `S-D5` |

### The two panels that exist and are not in the product (`AR-45`, fixed 2026-08-06)

**Fixed, fix queue row 5.** `VantageWindow` now adds `ProbePanel` to its
stacked widget and switches to it when `probe_requested` fires; it constructs
one `ConsolePanel` and docks it onto Bench, rebinding `session`/`pipeline` off
a new `MainWindow.session_ready` signal so the console is never stale across a
reopened recording. `scene` stays honestly unbound — no single "current scene"
object exists on `MainWindow` to bind live yet, a separate, smaller fix.
Verified by two new tests in `tests/system/test_d8_window.py`. The account
below is kept as the record of what was wrong and why the existing tests
missed it.

Both were **built, documented, and covered by passing system tests**, and
**neither was reachable by a user**:

- **`ConsolePanel`** is never constructed anywhere in `app/`. `window.py` does
  not import it. Its only two references outside its own module are its own
  test file.
- **`ProbePanel`** is constructed by `VantageWindow` and wired
  (`start_page.probe_requested → probe_panel.probe`) — and then never added to
  the stack, never docked, never shown. Choosing *"Probe a Library…"* on the
  start page loads the library and renders its port tree into a widget with no
  parent that is never displayed.

**Why the tests did not catch it.** `test_d8_probe_panel.py` and
`test_d8_console_panel.py` both instantiate the panel directly and assert it
behaves. That is a correct unit-level claim and it is not the claim `S-D8`'s
checkbox makes. The gap between *"the panel works"* and *"the application
contains the panel"* matters more here than usual because of what these two
panels are for: §4 calls the probe panel **"the day-one screen for a new
component and the answer to *what do I do first?*"**, and the console **"the
pressure valve that stops someone forking the tool for one experiment"** — an
`R-SIM-16` obligation, not a convenience.

**It also quietly flatters `L-1`.** `UT-D8-5` counts 8 controls against a budget
of 12; two docks that are not in the window contribute none. The limit is met
partly because the features are absent.

Owned by `S-D8`; both boxes re-closed 2026-08-06 (`AR-45`, fix queue row 5 —
functional source, so not fixed by the audit itself, which is documents-only).

### On Campaign's lock — one mechanism, not two (`AR-48`, fixed 2026-08-06)

**Fixed, fix queue row 6, the safe default.** Locked-by-omission is kept as the
real mechanism; `Workspace.require()`'s docstring no longer claims call sites it
does not have, and `UT-D8-2` is repointed at a new mechanical test
(`test_d8_campaign.py::test_ut_d8_2_locked_by_omission_no_mode_toggle_and_no_console`)
proving `CampaignWidget`'s widget tree carries no mode-toggle radio button and
no console-named widget. `require()`'s own tests stay — its correctness is real,
just unused in production — and the alternative (wiring real call sites into
`CampaignWidget`) was not taken, since that is a design change this row was not
asked to make. The account below is kept as the record of the original finding.

`app/shell/workspace.py` defines `Workspace.require(action, allowed=)` raising
`WorkspacePermissionError`, and its docstring called it *"the one call site every
permission-gated action routes through"*. **It had zero call sites in `src/`.**
`VantageWindow.current_workspace` — the only thing that could reach it — is a
property nothing calls.

The lock is nevertheless real, and `S-D8`'s own checkbox says how: *"locked by
omission, not by a disabled control — `CampaignWidget` never constructs an
override affordance, a mode toggle or a console at all."* **That is the stronger
mechanism and it is the one to keep** — there is nothing to grey out, so there
is nothing to bypass.

So the finding was not "Campaign is unlocked". It was that **two mechanisms were
built for one job and the dead one was the one that was tested**: `UT-D8-2`
proved the wording of an exception no code path can raise. Either `require()`
acquires its call sites or its docstring stops claiming them; `UT-D8-2` follows
whichever survives — the docstring's claim was dropped, `UT-D8-2` now follows
the omission mechanism.
