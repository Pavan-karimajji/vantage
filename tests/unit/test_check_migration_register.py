# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`check_migration_register.py` is tested, not trusted: one planted violation
per check, each built in a temporary directory (R-REQ-9)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import check_migration_register as cmr  # noqa: E402

SW = "4.2 Software"
CS = "4.1 Concept and system"


def _findings(tmp_path, rows=None, code=None, require_placed=False):
    """Write a register into tmp_path, parse it back, run every check."""
    root = tmp_path / "vantage"
    cmr.make_tree(root)
    ctx = cmr.make_context(root)
    text = cmr.render_register(
        rows if rows is not None else {k: list(v) for k, v in cmr.BASE_ROWS.items()},
        code if code is not None else list(cmr.BASE_CODE),
    )
    path = tmp_path / "register.md"
    path.write_text(text, encoding="utf-8")
    reg = cmr.parse_register(path.read_text(encoding="utf-8"))
    findings, _ = cmr.run_checks(ctx, reg, require_placed)
    return findings


def _rows():
    return {k: list(v) for k, v in cmr.BASE_ROWS.items()}


def _ids(findings, check):
    return [f for f in findings if f.startswith(check + " ")]


def test_selftest_catches_every_planted_violation():
    assert cmr.selftest() == []


def test_baseline_register_has_no_finding(tmp_path):
    assert _findings(tmp_path) == []


def test_c_missing_a_universe_row_not_listed(tmp_path):
    rows = _rows()
    rows[CS].pop(1)
    assert _ids(_findings(tmp_path, rows), "C-MISSING") == [
        "C-MISSING SIM:CN-0002: no disposition"
    ]


def test_c_duplicate_a_row_listed_twice(tmp_path):
    rows = _rows()
    rows[CS].append(("SIM:CN-0001", "carried", "VNT", "again"))
    assert len(_ids(_findings(tmp_path, rows), "C-DUPLICATE")) == 1


def test_c_unknown_a_uid_not_in_the_universe(tmp_path):
    rows = _rows()
    rows[CS].append(("SIM:CN-9999", "carried", "VNT", "x"))
    assert len(_ids(_findings(tmp_path, rows), "C-UNKNOWN")) == 1


def test_c_unknown_a_row_listed_outside_its_section_scope(tmp_path):
    rows = _rows()
    rows[SW].append(rows[CS].pop(0))
    found = _findings(tmp_path, rows)
    assert any(f.startswith("C-UNKNOWN SIM:CN-0001") and "outside" in f for f in found)


def test_c_word_a_word_outside_the_closed_list(tmp_path):
    rows = _rows()
    rows[CS][0] = ("SIM:CN-0001", "kept", "VNT", "x")
    assert len(_ids(_findings(tmp_path, rows), "C-WORD")) == 1


def test_c_word_a_code_word_outside_the_closed_list(tmp_path):
    code = list(cmr.BASE_CODE)
    code[-1] = ("scripts/a.py", "carried", "—", "x")
    assert any(f.startswith("C-WORD scripts/a.py") for f in _findings(tmp_path, code=code))


def test_c_target_a_contract_row_that_does_not_exist(tmp_path):
    rows = _rows()
    rows[CS][1] = ("SIM:CN-0002", "moved", "RCT:SYS-9999", "x")
    assert len(_ids(_findings(tmp_path, rows), "C-TARGET")) == 1


def test_c_target_a_decision_that_does_not_exist(tmp_path):
    rows = _rows()
    rows[CS][2] = ("SIM:SYS-0001", "superseded", "D99", "x")
    assert len(_ids(_findings(tmp_path, rows), "C-TARGET")) == 1


def test_c_target_an_architecture_section_that_does_not_exist(tmp_path):
    rows = _rows()
    rows[CS][2] = ("SIM:SYS-0001", "superseded", "ARCH §99", "x")
    assert len(_ids(_findings(tmp_path, rows), "C-TARGET")) == 1


def test_c_target_a_code_row_citing_no_architecture_section(tmp_path):
    code = list(cmr.BASE_CODE)
    code[0] = ("src/simcore/", "reused", "Runner", "x")
    assert any(f.startswith("C-TARGET src/simcore/") for f in _findings(tmp_path, code=code))


def test_c_target_a_replaced_row_naming_a_file_the_architecture_lacks(tmp_path):
    code = list(cmr.BASE_CODE)
    code[4] = ("include/simcore/h.hpp", "replaced", "`include/vantage/other.h`, ARCH §11", "x")
    assert any(f.startswith("C-TARGET include/simcore/h.hpp") for f in _findings(tmp_path, code=code))


def test_c_why_a_retired_row_with_an_empty_why(tmp_path):
    rows = _rows()
    rows[CS][2] = ("SIM:SYS-0001", "retired", "—", "")
    assert len(_ids(_findings(tmp_path, rows), "C-WHY")) == 1


def test_c_why_a_retired_code_row_with_an_empty_why(tmp_path):
    code = list(cmr.BASE_CODE)
    code[-1] = ("scripts/a.py", "retired", "—", "")
    assert any(f.startswith("C-WHY scripts/a.py") for f in _findings(tmp_path, code=code))


def test_c_inherit_an_imp_whose_sw_rows_disagree_and_is_not_listed(tmp_path):
    rows = _rows()
    rows[SW][1] = ("SIM:SW-0002", "retired", "—", "gone")
    assert len(_ids(_findings(tmp_path, rows), "C-INHERIT")) == 1


def test_an_imp_whose_sw_rows_agree_inherits_and_is_not_missing(tmp_path):
    found = _findings(tmp_path)
    assert _ids(found, "C-MISSING") == [] and _ids(found, "C-INHERIT") == []


def test_c_redundant_an_imp_listed_though_its_sw_rows_agree(tmp_path):
    rows = _rows()
    rows[SW].append(("SIM:IMP-0001", "carried", "VNT", "x"))
    assert len(_ids(_findings(tmp_path, rows), "C-REDUNDANT")) == 1


def test_c_code_an_entry_not_covered(tmp_path):
    code = list(cmr.BASE_CODE)
    code.pop()
    assert _ids(_findings(tmp_path, code=code), "C-CODE") == [
        "C-CODE scripts/a.py: not covered by any row"
    ]


def test_c_code_a_path_covered_twice(tmp_path):
    code = list(cmr.BASE_CODE) + [("scripts/a.py", "retired", "—", "again")]
    assert any("listed twice" in f for f in _ids(_findings(tmp_path, code=code), "C-CODE"))


def test_c_code_a_row_naming_a_path_that_does_not_exist(tmp_path):
    code = list(cmr.BASE_CODE) + [("scripts/none.py", "retired", "—", "x")]
    assert any("no such path" in f for f in _ids(_findings(tmp_path, code=code), "C-CODE"))


def test_a_directory_row_covers_its_children_and_a_deeper_row_overrides(tmp_path):
    entries = cmr.list_code_entries(cmr.SELF_SEED)
    assert "src/simcore/bus/" in entries and "scripts/a.py" in entries
    assert not any("pycache" in e or "deep" in e or "sub" in e for e in entries)
    assert _findings(tmp_path) == []


def test_a_directory_with_no_row_is_covered_when_every_file_under_it_has_a_row(tmp_path):
    code = list(cmr.BASE_CODE)
    assert ("src/simengine/pkg/a.py", "reused", "Runner, ARCH §3.3", "kept") in code
    assert ("src/simengine/pkg/b.py", "reused", "Runner, ARCH §3.3", "kept") in code
    assert not any(r[0] == "src/simengine/pkg/" for r in code)
    assert "src/simengine/pkg/" in cmr.list_code_entries(cmr.SELF_SEED)
    assert _ids(_findings(tmp_path, code=code), "C-CODE") == []


def test_c_code_a_directory_with_no_row_names_each_file_under_it_without_one(tmp_path):
    code = [r for r in cmr.BASE_CODE if r[0] != "src/simengine/pkg/b.py"]
    assert _ids(_findings(tmp_path, code=code), "C-CODE") == [
        "C-CODE src/simengine/pkg/b.py: not covered by any row"
    ]


def test_c_seed_the_seed_tag_is_missing(tmp_path):
    root = tmp_path / "vantage"
    cmr.make_tree(root)
    ctx = cmr.make_context(root)
    ctx.code_entries = None
    text = cmr.render_register(_rows(), list(cmr.BASE_CODE))
    found, _ = cmr.run_checks(ctx, cmr.parse_register(text))
    assert _ids(found, "C-SEED") == ["C-SEED seed-from-sim: tag not found"]


def test_a_row_may_name_a_retired_path_that_existed_at_the_seed(tmp_path):
    code = list(cmr.BASE_CODE) + [("src/simcore/bus/x.cpp", "retired", "—", "gone")]
    assert _findings(tmp_path, code=code) == []


def test_universe_excludes_a_row_a_document_lists_as_retired(tmp_path):
    root = tmp_path
    for name, (directory, docs) in cmr.SETS.items():
        (root / directory).mkdir(parents=True, exist_ok=True)
        for kind, filename, form in docs:
            if form == "concept":
                body = "| 1.1 | CN-0001 | live |\n| CN-0002 | was | retired |\n"
            elif form == "block":
                body = f"**`{kind}-0001`** · `P0` — live\n\n| `{kind}-0002` | was | moved |\n"
            else:
                body = (
                    "| `[x]` | `IMP-0001` | `SW-0001` | `WP-01` | `NEW` | file | t |\n"
                    if name == "PARITY"
                    else "| `IMP-0001` | `SW-0001` | `WP-01` | `NEW` | file | t |\n"
                )
            (root / directory / filename).write_text(body, encoding="utf-8")
    universe, serves = cmr.load_set(root, "SIM")
    assert "SIM:CN-0001" in universe and "SIM:CN-0002" not in universe
    assert "SIM:SYS-0002" not in universe and "SIM:SW-0002" not in universe
    assert serves["SIM:IMP-0001"] == ["SIM:SW-0001"]
    universe, serves = cmr.load_set(root, "PARITY")
    assert universe["PARITY:IMP-0001"] == "IMP" and serves["PARITY:IMP-0001"] == ["PARITY:SW-0001"]


# --------------------------------------------------------------- placement --

def _place(target, word="carried"):
    rows = _rows()
    rows[CS][0] = ("SIM:CN-0001", word, target, "x")
    return rows


def test_a_placement_on_a_vantage_sys_row_that_exists_passes(tmp_path):
    found = _findings(tmp_path, _place("VNT:SYS-0001"), require_placed=True)
    assert not any(f.startswith("C-PLACE SIM:CN-0001") for f in found)
    assert _findings(tmp_path, _place("VNT:SYS-0001")) == []


def test_c_place_a_placement_on_a_row_the_vantage_set_lacks(tmp_path):
    found = _findings(tmp_path, _place("VNT:SYS-9999"))
    assert _ids(found, "C-PLACE") == [
        "C-PLACE SIM:CN-0001: VNT:SYS-9999 does not exist in the Vantage set"
    ]


def test_c_place_every_placement_fails_while_the_vantage_set_does_not_exist(tmp_path):
    root = tmp_path / "vantage"
    cmr.make_tree(root)
    ctx = cmr.make_context(root)
    ctx.vnt_uids = set()
    text = cmr.render_register(_place("VNT:SYS-0001"), list(cmr.BASE_CODE))
    found, _ = cmr.run_checks(ctx, cmr.parse_register(text))
    assert len(_ids(found, "C-PLACE")) == 1


def test_c_place_only_a_sys_row_is_a_placement(tmp_path):
    found = _findings(tmp_path, _place("VNT:IMP-0001"))
    assert any("only VNT:SYS-nnnn" in f for f in _ids(found, "C-PLACE"))


def test_a_placement_on_a_row_the_set_lacks_in_a_list_is_found(tmp_path):
    found = _findings(tmp_path, _place("VNT:SYS-0001, VNT:SYS-9999"))
    assert len(_ids(found, "C-PLACE")) == 1


def test_a_bare_vnt_passes_without_the_flag_and_fails_with_it(tmp_path):
    assert _ids(_findings(tmp_path), "C-PLACE") == []
    found = _ids(_findings(tmp_path, require_placed=True), "C-PLACE")
    assert len(found) == 3 and found[0].startswith("C-PLACE SIM:CN-0001:")


def test_a_bare_vnt_in_a_section_row_fails_once_with_the_flag(tmp_path):
    rows = _rows()
    rows[SW] = [("SIM:SW-0001..0002", "carried", "VNT", "§1 — kept")]
    found = _findings(tmp_path, rows, require_placed=True)
    assert [f for f in found if f.startswith("C-PLACE SIM:SW-0001..0002:")] != []
    assert not any(f.startswith("C-PLACE SIM:SW-0001:") for f in found)


def test_a_row_that_is_not_carried_is_not_a_placement_matter(tmp_path):
    rows = _rows()
    rows[CS][0] = ("SIM:CN-0001", "superseded", "D13", "x")
    found = _ids(_findings(tmp_path, rows, require_placed=True), "C-PLACE")
    assert len(found) == 2 and not any("CN-0001" in f for f in found)


def test_the_summary_counts_placed_and_bare_carried_rows_by_section(tmp_path):
    root = tmp_path / "vantage"
    cmr.make_tree(root)
    ctx = cmr.make_context(root)
    text = cmr.render_register(_place("VNT:SYS-0001"), list(cmr.BASE_CODE))
    _, summary = cmr.run_checks(ctx, cmr.parse_register(text))
    assert summary[-1] == (
        "placement: carried 3, placed 1, still bare VNT 2 (4.2 Software: 2)"
    )


def test_load_vnt_reads_the_sys_document_that_layers_yaml_names(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    assert cmr.load_vnt(tmp_path) == set()
    (docs / "layers.yaml").write_text(
        "layers:\n  - id: SYS\n    name: System\n    doc: V_SYS.md\n  - id: IMP\n    doc: V_IMP.md\n",
        encoding="utf-8",
    )
    assert cmr.load_vnt(tmp_path) == set()
    (docs / "V_SYS.md").write_text("**`SYS-0001`** · P0 — a\n**`SYS-0002`** · P0 — b\n", encoding="utf-8")
    (docs / "V_IMP.md").write_text("**`SYS-0009`** · P0 — not read\n", encoding="utf-8")
    assert cmr.load_vnt(tmp_path) == {"VNT:SYS-0001", "VNT:SYS-0002"}


# ------------------------------------------------------------ section rows --

def _section_ctx(tmp_path):
    """Two sections of SYS; section 5 has non-contiguous UIDs (0003 lies in 6)."""
    root = tmp_path / "vantage"
    cmr.make_tree(root)
    ctx = cmr.make_context(root)
    ctx.universe = {
        "SIM:SYS-0001": "SYS", "SIM:SYS-0002": "SYS", "SIM:SYS-0003": "SYS",
        "SIM:SYS-0004": "SYS", "SIM:SYS-0005": "SYS", "SIM:SYS-0006": "SYS",
        "SIM:SW-0001": "SW", "SIM:SW-0002": "SW", "SIM:IMP-0001": "IMP",
    }
    ctx.serves = {"SIM:IMP-0001": ["SIM:SW-0001", "SIM:SW-0002"]}
    ctx.sections = {
        "SIM:SYS-0001": "§5", "SIM:SYS-0002": "§5.1", "SIM:SYS-0003": "§6",
        "SIM:SYS-0004": "§5.2", "SIM:SYS-0005": "§6",
        "SIM:SYS-0006": "PART C — CONSTRAINTS",
        "SIM:SW-0001": "§1", "SIM:SW-0002": "§1.1", "SIM:IMP-0001": "§1",
    }
    return ctx


def _section_findings(tmp_path, *rows):
    text = "### 4.1 Rows\n\nScope: SIM:SYS, SIM:SW\n\n| UID | Disposition | Target | Why |\n|---|---|---|---|\n"
    text += "".join(f"| {a} | {b} | {c} | {d} |\n" for a, b, c, d in rows)
    findings, _ = cmr.run_checks(_section_ctx(tmp_path), cmr.parse_register(text))
    return [f for f in findings if not f.startswith(("C-CODE", "C-SEED"))]


S5 = ("SIM:SYS-0001..0002, SIM:SYS-0004", "superseded", "D13", "§5 — viewer is out")
S6 = ("SIM:SYS-0003, SIM:SYS-0005..0005", "retired", "—", "§6 — gone")
PART_C = ("SIM:SYS-0006..0006", "carried", "VNT", "PART C — CONSTRAINTS — kept")
SWROW = ("SIM:SW-0001..0002", "carried", "VNT", "§1 — kept")


def test_a_section_row_covering_its_whole_section_passes_and_imp_rows_inherit(tmp_path):
    assert _section_findings(tmp_path, S5, S6, PART_C, SWROW) == []


def test_an_unnumbered_heading_is_a_section_of_its_own(tmp_path):
    found = _section_findings(tmp_path, S5, S6, SWROW)
    assert _ids(found, "C-MISSING") == ["C-MISSING SIM:SYS-0006: no disposition"]


def test_c_duplicate_a_single_row_inside_a_section_row(tmp_path):
    found = _section_findings(
        tmp_path, S5, S6, PART_C, SWROW, ("SIM:SYS-0002", "carried", "VNT", "again")
    )
    assert len(_ids(found, "C-DUPLICATE")) == 1
    assert _ids(found, "C-DUPLICATE")[0].startswith("C-DUPLICATE SIM:SYS-0002:")


def test_c_duplicate_two_section_rows_sharing_a_uid(tmp_path):
    other = ("SIM:SYS-0004..0005", "carried", "VNT", "§5.2 — x")
    found = _section_findings(tmp_path, S5, S6, PART_C, SWROW, other)
    assert any(f.startswith("C-DUPLICATE SIM:SYS-0004") for f in found)


def test_c_range_and_c_missing_a_section_row_with_a_gap(tmp_path):
    gap = ("SIM:SYS-0001..0002", "superseded", "D13", "§5 — viewer is out")
    found = _section_findings(tmp_path, gap, S6, PART_C, SWROW)
    assert _ids(found, "C-RANGE") == [
        "C-RANGE SIM:SYS-0001..0002: SIM:SYS-0004 is in §5 but not covered"
    ]
    assert _ids(found, "C-MISSING") == ["C-MISSING SIM:SYS-0004: no disposition"]


def test_c_range_a_section_row_reaching_into_another_section(tmp_path):
    wide = ("SIM:SYS-0001..0004", "superseded", "D13", "§5 — viewer is out")
    found = _section_findings(tmp_path, wide, S6, PART_C, SWROW)
    assert any(f.startswith("C-RANGE SIM:SYS-0001..0004:") and "SYS-0003 is not in §5" in f for f in found)


def test_c_range_a_subsection_is_part_of_its_section_but_not_the_other_way(tmp_path):
    sub = ("SIM:SYS-0002..0002", "superseded", "D13", "§5.1 — viewer is out")
    found = _section_findings(tmp_path, sub)
    assert not any(f.startswith("C-RANGE") for f in found)


def test_c_range_an_imp_range(tmp_path):
    found = _section_findings(tmp_path, S5, S6, PART_C, SWROW, ("SIM:IMP-0001..0001", "carried", "VNT", "§1 — x"))
    assert any(f.startswith("C-RANGE SIM:IMP-0001..0001:") and "IMP" in f for f in found)


def test_c_range_a_why_without_a_section_label(tmp_path):
    bare = ("SIM:SYS-0001..0002, SIM:SYS-0004", "superseded", "D13", "viewer is out")
    found = _section_findings(tmp_path, bare, S6, PART_C, SWROW)
    assert any(f.startswith("C-RANGE SIM:SYS-0001..0002") and "Why" in f for f in found)


def test_c_range_a_reversed_a_malformed_and_an_empty_range(tmp_path):
    for cell in ("SIM:SYS-0004..0001", "SIM:SYS-0001..", "SIM:SYS-0007..0009"):
        row = (cell, "superseded", "D13", "§5 — viewer is out")
        found = _section_findings(tmp_path, row)
        assert any(f.startswith(f"C-RANGE {cell}:") for f in found), cell


def test_load_set_records_the_section_of_each_row(tmp_path):
    root = tmp_path
    for name, (directory, docs) in cmr.SETS.items():
        (root / directory).mkdir(parents=True, exist_ok=True)
        for kind, filename, form in docs:
            if form == "concept":
                body = "# 1. Purpose\n## 1.1 Why\n| 1.1 | CN-0001 | live |\n# PART I — CONCEPT\n| 2 | CN-0002 | live |\n"
            elif form == "block":
                body = f"## 5.1 Readers\n**`{kind}-0001`** · `P0`\n```\n# not a heading\n```\n**`{kind}-0002`** · `P0`\n"
            else:
                body = "### 3.4a Table\n| `IMP-0001` | `SW-0001` | `WP-01` | `NEW` | f | t |\n"
            (root / directory / filename).write_text(body, encoding="utf-8")
    ctx_sections = cmr._scan_set(root, "SIM")[2]
    assert ctx_sections["SIM:CN-0001"] == "§1.1" and ctx_sections["SIM:CN-0002"] == "PART I — CONCEPT"
    assert ctx_sections["SIM:SYS-0001"] == "§5.1" and ctx_sections["SIM:SYS-0002"] == "§5.1"
    assert ctx_sections["SIM:IMP-0001"] == "§3.4a"
