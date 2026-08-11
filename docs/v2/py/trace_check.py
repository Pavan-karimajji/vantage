# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Traceability checker for the v2 document set (`SW-0372`, `IMP-0372`).

Closes the chain `CN -> SYS -> SW -> IMP -> WP -> test` **in both directions**
and refuses to let any link be asserted rather than checked.

Why this exists rather than a table someone maintains: `SW-0373` forbids storing
verification status by hand in a second place, and the same argument applies to
traceability. A trace matrix that is written down is a trace matrix that is wrong
the first time a requirement moves. This reads the documents.

Run it before any commit to `docs/v2/`:

    python docs/v2/py/trace_check.py            # full check, non-zero exit on failure
    python docs/v2/py/trace_check.py --progress # work-package checkbox counts
    python docs/v2/py/trace_check.py --matrix   # emit the derived trace matrix

**Known-gap handling.** SwReq §32.3 records five `SW` requirements with no `SYS`
parent. They are *reported as known*, never passed silently -- passing them would
hide the fact that the system boundary is under-described. They are listed in
`KNOWN_UNPARENTED` and a requirement leaving that list without gaining a parent
is a failure, as is a requirement in the list that has since gained one.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

V2 = Path(__file__).resolve().parent.parent

CONCEPT = V2 / "SIM_Concept_Document_v0.3.1.md"
SYSREQ = V2 / "SIM_System_Requirements_v0.1.md"
SWREQ = V2 / "SIM_Software_Requirements_v0.1.md"
DESIGN = V2 / "SIM_Implementation_Design_v0.1.md"
PLAN = V2 / "SIM_Implementation_Plan_v0.1.md"
TESTSPEC = V2 / "SIM_Software_Test_Spec_v0.1.md"

# SwReq section 32.3 -- unparented by finding, not by oversight.
KNOWN_UNPARENTED = {"SW-0060", "SW-0196", "SW-0199"}

TEST_ID = re.compile(r"\b(UT-[A-Z]+-\d+|IT-\d+|ANL-SW-\d+|INSP-SW-\d+)\b")


@dataclass
class Sw:
    uid: str
    item: str
    trace: set[str] = field(default_factory=set)
    tests: set[str] = field(default_factory=set)
    accept: str = ""


@dataclass
class Imp:
    uid: str
    serves: str
    wp: str
    change: str
    tests: set[str] = field(default_factory=set)


def _read(p: Path) -> str:
    if not p.exists():
        sys.exit(f"missing document: {p}")
    return p.read_text(encoding="utf-8")


def parse_uids(text: str, prefix: str) -> set[str]:
    # The negative look-behind matters: without it `ANL-SW-01` yields a bogus
    # `SW-01`, and `INSP-SW-nn` likewise. A checker that invents identifiers is
    # worse than no checker.
    return set(re.findall(rf"(?<![A-Za-z-])({prefix}-\d+)\b", text))


def parse_sw(text: str) -> dict[str, Sw]:
    """Requirements are `**\\`SW-nnnn\\`** ... ` blocks with Trace/Verify/Accept lines."""
    out: dict[str, Sw] = {}
    blocks = re.split(r"^\*\*`(SW-\d+)`\*\*", text, flags=re.M)
    # blocks[0] is preamble; then alternating uid, body
    for uid, body in zip(blocks[1::2], blocks[2::2]):
        item = ""
        m = re.match(r"\s*·\s*`(SI-\d+)`", body)
        if m:
            item = m.group(1)
        acc = re.search(r"\*\*Accept\.\*\*\s*(.*?)(?=\n\*\*|\Z)", body, re.S)
        ver = re.search(r"\*\*Verify\.\*\*(.*?)(?=\*\*Trace\.\*\*|\Z)", body, re.S)
        tra = re.search(r"\*\*Trace\.\*\*\s*(.*?)$", body, re.M)
        out[uid] = Sw(
            uid=uid,
            item=item,
            trace=set(re.findall(r"\b(SYS-\d+)\b", tra.group(1))) if tra else set(),
            tests=set(TEST_ID.findall(ver.group(1))) if ver else set(),
            accept=" ".join(acc.group(1).split()) if acc else "",
        )
    return out


IMP_ROW = re.compile(
    r"^\| `(IMP-\d+)` \| `(SW-\d+)` \| (?:`(WP-\d+)`|—) \| `(\w+)` \| (.*?) \| (.*?) \|\s*$",
    re.M,
)


def parse_imp(text: str) -> dict[str, Imp]:
    out: dict[str, Imp] = {}
    for uid, serves, wp, change, _art, tests in IMP_ROW.findall(text):
        out[uid] = Imp(
            uid=uid,
            serves=serves,
            wp=wp or "",
            change=change,
            tests=set(TEST_ID.findall(tests)),
        )
    return out


def parse_plan(text: str) -> tuple[dict[str, set[str]], dict[str, bool]]:
    """Return (wp -> IMP ids it claims to land, wp -> all-boxes-ticked)."""
    lands: dict[str, set[str]] = defaultdict(set)
    ticked: dict[str, bool] = {}
    current = ""
    for line in text.split("\n"):
        h = re.match(r"^### (WP-\d+) ", line)
        if h:
            current = h.group(1)
            ticked.setdefault(current, True)
            continue
        if not current:
            continue
        box = re.match(r"^\s*- \[( |x)\] ", line)
        if box:
            if box.group(1) != "x":
                ticked[current] = False
            if "**Lands:**" in line:
                lands[current] |= set(re.findall(r"\b(IMP-\d+)\b", line))
                # ranges written `IMP-0021`…`IMP-0027` are expanded by the caller
                for a, b in re.findall(r"`(IMP-\d+)`…`(IMP-\d+)`", line):
                    for n in range(int(a[4:]), int(b[4:]) + 1):
                        lands[current].add(f"IMP-{n:04d}")
    return lands, ticked


def parse_testspec(text: str) -> set[str]:
    """Test ids appearing in an ID column of the specification's tables."""
    return {m.group(1) for m in re.finditer(r"^\| `(" + TEST_ID.pattern[2:-2] + r")`", text, re.M)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--progress", action="store_true", help="work-package checkbox counts")
    ap.add_argument("--matrix", action="store_true", help="emit the derived trace matrix")
    args = ap.parse_args()

    cn_text, sys_text = _read(CONCEPT), _read(SYSREQ)
    sw_text, imp_text = _read(SWREQ), _read(DESIGN)
    plan_text, test_text = _read(PLAN), _read(TESTSPEC)

    cn = parse_uids(cn_text, "CN")
    sysr = parse_uids(sys_text, "SYS")
    sw = parse_sw(sw_text)
    imp = parse_imp(imp_text)
    lands, ticked = parse_plan(plan_text)
    spec_tests = parse_testspec(test_text)

    fails: list[str] = []
    notes: list[str] = []

    def bad(msg: str) -> None:
        fails.append(msg)

    # ---- 1. SW -> SYS ----------------------------------------------------
    for uid, r in sorted(sw.items()):
        unknown = r.trace - sysr
        if unknown:
            bad(f"{uid}: traces to non-existent {sorted(unknown)}")
        if not r.trace:
            if uid in KNOWN_UNPARENTED:
                notes.append(f"{uid}: unparented -- KNOWN (SwReq 32.3)")
            else:
                bad(f"{uid}: no SYS parent and not in KNOWN_UNPARENTED")
    for uid in sorted(KNOWN_UNPARENTED):
        if uid in sw and sw[uid].trace:
            bad(f"{uid}: listed as a known gap but now has a SYS parent -- update the list")

    # ---- 2. SW falsifiability (SV-1, ANL-SW-74) --------------------------
    for uid, r in sorted(sw.items()):
        if not r.accept:
            bad(f"{uid}: no Accept clause -- a motivation, not a requirement")
        if not r.tests:
            bad(f"{uid}: cites no test identifier")

    # ---- 3. SW <-> IMP ---------------------------------------------------
    served = defaultdict(list)
    for i in imp.values():
        served[i.serves].append(i.uid)
    for uid in sorted(sw):
        if uid not in served:
            bad(f"{uid}: no IMP design requirement serves it")
    for i in sorted(imp.values(), key=lambda x: x.uid):
        if i.serves not in sw:
            bad(f"{i.uid}: serves non-existent {i.serves}")

    # ---- 4. IMP test column matches the SW's own citations ---------------
    for i in sorted(imp.values(), key=lambda x: x.uid):
        if i.serves in sw and i.tests != sw[i.serves].tests:
            bad(
                f"{i.uid}: test column {sorted(i.tests)} != {i.serves}'s own "
                f"{sorted(sw[i.serves].tests)}"
            )

    # ---- 5. IMP -> WP ----------------------------------------------------
    plan_wps = set(ticked)
    for i in sorted(imp.values(), key=lambda x: x.uid):
        if not i.wp:
            notes.append(f"{i.uid}: no work package (deferred with its parent)")
        elif i.wp not in plan_wps:
            bad(f"{i.uid}: assigned to {i.wp}, which the plan does not define")
    for wp, claimed in sorted(lands.items()):
        for c in sorted(claimed):
            if c not in imp:
                bad(f"{wp}: claims to land non-existent {c}")
            elif imp[c].wp != wp:
                bad(f"{wp}: claims {c}, but the design assigns it to {imp[c].wp or '(none)'}")

    # ---- 6. tests: cited <-> specified -----------------------------------
    cited: set[str] = set()
    for r in sw.values():
        cited |= r.tests
    for t in sorted(cited - spec_tests):
        bad(f"{t}: cited by a requirement but absent from the Test Specification")
    for t in sorted(spec_tests - cited):
        bad(f"{t}: specified as a test but cited by no requirement")

    # ---- 7. no invented ids anywhere in the derived documents ------------
    for name, text in (("design", imp_text), ("plan", plan_text), ("test spec", test_text)):
        for t in sorted(set(TEST_ID.findall(text)) - cited):
            bad(f"{name}: references test id {t}, which no requirement cites")
        for c in sorted(parse_uids(text, "CN") - cn):
            bad(f"{name}: references non-existent {c}")
        for s in sorted(parse_uids(text, "SYS") - sysr):
            bad(f"{name}: references non-existent {s}")
        for s in sorted(parse_uids(text, "SW") - set(sw)):
            bad(f"{name}: references non-existent {s}")
        for s in sorted(parse_uids(text, "IMP") - set(imp)):
            bad(f"{name}: references non-existent {s}")
        for w in sorted(set(re.findall(r"(?<![A-Za-z-])(WP-\d+)\b", text)) - plan_wps):
            bad(f"{name}: references non-existent work package {w}")

    # ---- report ----------------------------------------------------------
    print("=" * 72)
    print("  SIM v2 traceability")
    print("=" * 72)
    print(f"  CN concept UIDs          {len(cn):5d}")
    print(f"  SYS requirements         {len(sysr):5d}")
    print(f"  SW requirements          {len(sw):5d}")
    print(f"  IMP design requirements  {len(imp):5d}")
    print(f"  WP work packages         {len(plan_wps):5d}")
    print(f"  test identifiers         {len(cited):5d}  (specified {len(spec_tests)})")
    print()
    print(f"  SW covered by an IMP     {len(served):5d} / {len(sw)}")
    print(f"  SW with a SYS parent     {sum(1 for r in sw.values() if r.trace):5d} / {len(sw)}")
    print(f"  known unparented         {len(KNOWN_UNPARENTED):5d}  (SwReq 32.3)")

    if args.progress:
        print()
        print("  work packages")
        done = sum(1 for v in ticked.values() if v)
        for wp in sorted(plan_wps):
            n = sum(1 for i in imp.values() if i.wp == wp)
            print(f"    [{'x' if ticked[wp] else ' '}] {wp}  {n:3d} IMP")
        print(f"    ticked {done} / {len(plan_wps)}")
        print("    (counts boxes; makes no verification claim -- Plan 0.4)")

    if args.matrix:
        print()
        print("  SW,SI,SYS,IMP,WP,change,tests")
        for uid in sorted(sw):
            for i in served.get(uid, []):
                o = imp[i]
                print(
                    f"  {uid},{sw[uid].item},"
                    f"{'|'.join(sorted(sw[uid].trace)) or '-'},"
                    f"{i},{o.wp or '-'},{o.change},"
                    f"{'|'.join(sorted(sw[uid].tests))}"
                )

    if notes:
        print()
        print(f"  notes ({len(notes)}):")
        for n in notes:
            print(f"    - {n}")

    print()
    if fails:
        print(f"  FAIL -- {len(fails)} problem(s):")
        for f in fails:
            print(f"    x {f}")
        return 1
    print("  PASS -- the chain closes in both directions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
