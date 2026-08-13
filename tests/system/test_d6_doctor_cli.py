# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 `UT-D6-8` system test (`docs/sim_implementation_plan.md`): `sim
doctor` exits non-zero on a broken stem, a bundle mismatch and a missing
codec capability, against a real, already-built `df_sil.dll` and a real
recording. Skips with a named reason if either is absent, same precedent
`test_c1c_component.py`/`test_d7_pin_builds_cli.py` set -- `df` is not
required to run this suite (`sim_sil_contract.md` SS8).

The pure-Python halves (codec table, an unregistered recording extension,
`Pipeline.parse_stages` never raising on a missing library) are proven with
no DLL at all in `tests/unit/test_d6_doctor.py`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from adas_sim.cli import doctor
from adas_sim.io.base import RunManifest
from adas_sim.plugins.registry import writer_for
from adas_sim.config.project import bundle_bytes_for_recording

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_ROOT = MODULES_ROOT / "df"

_DF_SIL_DIR = DF_ROOT / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release"
_DF_SIL_CONFIG = _DF_SIL_DIR / "config"
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


def _one_recording() -> Path:
    recordings = sorted(_RECORDINGS_DIR.rglob("*.mcap"))
    if not recordings:
        pytest.skip(f"{_RECORDINGS_DIR} exists but has no .mcap files")
    return recordings[0]


def test_doctor_reports_a_healthy_pipeline_and_exits_zero():
    exit_code = doctor.run([
        "--pipeline", str(_PIPELINE_PATH), "--search", str(_DF_SIL_DIR), "--config", str(_DF_SIL_CONFIG),
        "--recording", str(_one_recording()),
    ])
    assert exit_code == 0


def test_doctor_reports_the_real_library_resolution_and_bundle_agreement(capsys):
    doctor.run([
        "--pipeline", str(_PIPELINE_PATH), "--search", str(_DF_SIL_DIR), "--config", str(_DF_SIL_CONFIG),
    ])
    out = capsys.readouterr().out
    assert "df_sil.dll" in out
    assert "ok                           True" in out  # the bundle entry: SUT and viewer agree


def test_doctor_exits_non_zero_on_a_broken_stem_naming_the_directories_searched(tmp_path, capsys):
    exit_code = doctor.run(["--pipeline", str(_PIPELINE_PATH), "--search", str(tmp_path)])
    out = capsys.readouterr().out
    assert exit_code != 0
    assert "df_sil" in out
    assert str(tmp_path) in out


def test_doctor_exits_non_zero_on_a_bundle_mismatch_naming_both_hashes(tmp_path, capsys):
    """A `--config` pointed at a real but DIFFERENT bundle than the one
    packed beside the actual library -- the SUT still reports its own real
    `config_bundle_sha256` (adasManifest() resolves module-relatively,
    independent of --config), so the two must disagree."""
    other_bundle = tmp_path / "vehicle"
    other_bundle.mkdir()
    (other_bundle / "ego_params.yaml").write_text(
        "EGO_LENGTH_M: 1.0\nEGO_WIDTH_M: 1.0\nEGO_WHEELBASE_M: 1.0\nEGO_OVERHANG_FRONT_M: 0.1\n",
        encoding="utf-8",
    )
    exit_code = doctor.run([
        "--pipeline", str(_PIPELINE_PATH), "--search", str(_DF_SIL_DIR), "--config", str(tmp_path),
    ])
    out = capsys.readouterr().out
    assert exit_code != 0
    assert "mismatch" in out
    assert "sut_config_bundle_sha256" in out
    assert "viewer_bundle_sha256" in out


def test_doctor_exits_non_zero_on_a_recording_with_no_registered_codec(tmp_path, capsys):
    fake_recording = tmp_path / "not_a_real_format.xyz"
    fake_recording.write_bytes(b"not a recording")
    exit_code = doctor.run(["--recording", str(fake_recording)])
    out = capsys.readouterr().out
    assert exit_code != 0
    assert str(fake_recording) in out


def test_doctor_reports_feasible_cuts_for_the_real_recording():
    """ST-D6-3-adjacent, informational: which stages this recording could
    drive as mode: measured (R-SIM-12/R-SIM-23)."""
    from adas_sim.diagnostics.diagnostics import doctor_report

    report = doctor_report(
        pipeline_path=_PIPELINE_PATH, search=[_DF_SIL_DIR], config_path=_DF_SIL_CONFIG,
        recording_path=_one_recording(),
    )
    assert "feasible_cuts" in report["recording"]
    assert report["recording"]["feasible_cuts"][0]["stage"] == "df"


# UT-C5-8: --config-source forces the bundle-agreement check onto exactly
# one tier, against the real df_sil.dll build (no fixture library can stand
# in -- _bundle_diagnoses only ever loads a real CtypesSilComponent).

def _origin_forced(out: str, origin: str) -> bool:
    return re.search(rf"viewer_bundle_origin\s+{origin}\b", out) is not None


def test_doctor_config_source_library_forces_the_library_tier(capsys):
    # No --config given -- forcing "library" must still resolve, from the
    # config/ packed beside the resolved dll itself, and (being the exact
    # bundle that dll was built with) must agree.
    exit_code = doctor.run([
        "--pipeline", str(_PIPELINE_PATH), "--search", str(_DF_SIL_DIR),
        "--config-source", "library",
    ])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert _origin_forced(out, "library")


def test_doctor_config_source_checkout_forces_the_checkout_tier(capsys):
    # The checkout tier hashes a single shared_config file, never the real
    # packed bundle -- shapes differ, so this is not expected to agree; the
    # point is that "checkout" was the tier actually consulted.
    doctor.run([
        "--pipeline", str(_PIPELINE_PATH), "--search", str(_DF_SIL_DIR),
        "--config-source", "checkout",
    ])
    out = capsys.readouterr().out
    assert _origin_forced(out, "checkout")


def test_doctor_config_source_embedded_resolves_from_the_recordings_own_bundle(tmp_path, capsys):
    # The fixture recordings under carla_testruns predate config-bundle
    # embedding (their config_bundle_bytes() is empty) -- a real, separate
    # gap, not this test's concern. Write a throwaway recording that DOES
    # embed the real library's own bundle, so --config-source embedded has
    # something genuine to force against and must agree exactly (same
    # bytes, both sides).
    recording = tmp_path / "embedded_bundle.mcap"
    writer = writer_for(recording)
    writer.open(recording, RunManifest(manifest_version=2), {}, config_bundle_bytes=bundle_bytes_for_recording(_DF_SIL_CONFIG))
    writer.close()

    exit_code = doctor.run([
        "--pipeline", str(_PIPELINE_PATH), "--search", str(_DF_SIL_DIR),
        "--recording", str(recording), "--config-source", "embedded",
    ])
    out = capsys.readouterr().out
    assert _origin_forced(out, "embedded")
    assert exit_code == 0


def test_doctor_config_source_embedded_without_a_recording_is_a_problem_naming_the_tier(capsys):
    exit_code = doctor.run([
        "--pipeline", str(_PIPELINE_PATH), "--search", str(_DF_SIL_DIR),
        "--config-source", "embedded",
    ])
    out = capsys.readouterr().out
    assert exit_code != 0
    assert "--config-source embedded could not resolve" in out
