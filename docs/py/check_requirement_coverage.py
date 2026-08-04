# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Check: how much of each requirement is actually *proven* today.

``check_traceability.py`` answers *"does every requirement name a test, and does
that test exist?"* — a structural question about the documents. It says nothing
about whether the named test has been **written and run**, because every id it
resolves is equally real whether its checkbox is ticked or blank.

That gap is what this check closes. A requirement's verification state is
**derived** from the implementation plan's own ticks, never stored as a second
field somebody has to maintain — a hand-kept ``Built:`` column beside a
checkbox-tracked plan is exactly the drifting second copy this project refuses
everywhere else (``R-SIM-22``, ``R-SIM-3a``, defect ``D13``). So the register
stays the source of *what was asked*, the plan stays the source of *what is
done*, and this script is the join.

What it reports, per requirement: how many of its cited ``UT-``/``ST-`` ids are
ticked in the plan, bucketed as ``proven`` / ``partial`` / ``unproven`` /
``no test id``, summarised by priority. The `P0` line is the one to read: a
`P0` requirement with no proven verifier is the register's own definition of
*"the tool is not usable without it"* colliding with *"nothing demonstrates
it"*.

**This check does not fail on low coverage.** Coverage is a status report, not
an invariant — most rows are legitimately unproven while their phase is still
ahead. It fails only on things that are always wrong:

* a cited ``UT-``/``ST-`` id the plan never defines as a checkbox (a verifier
  that cannot be resolved to a unit of work);
* a requirement whose ``Verified by`` field is missing entirely — **unless it
  is ``parked``**, which is the one status that legitimately has no verifier
  (nothing is being built, so nothing can prove it). A parked row without a
  verifier is correct; a frozen one without a verifier is a hole.

Aboutness — *is the cited test actually about this requirement?* — is
deliberately **not** checked, and cannot be: see ``sim_requirements.md`` §12.7,
where two of eleven ids pointed at real tests on unrelated subjects and every
mechanical check passed. Read the test.

Usage
-----
    python docs/py/check_requirement_coverage.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter

from _common import DOCS_DIR, Report

REQ = DOCS_DIR / "sim_requirements.md"
PLAN = DOCS_DIR / "sim_implementation_plan.md"

#: A code-test id. Gates (``GT-``), manual checks (``MC-``) and document
#: invariants (``DC-``) are legitimate verifiers but have no checkbox in the
#: plan to derive a state from, so they are counted as cited-but-not-scored.
TEST_ID_RE = re.compile(r"\b(?:UT|ST)-[A-E]\d+[a-z]?-\d+\b")
REQ_HEAD_RE = re.compile(r"^### ((?:FR|NR|CR)-SIM-\d+[a-z]?) +(?:--|—) *(.*)$", re.M)
#: The line that *defines* a test: a checkbox whose first token is the id.
#: ``> `` prefixes are allowed — several stages quote their scope in blockquotes.
DEFN_RE = re.compile(
    r"^\s*(?:> )?- \[([ x])\]\s*`((?:UT|ST)-[A-E]\d+[a-z]?-\d+)`", re.M)
FIELD_RE = "\\*\\*{}\\.?\\*\\*\\s*(.*?)(?=\\*\\*[A-Z][a-z]|\\Z)"


def _field(body: str, name: str) -> str:
    m = re.search(FIELD_RE.format(name), body, re.S)
    return " ".join(m.group(1).split()) if m else ""


def main() -> int:
    plan = PLAN.read_text(encoding="utf-8", errors="replace")
    reg = REQ.read_text(encoding="utf-8", errors="replace")

    # id -> ticked. A test ticked anywhere counts as done; several stages
    # restate an id in their Gate block after defining it in Tests.
    ticked: dict[str, bool] = {}
    for state, tid in DEFN_RE.findall(plan):
        ticked[tid] = ticked.get(tid, False) or (state == "x")

    heads = list(REQ_HEAD_RE.finditer(reg))
    rep = Report("check_requirement_coverage")
    rep.line("Requirement verification coverage, derived from the plan's ticks")
    rep.line(f"{len(heads)} requirements; {len(ticked)} test ids defined in the plan")

    failures: list[str] = []
    rows = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(reg)
        body = re.split(r"\n---\n", reg[m.end():end])[0]
        rid, title = m.group(1), m.group(2).strip()

        verified = _field(body, "Verified by")
        status = _field(body, "Status").replace("*", "").lower()
        parked = status.startswith("parked")
        if not verified and not parked:
            failures.append(f"{rid}: no 'Verified by' field at all")

        prio = _field(body, "Priority").replace("`", "")
        level = "P0" if prio.startswith("P0") else "P2" if prio.startswith("P2") else "P1"

        ids = sorted(set(TEST_ID_RE.findall(verified)))
        for tid in ids:
            if tid not in ticked:
                failures.append(
                    f"{rid}: cites {tid}, which the plan never defines as a checkbox")
        done = [t for t in ids if ticked.get(t)]

        if parked:
            state = "parked"
        elif not ids:
            state = "no test id"
        elif not done:
            state = "unproven"
        elif len(done) == len(ids):
            state = "proven"
        else:
            state = "partial"
        rows.append((level, rid, title, state, len(done), len(ids),
                     [t for t in ids if not ticked.get(t)]))

    by_state = Counter(r[3] for r in rows)
    rep.heading("Summary")
    rep.table(
        ["priority", "proven", "partial", "unproven", "no test id", "parked", "total"],
        [[lvl,
          sum(1 for r in rows if r[0] == lvl and r[3] == "proven"),
          sum(1 for r in rows if r[0] == lvl and r[3] == "partial"),
          sum(1 for r in rows if r[0] == lvl and r[3] == "unproven"),
          sum(1 for r in rows if r[0] == lvl and r[3] == "no test id"),
          sum(1 for r in rows if r[0] == lvl and r[3] == "parked"),
          sum(1 for r in rows if r[0] == lvl)]
         for lvl in ("P0", "P1", "P2")],
    )

    rep.heading("P0 requirements — the tool is not usable without these")
    rep.table(
        ["id", "state", "done", "requirement", "outstanding verifiers"],
        [[r[1], r[3], f"{r[4]}/{r[5]}", r[2][:44], ", ".join(r[6]) or "-"]
         for r in rows if r[0] == "P0"],
    )

    rep.heading("Partial — some verifiers proven, some not")
    rep.table(
        ["id", "pri", "done", "requirement", "outstanding verifiers"],
        [[r[1], r[0], f"{r[4]}/{r[5]}", r[2][:44], ", ".join(r[6])]
         for r in rows if r[3] == "partial"],
    )

    rep.line()
    if failures:
        rep.line(f"RESULT  FAIL — {len(failures)} unresolvable verifier(s)")
        for f in failures:
            rep.line(f"  {f}")
        rep.failures.extend(failures)
    else:
        rep.line("RESULT  ok — every cited verifier resolves to a unit of work "
                 f"({by_state['proven']} proven, {by_state['partial']} partial, "
                 f"{by_state['unproven']} unproven, "
                 f"{by_state['no test id']} verified by other means)")
    rep.write_log()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
