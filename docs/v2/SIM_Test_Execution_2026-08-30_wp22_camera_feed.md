# Test Execution — 2026-08-30 — `WP-22` implemented: one real camera frame, drawn live

**Verdict: exit gate met.** A real frame from `bsd_curve_r172_passby.mcap`'s
`carla/chase_camera` topic decodes and draws in `viz_player.exe`'s own
"Camera" panel, beside the BEV grid, screenshotted live —
`modules/sim/logs/wp22_camera_feed/viz_player_camera_bev_2026-08-30.png`.
Built and run on native Windows, `vs2026`, real binaries, not a synthetic
fixture.

**Not `vantage_app.exe`** — per the author's own decision this pass (asked
mid-session, see the log entry below): `vantage_app.exe`'s only tick source
is a live `EmbeddedEngine` run through `frame_bridge.cpp`, which never fills
`PortValue::schema_bytes` for any port (its own header says so) — the
resolver's dynamic-descriptor decode needs exactly that field, and it isn't
there. `viz_player.exe` (`modules/viz`'s own `player_app.cpp`, `--recording`)
has a real `Session` with real `schema_bytes` and is otherwise the identical
`RunPlayerWindow`/GL loop `vantage_app.exe` also drives. `vantage_app.exe`
was not touched this pass.

## The three pieces, as built

**1. Producer — `modules/df/src/platform/df_viz/layers/camera.cpp` (new).**
`BuildCameraLayerAdapter` calls `SceneBuilder::AppendReference("carla/
chase_camera", ports.log_time_ns, ReferenceKind::kImage, "camera.chase")`
every tick, unconditionally — no declared port, no `PortBytes::Find` lookup;
`carla/chase_camera` is the recording's own raw topic name (`df`'s fact per
R-SIM-1, matching `sim/ingest/carla_legacy.yaml`'s `provides:` entry),
addressed directly the way `R-SIM-2` reference prims always are, never
through a component port. Registered as `kLayerProviders[]`'s sixth entry,
`space: "image:chase"`.

**2. Resolver — `modules/viz/cpp/viz/render_gl/session_image_resolver.{hpp,cpp}`
(new), `SessionImageResolver : ImageResolver`.** Wraps a `viz::session::
Session&` (constructed in `player_app.cpp`, only when `--recording` is
given — `player_runner.cpp` stays backend-agnostic, unchanged from `WP-34`'s
own split). `Resolve(topic, log_time_ns, ...)`: `Session::SeekNs` → `Tick::
Port(topic)` → raw `payload` bytes (never decoded by `Session`, by design)
→ parse as `foxglove.CompressedImage` using that same `PortValue`'s own
`schema_bytes` (dynamic `FileDescriptorSet`, the exact `R-SIM-11` pattern
`modules/sim`'s `simcore/abi/simcore.cpp` already uses for its
`PopulateDescriptorPool*` functions — reused, not reinvented, multi-pass
dependency-order build included) → `stbi_load_from_memory` (JPEG, see
below) → `glGenTextures`/`glTexImage2D`, cached by `(topic, log_time_ns)` in
a depth-64 bounded FIFO (a GL texture is real GPU memory; the codebase's own
`PushSource`-style "depth-capped ring" idiom, not invented fresh). Named,
scoped failure at every step (missing tick, missing port, empty schema,
malformed schema, non-"jpeg" format, a JPEG `stb_image` itself can't decode)
returns `false` — R-SIM-7, draws nothing, never a placeholder.

**Decoder, named as asked: `stb_image.h` (Sean Barrett, public domain / MIT
dual license), vendored at `modules/viz/src/third_party/stb/`** — pinned
(commit `2c980bb5...`, `VERSION`, `.pin_manifest.sha256` via
`scripts/check_vendor_pins.py --update`), same discipline as the pre-existing
`imgui`/`glfw`/`implot` vendors. `STBI_ONLY_JPEG` compiled in
(`stb_image_impl.cpp`, the one activation TU) — no other format decoder from
that file is built. No other new dependency: no image library beyond this
one header, no network fetch at build time (vendored, not pulled per-build).

**3. Panel — `player_runner.cpp`.** A second, real `ImGui::Begin("Camera")`
window with its own `DrawScene(..., config.image_resolver, VIZ_SPACE_IMAGE)`
call, beside the existing fullscreen-background-draw-list `VIZ_SPACE_EGO_BEV`
call (now forwarding `config.image_resolver` instead of a hardcoded
`nullptr`). `RunConfig` gained one field, `image_resolver` (default
`nullptr` — `vantage_app.exe` leaves it null, unaffected).

## The ABI extension this needed, and why (found live, not planned)

Neither `PortBytes` nor `VizTickView` (`df_viz_c.h`) carried the current
tick's own time — `AppendReference`'s `log_time_ns` argument had nothing
non-fabricated to be stamped with. Fixed by threading a genuine
`uint64_t log_time_ns` through `VizTickView` (new trailing field,
`DF_VIZ_ABI_VERSION` bumped **1 → 2**, additive-only — every existing
brace-init call site across both `viz` and `df` (12 files, checked
individually) already omits trailing initializers, C++ aggregate-init
zero-fills them, none needed editing) → `PortBytes::log_time_ns` (populated
by `BuildPortBytes`) → `player.cpp`'s `BuildTickView` (`view.log_time_ns =
tick.t_ns`). Verified end-to-end via `--export-ndjson`: tick 0's reference
prim carries `reference_log_time_ns: 50675799` — a real recorded nanosecond
value, not `0`. Two more real ABI-version consumers found and fixed:
`tests/unit/test_abi_version.cpp` (hardcoded `1`) and `src/adas_viz/
binding.py` (Python ctypes mirror of `VizTickView` — needed the new field
added to `_fields_` too, or the struct size mismatches the real C ABI;
`DF_VIZ_ABI_VERSION` constant updated alongside it).

## The frozen requirement this needed amending, and why (also found live)

`conf/viz.yaml` was governed by `SW-0021`/`SYS-0088` (`P0`, `R1`): *"exactly
five layers, no sixth,"* mechanically enforced in three places — a real
test (`test_manifest_no_protobuf.cpp`'s `header.layer_count == 5u`) and a
**build-time gate** (`scripts/gen_viz_shim.py`'s own `validate()`, which
would have hard-failed the codegen step, not just a test). Asked the author
mid-session (see log) rather than deciding unilaterally: amend the frozen
number (chosen) vs. piggyback the reference onto an existing calibration
layer to dodge it. `SW-0021`/`SYS-0088` amended in place with the change
recorded (`R-REQ-2` — the old text is quoted in the amendment, not deleted),
`gen_viz_shim.py`'s check moved to six, the checked-in `df_viz_c.cpp`
snapshot refreshed to match what the generator now actually produces
(`UT-abi_shim-03`'s own regeneration-diff test), and every cascading count
assertion fixed: `test_manifest_no_protobuf.cpp` (5u→6u),
`test_abi_shim.cpp`'s full-dispatch prim count (14→15, renamed to name six
layers), `test_scene_only_host.cpp`'s comment. **Named gap, not closed this
pass:** `SYS-0089` also requires a dedicated golden-Scene test per layer;
`camera.chase` has none yet, only the indirect coverage the count fixes
above give it — recorded in `SYS-0089`'s own row, not silently claimed done.

## Two build-only findings, fixed, real not cosmetic

- **`adas-viz-runner` couldn't see `<google/protobuf/descriptor.h>` at
  all** — `protobuf/3.21.12`'s own Conan-generated data file reports
  **empty** `INCLUDE_DIRS` for both the root and the `libprotobuf`
  component (verified by reading `protobuf-release-x86_64-data.cmake`
  directly); `get_target_property()` and a generator-expression form of the
  same read (the fix `df_viz`'s own `CMakeLists.txt` already uses for an
  adjacent class of Conan-CMakeDeps propagation gap) both came back empty
  too. Fixed by reading `protobuf_PACKAGE_FOLDER_RELEASE` (the one thing
  that Conan data file does populate) and adding `/include` directly —
  confirmed against `modules/interfaces`'s own already-working build of the
  same dependency, which resolves to the identical path.
- **`GL_CLAMP_TO_EDGE` undeclared** — GLFW's own minimal GL header is 1.1
  only; the constant is 1.2. Defined locally as the stable, cross-vendor
  `0x812F` rather than pulling in ImGui's own internal GL loader
  (`imgui_impl_opengl3_loader.h`) for one enum this file would otherwise
  never need.
- **`check_no_component_types.py` two false positives** — `ANL-VZ-02`'s
  `.pb.h`/`.pb.cc` include-name check doesn't distinguish a component's own
  generated proto binding from protobuf's own runtime reflection headers
  (`google/protobuf/descriptor.pb.h`, this row's own dynamic-decode
  dependency); `ANL-VZ-03`'s function-token grep has no `third_party/`
  exclusion, so vendored `stb_image.h` tripped on "acc" as a plain substring
  (inside "access"). Both fixed narrowly in the check itself (excluding
  `google/protobuf/` paths and `third_party/` respectively), not suppressed
  — matches what each check's own docstring already says it polices.

## Empirically verified, not assumed

`viz_player.exe --recording bsd_curve_r172_passby.mcap --export-ndjson`
(headless, no window) — 218 ticks, 2180 prims. Confirmed directly from the
export, not inferred:
- **218/218 ticks carry exactly one `camera.chase` reference prim**, topic
  `carla/chase_camera` verbatim (the raw mcap topic — `Session`'s own C++
  path does **not** apply `R-SIM-23`'s ingest-map renaming the way the
  Python `sources.py` path does; confirmed by the topic string itself, not
  assumed), real non-zero `reference_log_time_ns` per tick.
- **A real, separate, pre-existing gap, found not caused:** `objects`/`hud`/
  `bsd.warning` (df's own port-gated layers) emit **zero** prims against
  this recording, at every tick. Root cause, traced in `viz::player::
  TopicToPortName` (`player.cpp`): it strips a topic's producer/stage
  segment (`"stage/port"` → `"port"`) — correct for a **self-produced**
  recording (`sim record`'s own topic convention, what `WP-35`'s demo
  used), but `bsd_curve_r172_passby.mcap` is a raw `carla_bridge.py`
  legacy capture (`"df/gen_object_list"` → `"gen_object_list"`, never
  `"objects"`) — a mismatch this recording had before this pass and that
  `WP-22` does not touch. Only calibration-only layers (`bsd.zone`,
  `bsd.sensor_fov`, both port-free) plus `furniture` plus the new
  `camera.chase` draw anything against this file — confirmed by the
  screenshot: a real BEV grid and BSD zone/sensor-FOV geometry are visible,
  but no object boxes. **Named here so "beside a live BEV" isn't overclaimed
  as "beside live object tracking."**

## Screenshot

`modules/sim/logs/wp22_camera_feed/viz_player_camera_bev_2026-08-30.png` —
`viz_player.exe`, native Windows, launched against `bsd_curve_r172_passby.
mcap` + the real `df_viz.dll` (`sil_viz` build), left to play to tick 218
(`Timeline` panel reads `tick 218, LIVE`), `PrintWindow`-captured. Shows: a
real decoded road scene (car ahead, guardrail, trees, lake) in the "Camera"
panel; the BEV grid and BSD zone/sensor-FOV geometry visible behind/around
it; the Layers panel listing `camera.chase` registered under group `df`.

## Build/test state

- `modules/viz`: `sil` clean, `gtest` **49/49 green** (native Windows,
  `vs2026`, real rebuild from clean for the vendor-pin/protobuf/GL fixes).
- `modules/df`: `sil_viz` clean (`df_sil.dll` + `df_viz.dll`, `camera.cpp`
  compiled and linked, 6-layer manifest generated from `conf/viz.yaml`
  without the codegen validator's own count check tripping). `gtest`
  (reconfigured with `-DTARGET_TYPE=sil_viz` so `df_viz`'s own tests build
  — `scripts/build.py`'s plain `-t gtest` defaults `TARGET_TYPE=sil` and
  never builds them, a pre-existing, unrelated-to-this-pass build.py
  limitation) **311/312 green**; the one failure
  (`df_viz_test_render_svg`) is the already-dispositioned, pre-existing,
  author-decided-not-to-fix `"bsd.zone"` vs. `"bsd.zone.boundary"` stale
  test-literal finding from the 2026-08-30 CarMaker de-risking pass
  (`df_viz_Software_Test_Spec_v0.1.md` §8) — untouched, not this row's to
  fix.

## Not done this pass

- `vantage_app.exe` untouched (author's own choice, this pass).
- `SYS-0089`'s dedicated golden-Scene test for `camera.chase` — named gap,
  not written.
- The `objects`/`hud`/`bsd.warning`-against-legacy-topic-names gap — real,
  pre-existing, found and named, not fixed (would mean either changing
  `TopicToPortName`'s own mapping rule or regenerating the recording through
  a real `sim record` pass — a separate initiative, not a `WP-22` box).
- The other four `#20` pieces — not started, per instruction.
