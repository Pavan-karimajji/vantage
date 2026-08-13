# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C1c loader tests: UT-C1c-15 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

import pytest

from adas_sim.resolve.library import resolve_library
from adas_sim.diagnostics.errors import EnvironmentError_


@pytest.mark.parametrize(
    ("platform", "filename"),
    [
        ("win32", "df_sil.dll"),
        ("linux", "libdf_sil.so"),
    ],
)
def test_resolve_library_returns_the_right_file_for_the_platform(tmp_path, platform, filename):
    """UT-C1c-15."""
    (tmp_path / filename).write_bytes(b"")

    found = resolve_library("df_sil", search=[tmp_path], platform=platform)

    assert found == tmp_path / filename


def test_resolve_library_on_linux_falls_back_to_the_bare_stem(tmp_path):
    """UT-C1c-15: Linux tries `lib<stem>.so` before the bare `<stem>.so`."""
    (tmp_path / "df_sil.so").write_bytes(b"")

    found = resolve_library("df_sil", search=[tmp_path], platform="linux")

    assert found == tmp_path / "df_sil.so"


def test_resolve_library_on_linux_prefers_lib_prefixed_over_bare(tmp_path):
    """UT-C1c-15."""
    (tmp_path / "libdf_sil.so").write_bytes(b"")
    (tmp_path / "df_sil.so").write_bytes(b"")

    found = resolve_library("df_sil", search=[tmp_path], platform="linux")

    assert found == tmp_path / "libdf_sil.so"


def test_resolve_library_searches_directories_in_order(tmp_path):
    """UT-C1c-15."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (second / "df_sil.dll").write_bytes(b"")

    found = resolve_library("df_sil", search=[first, second], platform="win32")

    assert found == second / "df_sil.dll"


def test_resolve_library_miss_names_every_pattern_and_directory_tried(tmp_path):
    """UT-C1c-15: a miss names every pattern tried and every directory
    searched (N-8), never just an identifier."""
    first = tmp_path / "first"
    second = tmp_path / "second"

    with pytest.raises(EnvironmentError_) as excinfo:
        resolve_library("df_sil", search=[first, second], platform="win32")

    message = str(excinfo.value)
    assert "df_sil.dll" in message
    assert str(first) in message
    assert str(second) in message


def test_resolve_library_with_no_search_directories_names_that_fact(tmp_path):
    """UT-C1c-15: an empty search path is a miss too, not a crash."""
    with pytest.raises(EnvironmentError_) as excinfo:
        resolve_library("df_sil", search=[], platform="win32")

    assert "no directories given" in str(excinfo.value)
