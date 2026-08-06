# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D7 system test: `ST-D7-7` (`sim_implementation_plan.md`, `NR-SIM-23`)
-- campaign sizing, measured. **The numbers go in this document, whatever
they are** -- this test exists to produce a fact, not to pass, same
"timed, not asserted" discipline `test_b2_session_system.py::test_pass_1_
over_the_largest_existing_recording_is_timed_not_asserted` already sets
for `ST-B2-2`. `core.batch.run_batch` (`S-D7`) over the real recording set
at `modules/df/tests/carla_testruns/`, `-j 1` vs `-j N` for the real
`df_only.yaml` pipeline against a real `df_sil.dll`.

Skips with a named reason if the real recording set or a real `df_sil.dll`
build is absent (partial clone / no MSVC-Conan build here), same
precedent `test_c7_cross_host_resim.py` sets.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from adas_sim.core.batch import run_batch

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_ROOT = MODULES_ROOT / "df"

_DF_SIL_DIR = DF_ROOT / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release"
_PIPELINE_PATH = DF_ROOT / "sim" / "pipelines" / "df_only.yaml"
_RECORDINGS_DIR = DF_ROOT / "tests" / "carla_testruns"

_SKIP_REASON = (
    "needs a real df_sil.dll build here (scripts/build.py df -t sil -p vs2026 -P base) "
    "and modules/df/tests/carla_testruns/ (partial clone may lack it)"
)


@pytest.fixture(autouse=True)
def _require_real_environment():
    if sys.platform != "win32":
        pytest.skip("Windows-only build path (df_sil.dll) -- same as test_c7_cross_host_resim.py")
    if not (_DF_SIL_DIR / "df_sil.dll").is_file():
        pytest.skip(f"{_SKIP_REASON}: df_sil.dll not found at {_DF_SIL_DIR}")
    if not _RECORDINGS_DIR.is_dir():
        pytest.skip(f"{_SKIP_REASON}: {_RECORDINGS_DIR} not found")


def test_st_d7_7_campaign_sizing_over_the_real_recording_set(capsys):
    recordings = sorted(_RECORDINGS_DIR.rglob("*.mcap"))
    if not recordings:
        pytest.skip(f"{_RECORDINGS_DIR} exists but has no .mcap files")

    total_bytes = sum(r.stat().st_size for r in recordings)

    timings: dict[int, float] = {}
    for jobs in (1, len(recordings)):
        start = time.perf_counter()
        results = run_batch(
            recordings, _PIPELINE_PATH, search=(_DF_SIL_DIR,), config=_DF_SIL_DIR / "config", jobs=jobs,
        )
        elapsed_s = time.perf_counter() - start
        timings[jobs] = elapsed_s
        assert all(r.outcome == "ok" for r in results), [r for r in results if r.outcome != "ok"]

    with capsys.disabled():
        print(f"\nST-D7-7: {len(recordings)} recordings, {total_bytes / 1e6:.1f} MB total")
        for jobs, elapsed_s in timings.items():
            print(f"  -j {jobs}: {elapsed_s:.2f}s ({elapsed_s / len(recordings):.3f}s/recording)")
        scaling = timings[1] / timings[len(recordings)]
        print(f"  scaling -j1 -> -j{len(recordings)}: {scaling:.2f}x")
