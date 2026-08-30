# Test Execution — 2026-08-31 — three stale viz tests fixed, camera.chase golden test added, requirements re-marked

**Scope:** author's follow-up to `..._legacy_objects_ingest.md`: (1) fix the
three `viz` unit tests left red by the canonicalization regression, (2) add
`SYS-0089`'s missing golden-Scene test for `camera.chase`, (3) re-mark
`misc/CONSOLIDATED_REQUIREMENTS.md` against reality (`WP-22`, the ingest fix,
and a scope change removing lane/pedestrian markings, free space and
semantic segmentation from item #20 entirely), (4) name the stale-build
pattern this week exposed twice.

## 1. Three stale viz unit tests, fixed

Root cause (already recorded in `..._legacy_objects_ingest.md`): the mcap
and `.erg` codecs have canonicalized every topic unconditionally since
`450031e` (2026-08-28, `WP-12`'s ingest work) — `simcore::io::CanonicalTopic`
turns an arbitrary raw spelling like `"df.a"` into `"/df/a"`, and
`"bsd.outputs"` into `"/bsd/outputs"`. Three tests, all written before that
commit and never re-run against a freshly-built `sim` library since, still
asserted the pre-canonicalization spelling:

- `viz_test_session` (`Session.BackwardScrubAfterForwardPassMaterializesNothingNew`,
  `Session.KnownPortsAndRunManifestReadFromTheRecording`) — fixture writes
  `"df.a"`/`"df.b"`; assertions updated to the real `"/df/a"`/`"/df/b"` the
  codec's own reader reports.
- `viz_test_pull_source`
  (`PullSource.FullScrubThroughTheInterfaceAloneStructurallyIndistinguishable`)
  — same fixture/mismatch, same fix (`"/df/a"`).
- `viz_test_erg_pull_integration`
  (`ErgPullIntegration.RealErgRecordingDrivesPluginHostBuildScene`) — a real
  `.erg` fixture whose ports are declared `"bsd.outputs"`/`"bsd.compState"`
  (`ComponentManifest`-style dotted names); the `.erg` codec's own
  `Describe()`/`Pull()` canonicalize these too (`erg.cpp`, "one spelling
  above `io`", `F-1`) to `"/bsd/outputs"`/`"/bsd/compState"` — assertions
  updated to match.

**No production code changed** — every fix is a test-assertion update to the
real, current, correct codec behaviour; the fixtures' own as-written topic
spellings are untouched (changing them was unnecessary and would have been a
bigger diff for no reason). Each fix carries an inline comment naming the
root cause and pointing at this record's own predecessor, so the next reader
does not have to re-derive it.

**Verified:** `viz` `gtest`, `vs2026` — **49/49 green** (was 46/49). No other
test regressed.

## 2. `SYS-0089`'s `camera.chase` golden-Scene test, added

`SYS-0089`'s own "known gap" note (written `WP-22`, 2026-08-30) named
`camera.chase` as the one of six `R1` layers with no golden-Scene test of
its own — its only coverage was indirect, through the full-dispatch/
scene-only-host tests' updated prim counts. Closed:

- **New SW-level requirement, `SW-0077`** (`df_viz_Software_Requirements_v0.1.md`):
  "`camera.chase` layer emits its reference prim" — one `kReference`/
  `kImage` prim per tick, topic `carla/chase_camera`, style `camera.chase`,
  stamped with the tick's own `log_time_ns`. Traces to `SYS-0089` (the
  cross-cutting "every layer has a golden test" requirement — `camera.chase`
  has no Python twin to "match", so it does not get a `SYS-0083..0087`-style
  per-layer row the way the other five do; that is not a gap, since no such
  row is applicable to a layer nothing in Python ever built).
- **New test, `UT-layers-13`** (`src/platform/df_viz/tests/unit/test_layers.cpp`):
  calls `BuildCameraLayer` directly with a fixed `log_time_ns`, asserts
  exactly one prim, `VIZ_PRIM_REFERENCE`, topic `carla/chase_camera`, kind
  `VIZ_REFERENCE_IMAGE`, style `camera.chase`, and the stamped
  `log_time_ns` matches the input. Mirrors `UT-layers-07`/`09`'s own
  finalize-and-assert shape; no fixture needed (`camera.chase` reads no
  port, `layers/camera.cpp`'s own design).
- **Three stale "five"s fixed while touching this table**, all direct
  fallout of `SW-0021`/`SYS-0088`'s own `WP-22` amendment to six layers that
  never fully cascaded: `UT-layers-11`'s own row (`df_viz_Software_Test_Spec_v0.1.md`),
  `SYT-HST-02` and `SYT-SCP-16`/`17` (`df_viz_System_Test_Spec_v0.1.md`) all
  still said "five" — each corrected in place, amendment dated and reasoned
  inline, matching `R-REQ-2`'s "old text quoted, not deleted" discipline
  already used for the original amendment.
- `SYS-0089`'s own "known gap" note rewritten to "gap closed 2026-08-30" —
  the old text stays legible as history, not silently overwritten.

**Verified:** `df_viz_test_layers` — **13/13 green** (was 12/12, new test
added and passing). Full `df` suite re-run: **311/312** — same,
already-dispositioned `df_viz_test_render_svg` failure, untouched, no new
regressions.

## 3. `misc/CONSOLIDATED_REQUIREMENTS.md` re-marked

Predates `WP-22`, the legacy-recording ingest fix, and the author's own
scope change. Touched only what became false, per the document's own stated
discipline (no line added, removed or reworded beyond that):

- **Item #20's row.** The old sentence listed lane/pedestrian markings, free
  space and semantic segmentation as things item #20 still asks for —
  false the moment the author took them out of scope entirely (2026-08-30).
  Rewritten to name only what #20 still covers: driver view and video feed
  publishing. Status changed from 🔴 "none built" to 🟡, spelled out
  honestly rather than forced to green or red: video feed is real and
  screenshotted (`WP-22`); driver view's mechanism exists but **no recording
  on hand carries a driver-view camera topic** — only `carla/chase_camera`,
  the chase camera — so it stays unverified, which is the author's own call
  to resolve (get such a recording, or decide the mechanism proving itself
  on the chase camera is sufficient), not something this pass could decide
  for them.
- **§2 "Where is it?"** — directly downstream of the item #20 change:
  "24 of 25 are green or amber, the only red is #20" is false the moment
  #20 stops being red. Rewritten to "25 of 25 are green or amber", with
  the same driver-view caveat carried through rather than dropped.
- **The document's own re-measurement header** — extended with today's date
  and reason, matching the existing 2026-08-27→2026-08-28 precedent (not a
  new requirement, the document's own provenance trail staying accurate).
- **Left untouched, deliberately:** the "Two moved on 2026-08-28" paragraph
  (still true, about a different day), the "What is NOT in scope" list (the
  newly-out-of-scope items belong in item #20's own row, which already
  names them — a second copy in that list would be exactly the kind of
  addition this pass was told not to make), and every other line (items
  1–19, 21–25 — none of today's work touches what they describe).

## 4. The stale-build pattern — named, not fixed

**Twice this week, a stale build artifact silently masked a real
regression, and both times it was found by accident, not by a check:**

1. **`cm_viz` (vs2026), last built 2026-08-21**, still in use for the
   CarMaker de-risking pass on 2026-08-30 until someone thought to check —
   it predated `viz` commit `9ca1324` (2026-08-27, "`Span<T>` single-pointer
   ctor silently truncated a 2-element array to its first element"), a real
   geometry bug (a circle's/arrow's second point silently duplicating the
   first). The stale binary would have shown that bug as "the app renders
   fine" to anyone not specifically told to rebuild first.
2. **`sim`'s `sil` library (vs2026), three days stale** (built 2026-08-25),
   still the one `viz`/`df` linked as an editable Conan package until this
   week's ingest-map work needed a symbol only a fresh build had. The stale
   library predated `450031e` (2026-08-28, `WP-12`'s topic-canonicalization
   change) — its absence is exactly what let the three `viz` unit-test
   regressions (§1 above) and `WP-22`'s own camera-panel regression ship
   and stay green/unnoticed for two days after `WP-22` itself landed.

**Both incidents share one shape:** an editable Conan dependency's build
artifact sat stale across a real, behavior-changing commit to the depended-on
module, and nothing in the ordinary build/test loop noticed, because
`cmake --build`/`ctest` only rebuild what their own dependency graph says is
stale relative to *their own* source tree — an editable package's binary,
sitting in a sibling checkout, is invisible to that graph unless something
explicitly rebuilds it first. Both were caught only because a human (or an
agent) happened to need a fresh rebuild for an unrelated reason.

**Named as a candidate for a mechanical freshness check — a build or CI step
that compares an editable dependency's last-built commit against its current
HEAD and warns (or refuses) on drift — not built this pass.** Two
independent incidents in one week is a real signal, but a check like this
touches every module's build machinery (`R-BUILD-6`'s own "a change to any
machinery file is a cross-submodule change... apply it to all component
repos in the same pass") and deserves its own scoped design, not a
same-session bolt-on.
