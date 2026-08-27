# SIM — Test Execution Record — 2026-08-27

**The first execution record this module has ever carried.** `R-REQ-6`:
verification status is derived from a campaign, never stored in a specification.
`modules/sim/CLAUDE.md` has said *"not yet created; generate its rows when the
first campaign runs"* since the v2 set was written. This is that campaign.

## Campaign

| | |
|---|---|
| Date | 2026-08-27 16:41 UTC |
| Commit | `005ad18` (`main`, clean except the 2026-08-27 reset edits) |
| Host | Windows 11, native (not WSL) |
| Python | 3.14.6 |
| Command | `python scripts/ci_gate.py --artifact-dir logs/ci_gate/reset_2026-08-27` |
| Artifacts | `logs/ci_gate/reset_2026-08-27/` (junit XML, per-check stdout, scenario JSON) |
| Operator | reset session, Movement A item 3 |

## Result: **FAIL**

```
event=ci_gate_result run=20260827T164134Z-0558270e status=fail mode=full
```

| Gate component | Result |
|---|---|
| pytest | **1499 passed · 12 failed · 12 skipped** (1523 collected, 1498 counted toward floor 692) |
| `check_invariants.py` | clean — `GT-1/2/3/6/11`, `UT-D8-9`, `WP-02(b)`, `ANL-SW-02/03/04/07/08/35/37/38/61` |
| `check_closed_sets.py` | clean |
| `check_no_duplication.py` | clean |
| `check_artifact_kinds.py` | clean |
| `check_headers.py` | **12 violations** |
| `check_time_units.py` | **3 floating-point time members** |
| `check_trace.py` | **155 `R-REQ-9` violations** — a cited test id with no matching test |
| `sim check` | **18 scenarios, 3 failed** (0 known, 3 unexpected) |

## Prior claim this campaign corrects

`WP-01`'s `IMP-0366` box records the suite *"verified green on Windows locally"*
on 2026-08-13. It is not green on 2026-08-27. Nothing observed it in between,
because the CI job could not fire — see the trigger finding below.

## The 12 test failures, by cause

**Group 1 — the check harness has drifted from its own tests (5).**
`scripts/check_closed_sets.py:142` and `:151` raise
`ValueError: too many values to unpack (expected 2)` against the 5-tuple its
tests pass. The check passes on real configuration, so it reports clean while
**its planted-violation tests cannot run** — precisely the *"a check nobody has
seen fail is a check nobody should believe"* case `R-REQ-9` exists to prevent.

- `test_a1_check_closed_sets.py::test_check_closed_sets_fails_on_a_planted_extra_verb`
- `…::test_check_closed_sets_fails_on_a_planted_missing_verb`
- `…::test_check_closed_sets_reports_unimportable_module`
- `…::test_check_closed_sets_fails_on_a_planted_cpp_origin_extra_value`
- `…::test_check_closed_sets_reports_unreadable_cpp_header`

**Group 2 — the tree genuinely violates two checks (3).**
These assert *"passes on the current skeleton"*, and the skeleton no longer does.

- `test_a1_check_headers.py::test_check_python_headers_passes_on_the_current_skeleton`
- `test_a1_check_headers.py::test_check_cpp_headers_passes_on_the_current_skeleton`
- `test_a1_check_time_units.py::test_check_time_units_passes_on_the_current_tree`

Violations are all in `simcore` and in `scripts/check_*.py` — the newest code,
never header-stamped: `check_anl_sw36.py`, `check_coverage_delta.py`,
`check_engine_boundary.py`, `check_no_repeated_field_allocation.py`,
`prove_equal.py`, `simcore/bus/port_bus.cpp`, `simcore/io/codecs/erg_wire.cpp`,
`simcore/scheduler/due.cpp`, `simcore/scheduler/reconcile.cpp`,
`simcore/transport/inproc.cpp`, `simcore/transport/shm.cpp`,
`include/simcore/abi/simcore.h`. Float time members:
`module_host.hpp:80 age_s`, `erg.cpp:605 time_s`, `component.cpp:146 dt_s`.

**Group 3 — tests reference a symbol the refactor removed (2).**
`AttributeError: module 'adas_sim.cli.resim' does not have the attribute
'run_pipeline_via_engine'`. `WP-15b` rewired the live callers onto `simengine`;
these two were not rewired with them.

- `test_d3_run_manifest_cli.py::test_sim_resim_reads_recording_project_config_from_the_manifest_alone`
- `test_d3_run_manifest_cli.py::test_an_explicit_cli_flag_wins_over_the_manifests_own_value`

**Group 4 — environment and golden (2).**

- `test_a1_install.py::test_conan_editable_add_resolves_adas_sim` — Conan
  editable resolution, msvc/195/Release profile.
- `test_b1_replay.py::test_replay_matches_the_golden_for_every_sampled_tick` —
  golden mismatch; needs a diff read before it is called stale or called a bug.

## The 3 scenario failures

All three are a signal that never fired, not a wrong value:

| Scenario | Signal | Expected | Actual |
|---|---|---|---|
| `aeb_canonical_10mps_30m` | `df.aeb.outputs.latent_pre_warning_active` | `2.283 s` | never became `True` |
| `aeb_closing_ego20mps_lead10mps_30m` | `df.aeb.outputs.latent_pre_warning_active` | `2.274 s` | never became `True` |
| `bsd_ego_lane_exit` | `df.bsd.outputs.right.warning` | `1.0 s` | never became `NORMAL` |

## Trigger finding — why no campaign ran between 13 and 27 August

`.github/workflows/sim-ci.yml` triggered on `push: branches: [feat/sim-platform]`.
That branch is **98 commits behind `main` and holds nothing `main` lacks**. The
job was written 2026-08-13 and **could never once have fired**. Corrected in this
session to `main` plus `pull_request` plus `workflow_dispatch`.

This is `WP-01`'s own Exit-gate reasoning — *a green check that scanned nothing is
indistinguishable from a green check that scanned everything* — reappearing one
level up, at the trigger instead of the check.

## Consequence for `WP-01`

`WP-01` **cannot close** on this campaign. `IMP-0366` closes on *a real GitHub
Actions run of `gate-windows` passing*, and the gate does not pass. The 12
failures above are the work between here and that box.

`IMP-0417` remains correctly deferred: it closes on the first `WP` citing a kind
`true` in `conf/artifact_kinds.yaml`, which is `WP-31` scope.

## Next campaign

Re-run the identical command after the four groups are addressed. Same file name
pattern, new date. This record is never edited to show a better result — a later
campaign is a new file (`R-REQ-6`).
