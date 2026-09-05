# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <pavankarimajji1997@gmail.com>

"""Evidence for the 2026-09-05 ``R-REQ-13``/``R-REQ-14`` change.

That change did four things to ``trace_check.py``: it deleted the document
length cap, demoted the requirement budget from a failure to a reported
expectation, added the commentary cap that replaced both, and started printing
``budget_history``. A fifth is an unrelated bug fix -- a declared-but-unwritten
test spec used to raise instead of reporting.

**The commentary cap itself is proved by the module's own ``--selftest``**
(``selftest_mutations.yaml``, the mechanism ``R-REQ-9`` already sanctions).
What that mechanism cannot express is the *absence* of a finding, which is
most of what this change is -- so this file covers the negative half:

======================================  ====================================
claim                                   why --selftest cannot prove it
======================================  ====================================
document length is no longer capped     nothing to plant; the check is gone
over budget is a note, not a finding    a plant asserts a finding APPEARS
commentary is reported in --stats       output, not a finding
budget_history is printed               output, not a finding
missing test spec never raises          a traceback is not a finding
======================================  ====================================

Run:  python py/test_checker_additions.py           # the checks
      python py/test_checker_additions.py --plant   # prove they can fail
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

HISTORY = re.compile(r"Budget history -- \d+ change")
COMMENTARY_REPORT = re.compile(r"Commentary per requirement")

# Read from layers.yaml, never hard-coded -- the same discipline that makes
# trace_check.py copyable to any module without editing it.
SPEC = yaml.safe_load((ROOT / "layers.yaml").read_text(encoding="utf-8"))
TOP = SPEC["layers"][0]
TOP_DOC = TOP["doc"]
TOP_ID = TOP["id"]
TOP_BUDGET = TOP["budget"]
TEST_SPEC = SPEC["test_spec"]
TOP_TEST = TOP["tests"][0]


def run(root: Path, *args: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(root / "py" / "trace_check.py"), *args],
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def sandbox(tmp: Path, name: str, edit=None) -> Path:
    """Copy the whole set to a throwaway directory, optionally editing layers.yaml."""
    dst = tmp / name
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns("__pycache__"))
    if edit:
        f = dst / "layers.yaml"
        f.write_text(edit(f.read_text(encoding="utf-8")), encoding="utf-8")
    return dst


def drop_history(text: str) -> str:
    """Remove the budget_history block: its key through to the next top-level key."""
    out, skipping = [], False
    for line in text.splitlines(keepends=True):
        if line.startswith("budget_history:"):
            skipping = True
            continue
        if skipping:
            if line[:1].strip() and not line.startswith(" "):
                skipping = False
            else:
                continue
        out.append(line)
    return "".join(out)


def check(name: str, condition: bool) -> bool:
    print(f"  {'pass' if condition else 'FAIL'}  {name}")
    return condition


def main() -> int:
    print("\n  R-REQ-13/14 change -- evidence for the half --selftest cannot reach\n")
    ok = True

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        live = run(ROOT, "--stats")

        # -- length is no longer capped ----------------------------------------
        # The point of the change: a document is as long as the problem needs.
        fat = sandbox(tmp, "fat")
        doc = fat / TOP_DOC
        # 900 lines of REQUIREMENT-SHAPED content: long, but not commentary.
        pad = "".join(
            f"\n**`{TOP_ID}-{900 + i}`** · `P2` · `R2` — Padding row {i}\n"
            f"**Shall.** A padding obligation.\n"
            f"**Accept.** A padding observation that could be false.\n"
            f"**Category.** `feature`\n"
            f"**Verify.** T · `{TOP_TEST}-{900 + i}`   **Trace.** —\n"
            for i in range(150)
        )
        doc.write_text(doc.read_text(encoding="utf-8") + pad, encoding="utf-8")
        fat_out = run(fat, "--stats")
        ok &= check("a 900-line document raises no length finding", "C-DOCLINES" not in fat_out)
        # The claim is about the CHECKER, not its output: the cap is gone from the
        # code, not merely quiet today. Asserting on output text was tried first
        # and collided with the commentary report's own wording ("... lines over
        # N requirements") -- a reminder that a string match is not a claim.
        src = (ROOT / "py" / "trace_check.py").read_text(encoding="utf-8")
        ok &= check("...because the cap is gone from the checker, not just quiet",
                    "doc_lines" not in src and "C-DOCLINES" not in src)

        # -- over budget is a NOTE, not a finding -------------------------------
        over = run(
            sandbox(tmp, "over", lambda s: s.replace(f"    budget: {TOP_BUDGET}\n", "    budget: 1\n")),
            "--stats",
        )
        ok &= check("over the expectation produces no C-BUDGET finding", "C-BUDGET " not in over)
        ok &= check("...and says so as a note instead", "declared expectation of 1" in over)
        # The ratio is over the ACTUAL count, not the old expectation -- a layer
        # need not be full. Computed from the run itself rather than assumed.
        # Defensive: a planted violation can make the checker produce no table at
        # all, and an exception here would abort the run before the check that
        # violation is meant to trip. A test that cannot survive a broken subject
        # cannot prove anything about it.
        m = re.search(rf"  {TOP_ID}\s+(\d+)", over)
        ok &= check(
            "...naming the percentage, so the scope signal is legible",
            bool(m) and f"({int(m.group(1)) * 100}%)" in over,
        )

        # -- commentary is measured and reported --------------------------------
        ok &= check("commentary per requirement is reported", bool(COMMENTARY_REPORT.search(live)))
        ok &= check("...with the cap in force named", "cap 6" in live)
        ok &= check("...and this set is under it", "C-COMMENTARY" not in live)

        # -- prose with no requirements at all ----------------------------------
        # The shape of the two documents this cap exists for: 990 and 81
        # commentary lines per requirement. A ratio needs a denominator, so the
        # zero-requirement case is checked separately or it would divide by nothing.
        prose = sandbox(tmp, "prose")
        (prose / TOP_DOC).write_text(
            "# Prose\n\n" + "An essay line.\n" * 80, encoding="utf-8"
        )
        prose_out = run(prose, "--stats")
        ok &= check("a requirement document with prose and no requirements is caught", "C-COMMENTARY" in prose_out)

        # -- budget_history -----------------------------------------------------
        # Only a set that has actually changed its basis has a history to print.
        # Most sets never do, and that is the healthy case -- so the positive
        # half is skipped rather than failed.
        if SPEC.get("budget_history"):
            ok &= check("budget_history is printed", bool(HISTORY.search(live)))
            ok &= check(
                "...with a reason, not just the numbers",
                any(len(h.get("why", "")) > 40 for h in SPEC["budget_history"]),
            )
        else:
            print("  skip  budget_history -- none declared, nothing to print")
        nohist = run(sandbox(tmp, "nohist", drop_history), "--stats")
        ok &= check("...and the block is absent when unset", not HISTORY.search(nohist))
        ok &= check("...with the run still completing", "requirement set" in nohist)

        # -- missing test spec: a finding, never a traceback --------------------
        bare = sandbox(tmp, "bare")
        (bare / TEST_SPEC).write_text("placeholder\n", encoding="utf-8")
        ok &= check("a present test spec produces no finding for it", "test_spec" not in run(bare, "--stats"))
        (bare / TEST_SPEC).unlink()
        absent = run(bare, "--stats")
        ok &= check("a missing test spec reports C-DOC-MISSING", "C-DOC-MISSING  test_spec" in absent)
        ok &= check("...and does not raise", "Traceback" not in absent)

        # -- every mode still runs ----------------------------------------------
        for mode in ("--stats", "--matrix", "--next-uid", "--exec-rows", "--selftest"):
            ok &= check(f"{mode} runs without raising", "Traceback" not in run(ROOT, mode))

    print()
    print("  ALL PASS" if ok else "  FAILURES ABOVE")
    return 0 if ok else 1


# --------------------------------------------------------------- planting ----
# R-REQ-9 turned on this file. Each change is reverted in a COPY of the checker
# and the check above must go red. The real checker is never edited.


def _restore_doclines(t: str) -> str:
    """Put the deleted length cap back."""
    i = t.index("        body = doc.read_text")
    return (
        t[:i]
        + '        body = doc.read_text(encoding="utf-8").splitlines()\n'
        + "        if len(body) > 400:\n"
        + '            findings.append(Finding("C-DOCLINES", ly["doc"], "over 400 lines"))\n'
        + t[i + len('        body = doc.read_text(encoding="utf-8").splitlines()\n'):]
    )


def _restore_hard_budget(t: str) -> str:
    """Put the budget back as a failure instead of a note."""
    i = t.index("            notes.append(\n                f\"{lid} holds {n} requirements")
    j = t.index("\n\n", i)
    return t[:i] + '            findings.append(Finding("C-BUDGET", lid, "over budget"))' + t[j:]


def _remove_commentary(t: str) -> str:
    i = t.index("        ccap = limits.get(\"commentary_lines_per_requirement\")")
    j = t.index("    # --- C-LAYER-EMPTY", i)
    return t[:i] + t[j:]


def _remove_history(t: str) -> str:
    i = t.index('    history = spec.get("budget_history")')
    j = t.index("    com = stats.get(", i)
    return t[:i] + t[j:]


def _restore_crash(t: str) -> str:
    i = t.index("    if tspec.is_file():")
    tail = "        tests_list, fixtures = [], set()\n"
    j = t.index(tail) + len(tail)
    return t[:i] + "    tests_list, fixtures = parse_tests(tspec, prefix_layer)\n" + t[j:]


PLANTS = [
    ("length cap put back", _restore_doclines, "raises no length finding"),
    ("budget restored to a hard failure", _restore_hard_budget, "no C-BUDGET finding"),
    ("commentary cap removed", _remove_commentary, "prose and no requirements is caught"),
    ("budget_history printing removed", _remove_history, "budget_history is printed"),
    ("test-spec guard reverted to the old crash", _restore_crash, "does not raise"),
]


def plant() -> int:
    print("\n  Planted violations -- each change reverted, this file must notice\n")
    print(f"  {'planted':44s}{'the check that must go red':40s}caught?")
    print("  " + "-" * 92)
    original = (ROOT / "py" / "trace_check.py").read_text(encoding="utf-8")
    ok = True
    # A plant is only meaningful where the behaviour it removes is exercised.
    # A set that declares no budget_history prints none either way, so removing
    # the printing changes nothing and the plant would be a false failure.
    plants = [p for p in PLANTS if not (p[1] is _remove_history and not SPEC.get("budget_history"))]
    with tempfile.TemporaryDirectory() as td:
        for i, (name, mutate, expect) in enumerate(plants):
            dst = sandbox(Path(td), f"plant{i}")
            (dst / "py" / "trace_check.py").write_text(mutate(original), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(dst / "py" / "test_checker_additions.py")],
                capture_output=True,
                text=True,
            )
            red = [l for l in proc.stdout.splitlines() if l.strip().startswith("FAIL")]
            caught = proc.returncode != 0 and any(expect in l for l in red)
            ok &= caught
            print(f"  {name:44s}{expect:40s}{'yes' if caught else 'NO'}")
    print()
    print("  ALL PLANTS CAUGHT" if ok else "  A PLANT WAS MISSED -- that check is not real")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(plant() if "--plant" in sys.argv else main())
