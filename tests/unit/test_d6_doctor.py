# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 `UT-D6-8` unit tests (`docs/sim_implementation_plan.md`): the parts
of `sim doctor`'s completion that need no real `dll:`/`stubdll:` build --
the codec table (always reported), an unregistered/write-only recording
extension, and a broken `impl:` stem reported rather than crashing
`Pipeline.load` itself. The real-library halves (actual resolution, config
bundle agreement, feasible cuts) are `tests/system/test_d6_doctor_cli.py`'s
job, against a real `df_sil.dll`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adas_sim.cli import doctor as doctor_cli
from adas_sim.graph.build import Pipeline
from adas_sim.diagnostics.diagnostics import _plugin_diagnoses, doctor_report

import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap"/".csv" codecs

#: WP-06 (SW-0042): every plugin.yaml fixture here declares these four so
#: identity validation never contaminates a test aimed at a different check.
_IDENTITY = {"description": "test plugin", "version": "1.0", "author": "test", "projects": ["base"]}


def _pipeline_yaml(tmp_path: Path, *, stem: str = "nonexistent_stem") -> Path:
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        f"version: 1\nname: doctor_test\nstages:\n"
        f"  - name: df\n    mode: simulate\n    impl: \"dll:{stem}\"\n    inputs: {{}}\n",
        encoding="utf-8",
    )
    return path


def test_doctor_report_with_no_arguments_still_reports_the_codec_table():
    report = doctor_report()
    assert "codecs" in report
    extensions = {entry["extension"] for entry in report["codecs"]}
    assert {".mcap", ".csv"} <= extensions
    assert report["problems"] == []


def test_doctor_report_flags_an_unregistered_recording_extension(tmp_path):
    fake = tmp_path / "recording.xyz"
    fake.write_bytes(b"")
    report = doctor_report(recording_path=fake)
    assert report["recording"]["ok"] is False
    assert report["problems"]
    assert str(fake) in report["problems"][0]


def test_doctor_report_flags_a_write_only_codec_as_unreadable(tmp_path):
    fake = tmp_path / "export.csv"
    fake.write_text("a,b\n1,2\n", encoding="utf-8")
    report = doctor_report(recording_path=fake)
    assert report["recording"]["ok"] is False
    assert "write-only" in report["recording"]["detail"]


def test_doctor_report_flags_a_broken_impl_stem_without_crashing(tmp_path):
    pipeline_path = _pipeline_yaml(tmp_path)
    report = doctor_report(pipeline_path=pipeline_path, search=[tmp_path])
    assert report["libraries"][0]["ok"] is False
    assert report["libraries"][0]["stem"] == "nonexistent_stem"
    assert "pipeline_load_error" in report
    assert any("nonexistent_stem" in p for p in report["problems"])


def test_pipeline_parse_stages_never_raises_on_a_missing_library(tmp_path):
    """The whole point of splitting parse_stages out of load(): reading
    stage declarations must not require resolving impl: at all."""
    pipeline_path = _pipeline_yaml(tmp_path)
    stages = Pipeline.parse_stages(pipeline_path)
    assert len(stages) == 1
    assert stages[0].name == "df"
    assert stages[0].impl == "dll:nonexistent_stem"


def test_doctor_cli_exits_non_zero_on_a_broken_stem(tmp_path, capsys):
    pipeline_path = _pipeline_yaml(tmp_path)
    exit_code = doctor_cli.run(["--pipeline", str(pipeline_path), "--search", str(tmp_path)])
    out = capsys.readouterr().out
    assert exit_code != 0
    assert "nonexistent_stem" in out


def test_doctor_cli_exits_zero_with_no_flags():
    assert doctor_cli.run([]) == 0


def test_doctor_cli_rejects_an_unknown_config_source():
    with pytest.raises(SystemExit):
        doctor_cli.build_parser().parse_args(["--config-source", "nonsense"])


# ---------------------------------------------------------------------------
# S-C8's own remaining item: sim doctor reports each stage's plug-in bundle.
# `_plugin_diagnoses` takes an already-built `library_diagnoses` list
# directly (the same shape `_library_diagnoses` returns) rather than going
# through `doctor_report()`'s own library RESOLUTION -- that half needs a
# real dll:/stubdll: build (test_d6_doctor_cli.py's job); this is the pure
# logic underneath it, same split test_c5_overrides.py already used for
# resolve_swept_config.
# ---------------------------------------------------------------------------


def _library_entry(tmp_path: Path, *, stage: str = "df") -> dict[str, object]:
    lib_dir = tmp_path / stage
    lib_dir.mkdir(parents=True, exist_ok=True)
    return {"stage": stage, "ok": True, "resolved": str(lib_dir / f"{stage}_sil.dll")}


def test_plugin_diagnoses_reports_a_resolved_library_tier_bundle(tmp_path):
    entry = _library_entry(tmp_path)
    plugin_dir = tmp_path / "df" / "sim"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yaml").write_text(
        yaml.safe_dump({"api": 1, "component": "df", "provides": [], "sha256": "abc123", **_IDENTITY}),
        encoding="utf-8",
    )

    results = _plugin_diagnoses([entry])

    assert results == [{
        "stage": "df", "found": True, "component": "df", "api": 1,
        "sha256": "abc123", "origin": "library", "root": str(plugin_dir),
    }]


def test_plugin_diagnoses_reports_found_false_for_a_component_with_no_sim_plugins(tmp_path):
    entry = _library_entry(tmp_path, stage="vdy")  # no sim/plugin.yaml ever written under it

    results = _plugin_diagnoses([entry])

    assert len(results) == 1
    assert results[0]["stage"] == "vdy"
    assert results[0]["found"] is False
    assert "no plugin.yaml" in results[0]["detail"]


def test_plugin_diagnoses_skips_a_stage_whose_library_never_resolved(tmp_path):
    broken_entry = {"stage": "df", "ok": False, "resolved": ""}
    assert _plugin_diagnoses([broken_entry]) == []


def test_plugin_diagnoses_explicit_plugin_root_wins_over_the_library_tier(tmp_path):
    entry = _library_entry(tmp_path)
    library_plugin_dir = tmp_path / "df" / "sim"
    library_plugin_dir.mkdir(parents=True)
    (library_plugin_dir / "plugin.yaml").write_text(
        yaml.safe_dump({"api": 1, "component": "df", "provides": [], **_IDENTITY}), encoding="utf-8",
    )
    explicit_dir = tmp_path / "explicit_override"
    explicit_dir.mkdir()
    (explicit_dir / "plugin.yaml").write_text(
        yaml.safe_dump({"api": 1, "component": "df-explicit", "provides": [], **_IDENTITY}), encoding="utf-8",
    )

    results = _plugin_diagnoses([entry], plugin_root=explicit_dir)

    assert results[0]["origin"] == "explicit"
    assert results[0]["component"] == "df-explicit"
