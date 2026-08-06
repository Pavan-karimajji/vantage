# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Check: a ticked verifier can be found from the code that implements it.

``check_traceability.py`` proves a requirement's cited id is *defined* in the
plan. ``check_requirement_coverage.py`` proves it is *ticked*. Neither can tell
you where the test **is** — and a ticked box whose id appears in no source file
is bound to its implementation by one sentence in a 8,000-line plan.

That is not hypothetical. ``AR-7`` (audit run 1) found exactly it: ``ST-C9-1``
was real, passing, and implemented inside a file named for a *different* stage,
whose docstring announced only ``ST-C1c-1``. Grepping the suite for a ``P0``
requirement's primary verifier returned nothing. It was fixed for that one id,
by hand, and **nothing stopped it recurring** — audit run 3 measured the same
defect on a further batch of ids (``AR-50``).

The reverse polarity is ``AR-8``: a docstring claiming an id no test function
implements. That one this check cannot see; only a human reading the test can.

**This check reports, and ratchets.** It does not fail on the ids that were
already undiscoverable when it was written — turning a documentation-hygiene
number into a red build on day one is how a check gets an exemption bolted on
and stops meaning anything (``check_requirement_coverage.py``'s own docstring
makes the same call for the same reason). It fails on **growth**: a run that
finds more undiscoverable ids than ``BASELINE`` has let a new one in, which is
the moment fixing it is cheap.

Lowering ``BASELINE`` as ids are fixed is the intended direction and needs no
ceremony. **Raising it is a decision that needs a written reason**, exactly like
a ``GT-4`` floor.

Usage
-----
    python docs/py/check_verifier_discoverability.py
"""

from __future__ import annotations

import re
import sys

from _common import DOCS_DIR, SIM_DIR, Report

PLAN = DOCS_DIR / "sim_implementation_plan.md"
MODULES = SIM_DIR.parent

#: **Measured**, not chosen: 19 of 297 ticked ids were undiscoverable when this
#: check was first run (2026-08-06, audit run 3, `AR-50`). Every one is a REAL,
#: passing test whose id is simply not written where the test lives -- roughly
#: half are C++ gtests in `df`/`interfaces`/`sil_host` named after the behaviour
#: rather than the id, and the rest are Python tests the plan cites by function
#: name (`UT-C5-2` -> `test_a2_project.py::test_resolution_order_...`), which is
#: a legitimate citation in the plan and still leaves the code end blank.
#: All 19 threaded back to their implementing code 2026-08-06 (`AR-50`,
#: fix queue row 1) -- lowered to 0.
BASELINE = 0

#: A checkbox that DEFINES a test id: the id is its first token. `> ` prefixes
#: are allowed (several stages quote their scope inside blockquotes), and `~`
#: is the plan's own partial state. Identical shape to
#: `check_requirement_coverage.py`'s `DEFN_RE`, deliberately -- if the two ever
#: disagree about what "defined" means, one of them is scoring the wrong set.
DEFN_RE = re.compile(r"^\s*(?:> )?- \[([ x~])\]\s*`((?:UT|ST)-[A-E]\d+[a-z]?-\d+)`", re.M)

#: Where an id may legitimately live. Sources across every module, not just
#: `sim` -- roughly a third of the plan's verifiers are C++ gtests in `df`,
#: `interfaces`, `vdy` or `sil_host`, and a check that looked only at
#: `modules/sim/tests` would report those as missing and be switched off.
SOURCE_SUFFIXES = {".py", ".cpp", ".hpp", ".h", ".cmake", ".yaml", ".yml", ".txt", ".md"}
SKIP_PARTS = ("/.venv/", "/.git/", "__pycache__", "/build", "/docs/")


def _sources():
    for path in MODULES.rglob("*"):
        if path.suffix not in SOURCE_SUFFIXES or not path.is_file():
            continue
        posix = path.as_posix()
        if any(part in posix for part in SKIP_PARTS):
            continue
        yield path


def main() -> int:
    rep = Report("check_verifier_discoverability")
    rep.line("Ticked verifiers whose id appears in no source file")

    plan = PLAN.read_text(encoding="utf-8", errors="replace")
    ticked: dict[str, bool] = {}
    for state, tid in DEFN_RE.findall(plan):
        ticked[tid] = ticked.get(tid, False) or (state == "x")
    done = {tid for tid, is_done in ticked.items() if is_done}

    blob = []
    scanned = 0
    for path in _sources():
        try:
            blob.append(path.read_text(encoding="utf-8", errors="replace"))
            scanned += 1
        except OSError:
            pass
    corpus = "\n".join(blob)
    present = set(re.findall(r"\b((?:UT|ST)-[A-E]\d+[a-z]?-\d+)\b", corpus))

    missing = sorted(done - present)

    rep.heading("Measured")
    rep.table(
        ["ticked ids", "source files scanned", "undiscoverable", "baseline"],
        [[len(done), scanned, len(missing), BASELINE]],
    )

    if missing:
        rep.line()
        rep.line("Ticked in the plan, id present in no source file:")
        for tid in missing:
            rep.line(f"    {tid}")
        rep.line()
        rep.line("Fix: put the id in the implementing test's docstring or name. Do NOT")
        rep.line("untick the box -- these are real, passing tests (AR-7's own finding);")
        rep.line("what is missing is the thread from the id back to the code.")

    rep.line()
    if len(missing) > BASELINE:
        rep.fail(
            f"{len(missing)} undiscoverable verifier(s), above the baseline of {BASELINE} -- "
            "a new one was introduced. Name the id where the test lives, or raise "
            "BASELINE with a written reason (it is a floor, like GT-4's)")
    elif len(missing) < BASELINE:
        rep.ok(f"{len(missing)} undiscoverable, BELOW the baseline of {BASELINE} -- "
               f"lower BASELINE to {len(missing)} in this same commit so the ratchet holds")
    else:
        rep.ok(f"{len(missing)} undiscoverable, exactly the declared baseline -- no growth")

    return rep.finish()


if __name__ == "__main__":
    sys.exit(main())
