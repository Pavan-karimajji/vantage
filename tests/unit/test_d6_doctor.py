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

from adas_sim.cli import doctor as doctor_cli
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.diagnostics import doctor_report

import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap"/".csv" codecs


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
