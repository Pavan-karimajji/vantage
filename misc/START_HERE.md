# START HERE

**Updated:** 2026-09-01 (Step 7 fully closed; next action reframed) · **Read this first, then run the status command below.**

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

**2026-08-31 — hosted CI closed out entirely, author's decision.** Not fixed,
not observed, not abandoned — descoped: `scripts/ci_gate.py` stays as the real
local gate; `.github/workflows/sim-ci.yml` kept with a header stating it is
unobserved and unmaintained by decision, so its presence is never mistaken for
a passing run. `WP-01`'s two items that used to wait on this — the 154
`R-REQ-9` citations and the Conan-editable-install system test (the latter
was actually failing here on a Conan-remote credential prompt, not skipping)
— are now-**decided not-doing**, not pending-on-`WP-31`; `IMP-0366` closed
against the decision (17/18 `Lands`). `IMP-0417` stays open — real, unrelated,
`WP-31`-scoped content gap, left untouched. Board `#25` re-marked 🟢: headless
parity (`GT-9`) already proved the requirement; CI was only ever evidence for
it. `misc/memory.md` §6 corrected in place: "no CI anywhere" is now a closed
decision, and "no dated evidence it passes" was answered separately, by the
eighteen (now nineteen) `docs/v2/SIM_Test_Execution_*.md` records this module
has produced since 2026-08-27. Record:
`docs/v2/SIM_Test_Execution_2026-08-31_ci_descope.md`. **Committed, not
pushed** (`sim` `8b3f4de`, superproject `6cc0642`) — push was not asked for
this pass (`R-GIT-2`).

**2026-08-31, same day — board `#20` closed green.** Author's decision: the
chase camera (`WP-22`, shipped 2026-08-30) is sufficient; driver view is not
wanted. `#20`'s row narrowed to what it still covers (video feed publishing,
built) with driver view joining the other three already-out-of-scope items;
`misc/CONSOLIDATED_REQUIREMENTS.md` §2 rewritten from "driver view...
unverified" to **25 of 25 green or amber, none red, none unverified**. New
Decision `G`. No code changed — a scope decision against an already-shipped
capability, not a build. Record:
`docs/v2/SIM_Test_Execution_2026-08-31_item20_close.md`. **Committed, not
pushed** (`sim` `ca30250`, superproject `4c64285`).

**2026-08-31, same day — item `#16`'s `A-15` config-bundle-hash fix proven on
the real path.** Yesterday's fix was Python-only (`Pipeline` unit test). This
session built `df_sil` for `vs2026` (Conan's full install path still blocked
by the same credential gap as `WP-01`'s Conan-editable test; worked around
with a direct `cmake --build` against the already-resolved dependency graph
on disk — a real relink, bundle genuinely repacked,
`bundle.sha256=966f0e30...`), ran the demo's own `sim resim --save`, and read
back that exact hash as `config_bundle_sha256` both from the recording's own
manifest and through `sim explain`'s evidence chain (the same formatter the
player's evidence panel calls, `R-SIM-25`). Board `#16` re-marked 🟢. **One
real, separate gap found and named, not fixed:** the config bundle's actual
*bytes* are still not embedded in the recording (`R-SIM-3a`'s other half) —
`simengine`'s own writer embeds no run manifest at all, a different, larger
mechanism `A-15` never touched. Record:
`docs/v2/SIM_Test_Execution_2026-08-31_a15_real_path_proof.md`. **Committed,
not pushed** (`sim` `f81de52`, superproject `802801a`).

**2026-08-31, same day — `simcore/io/codecs/mcap.cpp`'s own named
`capture_time_ns` gap closed.** That file's top note said the reader trusted
`publishTime` unconditionally, never replicating `io/mcap.py`'s
`manifest_version >= CAPTURE_TIME_MANIFEST_VERSION` gate (`R-SIM-14`),
because `simcore` has no structured `RunManifest` C++ type. Fixed without
building that type: a narrow, targeted scalar read of the one
`manifest_version:` line the opaque `manifest` meta block's bytes carry
(`ParseManifestVersion`, explicitly documented as not a YAML parser),
computed once per `Open()` (`DetermineCaptureTimeAwareness`) and gating
`Pull()`'s `capture_time_ns` — `nullopt` for any file with no manifest or a
pre-two-clock one, never a filled-in value. **A second, dormant bug found
while tracing this and fixed alongside it:** `ToString(MetaKind::
kRunManifest)` returned `"run_manifest"`, not the `"manifest"` string
Python's writer actually uses — never exercised before (nothing called it),
but would have silently defeated this very fix. Three new regression cases
in `test_ut_io_mcap_roundtrip.cpp` (no new `UT-IO-nn` id — those numbers are
already spoken for by unrelated requirements; same "regression coverage, not
a new requirement" shape `test_ut_io_erg_negative.cpp` already uses).
`simcore_tests`: 6/6 on the affected suite, 215/218 on the full suite — the
one failure is the already-documented, pre-existing Windows temp-dir flake
(`UtEdg08Reproducer`, verified 2026-08-28), confirmed unrelated. Record:
`docs/v2/SIM_Test_Execution_2026-08-31_io_capture_time_gap.md`. **Committed,
not pushed** (`sim` `c5a095e`, superproject `f848ea5`).

**2026-08-31, same day — cross-repo `Session` duplication disposition
closed: both live, nothing deleted.** `MOVEMENT_B_PLAN.md`'s "findings to
decide on separately" item 3 (recorded 2026-08-30, never acted on)
re-measured from the build graph and git log, not carried over —
`adas_sim/session/` (Python, unchanged 749 lines, 13 real callers + 14
tests, the `Session` behind every headless CLI verb) and `viz::session::
Session` (C++, compiled into `adas-viz-player` → `adas-viz-runner` → the
real, shipped `viz_player.exe`) are **both genuinely live**, each for a
consumer that cannot share the other's runtime. **Reframed, not just
confirmed:** this is the same deliberate cross-language-twin pattern
`io/mcap.py` ↔ `mcap.cpp` already uses, not `B1`'s superseded-vs-leftover
shape — "copy-never-move" was the wrong label. **No deletion.** The real
remaining risk — drift between the two implementations, already manifested
once (`SessionImageResolver::Resolve`'s topic-canonicalization regression,
found and fixed 2026-08-30) — is named as a new open risk, not fixed this
pass. No code touched in either `sim` or `viz`. Record:
`docs/v2/SIM_Test_Execution_2026-08-31_session_duplication_disposition.md`.
**Committed, not pushed** (`sim` `0a5732a`, superproject `6e6e7a2`).

**2026-08-31, same day — the stale-build pattern named twice this week
(Open Risk, below) is answered with a real, mechanical check, not just
named again.** `scripts/check_build_freshness.py`, superproject root
(cross-submodule, so it cannot live inside this module alone) — for every
Conan-editable-registered package, every binary under its own `build*/`
dirs is compared against the newest file in what actually feeds that
package's build (`src/`/`include/`/`conf/`/recipe files, never the whole
tree). Run by hand before trusting a build, same discipline as
`check_invariants.py`/`setup.py`; deliberately not wired into any
automated gate (hosted CI out of scope, Decision F) or into any
component's byte-identical `build.py`/`build.bat` (`R-BUILD-6`, too big for
this item). **A real bug found and fixed before this shipped:** the first
version walked each package's whole root as "source," producing 26 mostly-
false findings on this machine's real registry — one build tree's own
`ALL_BUILD.lastbuildstate` bookkeeping read as "the source changed" against
a *different* build tree's artifact, `CompilerIdC.exe` treated as a real
deliverable, `mathlib/gui.bat` counted as C++ source. Narrowed and fixed;
re-run, **2 real, plausible findings** (`interfaces`/`mathlib`'s own
`build/`/`build-sil-vs2026` `.lib`s, both genuinely behind their own
`conanfile.py`), neither rebuilt here. 10/10 new unit tests. Record:
`docs/v2/SIM_Test_Execution_2026-08-31_build_freshness_check.md`. **Not yet
committed — reported, awaiting go-ahead.**

**2026-09-01 — Step 7 executed, two phases, both committed.** Author
approved execution with two amendments (run the `sim_api_reference.md`
conditional check first; don't touch `.claude/rules/sim.md`, collect its
edits for separate approval). The conditional check found a real, separate
finding: `sim_api_reference.md` describes `scene`/`render`/`app` Python
packages deleted wholesale by `7d4c626` (2026-08-29, Decision B) — excluded
from retirement, left as full text, unremediated. Phase 1: 9 `docs/v1/`
files retired to stubs naming their successor and commit `1e2bb5b`;
`FROZEN_DESIGN_ORIGINS.md` created holding the two externally-cited
fragments (Scene primitive catalogue/style tokens, Vantage naming/what-
shipped) verbatim; `sim_requirements.md` superseded with an `R-REQ-2`
compact disposition table built from `SIM_System_Requirements_v0.1.md`
§25's own existing crosswalk; `sim_naming_and_diagnostics.md` inspected,
left untouched (almost nothing to cut, confirmed). 5 cross-repo citing
files repointed in `df`/`viz`. Phase 2: `SIM_Implementation_Plan_v0.1.md`'s
85 essay-length checkbox rows compressed — none already cited a Test
Execution record (all pre-date the 2026-08-27 dated-record discipline), so
each was pointed at its closing git commit instead, per the author's
decision when this scope mismatch was raised mid-session; 70,504→33,343
characters (~53% cut). `trace_check.py`/`check_invariants.py` verified
clean after each phase, zero derived-mark drift. **Net: `docs/v1/`
17,681→2,078 lines (−88%); `docs/v2/` line count unchanged as the plan
itself predicted, byte weight −~18%; total tracked set ~35,894→~22,195
lines (−38%), not the plan's own "~4,000–4,500" headline, which its own
§2 could not have reached given `docs/v2/` was never going to shrink in
line count — named as the plan's own arithmetic inconsistency, not an
execution shortfall.** Record:
`docs/v2/SIM_Test_Execution_2026-09-01_step7_execution.md`.

**2026-09-01, same day — pushed, and the two rule-file items closed to
one.** All four repos (`sim`/`df`/`viz`/superproject) pushed to origin,
R-GIT-1 order. Of the two `.claude/rules/sim.md` edits collected above,
the mechanical one is **applied**: `R-SIM-1`'s dangling "Full map: §5.8"
pointer dropped, and every stale v1-doc description in the normative-index
preamble (`sim_requirements.md`, `sim_architecture.md`,
`sim_sil_contract.md`, `sim_resim_and_recording.md`,
`sim_scenarios_and_expectations.md`, `sim_player.md`,
`sim_visualization_spec.md`, `sim_portability.md`, `sim_learn.md`)
corrected to say what each file actually holds now — its **`sim_api_reference.md`
clause left byte-for-byte untouched**, since narrowing or softening that
one claim is the substantive decision, not bookkeeping. That decision was
presented with three options and their costs (retire with the claim
dropped, like its nine siblings; keep the file and narrow the claim to the
parts spot-checked as still true — CLI verbs, the closed error taxonomy,
now relocated to `diagnostics/errors.py` — at the cost of a maintenance
burden that recurs every time more logic moves to C++; or mark it
superseded-in-part and change nothing else, which fixes nothing a reader
still has to verify every claim). Recommendation given: retire it like the
other nine — not decided here. `misc/memory.md` gained a closing §10
against its own 2026-08-27 findings, stating what closed (`§1`, `§3` twice
now, `§4` including the shrink plan's own caught counting error, `§6`) and
what is still open (`§2`'s zero-progress packages, six amber board items,
`sim_api_reference.md` itself) rather than declaring the module done.

**2026-09-01, same day, closing pass — the author accepted the
recommendation.** `sim_api_reference.md` retired to a stub, same pattern as
its nine siblings, naming both what was wholesale wrong (§1/§1a's
`scene`/`render`/`app` rows, §5 — deleted by `7d4c626`) and what had merely
moved (§9's error taxonomy to `diagnostics/errors.py`, §10's CLI table
~80% still accurate) so a later reader knows what was lost versus relocated.
`.claude/rules/sim.md`'s "a signature there is a contract" clause removed,
not reworded. `misc/memory.md` §10 updated to close that item rather than
list it as open. **This closes Step 7 in full** — nothing from
`STEP_7_SHRINK_PLAN.md` remains undecided. **The next action** below is
rewritten to match: Movements A/B/C are complete, and what is left is
named as remaining capability against a working demo, not a task list.

**2026-08-31, Step 7 — document-set shrink plan written, not executed.**
`memory.md`'s last untreated root cause (§4/§7: 41,341 lines / 3.3 MB of spec
for a concept an external reference expresses in 5 KB) now has a scoped
answer: `misc/STEP_7_SHRINK_PLAN.md`. Target: `docs/v1`+`docs/v2`+`misc`
tracked `.md` from ~35,894 lines to ~4,000–4,500. Read-before-cut discipline
applied per-file (`git log` + repo-wide grep + a v2 `Trace`-field scan for
`R-REQ-2` exposure) rather than the line-count sweep that mis-scoped `viz`
last time (`memory.md` §3): **9 of 12 `docs/v1/` files have zero live
external readers and are safe to retire to a stub; 2 (`sim_visualization_
spec.md`, `sim_player.md`) are cited from real, live `df`/`viz` requirement
docs and one C++ header (`workspace_mode.hpp`) and must be extracted, not
deleted; `sim_requirements.md` carries 49 IDs live in v2 `Trace` fields and
is governed by `R-REQ-2` — superseded with a compact register, never
dropped; `sim_naming_and_diagnostics.md` turned out to already be mostly
the cited content (260 of 440 lines) and stays.** A separate, real defect
found in the same pass: `SIM_Implementation_Plan_v0.1.md` has 85 checkbox
rows over 300 characters (79,512 total), essay narrative that belongs in a
Test Execution record per `R-REQ-6a`'s own "closed by \<clause\>" discipline
— proposed for compression, not structural change. All ten of `memory.md`
§8's "genuinely good" ideas confirmed already anchored in a root rule +
a v2 requirement, independent of anything v1 retirement would remove.
**Nothing deleted or edited in `docs/v1`/`docs/v2` this pass** — proposal
only, awaiting the author's go-ahead to execute.

## The next action — exactly one

> **Write `WP-01` of the PARITY set: the ingest map keyed by port, with an
> ordered address list.** Eight design rows, each naming a file and a symbol,
> blocked by nothing. **`docs/v2/parity/README.md` first**, then run its
> checker — that is what answers "where do I start", not a written-down list.
>
> That set is the requirement work for bringing this module and *Vantage* up to
> the behaviour of a production-grade developer bench. It **amends** the v2 set;
> it does not replace it, and there is no sim v3 here or proposed. Its reasoning
> lives in its change register, its build order and file-level design in one
> document beside it.
>
> **The next thing is code, not documents.**

---

**Everything below this line is the pre-PARITY position, unchanged.**

> **Movements A, B and C are complete. The demo works.** `DEMO_AND_SCOPE.md`
> §1 runs end to end, all five clauses, watched and screenshotted (`WP-35`,
> closed). That is the baseline every item below is measured against — not
> a task list with a broken core, a working system with named gaps in
> breadth.
>
> **What remains is remaining capability, not unfinished work:**
>
> - **Six board items are amber, not red** (`CONSOLIDATED_REQUIREMENTS.md`
>   — `#2`/`#3` the three-pillar/two-face architecture, `#12`/`#13` crash
>   isolation and determinism, `#17` export one-way-ness, `#24` geometry
>   from calibration). Each already does its job for the one case the demo
>   exercises; each is amber because it does not yet do it for every case
>   the concept promises.
> - **Five work packages are at zero boxes** (`misc/memory.md` §2 —
>   `WP-17`/`18`/`19`/`30`/`31`: the io codecs/export, images, packaging).
>   Named honestly as not started, not guessed at as partial.
> - **`sim_api_reference.md`'s own disposition is closed** (retired
>   2026-09-01, `.claude/rules/sim.md`'s stale claim removed with it) — not
>   a remaining item, listed here only so the next reader doesn't go
>   looking for it as one.
>
> **Pick one board amber or one zero-progress package.** Nothing here
> gates anything else — that is what "the demo works" means. `trace_check.py
> --status` names the next untouched package by number if a default is
> wanted (`WP-17` as of 2026-09-01); it is not a priority order, only the
> lowest-numbered gap. History for how each of the above got here lives in
> **Where we are**, above, and in `docs/v2/SIM_Test_Execution_*.md`; this
> field states only where things stand today.

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
| **F** | Hosted CI is out of scope. `scripts/ci_gate.py` (run by hand, both platforms) is the real gate; `.github/workflows/sim-ci.yml` stays as an explicitly unobserved, unmaintained artifact. `WP-01`'s two items that were waiting on this (the stale `R-REQ-9` test-id citations, the Conan-editable-install system test) are **not-doing**, not pending — recorded, not silently dropped | 2026-08-31 |
| **G** | **No driver view.** The chase camera (`#20`, `WP-22`) is sufficient; a driver-view camera feed is not wanted. Board `#20` closes green with nothing left open in it — stated explicitly so it cannot quietly reopen as a "gap" | 2026-08-31 |

## Open — PARITY's three, none blocking

Raised by writing the set, and none of them stops the first seven work
packages. Each is a decision no tool can make.

| # | Question | Blocks |
|---|---|---|
| 1 | **The absent-port convention.** `SYS-0084` says an unused stage's ports *shall simply be absent*. The bench study's `C-04` wants them *bound to a typed, inert sink* so an upstream producer keeps writing somewhere legal. Both keep the graph whole; only one can be the convention. | Nothing — `WP-02` proceeds either way |
| 2 | **Does the resolved run spec carry which candidate address matched**, or does the run manifest alone carry it? | Nothing — the manifest already does |
| 3 | **Who writes `IF-06`** (`Source`/`Feed`) in `modules/viz`, and when? It is unwritten, and every transport control is a call on it. | `WP-08` and `WP-09` only |

## Parked — and what unparks each

| Parked | Why | Unpark when |
|---|---|---|
| ERG · `WP-17` · `WP-18` | No ERG measurement exists or can be obtained | Real data arrives in a format sim cannot read |
| `WP-19` `WP-30` `WP-31` | No demo dependency | **Condition met 2026-08-28 — the demo runs.** Unparking them is now a scope decision, not a wait |
| The scenario finding — **now only its corpus half** (4 of 18 runnable, and those four under-asserted). Every *"never became"* and every vacuous pass is fixed | Author's call, 2026-08-27 | Before `B3` deletes `tools/carla/`, or when coverage rather than the warning path matters |

**Removed 2026-08-31, not unparked:** the 155 `R-REQ-9` citations and the Conan
editable-install system test are **not-doing** (Decision F) — they no longer
wait on `WP-31` or anything else. See the log entry below and
`docs/v2/SIM_Test_Execution_2026-08-31_ci_descope.md`.

## Open risks

1. **A recording carrying no provenance grade still computes nothing** (`F-6`,
   2026-08-28 record). Validity is inferred from evidence grade, so a foreign or
   supplier file has every input flagged invalid — `F-1`'s symptom by a second
   route. Not on the demo path; does not report itself.
2. **The scenario corpus is thin and under-asserted.** Only 4 of 18 scenarios
   can run. All four now assert real computed behaviour (`bsd_curve_r172_passby`
   stopped being a false green 2026-08-28) — but its BSD warning fires at
   t≈7.4–9.6 s with no expectation covering it. Green is not coverage.
3. **A real capability loss, not silently dropped** (`SM-12`, 2026-08-29):
   `vantage_app.exe` has no bare-replay mode (no `--pipeline`) and no
   `--preset`/`--at`/`--workspace`/`--version` — the Python viewer that used
   to serve them is deleted, and there is no native equivalent yet.
4. **The Python and C++ `Session` twins can drift, and already have once**
   (2026-08-31 disposition, `docs/v2/SIM_Test_Execution_2026-08-31_session_
   duplication_disposition.md`). No test asserts the two agree on anything
   across the language boundary — each side's unit tests cover only its own
   implementation. Unparks with a cross-language parity/invariant check,
   not a deletion (the two are not redundant, see the disposition record).

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

- **2026-09-05** — PARITY requirement set written, `docs/v2/parity/`. Four
  layers down to file-and-symbol design rows, landed by work packages whose
  contents are derived rather than listed. Restarted once at stage 1 on the
  author's finding that a two-layer set cannot be built from — correct, and the
  reason is dated in its `layers.yaml`. Three rules came out of it and now bind
  every module: `R-REQ-13`/`R-REQ-14` (cap the commentary, never the count or
  the length) and `R-REQ-6a`'s plan checks, mechanised in the shared checker.
  Two corrections to its own record are on the record rather than quietly
  fixed: `SYS-0004` retired the day it was written as a duplicate of
  `SYS-0022`, and the claim that `SW-0011`/`SW-0032` would become "actively
  wrong" was too strong — both survive.

- **2026-09-01** — Step 7 fully closed. `docs/v1/` all 10 files retired
  (9 to stubs + `sim_requirements.md`'s compact register, 17,681→2,078
  lines), including `sim_api_reference.md` — held back pending a
  conditional check, found to describe `scene`/`render`/`app` packages
  `7d4c626` deleted, three options presented, author accepted retiring it
  like its siblings, its stub naming both what was wrong and what merely
  moved. 85 essay checkbox rows compressed to closing-commit pointers.
  `.claude/rules/sim.md`'s two mechanical repoints applied and its stale
  "signature is a contract" clause removed outright. `misc/memory.md` §10
  closed against `sim_api_reference.md` too — only `§2`'s zero-progress
  packages and six amber board items remain open, reframed as remaining
  capability against a working demo, not unfinished work. **The next
  action** rewritten to match. Pushed across `sim`/`df`/`viz`/superproject,
  R-GIT-1 order. `trace_check.py`/`check_invariants.py` clean throughout.
  Record: `docs/v2/SIM_Test_Execution_2026-09-01_step7_execution.md`.
- **2026-08-31** — Everything pushed (sim, df, superproject). Two freshness-
  check findings resolved (`mathlib` rebuilt on real `vs2026`; `interfaces`'
  flagged artifact was a dead pre-`WP-33` leftover, deleted). `df`'s
  `.IPGControl.conf` gitignored. Step 7 document-set shrink plan written
  (not executed): `misc/STEP_7_SHRINK_PLAN.md`, target ~35,894 → ~4,000–4,500
  tracked lines, read-before-cut per file, `R-REQ-2` respected for
  `sim_requirements.md`'s 49 live trace citations.
- **2026-08-31** — Build-artifact freshness check built
  (`scripts/check_build_freshness.py`, superproject root, cross-submodule):
  for every Conan-editable package, its own `build*/` binaries vs. the
  newest file in what actually feeds its build (`src`/`include`/`conf`/
  recipe files). Run by hand, not wired into any gate. **A real bug found
  and fixed before shipping:** the first version scanned each package's
  whole tree as "source," producing 26 mostly-false findings (one build
  tree's own bookkeeping read as source, `CompilerIdC.exe` treated as a
  deliverable, a dev launcher `.bat` counted as C++ source) — narrowed;
  re-run, 2 real findings (`interfaces`/`mathlib`, both behind their own
  `conanfile.py`), neither rebuilt. 10/10 new unit tests. **Uncommitted —
  reported, awaiting go-ahead.** Record:
  `docs/v2/SIM_Test_Execution_2026-08-31_build_freshness_check.md`.
- **2026-08-31** — Cross-repo `Session` duplication disposition closed:
  re-measured from the build graph and git log (not carried over), both
  Python `adas_sim/session/` and C++ `viz::session::Session` are genuinely
  live for different consumers (every headless CLI verb; the real shipped
  `viz_player.exe`). Reframed as a cross-language twin (`io/mcap.py`↔
  `mcap.cpp`'s pattern), not copy-never-move debt — no deletion. Drift risk
  (already manifested once) named as a new open risk. No code touched.
  **Committed, not pushed** (`sim` `0a5732a`, superproject `6e6e7a2`).
  Record:
  `docs/v2/SIM_Test_Execution_2026-08-31_session_duplication_disposition.md`.
- **2026-08-31** — `mcap.cpp`'s own named `capture_time_ns` gap closed: a
  narrow scalar read of `manifest_version:` (not a full `RunManifest` port)
  gates `Pull()`'s `capture_time_ns`, mirroring `io/mcap.py`'s
  `CAPTURE_TIME_MANIFEST_VERSION` check — `nullopt` for no manifest or a
  pre-two-clock one, never defaulted. Dormant `MetaKind::kRunManifest`
  string-mismatch bug (`"run_manifest"` vs. Python's real `"manifest"`)
  found and fixed alongside it. Three new regression cases,
  `simcore_tests` 215/218 (1 pre-existing, unrelated Windows temp-dir
  flake). **Committed, not pushed** (`sim` `c5a095e`, superproject
  `f848ea5`). Record:
  `docs/v2/SIM_Test_Execution_2026-08-31_io_capture_time_gap.md`.
- **2026-08-31** — `A-15`'s config-bundle-hash fix proven on the real path:
  real `vs2026` `df_sil` build (Conan blocked by the known credential gap,
  worked around with a direct `cmake --build` against the already-resolved
  graph), demo's own `sim resim --save`, real `config_bundle_sha256`
  (`966f0e30...`) read back from both the recording's manifest and `sim
  explain`'s evidence chain. Board `#16` re-marked 🟢. Separate gap named,
  not fixed: the bundle's actual bytes still are not embedded in the
  recording. **Committed, not pushed** (`sim` `f81de52`, superproject
  `802801a`). Record:
  `docs/v2/SIM_Test_Execution_2026-08-31_a15_real_path_proof.md`.
- (older entries trimmed per this section's own "keep about five" rule —
  see git history on this file for anything earlier, including Board `#20`
  closing green 2026-08-31.)
