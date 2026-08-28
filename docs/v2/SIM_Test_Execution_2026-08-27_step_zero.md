# SIM — Test Execution Record — 2026-08-27 · step-zero campaign

**Second campaign of 2026-08-27.** The first (`SIM_Test_Execution_2026-08-27.md`)
was the CI gate. This one is the manual step-zero probe of the POC demo. Two
campaigns share a date, so the campaign name is appended to the filename —
`R-REQ-6` fixes one artifact per *campaign*, and the date alone no longer
distinguishes them.

**This record is evidence, not a specification.** It is exempt from the
2026-08-27 freeze on that basis, and is never edited after the fact — a later
campaign is a new file.

## Campaign

| | |
|---|---|
| Question | Can a recording carrying df's outputs be produced, and does `mode: measured` consume it? (`START_HERE.md`'s step zero) |
| Method | `D` demonstration — real `df_sil.dll`, real `simengine.exe`, Windows venv |
| Run by | a separate session, 2026-08-27 evening |
| Findings verified independently | **F-1, F-2, F-3, F-4** re-checked against source by a second session before this record was written. **F-5 not independently checked.** |
| Raw evidence | `modules/sim/logs/_step0/` (gitignored) |

## Result

**The mechanism works. The demo, as defined, does not — `F-3` blocks its shape.**

`sim resim --save` produces a recording carrying all four declared df output
ports plus its three inputs. `mode: measured` against that recording ran 100
ticks and injected every declared output **byte-identically**, including the 20
ticks where AEB genuinely fires (`t=2.300 s`, `critical_obj_id=150`).
`R-SIM-10`'s invariant holds on real data.

**But the first attempt passed vacuously** — both sides produced 100 empty
payloads, and a run fed *no input at all* was byte-identical to a correct one.
That false pass is what uncovered `F-1`.

---

## F-1 · `origin_for` matches strictly while payloads match tolerantly — **DEMO-BLOCKING**

**Every resim of a recording written before 2026-08-23 silently computes
nothing, exits 0, and warns about nothing.**

| Step | Evidence |
|---|---|
| `TopicToPortName` **strips** slashes | `src/simcore/runner/cycle_loop.cpp:92` |
| `PortNameToTopic` **always prepends** `/` | `cycle_loop.cpp:103` |
| `origin_for` uses exact `topics.find()` | `cycle_loop.cpp:292` |
| `meta.valid = origin != Origin::Unknown` | `cycle_loop.cpp:382` |
| df recordings carry `source/gen_object_list` — **no leading slash** | read from `modules/df/tests/carla_testruns/bsd/bsd_ego_lane_exit.mcap` |

Payloads resolve, origins miss, every input port of every stage is flagged
invalid every tick, and the component publishes neutral output
(`aeb_function.cpp:38` gates on exactly that).

**Proof:** adding *only* a leading slash to a legacy recording's topics, changing
nothing else, makes AEB fire at `t=2.300 s` — matching both the Python path and
the scenario's own dated `2.274 s ± 0.1` marker. Without it, `sim check` reports
`latent_pre_warning_active never became True`.

**Fix:** make `origin_for` look up tolerantly, the way the payload path already
does. Three candidate sites — inside `origin_for`, or normalise the reader's
topic index once at load, or push it onto `WP-12`'s ingest map. **Prefer
normalising the index once at load**: it fixes every consumer at one point rather
than the one that happens to be reported.

**This is the `WP-15b` follow-on's blind side.** That 2026-08-23 fix aligned the
**writers** onto the leading-slash convention, repairing newly-written recordings
and leaving every existing one silently broken. The reader side was never done.

**It also explains the three scenario failures parked earlier today**, and
retires a false green: `bsd_curve_r172_passby` "passed" only because both its
expectations assert the warning is `OFF` — it was passing because nothing fired.

## F-2 · Provenance is assigned by port direction, not carried — **DEMO-BLOCKING**

`src/simcore/abi/simcore.cpp:118`:

```cpp
info.provenance = (port.dir == "pro" && stage.mode == "simulate")
                    ? Provenance::kSimulated : Provenance::kMeasured;
```

Every `req` port is tagged `kMeasured` unconditionally; the source's real grade
is never carried forward. **Mocked CARLA stimulus is recorded as `measured`.**
The closed set has four values and this expression can only ever emit two.

Direct `R-SIM-12` violation — *"a report must never let 'perception was measured'
mean 'perception was a mock'"* — and it sits in the click-to-evidence path, which
is demo requirement **#22**. The comment shows the cause: it treats *direction*
(`req` vs `pro`) as though it were *evidence grade*.

**Fix:** carry the origin from the source topic's own provenance; fall back to
`kUnknown`, never to `kMeasured`.

## F-3 · A self-produced recording cannot be re-simulated — **BLOCKS THE DEMO'S SHAPE**

`sim resim --save` records `req` topics under the **consuming stage's** name
(`cycle_loop.cpp`'s `delivered_req_[stage_name + "." + port.name]`). Topics in
`logs/_step0/df_with_outputs.mcap`:

```
/df/aeb.outputs   /df/bsd.outputs   /df/aeb.compState   /df/bsd.compState
/df/objects       /df/egoDyn        /df/vehSig
```

The producing names (`source/gen_object_list`, `source/veh_dyn`) are **gone**.
Consequences, both demonstrated:

- **`mode: measured` works** — inputs stay wired to `source.*`, nothing executes,
  outputs inject.
- **`mode: simulate` cannot be spelled** — df's inputs must name `df.objects`,
  and `check_zero_delay_cycles` (`graph/grid.py:61`) rejects `df -> df`. The
  check examines `inputs:` for **every** stage regardless of mode.

So one recording cannot be toggled both ways. **The demo as written in
`DEMO_AND_SCOPE.md` §1 — one recording, `measured` and `simulate`, results
match — is not achievable today.**

This also contradicts `R-SIM-6`'s stated reason for recording outputs at all:
*"a recording containing every stage's outputs supports any cut point."* A
recording whose inputs are named after their consumer supports exactly one.

**Fix (design decision, not a bug fix — needs a call before coding):**

1. **Record `req` topics under their producing identity** (`source/...`), so one
   recording supports both directions. Matches `R-SIM-6`'s intent. Care needed:
   `delivered_req_` deliberately captures *post-mutation* bytes, so overrides
   must stay visible — likely a second topic or a tag, not a rename.
2. **Or** accept a two-recording demo (simulate against the original, measured
   against the self-produced) and rewrite the demo definition to match. Weaker:
   it no longer shows one file toggled two ways.

**Recommend 1.** Option 2 changes the demo for the third time to fit a defect.

## F-4 · The ingest map is never populated — not demo-blocking

`src/adas_sim/engine/bridge.py:386` emits `"ingest": [], "absent": []` with the
comment *"WP-12's ingest-map parser not landed yet"*. A legacy `df/*`-vocabulary
recording therefore feeds df literally nothing.

Not on the POC path — a self-produced `mcap` needs no ingest map. **But `WP-12`
reads 20/21 boxes done**, which overstates a feature that emits an empty list.
Worth a checkbox correction, and a reminder that *built* is not *working*.

## F-5 · `aeb.compState` is never emitted — not a defect

Pre-existing and deliberate (`aeb_function.cpp:35`). Recorded here so it is not
re-investigated as a measured-mode symptom. **Not independently verified.**

---

## Fix order for the next session

1. **F-1** — nothing else can be judged until resim computes. Re-run
   `sim check` over `modules/df/tests/carla_scenarios/` afterwards; expect the
   three parked scenario failures to clear.
2. **F-3** — take the design decision first, then implement. It changes what the
   demo *is*, so it outranks F-2.
3. **F-2** — provenance, before the demo claims click-to-evidence is truthful.
4. **F-4** — correct the `WP-12` checkbox; leave the parser to its own package.

Then `WP-28` (the launcher toggle, red item #8) is the remaining demo work.

**A C++ rebuild (`vs2026`) is required for F-1, F-2 and F-3** — all three are in
`simcore`.

## Re-run command

```
cd modules/sim && python scripts/ci_gate.py --artifact-dir logs/ci_gate/<name>
```

A later campaign is a **new file**, never an edit to this one (`R-REQ-6`).
