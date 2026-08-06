# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D7 `UT-D7-9` system test (`docs/sim_implementation_plan.md`, `OQ-9`/
`NR-SIM-24`): `sim resim --pin-builds` against a real, already-built
`df_sil.dll` and a real recording. Skips with a named reason if either is
absent, same precedent `test_d7_campaign_sizing.py` sets -- `df` is not
required to run this suite (`sim_sil_contract.md` SS8).

The pure logic (`Pipeline.component_build_shas`, `core.manifest.
verify_pinned_builds`) is proven with no DLL at all in `tests/unit/
test_d7_pin_builds.py`; this file proves the real CLI wiring end to end --
in particular that `sim resim --save` now embeds the real, currently-
resolved library's own hash (`cli/resim.py`'s own gap this stage closes:
every resim-produced manifest used to carry `library_sha256=""`)."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

from adas_sim.cli import resim as resim_cli
from adas_sim.core.errors import ContractError
from adas_sim.io.registry import reader_for, writer_for

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


def _one_recording() -> Path:
    recordings = sorted(_RECORDINGS_DIR.rglob("*.mcap"))
    if not recordings:
        pytest.skip(f"{_RECORDINGS_DIR} exists but has no .mcap files")
    return recordings[0]


def _resim_and_save(recording: Path, out_path: Path) -> None:
    argv = [
        str(recording), "--pipeline", str(_PIPELINE_PATH), "--save", str(out_path),
        "--search", str(_DF_SIL_DIR), "--config", str(_DF_SIL_DIR / "config"),
    ]
    assert resim_cli.run(argv) == 0


def _with_tampered_library_sha(path: Path, out_path: Path, *, stage: str, library_sha256: str) -> None:
    """Copies `path` to `out_path` with `stage`'s own `ComponentBuildInfo.
    library_sha256` overwritten -- the same read-everything/rewrite pattern
    `sim convert` (`cli/convert.py`) already uses over the Reader/Writer
    Protocols, with one manifest field mutated in between. Stands in for a
    SECOND, differently-built library without needing two real compiles."""
    reader = reader_for(path)
    try:
        meta = reader.meta()
        topics = reader.topics()
        messages = list(reader.messages())
    finally:
        reader.close()
    new_components = tuple(
        replace(c, library_sha256=library_sha256) if c.name == stage else c for c in meta.components
    )
    new_meta = replace(meta, components=new_components)
    writer = writer_for(out_path)
    writer.open(out_path, new_meta, topics)
    try:
        for topic, log_time_ns, capture_time_ns, payload in messages:
            writer.write(topic, log_time_ns, payload, capture_time_ns=capture_time_ns)
    finally:
        writer.close()


def test_pin_builds_passes_against_the_recording_it_actually_produced(tmp_path):
    """`sim resim --save` now embeds the real, currently-resolved
    `df_sil.dll`'s own hash; resim-ing that SAME recording again with
    `--pin-builds` must pass, because it genuinely is the same library."""
    saved = tmp_path / "baseline.mcap"
    _resim_and_save(_one_recording(), saved)

    argv = [
        str(saved), "--pipeline", str(_PIPELINE_PATH), "--pin-builds",
        "--search", str(_DF_SIL_DIR), "--config", str(_DF_SIL_DIR / "config"),
    ]
    assert resim_cli.run(argv) == 0


def test_pin_builds_refuses_a_recording_pinned_to_a_different_build(tmp_path):
    saved = tmp_path / "baseline.mcap"
    _resim_and_save(_one_recording(), saved)
    tampered = tmp_path / "tampered.mcap"
    stale_sha = "f" * 64
    _with_tampered_library_sha(saved, tampered, stage="df", library_sha256=stale_sha)

    argv = [
        str(tampered), "--pipeline", str(_PIPELINE_PATH), "--pin-builds",
        "--search", str(_DF_SIL_DIR), "--config", str(_DF_SIL_DIR / "config"),
    ]
    with pytest.raises(ContractError) as exc_info:
        resim_cli.run(argv)
    assert stale_sha in str(exc_info.value)
