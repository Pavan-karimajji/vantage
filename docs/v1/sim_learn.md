# Learn the simulation platform — the story, stage by stage

Status: **explanatory, not normative.** Every other document in `docs/` tells
you *what the rules are*. This one tells you *what we are building and why*, in
order, in plain language, for a reader who has not spent a week inside the
design set.

**If a statement here disagrees with a spec, the spec wins** — and that
disagreement is a bug in this file, worth reporting (`GT-7`). Nothing here is a
requirement; this document is a door, not a contract.

Read this first. Then read [sim_architecture.md](sim_architecture.md) for the
real design, and [sim_implementation_plan.md](sim_implementation_plan.md) for
the build order.

---

## 0. One analogy, used throughout

The whole system is a **multitrack recording studio**. Almost every design
decision in these documents is a decision a studio already made decades ago,
and the mapping holds all the way down:

| In the studio | Here |
|---|---|
| An instrument (a guitar, a synth) | A **component** — `df`, `perception-core`, `planning`. Compiled into a DLL |
| The standard jack socket on the wall | The **generic ABI** — five C functions every component exposes |
| The label on the instrument's case: *"takes 2 inputs, gives 3 outputs"* | The **port manifest** — what the DLL says about itself when asked |
| The setup card taped to the case: *"tuned to A=442"* | The **config bundle** — the calibration this build was made with |
| The patch bay — which output feeds which input | The **pipeline** — a YAML file, wiring stages by port name |
| The multitrack tape — *every* track recorded separately | The **recording** (`.mcap`) — every stage's inputs *and* outputs |
| The stereo master — the finished mix, nothing left to change | An **export** (CSV, video) — lossy and terminal |
| A live gig | **sim** — the world model is running, nothing is reproducible |
| Re-mixing from the multitrack | **resim** — the SUT re-executed against a recording. Deterministic |
| Playing the master through speakers | **replay** — a recorded result drawn, no computation |
| *"Mute the live drummer, play the drum track from tape"* | `mode: measured` on a stage |
| The score — notes and timings, no sound yet | The **Scene** — geometry in metres, no pixels |
| The speakers | The **renderers** — Qt, matplotlib, Foxglove |
| The mixing console you sit at | **Vantage**, the player application |
| The track sheet: which mic, which take, which day | The **evidence chain** — every drawn value traced to its bytes (`R-SIM-25`) |
| *"Recorded at 14:05, dropped into the mix at 14:07"* | **Capture time and reception time** — two clocks, because latency is real (`CR-SIM-4`) |

Two things follow from the analogy that are worth stating before anything else,
because they are the two ideas people push back on hardest:

1. **The mixing desk does not know what a guitar is.** It knows *channels*. That
   is why the framework must never contain the string `bsd` — not as
   fastidiousness, but because a desk that has a guitar button needs a new
   button for every instrument ever invented. (`R-SIM-1`)
2. **You record every track, not just the vocal.** It costs almost nothing and
   it is the difference between "we can remix this" and "we can only listen to
   it". That is why we record every stage's outputs, not only its inputs.
   (`R-SIM-6`)

---

## 1. The problem, before any design

Today, to look at what the driving functions did, you run a Python script that
lives inside `modules/df`. That script does everything: connects to CARLA,
invents the objects, calls the DLL, records an mcap, and draws a picture with
OpenCV.

It works. It also has eleven specific defects, catalogued as `D1`…`D11` in
[sim_architecture.md](sim_architecture.md) §3. Four of them explain the whole
rework, and each is worth understanding as a *shape*, because the same shape
recurs:

**D1 — the C function grows every time you add a driving function.**
`dfExec(handle, dt, objectsIn, objectsLen, egoIn, egoLen, aebOut, aebLen, …)`.
Add BSD, and the function gets two more parameters. Add ACC, two more. Every
host that calls it must be recompiled and edited. Six functions in, the
signature is unreadable and the ABI has broken six times.
*Studio version: a mixing desk where adding a guitar means drilling a new hole
in the front panel.*

**D2 — the renderer grows the same way.** `draw(frame, aeb=..., bsd=...,
lca=...)`. One keyword argument per function, in the framework.

**D3 — the picture is drawn from numbers typed into Python**, while the real
vehicle dimensions sit in YAML that the DLL reads. Two sources for one truth.
When they drift, the picture is confidently wrong — which is worse than blank,
because you believe it.

**D9 — all of it is `df`'s private property.** `perception-core` cannot use any
of it. So when perception needs a viewer, someone writes a second one. Then a
third. Each is 80% the same code and 100% separately maintained.

Every one of these is the same underlying mistake: **a thing that should be
data was written as code.** The port list was code (D1). The layer list was code
(D2). The geometry was code (D3). The ownership was a folder path (D9).

The whole rework is one move, applied four times: **turn it into data, and let
the code discover it.**

---

## 2. The seven ideas

Everything else is consequences of these.

### Idea 1 — The socket (`R-SIM-4`)

Instead of a C function that grows, every component exposes exactly **five**
functions, forever:

```c
adasAbiVersion()   // which ABI generation am I?
adasManifest()     // what ports do I have?          <- the label on the case
adasInit(path)     // give me my configuration
adasExec(h, dt, in, out)  // run one tick
adasShutdown(h)
```

`in` and `out` are **arrays of named ports**, not fixed parameters. Adding BSD
adds a *row* to the manifest. The five functions never change. `adasAbiVersion()`
still returning `1` after six driving functions have been added is the entire
evidence that D1 is closed.

This is genuinely all the ABI is. It is deliberately **empty of architecture** —
it does not know how many components exist, what they are called, or how they
are wired. A wall socket does not know the layout of your house. That emptiness
is the point.

### Idea 2 — Geometry, then pixels (`R-SIM-2`)

A **layer provider** is a small function that answers "what shapes describe this
right now?" It returns rectangles and circles in **metres**, in a named frame,
labelled with a **meaning** (`"zone.entry"`), never a colour.

A **renderer** turns those shapes into pixels.

They never meet. Which is why the same picture works in a Qt window, in a
matplotlib PDF, and in Foxglove — three renderers, one provider. And why a
provider is testable without a screen: you assert on the shapes.

*Studio version: the score is the score. It plays on a piano, an orchestra, or
a phone speaker. The composer never writes "and here, use the good speakers".*

### Idea 3 — Configuration is the source of geometry (`R-SIM-3`, `R-SIM-3a`)

The ego vehicle's length is not a number in Python. It is read from the same
project YAML the DLL reads. Switch project, and the picture changes — if it
doesn't, something is hardcoded and lying.

The hard part is *making sure both readers read the same bytes*. That is the
**config bundle**: at build time, the calibration files are copied into a
`config/` folder next to the DLL, with a checksum. `adasInit(NULL)` finds it by
looking beside itself. A recording embeds a copy. So the viewer can prove it is
looking at the same numbers the algorithm used, rather than agreeing by
coincidence.

*Studio version: the setup card is taped to the instrument case, and a copy goes
in the tape box. Not on a whiteboard back at the studio.*

### Idea 4 — Two independent switches per stage (`R-SIM-10`)

This is the idea that makes one tool cover every kind of test, and it is the one
worth slowing down for.

Every stage in a pipeline has two settings that have nothing to do with each
other:

- **`mode:`** — is this stage *actually executed*, or is its output *played from
  the recording*? (`simulate` / `measured` / `off`)
- **`impl:`** — if executed, by what? (a real DLL / a Python stand-in / a
  compiled stand-in)

The invariant that makes it work: **a stage that was executed and a stage that
was injected produce the same port set.** The consumer downstream cannot tell
which it got — and must not be able to.

Once that holds, everything else is free:

- *"Test the driving functions in isolation"* = set perception to `measured`.
- *"Now test perception too"* = flip one word to `simulate`.
- *"That component doesn't exist yet"* = a stand-in, which is a stage like any
  other, not a special mode in the tool.
- The downstream component's configuration is **byte-identical** in all three
  cases. That is the whole payoff.

*Studio version: solo and mute. "Play the drums from tape while the bassist
plays live" is one button, not a different studio.*

One honest complication, and the reason `R-SIM-10` is the longest rule: if you
set the *middle* stage to `measured` while both neighbours are `simulate`, the
first stage computes into nothing and the third never sees it. The chain is
severed and the toggle is lying to you. So setting a stage to `simulate` closes
the gap by default — and if you deliberately force it open (a legitimate thing
to do while debugging), the orphaned stage is badged *"computed, not consumed"*
rather than silently ignored.

### Idea 5 — A recording is a model, a format is a codec (`R-SIM-14`)

Nothing downstream knows the file is an `.mcap`. The Scene doesn't, the viewer
doesn't, the expectations don't. They know: metadata, topics, and
`(topic, time, bytes)`.

So supporting CarMaker's output format is **one file with four read methods**,
not an integration project. And `sim convert` isn't a feature anybody built —
it's what you get for free once readers and writers are symmetric.

### Idea 6 — Every number can be traced back to its bytes (`R-SIM-25`)

Added after an adversarial review of this design in July 2026, and it may be the
most important one for whether anybody actually uses the tool.

The way a visualization tool dies is not a crash. It is a developer who sees
something odd on screen, cannot work out where it came from, stops trusting the
window, and goes back to `printf`. Every feature built after that moment is
wasted.

So: click anything — a box, a zone, a point on a plot — and the tool answers, in
one action: **which port · which topic · which tick · where the data came from ·
which calibration · which build of which component · and whether the SUT actually
published this or a layer reconstructed it.**

The pieces for that all existed already; they were just never joined. What is new
is one small rule with a large consequence: **there is one function that produces
that answer, and two things that format it** — the panel in the window, and
`sim explain` on the command line. Not two implementations that are *supposed* to
agree. One, formatted twice. And a field it cannot fill says `unknown`, never a
plausible-looking guess — on the one surface whose whole job is being believed.

*Studio version: every track on the tape is labelled with which microphone,
which take, which day, and whether it was played or punched in later.*

### Idea 7 — A message has two times, not one (`R-SIM-14`)

A camera frame is *taken* at one instant and *arrives* at the ECU at another.
The gap is latency, and it varies.

The recording used to keep only the arrival time. That sounds harmless — and
replaying such a recording does reproduce the delay correctly, because "arrived
late" is stored as *which tick it landed on*. But the delay becomes **invisible**:
the tool would tell you the data is 0.0 seconds old when it is really 80 ms old,
so the "stale data" warning lies in exactly the situation it exists for. And a
real measurement from a vehicle arrives with *both* stamps already — throwing one
away at the door is not recoverable.

So a message now carries **capture time** and **reception time**. When capture is
unknown it is `None`, and it is never quietly set equal to reception — because
"equal" would manufacture an age of exactly zero that you could not tell apart
from a true one.

*Studio version: the take was recorded at 14:05 and dropped into the mix at
14:07. Writing both down is what lets you fix the timing later.*

---

## 3. The walkthrough

Five phases. The ordering is not aesthetic — each phase is chosen so that a
mistake in it is cheap.

| Phase | What it builds | Needs a compiler? | State |
|---|---|---|---|
| **A** Foundations | the vocabulary: project model, Scene IR, the mcap codec | no | done |
| **B** The viewer | `Session`, layer providers, the Qt shell, capture — driven by **already-recorded files** | no | done |
| **C** The contract | the generic ABI, the production side, the config bundle, ingest | **yes** | done |
| **D** Reach | Foxglove, the pipeline panel, a second component, packaging, overrides, batch, **Vantage** | yes | done |
| **E** Retirement | delete the per-component private tooling it replaced | yes | not started |

[sim_implementation_plan.md](sim_implementation_plan.md) §0a is the authority on
what is left and in what order; this table is the story, not the tracker.

### Why this order, and not "build the exciting thing first"

The tempting order is: get a picture on screen driven by a real DLL, then tidy
up. That order has a trap in it.

To drive the DLL *before* the generic ABI exists, the framework would need a
component-specific ctypes binding **inside the framework** — the exact thing
`R-SIM-1` forbids, written in the one place it must never live, and then
unpicked later. Building the viewer against **already-recorded files** avoids
needing one at all. By the time the framework first talks to a library, the
socket already exists and the binding is component-agnostic by construction.

Everything in A and B is testable with **no build at all**, which is why most of
the suite runs in seconds on a laptop with no compiler.

### The one sentence that organises Phase C

Phase C is confusing for an honest reason: it is six things across three repos
and two languages. This is the sentence that lines them up:

> **A component's DLL must be able to answer three questions — *what ports do I
> have*, *what configuration am I using*, and *run one tick*. Everything else in
> Phase C is building the things that ask those three questions.**

Two properties held throughout, and they are why it could touch production C++
safely: **every change was additive**, and `src/component/**` was never touched.
The generic exports were built *beside* the positional ones, with a test proving
both paths produce **byte-identical output** for the same inputs. Nothing is
removed until Phase E, and only after its replacement is proven. That
equivalence test is the most valuable single thing in Phase C — it turns "we
rewrote the interface" from a leap into a measurement.

**One lesson from Phase C that generalises**, because it cost a re-open: two
stages were built and reported green against a standalone `gcc` harness by a
session that had no Conan and no MSVC. The *code* was right; the *build* was
red, and the defects lived entirely in CMake and cross-repo commit order.

> A parallel toolchain verifies the code. It structurally cannot verify the
> build, because it does not use the build.

**Phase E's risk has a different shape** from A–D's: adding code fails loudly on
the thing you just wrote; removing code fails weeks later, for someone who was
not in the room. That is why every deletion is gated on its replacement being
*proven* rather than merely existing (`NR-SIM-30`).

---

## 4. How you actually use it

One executable, `sim`, plus `vantage` for the window. Fourteen verbs, and none
of them names a driving function — the tool learns what exists by asking the
DLL.

**Look at something**

| Command | Does |
|---|---|
| `sim doctor` | reports your environment: interpreter, install mode, platform, encoding. Grows a section per capability, so it is the first thing to run when something is odd |
| `sim probe <lib.dll>` | asks a library what ports it has — no repo, no Python knowledge, no docs |
| `sim probe <rec.mcap>` | asks a **recording** what it provides, and **which cuts it supports** (§8) |
| `sim explain <name>` | explains any name in the system — a port, a layer, a signal, a topic, an error |
| `sim list ports\|topics\|layers\|signals` | enumerates one kind for a library, recording or session |
| `sim view <rec>` / `vantage <rec>` | opens the window |
| `sim render <rec> --at <tick>` | headless snapshot to PNG, with a provenance sidecar |

**Produce a recording**

| Command | Does |
|---|---|
| `sim record <scenario>` | drives a world model and writes a recording. **Executes nothing** |
| `sim run <scenario>` | drives a world model **and** executes a pipeline, live, writing a session recording |

**Re-execute one**

| Command | Does |
|---|---|
| `sim resim <rec> --pipeline <p.yaml>` | re-runs the SUT against a recording. **Deterministic, and the only thing that goes in CI** |
| `sim check <scenario-dir>` | evaluates the scenarios' `expect:` blocks headless; exits non-zero on failure |
| `sim determinism <a> <b>` | compares two recordings; **the axis is derived from their manifests, never declared by a flag** |
| `sim batch <recordings>` | runs a pipeline over a set, one subprocess per recording, so a crash costs one row |

**Move data**

| Command | Does |
|---|---|
| `sim convert <in> <out>` | recording → recording, between codecs |
| `sim export <rec> --ports …` | recording → CSV. **Lossy and terminal** — an export is never a resim input |

### The three words, against those verbs

This is the distinction the whole tool rests on (`R-SIM-5`), and it is easiest
to see here:

- **sim** — a live world model computes the world. Non-deterministic. `sim run`.
- **resim** — the SUT is re-executed against a recording. Deterministic, and the
  only one CI trusts. `sim resim`.
- **replay** — a recorded result is rendered with **no computation at all**.
  `sim view`.

Never call a resim a replay. The difference is whether your code ran.

---

## 5. What you configure, and where

Nothing physical is a constant in the source. Every number that describes the
world is resolved from YAML at run time, and **switching project must change
the picture** (`R-SIM-3`). Here is every file that decides something, who owns
it, and what breaks if it is wrong.

### Calibration — what the vehicle actually is

| File | Owner | Decides |
|---|---|---|
| `projects/<p>/default.yaml` | the project | every physical number: zone geometry, thresholds, sensor poses, class footprints, sample periods (`R-VAR-4`) |
| `shared_config` → `vehicle/ego_params.yaml` | shared | the ego body — wheelbase, overhangs, width |

Calibration keys are **ALL_CAPS with a domain prefix and a unit suffix**
(`EGO_WHEELBASE_M`, `<COMPONENT>_<FN>_PERIOD_US`) — `R-NAME-3`. The unit is in
the name because a bare `width` is exactly how you get a plausible wrong
picture.

### The bundle — calibration, as delivered

The build copies the resolved calibration **beside the built library**, so a
recording renders correctly on a machine with no checkout:

```
<library_dir>/
  df_sil.dll
  config/
    default.yaml          the project's calibration
    vehicle/              shared_config's ego params
    df_sil.ports.yaml     a dump of the ports that compiled
    bundle.sha256         what makes it one atomic artifact
  sim/                    the component's plug-ins (below)
```

Three things follow, and each exists to prevent a specific failure:

- **`adasInit(NULL)` resolves it module-relative.** An explicit path always
  wins; a project mismatch is a **warning**, not a stop.
- **It is copied beside the DLL, never compiled into it.** Compiling it in would
  kill the edit-and-re-run calibration loop. Production freezes parameters via
  AUTOSAR instead.
- **The viewer must read the bundle the SUT was initialised with**, resolving
  *embedded-in-recording → library `config/` → source checkout* — and **stating
  which**. Two readers agreeing by coincidence is the exact failure this
  prevents (`R-SIM-3a`).

**Never edit the bundle.** It is a build output. Edit `projects/<p>/` and
rebuild, or the next build silently reverts you.

### What a component declares about itself

| File | Decides |
|---|---|
| `modules/<n>/conf/build.yml` | project × target × platform, Conan `requires`, and `enabled_functions` (`R-VAR-3`) |
| `modules/<n>/conf/ports.yaml` | **the port declaration** — the one hand-written source the ABI shim is generated from (`R-SIM-22`) |
| `<n>_sil.ports.yaml` | **generated.** A dump of what compiled. Never hand-edit it; it exists so a human can read the manifest without loading the DLL |

Function selection is **compile-time** (`ENABLED_FUNCTIONS`, `R-VAR-5`), so the
manifest cannot drift from what was built.

### What a component contributes to the picture

All of it lives in `modules/<n>/sim/`, and the build deploys it to
`<library_dir>/sim/` exactly as it deploys the config bundle — which is what
makes *"point Vantage at a folder of DLLs and it draws them"* true with no
checkout and no `PYTHONPATH` (`R-SIM-20`).

| File | Decides |
|---|---|
| `plugin.yaml` | the plug-in API generation and the bundle hash. **Read before importing**, so an incompatible plug-in is refused rather than half-loaded |
| `layers/<fn>.py` | one file per function — the *only* place that function's picture is described |
| `viewpoints.yaml` | named camera viewpoints |
| `pipelines/*.yaml` | **the wiring**: per stage `mode:` and `impl:`, per-port overrides, the `record:` policy |
| `sensor_models/*.yaml` | sensor **error** models — noise, latency, dropout, occlusion |
| `ingest/*.yaml` | which topic in a foreign recording satisfies which port (§8) |
| `tolerance.yaml` | determinism tolerance. `default: exact`; every row needs a `why:` |
| `workspace.yaml` | the component's default panel arrangement. *Specified (viz §13b); no component authors one yet* |

A recording embeds the config bundle's **bytes** but only the plug-in bundle's
**hash and identity**. The asymmetry is deliberate and nobody should "fix" it:
**configuration is data, a plug-in is code** — opening a colleague's recording
must never run their code. A missing plug-in degrades to *"these layers
unavailable"*, named with the hashes it expected.

### The pipeline file — where you decide what actually runs

This is the file a developer edits most, and the one that makes one tool cover
every level of simulation. Per stage, **two independent fields**:

- **`mode:`** — `simulate` (execute it) · `measured` (inject it from the
  recording) · `off`
- **`impl:`** — `dll:` (the real library) · `stub:` (a Python stand-in) ·
  `stubdll:` (a stand-in on the same generic ABI)

The invariant that makes this work: *executed* and *injected* produce **the same
port set**, so a downstream consumer cannot tell which it got. Ground truth →
real perception → RSP in the loop is therefore a `mode:`/`impl:` change, and the
downstream stage's entry stays byte-identical (`R-SIM-10`).

`impl:` is **retained** on a `measured` stage, so the toggle is reversible.
Setting a stage to `simulate` **closes the gap by default** — intervening stages
flip too — because a `measured` stage between two `simulate` stages is a severed
chain where the upstream computes into nothing. Forcing the gap open is allowed
and is how you watch one stage diverge while holding the next on known-good
input; the orphaned stage is then badged *"computed, not consumed"*.

You can also **tweak a port's value** from a closed list of six verbs — `const`,
`hold`, `offset`, `scale`, `select`, `drop` — addressed at a port, a field path
(`egoDyn.vx`) or a repeated element (`[i]`, `[*]`). The line that keeps the list
closed: **an override may destroy or attenuate information; it may never create
an entity.** There is no expression language and no scripting hook, deliberately
(`R-SIM-15`). Every override is declared in the run manifest and badged in the
HUD — never smuggled.

### Scenarios

A scenario lives with the **module that owns its behaviour**
(`modules/<n>/tests/*_scenarios/**/*.yaml`), never in the framework — its
`expect:` block names component ports, so a scenario in `modules/sim` would put
a function's name in the framework. It carries the world-agnostic content, how
that is realised in a specific simulator, the sensor model, run control, the SUT
reference, and its `expect:` block. **The expectations are data, from one
source**: the same block drives the timeline marker, the headless `sim check`
and the report, and every timing predicate carries an explicit `within_s` —
there is no default tolerance (`R-SIM-8`).

### The other inputs

| Thing | What it is |
|---|---|
| **`<n>_sil.dll`** | the component under test. Carries its own manifest **and** a `FileDescriptorSet`, so message classes are built at run time from the DLL that produced the bytes — **no generated Python bindings, no sibling checkout** (`R-SIM-11`) |
| **`.mcap`** | the recording. Read **and** written |
| **`.jsonl`** | read and written; the debuggable text format |
| **CSV** | **write-only.** Registered without a reader, so the loader refuses it by capability rather than by convention — an export is lossy and terminal |
| **Foxglove `SceneUpdate`** | an export, for viewing a Scene in a foreign viewer |

A recording is a *model*; a format is a *codec* (`R-SIM-14`). Adding one is a
reader and a writer of about four methods each, registered by extension —
nothing in the viewer, the layers or the expectations may learn a format exists.

---
## 6. The questions you will actually ask

### "Why is sim code spread across five repos? Isn't that the opposite of modular?"

Count what is actually in each place:

| Repo | What | Size |
|---|---|---|
| `modules/sim` | the entire framework | ~8,300 lines |
| `modules/df/sim` | what BSD looks like | ~320 lines |
| `modules/interfaces` | one C header + one `.proto` | ~2 files |
| `modules/df/src/platform/df_sil` | the DLL's ABI shim | ~1 file |

That is not "sim code everywhere". That is one framework plus a thin
contribution per component — and the contribution is the part that is genuinely
about *that component*, which is the only part that can't be shared.

The test is: **when you add ACC, what changes?** Answer: a declaration in `df`,
a layer file in `df/sim/layers/`. Nothing in `modules/sim`. Nothing in the ABI.
No host edit. If that stops being true, the design has failed and the grep gate
(`GT-1`) is what will tell you.

### "Then why not move `df/sim` into `modules/sim` so the tool is standalone?"

Because that question is really **two** questions, and they have different
answers:

- *Where is BSD's picture **authored**?* → in `df`. Moving it into the framework
  puts a function's name in the framework, which is D9 coming back with the
  polarity reversed: instead of `df` owning everyone's viewer, `sim` owns
  everyone's content. Every component's picture change becomes a `sim` release.
- *Does Vantage need `modules/df` **checked out** to draw BSD?* → **it must not,
  and today it does.** That is the real gap, and it is your instinct being
  correct.

The fix is not to move the folder. It is to **deploy** it: the build copies
`modules/df/sim/` next to `df_sil.dll` — exactly as it already copies the config
bundle — and Vantage discovers plug-ins from a **plug-in path** of library
directories. Then "point the player at a folder of DLLs and it draws them" is
true, with no checkout, no `PYTHONPATH`, and no rebuild of the player to add a
function. This is now `R-SIM-20`, and it is a change this review introduced.

### "Where do port names live? It looks like they're typed into code."

Half right, and the half that is wrong is the important half.

**Producer side (C++) — solved.** The port name is a single named constant, read
by both the manifest builder and the `adasExec` dispatch. A rename is one edit;
the manifest cannot desynchronise from the dispatch. This was verified the right
way — by deliberately breaking it and confirming the tests went red.

**Consumer side (Python) — not solved.** `modules/df/sim/layers/bsd.py` contains
the literal string `"df.bsd.outputs"`. That string is a *pipeline-authoring
choice* (`df` is the stage name someone typed in a YAML file) glued to a port
name. Rename either, and the layer **silently disappears** — the gating code
returns an empty result, and an empty overlay on screen looks exactly like "the
algorithm didn't fire".

So your instinct is right and now has a rule: `R-SIM-21` — a plug-in names ports
relative to **its own component**, resolution happens once at load, and a name
that resolves against nothing is an error that names the plug-in, the port asked
for, and every port the manifest actually has.

### "What is `sil_host` for, exactly?"

A small C++ program that loads component DLLs and ticks them, with no Python
anywhere. That makes it the one place a timing measurement is trustworthy, and
the closest thing to a real production integrator.

The intended split: `sil_host` runs compiled things (`dll:`, `stubdll:`) and can
inject recorded values (`measured`). It can never run a Python stand-in, and —
stated as a rule so it cannot erode — **it must never grow its own way of
inventing test data.** If it needs a stand-in, that stand-in is built once as a
compiled component on the same socket, usable by both tools.

**Honest status:** `sil_host` is 54 lines today and calls the old positional
functions directly. The stated aspiration — one pipeline file runs unchanged
under both Vantage and `sil_host` — is written as fact in the architecture and
as an open question (`OQ-11`) in the contract. Only ABI compatibility is
actually scheduled. That inconsistency is now resolved in favour of building it:
see `S-C7` in the implementation plan.

### "Is this over-engineered?"

Here is the honest scorecard.

**Arguments it is not:** 8,300 lines for a full BEV player, a resim engine, two
recording codecs, four renderers and a pipeline scheduler is *small* — comparable
open tools are ten to a hundred times that. About 3,500 lines get deleted at
Phase E, so the net addition is ~5,000. And 410 tests run in 42 seconds with no
compiler, which is the property that will still matter in two years.

**Arguments it is:** the design set is ~600 KB of normative prose across ten
documents — **larger than the code it describes.** The implementation plan alone
is 3,745 lines. Every stage must re-tick two discipline checklists and nine
global gates. That is real overhead, and it is the thing to watch: if a stage
starts costing more in document maintenance than in code, the documents have
stopped paying for themselves.

**The specific thing to watch:** how many concepts a developer must hold to do
the simplest useful thing. The first count of this said **ten** for one
rectangle — the provider decorator, `LayerCtx`, `Prim`, style tokens, themes,
frames, port addressing, the `derived` flag, the `assumed_geometry` flag, and
three grep gates.

Counting again, more honestly, the ten are not ten. Themes are a concept for
whoever writes a *theme*. Frames default to `ego`, so you never type one.
`derived` and `assumed_geometry` are honesty markers that matter only when you
are doing something unusual. And the three grep gates scan `modules/sim` — they
**do not apply** to a component's own plug-in folder at all.

What is genuinely unavoidable is **four**: the decorator, the context you are
handed, the `Prim` you return, and the style token you name. That happens to be
exactly the limit the design set out for itself (`L-3`, at most four concepts
before first use), which means the API was never the problem — **the
documentation was**, because it taught all ten at once.

So the fix was not to remove anything. It was a canonical minimal example of
fifteen lines that mentions none of the six optional ideas, with everything else
moved further down the page. `GT-8` still measures the consequence: *can a
developer who has only their own component checked out get a picture in under ten
minutes?* No feature substitutes for that number, and it has not been measured
yet.

---

## 7. A day in the life

```bash
# What can this library do?  (no repo, no Python knowledge, no docs)
sim probe ./df_sil.dll

# What can this RECORDING do — which cuts does it support?
sim probe modules/df/tests/carla_testruns/bsd/bsd_ego_lane_exit.mcap

# Run a scenario the COMPONENT owns, record everything, watch it
sim run modules/df/tests/carla_scenarios/bsd/ego_lane_exit.yaml

# Re-run just the driving functions against yesterday's recording
sim resim runs/<date>/bsd_ego_lane_exit.mcap --pipeline df_only.yaml

# Did it do what the scenario says it should?  (headless, exits non-zero)
sim check modules/df/tests/carla_scenarios/bsd/

# Open it in the window -- --plugin-root points at the BUILT library
# directory (the deployed copy, R-SIM-20) and makes df's own zones and
# ego box actually draw
vantage.bat modules\df\tests\carla_testruns\bsd\bsd_ego_lane_exit.mcap --plugin-root modules\df\build-sil-vs2026\src\platform\df_sil\Release
```

Two things to notice.

**None of those commands name a driving function.** The tool learns what exists
by asking the DLL. That is the whole design, compressed into six commands.

**Every path points into `modules/df`.** That is not incidental — see below.

**`--plugin-root` takes either a component's built library directory
(its deployed `sim/` and `config/` copies) or a source checkout — both
resolve. The component's own layer groups then appear in the Layers panel;
check their boxes to draw.**

### Vantage authors nothing

**Vantage is not a scenario editor** (`CR-SIM-3`). Scenarios are created and
owned by the module whose behaviour they describe: BSD's cases live in
`modules/df/tests/carla_scenarios/bsd/`, and perception's will live in
`modules/perception-core/`. The reason is not organisational tidiness — a
scenario's `expect:` block names component ports (`df.bsd.outputs.left.warning`),
so a scenario in `modules/sim` would put a function's name in the framework and
break `GT-1`.

Vantage **executes** a scenario the module owns, against a DLL the module built,
using calibration the module packed. It creates none of them. If you find
yourself adding a "new scenario" button to the player, the ownership boundary
has moved and something downstream will break at `GT-1`.

---

## 8. The hard part: recordings we did not make

This is the question that decides whether the tool is usable on day one, because
**every recording that exists today was made by something else.**

Open one of BSD's existing test runs and look at what is actually in it: objects,
ego dynamics, a camera frame, and the function outputs. That is all. There is no
radar, no detections, no perception layer — the old bridge *invented* the objects
in Python and handed them straight to `df`.

So that file can be resimmed exactly one way: **inject objects → run `df`.** It
cannot exercise perception, because nothing in it describes what perception
would have seen.

Now imagine the perception team next year. Their recordings will carry
*detections* and *tracks* and no objects at all — cut at a different depth, quite
possibly in a different file format. Also legitimate. Also supporting exactly
one cut, and a different one.

**There are two independent dimensions here, and keeping them independent is the
whole trick:**

| | Dimension | Example | Handled by |
|---|---|---|---|
| **1** | The **type** of recording | `.mcap` today, MF4 or CarMaker results tomorrow | A **codec** — ~4 read methods, registered by extension (`R-SIM-14`) |
| **2** | The **depth** the ports were cut at | objects-only vs detections-only | An **ingest map** + per-stage `mode:` (`R-SIM-23`, `R-SIM-10`) |

If those two were tangled, every new format would have to be re-solved for every
cut depth — four formats × four depths = sixteen problems. Kept apart, they are
four plus four.

**What an ingest map is.** A recording made by *this* framework needs none: the
recorder derives its topic list from the port manifests, so a topic simply *is* a
port name (`R-SIM-6`). For everything else, something has to say which topic
satisfies which port — and that something is a small declared file, living with
whoever owns those recordings:

```yaml
# modules/df/sim/ingest/carla_legacy.yaml
provides:
  df/gen_object_list: {port: objects, proto_type: adas.perception.DfObjList, origin: mocked}
  df/veh_dyn:         {port: egoDyn,  proto_type: adas.common.VehDyn,            origin: truth}
absent:
  vehSig: "never recorded by the old bridge; consumers see valid=0"
```

Three properties matter, and each one is a rule rather than a preference:

- **It is a declaration, never a computation.** Renaming and origin-tagging
  only — no unit conversion, no arithmetic, no derived signals. A preprocessing
  step that *computes* is an unversioned algorithm sitting between the recording
  and the component under test, so your resim would be reproducing the recording
  *plus whatever the preprocessor did*. That destroys the one property resim
  exists for (`R-SIM-5`).
- **It lives with the recordings, not with the framework.** `df/gen_object_list`
  is a fact about `df`'s recordings. Putting it in `modules/sim` is how the
  framework learns a function's name (`R-SIM-1`).
- **`absent:` is declared, not discovered.** A port a recording family never
  captured is a known fact. Saying so at load — *"this file has no `vehSig`,
  consumers will see `valid=0`"* — is an answer. Finding out at tick 0 is a
  bug report.

**And then the payoff:** given a recording and the manifests present, the tool
can *compute* which cuts are possible and tell you **before** you run:

```
$ sim probe modules/df/tests/carla_testruns/bsd/bsd_ego_lane_exit.mcap
  family     carla_legacy  (modules/df/sim/ingest/carla_legacy.yaml)
  provides   objects (mocked) · egoDyn (truth) · df.bsd.outputs (simulated)
  absent     vehSig — never recorded by the old bridge
  cuts       [source → df]                  OK
             [source → perception → df]     unsupported: no detections topic
```

Both dimensions are built — the codec table (`R-SIM-14`) and the ingest map
(`R-SIM-23`, closing defect `D14`).

---

## 9. Where to go next

| You want | Read |
|---|---|
| The real design and why each alternative was rejected | [sim_architecture.md](sim_architecture.md) |
| What was actually asked for, in the asker's words | [sim_requirements.md](sim_requirements.md) |
| The socket, in implementation detail | [sim_sil_contract.md](sim_sil_contract.md) — start at §0, it is written for a newcomer |
| What the picture must contain | [sim_visualization_spec.md](sim_visualization_spec.md) |
| The application itself | [sim_player.md](sim_player.md) |
| The build order and what proves each step | [sim_implementation_plan.md](sim_implementation_plan.md) |
| The exact symbols to type | [sim_api_reference.md](sim_api_reference.md) |
| Why every name is shaped the way it is | [sim_naming_and_diagnostics.md](sim_naming_and_diagnostics.md) |
| The rules, as a one-page index | `../../../.claude/rules/sim.md` |
