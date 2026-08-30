# Scoping record — 2026-08-30 — item `#20`'s video-feed entry, against `WP-30`

**Not a test campaign** (no code changed this pass) — a scoping analysis,
recorded in this module because `START_HERE.md`'s "next action" points here.
Spans `sim`, `viz` and `df`; the verdict below is that none of the missing
work is `sim`'s to do.

## Verdict

**`WP-30` is the wrong anchor. Unparking it does not get a frame on screen,
and no new package needs opening.** The display-only half of what `WP-30`
used to cover was carved out of it on 2026-08-20 (`SM-01` trial) and moved to
`viz`, where the low-level machinery (`Prim` kind, `Session`, serializer,
budget) was then built for real under `VZ-09`/`VZ-12`, closed 2026-08-19 —
**quietly, without `SYS-0156`/`SYS-0157` ever getting a `VIZ:SYS-nnnn` UID**
(`SIM_System_Requirements_v0.1.md` §11.5: "not yet allocated"). What remains
is a real, unclaimed, three-file gap — concrete image decode/upload, a second
player panel, and a layer provider that actually calls the API — that is
`viz`'s and `df`'s own deferred work, not a `sim` package. `sim`'s own io
layer needs nothing: the two candidate recordings are single-format, single-
camera mcap files, and the generic mcap codec already serves arbitrary-topic
raw bytes today (proven below) — exactly the case `WP-30`'s codecs/merge
machinery does not exist to solve.

## The six questions

### 1. What `WP-30`'s 8 boxes say, and which are needed for a first frame

`SIM_Implementation_Plan_v0.1.md:1216-1228`. Re-scoped 2026-08-20: *"its own
display-only software item superseded to `viz` ... Never started, so this is
a scope removal, not a code move."* The 8 unticked boxes (`Prereq`, `Lands`
header, 4 `IMP` lines, `Files`, `Exit`) are entirely **io-side**: new codecs
for `rosbag`/`imagedir`/`carmaker` (`IMP-0382`), a multi-camera sync buffer in
`merge.cpp` (`IMP-0071`), a multi-camera `replay_one.cpp` driver
(`IMP-0396`), `build.py::instantiate` wiring (`IMP-0401`). Exit: *"a
multi-camera recording opens and plays via the codecs/merge/replay path."*
**None of the 8 are needed for a first frame** — they solve multi-camera
synchronization across foreign formats; the target recordings are one mcap
file each with one camera topic, already inside the format the existing
generic mcap codec reads.

### 2. What the viz side needs — new `Prim` kind or reference-resolved draw

**A reference-resolved draw. No new `Prim` kind — it already exists and is
tested.** `PrimKind::kReference` (`viz/cpp/viz/scene/scene_impl.hpp:28-38`,
comment: "`CN-0093`'s prim catalogue, closed set"), `ReferenceKind::kImage`
(`scene_impl.hpp:44-49`), `SceneBuilder::AppendReference(topic, log_time_ns,
kind, style)` and the C-ABI mirror (`VIZ_PRIM_REFERENCE`/
`VIZ_REFERENCE_IMAGE`, `scene_accessors.hpp:33-53`) landed under `WP-09`/
`VZ-09`, closed 2026-08-19 (`VIZ_Implementation_Plan_v0.1.md:491-544`,
`UT-scene-REF-01`/`UT-render_gl-REF-02` green). The cardinality gate is real
and mechanised (`scripts/check_prim_kind_cardinality.py`, wired into
`tests/CMakeLists.txt:211`) — adding a *tenth* kind would be the semver event
the user's framing describes; using the ninth, already-shipped one is not.

**What is missing is the concrete resolver, and it was left missing on
purpose.** `ImageResolver` (`viz/render_gl/image_resolver.hpp:31-41`) is a
pure-virtual seam — its own file comment: *"the toolkit itself carries no
recording reader ... this interface is what a real player implementation
fills in once `VZ-12` exists."* `VZ-12` (`Session` in C++) is now closed
(`WP-11`, 2026-08-19). At runtime the resolver is still never wired:
`player_runner.cpp:317` passes `/*image_resolver=*/nullptr`, so
`EmitReference` (`draw_scene.cpp:155-168`) always early-returns — **no image
has ever been drawn by this codebase.** The only concrete `ImageResolver` in
the tree is a test fake (`tests/unit/test_render_gl.cpp`).

**A second gap, not mentioned in either plan: there is exactly one player
panel, hardcoded to `VIZ_SPACE_EGO_BEV`** (`player_runner.cpp:317`). Nothing
in `player_runner.cpp` ever draws the `image:<cam>` space — `CN-0028`'s "viz
is BEV-only today" note (`viz/CLAUDE.md`) is still literally true. Landing a
working resolver alone draws nothing: a second `DrawScene` call (or an
equivalent second window) scoped to the image space is also needed.

**A third gap: nothing calls `AppendReference` outside `scene_builder.cpp`
itself.** No layer provider — Python or C++ — emits a `kReference` prim
today. `AppendReference` matches in the tree are the builder's own
declaration/definition and its C-ABI accessor, nothing else
(`grep AppendReference cpp/` → `scene_builder.{hpp,cpp}`,
`draw_scene.cpp`, `view_space.{hpp,cpp}`, `scene_impl.hpp`,
`scene_accessors.hpp`, `error_codes.hpp` — all framework, zero plug-ins).

None of these three gaps is a new `Prim` kind or a semver event. All three
are real code that has never been written.

### 3. Are the two recordings enough, or must something be regenerated

**Enough, verified directly — no regeneration, `carla_bridge.py` not
needed.** Both recordings read clean with the `mcap` Python package, no
`foxglove` package involved:

```
bsd_curve_r172_passby.mcap:            carla/chase_camera  foxglove.CompressedImage  216 msgs  protobuf
canonical_10mps_30m_20260714_174456.mcap: carla/chase_camera foxglove.CompressedImage  61 msgs  protobuf
```

The schema is embedded per-recording (`FileDescriptorSet`, 458 bytes, schema
id 3) — decoded dynamically with no vendored `.proto` and no `foxglove`
package: `format="jpeg"`, `data` 34,685 bytes, `frame_id="chase_camera"`,
timestamp matching `log_time`. This is the `R-SIM-11` pattern the codebase
already uses elsewhere for the same reason (`google::protobuf::
DescriptorPool`/`DynamicMessageFactory` precedent: `simcore/abi/
simcore.cpp`) — reuse it in C++, don't invent a second decode path.

`df`'s own ingest map already half-anticipates this port:
`modules/df/sim/ingest/carla_legacy.yaml:25-28` —
`carla/chase_camera → port: source.camera.chase, proto_type: "", origin:
measured` — covered by `tests/unit/test_a4_legacy.py`. The blank
`proto_type` is a real, small, named gap (no port declares a type for images
yet) but not a blocker: `PortValue.payload` (`viz/cpp/viz/session/
tick.hpp:45`, "raw wire bytes — decode is a plug-in's job, never `Session`'s")
is populated straight from the generic codec regardless of `proto_type`,
by design (`R-SIM-2`'s referenced-bulk-data pattern, restated in that same
file's header comment).

### 4. The smallest demonstrable first step

**Not a `df`-component integration — a minimal harness proving the three
missing pieces end-to-end, same "mechanism first, integration after" split
this plan already used for `VZ-19`/`WP-21` and `WP-32`:**

1. **`viz`:** a concrete `SessionImageResolver` (new file, `viz/render_gl/`)
   wrapping a `viz::session::Session&` — `Resolve(topic, log_time_ns, ...)`
   → seek the tick → `Tick::Port(topic)` → parse `.payload` as
   `foxglove.CompressedImage` via `.schema_bytes` (dynamic descriptor,
   `simcore.cpp`'s own pattern) → JPEG-decode → `glGenTextures`/
   `glTexImage2D` (no JPEG decoder is vendored anywhere in `modules/viz`
   today — `src/third_party/` holds only `glfw`/`imgui`/`implot`; a small
   single-header decoder, e.g. `stb_image.h`, is a new but trivial
   dependency; existing `glTexImage2D` precedent is ImGui's own font-atlas
   upload, `src/third_party/imgui/backends/imgui_impl_opengl3.cpp:690,697`
   — same call shape, different source buffer).
2. **`viz`:** wire it into `player_runner.cpp` in place of the `nullptr`,
   and add the second `DrawScene` call/window for the image space —
   currently absent, not merely unwired.
3. **`df`:** one layer provider in the *real*, shipping plug-in
   (`src/platform/df_viz/layers/`, C++ — **not** `sim/layers/*.py`, which is
   prototyping-only per `D-4`/`R-SIM-2` and never ships) calling
   `SceneBuilder::SetCurrentLayer("df.camera.chase", image-space)` then
   `AppendReference("source.camera.chase", tick's log_time_ns,
   ReferenceKind::kImage, style)` — the existing `layers/common.cpp` pattern
   (`out.AppendBox`/`AppendText` calls, `common.cpp:146-232`) is the
   precedent to extend, not a new shape to invent.

Exit for this first step: one real frame from `bsd_curve_r172_passby.mcap`,
decoded and textured, drawn in `vantage_app.exe` beside the existing BEV —
not yet multi-camera, not yet a packaged deliverable.

### 5. `foxglove.CompressedImage` — where it's defined, and `R-IFACE-1`

**Not defined anywhere in this repo, and never should be.** `modules/
interfaces/proto/**` contains no `foxglove`/`CompressedImage` proto — `grep`
across every producer folder returns nothing. `modules/viz` contains zero
references. It appears in exactly two places, both in `df`'s **legacy**
CARLA tooling (`modules/sim/CLAUDE.md`'s own banner: *"predates these rules
and is what they exist to replace... do not extend"*): `mcap_recorder.py`
(write side, via the pip package `foxglove-schemas-protobuf`) and
`replay/foxglove_stream.py` (a live Foxglove Studio websocket stream — the
`No Foxglove stream` hard constraint's namesake, confirmed by reading it:
`import foxglove`, `foxglove.websocket`, `CompressedImageChannel`).

**The read side needs neither.** Verified directly (§3 above): the schema
is decoded from the recording's own embedded `FileDescriptorSet` bytes with
no `foxglove` package installed. This is exactly `R-SIM-11`'s "no host
requires generated bindings" contract, applied to a schema we did not
author.

**Consistent with `R-IFACE-1`.** `R-IFACE-1` governs where *we* define *our
own* contracts — it says nothing about consuming a third party's
self-describing schema off a recording, and doing so adds no `.proto` file
anywhere, vendors nothing into `modules/interfaces`, and generates no static
C++ binding. The violation `R-IFACE-1` exists to prevent — a second place
schemas get defined — does not occur here because nothing is *defined*
here; a `FileDescriptorSet` is read, exactly as `adasManifest()`'s own bytes
already are. Consuming `foxglove.CompressedImage` is `R-SIM-14`'s codec
model (schema travels with the file) applied for the first time to a
schema `sim`/`viz` don't own — worth naming explicitly, never worth
vendoring a static copy to "make it ours."

### 6. Is `carla_bridge.py` needed

**No.** Both recordings already exist, already carry the topic, and read
correctly with the generic codec (§3). `carla_bridge.py` (`modules/df/
tools/carla/carla_bridge.py`) is live and could regenerate or extend footage
later, but nothing in the first-step scope above touches it.

## What this changes in `MOVEMENT_B_PLAN.md`'s "findings to decide on
separately" pattern

This is the same shape as that list's item 3 (the cross-repo `Session`
duplication): a real, named, cross-module gap that neither module's plan
currently owns, found by looking rather than by a stale claim. Not added to
that list — it belongs to item `#20`'s own scoping, not `Movement B` — but
the pattern is the same and is why this record names owners per piece
rather than proposing a new `sim` package.

## Not done this pass

No code written. `WP-30` untouched (correctly — see Verdict). No `VZ` or `WP`
row opened yet for the three-piece gap in §4; that is the author's call,
named but not taken here per instruction (report and ask before committing).
