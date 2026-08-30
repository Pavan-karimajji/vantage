# SIM — Test Execution Record — 2026-08-29 · `B1` closes: `SM-10`/`SM-05`/`SM-07`/`SM-12`/`SM-08`

**This record is evidence, not a specification.** Exempt from the freeze on
that basis, never edited after the fact. A later campaign is a **new file**.

## Campaign

| | |
|---|---|
| Question | Does the viz sync plan's `B1` (10 boxes) actually close — is the Python scene/render/player implementation genuinely gone, with nothing silently broken? |
| Method | `T` (pytest, both platforms) · `A` (`ANL-SM-02`, `ANL-SM-03`, every `scripts/check_*.py`, `trace_check.py`, `sync_check.py`, `check_cross_module_trace.py`) |
| Platform | `ubuntu_gcc` (WSL sandbox, native python3.10) and native `vs2026` (`.venv/Scripts/python.exe`, WSL2 interop) |
| Committed | Yes — three commits, `modules/viz` `ab07a0d`, `modules/sim` `7d4c626`, superproject `5270fdf`, plus this closing pass |

## Result

**All 43 rows of `modules/viz/docs/VIZ_Sync_Plan_v0.1.md` §2 reached `DONE`.**
`G-0`..`G-7` all `CLOSED`. §2/§3 are deleted per the plan's own §6.6, with two
honest exceptions named below rather than forced.

| Row | What closed |
|---|---|
| `SM-10` | The real finding was `modules/viz`'s own `CLAUDE.md`, not `sim`'s (already correct) — still opened *"this module does not exist yet"* over 112 real files |
| `SM-05` / `SM-07` | No independent work; both closed automatically once `SM-12`'s dual-run window closed |
| `SM-12` | The Python `scene/`/`render/`/`player/shell/` tree deleted; `player/panels/` down to `pipeline_panel.py` (`SI-22`'s own `KEEP`) |
| `SM-08` | `pyproject.toml`'s `viewer` extra dropped, two stale docstrings fixed, `sim-ci.yml`'s three install lines corrected (would have failed outright on the unknown `viewer` extra), `ANL-SM-02` built and wired into `ci_gate.py` |

## The point this record exists to make explicit

**`E2E-VZ-01`'s "`PASS`" no longer means what it used to mean, and this is
deliberate, not a regression.** Before `SM-12`, a `PASS` from
`compare_scene_parity.py` meant *"the live Python implementation and the live
C++ implementation agree, run today, against a real recording."* Two real,
independently executing implementations, compared fresh.

**After `SM-12`, there is no second live implementation to compare against.**
The Python side is deleted. What `compare_scene_parity.py` checks now is the
real, live C++ output against the **committed, frozen NDJSON golden files**
(`modules/sim/tests/fixtures/golden/ndjson/*.py.ndjson`) — a snapshot of what
Python produced on 2026-08-26/27, before it stopped existing. Re-running the
comparator today (confirmed this session) still reports `PASS`, and that
`PASS` is real and worth having: it proves the C++ side has not silently
drifted from the last point the two implementations were shown to agree. **It
does not prove the two implementations still agree, because there is only one
implementation left.** A future change to `viz`'s C++ scene/layer code that
happens to match Python's old (frozen, unreachable) behaviour would still
read `PASS`; a future change that's actually *more correct* than Python's old
behaviour would read `FAIL` against a snapshot that was never re-validated
against anything after 2026-08-27. Anyone citing "`E2E-VZ-01` passes" after
this point should read it as *"matches the frozen pre-deletion snapshot,"*
never as *"two live implementations agree"* — the two-implementation
question stopped being askable the moment `SM-12` ran.

This is exactly what `D-6`'s dual-run window was always going to end in
(`viz_concept.md`, `SM-12`'s own gate: *"the Python scene is deleted and
`ANL-SM-03` proves one implementation remains"*) — named here so the
distinction is on the record rather than discovered by someone assuming more
than the number says.

## Verification

| Check | Result |
|---|---|
| `pytest tests/unit` | 967 passed, 1 skipped, 0 failed |
| `pytest tests/system` | 97 passed, 8 skipped, 1 failed (`test_conan_editable_add_resolves_adas_sim` — pre-existing Conan-remote credentials gap, unrelated) |
| `compare_scene_parity.py`, both phase-1 corpora | `PASS`, 0 divergences (against the frozen goldens named above) |
| `scripts/check_no_graphical_toolkit.py` (`ANL-SM-02`) | clean; `.c1`/`.c2`/`.c3` planted-violation cases all correct |
| `scripts/check_one_layer_implementation.py` (`ANL-SM-03`, superproject root) | `exactly one layer-provider-registration implementation found` |
| Every other `scripts/check_*.py` in `modules/sim` | clean, except `check_engine_boundary.py` (same pre-existing Conan-credentials gap) |
| `modules/sim/docs/v2/py/trace_check.py` | `PASS` |
| `modules/viz/docs/py/sync_check.py` | `PASS` — 43/43 rows `DONE`, all gates `CLOSED`, `next: none` |
| `modules/viz/docs/py/trace_check.py` | `PASS` — 296 requirements, 163 tests |

## Two things closed honestly, not swept in

1. **`modules/viz/docs/py/sync_check.py` is not deleted.** `scripts/next.py`
   (superproject root) hard-imports it with no fallback; deleting the script
   would break `next.py` outright, and `next.py` has not itself been
   rewritten to drop the dependency (§6.4 always said it would need to be —
   *"minus its gate table"*). Left in place, inert. `next.py`'s own
   `CHECKERS` list had the `sync` entry removed instead (a real, immediate
   fix, not a workaround): with §2/§3 gone, `sync_check.py` correctly reports
   `SKIPPED -- scanned 0 rows` with a non-zero exit on every future run,
   which — before this fix — made `next.py` refuse to issue a work order for
   *any* of the three modules, permanently. Verified fixed: `python
   scripts/next.py` now reports `NEXT none — every row in §2 is ticked. Run
   §6.5's definition of done before believing it.`
2. **`scripts/check_cross_module_trace.py` (§6.3's own promoted survivor) is
   not clean.** Run before §2/§3 were deleted, on principle: 60 `BROKEN`
   findings, pre-existing and unrelated to this session's own work. Reading
   the checker's source, this looks like a parser gap, not 60 real dangling
   links — `DEFINE_TABLE_RE` recognizes a numbered-heading table row as
   defining a UID but not the `| SYS-0132 | ... | VIZ:SYS-0061 |`
   disposition-table row shape `R-REQ-2` actually uses for a retired UID, so
   a properly superseded `SI-19`/`20`/`21` UID reads as *"no such UID"*
   rather than as the recorded disposition it is. Not investigated case by
   case, not fixed here — a real, separate finding for whoever owns
   cross-module trace integrity next.

## Files changed (summary; see the three commits for the full list)

| Repo | Commit | Scope |
|---|---|---|
| `modules/viz` | `ab07a0d` | `CLAUDE.md`, `docs/VIZ_Sync_Plan_v0.1.md` (`SM-10`/`SM-05`/`SM-07`/`SM-12` closure), `docs/py/sync_check.py` (`KNOWN_DEAD` additions) |
| `modules/sim` | `7d4c626` | `SM-12`'s deletion (~124 files) and cascading fixes (~34 files), `misc/START_HERE.md` |
| superproject | `5270fdf` | pointer bump, both submodules |
| (this pass) | — | `SM-08` (`pyproject.toml`, two docstrings, `sim-ci.yml`, `scripts/check_no_graphical_toolkit.py`, `ci_gate.py`), §6.6 execution (`VIZ_Sync_Plan_v0.1.md` §2/§3 deletion), `scripts/next.py` (`CHECKERS` fix), this record, `misc/START_HERE.md` (second update) |

## Re-run commands

```
cd modules/sim
python -m pytest tests/unit tests/system -q
python docs/v2/py/trace_check.py
python scripts/check_no_graphical_toolkit.py
cd ../viz
python -m compare_scene_parity  # via sim/compare_scene_parity.py, see its own --help
python docs/py/sync_check.py
python docs/py/trace_check.py
cd ../..
python scripts/check_one_layer_implementation.py
python scripts/check_cross_module_trace.py   # currently 60 BROKEN, see above
python scripts/next.py
```

A later campaign is a **new file**, never an edit to this one (`R-REQ-6`).
