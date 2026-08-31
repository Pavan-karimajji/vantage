# SIM — Test Execution Record — 2026-08-31 — A15: config-bundle hash filled, copy-drift check proposed

**Scope:** two independent asks. (1) `misc/CONSOLIDATED_REQUIREMENTS.md` #16's
amber cause — an empty config-bundle hash on every recording — root-caused and
fixed (`SYS-0177`/`SYS-0123`, `R-SIM-3a`, `R-SIM-6`), the weak point inside
demo clause 5's (`#22`) own click-to-trace claim. (2) A proposal (not built) for
the smallest mechanical check that would have caught the "five layers in four
documents" copy-drift, scoped to the two named shapes: layer counts and
port-name spellings.

## 1. A15 — the config-bundle hash, filled

### Root cause

`graph.build._resolve_components` has always computed each `dll:`/`stubdll:`
stage's bundle directory (`bundle_dirs`, `<library_dir>/config`) — it is
`_validate_cross_component_agreement`'s own input, at LOAD. `Pipeline.load`
called that check and then **discarded `bundle_dirs`** — it was never stored
on the `Pipeline` instance, unlike `library_paths`, which `component_build_
shas()` already turns into a real hash. So no analogous `component_bundle_
shas()` method could exist, `cli/run.py`/`cli/resim.py` had nothing to pass
`core.manifest.build_manifest`'s `component_bundle_shas`/`component_bundle_
paths` kwargs, both defaulted to `{}`, and every `ComponentBuildInfo.config_
bundle_sha256` in every recording this framework has ever written has been
empty — exactly `RUN_THE_DEMO.md`'s own documented rough edge ("`config_
bundle_sha256` reads `unknown` — the calibration hash is not recorded yet,
only the build") and `misc/CONSOLIDATED_REQUIREMENTS.md` #16/#24's amber.

**Confirmed as the exact defect on the demo's own path**, not a nearby one:
`RUN_THE_DEMO.md` step 1 is `sim resim ... --save`, which is `cli/resim.py`'s
`--save` branch — `pipeline = Pipeline.load(args.pipeline, search=args.search)`
followed by `build_manifest(pipeline=pipeline, ...)` with no `component_
bundle_shas=`/`component_bundle_paths=` kwarg, then `overwrite_manifest_meta`
writes that `meta` over whatever `simengine`'s own C++ writer produced — so
the Python-built manifest is what a saved recording actually carries,
regardless of what `ComponentManifest.config_bundle_sha256` (a different,
component-reported field feeding the Resolved Run Spec, `runspec/emit.py:294`)
says.

### Fix

- `Pipeline.__init__`/`Pipeline.load` (`src/adas_sim/graph/build.py`): added a
  `bundle_dirs` parameter, stored as `self.bundle_dirs` (previously computed
  and dropped).
- Two new methods, mirroring `component_build_shas()`'s own shape and
  "absent, never an empty string" discipline (`R-SIM-25`/`NR-SIM-4`):
  - `component_bundle_paths()` — the resolved directory as a display string.
  - `component_bundle_shas()` — `config.project._bundle_sha256` (the same
    algorithm `ProjectModel.resolve` hashes with) over each stage's bundle
    directory, omitted when the directory does not exist on disk.
- `graph/modes.py::with_mode`/`with_port_mode` — all three `Pipeline(...)`
  reconstructions were missing `bundle_dirs=` (same drop `Pipeline.load` used
  to make, just at a second call site); fixed alongside, since a mode-toggled
  pipeline (`Vantage`'s own launcher path, `RUN_THE_DEMO.md` §4) would
  otherwise have silently lost the bundle directory again.
- `cli/run.py`/`cli/resim.py` — both `build_manifest(...)` calls now pass
  `component_bundle_paths=pipeline.component_bundle_paths()` and
  `component_bundle_shas=pipeline.component_bundle_shas()`, the same way they
  already pass `component_build_shas=pipeline.component_build_shas()`.

`orchestrate/batch.py`'s own `_write_outcome_manifest` was **not** touched —
it never loads a `Pipeline` at all (`pipeline_path=` only, no `pipeline=`), so
`components=()` there regardless; that is a different, pre-existing gap
(no `component_build_shas` either) and is out of this row's scope.

### Proof

`tests/unit/test_a15_config_bundle_hash.py`, new:

- `component_bundle_shas()` matches a direct `_bundle_sha256` of the resolved
  directory; `component_bundle_paths()` reports it as a string.
- Both are correctly **absent** (never `""`) for a `components=`-supplied
  stage and for a bundle directory that does not exist on disk yet — the
  same honesty discipline `component_build_shas()` already follows.
- **End to end:** `build_manifest(pipeline=..., component_bundle_shas=
  pipeline.component_bundle_shas(), ...)` produces a `RunManifest` whose
  `components[0].config_bundle_sha256` is the real hash, not `""`.
- **The actual claim in #22/`DEMO_AND_SCOPE.md` §1** ("click an object and see
  which signal, tick, file and build produced it") is proven at the surface
  that answers it: a `Session` built with that `RunManifest` fed to `diagnostics.
  evidence.evidence()` reports `record.config_bundle_sha256` equal to the real
  hash, and `format_evidence()` — the exact function `cli/explain.py --at` and
  the player's evidence panel both call (`GT-9`, one producer two formatters)
  — renders it, **not** `"unknown"`.

**Verified**, native `vs2026` Python (`.venv`, via WSL2 interop — no Linux
path exists for this checkout's own Python 3.12 syntax, `config/layers.py`'s
`class Provenanced[T]`, so a WSL-native `python3.10` cannot even import
`adas_sim`):

```
.venv\Scripts\python.exe -m pytest tests\unit\test_a15_config_bundle_hash.py tests\unit\test_d7_pin_builds.py tests\unit\test_c1c_pipeline.py tests\unit\test_b2_evidence.py -q
69 passed in 6.68s
```

Full unit suite: **973 passed, 1 skipped** (unchanged skip, pre-existing).
Full system suite: **96 passed, 9 skipped** (pre-existing, dll-build-dependent
skips), **1 failed** — `test_conan_editable_add_resolves_adas_sim`, a Conan
remote-credentials/network error (`adas-local` asks for a username
interactively) unrelated to this change; unmodified by this pass, not
investigated further here.

**Not run**: an actual `sim resim --save` against a real `df_sil.dll` +
packed config bundle, the way `RUN_THE_DEMO.md` step 1 does it, followed by
`sim explain ... --at 46` printing a real `config_bundle_sha256` line. That
needs `df`'s `sil`/`sil_viz` targets built (`vs2026`) and a packed bundle on
disk, neither present in this pass — the unit-level proof above exercises the
identical code path (`Pipeline.component_bundle_shas` → `build_manifest` →
`RunManifest.components[].config_bundle_sha256` → `evidence()` →
`format_evidence()`) with a fixture bundle standing in for a real packed one,
same "a plain temp file stands in for a resolved library" precedent
`test_d7_pin_builds.py`'s own docstring already established for `component_
build_shas`. Running the real demo command to see a live hash print is a
named follow-on, not done here.

**Not fabricated**: no hash was invented anywhere in this pass. Every hash
printed by the new tests is computed by `_bundle_sha256` over a real,
on-disk fixture directory; a stage with no such directory correctly still
reports nothing (`{}`), never a placeholder.

## 2. Proposed — a mechanical check for the copy-drift family (not built)

### The pattern, five times

| # | Where | The one fact | The copies | What broke |
|---|---|---|---|---|
| **F-1** (2026-08-28) | topic spelling | the canonical form a topic takes (`CanonicalTopic`, centralized in `io/meta.cpp`) | every reader that used to match topics its own way — including, discovered **2026-08-30/31 by accident** (a stale `sil` rebuild), three `viz` gtest fixtures still asserting the pre-canonicalization spelling (`"df.a"` instead of `"/df/a"`) | fixtures silently stopped matching real output; the tests kept "passing" against fixtures, not against the codec |
| **F-7** (2026-08-28) | what a port is keyed by | bare `fn.out` vs. topic `/stage/fn.out` | `graph.feasible.feasible_cuts`, `Session.feasible_cuts`, `resolve.probe.describe_recording` — three modules, each internally consistent, each separately tested | the pre-run feasibility query said "infeasible" on a recording that then ran 100 ticks fine; no test ever fed a real recording through all three |
| **F-8** (2026-08-28) | the evidence-panel label column width | `cli/explain.py`'s `{field:<20}` and its test's `line[:20]` | two literal `20`s | adding a longer field name (`component_library_sha256`) misaligned CLI output against what the test parsed, until `GT-9` caught it |
| **#5** (2026-08-28) | "recording ingest is wired" | the emitter, the engine's spec parser, and a `Translator` that had existed for months uncalled — three legs of one requirement, each real on its own | none — no check joined them | the status mark read amber ("partly") when the true state was "one leg only," discovered only when a real foreign-vocabulary recording was pushed through and came out empty |
| **five layers → six** (2026-08-30/31, the trigger for this ask) | how many layers `SW-0021`/`SYS-0088` require | the requirement text, `UT-layers-11`, `SYT-HST-02`, `SYT-SCP-16`/`17` | four documents, one number each | amending the requirement to six (`WP-22`) did not cascade; the three test-spec mentions stayed "five" until fixed by hand 2026-08-31 |

Every row is `R-REQ-11`'s own diagnosis ("the two halves drift while each
document passes inspection on its own") at a smaller grain than trace links —
a spelling, a keying convention, a literal, a wiring claim, a count — with
**no** mechanised check joining the copies in any of the five cases. `R-REQ-11`
itself is applied today only to `Verify`/`Serves` trace links.

### What is proposed

**Two narrow, mechanical checks — scoped exactly to layer counts and
port-name spellings, per the ask, not a general "no duplicate literals"
scanner** (that would be its own, much larger, design question):

1. **Layer-count check.** One authoritative source: the number of
   `@layer_provider`-registered functions the build actually produced
   (`gen_viz_shim.py`'s own generated count, already a build gate per `R-SIM-22`
   — `WP-22`'s record calls it "a real build-time gate"). Grep every `docs/v2/`
   requirement and test-spec document for a layer-count assertion — a fixed
   pattern: a requirement's own stated cardinality (`SW-0021`/`SYS-0088`'s
   "exactly N layers") and any `UT-`/`SYT-` row whose **name or body** states a
   layer count (`UT-layers-NN`'s own docstring, `SYT-HST-02`/`SYT-SCP-16`/`17`'s
   expected-count assertions). Fail if any disagree with the build's own
   number, naming every document and line found, same "naming every candidate,
   never guessing" discipline `R-SIM-15`'s override-address check already uses.

2. **Port-name-spelling check.** One authoritative source per recording: the
   codec's own `CanonicalTopic` output (or, for a hand-built fixture, the
   spelling `RecordingIndex.topics` actually reports). Grep test fixtures and
   layer-provider `requires=`/`self.<port>`/`source.<port>` literals for a
   port/topic-name string, and flag one that does not match the canonical form
   a *current* build of the relevant codec would produce for the same
   logical port — the exact shape that let three `viz` fixtures assert
   `"df.a"` for months after `450031e` made the real answer `"/df/a"`.

**Where it runs:** `scripts/check_invariants.py` — already the mechanised
home for this module's other structural greps (`GT-1`'s middleware-free
`src/` scan, `GT-11`'s `modules/*/sim/**` port-reference scan), run at the
same point `trace_check.py` already runs ("before any `docs/v2/` commit"),
so it fires on the ordinary gate rather than needing anyone to remember it —
same reasoning `R-SIM-1`'s own grep enforcement gives for living there rather
than in a person's head.

### What it would and would not have caught

| # | Caught? | Why |
|---|---|---|
| **five layers → six** | **Yes** | Exactly a layer-count assertion, in exactly the four documents that drifted — this is the check's primary target. |
| **F-1**'s fixture half (the 3 stale `viz` tests) | **Yes** | Exactly a port/topic-name-spelling literal, stale against the codec's real canonical output — the check's second target. It would have failed the same day `450031e` landed, not four days later by accident. |
| **F-7** | **Yes** | Also a port-name-spelling disagreement — three modules keying the same logical port two different ways (bare vs. topic-qualified). The check as scoped (compare a literal port/topic reference against the canonical form) catches a *spelling* mismatch; it would need to be read broadly enough to include "keying convention," which is the same fact under a different name — worth stating explicitly rather than assuming, since F-7's own record calls it "two correct halves with incompatible key conventions," not a misspelling. |
| **F-8** | **No** | The duplicated fact is a numeric column width (`20`), not a layer count or a port name — outside the stated scope. Catching this needs a separate, general "duplicated literal" check, named but not designed here. |
| **#5** | **No** | The duplicated/missing fact is "this leg is wired," a wiring/dead-code claim — not a count and not a spelling. No grep over counts or names touches it; it needs an integration test that exercises all three legs together, which is a test-coverage question, not a mechanical-check question. |

**Net: 3 of 5 caught** (the two the ask named as in-scope, plus F-7 on a
generous but stated reading of "spelling"). **F-8 and #5 would not be**,
each for a stated reason — both are real instances of the same family but a
different shape, and forcing the narrow check to cover them would widen it
past "layer counts and port-name spellings only," which is exactly the scope
creep this proposal is trying not to commit on the author's behalf.

**Not built.** No code under `scripts/check_invariants.py` was touched in
this pass.
