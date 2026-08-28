# SIM — Test Execution Record — 2026-08-28 · `F-8`, and the demo's fifth clause

**Fourth campaign of 2026-08-28**, after `…_2026-08-28.md` (step-zero fixes),
`…_wp28.md` (`F-7`) and `…_wp35.md` (the demo, four clauses of five).

**A new file, not an edit to `…_wp35.md`.** That record says `F-8` was found
and not fixed, which was true of that run; rewriting it to look better than
the run was is precisely what `R-REQ-6`'s one-artifact-per-campaign rule
exists to prevent.

**This record is evidence, not a specification.** Exempt from the freeze on
that basis, never edited after the fact.

## Campaign

| | |
|---|---|
| Question | Does the demo's fifth clause — *"see which signal, tick, file **and build** produced it"* — now answer? |
| Method | `T` (2 new unit cases + `UT-D3-8`'s field-by-field GUI/CLI comparison) · `D` (the demo re-run, both directions, screenshotted) |
| Platform | `vs2026`, native, via WSL2 interop |
| Evidence | `modules/sim/logs/_wp35/` (screenshots `05`/`06`), `logs/ci_gate/2026-08-28-f8/` |
| Committed | **No.** Working tree only. |

## Result

**`F-8` is fixed, `WP-35`'s Exit box is `[x]`, and all five §1 clauses now
hold.** `trace_check` reports 18 packages closed, up from 17.

| §1 clause | |
|---|---|
| Open the launcher | ✅ |
| Pick a recording the system itself produced | ✅ |
| df → MEASURED, picture from the file | ✅ screenshot `05` |
| df → SIMULATED, computed live by the real DLL | ✅ screenshot `06` |
| The two pictures agree | ✅ watched — same 9 prims, same layer tree, tick 100 |
| Click an object → signal, tick, file **and build** | ✅ **now answered** |

---

## `F-8` · the fix, and what it deliberately does not do

`_component_provenance` returned `(config_bundle_sha256, build_id)` and
`build_id` is empty on every recording this framework writes — nothing sets one
today. `library_sha256` is populated and is the real answer to *"which build
produced this"*, but it is **a different fact under a different name**.

**The obvious fix was the wrong one.** Returning `library_sha256` where
`build_id` was asked for would have made one label mean two things — the
library file on most recordings, a genuine build id on the rest — which is the
plausible-looking default `R-SIM-25`/`NR-SIM-4` exist to forbid, on the one
surface whose entire purpose is being believed.

So both are carried, each under its own name:

```
component_build_id       unknown
component_library_sha256 b3524ca8726bf29eecf2b7c8a4ada4fa5342a9a987bb98e1e2c1ff14f49994a6
```

`component_build_id` still reads `unknown` — **correctly**: no build id was
recorded. The question is answered, and the answer says what it is.

**Both surfaces, one producer** (`GT-9`): the field is added to
`EVIDENCE_FIELDS`, which `format_evidence` renders and which *both*
`cli/explain.py --at` and the GUI `EvidencePanel` consume. Neither re-derives
it, so they cannot disagree by accident — and `UT-D3-8` asserts that field by
field, not merely "both non-empty".

### A second defect, found by that same test

Adding the field broke `UT-D3-8` immediately: `cli/explain.py` printed with a
hardcoded `{field:<20}` and the test parsed with a hardcoded `line[:20]` — two
copies of one number. `component_library_sha256` is 24 characters, so the CLI's
own output split in the wrong place and the two surfaces *appeared* to disagree
when they did not. Fixed by deriving the width once
(`EVIDENCE_LABEL_WIDTH = max(len(f) for f in EVIDENCE_FIELDS) + 1`) and having
both the CLI and the test read it, so a longer field name can never silently
misalign them again. **The GT-9 test earned its keep here** — a literal-vs-
literal drift is exactly what it exists to catch, and it caught it.

### Seen to fail

The substitution guard was planted and confirmed: with
`component.build_id or component.library_sha256` restored as a fallback,
`test_a_library_hash_is_never_reported_as_a_build_id` fails
(`'lib-sha-42' = …component_build_id`) and the other six pass. The mirrored
case (`test_a_missing_library_hash_reads_unknown_rather_than_borrowing_the_build_id`)
covers the substitution in the other direction, so neither is only accidentally
absent.

## Verification

| Check | Before `F-8` | After | Verdict |
|---|---|---|---|
| `pytest` (collected) | 1535 | **1537** | +2 |
| `pytest` failures | 1 (parked Conan) | **1** (same) | no regression |
| `UT-D3-8` GUI ≡ CLI, field by field | pass | **pass** | `GT-9` holds |
| `check_invariants.py` | clean | clean | pass |
| `check_headers` / `closed_sets` / `no_duplication` / `artifact_kinds` / `time_units` | clean | clean | pass |
| `sim check` | 18 scenarios, 0 failed | 18, 0 failed | pass |
| `check_trace.py` | 155 `R-REQ-9` | **155** | unchanged — parked |
| `trace_check.py` | PASS | **PASS** · 18 packages closed | `WP-35` closed |
| `ci_gate.py` | `status=fail` | **`status=fail`** | same two parked inputs |

`ci_gate_config.yaml` untouched. No floor moved, no tolerance widened, nothing
skipped or deleted to reach any of the above. **The gate still exits 1**, on
the 155 parked `R-REQ-9` citations and the parked Conan editable test — neither
touched by this work, and whether to tolerate them is not this campaign's call.

## What is still not true

Stated so the demo is not over-claimed:

- **`config_bundle_sha256` reads `unknown`.** The manifest's
  `ComponentBuildInfo.config_bundle_sha256` is empty on these recordings — the
  same shape as `build_id`, one layer earlier. §1 does not ask for it, so it is
  named here rather than fixed.
- **"The two pictures agree" remains watched, not asserted.**
  `vantage_app.exe` has no snapshot flag. The port values behind the claim are
  asserted byte-identical (the step-zero campaign).
- **The launcher fields were set programmatically**, not by mouse — this
  session cannot drive a pointer. Everything downstream is the real thing.
- **`F-6` and `WP-12`'s ingest map are untouched**, and
  `bsd_curve_r172_passby`'s green `sim check` is still a false green.

## Files changed

| File | Why |
|---|---|
| `src/adas_sim/diagnostics/evidence.py` | `component_library_sha256`; `_component_provenance` returns three; `EVIDENCE_LABEL_WIDTH` |
| `src/adas_sim/cli/explain.py` | prints at the derived width, not a literal |
| `tests/unit/test_d6_evidence_prim_join.py` | 2 new cases — the substitution guard, both directions |
| `tests/system/test_d3_evidence_panel_widget.py` | parses at the derived width |
| `docs/v2/SIM_Implementation_Plan_v0.1.md` | `WP-35` Exit `[~]` → `[x]` |

## Re-run commands

```
cd modules/sim
python -m pytest tests/unit/test_d6_evidence_prim_join.py tests/system/test_d3_evidence_panel_widget.py -q
sim explain df.aeb.outputs --session logs/_step0/v_self.mcap --at 46
python scripts/ci_gate.py --artifact-dir logs/ci_gate/<name>
```

A later campaign is a **new file**, never an edit to this one (`R-REQ-6`).
