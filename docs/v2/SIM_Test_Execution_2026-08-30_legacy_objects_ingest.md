# Test Execution — 2026-08-30 — legacy-recording objects finding: ingest map applied to the player

**Verdict: exit gate met.** `bsd_curve_r172_passby.mcap` (the same recording
`WP-22`'s camera panel uses) now renders a real object box in
`viz_player.exe`'s BEV, beside the BSD zone/sensor-FOV geometry and the
camera panel. Headless proof:
`viz_player.exe --plugin-path <df_viz Release dir> --recording
bsd_curve_r172_passby.mcap --export-ndjson` went from **2180 prims, zero
`box`/`object.*` styles** (root-cause pass) to **2616 prims, 218 `box` +
218 `text` prims styled `object.classification.car`/`object.label`** — one
real `CAR` object per tick, matching the recording's own decoded
`DfObjList` payload (`local_id=150`, `dist_x≈-73…-30m`) verified directly
against the mcap in Python. Live-GUI confirmation: the Layers panel's
`Scene:` prim count moved from 10 (an earlier same-day reference shot) to
12 — the exact +2 (box+label) the headless export predicts.

## The architectural decision, made and justified

**Chosen: teach the player path to apply the same R-SIM-23 ingest map**
(the preferred option named in the ask), not widen `requires=` alternation
with a third hard-coded spelling. Two reasons, beyond the one already
named:

1. **`viz::session::Session` already has the exact dependency this needs.**
   `conf/build.yml`'s `player` component already links `AdasSim::io`
   (`VZ-12`) — the same `simcore::io::Translator`/`TranslatingReader` the
   engine's `simcore.cpp::simEngineCreate` already uses (`WP-12`,
   `450031e`) is reachable with zero new cross-module edges. Reusing it
   means the *apply* mechanism — factor/offset, declared-type refusal,
   origin tagging — is **one implementation**, shared verbatim between the
   engine and the player, never re-derived.
2. **`simcore::io` itself refuses to own this.** `SW-0032`'s own Shall
   states `io` "contains no parser, no schema and no validation for ingest
   maps" — parsing the YAML is deliberately pushed up to whichever caller
   needs a resolved table. The engine's caller is Python
   (`adas_sim.ingest.map`); the player has no Python and no `RunSpec`
   (`R-SIM-13`), so a small, `viz`-local loader
   (`viz/session/ingest_loader.{hpp,cpp}`) is the only place left for it to
   live — mirroring `viz/config/ego_geometry.cpp`'s own established
   precedent of reading a declared YAML file directly with `yaml-cpp`
   rather than inventing a cross-module dependency.

## What was actually built

1. **`viz/session/ingest_loader.{hpp,cpp}` (new).** Scans
   `<plugin_dir>/sim/ingest/*.yaml` for every directory in `--plugin-path`
   (`R-SIM-20`'s deployed-beside-the-library convention — the very
   directory a `df_viz.dll` build already copies
   `modules/df/sim/ingest/carla_legacy.yaml` into), parses the closed
   `family`/`matches.any_topic`/`provides:{port,proto_type,origin}` schema
   (same validation discipline as `adas_sim.ingest.map._parse_ingest_map`:
   an unsupported key — `unit:`/`shape:`/`header:` — is a **named refusal**,
   never silently dropped), and folds every matching map's rows into one
   `simcore::io::Translator`. **A `provides:` row with an empty
   `proto_type:` is skipped, never translated** — `carla/chase_camera`'s own
   row (`proto_type: ""`) is exactly this case, and `R-SIM-2` requires a
   reference prim to stay addressed by the recording's own raw topic
   (`layers/camera.cpp`'s `AppendReference` is a hardcoded literal with no
   port lookup at all) — translating it would have silently broken `WP-22`'s
   camera panel. Two applicable maps claiming the same raw topic is a named
   authoring error (mirrors `adas_sim.ingest.map`'s own
   `check_no_double_claim`), never a silent pick.
2. **`Session::Open` gains an optional `plugin_dirs` parameter** (default
   empty — every existing caller, including the three unit tests that
   compile `session.cpp` as a direct source, is unaffected). When
   non-empty and a map matches the recording's raw topics, the reader is
   wrapped in `TranslatingReader` — the identical 3-line pattern
   `simEngineCreate` already runs, just resolved by a direct YAML read
   instead of a `RunSpec`-supplied table. `player_app.cpp` passes its
   already-collected `--plugin-path` list straight through.
3. **A real, previously-unexercised porting gap, found and closed
   (`layers/common.cpp`, `conf/viz.yaml`).** Applying the ingest map alone
   was **not sufficient** — `carla_legacy.yaml`'s declared
   `port: source.gen_object_list` is shaped for the *engine's* pipeline
   grammar (`R-SIM-21`'s reserved `source.<port>` keyword, resolved by
   Python's `port_any` alternation against a `Pipeline`'s `known_ports`).
   The player has no pipeline and no `port_any` — its own
   `viz::player::TopicToPortName` (`player.cpp`) unconditionally drops a
   topic's first `/`-delimited segment, "source" included (a deliberate,
   already-tested choice — `test_player.cpp`'s own
   `BuildTickViewDropsTheProducerStageSegmentFromARawRecordedTopic` names
   this *exact*, then-unexercised collision with `R-SIM-21` in its own
   comment, written before this ingest map ever reached that function for
   real). So `source.gen_object_list`, once canonicalized and stripped,
   reaches `PortBytes` as the **bare suffix**, `gen_object_list` — never
   `source.gen_object_list`. `conf/viz.yaml`'s `objects`/`hud` layers now
   declare a second required-port entry (`gen_object_list`/`veh_dyn`, the
   bare legacy names — not `R-SIM-21`'s `source.<port>` pair, which does not
   survive this player's stripping), and `layers/common.cpp` gained a small
   `FindEither(ports, primary, fallback)` helper so
   `BuildObjectsLayerAdapter`/`BuildHudLayerAdapter` try the
   consumer-declared name first, falling back to the bare legacy one. Both
   changes are declared data (`conf/viz.yaml`) plus a two-line, no-new-ABI
   fallback — `kMaxPortsPerLayer` (4) had headroom, no manifest format
   change needed.
4. **`hud` still emits nothing against this recording** — not a defect.
   `bsd_curve_r172_passby.mcap` carries exactly three topics
   (`carla/chase_camera`, `df/gen_object_list`, `df/veh_dyn`, confirmed
   directly via the mcap's own schema/channel index) — no `bsd.compState`
   at all, so `BuildHudLayerAdapter`'s existing (unrelated, pre-existing)
   dual-port gate correctly reports nothing. Genuinely absent data, not a
   naming defect.

## A real, separate, pre-existing regression found — not caused by this work, not fixed

Rebuilding `modules/sim`'s `sil` library was required to link this feature
at all (`simcore::io::Translator`/`TranslatingReader`/`CanonicalTopic` were
present in source since `450031e`, 2026-08-28, but the `sil` build artifact
viz/df link against as an editable package was still dated **2026-08-25** —
three days stale, never rebuilt since). That incidental rebuild is what
first exercised `450031e`'s own topic-canonicalization change
(`simcore::io::CanonicalTopic`, applied unconditionally inside the mcap
codec's `Describe()`/`ReadRange()`) against real, fresh binaries, and it
surfaced two **independent, real, pre-existing** defects, neither touched by
this session's own code:

- **Three `viz` unit tests regress** (`viz_test_session`,
  `viz_test_pull_source`, `viz_test_erg_pull_integration`) — each asserts an
  un-canonicalized topic spelling (e.g. `"df.a"`, `"bsd_outputs"`) that the
  codec no longer produces (it now returns `"/df/a"`-shaped canonical
  strings). Confirmed orthogonal to this session's own change: these three
  tests compile `session.cpp` directly with an empty, default
  `plugin_dirs`, so `ResolveIngestMaps` is a verified no-op for all three.
  46/49 `viz` `gtest` otherwise green.
- **`WP-22`'s own camera panel now renders solid black**, live-GUI-verified
  twice (with and without `--plugin-path` — **identical black result both
  times**, which rules out this session's own ingest-map feature as the
  cause). Root cause, by the same mechanism as the point above:
  `layers/camera.cpp`'s `AppendReference("carla/chase_camera", ...)` is a
  hardcoded literal (`R-SIM-2`'s own "addressed directly" design, `WP-22`'s
  own text), and `SessionImageResolver::Resolve` looks it up via
  `tick.Port("carla/chase_camera")` — an **exact**, non-canonicalized
  string match. Since the codec now reports this topic as
  `"/carla/chase_camera"` (leading-slash canonical form), the lookup misses,
  `Resolve` returns `false` (`R-SIM-7`: draws nothing), and the panel is
  empty. **`WP-22`'s own screenshot (14:59, this same day) was taken against
  the stale, pre-`450031e` `sil` build and never exercised this path** — the
  feature was already latently broken the moment `450031e` landed
  (2026-08-28), two days before `WP-22` shipped, and nobody had rebuilt+
  retested the pair since. This is a real, live regression on an
  **already-pushed** feature (`viz` `0f67af6`, `df` `b9ceba1`, `sim`
  `6495ab8`, superproject `c231337`), found only because this session's own
  link error forced the first fresh rebuild since `450031e`. **Not fixed
  here** — out of this pass's scope, named for the author's own
  prioritisation. The one-line-shaped fix, for whoever picks this up:
  canonicalize `SessionImageResolver::Resolve`'s lookup key
  (`simcore::io::CanonicalTopic(topic)`) before calling `tick.Port(...)`,
  symmetric with the write side the codec already applies.

Screenshots: `modules/sim/logs/wp22_camera_feed/viz_player_legacy_objects_2026-08-30.png`
(live GUI, `--plugin-path` given, `Scene: 12 prims`, camera panel black —
the regression above, visible in the same shot) and
`viz_player_no_pluginpath_test_2026-08-30.png` (isolation re-test, no
`--plugin-path`, camera panel still black, confirming the regression is
independent of this session's own feature).

## Update, same day: the camera regression fixed

Author's call: fix it in this same pass rather than defer it.
`SessionImageResolver::Resolve` (`modules/viz/cpp/viz/render_gl/
session_image_resolver.cpp`) now canonicalizes its lookup key
(`simcore::io::CanonicalTopic(key.topic)`) before calling `tick.Port(...)`
— symmetric with the write side the mcap codec already applies
unconditionally since `450031e`. Scoped entirely to `modules/viz`'s
player-side code (`adas-viz-runner`, linked only by `viz_player.exe`/
`vantage_app.exe`, never by a component's own DLL) — `modules/df`'s own
build and test suite need no change and were re-verified unchanged
(`311/312`, same baseline). Live-GUI re-verified: the Camera panel shows
the decoded road scene again (car, road, guardrail, trees, sky), sampled 3
times over ~10s, no flicker. Screenshot:
`modules/sim/logs/wp22_camera_feed/viz_player_camera_fixed_2026-08-30.png`.
`viz` `gtest` re-run after the fix: still **46/49** — the 3 pre-existing,
orthogonal canonicalization-regression failures (`viz_test_session`,
`viz_test_pull_source`, `viz_test_erg_pull_integration`) are untouched by
this fix and remain open, named above, not this pass's to close.

## Build/test state

- `modules/sim`: `sil` (`vs2026`) rebuilt clean from the 2026-08-25 stale
  artifact — required to link this feature at all, not a change of its own.
- `modules/viz`: `gtest` (`vs2026`) clean rebuild, **46/49 green** — the 3
  failures are the pre-existing, orthogonal canonicalization regression
  above, verified independent of this session's own `plugin_dirs`-gated
  code path.
- `modules/df`: `sil_viz` and `gtest` (`vs2026`, reconfigured directly via
  `cmake . -DTARGET_TYPE=sil_viz` — `scripts/build.py`'s plain `-t gtest`
  resets this cache var to its `sil` default on every invocation, the same
  pre-existing build.py limitation `WP-22`'s own record already named)
  clean rebuild, **311/312 green** — identical baseline to `WP-22`'s own
  result; the one failure is the same already-dispositioned
  `df_viz_test_render_svg` stale-token finding, untouched.

## Not done this pass

- The camera-panel canonicalization regression — real, found, named, not
  fixed (author's call on priority; the fix is small and independent of
  everything in this pass).
- The three pre-existing `viz` unit-test failures (same root cause) — not
  fixed, same reasoning.
- `objects`/`hud`'s legacy-name fallback covers exactly the two ports this
  recording carries; it is not a general audit of every `conf/viz.yaml`
  port across every component for the same class of gap.
