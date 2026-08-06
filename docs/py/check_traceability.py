# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Check: the requirements register, the rules and the plan agree with each other.

The design set is only trustworthy if its three halves stay joined:

* every requirement names the test that proves it, and that test exists;
* every test defined in the plan belongs to a stage that exists;
* every stage has a gate, and the gate cites tests it actually defines.

A broken link here is how a requirement silently stops being verified -- the
document still reads correctly, and nothing proves it any more. This is the
check to run before every docs commit.

Exit code is non-zero on any failure, so it can gate a hook or a CI step.

Usage
-----
    python docs/py/check_traceability.py
"""

from __future__ import annotations

import re
import sys

from _common import DOCS_DIR, Report

REQ = DOCS_DIR / "sim_requirements.md"
PLAN = DOCS_DIR / "sim_implementation_plan.md"

#: A verifier identifier. Four classes, because not every requirement is
#: provable by a unit test:
#:   UT-<stage>-<n> / ST-<stage>-<n>  code tests, defined in the plan
#:   GT-<n>                           global gates, re-checked every stage
#:   MC-<n>                           named manual checks
#:   DC-<n>                           design-document invariants, implemented
#:                                    by docs/py/check_doc_invariants.py
ID_RE = re.compile(r"\b((?:UT|ST)-[A-Z]\d[a-z]?|GT|MC|DC)-(\d+)(?:\.\.(\d+))?\b")
#: DC ids live in the checker, not the plan, so a requirement may cite one
#: without the plan having to redefine it. **Derived from the implementation,
#: never restated here** -- this was `range(1, 9)`, a hand-kept second copy that
#: went stale the moment audit run 3 added `DC-9`, and the failure it produced
#: read as "the plan does not define DC-9" rather than "this list is out of
#: date". Reading the checker's own `rep.heading("DC-n ...")` calls makes the
#: implementation the single source, which is the discipline `R-SIM-22` states
#: for generated code and `AR-34`/`AR-40` found violated twice in the register.
def _dc_ids() -> set[str]:
    src = (DOCS_DIR / "py" / "check_doc_invariants.py")
    if not src.is_file():                      # defensive: keep the check usable
        return {f"DC-{n}" for n in range(1, 10)}
    return set(re.findall(r'rep\.heading\("(DC-\d+)\b', src.read_text(encoding="utf-8")))


DC_IDS = _dc_ids()
#: A requirement heading: "### FR-SIM-46 -- title"
REQ_HEAD_RE = re.compile(r"^### ((?:FR|NR|CR)-SIM-\d+[a-z]?) +(?:--|—) *(.*)$", re.M)
#: A stage heading: "### S-D6 -- title"
STAGE_HEAD_RE = re.compile(r"^### (S-[A-E]\d[a-z]?) +(?:--|—) *(.*)$", re.M)


def expand(text: str) -> set[str]:
    """All test ids in ``text``, expanding ``UT-B2-7..10`` ranges."""
    out: set[str] = set()
    for base, first, last in ID_RE.findall(text):
        lo = int(first)
        hi = int(last) if last else lo
        for n in range(lo, hi + 1):
            out.add(f"{base}-{n}")
    return out


def main() -> int:
    rep = Report("check_traceability")
    rep.line("Checking: requirements <-> tests <-> stages")

    for path in (REQ, PLAN):
        if not path.is_file():
            rep.fail(f"missing document: {path.name}")
            return rep.finish()

    req_text = REQ.read_text(encoding="utf-8")
    plan_text = PLAN.read_text(encoding="utf-8")

    defined = expand(plan_text) | DC_IDS
    stages = {m.group(1) for m in STAGE_HEAD_RE.finditer(plan_text)}
    rep.line(f"plan defines {len(defined - DC_IDS)} test/gate ids across "
             f"{len(stages)} stages, plus {len(DC_IDS)} document checks")

    # -- 1. every id cited by a requirement exists ------------------------
    rep.heading("1. Requirement -> test")
    requirements = REQ_HEAD_RE.findall(req_text)
    rep.line(f"{len(requirements)} requirements in the register")

    blocks = re.split(r"^### ", req_text, flags=re.M)[1:]
    unverified: list[str] = []
    no_verifier_yet: list[str] = []
    for block in blocks:
        head = block.split("\n", 1)[0]
        m = re.match(r"((?:FR|NR|CR)-SIM-\d+[a-z]?)", head)
        if not m:
            continue
        rid = m.group(1)
        cited = expand(block)
        for tid in sorted(cited):
            if tid not in defined:
                rep.fail(f"{rid} cites {tid}, which the plan does not define")
        # A requirement legitimately has no verifier when it is not yet
        # decided (`open`), deliberately not designed (`parked`), or --
        # `NR-SIM-46`'s own case, found when its decision landed 2026-08-05
        # -- provable only by a human decision record, never by a test (a
        # product judgement, not a code behaviour). Anything else without
        # one is a requirement nothing will ever prove.
        deferred = any(m in block for m in
                       ("**parked**", "**Status.** parked",
                        "**`open`**", "**Status.** open", "`open`.",
                        "**Verified by.** A recorded decision"))
        if not cited and not deferred:
            unverified.append(rid)
        elif not cited:
            no_verifier_yet.append(rid)
    if unverified:
        for rid in unverified:
            rep.fail(f"{rid} names no verifying test and is not marked open or parked")
    else:
        rep.ok("every decided requirement names at least one existing test")
    # Reported, never silent: an open requirement is a known hole, and a list
    # of known holes that nobody prints is indistinguishable from no holes.
    if no_verifier_yet:
        rep.line(f"  {len(no_verifier_yet)} requirement(s) open/parked, verifier "
                 f"not written yet: {', '.join(sorted(no_verifier_yet))}")

    # -- 2. every test belongs to a stage that exists ---------------------
    rep.heading("2. Test -> stage")
    orphans = set()
    for tid in sorted(defined):
        kind, _, rest = tid.partition("-")
        if kind in ("GT", "MC", "DC"):
            continue                        # global, not stage-scoped
        stage_token = rest.rsplit("-", 1)[0]
        if f"S-{stage_token}" not in stages:
            orphans.add(tid)
    if orphans:
        for tid in sorted(orphans):
            rep.fail(f"{tid} names stage S-{tid.split('-')[1]}, which does not exist")
    else:
        rep.ok("every stage-scoped test id maps to a declared stage")

    # -- 2b. no test id is defined twice ----------------------------------
    # This bit twice while the plan was being granularised: a test appended to
    # a stage reused a number already present further up, and both readings
    # looked correct in isolation. A duplicate id silently merges two
    # obligations into one, so a requirement citing it may be verified by the
    # wrong test. Mechanical from here on -- same lesson as DC-8.
    # A test is *defined* by a bullet inside a stage's **Tests** block. The same
    # id appearing in a **Gate** block is a citation and is expected -- scoping
    # to the Tests block is what makes the difference, and getting that wrong
    # was this check's own first bug.
    rep.heading("2b. Test ids are unique")
    seen: dict[str, int] = {}
    dupes = 0
    lines = plan_text.splitlines()
    in_tests = False
    for n, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("**"):
            in_tests = stripped.startswith("**Tests**")
            continue
        if stripped.startswith("### ") or stripped.startswith("## "):
            in_tests = False
            continue
        if not in_tests:
            continue
        for m in re.finditer(r"- \[[ x]\] `((?:UT|ST)-[A-Z]\d[a-z]?-\d+)`", line):
            tid = m.group(1)
            if tid in seen:
                rep.fail(f"{tid} defined twice in a Tests block: "
                         f"lines {seen[tid]} and {n}")
                dupes += 1
            else:
                seen[tid] = n
    if not dupes:
        rep.ok(f"all {len(seen)} test definitions unique")

    # -- 2c. a test is defined under the stage its id names ---------------
    # `UT-C5-6` sitting in S-C3's Tests block passes every other check here:
    # the id is unique, and S-C5 exists so the id resolves. But S-C5's gate
    # will never see it, and S-C3's gate covers a test about someone else's
    # work. A misfiled test is a gate that silently covers nothing.
    rep.heading("2c. Tests are filed under the stage they name")
    misfiled = 0
    current: str | None = None
    in_tests = False
    for line in plan_text.splitlines():
        stripped = line.strip()
        m_stage = re.match(r"^### (S-[A-E]\d[a-z]?)\b", stripped)
        if m_stage:
            current, in_tests = m_stage.group(1), False
            continue
        if stripped.startswith("**"):
            in_tests = stripped.startswith("**Tests**")
            continue
        if not (in_tests and current):
            continue
        for m in re.finditer(r"- \[[ x]\] `(?:UT|ST)-([A-Z]\d[a-z]?)-\d+`", line):
            owner = f"S-{m.group(1)}"
            if owner != current:
                rep.fail(f"{current} defines a test named for {owner}: "
                         f"{line.strip()[:70]}")
                misfiled += 1
    if not misfiled:
        rep.ok("every test is defined under the stage its id names")

    # -- 3. every stage has tests and a gate ------------------------------
    rep.heading("3. Stage -> tests + gate")
    sections = re.split(r"^### (?=S-[A-E]\d)", plan_text, flags=re.M)
    for sec in sections[1:]:
        sid = sec.split(" ", 1)[0].strip()
        body = sec
        n_tests = len(expand(body) - {t for t in expand(body) if t.startswith(("GT-", "MC-"))})
        has_gate = "**Gate**" in body
        if n_tests == 0:
            rep.fail(f"{sid} defines no tests")
        if not has_gate:
            rep.fail(f"{sid} has no **Gate** block")
    if not rep.failures:
        rep.ok(f"all {len(stages)} stages define tests and a gate")

    # -- 4. summary -------------------------------------------------------
    rep.heading("4. Coverage summary")
    cited_total = expand(req_text)
    rep.line(f"tests defined in plan      {len(defined)}")
    rep.line(f"tests cited by a requirement {len(cited_total & defined)}")
    rep.line(f"tests not cited by any requirement "
             f"{len(defined - cited_total)}  (fine -- stage gates cite them)")
    return rep.finish()


if __name__ == "__main__":
    sys.exit(main())
