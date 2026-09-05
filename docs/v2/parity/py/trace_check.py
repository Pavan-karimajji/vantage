# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: DF
# @author Pavan Karimajji <pavankarimajji1997@gmail.com>

"""Requirement-set checker, driven entirely by ``layers.yaml``.

Nothing about the layer chain is hardcoded here -- that is the point
(``R-REQ-12`` proposed, ``../PROPOSED_RULES.md``). A module declaring
``[CN, SYS]`` or ``[SYS]`` alone works without touching this file, and the top
declared layer is unparented *by definition* rather than by a hand-edited
exception set.

Usage
-----
    python trace_check.py                 # run every check; exit 1 on findings
    python trace_check.py --matrix        # print the generated traceability matrix
    python trace_check.py --stats         # counts against the declared budget
    python trace_check.py --next-uid      # next free UID per layer, and remaining budget
    python trace_check.py --exec-rows     # Test Execution Record skeleton
    python trace_check.py --selftest      # plant violations, prove each is caught

``--selftest`` is ``R-REQ-9`` applied to the checker itself: a check nobody has
seen fail is a check nobody should believe.
"""

from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# --------------------------------------------------------------------- parse --

RE_REQ = re.compile(
    r"^\*\*`(?P<uid>[A-Z]+-\d{4})`\*\*\s*·\s*`(?P<prio>[^`]+)`\s*·\s*`(?P<rel>[^`]+)`\s*—\s*(?P<headline>.+?)\s*$"
)
RE_TEST = re.compile(
    r"^\*\*`(?P<tid>[A-Z]{2,4}(?:-[A-Za-z]+)?-\d{2})`\*\*\s*·\s*(?P<method>[TDAI])\s*·\s*"
    r"fixture\s+(?P<fixtures>.+?)\s*—\s*(?P<headline>.+?)\s*$"
)
RE_FIELD = re.compile(r"^\*\*(?P<name>[A-Z][a-z]+)\.\*\*\s*(?P<value>.*)$")
RE_CASE = re.compile(r"^-\s*`\.(?P<case>c\d+)`")
RE_UID = re.compile(r"\b[A-Z]+-\d{4}\b")
RE_TID = re.compile(r"\b[A-Z]{2,4}(?:-[A-Za-z]+)?-\d{2}\b")
RE_TICKED = re.compile(r"`([^`]+)`")
RE_FIXROW = re.compile(r"^\|\s*`(?P<fix>F-[A-Z0-9-]+)`\s*\|")
RE_STATUS = re.compile(r"^\s*\*\*Status\.\*\*|^\|\s*Status\s*\|", re.MULTILINE)


@dataclass
class Req:
    uid: str
    layer: str
    headline: str
    doc: str
    line: int
    shall: str = ""
    accept: str = ""
    binds: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    category: str = ""
    verify: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)


@dataclass
class Test:
    tid: str
    layer: str
    method: str
    headline: str
    line: int
    fixtures: list[str] = field(default_factory=list)
    serves: list[str] = field(default_factory=list)
    cases: list[str] = field(default_factory=list)


@dataclass
class Finding:
    code: str
    where: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return f"  {self.code:<14} {self.where:<28} {self.message}"


# ---------------------------------------------------------------- loading ----


RE_HEAD = re.compile(r"^\*\*`?[A-Z]{2,5}-\d+")
RE_FIELDLINE = re.compile(
    r"^\*\*(Shall|Accept|Verify|Trace|Binds|Category|Built|Now|Serves|Fixture|Steps)\.?\*\*"
)
RE_TABLERULE = re.compile(r"^\|[-: |]+\|$")


def load_spec(root: Path) -> dict:
    return yaml.safe_load((root / "layers.yaml").read_text(encoding="utf-8"))


def declared_ports(root: Path, spec: dict) -> tuple[dict[str, str], set[str]]:
    """Return {port name: grade} and the set of names graded REAL.

    ``R-REQ-15``: a port is resolved against the component's real
    ``conf/ports.yaml`` first; one found only under ``ports.proposed:`` is
    graded PROPOSED and reported, never silently accepted.
    """
    ports: dict[str, str] = {}
    real: set[str] = set()
    cfg = spec.get("ports", {}) or {}

    src = root / cfg.get("source", "")
    if src.is_file():
        data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
        for group in ("inputs", "outputs"):
            for entry in data.get(group) or []:
                ports[entry["name"]] = "REAL"
                real.add(entry["name"])

    for group in ("inputs", "outputs"):
        for entry in (cfg.get("proposed") or {}).get(group) or []:
            ports.setdefault(entry["name"], "PROPOSED")
    return ports, real


RE_WP = re.compile(
    r"^-\s*\[(?P<box>[ x~])\]\s*\*\*(?P<wp>WP-\d+)\*\*\s*—\s*(?P<headline>.+?)\s*·\s*lands\s*(?P<lands>.+?)\s*·\s*(?P<note>.*)$"
)


def parse_plan(path: Path) -> list[dict]:
    """Work packages, in document order. R-REQ-6a: the ONE hand-maintained
    progress state in a set -- everything else about progress is derived."""
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = RE_WP.match(raw.strip())
        if not m:
            continue
        out.append(
            {
                "wp": m["wp"],
                "box": m["box"],
                "headline": m["headline"],
                "lands": RE_UID.findall(m["lands"]),
                "note": m["note"],
            }
        )
    return out


def count_commentary(lines: list[str], table_style: bool = False) -> int:
    """Lines that are neither requirement content nor structure (``R-REQ-14``).

    A requirement field, a UID headline, a markdown heading, a table rule, a
    fence and a blank line are all structure. Everything else is commentary --
    preamble, rationale, notes, crosswalk tables. That is the thing which makes
    a document unreadable, and the thing length has never been able to see.
    """
    n = 0
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if RE_HEAD.match(s) or RE_FIELDLINE.match(s):
            continue
        if s.startswith("#") or s.startswith("```") or RE_TABLERULE.match(s):
            continue
        # In a table-style layer every requirement IS a table row, so counting
        # rows as prose would fail the one document R-REQ-14 exempts.
        if table_style and s.startswith("|"):
            continue
        n += 1
    return n


RE_TABLE_REQ = re.compile(
    r"^\|\s*`(?P<uid>[A-Z]+-\d{4})`\s*\|(?P<serves>[^|]*)\|(?P<wp>[^|]*)\|"
    r"(?P<change>[^|]*)\|(?P<design>.*)\|(?P<tests>[^|]*)\|\s*$"
)

# R-REQ-3's anatomy in one row. `Change` is a closed vocabulary derived from
# what exists today, never asserted: a row claiming NEW for code that is
# already there is a design error a reviewer can see.
CHANGE_CLASSES = {"KEEP", "MOVE", "DEDUPE", "EXTEND", "NEW", "DROP"}


def parse_table_requirements(path: Path, layer: str) -> list[Req]:
    """One row per requirement (``row_style: table``).

    The design text lands in ``shall`` so the word cap still applies -- a
    design statement that runs past 60 words is doing more than naming a file
    and a symbol, which is the same defect the cap catches everywhere else.
    """
    reqs: list[Req] = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = RE_TABLE_REQ.match(raw.strip())
        if not m:
            continue
        design = m["design"].strip()
        r = Req(
            uid=m["uid"],
            layer=layer,
            headline=design[:90],
            doc=path.name,
            line=n,
            shall=design,
            accept="",
        )
        r.trace = RE_UID.findall(m["serves"])
        r.verify = RE_TID.findall(m["tests"])
        r.items = RE_TICKED.findall(m["wp"]) + RE_TICKED.findall(m["change"])
        r.category = (m["change"] or "").strip().strip("`* ")
        reqs.append(r)
    return reqs


def parse_requirements(path: Path, layer: str) -> list[Req]:
    reqs: list[Req] = []
    current: Req | None = None
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        head = RE_REQ.match(raw)
        if head:
            current = Req(
                uid=head["uid"],
                layer=layer,
                headline=head["headline"],
                doc=path.name,
                line=n,
            )
            reqs.append(current)
            continue
        if current is None:
            continue
        fld = RE_FIELD.match(raw)
        if not fld:
            continue
        name, value = fld["name"], fld["value"]
        if name == "Shall":
            current.shall = value
        elif name == "Accept":
            current.accept = value
        elif name == "Binds":
            current.binds = RE_TICKED.findall(value)
        elif name == "Item":
            current.items = RE_TICKED.findall(value)
        elif name == "Category":
            found = RE_TICKED.findall(value)
            current.category = found[0] if found else value.strip()
        elif name == "Verify":
            verify_part, _, trace_part = value.partition("**Trace.**")
            current.verify = RE_TID.findall(verify_part)
            current.trace = RE_UID.findall(trace_part)
        elif name == "Trace":
            current.trace = RE_UID.findall(value)
    return reqs


def parse_tests(path: Path, prefix_layer: dict[str, str]) -> tuple[list[Test], set[str]]:
    tests: list[Test] = []
    fixtures: set[str] = set()
    current: Test | None = None
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fix = RE_FIXROW.match(raw)
        if fix:
            fixtures.add(fix["fix"])
            continue
        head = RE_TEST.match(raw)
        if head:
            token = head["tid"].split("-")[0]
            current = Test(
                tid=head["tid"],
                layer=prefix_layer.get(token, "?"),
                method=head["method"],
                headline=head["headline"],
                line=n,
                fixtures=RE_TICKED.findall(head["fixtures"]),
            )
            tests.append(current)
            continue
        if current is None:
            continue
        case = RE_CASE.match(raw)
        if case:
            current.cases.append(case["case"])
            continue
        fld = RE_FIELD.match(raw)
        if fld and fld["name"] == "Serves":
            current.serves = RE_UID.findall(fld["value"])
    return tests, fixtures


# ----------------------------------------------------------------- checks ----


def run_checks(root: Path) -> tuple[list[Finding], list[str], dict]:
    spec = load_spec(root)
    layers = spec["layers"]
    order = [ly["id"] for ly in layers]
    by_id = {ly["id"]: ly for ly in layers}
    limits = spec.get("limits", {})
    items_declared = set((spec.get("items") or {}).keys())
    ports, real_ports = declared_ports(root, spec)

    prefix_layer: dict[str, str] = {}
    for ly in layers:
        for token in ly.get("tests") or []:
            prefix_layer[token] = ly["id"]

    findings: list[Finding] = []
    notes: list[str] = []

    reqs: dict[str, Req] = {}
    per_layer: dict[str, list[Req]] = {lid: [] for lid in order}
    commentary: dict[str, tuple[int, int, float]] = {}
    for ly in layers:
        doc = root / ly["doc"]
        if not doc.is_file():
            findings.append(Finding("C-DOC-MISSING", ly["id"], f"declared doc {ly['doc']} not found"))
            continue
        # R-REQ-14. There is NO cap on document length -- a document is as long
        # as the problem needs. What is capped is COMMENTARY: every line that is
        # not a requirement field, a headline, a heading or blank, measured per
        # requirement so a thorough document is never punished for being large.
        # Measured 2026-09-05: readable sets run 1.6-4.3, unreadable ones 81-990.
        body = doc.read_text(encoding="utf-8").splitlines()
        if RE_STATUS.search("\n".join(body)):
            findings.append(
                Finding("C-STATUS", ly["doc"], "a Status field in a specification (R-REQ-6)")
            )
        table_style = ly.get("row_style") == "table"
        parse = parse_table_requirements if table_style else parse_requirements
        for r in parse(doc, ly["id"]):
            if r.uid in reqs:
                findings.append(Finding("C-DUPUID", r.uid, f"allocated twice ({reqs[r.uid].doc}, {r.doc})"))
            reqs[r.uid] = r
            per_layer[ly["id"]].append(r)

        ccap = limits.get("commentary_lines_per_requirement")
        nreq = len(per_layer[ly["id"]])
        ncom = count_commentary(body, table_style)
        if ccap and nreq:
            per = ncom / nreq
            commentary[ly["id"]] = (ncom, nreq, per)
            if per > ccap:
                findings.append(
                    Finding(
                        "C-COMMENTARY",
                        ly["doc"],
                        f"{ncom} commentary lines over {nreq} requirements = {per:.1f} each, "
                        f"cap {ccap} -- cut the prose, never the requirements (R-REQ-14)",
                    )
                )
        elif ccap and not nreq and ncom:
            findings.append(
                Finding(
                    "C-COMMENTARY",
                    ly["doc"],
                    f"{ncom} commentary lines and no requirements at all -- this is prose "
                    f"wearing a requirement document's name (R-REQ-14)",
                )
            )

    tspec = root / spec["test_spec"]
    if tspec.is_file():
        tests_list, fixtures = parse_tests(tspec, prefix_layer)
    else:
        findings.append(
            Finding("C-DOC-MISSING", "test_spec", f"declared test spec {spec['test_spec']} not found")
        )
        tests_list, fixtures = [], set()
    tests: dict[str, Test] = {}
    for t in tests_list:
        if t.tid in tests:
            findings.append(Finding("C-DUPTEST", t.tid, "test id defined twice in the spec"))
        tests[t.tid] = t

    # --- C-LAYER-EMPTY / C-BUDGET ------------------------------------------
    for lid in order:
        n = len(per_layer[lid])
        if n == 0:
            findings.append(
                Finding("C-LAYER-EMPTY", lid, "layer declared but empty -- declare it or delete it")
            )
        # R-REQ-13. An EXPECTATION, reported -- never a failure. A hard cap here
        # makes a writer merge two obligations into one row to fit, and the
        # merge is invisible in the finished document. Over expectation is a
        # scope signal for a human to judge, not something to silently shrink.
        budget = by_id[lid].get("budget")
        if budget and n > budget:
            notes.append(
                f"{lid} holds {n} requirements against a declared expectation of {budget} "
                f"({n * 100 // budget}%). Not an error (R-REQ-13) -- either the scope grew, "
                f"or raise budget_basis with a dated budget_history entry."
            )

    # --- C-BUDGET-BASIS -----------------------------------------------------
    # The per-layer caps must add up to the declared basis, or the basis is a
    # comment rather than a derivation (R-REQ-13).
    basis = spec.get("budget_basis") or {}
    if basis:
        declared_total = basis.get("total")
        derived = basis.get("count", 0) * basis.get("per_unit", 0)
        layer_sum = sum(by_id[lid].get("budget", 0) for lid in order)
        if declared_total != derived:
            findings.append(
                Finding("C-BUDGET-BASIS", "budget_basis", f"total {declared_total} != count x per_unit ({derived})")
            )
        elif layer_sum != declared_total:
            findings.append(
                Finding("C-BUDGET-BASIS", "budget_basis", f"per-layer budgets sum to {layer_sum}, basis total is {declared_total}")
            )

    # --- C-PARENT / C-DANGLING ---------------------------------------------
    for r in reqs.values():
        idx = order.index(r.layer)
        if idx == 0:
            if r.trace:
                findings.append(
                    Finding("C-PARENT", r.uid, f"top declared layer {r.layer} must not trace upward")
                )
            continue
        parent_layer = order[idx - 1]
        if not r.trace:
            findings.append(
                Finding("C-PARENT", r.uid, f"no {parent_layer} parent (the layer above is incomplete, or this is at the wrong layer)")
            )
        for p in r.trace:
            if p not in reqs:
                prefix = p.split("-")[0]
                if prefix not in order:
                    findings.append(
                        Finding("C-LAYER-GONE", r.uid, f"traces to {p}, but layer {prefix} is not declared -- re-point to {parent_layer}")
                    )
                else:
                    findings.append(Finding("C-DANGLING", r.uid, f"traces to {p}, which does not exist"))
            elif reqs[p].layer != parent_layer:
                findings.append(
                    Finding("C-PARENT", r.uid, f"traces to {p} in {reqs[p].layer}; nearest declared layer above is {parent_layer}")
                )

    # --- C-UNDECOMP ---------------------------------------------------------
    has_child: set[str] = set()
    for r in reqs.values():
        has_child.update(r.trace)
    for lid in order[:-1]:
        for r in per_layer[lid]:
            if r.uid not in has_child:
                findings.append(
                    Finding("C-UNDECOMP", r.uid, f"nothing in {order[order.index(lid) + 1]} decomposes it")
                )

    # --- C-ORPHAN / C-WIDOW / C-TWOWAY -------------------------------------
    for r in reqs.values():
        if not r.verify:
            # A layer declaring no test prefixes is verified by something other
            # than a test in this spec -- an implementation design is checked by
            # the tests of the requirement it serves, plus build gates. Asking it
            # for its own test id would invent a second, weaker copy of them.
            if by_id[r.layer].get("tests"):
                findings.append(Finding("C-ORPHAN", r.uid, "no test -- unverifiable as written"))
        # A layer declaring no test prefixes repeats its parent's test ids so a
        # row reads standalone. That is a citation, not a claim to be served --
        # the test still names only the requirement it verifies, and demanding it
        # name the design row too would invent a link R-REQ-11 never asked for.
        two_way = bool(by_id[r.layer].get("tests"))
        for tid in r.verify:
            if tid not in tests:
                findings.append(Finding("C-DANGLING", r.uid, f"cites test {tid}, which does not exist"))
            elif r.uid not in tests[tid].serves:
                if two_way:
                    findings.append(
                        Finding("C-TWOWAY", r.uid, f"claims to be served by {tid}, which does not cite it back (R-REQ-11)")
                    )
    for t in tests.values():
        if not t.serves:
            findings.append(Finding("C-WIDOW", t.tid, "serves no requirement -- invented scope"))
        for uid in t.serves:
            if uid not in reqs:
                prefix = uid.split("-")[0]
                code = "C-LAYER-GONE" if prefix not in order else "C-DANGLING"
                findings.append(Finding(code, t.tid, f"serves {uid}, whose layer {prefix} is not declared" if code == "C-LAYER-GONE" else f"serves {uid}, which does not exist"))
            elif t.tid not in reqs[uid].verify:
                findings.append(
                    Finding("C-TWOWAY", t.tid, f"serves {uid}, whose own Verify does not name it (R-REQ-11)")
                )
        if t.layer != "?" and t.serves:
            for uid in t.serves:
                if uid in reqs and reqs[uid].layer != t.layer:
                    findings.append(
                        Finding("C-TESTLAYER", t.tid, f"is a {t.layer} test but serves {uid} in {reqs[uid].layer}")
                    )
        if not t.cases:
            findings.append(Finding("C-NOCASE", t.tid, "no case -- nothing that can pass or fail (R-REQ-5)"))
        if t.method == "A" and len(t.cases) < 2:
            findings.append(
                Finding("C-NOPLANT", t.tid, "an A-method check ships a planted-violation case (R-REQ-9)")
            )
        for fx in t.fixtures:
            if fx not in fixtures:
                findings.append(Finding("C-FIXTURE", t.tid, f"fixture {fx} is not in the catalogue"))

    # --- C-CATEGORY (R-REQ-16) ---------------------------------------------
    # A layer may split its requirements into declared categories -- stakeholder
    # requirements into `feature` and `kpi`, for instance. A module that declares
    # only `feature` (cyber-security, an embedded item with no performance
    # target of its own) is never asked for a KPI it does not have.
    for lid in order:
        declared = by_id[lid].get("categories")
        if not declared:
            continue
        seen: dict[str, int] = {c: 0 for c in declared}
        for r in per_layer[lid]:
            if not r.category:
                findings.append(Finding("C-CATEGORY", r.uid, f"no category; {lid} declares {declared}"))
            elif r.category not in declared:
                findings.append(
                    Finding("C-CATEGORY", r.uid, f"category '{r.category}' is not declared by {lid} ({declared})")
                )
            else:
                seen[r.category] += 1
                if r.category == "kpi" and not any(ch.isdigit() or ch == "\u2298" for ch in r.accept):
                    findings.append(
                        Finding("C-KPI-UNMEASURED", r.uid, "a KPI Accept states no number and no \u2298 -- it cannot be measured")
                    )
        for cat, n in seen.items():
            if n == 0:
                findings.append(
                    Finding("C-CATEGORY-EMPTY", f"{lid}/{cat}", "category declared but empty -- populate it or stop declaring it")
                )

    # --- C-BINDS / C-ITEM (R-REQ-15) ---------------------------------------
    for lid in order:
        ly = by_id[lid]
        for r in per_layer[lid]:
            if ly.get("requires_binds"):
                if not r.binds:
                    findings.append(Finding("C-BINDS", r.uid, "binds no declared port (R-REQ-15)"))
                for p in r.binds:
                    if p not in ports:
                        findings.append(
                            Finding("C-BINDS", r.uid, f"binds {p}, declared in neither conf/ports.yaml nor ports.proposed")
                        )
            if ly.get("requires_item"):
                if not r.items:
                    findings.append(Finding("C-ITEM", r.uid, "names no declared software item (R-REQ-15)"))
                for it in r.items:
                    if it not in items_declared:
                        findings.append(Finding("C-ITEM", r.uid, f"names item {it}, which layers.yaml does not declare"))

    # --- plan coverage (R-REQ-6a) ------------------------------------------
    # Opt-in: a set with no `plan:` declared is not asked about one. Where a
    # plan exists, the question it answers is "will anything actually build
    # this requirement?" -- an orphan here is invisible to every other check,
    # because the requirement itself is perfectly well formed.
    packages = []
    if spec.get("plan"):
        planfile = root / spec["plan"]
        if not planfile.is_file():
            findings.append(
                Finding("C-DOC-MISSING", "plan", f"declared plan {spec['plan']} not found")
            )
        else:
            packages = parse_plan(planfile)
            landed: dict[str, str] = {}
            for pkg in packages:
                if pkg["box"] == "~" and "closed by" not in pkg["note"].lower():
                    findings.append(
                        Finding(
                            "C-PLANMARK",
                            pkg["wp"],
                            "marked started with no 'closed by <command or condition>' -- "
                            "a started mark exists to say where to resume (R-REQ-6a)",
                        )
                    )
                for uid in pkg["lands"]:
                    if uid not in reqs:
                        findings.append(
                            Finding("C-PLANUID", pkg["wp"], f"lands {uid}, which does not exist")
                        )
                    elif uid in landed:
                        findings.append(
                            Finding(
                                "C-DUPLAND",
                                uid,
                                f"landed by both {landed[uid]} and {pkg['wp']} -- "
                                "two places to build one requirement",
                            )
                        )
                    else:
                        landed[uid] = pkg["wp"]
            # Work packages land the LOWEST declared layer: that is where the
            # buildable work is, and it is derived rather than declared again.
            lowest = order[-1]
            for r in per_layer[lowest]:
                if r.uid not in landed:
                    findings.append(
                        Finding("C-UNLANDED", r.uid, "no work package lands it -- nothing will build it")
                    )
        stats_plan = packages

    # --- C-CHANGE ----------------------------------------------------------
    # A table-style layer declares a change class per row from a closed list.
    # An invented class is how a design starts describing intent instead of
    # what is actually there.
    for lid in order:
        if by_id[lid].get("row_style") != "table":
            continue
        for r in per_layer[lid]:
            if r.category not in CHANGE_CLASSES:
                findings.append(
                    Finding(
                        "C-CHANGE",
                        r.uid,
                        f"change class {r.category!r} is not one of {sorted(CHANGE_CLASSES)}",
                    )
                )

    # --- C-WORDS / C-HEADLINE (R-REQ-14) -----------------------------------
    wcap = limits.get("requirement_words")
    hcap = limits.get("headline_chars")
    for r in reqs.values():
        if wcap:
            words = len(f"{r.shall} {r.accept}".split())
            if words > wcap:
                findings.append(Finding("C-WORDS", r.uid, f"Shall+Accept is {words} words over the cap of {wcap}"))
        if hcap and len(r.headline) > hcap:
            findings.append(Finding("C-HEADLINE", r.uid, f"headline is {len(r.headline)} chars over the cap of {hcap}"))

    # --- port grades (a note, not a finding) -------------------------------
    used = {p for r in reqs.values() for p in r.binds}
    proposed = sorted(p for p in used if ports.get(p) == "PROPOSED")
    if proposed:
        notes.append(
            f"{len(proposed)} bound port(s) are PROPOSED, not yet in conf/ports.yaml: {', '.join(proposed)}"
        )
    if real_ports & used:
        notes.append(f"{len(real_ports & used)} bound port(s) resolved against the real conf/ports.yaml")

    stats = {
        "order": order,
        "by_id": by_id,
        "per_layer": {lid: len(per_layer[lid]) for lid in order},
        "reqs": reqs,
        "tests": tests,
        "spec": spec,
        "ports": ports,
    }
    stats["commentary"] = commentary
    stats["plan"] = packages
    return findings, notes, stats


# ---------------------------------------------------------------- reports ----


def print_status(stats: dict) -> None:
    """R-REQ-6a. Every number here is recomputed from the plan's checkboxes,
    which are the only progress state anyone types."""
    pkgs = stats.get("plan") or []
    if not pkgs:
        print("\n  no implementation plan declared (layers.yaml `plan:`) -- nothing to roll up")
        return
    sym = {"x": "done", "~": "started", " ": "open"}
    done = sum(1 for p in pkgs if p["box"] == "x")
    started = sum(1 for p in pkgs if p["box"] == "~")
    landed_done = sum(len(p["lands"]) for p in pkgs if p["box"] == "x")
    landed_all = sum(len(p["lands"]) for p in pkgs)
    print(f"\n  {stats['spec']['module']} -- implementation status (R-REQ-6a, derived)\n")
    for p in pkgs:
        print(f"    [{p['box']}] {p['wp']:<7} {sym[p['box']]:<8} {len(p['lands'])} req  {p['headline'][:52]}")
    print(f"\n    packages: {done} done, {started} started, {len(pkgs) - done - started} open, of {len(pkgs)}")
    print(f"    requirements landed by a done package: {landed_done} of {landed_all}")
    nxt = next((p for p in pkgs if p["box"] != "x"), None)
    if nxt:
        print(f"    next: {nxt['wp']} -- {nxt['headline']}")
    print("\n    Progress is not verification (R-REQ-6): a ticked box says the work")
    print("    was done, never that the requirement is met. That is a Test Execution")
    print("    Record's answer, one per campaign.")


def print_stats(stats: dict) -> None:
    spec = stats["spec"]
    basis = spec.get("budget_basis", {})
    print(f"\n  {spec['module']} -- requirement set\n")
    print(f"  {'layer':<8}{'reqs':>6}{'budget':>9}{'tests':>8}")
    print(f"  {'-' * 31}")
    total = 0
    for lid in stats["order"]:
        n = stats["per_layer"][lid]
        total += n
        budget = stats["by_id"][lid].get("budget", "-")
        ntests = sum(1 for t in stats["tests"].values() if t.layer == lid)
        print(f"  {lid:<8}{n:>6}{budget:>9}{ntests:>8}")
    print(f"  {'-' * 31}")
    print(f"  {'total':<8}{total:>6}{basis.get('total', '-'):>9}{len(stats['tests']):>8}")
    if basis:
        print(
            f"\n  Budget basis (R-REQ-13): {basis['count']} {basis['unit']}s"
            f" x {basis['per_unit']} = {basis['total']}. Derived, not negotiated."
        )
    # R-REQ-13. Printed every run: a reason kept only in a YAML comment is a
    # reason nobody reads, and "raised with a dated line saying why" is only
    # auditable if the line is in front of the person raising it next time.
    history = spec.get("budget_history") or []
    if history:
        print("")
        print("  Budget history -- %d change(s), each made while writing:" % len(history))
        for h in history:
            print(f"    {h['date']}  {h['change']}")
            print(f"              {h['why']}")
    com = stats.get("commentary") or {}
    if com:
        cap = (spec.get("limits") or {}).get("commentary_lines_per_requirement")
        print("")
        print(f"  Commentary per requirement (R-REQ-14, cap {cap}) -- the only size that is capped:")
        for lid, (ncom, nreq, per) in com.items():
            print(f"    {lid:<6} {per:5.1f}   ({ncom} commentary lines over {nreq} requirements)")
    for lid in stats["order"]:
        declared = stats["by_id"][lid].get("categories")
        if declared:
            counts = {c: 0 for c in declared}
            for r in stats["reqs"].values():
                if r.layer == lid and r.category in counts:
                    counts[r.category] += 1
            split = " \u00b7 ".join(f"{c}: {n}" for c, n in counts.items())
            print(f"\n  {lid} categories -- {split}")
    ncases = sum(len(t.cases) for t in stats["tests"].values())
    print(f"  Test cases: {ncases}. Ports bound: {len({p for r in stats['reqs'].values() for p in r.binds})}.")


def print_next_uid(stats: dict) -> None:
    """The next free UID per layer (R-REQ-2: creation order, never reused).

    Adding requirements to a finished set is ordinary work, not a migration.
    This exists so the number is read from the documents rather than eyeballed,
    which is how two requirements come to share a UID.
    """
    reqs = stats["reqs"]
    print()
    for lid in stats["order"]:
        used = sorted(int(u.split("-")[1]) for u in reqs if reqs[u].layer == lid)
        nxt = (used[-1] + 1) if used else 1
        budget = stats["by_id"][lid].get("budget", "-")
        room = (budget - len(used)) if isinstance(budget, int) else "-"
        print(f"  {lid:<6} next: {lid}-{nxt:04d}   (in use: {len(used)}, budget {budget}, room for {room} more)")
    tests = stats["tests"]
    print()
    for prefix in sorted({t.tid.rsplit("-", 1)[0] for t in tests.values()}):
        used = sorted(int(t.tid.rsplit("-", 1)[1]) for t in tests.values() if t.tid.rsplit("-", 1)[0] == prefix)
        print(f"  {prefix:<16} next: {prefix}-{used[-1] + 1:02d}")
    print()


def print_matrix(stats: dict) -> None:
    order, reqs, tests = stats["order"], stats["reqs"], stats["tests"]
    print("\n  Traceability matrix -- GENERATED, never hand-edited (R-REQ-7)\n")
    children: dict[str, list[str]] = {u: [] for u in reqs}
    for r in reqs.values():
        for p in r.trace:
            children.setdefault(p, []).append(r.uid)
    for lid in order:
        print(f"  == {lid} " + "=" * 62)
        print(f"  {'uid':<10}{'tests':<24}{'parents':<20}children")
        for uid in sorted(u for u, r in reqs.items() if r.layer == lid):
            r = reqs[uid]
            kids = ", ".join(sorted(children.get(uid, []))) or "-"
            print(
                f"  {uid:<10}{', '.join(r.verify) or '-':<24}"
                f"{', '.join(r.trace) or '- (top layer)':<20}{kids}"
            )
        print()
    print(f"  == tests " + "=" * 60)
    print(f"  {'id':<16}{'m':<3}{'cases':<7}serves")
    for tid in sorted(tests):
        t = tests[tid]
        print(f"  {tid:<16}{t.method:<3}{len(t.cases):<7}{', '.join(t.serves) or '-'}")


def print_exec_rows(stats: dict) -> None:
    """Generate the Test Execution Record skeleton (R-REQ-6).

    The Serves column has to agree with the specifications, so the skeleton is
    generated and only the human half -- verdict, date, evidence -- is typed.
    Every row lands as ``Not Run``: the generator never invents a verdict.
    """
    tests = stats["tests"]
    print("| Case | Serves | Method | Status | Date | Evidence | Comments |")
    print("|---|---|---|---|---|---|---|")
    for tid in sorted(tests):
        t = tests[tid]
        serves = ", ".join(f"`{u}`" for u in t.serves)
        for c in t.cases:
            print(f"| `{tid}.{c}` | {serves} | {t.method} | Not Run | | | |")


# --------------------------------------------------------------- selftest ----

def load_mutations(root: Path) -> list[dict]:
    """Planted violations, declared as data beside layers.yaml.

    Kept out of this file on purpose: the checker must contain no module's
    document names, or "copy it to any module" is not true.
    """
    f = root / "selftest_mutations.yaml"
    if not f.is_file():
        return []
    return yaml.safe_load(f.read_text(encoding="utf-8"))["mutations"]




def selftest() -> int:
    print("\n  Selftest -- every check is planted with a violation and must catch it")
    print("  (R-REQ-9: a check nobody has seen fail is a check nobody should believe)\n")
    baseline, _, _ = run_checks(ROOT)
    base_codes = {f.code for f in baseline}
    mutations = load_mutations(ROOT)
    if not mutations:
        print("  no selftest_mutations.yaml beside layers.yaml -- nothing to plant")
        return 1
    print(f"  {'planted':<20}{'file':<34}caught?")
    print(f"  {'-' * 62}")
    failures = 0
    for m in mutations:
        code, fname, old, new = m["expect"], m["file"], m["find"], m["replace"]
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / ROOT.name
            shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns("__pycache__"))
            target = work / fname
            text = target.read_text(encoding="utf-8")
            if old not in text:
                print(f"  {code:<20}{fname:<34}SKIPPED - anchor not found")
                failures += 1
                continue
            target.write_text(text.replace(old, new, 1), encoding="utf-8")
            found, _, _ = run_checks(work)
            caught = any(f.code == code for f in found)
            print(f"  {code:<20}{fname:<34}{'yes' if caught else 'NO -- CHECK IS BLIND'}")
            if not caught:
                failures += 1
    print()
    if failures:
        print(f"  {failures} check(s) did not catch their planted violation.\n")
        return 1
    print(f"  All {len(mutations)} checks caught their planted violation.")
    print(f"  Baseline codes present without mutation: {sorted(base_codes) or 'none'}\n")
    return 0


# ------------------------------------------------------------------- main ----


def main() -> int:
    ap = argparse.ArgumentParser(description="Requirement-set checker driven by layers.yaml")
    ap.add_argument("--matrix", action="store_true", help="print the generated traceability matrix")
    ap.add_argument("--stats", action="store_true", help="counts against the derived budget")
    ap.add_argument("--next-uid", action="store_true", help="next free UID per layer and test prefix (R-REQ-2)")
    ap.add_argument("--exec-rows", action="store_true", help="generate the Test Execution Record skeleton")
    ap.add_argument("--selftest", action="store_true", help="plant a violation per check and prove it is caught")
    ap.add_argument("--status", action="store_true", help="implementation status, derived from the plan's checkboxes")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    findings, notes, stats = run_checks(ROOT)

    if args.next_uid:
        print_next_uid(stats)
        return 0
    if args.exec_rows:
        print_exec_rows(stats)
        return 0
    if args.status:
        print_status(stats)
    if args.stats:
        print_stats(stats)
    if args.matrix:
        print_matrix(stats)

    print()
    for n in notes:
        print(f"  note: {n}")
    if findings:
        print(f"\n  {len(findings)} finding(s):")
        for f in sorted(findings, key=lambda x: (x.code, x.where)):
            print(f)
        print()
        return 1
    print(f"\n  PASS -- {len(stats['reqs'])} requirements, {len(stats['tests'])} tests, no findings.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
