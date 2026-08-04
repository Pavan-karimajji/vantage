# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Check: the audit ledger indexes real corrections, and never becomes one.

``sim_audit_log.md`` records findings from the full-scope audit
(``modules/sim/.claude/prompts/sim_audit.md``). Its whole design rests on one
rule, and that rule is the only thing standing between a useful index and a
second source of truth:

    A finding whose origin is the requirements or the design level is NOT
    closable until the master document at that level has actually been edited.
    The ledger records *that the edit happened and where*; it never carries
    the correction itself.

Without enforcement that is a sentence in a document, and the failure it
prevents is silent: an audit "fixes" a requirements defect by describing the
fix in the log, ``sim_requirements.md`` stays wrong, and the log quietly
becomes where the truth lives. Every later reader of the register is then
misled by a document that looks authoritative and is stale — which is the
precise defect this whole project refuses everywhere else (``R-SIM-22``,
``R-SIM-3a``, ``R-SIM-3a``'s "one authoring home", defect ``D13``).

So this check enforces, mechanically:

* **ids are unique** — they are declared stable and citable, so a duplicate
  silently re-points every citation of it;
* **every ``CLOSED`` row names at least one landed-in target**, and
* **every named target resolves** — a document that exists, or a stage id the
  implementation plan actually defines. A ``CLOSED`` row pointing at a file
  that was renamed is a closed finding nobody can audit;
* **level 1 and 2 findings that are ``CLOSED`` name a master document**, not
  only a stage. A requirements defect closed by ticking a stage box has not
  been fixed at its origin;
* **``WONTFIX`` and ``SUPERSEDED`` carry a reason** — the columns exist so the
  decision survives the person who made it.

Coverage of the *content* — is the correction correct? — is not checkable here
and is not attempted. This guards the shape.

Usage
-----
    python docs/py/check_audit_ledger.py
"""

from __future__ import annotations

import re
import sys

from _common import DOCS_DIR, Report

LEDGER = DOCS_DIR / "sim_audit_log.md"
PLAN = DOCS_DIR / "sim_implementation_plan.md"
SIM_ROOT = DOCS_DIR.parent
SUPERPROJECT = SIM_ROOT.parent.parent

#: A "Landed in" cell may name a path relative to any of these -- the
#: superproject root (`.claude/rules/sim.md`, `plan.md`), the module
#: (`docs/py/check_*.py`, `CLAUDE.md`) or the docs folder itself.
SEARCH_BASES = (SUPERPROJECT, SIM_ROOT, DOCS_DIR)


def _resolves(target: str) -> bool:
    """True if ``target`` names a real file, by relative path or by basename."""
    rel = target.strip("`").lstrip("./")
    for base in SEARCH_BASES:
        if (base / rel).exists():
            return True
    # Basename fallback: the cell may cite a document without its folder.
    name = rel.split("/")[-1]
    for base in SEARCH_BASES:
        try:
            if next(base.rglob(name), None) is not None:
                return True
        except OSError:
            pass
    return False

#: A finding id. Stable, never reused.
AR_RE = re.compile(r"\*\*(AR-\d+)\*\*")
#: A stage id the plan defines with a "### S-xx --" heading.
STAGE_DEF_RE = re.compile(r"^### (S-[A-E]\d+[a-z]?[^\s]*) +(?:--|—)", re.M)
#: Things a "Landed in" cell may name: a doc filename, or a stage id.
DOC_RE = re.compile(r"`?([A-Za-z0-9_./-]+\.(?:md|py|txt|yaml|yml))`?")
STAGE_REF_RE = re.compile(r"`(S-[A-E]\d+[a-z]?(?:Δ\d?)?)`")

LEVELS_NEEDING_A_DOC = {"1", "2"}


def main() -> int:
    if not LEDGER.exists():
        print(f"RESULT  skipped -- no ledger at {LEDGER.name} yet")
        return 0

    text = LEDGER.read_text(encoding="utf-8", errors="replace")
    plan = PLAN.read_text(encoding="utf-8", errors="replace")
    stages = set(STAGE_DEF_RE.findall(plan))

    rep = Report("check_audit_ledger")
    rep.line("Audit ledger shape check -- sim_audit_log.md")

    failures: list[str] = []
    seen: dict[str, int] = {}
    counts = {"OPEN": 0, "CLOSED": 0, "SUPERSEDED": 0, "WONTFIX": 0}
    rows = 0

    for lineno, line in enumerate(text.splitlines(), 1):
        m = AR_RE.search(line)
        if not m or not line.lstrip().startswith("|"):
            continue
        rid = m.group(1)
        rows += 1
        if rid in seen:
            failures.append(f"{rid}: duplicate id (also line {seen[rid]}) -- ids are stable and unique")
        seen[rid] = lineno

        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # Level is the cell right after the id cell.
        level = ""
        for i, c in enumerate(cells):
            if AR_RE.search(c) and i + 1 < len(cells):
                level = cells[i + 1].strip()
                break

        joined = " ".join(cells)
        state = next((s for s in counts if s in joined), None)
        # Section context decides the state when the row carries no state cell.
        if state is None:
            head = text[: text.find(line)]
            last = max(
                (head.rfind("### Open"), "OPEN"),
                (head.rfind("### Closed"), "CLOSED"),
                (head.rfind("### Won't fix"), "WONTFIX"),
                (head.rfind("### Superseded"), "SUPERSEDED"),
            )
            state = last[1] if last[0] >= 0 else "OPEN"
        counts[state] = counts.get(state, 0) + 1

        if state in ("CLOSED", "SUPERSEDED"):
            targets = DOC_RE.findall(joined)
            stage_refs = [s for s in STAGE_REF_RE.findall(joined)]
            if not targets and not stage_refs:
                failures.append(
                    f"{rid}: {state} but names no landed-in document or stage -- "
                    "a closed finding must say where the fix landed")
            for t in targets:
                if not _resolves(t):
                    failures.append(f"{rid}: {state}, names '{t}' which does not resolve")
            for s in stage_refs:
                if s.rstrip("Δ0123456789") not in stages and s not in stages:
                    failures.append(f"{rid}: {state}, names stage '{s}' the plan does not define")
            if level in LEVELS_NEEDING_A_DOC and not targets:
                failures.append(
                    f"{rid}: origin level {level} closed without naming a master document -- "
                    "a requirement/design defect is not fixed by ticking a stage box")

        if state in ("WONTFIX", "SUPERSEDED") and len(joined) < 120:
            failures.append(f"{rid}: {state} with no recorded reason")

    rep.heading("Ledger")
    rep.table(["rows", "open", "closed", "superseded", "wontfix"],
              [[rows, counts["OPEN"], counts["CLOSED"],
                counts["SUPERSEDED"], counts["WONTFIX"]]])

    rep.line()
    if failures:
        rep.line(f"RESULT  FAIL -- {len(failures)} ledger defect(s)")
        for f in failures:
            rep.line(f"  {f}")
        rep.failures.extend(failures)
    else:
        rep.line(f"RESULT  ok -- {rows} findings, every closed row names a "
                 "landed-in target that resolves")
    rep.write_log()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
