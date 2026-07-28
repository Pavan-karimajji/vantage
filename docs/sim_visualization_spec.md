# Visualization Spec — the 2D BEV viewer and its renderers

Status: **concept, frozen for review 2026-07-27.** Part of the simulation
rework — see [sim_architecture.md](sim_architecture.md). This document owns
L3/L4/L5: the Scene primitive catalogue, the style/theme system, the complete
BEV feature set, the three renderers, and the camera/perception panel.

Supersedes the forward direction of [df_carla_viz_plan.md](../../../docs/df_carla_viz_plan.md),
whose §4 canvas semantics, §5.1a–c additions and §6 parked list are all either
carried forward or explicitly scheduled below.

---

## 1. Scope and the two rules

**A layer provider produces geometry in metres. A renderer produces pixels.
Neither knows the other.**

**The viewer never talks to a world model, a DLL or a file. It renders a
`Session`.** That is its only input (`sim_architecture.md` §5.12). A Session
comes from our own runner, from a recording in any format, or from what an
embedded CarMaker run wrote — and the viewer cannot tell which. So the
visualization is **identical** across CARLA, CarMaker, mcap, a real vehicle
measurement, and anything not yet invented; nothing in this document mentions a
world model or a file format, and nothing in it ever should.

The one honest limitation: **live** viewing requires that we own the loop —
true for CARLA and for resim. A simulator that owns its own loop has its own
live view, and ours runs afterwards from its recording.

Everything in this document is downstream of that. It is what lets one Scene
drive an interactive window, a print figure and a shared recording; it is what
lets `df` add LCA's visualization without touching a renderer; and it is what
makes a requirement figure and a live run provably the same picture.

Non-goals, restated from `sim_architecture.md` §11: no 3D scene graph, no
closed-loop actuation, no HIL, no analytics dashboard.

---

## 2. The Scene primitive catalogue

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
  distance from its anchor regardless of zoom. This is what `_draw_label`'s
  `y_offset_px=-14` already does; it is promoted to the model rather than left
  in the renderer.
- **`Box` has an optional `height`.** Ignored by the BEV renderer, used by the
  image renderer to build a 3D box for projection, and by Foxglove's 3D panel.
  One primitive, three consumers — this is the 2.5D compromise.
- **`Heatmap` exists because BSD needs it.** `viz.py` currently draws the
  unobservable region as a nested Python loop emitting one filled rectangle per
  0.5 m cell — hundreds of `cv2.rectangle` calls per tick. As a `Heatmap` prim
  it becomes one array the renderer blits, which is both faster and correct at
  any zoom.

---

## 3. Style tokens and themes

### 3.1 The rule

A layer provider writes `style="zone.entry"`. It never writes a colour, a line
style, a hatch, a dash pattern or an alpha. One theme table per output medium
resolves tokens to appearance.

This is not new to the repo — `bsdviz/palette.py`'s own header already states
the principle: *"Colour is semantic and never colour-only — every colour is
paired with a hatch, marker or label."* This spec elevates it from one library's
convention to the framework contract, and extends it across renderers.

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

Four rules on top of the taxonomy, taken directly from the project's
visualization method:

1. **`status.*` is reserved.** `good` / `warning` / `serious` / `critical` /
   `inactive` are *state* colours and are never reused as "the fourth series"
   or "another function's colour". BSD's `OFF` / `NORMAL` / `BLINKING` and AEB's
   pre-warning both map onto `status.*`; a warning therefore looks the same
   whichever function raised it, which is the point.
2. **Never colour-alone.** Every `status.*` mark ships with a shape or a label
   as well. Today's BSD warning band is a filled circle whose *only* difference
   between OFF and BLINKING is hue — it already carries a text label beside it,
   which is what makes it legal; that pairing becomes mandatory rather than
   incidental.
3. **Colour follows the entity, not its rank.** Object 3's colour must not
   change because objects 1 and 2 left the scene. Today's viewer is accidentally
   correct here (all objects share one colour); the rule is written down before
   per-object colouring is ever added.
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

`bsdviz`'s current palette is the seed of `print`; `viz.py`'s BGR constants are
the seed of `dark`. Neither survives as a table of literals scattered through
drawing code.

### 3.4 Acceptance criterion for the token table

The token table is not frozen by taste. Before Phase A3 is called done:

- every categorical set (object classifications, function namespaces, timeline
  signal lanes) is run through the palette validator for the lightness band,
  chroma floor, adjacent-pair colour-vision-deficiency separation, the
  normal-vision floor and contrast, in **both** `dark` and `light` surfaces;
- any pair that lands in the 6–8 ΔE floor band is legal only because it already
  carries a secondary encoding (hatch/marker/label) — and that encoding is named
  in the table, not assumed;
- a contrast warning obligates a visible label, and the label is added.

This is a computable check, so it is computed, not argued.

---

## 4. Viewport

Replaces D6 (`CANVAS_WIDTH_PX`/`PX_PER_METER`/`ORIGIN_PX` constants).

### 4.1 State

```python
@dataclass
class Viewport:
    centre_m: tuple[float, float]   # what sits at the middle of the canvas
    scale_px_per_m: float
    rotation_rad: float             # 0 = +x up
    follow: FollowMode
    size_px: tuple[int, int]        # from the widget, not a constant
```

### 4.2 Follow modes

| Mode | Behaviour | For |
|---|---|---|
| `ego_forward` | ego fixed on screen, +x up | today's behaviour; forward functions |
| `ego_heading` | ego fixed, canvas rotates with ego yaw | curve scenarios — the zone stops swinging |
| `world` | camera fixed in world frame, ego moves through it, trail drawn | lane-change and merge geometry; trajectory review |
| `locked:<pick_id>` | a selected object holds the centre | following one target through a pass-by |

### 4.3 Presets

Named viewports, declared as **data** so a function ships its own without a code
change — the same discovery principle as layer providers:

```yaml
# modules/df/sim/viewpoints.yaml
forward:      {centre: [40, 0],   span_m: 120, follow: ego_forward}
rear:         {centre: [-25, 0],  span_m:  70, follow: ego_forward}
blindspot_l:  {centre: [-4, 4],   span_m:  18, follow: ego_heading}
blindspot_r:  {centre: [-4, -4],  span_m:  18, follow: ego_heading}
wide:         {centre: [0, 0],    span_m: 200, follow: world}
```

`blindspot_*` is the concrete fix for the observation in D6 that the BSD zone
currently occupies the bottom strip of a canvas built for AEB.

### 4.4 Controls

- drag to pan; wheel to zoom about the cursor (not about the centre — zooming
  about the centre is the single most common viewport annoyance);
- `F` fit to visible content; `1`…`9` jump to preset *n*; `0` reset;
- `R` cycle follow mode;
- zoom is clamped to `[0.5, 200] px/m` and the scale legend always states the
  current value, so a screenshot is self-describing.

---

## 5. Time transport — the "scrolling" requirement

Enabled by the two-pass Session (`sim_architecture.md` §6.4). All of this is
currently absent; `--step` is forward-only by construction.

Everything here is defined against **the head** — the furthest tick computed
(`R-SIM-17`, arch §6.4). Behind the head the Session is immutable data; at the
head, execution advances. The toolbar is split accordingly, and the split is
visible rather than implied.

| Control | Behaviour | Where |
|---|---|---|
| **Scrub bar** | full-width, one pixel ≈ one or more ticks; drag to seek anywhere, forwards or backwards, instantly | behind head |
| Play / pause | `Space` | both |
| Step forward | `→` one tick; `Shift`+`→` ten | both (executes at head) |
| **Step backward** | `←` one tick — **leaves execution mode, enters review** (below) | behind head |
| **Advance N** | run forward `50` / `100` / `200` / custom ticks as one job, with progress and **cancel** | at head |
| Speed | `0.1×` … `8×`, plus "as fast as it renders" | both |
| Loop | mark in/out on the scrub bar, `L` to loop the interval | behind head |
| Jump to event | `[` / `]` to the previous/next event marker (§7) | behind head |
| Goto | type a time or a tick index | behind head; ahead of head = advance-N to it |
| Live tail | during a live sim run the bar grows; releasing the head resumes tailing | at head |

Two properties that matter and are easy to lose:

- **Seeking never re-executes the SUT.** A seek is an array index plus a
  re-render, so it is instant even at tick 1200.
- **Toggling a layer or changing theme re-renders without re-executing**, for
  the same reason. This is what makes the layer panel feel like a real tool
  rather than a re-run.

### 5.1 Backward is not the mirror of forward

Forward calls `exec()`. Backward would have to **undo** it, and the SUT holds
state the ABI does not expose. There is no inverse `exec()`, so stepping
backward **stops execution and enters review** — everything already computed
stays fully scrubbable, and nothing new is computed until the user returns to
the head.

The head is drawn on the scrub bar as a distinct marker, and the region ahead of
it is visibly empty rather than merely grey — "not computed yet" and "computed,
value zero" must never look alike.

Resuming forward from behind the head presents exactly two buttons, both named:

| Choice | Meaning | Available |
|---|---|---|
| **Skip to head** | resume where execution actually is | always |
| **Recompute from 0** | re-run to this tick, exactly | deterministic resim only (`R-SIM-5`) |

In a live **sim** the second is greyed with its reason on hover — the world is
gone, so it cannot be re-driven. Silently continuing from a rewound position is
never offered: it would feed tick 400's stimulus to tick 900's internal state
and produce a plausible-looking fabricated run.

### 5.2 Advance-N is a job, not a loop

`50` / `100` / `200` / custom is the coarse-jump control the reference console
puts on its toolbar, and it is what makes a 1200-tick recording navigable. It
runs as **one cancellable job**: a progress indicator, a live tick counter, and
`Esc` to stop at whatever tick has been reached — which then becomes the head.
An expectation failing mid-advance (§7) does not abort it; it drops a marker and
the run continues, because "show me the next 200 ticks" means exactly that.

---

## 6. Layers panel

Directly the reference measurement stack's proven model — its draw API's entry
point is literally `DrawStartNewGroup(group, subgroup, active_on_startup)`.

- A tree, grouped by `Layer.group`: `ego`, `world`, `ground_truth`, `aeb`,
  `bsd`, `perception`, `measure`.
- Per-layer checkbox; per-group checkbox tri-states.
- `Layer.default_on` decides the initial state; the user's overrides persist per
  project + pipeline, so opening a BSD recording restores the BSD layers.
- **Verbosity levels.** A group may declare layers at level 1/2/3 (the reference
  stack's own `VISU_LEVEL1..3` idea): level 1 is what you always want, level 3
  is internal debug. One control raises the level for a whole group instead of
  ticking fifteen boxes.
- **Solo / mute** on a group (`Alt`+click), for isolating one function's view.
- Search box, because seven functions × several layers each will get long.

The panel is entirely derived from the Scene. No layer is registered anywhere
except by existing.

---

## 7. Selection, inspection, timeline, plots

### 7.1 Selection

`Prim.pick_id` makes selection general. Today only object boxes and the ego box
are hit-testable, via `_hit_test_box` re-deriving the same geometry the drawing
code used — a duplication that is a bug waiting to happen. In the Scene model
the renderer hit-tests the prims it actually drew, so the two cannot disagree.

- click to select; `Ctrl`+click to multi-select; `Esc` to clear;
- selected prims get `object.selected` styling plus a halo;
- selection **persists across ticks by `pick_id`**, so stepping through a run
  keeps the same target selected — which today's popups already do via their
  `("object", ui_id)` key, and which is the right behaviour to keep.

### 7.2 Inspector

Docked panel, not a floating window per entity. Today's independent tkinter
popups solved a real problem (two entities visible at once) with the tool
available; a dock with a pinned list solves it without a second event loop.

- shows the selected entity's fields, resolved by asking its **layer provider**
  — so `df` decides what an AEB-critical object shows and `perception-core`
  decides what a track shows, without a framework change;
- fields are declared, not dumped: the two rejected iterations in
  `../../../docs/df_carla_viz_plan.md` §5.1c (full recursive proto dump) established that a
  ~42-field dump is worse than five chosen fields. That finding is carried
  forward as a rule: **a layer provider declares an ordered field list**, and a
  "show all fields" toggle exists for when you really need it;
- values update live as the tick changes, including while scrubbing;
- pin an entity to keep it in the panel after deselecting;
- copy-as-text for pasting into a ticket.

### 7.3 Timeline / signal strip

A synced strip below the BEV. Entirely new, and the single biggest usability
gain after scrubbing.

- **Signal lanes.** Numeric signals over time (TTC, `f_dist_y` of the selected
  object, ego speed, `observable_fraction`). One scale per lane — **never two
  y-scales in one lane**; two signals of different magnitude get two lanes.
- **State lanes.** Categorical/state signals as coloured bands with text
  (`bsd.left.warning` OFF→NORMAL→BLINKING, `bsd.scenario` ToS/SoT/MergeIn/
  EgoExit, `CompState`). Bands carry their label, never colour alone.
- **Event markers.** Vertical ticks at transitions — exactly the edges
  `carla_bridge.py` already detects and prints (`*** t=7.320s bsd_left warning
  OFF -> NORMAL`). Those prints become markers instead of scrollback.
- **Expectation markers** from the scenario's `expect:` block
  ([sim_scenarios_and_expectations.md](sim_scenarios_and_expectations.md)):
  expected windows drawn as translucent spans, so a pass/fail is visible rather
  than computed.
- Click anywhere in the strip to seek; the playhead is shared with the scrub bar.
- Any signal in the §7.4 address space can be lane'd; a function ships its own
  computed ones with `@signal`.

A legend is present whenever a lane carries two or more series; up to four
series are also direct-labelled at their last point, so identity never depends
on colour alone.

---

### 7.4 Plots — signals as a first-class, pluggable panel

The timeline strip (§7.3) is a *transport companion*: time-indexed, always
under the BEV, built for "when did this happen". It is **not** an analysis
surface. Plotting one signal against another — `dist_y` vs `dist_x` for a
trajectory, TTC vs closing speed, warning state vs ego speed — is a different
job and gets its own panel type.

**One address space, five consumers.** There is exactly one way to name a
signal, and the timeline, plot panels, the HUD, `sim check`'s expectations and
the A/B diff all resolve through it:

```
<component>.<port>.<field path>     df.bsd.outputs.left.warning      raw, no registration needed
source.<port>.<field path>          source.veh_dyn.longitudinal.velocity
truth.<name>.<field path>           truth.objects[0].dist_x
derived.<name>                      derived.ttc                      computed, registered
```

**Raw port fields need no registration** — the manifest already declares the
port and its `proto_type`, so the resolver walks the message. Only a *computed*
signal (TTC, which no ProPort carries) is registered, with `@signal`:

```python
@signal("derived.ttc", unit="s")
def _(tick, ctx): ...
```

An earlier draft had two mechanisms for one concept — a `@timeline_signal`
decorator for the viewer and a `signal:` path grammar for expectations. Two
address spaces for the same thing drift, and a signal you could plot but not
assert on (or vice versa) is exactly the seam that would open. Adding a
plottable, assertable signal is therefore the same zero-framework-change
operation as adding a layer (`R-SIM-1`).

| Panel type | Shows | Typical use |
|---|---|---|
| `timeseries` | N signals vs time, **one scale per lane** | TTC, ego speed, `observable_fraction` |
| `xy` | one signal vs another, optionally coloured by a third | a target's path in the ego frame; v vs a |
| `state` | categorical bands with labels | warning state, scenario enum, `CompState` |
| `distribution` | a signal's spread over a whole run | onset-time scatter across a scenario set |

Rules, inherited unchanged from the project's charting method:

- **Never two y-scales in one lane.** Two measures of different magnitude get
  two lanes, or are indexed to a common base. This is the single most common
  chart mistake and it is banned outright.
- **`status.*` tokens stay reserved** — a warning band is the same colour
  whichever function raised it, and never doubles as "series 4".
- **Colour follows the signal, not its position** in the current selection.
- A legend whenever a lane carries ≥ 2 series; up to four also direct-labelled
  at their last point, so identity never depends on colour alone.

**Everything is synced.** The playhead is shared across the BEV, the timeline
and every plot. Hovering a plot point highlights that tick and, when the signal
belongs to an entity, that entity in the BEV. Clicking seeks.

**Export**: any plot to PNG (via the print renderer, so it is publication-grade)
or to CSV, both carrying the same provenance sidecar as a BEV snapshot (§9).

### 7.5 Interaction-aware layers — without breaking provider purity

The reference console lets a render context declare that it wants input:
`MouseListener`, `KeyboardListener`, `WindowListener`. That is how a crosshair
follows the pointer, and how clicking a raw detection opens its detail. Our
providers, as specified so far, cannot do either — they are pure functions of a
tick and would have no way to know where the pointer is.

The resolution is **not** to hand a provider an event callback; that would put
state and UI knowledge inside the one thing that must have neither. Instead the
interaction *state* becomes an input:

```python
@dataclass(frozen=True)
class Interaction:
    cursor: Point2D | None      # in the layer's own frame, metres — not pixels
    selection: tuple[str, ...]  # pick_ids currently selected
    modifiers: frozenset[str]   # "shift", "ctrl", …
    toggles: Mapping[str, bool] # per-layer switches the panel exposes
```

carried on `LayerCtx` (arch §5.3). A provider declares what it reacts to, so the
panel knows to re-render it when that changes and not otherwise:

```python
@layer_provider(group="bsd", requires=[...], reacts_to=("cursor", "selection"))
def bsd_measurement_aid(tick, ctx): ...
```

The provider stays a **pure function of `(tick, ctx)`** — same inputs, same
layers — so Scene caching and golden tests are unaffected; the cache key simply
includes the interaction state for layers that declare a dependency on it. A
provider that declares nothing is never re-rendered on a mouse move, which is
also what keeps interaction cheap.

Cursor is delivered **in the layer's frame, in metres**. A provider that wanted
pixels would be violating `R-SIM-2`; a provider that had to convert them itself
would need the viewport, which it must not read.

## 8. Measurement

- **Ruler** — click-drag between two points; shows distance, Δx, Δy and bearing.
  Snaps to prim anchor points (box corners/centres) when within a few pixels.
- **Range rings** — toggleable set at declared radii from the rear-axle origin.
- **Cursor readout** — live `(x, y)` in metres under the pointer, plus the frame
  name. Exists today (`_draw_cursor_readout`) and is kept; the frame name is new
  and matters once more than one frame is in play.
- **Persistent annotations** — drop a labelled marker at a point, kept in the
  session and included in a snapshot. For "this is where it goes wrong".

---

## 9. Capture — the "snapshots" requirement

| Action | Output |
|---|---|
| `S` | PNG of the current canvas at display resolution, **plus a sidecar `.json`**: tick index, `t_s`, project, scenario, pipeline, SUT build id, viewport, active layers, theme |
| `Shift`+`S` | PNG at print resolution through the matplotlib renderer — same Scene, publication quality |
| `Ctrl`+`S` | MP4/GIF of the marked interval (§5's loop marks), at the current viewport and layer set |
| `Ctrl`+`C` | current canvas to clipboard |
| — | `sim render <recording> --at 7.3 --preset blindspot_l --out fig.png` — the same capture, headless, for documents and CI |

The sidecar is what makes a snapshot evidence instead of a picture: a PNG in a
ticket that states which DLL build and which calibration produced it can be
reproduced a month later. This is the counterpart of the run manifest in
[sim_resim_and_recording.md](sim_resim_and_recording.md).

---

## 10. HUD and always-on furniture

Drawn by the framework, not by any layer provider, so it cannot be omitted or
moved — the same discipline `bsdviz.canvas.bev_axes()` already enforces for the
frame triad and ego body ("a figure author cannot omit or move them").

- origin dot at the rear-axle centre, `+x fwd` / `+y left` arrows, `LEFT (+y)` /
  `RIGHT (−y)` side captions;
- distance grid with labelled spacing and a `1 square = N m` legend;
- current scale in px/m;
- `t = 12.35 s · tick 247/1200`;
- project · scenario · pipeline · SUT build id, compact, top-right;
- ego state line: `v 36 km/h · a 0.0 m/s² · yaw +1.2 °/s · ay 0.21 m/s²`;
- a **stale/invalid banner** when an input port's `valid=0` or `ageS` exceeds
  the function's own max-age calibration — currently invisible in the viewer
  even though `AEB_MAX_AGE_OBJECTS_S` exists and the DLL acts on it.

The coordinate convention being visible on the canvas is a deliberate, already
learned lesson (`../../../docs/df_carla_viz_plan.md` §4, added 2026-07-13) and is kept as a
framework guarantee rather than a renderer's habit.

---

## 11. Renderers

Four, all thin adapters over one Scene.

### 11.1 Interactive viewer — the primary

**The shell is a dockable panel grid, not "a BEV with extras".** BEV, camera
view, plots, timeline, inspector, layer tree and the pipeline panel are all
**peer panels**: any can be opened, closed, split, tabbed or floated, and a
layout is saveable per project. That is what makes "plug in a camera view, a
plot, or whatever comes next" a real property rather than a hope — a new panel
type registers itself the way a layer provider or a signal does, and the shell
does not change. Two BEV panels at different viewpoint presets, side by side,
falls out of the same model (and is how an A/B diff is viewed).

Toolkit decision is OD-1 in `sim_architecture.md` §10; the recommendation is Qt
(PySide6), whose dock-widget model is precisely this. The renderer draws prims into a widget; the shell provides docks
(layers, inspector), the scrub bar, the timeline strip, the menu and the
keymap. Retires both the OpenCV window and the tkinter popups, and with them
the two-event-loop pumping hack that `../../../docs/df_carla_viz_plan.md` §5.1c documents as
"the one real gotcha".

**Threading.** Pass 1 (building the `Session` — reading the recording, and in a
resim executing the SUT) runs on a **worker thread**; the UI thread never blocks
on it. Progress is reported and the tail is viewable while it fills, so a long
recording is usable immediately rather than after a freeze. Pass 2 (rendering)
runs on the UI thread and can afford to, because Scenes are cached and layer
providers are pure. That purity also leaves per-tick parallelism available
later without redesign — it is not needed now and is not built.

Components themselves are never executed off that one worker: they are
single-threaded by deliberate design (`sim_sil_contract.md` §4.2).

Performance budget: 60 fps at 2000 prims; a scrub drag must stay interactive at
1200 ticks. Achieved by rendering from the Scene rather than recomputing it —
Scenes are cached per tick and invalidated only when layer selection or theme
changes.

### 11.2 matplotlib — print

Same Scene, `print` theme, vector output. This is the renderer that
`docs/bsd/py/df_bsd_image_creation.py`'s 53 figures move onto, so a requirement
figure and a live view stop being two independent drawings of one geometry
(D5). Figure-specific furniture (captions, provenance colouring, symbol tables)
stays in the figure driver — it is a document concern, not a viewer one.

### 11.3 Foxglove `SceneUpdate` — share and interop

Translates a Scene into Foxglove's scene entities, one entity per layer so its
own visibility toggles line up with ours. Two uses:

- a **live** channel during a run, alongside the existing signal channels;
- a **recorded** channel written into the exported mcap, so a file opened cold
  has the full spatial scene with working seek and layer toggles — closing D8.

The earlier attempt at this failed on a transform-tree bug (`../../../docs/df_carla_viz_plan.md`
§2, design #2: the video channel carried `chase_camera` while the scene used
`ego`, stranding every entity). An explicitly frame-typed Scene is exactly the
structure that prevents that class of bug: the frame is a required field on
every prim, and the frame graph is emitted once from the project model.

### 11.4 Image / camera view

Projects Scene prims onto a camera frame using `model.cameras` intrinsics and
extrinsics. A `Box` with a `height` becomes a projected 3D box; a `Polyline`
becomes a projected polyline. Because it is the same prim the BEV drew, the two
views cannot disagree — which is the whole reason the camera-overlay item was
parked in `../../../docs/df_carla_viz_plan.md` §6 rather than hacked in.

Needs, and does not have today: a `CameraModel` — intrinsics and extrinsics —
and lens distortion handling. Where it is authored follows `R-SIM-9`: a real
mounted camera's calibration is runtime configuration, so it goes wherever the
component that reads it keeps its calibration (`shared_config` only if a second
component needs the same camera). A *simulated* CARLA camera's placement is not
that, and stays with the chase-view code in `sources/carla`. Scoped for Phase D4.

---

## 12. Perception and ground truth

The layer groups that make perception legible, all falling out of the Scene
model with no framework change:

| Group | Layers |
|---|---|
| `ground_truth` | true object boxes, true trajectories, true lane geometry (from `Tick.truth`) |
| `perception` | detections, tracks, track history, association lines, existence/confidence, free space, lane polylines |
| `perception.error` | derived: per-track position/velocity error vs. the matched ground-truth object, drawn as a connector plus a magnitude label |

Both groups render simultaneously and toggle independently, so **perception
error is something you look at rather than something you compute**. Ground truth
uses `truth.*` tokens that are visually distinct in every theme (typically an
outline where perception is a fill), so the two can never be confused at a
glance.

This is also what turns the CARLA bridge's current role inside out in a healthy
way: today it *is* the perception system (it synthesises `GenObjectList` from
actor transforms); afterwards it is a stimulus source that also happens to know
the truth, and both facts stay useful.

---

## 13. Pipeline panel — measured vs simulated, per stage

The one UI surface that is not a *view* of a run but a *definition* of one, and
the one the reference measurement/resim toolchain gets right: **the component
chain, with a per-stage toggle for take-from-measurement versus simulate**. The
operator moves the boundary; they do not switch tools.

It is a direct rendering of the pipeline's `mode:` / `impl:` fields
(`sim_architecture.md` §5.10) — the panel edits data, it does not hold state of
its own.

```
 PIPELINE   df_only · project base · recording bsd_curve_r172_passby
 ┌──────────────────┬───────────────────────────┬──────────────────────────┐
 │ stage            │ source                    │ implementation           │
 ├──────────────────┼───────────────────────────┼──────────────────────────┤
 │ rsp              │ ( ) simulate  ( ) measured│  —                       │
 │                  │ (•) off                   │                          │
 │ perception-core  │ (•) simulate  ( ) measured│  [stub:carla_ground_truth ▾]
 │                  │                    ⚠ not in recording                │
 │ df               │ (•) simulate  ( ) measured│  [dll:df_sil.dll        ▾]
 │                  │               ✓ available │  build v0.4.2-17-g1b7b66c │
 └──────────────────┴───────────────────────────┴──────────────────────────┘
   ▸ compare simulated stages against their recorded outputs   [✓]
```

Behaviour:

- **`measured` is offered only when the loaded recording actually contains that
  stage's output topics.** Otherwise the radio is disabled with the reason
  inline — never a choice that fails at run time.
- **Flipping `mode` never discards `impl`**, so the toggle is reversible with
  one click. This is the whole ergonomic point.
- **A `measured` stage's inputs are greyed**, because they are not consumed —
  which makes it visible that upstream work is being discarded.
- **A `measured` stage downstream of a `simulate` stage is flagged**, not
  blocked: it is legitimate for isolating one component, but it usually means
  the simulated stage above it is having no effect, which is worth saying out
  loud.
- **Per-port override** is available by expanding a stage (`inputs:` wiring),
  for the "simulate this component but feed it one recorded input" case.
- **Compare-against-recorded** (the checkbox) is available whenever a
  `simulate` stage's outputs also exist in the recording. Turning it on adds a
  divergence lane per port to the timeline (§7.3) and marks the **first
  differing tick** as an event — the number you actually want when a build
  change moves a decision.
- Changing anything here **invalidates the Session and re-runs pass 1**; layer
  toggles and viewport changes do not (§5). The panel says which of the two a
  given control is, so nobody is surprised by a re-run.

The panel is populated entirely by discovery: stages from the pipeline YAML,
available `impl:` choices from the component manifests found on disk, `measured`
availability from the recording's topic index. Nothing is hardcoded, and a new
component appears without a GUI change — the same rule
`df_sim_gui.py`'s dropdowns already follow today.

## 13b. Workspaces — a component ships a default arrangement

> **Two different things share the word "workspace"; keep them apart.**
>
> | Term | Meaning | Owner | Defined in |
> |---|---|---|---|
> | **Workspace** (this section) | a component's default *panel arrangement*, shipped as data | the component | `modules/<name>/sim/workspace.yaml` |
> | **Bench / Campaign** | the application's two *modes* — one run interactive vs. many runs reported | the framework | [sim_player.md](sim_player.md) §1, §4, §5 |
>
> They compose rather than compete: **Bench and Campaign each load the
> component's workspace as their starting arrangement**, then apply their own
> permission set (Bench permissive, Campaign locked). A component never knows
> which mode it was opened in — the same discipline `R-SIM-1` applies to
> function names, applied to workspaces (`UT-D8-9`).

§11.1 makes panels dockable and layouts saveable *per user*. That is only half
of it, and the reference measurement console shows the missing half: **the
component ships a default arrangement as data**, so opening a recording for the
first time gives a sensible workspace instead of an empty grid the user has to
assemble.

Its layout file is a tree of tabs, splitters and named views with ratios. Ours
is the same idea in the schema language we already use:

```yaml
# modules/df/sim/workspace.yaml
workspaces:
  default:
    tabs:
      - name: "BSD"
        split: {orientation: vertical, ratio: [1, 2]}
        views:
          - {panel: bev,      viewpoint: blindspot_l}
          - {panel: timeline, signals: [df.bsd.outputs.left.warning,
                                        df.bsd.outputs.right.warning,
                                        derived.ttc]}
      - name: "Approach"
        views: [{panel: bev, viewpoint: forward}]
```

Rules:

- **A workspace is a default, never a lock.** The user rearranges freely, and
  their layout persists per (project, pipeline) and wins next time. `Reset
  layout` returns to the shipped default.
- **A workspace names panels and viewpoints, never geometry or colours** — it
  composes things declared elsewhere (viewpoints §4.3, signals §7.4, layers).
- **It lives with the component** (`modules/<name>/sim/workspace.yaml`), because
  which arrangement is useful depends on the function — a rear-safety function
  wants a blind-spot view and warning lanes; a forward function does not.
  `R-SIM-1` holds: the framework reads the file, it does not know what `BSD` is.
- **A missing workspace is not an error** — the framework falls back to a single
  BEV plus the timeline.

## 14. Keymap

| Key | Action | | Key | Action |
|---|---|---|---|---|
| `Space` | play / pause | | `S` | snapshot PNG + sidecar |
| `←` `→` | step ∓1 tick | | `Shift`+`S` | print-quality snapshot |
| `Shift`+`←/→` | step ∓10 | | `Ctrl`+`S` | export marked interval to video |
| `Home` `End` | first / last tick | | `M` | ruler |
| `[` `]` | previous / next event | | `A` | drop annotation |
| `L` | loop marked interval | | `G` | toggle grid |
| `F` | fit to content | | `T` | cycle theme |
| `1`…`9` | viewport preset | | `Ctrl`+`L` | focus layer search |
| `0` | reset viewport | | `?` | keymap overlay |
| `R` | cycle follow mode | | `Esc` | clear selection |

---

## 15. What a layer provider may and may not do

The contract, stated as rules because this is where a framework erodes.

**Must:**
- return `Layer`s built only from the `Tick` it was given and the
  `ProjectModel`;
- express every geometry in metres in a declared frame;
- use style tokens;
- declare its inspector fields and timeline signals.

**Must not:**
- compute pixels, or read the viewport;
- import a renderer, `cv2`, `matplotlib` or Qt;
- read a file, open a socket, or hold state between ticks (a provider is a pure
  function; a provider that needs history reads it from the Session);
- **re-derive a value the SUT already produced.** If `BsdOutputs` carries a
  warning state, draw that state — never recompute it. Today's viewer honours
  this for warnings and knowingly breaks it for the zone rectangle and the
  unobservable region, which it re-derives in Python from calibration because
  no debug ProPort exposes them. That is a legitimate stopgap and it is
  **marked as such**: a re-derived layer is drawn with a `derived` style variant
  and named `…(derived)` in the layer panel, so nobody mistakes a Python
  reconstruction for what the algorithm actually did. The permanent fix is a
  debug ProPort, tracked as an open point below.

---

## 16. Feature checklist

Everything a state-of-the-art ADAS debug BEV needs, with today's status.

| # | Feature | Today | Stage |
|---|---|---|---|
| 1 | Object boxes with labels | ✅ fixed 4.5×1.8 m, unrotated | B1 |
| 2 | **Config-driven ego body** | ⚠ BSD-only branch | A2/B1 |
| 3 | **Config-driven object footprints by class** | ❌ | A2/C4 |
| 4 | Oriented (yawed) footprints | ❌ | B1 |
| 5 | Geometry from `GenObject.geometry` when present | ❌ parked | D4 |
| 6 | Coordinate frame furniture (origin, triad, grid, scale) | ✅ | B1 |
| 7 | Cursor metre readout | ✅ | B1 |
| 8 | Click-to-inspect | ✅ two entity types, popups | B3 |
| 9 | **Pan / zoom / fit** | ❌ | B3 |
| 10 | **Viewport presets incl. blind-spot** | ❌ | B3 |
| 11 | **Follow modes (heading / world / locked)** | ❌ | B3 |
| 12 | **Scrub bar, backwards seek** | ❌ forward-only | B2 |
| 13 | Step / speed / loop | ⚠ step only | B2 |
| 14 | **Layer panel with groups + verbosity** | ❌ | B3 |
| 15 | **Timeline signal + state lanes** | ❌ | B3 |
| 16 | **Event markers from state transitions** | ⚠ console prints | B3 |
| 17 | Expectation spans on the timeline | ❌ | C3 |
| 18 | **Snapshot PNG + provenance sidecar** | ❌ | B3 |
| 19 | Print-quality snapshot | ⚠ separate figure pipeline | D2 |
| 20 | **Video export of an interval** | ❌ parked | B3 |
| 21 | Ruler / range rings / annotations | ❌ | B3 |
| 22 | Themes incl. validated palette | ⚠ two ad-hoc palettes | A3 |
| 23 | Stale / invalid input banner | ❌ | B1 |
| 24 | Heatmap layer (η coverage) | ⚠ per-cell rectangles | B1 |
| 25 | Foxglove scene (live + recorded) | ❌ signals only | D1 |
| 26 | A/B diff of two sessions | ❌ | D1 |
| 27 | Camera panel with projected overlays | ⚠ raw video only | D4 |
| 28 | Ground-truth vs perception layers | ❌ | D4 |
| 29 | Headless render for docs/CI | ❌ | C3 |
| 30 | **Pipeline panel: per-stage measured/simulate toggle** | ❌ | C2/D3 |
| 31 | **Simulated-vs-recorded divergence lane + first differing tick** | ❌ | C2/D3 |
| 32 | **Plot panels — timeseries / xy / state / distribution** | ❌ | B3 |
| 33 | **Dockable peer-panel grid; saveable layouts** | ❌ | B3 |
| 34 | Plot export to PNG / CSV with provenance | ❌ | B4 |
| 35 | **Component-shipped default workspaces** | ❌ | B3 |
| 36 | **Interaction-aware layers (cursor / selection / toggles)** | ❌ | B3 |
| 37 | **Config source override, per artifact kind, user-visible** | ❌ | C5 |

Legend: ✅ works · ⚠ partial or worked around · ❌ absent.

---

## 17. Open points

- **Debug ProPorts.** Several things worth drawing exist only inside the
  algorithm (the warped zone polygon under curvature, per-object gate results,
  the corridor). Re-deriving them in Python is a stopgap that can silently
  disagree with the DLL. A `<fn>.debug` output port — present only in SIL
  builds, gated the same way `ENABLED_FUNCTIONS` gates code — is the clean
  answer and is cheap once ports are named ([sim_sil_contract.md](sim_sil_contract.md)).
  Not scheduled; raise it when the first disagreement bites.
- **Rendering large heatmaps at high zoom.** η coverage at 0.02 m resolution
  over a 3 m × 10 m zone is ~75 k cells. The `Heatmap` prim must carry its own
  resolution and let the renderer downsample; not designed here.
- **Multi-panel layouts.** BEV + camera + timeline is three panels; whether the
  user can add a fourth (a second BEV at a different preset, for an A/B diff) is
  a shell feature, deferred to B3's implementation.
- **Session size with camera frames.** Frames stay by reference into the
  recording and are decoded on demand; the cache policy is an implementation
  detail with a real memory consequence, flagged rather than decided.
