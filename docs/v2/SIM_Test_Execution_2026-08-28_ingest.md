# SIM — Test Execution Record — 2026-08-28 · the ingest map, wired (`#5`)

**Fifth campaign of 2026-08-28**, after the step-zero fixes, `_wp28` (`F-7`),
`_wp35` (the demo) and `_f8` (the demo's fifth clause).

**This record is evidence, not a specification.** Never edited after the fact;
a later campaign is a new file (`R-REQ-6`).

## Campaign

| | |
|---|---|
| Question | Close `CONSOLIDATED_REQUIREMENTS.md` #5 — read a recording we did not produce — and does `bsd_curve_r172_passby` stop being a false green? |
| Method | `T` (2 new cases + both suites) · `D` (a real legacy-vocabulary recording through the real engine) |
| Platforms | `ubuntu_gcc` **and** `vs2026` — the fix spans Python and `simcore` |
| Evidence | `logs/_step0/after_ingest.mcap`, `logs/ci_gate/2026-08-28-ingest/` |
| Committed | **No.** Working tree only. |

## Result

**#5 is closed: red → green.** A foreign-vocabulary recording now feeds its
module real data.

**`bsd_curve_r172_passby` did NOT go red. It stayed 2/2 PASS — and the green is
now real rather than vacuous.** That is the honest outcome, and it is not the
one the task anticipated. Detail below, including a new coverage gap it exposed.

---

## What was actually broken

Three legs; the brief named one.

| Leg | State before |
|---|---|
| `ingest/map.py` — the parser | **real and tested** since `WP-12` |
| `simcore/io/translate.cpp` — `Translator::Apply` | **real and tested** since `IMP-0032` |
| Anything joining them | **did not exist** |

`bridge.py::pipeline_to_run_spec` emitted a hardcoded
`{"ingest": [], "absent": []}` under a comment saying the parser had not landed
— long after it had. But emitting the table would not have been enough on its
own: **`load.cpp` never parsed `sources[].ingest`, and a `grep` for
`Translator` across `src/` returned no constructor call at all.** Both missing
legs were fixed here, or the emitted rows would have been read by nobody and
the recording would still have fed nothing — a change that looks like a fix and
is not.

## The fix

| File | Change |
|---|---|
| `engine/bridge.py` | `_ingest_for(recording)` — picks the applicable map by the recording's **own topics** (`IngestMap.matches`), never by filename |
| `runspec.hpp` / `runspec/load.cpp` | `SpecSource.ingest`/`.absent` parsed; optional on read, so every older spec still loads |
| `io.hpp` / `io/translate.cpp` | `TranslatingReader` — a `Reader` decorator; `Translator::PortFor`; keys canonicalised |
| `abi/simcore.cpp` | wraps the reader **only when the spec carries rows** |

Two things deliberately not done: no parser, schema or vocabulary was added to
`simcore` (`SW-0032` puts those in Python, and a second validator here would be
the copy that rule exists to prevent), and the map still does only what
`R-SIM-23` allows — **rename and tag, never compute**.

### Two real defects found while wiring, both fixed

1. **`unresolved()` refused the first attempt, correctly.** Emitting a row's
   `port` as `source.gen_object_list` puts reference grammar into a *Resolved*
   Run Spec, which `ANL-SW-01` forbids outright. The fix was not to weaken the
   check but to emit **topic → topic** (`/df/gen_object_list` →
   `/source/gen_object_list`) and let the engine derive the port name with
   `TopicToPortName`, the transform it already uses for every other topic.
   Nothing new learns the reference grammar. The check earned its keep.
2. **Key-spelling mismatch.** A map is authored in the recording's own
   vocabulary (`df/gen_object_list`); a reader's index and messages are
   canonical (`/df/gen_object_list`). Comparing them raw would have made every
   row silently fail to match the very recordings it was written for — `F-1`
   again, one layer up. `Translator` now canonicalises on both insert and
   lookup.

## Demonstrated

`bsd_curve_r172_passby.mcap` (topics `df/gen_object_list`, `df/veh_dyn`),
resimmed through `df_only.yaml` — the same command as 2026-08-27:

| `/df/…` topic | Before | After |
|---|---|---|
| `source/gen_object_list` | 218 messages, **all empty** | 218, **174 distinct**, none empty |
| `source/veh_dyn` | 218, **all empty** | 218, **109 distinct**, none empty |
| `bsd.outputs` | 218, **all empty** | 218, **3 distinct**, none empty |

df is genuinely computing.

## `bsd_curve_r172_passby`: still green, and now honestly so

The brief expected this to go red and said to report it red if it did. **It did
not.** Decoded from the new recording:

```
/df/bsd.outputs messages : 218  (non-empty payloads: 218)
right.warning values     : {OFF: 173, ON: 45}
left.warning  values     : {OFF: 218}
```

`right.warning` **does** fire — 45 ticks, **first at t=7.374 s, last at
t=9.597 s**. Its expectations are:

- `EXP-1` — `right.warning == 'OFF'` **over during [0.000, 5.000]**
- `EXP-2` — `left.warning == 'OFF'` **always**

The firing is entirely **outside** `EXP-1`'s five-second window, and `left`
never fires at all. So both expectations are true of real computed data, and
the pass is legitimate.

**What changed is the reason, not the verdict.** Before, every payload was
empty, `right.warning` decoded to its default `OFF`, and the assertion could
not have failed for any input. Now df receives 174 distinct object lists,
computes a warning that genuinely turns on and off, and the assertion
discriminates. The false green is gone; a true green replaced it.

### New finding: the scenario is under-asserted

Now that data flows, something nobody could see before is visible: **the BSD
warning fires from t≈7.4 s to t≈9.6 s and no expectation covers it.** The
recording is ~10.9 s; `EXP-1` asserts only the first 5 s and `EXP-2` asserts a
side that never activates. The scenario's most interesting 2.2 seconds are
unasserted.

Not fixed here — writing an expectation for it is authoring a test, and the
brief said not to adjust the scenario. Recorded so it is not lost.

## Verification

| Check | Before | After | Verdict |
|---|---|---|---|
| `ctest` `ubuntu_gcc` | 220/220 | **220/220** | pass |
| `ctest` `vs2026` | 214/215, 1 failed | **214/215, 1 failed** | the same pre-existing `UtEdg08Reproducer` Windows temp-dir failure, verified pre-existing on 2026-08-28 |
| `pytest` | 1537 collected, 1 failed | **1537 collected, 1 failed** | +2 new cases; the failure is the parked Conan test |
| `sim check` | 18 scenarios, 0 failed | **18, 0 failed** | pass |
| `check_invariants` + 5 others | clean | clean | pass |
| `check_trace.py` | 155 `R-REQ-9` | **155** | unchanged — parked |
| `ci_gate.py` | `status=fail` | **`status=fail`** | same two parked inputs |

`ci_gate_config.yaml` untouched; no floor moved, no tolerance widened, no test
skipped or deleted. The gate's own `known_flake` line
(`test_b3_viewport_controls`) is a pre-declared, tolerated-by-name entry, not a
new failure.

### The regression tests

`tests/system/test_d15b_engine_bridge.py`, 2 new cases:

- a foreign-vocabulary recording resolves a **real** table, and neither side of
  any row carries reference grammar;
- **the planted violation** — a recording this framework produced resolves **no**
  table, so the first case cannot pass for any file at all.

## Also fixed

The **stale plug-in-root tooltip** in `scripts/gui.py`. It told the user to
point at the source checkout `..\df` and to avoid the built directory, citing
`AR-61` as open. `AR-61` was closed and re-verified at `WP-34a`, and the native
host cannot load a bare checkout at all — the classifier already refuses it
(`No built library (.dll/.so) here`) while the tooltip recommended it. Corrected
to name the deployed viz build, and to say the coloured status line is the
authority.

## Still not true

- **`sim probe` still reports `provides (0)`.** It reads `Session.provides`,
  a different path from the engine's; this fix wired the engine. Not the same
  gap, and not touched.
- `F-6`, `WP-12`'s remaining scope, Movement B and `#20` — untouched, as
  instructed.

## Re-run commands

```
cd modules/sim
python -m pytest tests/system/test_d15b_engine_bridge.py -q
.venv\Scripts\sim.exe resim ..\df\tests\carla_testruns\bsd\bsd_curve_r172_passby.mcap ^
  --pipeline ..\df\sim\pipelines\df_only.yaml --save logs\_step0\after_ingest.mcap ^
  --search ..\df\build-sil-vs2026\src\platform\df_sil\Release ^
  --config ..\df\src\project\base\default.yaml
python scripts/ci_gate.py --artifact-dir logs/ci_gate/<name>
```

A later campaign is a **new file**, never an edit to this one (`R-REQ-6`).
