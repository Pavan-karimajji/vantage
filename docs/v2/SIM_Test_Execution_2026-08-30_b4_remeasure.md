# SIM — Test Execution Record — 2026-08-30 · `B4` re-measured — 4 of 5 claimed overlaps were never overlaps

**This record is evidence, not a specification.** Exempt from the freeze on
that basis, never edited after the fact. A later campaign is a **new file**.
**Reads with:** `SIM_Test_Execution_2026-08-30_movement_b_plan_audit.md` and
`..._b2_execute_b3_rescope.md` — the same day's earlier corrections to `B2`
and `B3`, same method applied to `B4`.

## Campaign

| | |
|---|---|
| Question | `B4`'s counts predate `B1`'s deletion of the Python scene/render/player tree, and an earlier pass this session already found `session` Python-only and `abi` C++-only against the original five-row table. Re-measure properly: for each of `io`, `runspec`, `session`, `abi`, `diagnostics`, what exists on each side today, and is it a genuine second implementation or two different things sharing a name? Delete nothing. If `B4` is empty like `B3`, retire it and record Movement B done. |
| Method | `A` (analysis — read the code and its own header comments on both sides of each claimed overlap; `git`/`find`/`wc` for the raw counts, not assumed) |
| Platform | native Windows, this session's shell |
| Scope | `modules/sim/misc/MOVEMENT_B_PLAN.md` only. **No deletion executed** — `io`, the one real finding, is left exactly as-is per instruction |
| Committed | Not yet — review-first, per the user's ask |

## Result — per-item findings

| Item | Python (`adas_sim`) | C++ (`simcore`) | Verdict |
|---|---|---|---|
| `io` | `io/` — 5 files, 1,266 lines | `io/` — 10 files, 1,673 lines | **Genuine second implementation, not yet at parity.** `registry.cpp`: *"Ports `io/registry.py`'s ... behaviour."* `codecs/mcap.cpp`: *"the C++ twin of `io/mcap.py` ... ported"*, and its own comment names the gap — it does not yet replicate `io/mcap.py`'s `manifest_version >= CAPTURE_TIME_MANIFEST_VERSION` gate. Real, but the C++ side's own author already flagged it as unfinished |
| `runspec` | `runspec/` — 6 files, 1,614 lines. `emit.py`: *"the seam's own producer"* | `runspec/` — 1 file (`load.cpp`), 255 lines | **Not a duplicate.** `load.cpp`: *"parses the JSON text `emit_run_spec`/`write_run_spec` produced."* Producer (Python) and consumer (C++) of the same artifact, not two implementations of the same responsibility |
| `session` | `session/` — 4 files, 749 lines; imported by 11 real source files and 14 test files today | none in `simcore` | **Real duplicate, wrong repo.** `modules/viz/cpp/viz/session/session.hpp`: *"the C++ rewrite of `adas_sim.session.session.Session`, living in `adas-viz-player`."* Both halves live and used, but the C++ half is in `modules/viz`, not `simcore` — outside `B4`'s own stated scope (`modules/sim/src`'s two stacks) |
| `abi` | none in `adas_sim` | `abi/simcore.cpp` — 514 lines (`simEngineCreate`/`Run`/`Destroy`) | **Not an overlap.** The per-tick engine's own generic ABI — C++-only by design (Decision A); Python has nothing here because Python does not host a per-tick engine any more. Nothing missing |
| `diagnostics` | `diagnostics/` — 13 files, 1,724 lines: `determinism`, `explain`, `evidence`, `tolerance`, `suggest`, `console`, ... | `diagnostics/` — 6 files, 470 lines: `breakpoints`, `reproducer`, `trace`, `cost`, `graph_dump`, `modules` | **Not a duplicate.** Python is offline reporting/CLI tooling (once-per-run); C++ is runtime engine instrumentation hooked directly into the execution loop (per-tick). `evidence.py`'s own header names the split: *"viz's own C++ evidence chain (`BuildEvidence`) is the live [formatter]"* for the runtime half, this file stays the headless `sim explain --at` half |

Evidence for each verdict is a direct quote from that file's own header
comment, not an inference from directory names or line counts — the exact
failure mode the original five-row table fell into.

## Result — `B4` is re-scoped, not retired

**1 of 5 rows is real** (`io`), so `B4` is *not* empty the way `B3` turned
out to be — **Movement B is not fully done.** `io`'s own C++ code already
documents why it is not actionable this pass (the `manifest_version`/
capture-time parity gap), so nothing was deleted, matching the instruction.
`B4` is rewritten in `MOVEMENT_B_PLAN.md` from a five-row sweep to this one
item: close the parity gap in `simcore/io/codecs/mcap.cpp`, then delete
`adas_sim/io/`'s overlapping half.

`runspec`, `abi` and `diagnostics` are retired from `B4` — they were never
overlaps, so there is nothing to resolve. `session` is retired from `B4`
specifically (real, but the C++ half lives in `modules/viz`, a different
repo than `B4` was ever scoped to touch) — named as its own future
initiative, not folded into this movement.

`WP-16` (`sil_host` retirement, 10/11 boxes per `trace_check.py --status`,
unchanged) and `WP-02`'s "seven duplications"/restructure claims were
**not** independently re-verified this pass — out of the five-overlap scope
this session was asked to re-measure. Flagged so a future session does not
assume they were checked.

## What this does not close

`io`'s parity gap is real, named, and unstarted — closing it (then deleting
`adas_sim/io/`'s overlapping half) is real work for a future pass, not this
one. `session`'s cross-module duplicate (`adas_sim.session` vs
`viz::session`) is real and unaddressed; resolving it needs its own
initiative since `B4` was never scoped to reach across repos. `WP-16`/`WP-02`
remain unverified beyond `trace_check.py`'s own box counts.

## Files changed

| Repo | Scope |
|---|---|
| `modules/sim` | `misc/MOVEMENT_B_PLAN.md` (`B4` rewritten, top status line, `Order` section, Definition-of-done item 3), this record |

## Re-run commands

```
find modules/sim/src/adas_sim/<item> -name '*.py' -not -path '*__pycache__*' | xargs wc -l
find modules/sim/src/simcore/<item> \( -name '*.cpp' -o -name '*.hpp' \) | xargs wc -l
head -20 modules/sim/src/simcore/io/codecs/mcap.cpp
head -20 modules/viz/cpp/viz/session/session.hpp
cd modules/sim && python docs/v2/py/trace_check.py --status
```

A later campaign is a **new file**, never an edit to this one (`R-REQ-6`).
