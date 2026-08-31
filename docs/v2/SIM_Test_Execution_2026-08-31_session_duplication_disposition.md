# SIM Test Execution — 2026-08-31 — cross-repo `Session` duplication: disposition closed, both live

**Campaign:** `MOVEMENT_B_PLAN.md`'s "findings to decide on separately" item
3 — `adas_sim/session/` (Python) vs. `viz::session::Session` (C++) — recorded
2026-08-30, never acted on. Close the disposition with evidence: which is
live, for whom, on which targets. **Warned explicitly against repeating
this project's own disease** (a prior pass called `df`'s live CarMaker
plug-in dead code from line counts and directory listings alone, and was
wrong — `misc/memory.md` §3). Every claim below is re-derived from the build
graph, git log and real call sites this session, not carried over from the
2026-08-30 note.

## Evidence — Python `adas_sim.session.session.Session`

- **Files, re-measured:** `src/adas_sim/session/{session,history,signals,
  tick}.py`, 749 lines total (`183+178+168+220`) — matches the 2026-08-30
  count exactly; unchanged.
- **Packaging:** `pyproject.toml`'s `[tool.setuptools.packages.find]` →
  `include = ["adas_sim*"]` ships it; `sim = "adas_sim.cli:main"` is the real
  installed console-script entry point, not a dead declaration.
- **Real call sites** (`grep -rln "adas_sim\.session\|from adas_sim import
  session\|from \.\.session\|from \.session"`, excluding the module's own
  four files): **13 production source files** — `check/expect.py`,
  `check/runner.py`, `cli/list_cmd.py`, `cli/probe.py`, `config/fault.py`,
  `core/runner.py`, `diagnostics/diagnostics.py`, `diagnostics/evidence.py`,
  `diagnostics/explain.py`, `graph/build.py`, `orchestrate/progress.py`,
  `pyapi/api.py` — plus **14 test files**.
- **The load-bearing one:** `core/runner.py::build_session_from_recording`
  builds an `adas_sim.session.session.Session` directly
  (`from adas_sim.session.session import Session`) — this is the exact
  function `sim explain` calls, which this session's own earlier item
  (`A-15` real-path proof, `docs/v2/SIM_Test_Execution_2026-08-31_a15_real_
  path_proof.md`) just exercised against a real `df_sil.dll` build. It also
  backs `sim check`'s expectation evaluation (`check/runner.py`,
  `check/expect.py`) and the evidence chain (`diagnostics/evidence.py`,
  the same producer `sim explain`/the GUI evidence panel share, `R-SIM-25`).
  In short: **this is the Session behind every headless CLI verb** —
  `explain`, `check`, `probe`, `list` — the library-first, no-GUI face
  `R-SIM-16` requires to exist and be usable from a script in ~3 lines.
- **Git log** (`git log --oneline -- src/adas_sim/session/`): real, recent
  commits, most recently `09669cb` (`self.<port>`/`source.<port>`
  alternation, 2026-08-26/27 era) — actively maintained, not abandoned.

## Evidence — C++ `viz::session::Session`

- **Files:** `modules/viz/cpp/viz/session/{session,ingest_loader,
  pull_source,source,tick,transport_client}.{hpp,cpp}`, 1222 lines across
  the directory. Own header states explicitly: *"the C++ rewrite of
  `adas_sim.session.session.Session`, living in `adas-viz-player`."*
- **Build graph** (`modules/viz/CMakeLists.txt`): `session.cpp` (plus four
  siblings) compiles into `add_library(adas-viz-player STATIC ...)`, which
  `target_link_libraries(adas-viz-player PUBLIC AdasSim::io
  AdasInterfaces::AdasInterfaces ...)` — a real, declared dependency on the
  very `simcore`/`io` C++ codec layer this session's item 4 just patched
  (`mcap.cpp`'s `capture_time_ns` fix). `adas-viz-runner` links
  `adas-viz-player` (`target_link_libraries(adas-viz-runner PUBLIC adas-viz
  adas-viz-player ...)`), and `add_executable(viz_player ...)` links
  `adas-viz-runner` — a direct, unbroken chain from `session.cpp` to the
  real, currently-shipped `viz_player.exe`, the exact binary this session's
  earlier `WP-22` work (camera-panel fix, `docs/v2/SIM_Test_Execution_2026-
  08-30_legacy_objects_ingest.md`) built, ran and screenshotted.
- **Tests:** `tests/unit/test_session.cpp` (`viz_test_session` — one of the
  three tests this same week's own pass fixed for a stale topic-spelling
  assertion, `docs/v2/SIM_Test_Execution_2026-08-31_test_fixes_and_remark.md`).
- **Git log** (`git log --oneline -- cpp/viz/session/` in `modules/viz`):
  most recent `82da36b` — **this is literally the ingest-map commit from
  this session's own item-1 CI-descope work's prior history**, i.e. actively
  touched within the last 24 hours of this same effort, not stale.

## Verdict: both are live. No deletion.

This is outcome (c) of the three the task named as acceptable — **reported
with evidence, nothing deleted.** Both implementations are exercised by a
real, currently-shipped binary (`viz_player.exe` for C++) and a real,
currently-shipped console script (`sim` for Python), each for a genuinely
different consumer:

- **Python `Session`** — the headless, library-first engine face (`sim
  explain`/`check`/`probe`/`list`, `R-SIM-16`): usable from a script in a
  few lines, no GUI, no C++ toolchain required to run it.
- **C++ `Session`** — the interactive GUI face (`viz_player.exe`): real-time
  rendering, no Python runtime dependency on the render path (`R-SIM-11`'s
  "a host must not require generated protobuf bindings or a sibling
  checkout" — a GUI shipped to a user's machine cannot assume a Python
  install any more than `df_sil.dll` can).

**The framing this item was handed ("the largest surviving instance of this
project's copy-never-move pattern") is corrected, not just confirmed.**
Re-reading both headers side by side: this is not a superseded-vs-leftover
pair like the old Python scene/render/player stack `B1` deleted (where one
side was genuinely dead once the other shipped). It is the **same
deliberate cross-language-twin pattern `io/mcap.py` ↔
`simcore/io/codecs/mcap.cpp` already uses** — a C++ *rewrite*, by its own
header's own word, of a Python original that keeps a real, different job
once the rewrite exists. `copy-never-move` names code left standing after
its replacement made it redundant; this is two ports of one model serving
two audiences that cannot share a runtime, which is a different shape with
a different risk profile.

**The real, smaller risk this framing correction does not erase:** the two
implementations can drift, and already have — `SessionImageResolver::
Resolve`'s topic-canonicalization regression (`docs/v2/SIM_Test_Execution_
2026-08-30_legacy_objects_ingest.md`'s own "real, separate, pre-existing
regression" section) was exactly a C++-side Session-adjacent component
falling out of step with a Python-side convention change. No test today
asserts the two `Session`s agree on anything across the language boundary
(each has its own unit tests, never a shared fixture). **Named as a real,
open risk, not proposed as this pass's fix** — building a cross-language
parity check is a new, scoped initiative (a golden-fixture comparison, or a
documented list of invariants each side's tests must individually cover),
not a deletion, and not attempted here without being asked.

## Disposition

`misc/MOVEMENT_B_PLAN.md`'s "findings to decide on separately" item 3
rewritten: from "real, no owner, not acted on" to closed — both live,
evidence above, reframed as a cross-language twin rather than
copy-never-move debt, with the drift risk named explicitly as the
follow-on that would unpark it (a shared-invariant/parity check, not a
deletion).

## Files changed

No code changed — read-only investigation, documentation-only disposition.
`modules/sim`: `misc/MOVEMENT_B_PLAN.md`, `misc/START_HERE.md`, this record.
`modules/viz`: untouched. No commit needed in `viz`.
