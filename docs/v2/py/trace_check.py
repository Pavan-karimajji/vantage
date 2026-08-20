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

    python docs/v2/py/trace_check.py                # full check, non-zero exit on failure
    python docs/v2/py/trace_check.py --status       # progress per layer, and the next WP
    python docs/v2/py/trace_check.py --write-status # regenerate the `**Built.**` lines
    python docs/v2/py/trace_check.py --progress     # work-package checkbox counts
    python docs/v2/py/trace_check.py --counts       # the Test Specification's own totals
    python docs/v2/py/trace_check.py --matrix       # emit the derived trace matrix
    python docs/v2/py/trace_check.py --exec-rows all  # Test Execution Record skeleton

**Progress, and why it is written into the requirement documents at all**
(`R-REQ-6a`, `CN-0403`, added 2026-08-13). *"Has this been verified?"* and *"has
this been built yet?"* are different questions, and the second is what a session
resuming tomorrow asks. No suite answers it: a test that has never run and a test
for code nobody has written are indistinguishable in a suite.

So the plan's per-`IMP` checkboxes are the **single** stored progress state, and
`SW`, `SYS` and `CN` marks are *rolled up* from them by `roll_up` and written by
`--write-status`. The ordinary run **recomputes every mark and fails on
disagreement**, which is the half that separates this from the hand-kept status
column `R-REQ-6` forbids -- v1's register read `frozen` on 68 of 77 rows because
nobody updated it and nothing checked it. `R-REQ-11`'s principle, in its own
words: the copy is made safe by checking it, not by deleting it.

Three box states (`[x]`, `[ ]`, `[~]`), and `[~]` must say `closed by <what>`.
Two marks are deliberately not progress and are never coloured as such:
`deferred` (no work package) and `orphan` (nothing decomposes it -- a finding
about the decomposition, which is how `SYS-0109` and `SYS-0257` were found).

**Scan-path handling.** An analysis check that names a directory which does not
exist scans nothing and therefore *passes*, which is indistinguishable from a
check that scanned everything -- right up to the day it should have failed. The
Test Specification's scan column is therefore checked against the Design's target
tree, so a superseded or misspelt path is a failure here rather than a silence
later.

**Counts.** The Test Specification quotes no totals; they are emitted by
`--counts`. A number derivable from the documents is a second stored copy, and a
second copy drifts whether it holds a status or a total.

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

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

V2 = Path(__file__).resolve().parent.parent

CONCEPT = V2 / "SIM_Concept_Document_v0.3.1.md"
SYSREQ = V2 / "SIM_System_Requirements_v0.1.md"
SWREQ = V2 / "SIM_Software_Requirements_v0.1.md"
DESIGN = V2 / "SIM_Implementation_Design_v0.1.md"
PLAN = V2 / "SIM_Implementation_Plan_v0.1.md"
TESTSPEC = V2 / "SIM_Software_Test_Spec_v0.1.md"
SYSTESTSPEC = V2 / "SIM_System_Test_Spec_v0.1.md"
CNTESTSPEC = V2 / "SIM_Concept_Test_Spec_v0.1.md"

# SwReq section 32.3 -- unparented by finding, not by oversight.
KNOWN_UNPARENTED = {"SW-0060", "SW-0196", "SW-0199"}

# The mirror gap, found 2026-08-13 by the status rollup on its first run: system
# requirements no software requirement decomposes. Their progress is therefore
# not merely zero, it is *unknowable* -- there is nothing under them to tick.
# Listed rather than failed for the same reason as KNOWN_UNPARENTED: a gate that
# is red before any work starts is a gate nobody can act on. The list is checked
# in both directions, so a requirement cannot leave it silently and one that
# gains a decomposition cannot stay.
KNOWN_UNDECOMPOSED = {"SYS-0109", "SYS-0257"}
# SYS-0025 was here 2026-08-20..2026-08-20: SW-0312 (SI-19, superseded to
# `viz`) was its sole decomposer, found live while executing SM-01's SI-19
# slice. Closed same day by SW-0420 (SI-02 -- the port catalogue's own item,
# not the scene's), which states the semantic-versioning rule SYS-0025 asks
# for and traces to it directly. Left out of the set rather than re-added
# with a strikethrough, matching KNOWN_UNPARENTED's own convention of no
# historical entries -- the finding is recorded in SW-0420's own `Now.` note
# and in VIZ_Sync_Plan_v0.1.md instead.

TEST_ID = re.compile(r"\b(UT-[A-Z]+-\d+|IT-\d+|ANL-SW-\d+|INSP-SW-\d+)\b")

# The system and concept levels. `ANL-SW-nn`/`INSP-SW-nn` are the *software*
# level and must not be swept up here, hence the `(?!SW-)` -- without it every
# software analysis check would be read as a system one and the two levels'
# coverage figures would both be wrong, in opposite directions.
SYS_TEST_ID = re.compile(r"\b(SYT-[A-Z]{3}-\d+|ANL-(?!SW-)\d+|INSP-(?!SW-)\d+)\b")
CN_TEST_ID = re.compile(r"\b(CT-\d+|E2E-\d+)\b")

# `E2E-*` is cited by SYS requirements but specified one level up, in the
# Concept Test Specification (SysReq 0.5). A checker that did not know this
# would report all twelve as uncited or unspecified depending on which
# document it read first.
CONCEPT_LEVEL = CN_TEST_ID


@dataclass
class Sw:
    uid: str
    item: str
    trace: set[str] = field(default_factory=set)
    tests: set[str] = field(default_factory=set)
    accept: str = ""


@dataclass
class SysR:
    uid: str
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


def parse_sys(text: str) -> dict[str, SysR]:
    """`**\\`SYS-nnnn\\`** ... ` blocks, same anatomy as SW one layer up."""
    out: dict[str, SysR] = {}
    blocks = re.split(r"^\*\*`(SYS-\d+)`\*\*", text, flags=re.M)
    for uid, body in zip(blocks[1::2], blocks[2::2]):
        acc = re.search(r"\*\*Accept\.\*\*\s*(.*?)(?=\n\*\*|\Z)", body, re.S)
        ver = re.search(r"\*\*Verify\.\*\*(.*?)(?=\*\*Trace\.\*\*|\Z)", body, re.S)
        tra = re.search(r"\*\*Trace\.\*\*\s*(.*?)$", body, re.M)
        vtext = ver.group(1) if ver else ""
        out[uid] = SysR(
            uid=uid,
            trace=set(re.findall(r"\b(CN-\d+)\b", tra.group(1))) if tra else set(),
            tests=set(SYS_TEST_ID.findall(vtext)) | set(CN_TEST_ID.findall(vtext)),
            accept=" ".join(acc.group(1).split()) if acc else "",
        )
    return out


def parse_spec_ids(text: str, pattern: re.Pattern[str]) -> set[str]:
    """Ids in an ID column of a specification's tables.

    Anchored to the column so that a test *mentioned* in prose is not mistaken
    for one *specified* here -- the distinction the cited-vs-specified check in
    section 6 depends on.
    """
    out: set[str] = set()
    for line in text.split("\n"):
        m = re.match(r"^\| `([A-Za-z0-9-]+)`", line)
        if m and pattern.fullmatch(m.group(1)):
            out.add(m.group(1))
    return out


# A range wider than this is a typo, not a range. The widest real one is
# `SYS-0220`…`SYS-0229` in E2E-09.
RANGE_MAX = 60


def parse_serves(
    text: str, test_pat: re.Pattern[str], prefix: str
) -> tuple[dict[str, set[str]], list[str]]:
    """test id -> the requirement UIDs its own row names, plus malformed ranges.

    This is the **downward** half of the trace. The upward half (a requirement's
    `Verify` clause naming a test) was already checked; without this, the two are
    independent statements of one fact and nothing forces them to agree -- a row
    can claim to serve one requirement while that requirement cites a different
    test, and both documents pass inspection separately.

    The requirement column sits second, beside the id. It is used **alone** when
    it names any requirement of this layer, because a `Steps` or `Cases` cell
    legitimately mentions other requirements in prose (`SYT-OUT-05` cites
    `SYS-0029` in its steps) and sweeping the whole row would read those as
    claims. Rows that name their requirements in a later column instead -- `E2E`
    uses `Exercises` -- have no UID beside the id, and only those fall back to
    the whole row.
    """
    out: dict[str, set[str]] = defaultdict(set)
    bad_ranges: list[str] = []
    uid_re = re.compile(rf"\b({prefix}-\d+)\b")
    for line in text.split("\n"):
        m = re.match(r"^\| `([A-Za-z0-9-]+)` \|(.*)$", line)
        if not m or not test_pat.fullmatch(m.group(1)):
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        scope = cells[0] if cells and uid_re.search(cells[0]) else m.group(2)
        uids = set(uid_re.findall(scope))
        # `SYS-0001`…`SYS-0022` -- a range, as E2E's Exercises column writes it.
        # Bounded: a typo'd endpoint would otherwise expand into thousands of
        # invented UIDs and bury the real message in its own error text. A range
        # wider than the span is a malformed range, and saying so is the useful
        # report -- listing 9,000 non-existent requirements is not.
        for a, b in re.findall(rf"`{prefix}-(\d+)`…`{prefix}-(\d+)`", scope):
            lo, hi = int(a), int(b)
            if hi < lo or hi - lo > RANGE_MAX:
                bad_ranges.append(f"{m.group(1)}: malformed range {prefix}-{a}…{prefix}-{b}")
                continue
            for n in range(lo, hi + 1):
                uids.add(f"{prefix}-{n:0{len(a)}d}")
        out[m.group(1)] |= uids
    return out, bad_ranges


def parse_principles(concept_text: str) -> dict[str, set[str]]:
    """Concept section 4's principles -> the `CT-*` its `Validated by` column names.

    `CN-0380` makes these acceptance criteria for the product as a whole rather
    than individual requirements, so they are the part of the concept the Concept
    Test Specification owes complete coverage of. The column is the **downward**
    half of that link (`CN-0399`); the test spec's `Asserts` column is the upward
    half, and the two are checked against each other.

    `CN-0016` is carried too: it is the stated main measure of success and is
    validated by `CT-15`, but it lives in section 2.2 and is declared in section
    4's prose rather than as a column in a table whose other rows have no
    validation test.
    """
    block = re.search(r"^# 4\. Design principles\n(.*?)^# ", concept_text, re.S | re.M)
    if not block:
        return {}
    out: dict[str, set[str]] = {}
    for line in block.group(1).split("\n"):
        m = re.match(r"^\|\s*[\d.]+\s*\|\s*(CN-\d+)\s*\|", line)
        if m:
            out[m.group(1)] = set(re.findall(r"`(CT-\d+)`", line))
    prose = re.findall(r"`(CN-\d+)`[^*`]*is validated by `(CT-\d+)`", block.group(1))
    if not prose:
        # Stated rather than inferred: this parser has two halves and the prose
        # half matched nothing, which is indistinguishable from "there is none"
        # right up until it matters. The concept declares CN-0016 here.
        raise ValueError("section 4 prose declares no `CN-nnnn is validated by CT-nn` link")
    for uid, ct in prose:
        out.setdefault(uid, set()).add(ct)
    return out


def check_falsifiable(sw: dict[str, Sw]) -> list[str]:
    """IMP-0408 / ANL-SW-74 / SV-1: every SW requirement has a non-empty
    `Accept` and cites at least one test id -- a requirement with neither
    is a motivation, reported rather than passed silently."""
    findings: list[str] = []
    for uid, r in sorted(sw.items()):
        if not r.accept:
            findings.append(f"{uid}: no Accept clause -- a motivation, not a requirement")
        if not r.tests:
            findings.append(f"{uid}: cites no test identifier")
    return findings


def duplicate_test_ids(reqs: dict[str, SysR]) -> dict[str, list[str]]:
    """Test ids claimed by more than one requirement (`TV-7`, `R-REQ-2`).

    Six of these entered the System Requirements when late-added requirements
    took the next number *local to their subsection* rather than the highest in
    the document. The symptom is silent: two unrelated requirements appear
    verified by one test, and whichever is written second is effectively
    unverified. `E2E-*` is exempt -- one scenario is deliberately the acceptance
    vehicle for several requirements, and those requirements' Accept clauses say
    so literally.
    """
    claims: dict[str, list[str]] = defaultdict(list)
    for uid, r in sorted(reqs.items()):
        for t in sorted(r.tests):
            if not CONCEPT_LEVEL.fullmatch(t):
                claims[t].append(uid)
    return {t: us for t, us in claims.items() if len(us) > 1}


# A work package may carry a letter suffix: a package inserted after the
# numbering is fixed is lettered rather than renumbered, so that the plan's
# "lowest-numbered unticked package" rule keeps pointing at the right work
# (Plan 0.3). A checker that did not know this would read `WP-15a` as
# `WP-15` and silently mis-assign every requirement the new package lands.
WP_ID = r"WP-\d+[a-z]?"

IMP_ROW = re.compile(
    r"^\| `(IMP-\d+)` \| `(SW-\d+)` \| (?:`(" + WP_ID + r")`|—) \| `(\w+)` \| (.*?) \| (.*?) \|\s*$",
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


# The three box states (Plan 0.4). `~` is *started, a stated part complete*, and
# it had to enter this regex on the same day it entered the document: while the
# class was `[ x]` a `~` matched nothing, so a package whose every other box was
# ticked reported **ticked** while carrying unfinished work. A third state in the
# prose alone makes the progress count confidently wrong.
BOX = re.compile(r"^(\s*)- \[([ x~])\] (.*)$")

# A per-IMP box under a package's `Lands:` line: `  - [ ] \`IMP-0020\` · ...`
IMP_BOX = re.compile(r"^\s+- \[([ x~])\] `(IMP-\d+)`(.*)$")

DONE, PARTIAL, OPEN, DEFERRED, ORPHAN = "done", "partial", "open", "deferred", "orphan"
_STATE = {"x": DONE, "~": PARTIAL, " ": OPEN}


def parse_plan(
    text: str,
) -> tuple[dict[str, set[str]], dict[str, bool], dict[str, str], list[str]]:
    """Return (wp -> IMP ids claimed, wp -> all-ticked, IMP -> state, findings).

    The third value is the **only** hand-maintained progress state in the
    document set (Plan 0.5); `SW`, `SYS` and `CN` marks are rolled up from it and
    never typed. The fourth is the caveat check: a `[~]` whose text says nothing
    beyond the identifier records that somebody was unsure, not where to resume,
    so it is a finding rather than a state.
    """
    lands: dict[str, set[str]] = defaultdict(set)
    ticked: dict[str, bool] = {}
    imp_state: dict[str, str] = {}
    findings: list[str] = []
    current = ""
    for line in text.split("\n"):
        h = re.match(r"^### (" + WP_ID + r") ", line)
        if h:
            current = h.group(1)
            ticked.setdefault(current, True)
            continue
        if not current:
            continue
        box = BOX.match(line)
        if not box:
            continue
        mark, body = box.group(2), box.group(3)
        if mark != "x":
            ticked[current] = False
        ib = IMP_BOX.match(line)
        if ib:
            uid = ib.group(2)
            if uid in imp_state:
                findings.append(f"{uid}: has more than one checkbox in the plan")
            imp_state[uid] = _STATE[mark]
            # Plan 0.4: the value of `~` is entirely in the caveat, so the caveat
            # is required *positively* -- the line must say `closed by <what>`.
            # Measuring "is there extra text?" cannot work here: the generated
            # stem already carries an artifact hint, so any length or
            # difference test would accept a bare `[~]` on a long row and reject
            # a terse caveat on a short one. A required token is exact, and it
            # forces the one thing that makes the state useful to the next
            # session -- what closes it.
            if mark == "~" and "closed by" not in ib.group(3).lower():
                findings.append(
                    f"{uid}: `[~]` must say `closed by <command or condition>` (Plan 0.4)"
                )
            continue
        if "**Lands:**" in body:
            lands[current] |= set(re.findall(r"\b(IMP-\d+)\b", line))
            # ranges written `IMP-0021`…`IMP-0027` are expanded by the caller
            for a, b in re.findall(r"`(IMP-\d+)`…`(IMP-\d+)`", line):
                for n in range(int(a[4:]), int(b[4:]) + 1):
                    lands[current].add(f"IMP-{n:04d}")
    return lands, ticked, imp_state, findings


def roll_up(
    imp: dict[str, Imp],
    sw: dict[str, Sw],
    sysreqs: dict[str, SysR],
    imp_state: dict[str, str],
) -> tuple[dict[str, str], dict[str, str], dict[str, str], list[str]]:
    """Roll the plan's per-IMP boxes up the chain: IMP -> SW -> SYS -> CN.

    One stored source, three derived layers (Plan 0.5). The rule at every level
    is the same and is deliberately pessimistic: **done only when every child is
    done**, partial when any child has started, open otherwise. A parent that
    reported done while a child was open would be the one failure that makes a
    progress display worth less than none.

    Two shapes are *not* progress and must never be coloured as such:
    `DEFERRED` -- an IMP with no work package, deferred with its parent -- and
    `ORPHAN` -- a requirement with no child at all, which is a gap in the
    decomposition and is returned as a finding rather than as a status.
    """
    findings: list[str] = []

    def combine(children: list[str]) -> str:
        real = [c for c in children if c != DEFERRED]
        if not real:
            return DEFERRED if children else ORPHAN
        if all(c == DONE for c in real):
            return DONE
        if any(c in (DONE, PARTIAL) for c in real):
            return PARTIAL
        return OPEN

    imp_st: dict[str, str] = {}
    for uid, o in imp.items():
        if not o.wp:
            imp_st[uid] = DEFERRED
        elif uid in imp_state:
            imp_st[uid] = imp_state[uid]
        else:
            imp_st[uid] = OPEN
            findings.append(f"{uid}: assigned to {o.wp} but has no checkbox there")

    # IMP -> SW is 1:1 across all 417 rows, so this aggregation is a lookup
    # today. It is written as an aggregation anyway: the day one SW gains a
    # second IMP, a lookup would silently report the first one's state.
    by_sw: dict[str, list[str]] = defaultdict(list)
    for uid, o in imp.items():
        by_sw[o.serves].append(imp_st[uid])
    sw_st = {u: combine(by_sw.get(u, [])) for u in sw}

    by_sys: dict[str, list[str]] = defaultdict(list)
    for u, r in sw.items():
        for parent in r.trace:
            by_sys[parent].append(sw_st[u])
    sys_st = {u: combine(by_sys.get(u, [])) for u in sysreqs}

    by_cn: dict[str, list[str]] = defaultdict(list)
    for u, r in sysreqs.items():
        for parent in r.trace:
            by_cn[parent].append(sys_st[u])
    cn_st = {u: combine(v) for u, v in by_cn.items()}

    return imp_st, sw_st, sys_st, findings


GLYPH = {DONE: "●", PARTIAL: "◐", OPEN: "○", DEFERRED: "◌", ORPHAN: "⚠"}
WORD = {
    DONE: "done",
    PARTIAL: "started",
    OPEN: "not started",
    DEFERRED: "deferred",
    ORPHAN: "unknowable",
}

BUILT = re.compile(r"^\*\*Built\.\*\* ")


def built_line_sw(uid: str, sw_st: dict[str, str], imp: dict[str, Imp]) -> str:
    """The generated `**Built.**` line for one software requirement."""
    st = sw_st[uid]
    rows = sorted((o for o in imp.values() if o.serves == uid), key=lambda o: o.uid)
    where = ", ".join(f"`{o.uid}` in `{o.wp}`" if o.wp else f"`{o.uid}` (no package)" for o in rows)
    return f"**Built.** {GLYPH[st]} {WORD[st]} — {where or 'no design requirement serves it'}"


def built_line_sys(uid: str, sys_st: dict[str, str], kids: dict[str, list[str]], wps: dict[str, set[str]]) -> str:
    """The generated `**Built.**` line for one system requirement."""
    st = sys_st[uid]
    if st == ORPHAN:
        return "**Built.** ⚠ unknowable — no software requirement decomposes this (finding)"
    child = kids.get(uid, [])
    done = sum(1 for c in child if c == DONE)
    pkgs = ", ".join(f"`{w}`" for w in sorted(wps.get(uid, ())))
    tail = f", in {pkgs}" if pkgs and st != DONE else ""
    return f"**Built.** {GLYPH[st]} {WORD[st]} — {done}/{len(child)} software requirements done{tail}"


def apply_built(text: str, prefix: str, line_for) -> str:
    """Rewrite every `**Built.**` line in a requirement document.

    Idempotent by construction: the old line is dropped and a fresh one inserted
    after `**Trace.**`, so running this twice is the same as running it once.
    Placed beside `Verify`/`Trace` rather than at the end of the block because
    that is where a reader already looks for "how do I know", and because a
    trailing field drifts under later `*Note:*` additions.
    """
    out: list[str] = []
    current = ""
    fenced = False
    head = re.compile(r"^\*\*`(" + prefix + r"-\d+)`\*\*")
    for line in text.split("\n"):
        # A fenced block is prose *about* the field -- section 0.3a shows a
        # specimen line. Rewriting inside one would eat the documentation of the
        # thing being generated, which is how this function broke the first time
        # it ran against its own explanation.
        if line.startswith("```"):
            fenced = not fenced
            out.append(line)
            continue
        if fenced:
            out.append(line)
            continue
        m = head.match(line)
        if m:
            current = m.group(1)
        if BUILT.match(line):
            continue  # regenerated below
        out.append(line)
        if current and "**Trace.**" in line:
            out.append(line_for(current))
            current = ""
    return "\n".join(out)


def read_built(text: str, prefix: str) -> dict[str, str]:
    """The `**Built.**` lines a document currently carries, per requirement."""
    found: dict[str, str] = {}
    current = ""
    fenced = False
    head = re.compile(r"^\*\*`(" + prefix + r"-\d+)`\*\*")
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = head.match(line)
        if m:
            current = m.group(1)
        elif current and BUILT.match(line):
            found[current] = line.rstrip()
            current = ""
    return found


def parse_testspec(text: str) -> set[str]:
    """Test ids appearing in an ID column of the specification's tables."""
    return {m.group(1) for m in re.finditer(r"^\| `(" + TEST_ID.pattern[2:-2] + r")`", text, re.M)}


# A path a check scans, as written in the Test Specification: `src/simcore/**`,
# `adas_sim/graph/**`, `io/codecs/**`. Only the first segment is checked -- what
# matters is whether the check is pointed at a place the design says will exist.
SCAN_PATH = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)/[A-Za-z0-9_.*/]+`")

# Roots the target tree does not enumerate because they are not deliverables:
# the checks' own home, and the module root itself.
TREE_IMPLICIT = {"src", "modules"}


def parse_scan_paths(text: str) -> dict[str, set[str]]:
    """Return check id -> the root of every path its scan column names."""
    out: dict[str, set[str]] = defaultdict(set)
    for line in text.split("\n"):
        m = re.match(r"^\| `(ANL-SW-\d+)` \|[^|]*\|([^|]*)\|", line)
        if m:
            out[m.group(1)] |= set(SCAN_PATH.findall(m.group(2)))
    return out


def parse_tree_paths(design_text: str) -> set[str]:
    """Every directory name the Design's target tree (section 2.1) declares.

    Read as a set of names rather than as a nesting: the question a scan path
    asks is *does this place exist in the plan*, not *where does it sit*. The
    tree writes siblings on one line (`io/  bus/  scheduler/`), so the whole
    block is scanned rather than one name per line.
    """
    block = re.search(r"### 2\.1 The tree.*?```\n(.*?)```", design_text, re.S)
    if not block:
        return set()
    return set(re.findall(r"([A-Za-z_][A-Za-z0-9_.]*)/", block.group(1))) | TREE_IMPLICIT


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--progress", action="store_true", help="work-package checkbox counts")
    ap.add_argument("--counts", action="store_true", help="the Test Specification's own totals")
    ap.add_argument("--matrix", action="store_true", help="emit the derived trace matrix")
    ap.add_argument(
        "--exec-rows",
        metavar="LEVEL",
        choices=("system", "concept", "software", "all"),
        help="emit Test Execution Record rows for a level, all Not Run",
    )
    ap.add_argument("--status", action="store_true", help="progress per layer, and the next work package")
    ap.add_argument(
        "--write-status",
        action="store_true",
        help="regenerate every `**Built.**` line from the plan's checkboxes (idempotent)",
    )
    args = ap.parse_args()

    cn_text, sys_text = _read(CONCEPT), _read(SYSREQ)
    sw_text, imp_text = _read(SWREQ), _read(DESIGN)
    plan_text, test_text = _read(PLAN), _read(TESTSPEC)
    systest_text, cntest_text = _read(SYSTESTSPEC), _read(CNTESTSPEC)

    cn = parse_uids(cn_text, "CN")
    sysr = parse_uids(sys_text, "SYS")
    sysreqs = parse_sys(sys_text)
    sw = parse_sw(sw_text)
    imp = parse_imp(imp_text)
    lands, ticked, imp_boxes, box_findings = parse_plan(plan_text)
    spec_tests = parse_testspec(test_text)
    sys_spec_tests = parse_spec_ids(systest_text, SYS_TEST_ID)
    cn_spec_tests = parse_spec_ids(cntest_text, CN_TEST_ID)

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

    # ---- 2. SW falsifiability (SV-1, ANL-SW-74, IMP-0408) -----------------
    for msg in check_falsifiable(sw):
        bad(msg)

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
        for w in sorted(set(re.findall(r"(?<![A-Za-z-])(" + WP_ID + r")(?![\w-])", text)) - plan_wps):
            bad(f"{name}: references non-existent work package {w}")

    # ---- 7a. SYS -> CN, and SYS falsifiability (ANL-50, ANL-53) ----------
    for uid, r in sorted(sysreqs.items()):
        unknown = r.trace - cn
        if unknown:
            bad(f"{uid}: traces to non-existent {sorted(unknown)}")
        if not r.trace:
            bad(f"{uid}: no CN parent (ANL-53)")
        if not r.accept:
            bad(f"{uid}: no Accept clause -- a motivation, not a requirement (ANL-50)")
        if not r.tests:
            bad(f"{uid}: cites no test identifier (ANL-50)")

    # ---- 7b. no test identifier is claimed twice (TV-7, R-REQ-2) ---------
    # The check that would have caught the six duplicates found while writing
    # the System Test Specification, on the day they were introduced.
    for t, owners in sorted(duplicate_test_ids(sysreqs).items()):
        bad(f"{t}: claimed by {len(owners)} requirements {owners} -- ids are allocated once (R-REQ-2)")

    # ---- 7c. system + concept tests: cited <-> specified ------------------
    sys_cited: set[str] = set()
    cn_cited: set[str] = set()
    for r in sysreqs.values():
        for t in r.tests:
            (cn_cited if CONCEPT_LEVEL.fullmatch(t) else sys_cited).add(t)
    for t in sorted(sys_cited - sys_spec_tests):
        bad(f"{t}: cited by a SYS requirement but absent from the System Test Specification")
    for t in sorted(sys_spec_tests - sys_cited):
        bad(f"{t}: specified as a system test but cited by no requirement")
    # The Concept Test Specification also specifies CT-* rows, which assert a
    # CN principle rather than a SYS requirement -- so only the E2E half is
    # required to be SYS-cited.
    for t in sorted(cn_cited - cn_spec_tests):
        bad(f"{t}: cited by a SYS requirement but absent from the Concept Test Specification")

    # ---- 7d. the downward half: every test row's own requirement column ---
    # Checked against the upward half, in both directions, so the two cannot
    # drift apart while each looks correct on its own.
    def cross(level: str, serves: dict[str, set[str]], reqs: dict[str, set[str]], universe: set[str]) -> None:
        for tid, claimed in sorted(serves.items()):
            missing = claimed - universe
            if missing:
                bad(f"{level} {tid}: serves non-existent {sorted(missing)}")
            if not claimed:
                bad(f"{level} {tid}: names no requirement -- the downward link is absent")
            cites = {u for u in reqs if tid in reqs[u]}
            if claimed - cites:
                bad(f"{level} {tid}: claims to serve {sorted(claimed - cites)}, which do not cite it back")
            if cites - claimed:
                bad(f"{level} {tid}: cited by {sorted(cites - claimed)}, which its own row does not name")

    sys_verify = {u: r.tests for u, r in sysreqs.items()}
    sw_verify = {u: r.tests for u, r in sw.items()}
    sys_serves, r1 = parse_serves(systest_text, SYS_TEST_ID, "SYS")
    sw_serves, r2 = parse_serves(test_text, TEST_ID, "SW")
    cross("SYS", sys_serves, sys_verify, sysr)
    cross("SW", sw_serves, sw_verify, set(sw))

    # ---- 7e. CT -> CN, and every design principle covered (CN-0380) ------
    ct_pat = re.compile(r"CT-\d+")
    ct_asserts, r3 = parse_serves(cntest_text, ct_pat, "CN")
    principles = parse_principles(cn_text)
    if not principles:
        bad("could not read the concept's design principles -- the CT coverage check would pass on nothing")
    for tid, claimed in sorted(ct_asserts.items()):
        missing = claimed - cn
        if missing:
            bad(f"CT {tid}: asserts non-existent {sorted(missing)}")
        if not claimed:
            bad(f"CT {tid}: asserts no concept UID -- the upward link is absent")
    asserted = set().union(*ct_asserts.values()) if ct_asserts else set()
    for p in sorted(set(principles) - asserted):
        bad(f"{p}: a design principle no CT asserts (CN-0380)")

    # CN-0399: the concept's own `Validated by` column against the test spec's
    # `Asserts` column, both ways -- the same treatment SYS and SW already get.
    for uid, cts in sorted(principles.items()):
        if not cts:
            bad(f"{uid}: no `Validated by` entry -- the concept's downward link is absent (CN-0399)")
            continue
        for ct in sorted(cts - set(ct_asserts)):
            bad(f"{uid}: `Validated by` names {ct}, which the Concept Test Spec does not specify")
        for ct in sorted(ct for ct in cts if ct in ct_asserts and uid not in ct_asserts[ct]):
            bad(f"{uid}: `Validated by` names {ct}, which does not assert it back (CN-0399)")
    for ct, claimed in sorted(ct_asserts.items()):
        for uid in sorted(u for u in claimed if u in principles and ct not in principles[u]):
            bad(f"CT {ct}: asserts {uid}, whose `Validated by` column does not name it (CN-0399)")

    # E2E names the SYS requirements it is the acceptance vehicle for. Those
    # need only exist -- a scenario deliberately exercises a broader set than
    # the handful of requirements that cite it back, so no equality is imposed.
    e2e_serves, r4 = parse_serves(cntest_text, re.compile(r"E2E-\d+"), "SYS")
    for tid, claimed in sorted(e2e_serves.items()):
        missing = claimed - sysr
        if missing:
            bad(f"E2E {tid}: exercises non-existent {sorted(missing)}")
        if not claimed:
            bad(f"E2E {tid}: names no SYS requirement it exercises")

    for msg in r1 + r2 + r3 + r4:
        bad(msg)

    # ---- 7f. the status rollup, and the marks it writes -------------------
    # One stored source (the plan's per-IMP boxes), three derived layers, and
    # the derived halves are *checked* rather than trusted. This is R-REQ-11's
    # rule applied to progress: the copy is made safe by checking it, not by
    # deleting it -- which is what separates it from the hand-kept status column
    # R-REQ-6 forbids, and from v1's register that read `frozen` on 68 of 77.
    imp_st, sw_st, sys_st, roll_findings = roll_up(imp, sw, sysreqs, imp_boxes)
    for msg in box_findings + roll_findings:
        bad(msg)
    for uid in sorted(imp_boxes):
        if uid not in imp:
            bad(f"plan: checkbox for non-existent {uid}")

    # The undecomposed list, checked in both directions like KNOWN_UNPARENTED.
    for uid in sorted(sysreqs):
        if sys_st[uid] == ORPHAN:
            if uid in KNOWN_UNDECOMPOSED:
                notes.append(f"{uid}: no SW decomposes it -- KNOWN (SwReq 32.3a)")
            else:
                bad(f"{uid}: no SW requirement decomposes it and it is not a known gap")
    for uid in sorted(KNOWN_UNDECOMPOSED):
        if uid in sys_st and sys_st[uid] != ORPHAN:
            bad(f"{uid}: listed as undecomposed but now has a SW child -- update the list")

    sys_kids: dict[str, list[str]] = defaultdict(list)
    sys_wps: dict[str, set[str]] = defaultdict(set)
    for u, r in sw.items():
        for parent in r.trace:
            sys_kids[parent].append(sw_st[u])
            for o in imp.values():
                if o.serves == u and o.wp:
                    sys_wps[parent].add(o.wp)

    want_sw = {u: built_line_sw(u, sw_st, imp) for u in sw}
    want_sys = {u: built_line_sys(u, sys_st, sys_kids, sys_wps) for u in sysreqs}

    if args.write_status:
        SWREQ.write_text(
            apply_built(sw_text, "SW", lambda u: want_sw[u]), encoding="utf-8", newline="\n"
        )
        SYSREQ.write_text(
            apply_built(sys_text, "SYS", lambda u: want_sys[u]), encoding="utf-8", newline="\n"
        )
        print(f"  wrote {len(want_sw)} SW and {len(want_sys)} SYS `**Built.**` lines")
        return 0

    # The ordinary run verifies rather than writes. A mark that disagrees with
    # the plan is a failure here, so the generated half can never drift while
    # each document still passes inspection on its own.
    have_sw, have_sys = read_built(sw_text, "SW"), read_built(sys_text, "SYS")
    if have_sw or have_sys:
        for uid in sorted(sw):
            if have_sw.get(uid) != want_sw[uid]:
                bad(
                    f"{uid}: `Built.` line disagrees with the plan -- run --write-status\n"
                    f"        have: {have_sw.get(uid, '(missing)')}\n"
                    f"        want: {want_sw[uid]}"
                )
        for uid in sorted(sysreqs):
            if have_sys.get(uid) != want_sys[uid]:
                bad(
                    f"{uid}: `Built.` line disagrees with the plan -- run --write-status\n"
                    f"        have: {have_sys.get(uid, '(missing)')}\n"
                    f"        want: {want_sys[uid]}"
                )
    else:
        notes.append("no `Built.` lines present -- run --write-status to create them")

    # ---- 8. a check must scan somewhere that exists ----------------------
    tree = parse_tree_paths(imp_text)
    scans = parse_scan_paths(test_text)
    if not tree:
        bad("could not read the design's target tree -- the scan-path check would pass on nothing")
    for check, roots in sorted(scans.items()):
        for root in sorted(roots - tree):
            bad(f"{check}: scans '{root}/', which the design's target tree does not declare")

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
    print(f"  SYT/ANL/INSP system      {len(sys_cited):5d}  (specified {len(sys_spec_tests)})")
    print(f"  CT/E2E concept           {len(cn_spec_tests):5d}  (SYS-cited {len(cn_cited)})")
    print()
    print(f"  SYS with a CN parent     {sum(1 for r in sysreqs.values() if r.trace):5d} / {len(sysreqs)}")
    print(f"  SW covered by an IMP     {len(served):5d} / {len(sw)}")
    print(f"  SW with a SYS parent     {sum(1 for r in sw.values() if r.trace):5d} / {len(sw)}")
    print(f"  known unparented         {len(KNOWN_UNPARENTED):5d}  (SwReq 32.3)")

    if args.status:
        # Plan 0.1's resume pointer: the lowest-numbered package not yet done
        # whose prerequisites are done. Prereqs are prose, so this reports the
        # lowest unticked package and leaves 1.2's ordering to the reader --
        # claiming to have checked a dependency it cannot parse would be worse
        # than saying which one it used.
        def layer(name: str, st: dict[str, str]) -> None:
            c = defaultdict(int)
            for v in st.values():
                c[v] += 1
            total = len(st)
            print(
                f"  {name:<22s} {c[DONE]:4d} done  {c[PARTIAL]:4d} started  "
                f"{c[OPEN]:4d} open  {c[DEFERRED]:3d} deferred  "
                f"{c[ORPHAN]:2d} unknowable   / {total}"
            )

        cn_st_l: dict[str, list[str]] = defaultdict(list)
        for u, r in sysreqs.items():
            for p in r.trace:
                cn_st_l[p].append(sys_st[u])

        def _comb(v: list[str]) -> str:
            real = [c for c in v if c != DEFERRED]
            if not real:
                return DEFERRED
            if all(c == DONE for c in real):
                return DONE
            return PARTIAL if any(c in (DONE, PARTIAL) for c in real) else OPEN

        cn_st = {u: _comb(v) for u, v in cn_st_l.items()}
        print()
        print("  progress -- derived from the plan's checkboxes, nothing else")
        layer("CN concept", cn_st)
        layer("SYS system", sys_st)
        layer("SW software", sw_st)
        layer("IMP design", imp_st)
        print()
        nxt = [w for w in sorted(plan_wps) if not ticked[w]]
        if not nxt:
            print("  next work package    every package is ticked")
        else:
            w = nxt[0]
            mine = sorted(u for u, o in imp.items() if o.wp == w)
            left = [u for u in mine if imp_st[u] != DONE]
            print(f"  ▶ next work package  {w}   ({len(mine) - len(left)}/{len(mine)} IMP done)")
            for u in left[:12]:
                print(f"      {GLYPH[imp_st[u]]} {u}  {imp[u].serves}")
            if len(left) > 12:
                print(f"      … and {len(left) - 12} more")
            started = [w2 for w2 in nxt if any(imp_st[u] == PARTIAL for u, o in imp.items() if o.wp == w2)]
            if started:
                print(f"  packages with started-but-unfinished work: {', '.join(started)}")

    if args.progress:
        print()
        print("  work packages")
        done = sum(1 for v in ticked.values() if v)
        for wp in sorted(plan_wps):
            n = sum(1 for i in imp.values() if i.wp == wp)
            print(f"    [{'x' if ticked[wp] else ' '}] {wp}  {n:3d} IMP")
        print(f"    ticked {done} / {len(plan_wps)}")
        print("    (counts boxes; makes no verification claim -- Plan 0.4)")

    if args.counts:
        print()
        print("  test specification totals (Test Spec 0.2 quotes none; these are them)")
        by_kind: dict[str, int] = defaultdict(int)
        for t in spec_tests:
            if t.startswith("UT-"):
                by_kind["UT"] += 1
            elif t.startswith("IT-"):
                by_kind["IT"] += 1
            elif t.startswith("ANL-"):
                by_kind["ANL-SW"] += 1
            elif t.startswith("INSP-"):
                by_kind["INSP-SW"] += 1
        for kind in ("UT", "IT", "ANL-SW", "INSP-SW"):
            print(f"    {kind:<10s} {by_kind[kind]:5d}")
        print(f"    {'total':<10s} {len(spec_tests):5d}")
        print(f"    checks with a scan path {len(scans):3d}")

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

    if args.exec_rows:
        # The record carries status; this only lays out its rows, so that 345
        # test requirements are not hand-typed into a table (R-REQ-6/-7). Every
        # row starts `Not Run`: the generator never invents a verdict.
        serves_of: dict[str, list[str]] = defaultdict(list)
        for uid, r in sorted(sysreqs.items()):
            for t in sorted(r.tests):
                serves_of[t].append(uid)
        for uid, r in sorted(sw.items()):
            for t in sorted(r.tests):
                serves_of[t].append(uid)
        want = args.exec_rows
        chosen: set[str] = set()
        if want in ("system", "all"):
            chosen |= sys_spec_tests
        if want in ("concept", "all"):
            chosen |= cn_spec_tests
        if want in ("software", "all"):
            chosen |= spec_tests
        print()
        print("| Case | Serves | Status | Date | Evidence | Comments |")
        print("|---|---|---|---|---|---|")
        for t in sorted(chosen, key=lambda x: (re.sub(r"\d+$", "", x), int(x.rsplit("-", 1)[1]))):
            serves = ", ".join(f"`{u}`" for u in serves_of.get(t, [])) or "—"
            print(f"| `{t}.c1` | {serves} | `Not Run` | | | |")

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
