# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""WP-09a: IMP-0040 -- ``tests/support/lab_cases.py`` is tested, not trusted.

Finding a case, one setup edit, one recording edit and the skip, each on a small lab tree built in ``tmp_path``
(no lab build needed), and the finding of the real ``running_example`` ``cut_c`` when the lab is built here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.support import lab_cases

VANTAGE_ROOT = Path(__file__).resolve().parents[2]


def _writer_dir() -> Path:
    """The folder holding ``adas_recording``: the lab build's ``interfaces_python`` if the lab is built here, else the
    ``interfaces`` source tree beside this repo; a skip with the reason when neither exists."""
    for index in sorted((VANTAGE_ROOT.parent / "vantage-lab" / "conan_workarea").glob("build-sil-*/lab/*/index.json")):
        found = json.loads(index.read_text(encoding="utf-8")).get("interfaces_python")
        if found and (Path(found) / "adas_recording" / "writer.py").is_file():
            return Path(found)
    beside = VANTAGE_ROOT.parent / "interfaces" / "src"
    if (beside / "adas_recording" / "writer.py").is_file():
        return beside
    pytest.skip("no adas_recording writer on this machine (no lab build, no interfaces checkout)")


@pytest.fixture
def small_lab(tmp_path, monkeypatch):
    """A lab tree of one topology ``t``, one scenario ``base`` and two resim cases, with a three-message recording
    written through the interfaces writer, one library file and an index.json."""
    writer_dir = _writer_dir()
    root = tmp_path / "lab_root"
    (root / "catalogue").mkdir(parents=True)
    (root / "catalogue" / "t.yaml").write_text(
        "topology: t\nscenarios:\n"
        "  - name: base\n    resim:\n      - {name: cut_a, measured: [A]}\n      - {name: jump, jump_to_ms: 40}\n",
        encoding="utf-8")
    out = root / "lab" / "t"
    out.mkdir(parents=True)
    library = root / "conan_workarea" / "build-sil-vs2026" / "lab" / "t" / "A" / "lab_t_A.dll"
    library.parent.mkdir(parents=True)
    library.write_bytes(b"not a library")
    (library.parent.parent / "index.json").write_text(json.dumps({
        "topology": "t", "interfaces_python": writer_dir.as_posix(),
        "components": {"A": {"library": library.as_posix(), "config": "", "build_id": "x"}}}), encoding="utf-8")
    setup = {"run_id": "t", "outputs": {"path": (out / "base.cut_a.out.mcap").as_posix()}, "stages": [{"name": "A"}]}
    (out / "base.cut_a.run.json").write_text(json.dumps(setup), encoding="utf-8")
    (out / "base.jump.run.json").write_text(json.dumps(setup), encoding="utf-8")

    sys.path.insert(0, str(writer_dir))
    try:
        from adas_recording.writer import McapRecorder, TopicSpec
    finally:
        sys.path.remove(str(writer_dir))
    topics = {"/A/out": TopicSpec("t.Out", b"schema-A", "simulated"), "/source/X": TopicSpec("t.X", b"schema-X", "mocked")}
    manifest = {"source_kind": "synthetic", "run_kind": "sim", "components": [{"name": "A", "build_id": "x"}],
                "record_policies": {"A.out": "full", "source.X": "full"}}
    with McapRecorder(out / "base.mcap", topics, manifest) as writer:
        writer.write("/source/X", 10_000, b"x1")
        writer.write("/A/out", 10_000, b"a1")
        writer.write("/source/X", 20_000, b"x2")
    monkeypatch.setenv("VANTAGE_LAB_ROOT", str(root))
    monkeypatch.delenv("LAB_INDEX", raising=False)
    return root


def test_lab_case_finds_the_setup_the_recording_the_libraries_and_the_catalogue_entry(small_lab):
    case = lab_cases.lab_case("t", "jump")
    assert case.setup == small_lab / "lab" / "t" / "base.jump.run.json"
    assert case.recording == small_lab / "lab" / "t" / "base.mcap"
    assert set(case.libraries) == {"A"} and case.libraries["A"].is_file()
    assert case.case_entry["jump_to_ms"] == 40
    assert case.expect == "exact"
    assert case.interfaces_python is not None


def test_edit_setup_copies_with_one_change_and_leaves_the_labs_file_alone(small_lab, tmp_path):
    case = lab_cases.lab_case("t", "cut_a")
    before = case.setup.read_text(encoding="utf-8")
    edited = lab_cases.edit_setup(case, tmp_path / "work", lambda s: s.update(colour="red"), outputs=tmp_path / "work" / "o.mcap")
    data = json.loads(edited.read_text(encoding="utf-8"))
    assert data["colour"] == "red"
    assert data["outputs"]["path"] == (tmp_path / "work" / "o.mcap").as_posix()
    assert case.setup.read_text(encoding="utf-8") == before
    assert edited.parent == tmp_path / "work"


def test_edit_recording_writes_the_edited_messages_through_the_writer_with_the_originals_provenance(small_lab, tmp_path):
    case = lab_cases.lab_case("t", "cut_a")
    kept = lab_cases.edit_recording(case, tmp_path / "work" / "cut.mcap", lambda messages: [m for m in messages if m[0] != "/A/out"])
    messages, manifest, provenance, schemas = lab_cases.read_recording(kept)
    assert messages == [("/source/X", 10_000_000, b"x1"), ("/source/X", 20_000_000, b"x2")]
    assert manifest["source_kind"] == "synthetic" and manifest["run_kind"] == "sim" and manifest["manifest_version"] == 1
    assert provenance == {"/A/out": "simulated", "/source/X": "mocked"}
    assert schemas["/A/out"] == ("t.Out", b"schema-A")
    original, *_ = lab_cases.read_recording(case.recording)
    assert len(original) == 3  # the lab's recording is untouched


def test_edit_recording_refuses_a_time_that_is_not_a_whole_microsecond(small_lab, tmp_path):
    case = lab_cases.lab_case("t", "cut_a")
    with pytest.raises(ValueError, match="whole number of microseconds"):
        lab_cases.edit_recording(case, tmp_path / "bad.mcap", lambda messages: [(t, ns + 1, p) for t, ns, p in messages])


def test_a_lab_that_is_not_built_skips_with_the_reason_printed(small_lab, capsys):
    (small_lab / "lab" / "t" / "base.mcap").unlink()
    with pytest.raises(pytest.skip.Exception) as skipped:
        lab_cases.lab_case("t", "cut_a")
    assert "lab not built" in str(skipped.value) and "base.mcap" in str(skipped.value)
    assert "lab not built" in capsys.readouterr().err


def test_a_library_of_another_operating_system_skips(small_lab):
    next((small_lab / "conan_workarea").rglob("lab_t_A.dll")).unlink()
    with pytest.raises(pytest.skip.Exception, match="not on this machine"):
        lab_cases.lab_case("t", "cut_a")


def test_the_real_running_example_cut_c_is_found_when_the_lab_is_built_here():
    case = lab_cases.lab_case("running_example", "cut_c")  # skips with the reason when it is not built
    assert case.case_entry["measured"] == ["C"]
    assert set(case.libraries) == {"A", "B", "C", "D", "E"}
