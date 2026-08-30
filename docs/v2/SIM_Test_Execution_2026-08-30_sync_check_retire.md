# SIM — Test Execution Record — 2026-08-30 · `sync_check.py` retired, cross-module trace triaged

**This record is evidence, not a specification.** Exempt from the freeze on
that basis, never edited after the fact. A later campaign is a **new file**.

## Campaign

| | |
|---|---|
| Question | Close the two honest exceptions `SIM_Test_Execution_2026-08-29_b1_close.md` named: is `scripts/next.py`'s hard import of `sync_check.py` gone, and are `scripts/check_cross_module_trace.py`'s 60 `BROKEN` findings a parser gap or real dangling links? |
| Method | `A` (both scripts run directly, before and after each fix; every module's own `trace_check.py`) |
| Platform | native Windows (`vs2026`, this session's shell) |
| Committed | Not yet — this record is written before the commit it describes, per the user's ask to review first |

## Result

**Both exceptions closed.**

### 1. `scripts/next.py` rewritten, `sync_check.py` deleted

`next.py` was a cross-repo work-order dispatcher reading
`VIZ_Sync_Plan_v0.1.md`'s §2 (43 rows) and §3 (8 gates) via a hard
`import sync_check as sc`. Those sections were deleted 2026-08-29
(`B1` close, `SM-08`), which is exactly the condition the sync plan's own
§6.6 named as the trigger for rewriting `next.py` to *"minus its gate
table."* Done: `next.py` now runs each of the three modules' own
`trace_check.py` (sim, df, viz) and reports pass/fail plus what each says is
next — sim via its own `--status` resume pointer, df/viz (which have no
`--status` flag) via the plan's own idiom, the lowest-numbered unticked box.
No import of `sync_check` anywhere in the file. `modules/viz/docs/py/
sync_check.py` is deleted; its own planted-violation test
(`test_sync_check.py`) was already deleted 2026-08-29 for the same reason
(its cases mutated §2/§3 content that no longer exists).

Verified:
```
$ python scripts/next.py
  sim   PASS -- next: WP-17
  df    PASS -- next: Test: `INSP-11` (print-theme legibility) reviewed — **not cl...
  viz   PASS -- next: none -- every box ticked
```
All three modules' own `trace_check.py` still close `CN -> SYS -> SW -> IMP
-> WP -> test` (the plain, no-args run each PASS is gated on).

### 2. `check_cross_module_trace.py`'s findings triaged: 56 parser gap, 3 real

| Class | Count | Verdict |
|---|---:|---|
| `SIM:SW-*` / `SIM:SYS-*` cited from viz's docs | 56 | **Parser gap.** Every one is a real, defined, retired UID in one of sim's `R-REQ-2` disposition tables (`SM-01`/`SM-04`). `defined_uids()` recognized two definition shapes (df's prose-anchored `**\`UID\`**`, sim's numbered-heading table `\| 4.1.14 \| UID \|`) but not the third sim actually uses for a disposition row: `\| \`UID\` \| Was \| Replaced by \|` — the UID backtick-wrapped in the row's own first column. That is also the exact shape of sim's Implementation Design tracker (`\| \`IMP-nnnn\` \| \`SW-nnnn\` \| \`WP-nn\` \| ... \|`), which is why sim showed **0** defined `IMP` UIDs before this fix (`--defined` now reports 376). |
| `VIZ:IMP-0036` / `-0064` / `-0065` cited from `df_viz_Implementation_Design_v0.1.md` | 3 | **Real, not fixed.** df's design doc defines its *own* `IMP-0036`/`0064`/`0065` (df-side retired items, df's own numbering) and separately assumes a "VIZ-side equivalent" carries the identical number — it never did. None of the three numbers appears anywhere in `modules/viz/docs`, prose or table. Left for whoever owns df's design doc next; not investigated further, per instruction. |

Fix: added `DEFINE_BACKTICK_TABLE_RE` (`\| \`UID\` \|` anchored) as a third
recognized definition shape in `defined_uids()`, alongside the existing two.

Verified:
```
$ python scripts/check_cross_module_trace.py
check_cross_module_trace: FAIL -- 3 finding(s):
  BROKEN  VIZ:IMP-0036 cited by ... -- no such UID in modules\viz\docs
  BROKEN  VIZ:IMP-0064 cited by ... -- no such UID in modules\viz\docs
  BROKEN  VIZ:IMP-0065 cited by ... -- no such UID in modules\viz\docs
  scanned: 3/13 modules with a document set, 2163 UIDs defined, ...
```
(2163 UIDs defined, up from 1715 before the fix — the 448 newly-recognized
disposition/tracker rows across sim's document set.)

**Scope confirmed, not a bug:** the check covers 3/13 modules by design (its
own docstring) — only `sim`, `df` and `viz` have a real V-model document set
(`CN`/`SYS`/`SW`/`IMP` layered docs). Verified: none of the other ten
submodules (`interfaces`, `isp`, `perception-lane`, `planning`,
`platform-services`, `sil_host`, `shared_config`, `mathlib`, plus
`perception-core`/`vdy`, which have some docs but not the V-model set) has
one.

## What this does not close

`VIZ_Sync_Plan_v0.1.md` §6.5's item 3 (both root tools — `next.py` and
`check_cross_module_trace.py` — wired into CI, each with a planted-violation
test) is unaffected by this pass and remains the named, separate gap it
already was. Neither script has a planted-violation test; neither is invoked
by any CI workflow (there is still no superproject-root `.github/workflows/`).
The 3 real `VIZ:IMP-*` dangling links above are also not fixed, per
instruction.

## Files changed

| Repo | Scope |
|---|---|
| superproject | `scripts/next.py` (rewritten, gate table removed), `scripts/check_cross_module_trace.py` (`DEFINE_BACKTICK_TABLE_RE` added) |
| `modules/viz` | `docs/py/sync_check.py` deleted; `docs/VIZ_Sync_Plan_v0.1.md` (§2 and §6.6 closure notes updated to record both exceptions closed) |
| `modules/sim` | this record; `misc/MOVEMENT_B_PLAN.md` (`B1` exit note updated); `misc/START_HERE.md` |

## Re-run commands

```
python scripts/next.py
python scripts/check_cross_module_trace.py
cd modules/sim && python docs/v2/py/trace_check.py --status
cd ../df && python docs/viz/py/trace_check.py
cd ../viz && python docs/py/trace_check.py
```

A later campaign is a **new file**, never an edit to this one (`R-REQ-6`).
