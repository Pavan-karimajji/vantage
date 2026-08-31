# START HERE

**Updated:** 2026-08-31 · **Read this first, then run the status command below.**

> **No derived progress state in this file, ever** — no "N of M done", no
> per-item status, no checklist. That is what goes stale: this module already
> lost twelve stages to a hand-kept table reading `frozen` on most rows while the
> work shipped. *Dated evidence is fine* — `t=2.300 s`, a file, a line number —
> because a measurement from a named run is history, not state.
> **Anything derived is computed:**
>
> ```
> cd modules/sim && python docs/v2/py/trace_check.py --status
> ```
>
> That is the authority for *what is built*. This file is the authority for
> *what we are doing and why* — the part no tool can derive.

---

## Where we are

**Movement A** ✅ done, except one item blocked on the author (a push).
**Movement B** — `B1` closed 2026-08-29. `B2` corrected, re-scoped and
executed 2026-08-30 (388 lines, `modules/df`, committed/pushed). `B3`
re-scoped 2026-08-30 to empty — none of its four rows were real (see
`MOVEMENT_B_PLAN.md`). `B4` re-measured 2026-08-30 to one real item (`io`'s
Python/C++ parity gap, not yet actionable) — the other four claimed overlaps
were never overlaps. **Movement B is therefore not fully done** (that one
`io` item remains), but every row in `MOVEMENT_B_PLAN.md` now rests on
verified code, not a stale claim. `misc/memory.md` §3 corrected to match
(it was written from a day-one line-count/directory sweep, never the build
or `git log`). Records: `docs/v2/SIM_Test_Execution_2026-08-30_movement_b_plan_audit.md`,
`..._b2_execute_b3_rescope.md`, `..._b4_remeasure.md`.
**Movement C** ← **the POC demo runs, all five clauses, watched. The freeze
ends by its own terms.** Item `#20`'s video-feed entry scoped 2026-08-30
(author's chosen entry point, unblocked from "do not start"): **`WP-30` is
the wrong anchor and stays parked, correctly** — its 8 boxes are io-side
multi-camera codec/merge work the two candidate recordings don't need. The
real gap is three unclaimed pieces in `viz`/`df` — a concrete `ImageResolver`
(the seam has existed since `VZ-09`, closed 2026-08-19, deliberately unfilled
until `VZ-12`'s `Session`, also closed), a second player panel (today
hardcoded to `VIZ_SPACE_EGO_BEV` only), and a layer provider that calls
`AppendReference` (nothing does, anywhere, today). No new `Prim` kind needed
(`kReference`/`kImage` already shipped under `VZ-09`). Both recordings verified
sufficient with no regeneration. Record:
`docs/v2/SIM_Test_Execution_2026-08-30_item20_video_feed_scoping.md`.

**`WP-22` (the scoped three-piece gap) implemented and exit-gated 2026-08-30
— a real frame from `bsd_curve_r172_passby.mcap`'s `carla/chase_camera`
decodes and draws live in `viz_player.exe`'s own "Camera" panel, beside the
BEV, screenshotted.** Not `vantage_app.exe` — asked and answered mid-session
(`frame_bridge.cpp` never fills `schema_bytes`, no `--recording` path exists
there at all; `vantage_app.exe` untouched). Needed more than the three named
pieces, found live, not planned: a genuine `VizTickView`/`PortBytes`
`log_time_ns` field (`DF_VIZ_ABI_VERSION` bumped 1→2, additive, 12 call
sites checked, none broke) so a layer has a real tick time to stamp a
reference with at all; `SW-0021`/`SYS-0088` ("exactly five layers")
amended to six after asking the author (piggyback-on-an-existing-layer was
the smaller alternative, declined) — a real build-time gate
(`gen_viz_shim.py`) as well as a test, both fixed, cascading count
assertions fixed with it. `stb_image.h` vendored (public domain, pinned,
`STBI_ONLY_JPEG`) for the JPEG decode, named per instruction. **Real,
pre-existing, separate gap found, not caused:** `objects`/`hud`/
`bsd.warning` emit nothing against this specific legacy-topic-named
recording (`TopicToPortName`'s stage-stripping expects a self-produced
recording's own naming) — the BEV beside the camera is real (zone/
sensor-FOV/frame geometry) but has no object boxes; named, not fixed.
`viz` `gtest` 49/49, `df` `gtest` 311/312 (the one failure is the
already-dispositioned `render_svg` stale-token finding, untouched). Record:
`docs/v2/SIM_Test_Execution_2026-08-30_wp22_camera_feed.md`. **Not yet
committed — reported and awaiting the author's go-ahead.**

**`WP-22`'s own commit was reviewed and pushed 2026-08-30** (`viz` `0f67af6`,
`df` `b9ceba1`, `sim` `6495ab8`, superproject `c231337`) — the ABI bump and
frozen-requirement amendment both already asked about mid-session. Then the
legacy-recording finding that same record left open (`objects`/`hud`/
`bsd.warning` render nothing against `bsd_curve_r172_passby.mcap`) was
closed for `objects`: the player now applies the same `R-SIM-23` ingest map
the engine does (`viz/session/ingest_loader.{hpp,cpp}`, `Session::Open`'s
new `plugin_dirs` parameter), plus a real, previously-unexercised porting
gap this exposed and closed (`viz::player::TopicToPortName` drops a
topic's first segment unconditionally, so an ingest-mapped
`source.<port>` reaches `PortBytes` as the bare suffix, never `R-SIM-21`'s
`source.<port>` spelling — `conf/viz.yaml`'s `objects`/`hud` layers gained
a second required-port entry for the bare legacy name,
`layers/common.cpp`'s new `FindEither` tries both). Exit gate met: the same
screenshot now shows a real object box. **`bsd.warning` was never fixable
here** — the recording carries no `bsd.compState`/`bsd.outputs` topic at
all (genuinely absent data, confirmed directly against the mcap). This
work committed and pushed (`viz` `82da36b`, `df` `1e2c01d`, `sim`
`b40bcf3`, superproject `e91db63`).

**A real, separate, pre-existing regression was found in the same pass, not
caused by it — and fixed, author's call, same session.** Rebuilding
`sim`'s three-day-stale `sil` library (needed just to link the ingest-map
feature above) first exercised `450031e`'s 2026-08-28 topic-canonicalization
change for real, which silently blacked out `WP-22`'s own just-pushed
camera panel (`SessionImageResolver::Resolve`'s exact-string topic lookup no
longer matched the codec's now-canonical `"/carla/chase_camera"`) — verified
independent of the ingest-map work (reproduced identically with
`--plugin-path` omitted). Fixed by canonicalizing `Resolve`'s own lookup key
— scoped entirely to `viz`'s player-side code (`adas-viz-runner`, never
linked by a component's own DLL), so `df`'s build/tests needed no change
(re-verified unchanged, `311/312`). Live-GUI re-verified: the camera panel
decodes again. **The three pre-existing `viz` unit-test failures sharing
this same root cause remain open** (`viz_test_session`,
`viz_test_pull_source`, `viz_test_erg_pull_integration`) — a different class
of fix (stale test fixtures asserting an un-canonicalized topic spelling),
not this pass's to close. Record:
`docs/v2/SIM_Test_Execution_2026-08-30_legacy_objects_ingest.md`.

**2026-08-31 — the three pre-existing `viz` unit tests fixed, `SYS-0089`'s
`camera.chase` golden test added, `CONSOLIDATED_REQUIREMENTS.md` re-marked.**
`viz_test_session`/`viz_test_pull_source`/`viz_test_erg_pull_integration`
were asserting a pre-`450031e` topic spelling (`"df.a"` instead of the
codec's real `"/df/a"`); each fixed by updating the assertion to the real,
current canonical form, no production code touched. `viz` `gtest` is back to
**49/49**. `SYS-0089`'s own "known gap" note (`camera.chase` has no
golden-Scene test) closed: new `SW-0077`/`UT-layers-13`
(`test_layers.cpp`), plus three stale "five layers" mentions fixed in the
same table (`UT-layers-11`, `SYT-HST-02`, `SYT-SCP-16`/`17`) — direct,
never-cascaded fallout of `SW-0021`/`SYS-0088`'s own `WP-22` amendment to
six. `df_viz_test_layers` **13/13**, full `df` suite **311/312** (same
already-dispositioned failure). `misc/CONSOLIDATED_REQUIREMENTS.md`
re-marked against reality per the author's own instruction (status marks
and false lines only, nothing added or restructured): item #20's row
rewritten — three of its five original items are out of scope entirely
(author's call), video feed publishing is built (`WP-22`), and driver view
is stated plainly as unverified (mechanism exists, no recording on hand
carries a driver-view camera topic) rather than guessed green or red;
§2's "24 of 25, only red is #20" corrected to "25 of 25, #20 no longer
red" as the direct consequence. **A pattern named, not fixed:** two
independent incidents this week (`cm_viz` stale since 2026-08-21, missing
`9ca1324`'s `Span<T>` fix; `sim`'s `sil` library stale since 2026-08-25,
missing `450031e`'s canonicalization) both let a real regression ship
unnoticed because an editable Conan dependency's build artifact can sit
stale across a behaviour-changing commit with nothing in the ordinary
build/test loop noticing — both found by accident. Named as a candidate for
a mechanical freshness check; **not built this pass**, since it is
cross-submodule build machinery (`R-BUILD-6`) and deserves its own scoped
design. Record:
`docs/v2/SIM_Test_Execution_2026-08-31_test_fixes_and_remark.md`. **Not yet
committed — reported and awaiting the author's go-ahead.**

**2026-08-31, same day — item #16's amber cause (empty config-bundle hash)
fixed.** Root cause: `Pipeline.load` computed each `dll:`/`stubdll:` stage's
bundle directory for the cross-component agreement check and then discarded
it, so no method existed to turn it into a hash the way `component_build_
shas()` already does for the library file — every recording's `config_
bundle_sha256` has been empty since the field existed. Fixed: `Pipeline`
keeps `bundle_dirs`; new `component_bundle_shas()`/`component_bundle_paths()`
wired into `cli/run.py`/`cli/resim.py`'s `build_manifest` calls and
`graph/modes.py`'s two `Pipeline` reconstructions (which had the same drop).
Proven end-to-end with a new `tests/unit/test_a15_config_bundle_hash.py` —
`Pipeline.component_bundle_shas()` → `build_manifest` →
`RunManifest.components[].config_bundle_sha256` → `evidence()` →
`format_evidence()`, the same producer/formatter chain `sim explain`/the
evidence panel use — 69/69 relevant tests pass, full unit suite unaffected
(973 passed/1 skipped), system suite unaffected (96 passed/9 skipped, 1
pre-existing unrelated Conan-credentials failure). **Not run against a real
`df_sil.dll` + packed bundle** (no `vs2026` `df` build this pass) — named as
a follow-on, not assumed. Also proposed, **not built**: a mechanical
layer-count/port-name-spelling check for the copy-drift family this week's
own "five layers in four documents" finding belongs to (`F-1`, `F-7`, `F-8`,
`#5`) — would catch 3 of 5 (the layer-count case, `F-1`'s stale-fixture half,
`F-7`), not `F-8` (a numeric literal) or `#5` (a wiring claim), each for a
stated reason. Record:
`docs/v2/SIM_Test_Execution_2026-08-31_a15_bundle_hash_and_copy_drift.md`.
**Not yet committed — reported and awaiting the author's go-ahead.**

**`misc/memory.md` §3 no longer contradicts itself.** Its closing line used
to say *"deletion has never once been executed"* directly under this same
session's own correction that `B1` deleted the Python scene/render/player
stack — fixed: the pattern held for three attempts and `B1` broke it, the
first executed deletion in this project's history; the warning stays, aimed
at what is genuinely still undeleted. **A real, unowned finding recorded
alongside it:** `adas_sim/session/` (Python) and `viz::session::Session`
(C++, its own header: *"the C++ rewrite of `adas_sim.session.session.Session`"*)
are two live implementations in two repos, a direct consequence of Decision
B, correctly outside `B4`'s own scope but not thereby resolved —
`MOVEMENT_B_PLAN.md`'s *"findings to decide on separately,"* item 3. Not
acted on. Record: `docs/v2/SIM_Test_Execution_2026-08-30_memory_close_session_note.md`.

**CarMaker viz pipeline de-risked for a near-term demo, 2026-08-30 — no risk
found.** Clean `cm_viz` rebuild, both DLLs confirmed freshly deployed, a real
BSD TestRun run headless and live with the `df_viz` window screenshotted
showing `bsd.zone`/`bsd.warning`/`bsd.sensor_fov` registered and rendering.
`df_viz_test_render_svg`'s failure is root-caused, recorded as a known,
understood, author-decided-not-to-fix issue (SVG-test-only, zero live-picture
impact — `df_viz_Software_Test_Spec_v0.1.md` §8's own disposition note now
carries the one-line fix, so nobody re-investigates it), **not open.** Filed
on the `df` side: `modules/df/docs/viz/df_viz_Test_Execution_2026-08-30.md`.

The 2026-08-27 reset re-scoped this module around one watchable demo instead of a
completion percentage. Read `memory.md` for why, `DEMO_AND_SCOPE.md` for the
demo and the finite list, `MOVEMENT_B_PLAN.md` for the deletion work.
**To actually run the demo: `RUN_THE_DEMO.md` in this folder.**

**`DEMO_AND_SCOPE.md` §1 runs, end to end, all five clauses** — launcher,
self-produced recording, both modes, both pictures agreeing, and an object's
provenance answered down to the build. `WP-35` closed. Records, newest first:
**`…_2026-08-28_f8.md`** (the fifth clause), **`…_wp35.md`** (the demo and its
screenshots), **`…_wp28.md`** (`F-7`), **`…_2026-08-28.md`** (the step-zero
fixes).

## The next action — exactly one

> **`B1`/`B2`/`B3` are settled** (`B1` closed, `B2` done and pushed, `B3`
> empty). **`B4` is re-scoped to one real, named, not-yet-actionable item**
> (`io`'s `mcap.py`/`mcap.cpp` parity gap) — `Movement B` is not fully done,
> but nothing in it rests on an unverified claim any more, and `memory.md` no
> longer asserts something now false. The CarMaker viz pipeline is de-risked
> for the demo, and `df_viz_test_render_svg` is now a closed, understood,
> deliberately-not-fixed question — neither needs re-investigating. **The
> cross-repo `Session` duplication is real and has no owner** — recorded, not
> acted on; needs its own initiative before anyone touches it, not a `B4`
> sub-task. The Movement C scope conversation this file named before `B1`
> started (`DEMO_AND_SCOPE.md` §1's *"may begin. Not before"*) is still the
> standing open question and this session did not touch it. **Item `#20`'s
> video-feed entry (`WP-22`) is committed and pushed** (`viz` `0f67af6`,
> `df` `b9ceba1`, `sim` `6495ab8`, superproject `c231337`), **and the
> legacy-recording `objects` gap that record left open is closed, committed
> and pushed too** (`viz` `82da36b`, `df` `1e2c01d`, `sim` `b40bcf3`,
> superproject `e91db63`) — ingest map applied on the player's own
> `--recording` path, plus a bare-legacy-name fallback for the two ports
> that need one (not `R-SIM-21`'s `source.<port>` spelling, which does not
> survive this player's own topic stripping). **The camera-panel regression
> that same pass surfaced is fixed, committed and pushed too** (`viz`
> `598ed2b`, `sim` `e316220`, superproject `03d8d21`) —
> `SessionImageResolver::Resolve` now canonicalizes its lookup key,
> symmetric with the codec's own write side; scoped entirely to `viz`'s
> player-side code, `df` needed no rebuild. **2026-08-31: the three
> pre-existing `viz` unit tests sharing that regression's root cause are
> fixed** (`viz_test_session`, `viz_test_pull_source`,
> `viz_test_erg_pull_integration` — stale fixtures asserting a
> pre-canonicalization topic spelling, no production code touched; `viz`
> `gtest` back to `49/49`), **and `SYS-0089`'s missing `camera.chase`
> golden-Scene test is added** (`SW-0077`/`UT-layers-13`, plus three
> never-cascaded stale "five layers" mentions fixed alongside it —
> `UT-layers-11`, `SYT-HST-02`, `SYT-SCP-16`/`17`; `df_viz_test_layers`
> `13/13`, full `df` suite `311/312`, same already-dispositioned failure).
> **`misc/CONSOLIDATED_REQUIREMENTS.md` re-marked against reality**
> (status marks and false lines only): item #20's row now names only what
> it still covers (driver view, video feed publishing — three items moved
> out of scope entirely, author's call), video feed marked built, driver
> view stated plainly as unverified (mechanism exists, no recording on
> hand carries the right camera topic) rather than guessed; §2's "only red
> is #20" corrected to "25 of 25 green or amber" as the direct consequence.
> **The stale-build pattern this week exposed twice — `cm_viz` stale since
> 2026-08-21 missing `9ca1324`'s `Span<T>` fix, `sim`'s `sil` library stale
> since 2026-08-25 missing `450031e`'s canonicalization, both found by
> accident — is named as a candidate for a mechanical freshness check, not
> built this pass** (cross-submodule build machinery, `R-BUILD-6`,
> deserves its own scoped design). Record:
> `docs/v2/SIM_Test_Execution_2026-08-31_test_fixes_and_remark.md`. The other
> four `#20` pieces (driver view itself, lane/pedestrian markings, free
> space, semantic segmentation) stay untouched — the last three now
> explicitly out of scope, driver view still blocked on a recording nobody
> has yet. **Same day, a second pass:** item #16's amber cause (empty
> config-bundle hash) fixed — `Pipeline` now keeps the `bundle_dirs`
> `_resolve_components` already computed instead of discarding it, exposing
> `component_bundle_shas()`/`component_bundle_paths()` (mirroring `component_
> build_shas()`), wired into `cli/run.py`/`cli/resim.py`'s `build_manifest`
> calls and `graph/modes.py`'s two `Pipeline` reconstructions; proven
> end-to-end (`Pipeline` → `build_manifest` → `RunManifest` → `evidence()` →
> `format_evidence()`, `tests/unit/test_a15_config_bundle_hash.py`, 69/69
> relevant tests pass, full suite unaffected). Not yet run against a real
> `df_sil.dll` (no `vs2026` `df` build this pass) — named as a follow-on.
> Also proposed, **not built**: a mechanical layer-count/port-name-spelling
> check for the `F-1`/`F-7`/`F-8`/`#5`/"five layers" copy-drift family —
> would catch 3 of 5, not `F-8` or `#5`, each for a stated reason. **Not yet
> committed — the next action is one combined commit decision covering
> both of today's passes.** `sim`: `graph/build.py`, `graph/modes.py`,
> `cli/run.py`, `cli/resim.py`, the new `tests/unit/test_a15_config_bundle_
> hash.py`, `misc/CONSOLIDATED_REQUIREMENTS.md`, this file, and both new
> records. `viz`: the three stale-topic-spelling test files. `df`:
> `test_layers.cpp` plus four `docs/viz/*.md` files.

## Do not

- **Do not propose a sim v3.** Two rewrites already happened. A third would repeat
  a failure this module has documented twice.
- **The specification freeze has ended by its own terms** (2026-08-28 — it ran
  *"until the demo runs"*, and it does). That is not licence to resume writing:
  what it outgrew the product by is in `memory.md` §4. New scope is now the
  author's call, from `DEMO_AND_SCOPE.md` §4.2's parked list.
- **Do not start Movement B to feel productive.** It is real debt, but it does not
  gate the POC.
- **Do not resume `docs/v1/`.** It is evidence, never a build order.

## Decisions in force

| | Decision | Taken |
|---|---|---|
| **A** | C++ wherever there is scope; the Python run path is legacy | 2026-08-27 |
| **B** | The player lives permanently in viz, as C++; Python player/scene deleted | 2026-08-27 |
| **C** | ~~ERG is the format~~ → **parked**, no measurement exists. POC runs on `mcap` | 2026-08-27 |
| **D** | vdy is the second module, but months away — nothing may depend on it | 2026-08-27 |
| **E** | The demo *is* the definition of done, explicitly as a POC | 2026-08-27 |

## Parked — and what unparks each

| Parked | Why | Unpark when |
|---|---|---|
| ERG · `WP-17` · `WP-18` | No ERG measurement exists or can be obtained | Real data arrives in a format sim cannot read |
| `WP-19` `WP-30` `WP-31` | No demo dependency | **Condition met 2026-08-28 — the demo runs.** Unparking them is now a scope decision, not a wait |
| The scenario finding — **now only its corpus half** (4 of 18 runnable, and those four under-asserted). Every *"never became"* and every vacuous pass is fixed | Author's call, 2026-08-27 | Before `B3` deletes `tools/carla/`, or when coverage rather than the warning path matters |
| 155 `R-REQ-9` citations | Bookkeeping, not code | `WP-31` |
| Conan editable test | `WP-31` scope | `WP-31` |

## Open risks

1. **A recording carrying no provenance grade still computes nothing** (`F-6`,
   2026-08-28 record). Validity is inferred from evidence grade, so a foreign or
   supplier file has every input flagged invalid — `F-1`'s symptom by a second
   route. Not on the demo path; does not report itself.
2. **`WP-01` cannot close** until a real GitHub Actions run is observed passing.
   The trigger was fixed 2026-08-27 and the push it was waiting on happened
   **2026-08-28** — so a run may now exist, unobserved: `gh` is not installed
   here. Someone must look. The gate itself still exits 1 on two parked items.
3. **The scenario corpus is thin and under-asserted.** Only 4 of 18 scenarios
   can run. All four now assert real computed behaviour (`bsd_curve_r172_passby`
   stopped being a false green 2026-08-28) — but its BSD warning fires at
   t≈7.4–9.6 s with no expectation covering it. Green is not coverage.
4. **A real capability loss, not silently dropped** (`SM-12`, 2026-08-29):
   `vantage_app.exe` has no bare-replay mode (no `--pipeline`) and no
   `--preset`/`--at`/`--workspace`/`--version` — the Python viewer that used
   to serve them is deleted, and there is no native equivalent yet.

## How Movement C gets tracked when it grows

Movement C will be done in pieces. **Those pieces are `WP` boxes in
`docs/v2/SIM_Implementation_Plan_v0.1.md`, tracked by `trace_check.py` like
everything else** — not a list in this file. This file only ever names the
*current* piece, in *The next action* above.

If you find yourself adding a checklist here, stop: that is a second copy of the
plan's state, and it will drift from it.

## Ending a session

Always update these three: **Where we are**, **The next action**, and one line in
the log.

Also update **Decisions**, **Parked** or **Open risks** — but *only* when the
underlying fact actually changed (a decision taken, an item unparked, a risk
retired), and by **replacing** a row, never appending one. Everything else stays
untouched.

**Analysis does not go here.** A campaign's findings and evidence go in a
`docs/v2/SIM_Test_Execution_<date>[_<campaign>].md`; this file links to it in one
line. That is what keeps this file one screen — **if it grew, it has failed.**

## Log — newest first, one line each, keep about five

- **2026-08-31** — Three pre-existing `viz` unit tests fixed
  (`viz_test_session`/`viz_test_pull_source`/`viz_test_erg_pull_integration`
  — stale fixtures asserting a pre-`450031e` topic spelling, no production
  code touched; `viz` `gtest` back to 49/49). `SYS-0089`'s missing
  `camera.chase` golden-Scene test added (`SW-0077`/`UT-layers-13`), plus
  three never-cascaded stale "five layers" mentions fixed alongside it
  (`UT-layers-11`, `SYT-HST-02`, `SYT-SCP-16`/`17`); `df_viz_test_layers`
  13/13, full `df` suite 311/312 (same already-dispositioned failure).
  `misc/CONSOLIDATED_REQUIREMENTS.md` re-marked against reality (status
  marks and false lines only): item #20 now names only driver
  view/video feed (three items moved out of scope entirely, author's
  call), video feed marked built, driver view stated plainly as unverified
  (no recording on hand carries the right camera topic) rather than
  guessed; §2 corrected from "only red is #20" to "25 of 25 green or
  amber". The stale-build pattern this week exposed twice (`cm_viz` since
  2026-08-21 missing `9ca1324`'s `Span<T>` fix; `sim`'s `sil` lib since
  2026-08-25 missing `450031e`'s canonicalization, both found by accident)
  named as a candidate for a mechanical freshness check, not built.
  **Uncommitted — reported, awaiting go-ahead.** Record:
  `docs/v2/SIM_Test_Execution_2026-08-31_test_fixes_and_remark.md`.
- **2026-08-31** — Item #16's amber cause fixed: `Pipeline.load` computed
  each `dll:`/`stubdll:` stage's bundle directory (`_resolve_components`'s
  `bundle_dirs`, needed by the cross-component agreement check) and then
  discarded it instead of storing it, so `component_bundle_shas()` never
  existed and `cli/run.py`/`cli/resim.py` had nothing to pass `build_
  manifest`'s `component_bundle_shas`/`component_bundle_paths` kwargs —
  every recording's `config_bundle_sha256` has been empty since the field
  was added. Fixed (`graph/build.py`, `graph/modes.py`'s two `with_mode`/
  `with_port_mode` reconstructions, `cli/run.py`, `cli/resim.py`); proven
  end-to-end with a new `tests/unit/test_a15_config_bundle_hash.py`
  (`Pipeline.component_bundle_shas()` → `build_manifest` →
  `RunManifest.components[].config_bundle_sha256` → `evidence()` →
  `format_evidence()`, the same chain `sim explain`/the evidence panel use)
  — 69/69 relevant unit tests pass, full unit suite 973 passed/1 skipped
  (unchanged), system suite 96 passed/9 skipped/1 failed (pre-existing
  Conan-credentials failure, unrelated). Not run against a real `df_sil.dll`
  + packed bundle (needs a `vs2026` `df` build not present this pass) —
  named as a follow-on, not fabricated around. Also proposed, **not
  built**: a mechanical layer-count/port-name-spelling check for the
  copy-drift family (`F-1`, `F-7`, `F-8`, `#5`, and the "five layers in
  four documents" trigger) — would have caught 3 of 5 (the "five layers"
  case, `F-1`'s stale-fixture half, `F-7`); would not have caught `F-8`
  (a numeric literal, not a count or spelling) or `#5` (a wiring/dead-code
  claim), stated as out of scope rather than forced. **Uncommitted —
  reported, awaiting go-ahead.** Record:
  `docs/v2/SIM_Test_Execution_2026-08-31_a15_bundle_hash_and_copy_drift.md`.
- **2026-08-30** — `WP-22` reviewed and pushed (`viz` `0f67af6`, `df`
  `b9ceba1`, `sim` `6495ab8`, superproject `c231337`). Then the
  legacy-recording `objects` gap it left open, closed and pushed (`viz`
  `82da36b`, `df` `1e2c01d`, `sim` `b40bcf3`, superproject `e91db63`):
  player applies the same `R-SIM-23` ingest map the engine does
  (`viz/session/ingest_loader.{hpp,cpp}`, `Session::Open`'s new
  `plugin_dirs`), plus a real porting gap found and closed
  (`viz::player::TopicToPortName` drops "source" like any other producer
  prefix, so an ingest-mapped port reaches `PortBytes` as its bare legacy
  name, never `R-SIM-21`'s `source.<port>` spelling —
  `conf/viz.yaml`/`layers/common.cpp`'s new `FindEither` try both).
  **Verdict:** the same screenshot now shows a real object box; `bsd.warning`
  stays unfixable here (the recording carries no `bsd.compState` at all).
  **Real, separate, pre-existing regression found in the same pass (not
  caused by it) and fixed, author's call:** rebuilding `sim`'s three-day-
  stale `sil` lib (needed to link the ingest-map feature) first exercised
  `450031e`'s 2026-08-28 topic-canonicalization change for real, which
  blacked out `WP-22`'s own just-pushed camera panel (confirmed independent
  of the ingest-map change itself) — fixed by canonicalizing
  `SessionImageResolver::Resolve`'s own lookup key, scoped entirely to
  `viz`'s player-side code (`df` needed no rebuild, re-verified unchanged at
  `311/312`). `viz` `gtest` 46/49 both before and after this fix — the 3
  failures share the same canonicalization root cause but are a different,
  stale-fixture-shaped repair, left open. **Camera fix uncommitted —
  reported, awaiting go-ahead** (the ingest-map work above is already
  pushed). Record:
  `docs/v2/SIM_Test_Execution_2026-08-30_legacy_objects_ingest.md`.
- **2026-08-30** — Item `#20`'s video-feed entry implemented: `WP-22`'s
  three pieces (camera layer in `df`'s real C++ plug-in, `SessionImageResolver`
  in `viz`, a second player panel) plus two things found live and not
  planned — a `VizTickView`/`PortBytes` `log_time_ns` field
  (`DF_VIZ_ABI_VERSION` 1→2, additive, checked against all 12 call sites)
  and `SW-0021`/`SYS-0088`'s "exactly five layers" amended to six (asked the
  author mid-session: amend vs. piggyback on an existing layer — amend
  chosen; a real `gen_viz_shim.py` build gate and cascading test counts
  fixed with it). `stb_image.h` vendored (public domain, pinned,
  `STBI_ONLY_JPEG`) for the JPEG decode. **Verdict:** a real frame from
  `bsd_curve_r172_passby.mcap` decodes and draws live in `viz_player.exe`'s
  "Camera" panel beside the BEV, screenshotted
  (`modules/sim/logs/wp22_camera_feed/`). `vantage_app.exe` untouched — its
  own tick path (`frame_bridge.cpp`) never fills `schema_bytes`, asked and
  resolved mid-session. Real, pre-existing, separate gap found (not
  caused): `objects`/`hud`/`bsd.warning` render nothing against this
  legacy-topic-named recording via bare replay — `TopicToPortName` expects
  a self-produced recording's own naming convention. `viz` gtest 49/49,
  `df` gtest 311/312 (the one failure is the already-dispositioned
  `render_svg` stale-token finding, untouched). **Uncommitted — reported,
  awaiting go-ahead.** Record: `docs/v2/SIM_Test_Execution_2026-08-30_wp22_camera_feed.md`.
- **2026-08-30** — Prior pass's `memory.md`/`Session`-finding work
  committed/pushed (R-GIT-1: `sim` `ad4abb9`, superproject `361992c`; `df`
  had nothing pending). Then item `#20`'s video-feed entry scoped against
  `WP-30` per the author's ask: **`WP-30` is the wrong anchor** — its 8
  boxes are io-side multi-camera codec/merge work (`SM-01`, 2026-08-20
  re-scope moved the display half to `viz`), and both candidate recordings
  (`bsd_curve_r172_passby.mcap`, `canonical_10mps_30m_20260714_174456.mcap`)
  already carry `carla/chase_camera` as `foxglove.CompressedImage`, verified
  readable with no regeneration and no `foxglove` package (schema decoded
  from the recording's own embedded `FileDescriptorSet`, `R-SIM-11`'s
  pattern). The real gap: `viz`'s `kReference`/`kImage` `Prim` kind and
  `Session` both already shipped (`VZ-09`/`VZ-12`, closed 2026-08-19) but the
  `ImageResolver` seam was deliberately left unfilled and is still wired to
  `nullptr` (`player_runner.cpp:317`) — no image has ever been drawn by this
  codebase; the player also has exactly one panel, hardcoded to
  `VIZ_SPACE_EGO_BEV`; and no layer provider anywhere calls
  `AppendReference`. No new `Prim` kind needed, no `sim` package opened.
  Not started — the author decides where the three-piece fix lands (`viz`
  vs. `df` plan) before anyone writes it. Record:
  `docs/v2/SIM_Test_Execution_2026-08-30_item20_video_feed_scoping.md`.
