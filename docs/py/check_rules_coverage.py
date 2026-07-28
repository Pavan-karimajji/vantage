# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Check: every normative rule is anchored to a requirement and to a stage.

``.claude/rules/sim.md`` is the normative index. A rule that no requirement asks
for is a rule someone invented; a rule that no stage builds is a rule nothing
will ever enforce. Both are how a rules file becomes decoration.

This check closes the triangle the other two checks leave open:

    requirement  --(check_traceability)-->  test  --> stage
         \\                                              /
          \\------------- (this check) ----- rule ------/

Usage
-----
    python docs/py/check_rules_coverage.py
"""

from __future__ import annotations

import re
import sys

from _common import DOCS_DIR, SIM_DIR, Report

RULES = SIM_DIR.parent.parent / ".claude" / "rules" / "sim.md"
REQ = DOCS_DIR / "sim_requirements.md"
PLAN = DOCS_DIR / "sim_implementation_plan.md"

RULE_RE = re.compile(r"\bR-SIM-(\d+[a-z]?)\b")
#: Rules whose enforcement is a *document* discipline rather than code, and
#: which therefore legitimately appear in no stage. Each names why.
DOC_ONLY_RULES = {
    "5": "vocabulary discipline -- enforced by review and by DC checks, not by code",
}


def main() -> int:
    rep = Report("check_rules_coverage")
    rep.line("Checking: rule <-> requirement <-> stage")

    if not RULES.is_file():
        rep.skip(f"rules file not found at {RULES.name} "
                 "(run from a full superproject checkout)")
        return rep.finish()

    rules_text = RULES.read_text(encoding="utf-8")
    req_text = REQ.read_text(encoding="utf-8")
    plan_text = PLAN.read_text(encoding="utf-8")


    # Rules are *declared* by a table row "| R-SIM-n | ... |".
    declared = sorted(
        {m.group(1) for m in re.finditer(r"^\| R-SIM-(\d+[a-z]?) \|", rules_text, re.M)},
        key=lambda s: (int(re.sub(r"\D", "", s)), s),
    )
    rep.line(f"{len(declared)} rules declared")

    cited_req = {m.group(1) for m in RULE_RE.finditer(req_text)}
    cited_plan = {m.group(1) for m in RULE_RE.finditer(plan_text)}
    # "Derived, not invented" is satisfied by ANY design document explaining
    # the rule -- expectations live in the scenarios doc, the ABI in the
    # contract doc. Only the *build* obligation is narrowed to the plan.
    cited_arch = set()
    for doc in sorted(DOCS_DIR.glob("sim_*.md")):
        if doc.name in ("sim_requirements.md", "sim_implementation_plan.md"):
            continue
        cited_arch |= {m.group(1) for m in
                       RULE_RE.finditer(doc.read_text(encoding="utf-8"))}

    rep.heading("1. Every rule is asked for by a requirement")
    rows = []
    for rid in declared:
        in_req = rid in cited_req
        in_plan = rid in cited_plan
        in_arch = rid in cited_arch
        rows.append([f"R-SIM-{rid}",
                     "yes" if in_req else "NO",
                     "yes" if in_plan else "NO",
                     "yes" if in_arch else "NO"])
        if not in_req and not in_arch:
            rep.fail(f"R-SIM-{rid} is cited by neither the register nor the "
                     "architecture -- it was invented, not derived")
    rep.table(["rule", "in register", "in plan", "in design docs"], rows)

    rep.heading("2. Every rule is built by a stage")
    for rid in declared:
        if rid in cited_plan:
            continue
        if rid in DOC_ONLY_RULES:
            rep.line(f"  R-SIM-{rid}: document-only -- {DOC_ONLY_RULES[rid]}")
            continue
        rep.fail(f"R-SIM-{rid} appears in no stage of the implementation plan -- "
                 "nothing will enforce it")

    rep.heading("3. Rules cited but never declared")
    for rid in sorted(cited_req | cited_plan | cited_arch):
        if rid not in declared:
            rep.fail(f"R-SIM-{rid} is cited but not declared in the rules file")

    if not rep.failures:
        rep.ok(f"all {len(declared)} rules are derived from a requirement and "
               "built by a stage")
    return rep.finish()


if __name__ == "__main__":
    sys.exit(main())
