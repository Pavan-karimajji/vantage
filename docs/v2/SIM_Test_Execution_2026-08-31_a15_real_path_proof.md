# SIM Test Execution — 2026-08-31 — `A-15` config-bundle-hash fix, proven on the real path

**Campaign:** `A-15`'s fix (`docs/v2/SIM_Test_Execution_2026-08-31_a15_bundle_hash_and_copy_drift.md`,
committed `f10a388`/`sim`, `405bb22`/superproject) was proven in Python only —
a unit test against a hand-built `Pipeline`, no real `df_sil.dll`. This
campaign runs it on the real path: a real `vs2026` build of `df` with its
packed config bundle, the demo's own `sim resim --save`, and a read-back of
`config_bundle_sha256` from both the recording and the evidence chain `sim
explain` / the player's evidence panel share (`R-SIM-25`: one producer, two
formatters).

## 1. Build `df` for `vs2026` with a packed config bundle

A full `build.bat -t sil -p vs2026` (the documented path, `RUN_THE_DEMO.md`
§0) was attempted first and failed at the Conan step — the same
environment-credential gap already named and declared not-doing for `WP-01`'s
Conan-editable test (`docs/v2/SIM_Test_Execution_2026-08-31_ci_descope.md`):
`ERROR: Package 'protobuf/3.21.12' not resolved: EOF when reading a line.
[Remote: adas-local]`. `conan install --update` cannot complete non-interactively
in this sandbox.

**Worked around by building what `build.bat` itself would have invoked,
skipping only the Conan re-resolution step** (the dependency graph was
already resolved and cached from a prior successful install in this same
`build-sil-vs2026` tree — `cmake --build` against the existing configured
Visual Studio solution needs no Conan call at all):

```
cmake --build build-sil-vs2026 --config Release --target df_sil
```

This is a **real, full relink** — MSBuild output shows `df_common`,
`fn_aeb`, `fn_bsd` and `df_sil` all rebuilding, not a no-op — and it ends with
the bundle-packing step that matters here, run for real, not skipped:

```
Packing config bundle for df_sil	Packing plug-in bundle for df_sil
packed config bundle at .../df_sil/Release/config (bundle.sha256=966f0e3017a4d85a08a3dc6eaf5bad4f66b4103f59c1686d5d33a96a0204d980)
packed plugin bundle at .../df_sil/Release/sim (sha256=07531c48c2a8637a2955827332e7a12c5aaf9528f9d4ed9eaa5e77f49c962cb3)
```

**The bundle is genuinely packed on this path** — `config_bundle_pack`
(`R-SIM-3a`) ran for real and wrote
`build-sil-vs2026/src/platform/df_sil/Release/config/{bundle.sha256,
default.yaml, df_sil.ports.yaml, vehicle/ego_params.yaml}`. Independently
verified: `sha256sum df_sil.dll` → `dec40de2a39fd07190633a7510d56e3e103a70f28c07063d2530738d48d0de04`,
matching `sim explain`'s own `component_library_sha256` below exactly.

`df`'s own tree was clean at `efc1477` (HEAD, matching the superproject
pointer) save one unrelated pre-existing modification
(`src/platform/cm/Movie/Camera.cfg`, untouched by this pass).

## 2. Run the demo's own `sim resim --save`

```
.venv\Scripts\sim.exe resim <df>\tests\carla_testruns\aeb\aeb_closing_ego20mps_lead10mps_30m.mcap ^
  --pipeline <df>\sim\pipelines\df_only.yaml ^
  --save <sim>\logs\_item3\v_bundle_proof.mcap ^
  --search <df>\build-sil-vs2026\src\platform\df_sil\Release ^
  --config <df>\src\project\base\default.yaml
```

(Absolute paths required — `engine.bridge.pipeline_to_run_spec` rejects a
relative `spec.sources[0].path`/`spec.stages[0].impl.path`/`spec.outputs.path`
with `InternalError`; the relative-path form in `RUN_THE_DEMO.md` §1 assumes
a shell already rooted exactly at `modules/sim`, which this session's
`cmd.exe` invocation was not. Not a regression — a documentation
precondition worth noting, not fixed here since it is outside this item's
scope.)

`resim complete: 100 tick(s)`. `sim list topics` on the result: the same
seven topics `RUN_THE_DEMO.md` §1 names (`/df/aeb.outputs`,
`/df/aeb.compState`, `/df/bsd.outputs`, `/df/bsd.compState`, `/df/vehSig`,
`/source/gen_object_list`, `/source/veh_dyn`), tagged `simulated`/`mocked` as
expected.

## 3. Show the real `config_bundle_sha256`

**Via the evidence chain (`sim explain`, the same formatter the player's
evidence panel calls, `R-SIM-25`):**

```
.venv\Scripts\sim.exe explain df.aeb.outputs --session <sim>\logs\_item3\v_bundle_proof.mcap --at 46
```

```
config_bundle_sha256      966f0e3017a4d85a08a3dc6eaf5bad4f66b4103f59c1686d5d33a96a0204d980
component_build_id        unknown
component_library_sha256  dec40de2a39fd07190633a7510d56e3e103a70f28c07063d2530738d48d0de04
```

**Via the recording's own manifest directly** (`adas_sim.io.mcap.McapReader.meta()`):

```
run_id 20260831T061102Z-39c0be38
df config_bundle_sha256= 966f0e3017a4d85a08a3dc6eaf5bad4f66b4103f59c1686d5d33a96a0204d980
df library_sha256= dec40de2a39fd07190633a7510d56e3e103a70f28c07063d2530738d48d0de04
```

**The hash is real, not synthesised**: it is exactly the
`bundle.sha256` the build just wrote to disk (quoted above), read back
unchanged through `Pipeline.component_bundle_shas()` → `build_manifest` →
`RunManifest.components[].config_bundle_sha256` → `evidence()` →
`format_evidence()` — the full chain `A-15` wired, now exercised end to end
against a real built artifact for the first time. `component_library_sha256`
is likewise independently confirmed against a direct `sha256sum` of
`df_sil.dll`.

## Board

`misc/CONSOLIDATED_REQUIREMENTS.md` `#16` re-marked 🟡→🟢: "calibration hash
is empty" is no longer true. `RUN_THE_DEMO.md`'s "Known rough edges" updated
to match (was: *"`config_bundle_sha256` reads `unknown`"*).

## Not done, and not claimed

- **The embedded bundle *bytes* (`R-SIM-3a`'s "embeds the config bundle's
  bytes... so it renders correctly on a machine with no build") are still
  not written by this path.** `McapReader.config_bundle_bytes()` on the new
  recording returns 0 bytes. Root cause, read directly from
  `cli/resim.py`: `simengine`'s own C++ writer embeds no run manifest at all
  (documented inline, `WP-15b`/`SM-12`) — Python patches the manifest
  (`overwrite_manifest_meta`) after the fact from the pipeline's already-
  resolved `component_bundle_paths`/`component_bundle_shas`, which is
  exactly what made the *hash* real. Embedding the *bytes* is a different,
  larger mechanism (reading the bundle directory's actual file contents and
  writing them as a metadata block after the engine subprocess exits) that
  `A-15` never touched and this session was not asked to build. Named, not
  fixed — a real, separate, pre-existing gap, distinct from the hash gap
  `A-15` closed.
- `build.bat`'s full Conan-driven path remains unusable in this sandbox
  (credential gap, same as `WP-01`'s Conan-editable test). The incremental
  `cmake --build` used here is a legitimate substitute *given an
  already-resolved dependency graph on disk* — it would not work on a clean
  checkout with no prior successful `conan install`. Not a general
  workaround; noted so nobody assumes it replaces `build.bat` in every
  environment.
- `df_viz` (the picture) was not rebuilt this pass — this item only needed
  `df_sil` for the headless evidence chain, not the GUI panel itself.
