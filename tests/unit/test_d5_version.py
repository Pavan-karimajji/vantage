# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D5 unit test: `UT-D5-2` (`sim_implementation_plan.md`) -- `--version`
reports every one of the four compatibility fields the checklist names.
`app/version.py` reads its numbers from the SAME constants every real
compatibility refusal already enforces (see its own docstring), so this
test is that they are surfaced, not that they are correct -- correctness
is `UT-C1c-1`/`test_a3_codec.py`/`test_c1c_pipeline.py`'s own job.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError

from adas_sim.player.shell import version as version_mod
from adas_sim.player.shell.version import format_version_text, version_info
from adas_sim.resolve.component import ADAS_SIL_ABI_VERSION
from adas_sim.graph.build import CURRENT_PIPELINE_VERSION
from adas_sim.io.base import CAPTURE_TIME_MANIFEST_VERSION
from adas_sim.scene.codec import SUPPORTED_MAJOR as SCENE_MAJOR_VERSION


def test_version_info_reports_every_named_compatibility_field():
    info = version_info()
    assert info["abi_version"] == str(ADAS_SIL_ABI_VERSION)
    assert info["scene_major"] == str(SCENE_MAJOR_VERSION)
    assert info["recording_manifest_version"] == str(CAPTURE_TIME_MANIFEST_VERSION)
    assert info["pipeline_version"] == str(CURRENT_PIPELINE_VERSION)
    assert info["vantage"]  # non-empty -- the player's own version


def test_format_version_text_includes_every_field_value():
    text = format_version_text()
    for value in version_info().values():
        assert value in text


def test_missing_package_metadata_degrades_to_unknown_never_crashes(monkeypatch):
    """A frozen build missing `--copy-metadata adas-sim` (a real gap found
    running `scripts/freeze.py` for the first time) must still print a
    usable `--version`, not crash reporting its own name."""
    def _raise(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(version_mod, "_package_version", _raise)
    assert version_info()["vantage"] == "unknown"
