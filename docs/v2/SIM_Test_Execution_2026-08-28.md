# SIM — Test Execution Record — 2026-08-28 · step-zero fixes `F-1`…`F-4`

**This record is evidence, not a specification.** It is exempt from the
2026-08-27 freeze on that basis, and is never edited after the fact — a later
campaign is a new file (`R-REQ-6`).

## Campaign

| | |
|---|---|
| Question | Do `F-1`, `F-2`, `F-3` and `F-4` from `SIM_Test_Execution_2026-08-27_step_zero.md` close, and does anything regress? |
| Method | `T` test (both `ctest` suites, `pytest`, `ci_gate.py`) + `D` demonstration (real `df_sil.dll`, real `simengine.exe`, real recordings) |
| Platforms | `ubuntu_gcc` (WSL) **and** `vs2026` (native, via WSL2 interop) — all three code fixes are in `simcore` and needed the `vs2026` rebuild |
| Raw evidence | `modules/sim/logs/_step0/`, `modules/sim/logs/ci_gate/2026-08-28/` (both gitignored) |
| Committed | **No.** Working tree only. |

## Result

**`F-1`, `F-2` and `F-3` are closed and demonstrated. `F-4` is corrected as a
document change. The gate still exits non-zero, entirely on two already-parked
items. One new finding, `F-6`, is recorded rather than fixed.**

The headline: **the demo's own gesture now works.** One self-produced recording,
the `mode:` field the only thing that differs, both directions byte-identical,
on data where the algorithm actually fires.

---

## Verification results

| Check | Before (this branch, immediately prior) | After | Verdict |
|---|---|---|---|
| `ctest` `ubuntu_gcc` | 218/220 (2 flaky under `-j4`) | **220/220** | **pass** |
| `ctest` `vs2026` | 214/215, 1 failed, 2 skipped | **214/215, 1 failed, 2 skipped** | pre-existing failure, unchanged |
| `pytest` | 1515 passed · **1 failed** · 11 skipped | 1515 passed · **1 failed** · 11 skipped | no regression |
| `sim check` (`modules/df/tests/carla_scenarios/`) | 18 scenarios, **3 failed** | 18 scenarios, **0 failed** | **the three cleared** |
| `check_invariants.py` | clean | clean | pass |
| `check_headers` / `closed_sets` / `no_duplication` / `artifact_kinds` / `time_units` | clean | clean | pass |
| `check_trace.py` | 155 `R-REQ-9` violations | **155** | unchanged — parked (`WP-31`) |
| `ci_gate.py` | `status=fail` | **`status=fail`** | see *Why the gate still fails* |

### The one `vs2026` failure is pre-existing

`UtEdg08Reproducer.WritesARealPackageWithEveryDeclaredPiece` throws
`remove_all: The process cannot access the file because it is being used by
another process` on `%TEMP%\ut_edg_08_out`. **Verified pre-existing**: the
change set was stashed, `vs2026` rebuilt, and the same test failed with the
identical message. It passes on `ubuntu_gcc` with the changes applied, so it is
a Windows file-handle issue inside the test, not a logic regression. Not
investigated further — out of this campaign's scope, named rather than absorbed.

### The one `pytest` failure is pre-existing and parked

`test_a1_install.py::test_conan_editable_add_resolves_adas_sim` fails on a Conan
remote credential prompt (`Remote 'adas-local' username: ERROR: EOF when reading
a line`). Measured identically with the change set stashed. Already on
`START_HERE.md`'s parked list as *"Conan editable test · `WP-31` scope"*.

### Two `ubuntu_gcc` tests are flaky under `-j4`, not broken

`UtExe04Restart.*` (both cases) failed in the `-j4` baseline run and passed
serially, and passed in every later run. Recorded so the next campaign does not
chase them.

### Why the gate still fails

`ci_gate.py` exits 1 on exactly two inputs, both already parked and neither
touched by this work: the **155 `R-REQ-9` citations** (`WP-31`) and the
**Conan editable test** (`WP-31`). Every other sub-check is clean and
`sim check` is now fully green. **The gate was not made to pass by relaxing
anything** — no floor was moved, no tolerance widened, no test deleted.

---

## `F-1` · topic lookup made tolerant — **CLOSED**

**Fixed as the record recommended**: normalise the reader's topic index once at
load, not `origin_for` alone.

- `io::CanonicalTopic` (`include/simcore/io.hpp`, `src/simcore/io/meta.cpp`) is
  now the single definition of the canonical topic spelling, `"/<producer>/<port>"`.
- `McapReader` builds its index once in `Open()` (`BuildTopicIndex`) and
  `Describe()` returns the cache — which also removes a full map rebuild that
  was happening on **every tick** from inside `StepOnce`.
- `McapReader::Pull` and `ErgReader` canonicalise too, so no recording's own
  historical spelling leaks above `io` at all.
- `runner::PortNameToTopic` now **delegates** to `io::CanonicalTopic` instead of
  re-implementing it. This is the part that matters structurally: the index and
  the lookup are no longer two copies free to drift, which is what the defect
  was.

**Demonstrated.** `sim check` over `modules/df/tests/carla_scenarios/`, with the
real `df_sil.dll`:

```
aeb_canonical_10mps_30m              1/1 PASS
  latent_pre_warning_active -> True @ 2.300s (target 2.283 +/-0.100)
aeb_closing_ego20mps_lead10mps_30m   1/1 PASS
  latent_pre_warning_active -> True @ 2.300s (target 2.274 +/-0.100)
bsd_ego_lane_exit                    1/1 PASS
  right.warning -> 'NORMAL' @ 1.050s (target 1.000 +/-0.100)
```

All three previously reported *"never became True"*. The firing time matches the
markers measured on 2026-08-03 against these same recordings.

### `bsd_curve_r172_passby` reports `2/2 PASS` and is still a false green

Stated explicitly because a green line here is misleading. That recording
carries the legacy `df/*` topic vocabulary (`df/gen_object_list`,
`df/veh_dyn`), which needs the **ingest map** — `F-4`, `WP-12`, deliberately not
written in this pass. Re-measured today, after `F-1`: it still resims to
completion, exit 0, 218 ticks, with `/source/gen_object_list` and
`/source/veh_dyn` **empty on all 218 ticks**. Both its expectations assert a
warning is `OFF`, so it passes because nothing fires. `F-1` did not fix it and
was never going to; only the ingest map will.

## `F-2` · provenance carried, not assigned by direction — **CLOSED**

`BuildOutputTopics` (`src/simcore/abi/simcore.cpp`) now takes the input
recording's own index and carries each fed topic's grade forward, falling back
to `kUnknown` — **never** `kMeasured`. Only a `simulate` stage's `pro` port is
asserted as `kSimulated`, which is the one grade the engine is entitled to claim.

**Demonstrated.** Topics of a recording produced from a `mocked` CARLA source:

```
/df/aeb.outputs           origin=simulated      <- computed this run
/source/gen_object_list   origin=mocked         <- carried (was: measured)
/source/veh_dyn           origin=mocked         <- carried (was: measured)
/df/vehSig                origin=unknown        <- unwired; nobody established a grade
```

Before this change every one of those fed topics read `measured` — a mock
reported as a measurement, which is exactly what `R-SIM-12` forbids.

## `F-3` · a self-produced recording can now be re-simulated — **CLOSED, option 1**

Taken as instructed: **`req` topics are recorded under their producing
identity**. Implemented in `runner::RecordedTopicFor`, which is now the single
derivation used by **both** `Runner::Construct` (which writes the messages) and
`BuildOutputTopics` (which writes the index) — they derived it separately
before, which is `F-1`'s defect one level up.

**Post-mutation bytes stay visible via a second topic, not a rename**, as
required. Where a declared `RunSpec::mutations` entry touches the port, the
producing topic keeps the true upstream value and an additional topic under the
consuming address carries what the component was actually handed, tagged
`kOverridden` in the index (`R-SIM-15`). With no override declared the two would
be byte-identical, so only the producing topic is emitted.

Three consequences, all deliberate and all covered by updated tests:

1. **Topics are claimed `pro`-before-`req`, in two passes.** A `req` port
   resolving onto a topic a `pro` port owns must lose, or a `req` port marked
   `excluded` could suppress a `pro` port marked `full`. Two passes remove the
   ordering hazard instead of relying on `spec.order` being topological.
2. **A consumer of another stage's output no longer gets its own topic** — four
   declared ports can yield three topics. One signal, one topic, one value;
   which port received it is answerable from the spec's wiring, exactly as
   `df_only.yaml` already resolves `objects` against its producer.
3. **Transport publishes under the topic's identity**, not the consuming
   address, so the recording and the live feed cannot disagree about a name.

**Demonstrated — this is the demo's own gesture**, on `vs2026` (the platform
that has a built `df_sil.dll`; the `ubuntu_gcc` side was built and unit-tested
but not driven end to end). One self-produced recording, `mode:` the only
difference, `df_only.yaml` used *unchanged* for the simulate direction:

```
/df/aeb.outputs   /df/aeb.compState   /df/bsd.outputs   /df/bsd.compState
/source/gen_object_list   /source/veh_dyn   /df/vehSig
```

| Direction | Result |
|---|---|
| `mode: measured` (replayed from the file) | 100 ticks, AEB fires 20 ticks, first @ `t=2.300 s`, `critical_obj_id=150` |
| `mode: simulate` (recomputed by the real DLL) | 100 ticks, AEB fires 20 ticks, first @ `t=2.300 s`, `critical_obj_id=150` |
| `aeb.outputs` / `bsd.outputs` / `bsd.compState` | **byte-identical between the two** |

Before this change the simulate direction could not be expressed at all: the
inputs were named after their consumer, so a pipeline had to wire `df.objects`,
and `check_zero_delay_cycles` rejected `df -> df`.

Two asymmetries in that comparison, both explained, neither a defect:
`/df/aeb.compState` is empty in both (`F-5`, deliberate in `df`); `/df/vehSig`
is written only by the simulate direction, because a `measured` stage executes
nothing and so is handed nothing to record for an unwired input.

## `F-4` · `WP-12` checkbox corrected — **CLOSED (document only)**

The ingest-map parser was **not** written; it keeps its own package, as
instructed. `IMP-0011` in `SIM_Implementation_Plan_v0.1.md` carried a bare
`[~]` whose text ended *"left open rather than attempted under this label"* —
a disposition, not the `closed by <command or condition>` clause `R-REQ-6a`
requires, so the box recorded that somebody was unsure rather than where to
resume. Corrected to name the closing condition, and to record the measured
severity: the effect on a non-native recording is **total, not partial** (218
ticks of empty input, exit 0). `trace_check.py` re-run: **PASS**, chain closes
both directions.

## `F-6` · validity is inferred from evidence grade — **NEW, not fixed**

Found while fixing `F-3`. Recorded rather than fixed, because it is a fifth
finding outside this pass's instructed scope.

`cycle_loop.cpp` derives a port's validity from its provenance:

```cpp
meta.valid = value.origin != bus::Origin::Unknown;
```

`bus::Origin::Unknown` carries **two** meanings: *"no value was ever published
for this port"* (`PortBus::Get`'s never-produced branch) and *"a value exists,
its evidence grade is unknown"* (a recording with no `topic_provenance` block).
The write pass makes the same conflation for `pro` topics.

**Consequence:** a recording carrying no provenance metadata — a foreign or
supplier file, precisely the case `UT-IO-19` exists for — has every input
flagged invalid, and the component under test publishes neutral output. That is
`F-1`'s symptom reached by a second route, and `F-1` does not fix it.

Not hit by the demo path: every `df` recording that binds declares a real grade.
It surfaced as a test fixture (`WriteAbiPortRecording`) that never declared one,
where the producing stage's own topic silently dropped out of the recording; the
fixture now declares `kMeasured`, as every real recording does.

**Fix, when scheduled:** give `bus::PortValue` an explicit "was this ever
published" flag set by `PortBus::Get`, and use it wherever `origin == Unknown`
is currently standing in for absence. This is the same category error as `F-2`
— direction is not a grade, and neither is *absence*.

---

## Files changed

| File | Fix |
|---|---|
| `include/simcore/io.hpp` | `F-1` — `CanonicalTopic` declared |
| `src/simcore/io/meta.cpp` | `F-1` — `CanonicalTopic` implemented |
| `src/simcore/io/codecs/mcap.cpp` | `F-1` — index built once at load, canonical; messages canonical |
| `src/simcore/io/codecs/erg.cpp` | `F-1` — index and messages canonical |
| `include/simcore/runner.hpp` | `F-3` — `RecordedTopic::post_mutation`, `ProducerAddressOf`, `MutationTouches`, `RecordedTopicFor` |
| `src/simcore/runner/cycle_loop.cpp` | `F-1` delegation · `F-3` two-pass topic derivation, value selection, transport naming |
| `src/simcore/abi/simcore.cpp` | `F-2` — provenance carried · `F-3` — shared topic derivation |
| `docs/v2/SIM_Implementation_Plan_v0.1.md` | `F-4` — `IMP-0011` `closed by` clause + measured severity |
| `tests/unit/test_ut_io_meta.cpp` · `test_ut_io_erg_reconstruct.cpp` | canonical topic spellings |
| `tests/unit/test_ut_run_core.cpp` | `F-3` — asserts the producing-identity naming and the dedup |
| `tests/unit/test_mut_core.cpp` | carries its mutations on the spec, as a real run does |
| `tests/integration/test_it_transport.cpp` | `F-3` — port set is two names, not three |
| `tests/integration/test_ut_abi_writer_and_resolver.cpp` | `F-3` — both halves of an overridden input asserted; fixture declares provenance |

## Re-run commands

```
cd modules/sim
cmake --build build-gtest-ubuntu_gcc -j && ctest --test-dir build-gtest-ubuntu_gcc
cmake --build --preset gtest-vs2026 --parallel && ctest -C Release      # from build-gtest-vs2026
python scripts/ci_gate.py --artifact-dir logs/ci_gate/<name>
sim check ../df/tests/carla_scenarios --search <df_sil dir> --config ../df/src/project/base/default.yaml
```

A later campaign is a **new file**, never an edit to this one (`R-REQ-6`).
