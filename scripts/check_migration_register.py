# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""Checks `docs/VANTAGE_Migration_Register.md` against decision D15.

D15: the register disposes every sim v2 requirement row exactly once. An
implementation (`IMP`) row inherits the disposition of the `SW` rows it
serves, so only the exceptions are listed. This script builds the universe
(every live row of the two sets), reads the register, and reports one line
per finding, `C-<NAME> <uid or path>: <what>`. It exits 0 only with no
finding.

A section row (`SIM:SYS-0040..0063` and a Why that starts `§13 — `) disposes
every live row of one kind in one sim v2 section at once. The script expands it
to its rows, so each row is still disposed exactly once; a section row that does
not cover exactly one whole section is `C-RANGE`.

Row UIDs are qualified by set (`SIM:SW-0001`, `PARITY:STK-0001`) because the
two sets reuse numbers. A row that a sim v2 document lists as retired is not
in the universe: only a row defined in the document's own requirement form
(or, for `IMP`, its table row) counts as live.

Usage:
    check_migration_register.py [--register <md>] [--selftest]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent  # modules/vantage

ROW_WORDS = ("carried", "moved", "superseded", "retired")
CODE_WORDS = ("reused", "corrected", "replaced", "retired")

# set -> (directory under ROOT, [(kind, file, form)])
SETS = {
    "SIM": (
        "docs/v2",
        [
            ("CN", "SIM_Concept_Document_v0.3.1.md", "concept"),
            ("SYS", "SIM_System_Requirements_v0.1.md", "block"),
            ("SW", "SIM_Software_Requirements_v0.1.md", "block"),
            ("IMP", "SIM_Implementation_Design_v0.1.md", "imp"),
        ],
    ),
    "PARITY": (
        "docs/v2/parity",
        [
            ("STK", "PARITY_Stakeholder_Requirements.md", "block"),
            ("SYS", "PARITY_System_Requirements.md", "block"),
            ("SW", "PARITY_Software_Requirements.md", "block"),
            ("IMP", "PARITY_Implementation_Design.md", "imp"),
        ],
    ),
}

# The four roots whose direct entries the code table must cover, plus scripts/.
CODE_ROOTS = ("src/simcore", "src/simengine", "src/adas_sim", "include/simcore")
CODE_FILE_ROOTS = ("scripts",)
IGNORED_NAMES = {"__pycache__"}
# The code universe is the tree as forked (D2): this tag names it.
SEED_TAG = "seed-from-sim"

CONCEPT_RE = re.compile(r"^\|[^|]*\|\s*(CN-\d{4})\s*\|")
BLOCK_RE = r"^\*\*`(%s-\d{4})`\*\*"
IMP_RE = re.compile(
    r"^\|\s*(?:`\[.\]`\s*\|\s*)?`(IMP-\d{4})`\s*\|([^|]*)\|\s*`?WP-[^|`\s]*`?\s*\|"
)
SW_RE = re.compile(r"SW-\d{4}")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
SCOPE_RE = re.compile(r"^Scope:\s*(.+?)\s*$")
SCOPE_TERM_RE = re.compile(r"^([A-Z]+):([A-Z]+)(?:-(\d{4})\.\.(\d{4}))?$")
ARCH_REF_RE = re.compile(r"ARCH §(\d+(?:\.\d+)*)")
ARCH_HEAD_RE = re.compile(r"^#{2,6}\s+(\d+(?:\.\d+)*)\.?\s")
DECISION_RE = re.compile(r"^\|\s*(D\d+)\s*\|")
UID_RE = re.compile(r"^([A-Z]+):([A-Z]+)-(\d{4})$")
RANGE_RE = re.compile(r"^([A-Z]+):([A-Z]+)-(\d{4})\.\.(\d{4})$")
SECTION_NUM_RE = re.compile(r"^(\d+(?:\.\d+)*[a-z]?)\.?(?:\s|$)")
WHY_LABEL_RE = re.compile(r"^(§\d+(?:\.\d+)*[a-z]?) — (.*)$")


@dataclass
class Context:
    """Everything the checks compare the register with."""

    universe: Dict[str, str]  # qualified uid -> kind
    serves: Dict[str, List[str]]  # qualified IMP uid -> qualified SW uids
    decisions: Set[str]  # D1, D2, ...
    arch_sections: Set[str]  # "3", "3.1", "11", ...
    arch_text: str
    rct_uids: Set[str]  # RCT:SYS-0001, RCT:IMP-0001, ...
    root: Path = ROOT
    # Entries the code table must cover; None when the seed tag is missing.
    code_entries: Optional[List[str]] = None
    # qualified uid -> section label of its source heading: "§5.1" or heading text.
    sections: Dict[str, str] = field(default_factory=dict)
    # Every file of the seed tree under the code roots; used for a directory with no row.
    seed_files: Optional[List[str]] = None


@dataclass
class Row:
    line: int
    cells: List[str]


@dataclass
class Section:
    name: str
    scope: List[Tuple[str, str, Optional[int], Optional[int]]] = field(default_factory=list)
    rows: List[Row] = field(default_factory=list)


@dataclass
class Register:
    sections: List[Section] = field(default_factory=list)
    code_rows: List[Row] = field(default_factory=list)


# ---------------------------------------------------------------- universe --

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def section_label(heading: str) -> str:
    """`§<number>` when the heading starts with a section number, else its text."""
    m = SECTION_NUM_RE.match(heading)
    return f"§{m.group(1)}" if m else heading


def _scan_set(
    root: Path, name: str
) -> Tuple[Dict[str, str], Dict[str, List[str]], Dict[str, str]]:
    directory, docs = SETS[name]
    universe: Dict[str, str] = {}
    serves: Dict[str, List[str]] = {}
    sections: Dict[str, str] = {}
    for kind, filename, form in docs:
        label = ""
        fenced = False
        for line in _read(root / directory / filename).splitlines():
            if line.lstrip().startswith("```"):
                fenced = not fenced
            h = None if fenced else HEAD_RE.match(line)
            if h:
                label = section_label(h.group(2))
                continue
            if form == "concept":
                m = CONCEPT_RE.match(line)
                if m:
                    universe[f"{name}:{m.group(1)}"] = kind
                    sections[f"{name}:{m.group(1)}"] = label
            elif form == "block":
                m = re.match(BLOCK_RE % kind, line)
                if m:
                    universe[f"{name}:{m.group(1)}"] = kind
                    sections[f"{name}:{m.group(1)}"] = label
            else:
                m = IMP_RE.match(line)
                if m:
                    uid = f"{name}:{m.group(1)}"
                    universe[uid] = kind
                    sections[uid] = label
                    serves[uid] = [f"{name}:{s}" for s in SW_RE.findall(m.group(2))]
    return universe, serves, sections


def load_set(root: Path, name: str) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """Live rows of one requirement set, qualified, and what each IMP serves."""
    universe, serves, _ = _scan_set(root, name)
    return universe, serves


def load_rct(repo: Path) -> Set[str]:
    base = repo / "modules" / "interfaces" / "docs" / "resim_contract"
    uids: Set[str] = set()
    for line in _read(base / "RCT_System_Requirements.md").splitlines():
        m = re.match(BLOCK_RE % "SYS", line)
        if m:
            uids.add(f"RCT:{m.group(1)}")
    for line in _read(base / "RCT_Implementation_Design.md").splitlines():
        m = IMP_RE.match(line)
        if m:
            uids.add(f"RCT:{m.group(1)}")
    return uids


def load_context(root: Path = ROOT) -> Context:
    repo = root.parent.parent
    universe: Dict[str, str] = {}
    serves: Dict[str, List[str]] = {}
    sections: Dict[str, str] = {}
    for name in SETS:
        u, s, sec = _scan_set(root, name)
        universe.update(u)
        serves.update(s)
        sections.update(sec)
    decisions = {
        m.group(1)
        for m in (DECISION_RE.match(l) for l in _read(repo / "VANTAGE_DEV_PLAN.md").splitlines())
        if m
    }
    arch_text = _read(root / "docs" / "VANTAGE_Architecture.md")
    arch_sections = {
        m.group(1) for m in (ARCH_HEAD_RE.match(l) for l in arch_text.splitlines()) if m
    }
    return Context(
        universe, serves, decisions, arch_sections, arch_text, load_rct(repo), root,
        read_seed_entries(root), sections, read_seed_files(root),
    )


# ---------------------------------------------------------------- register --

def _cells(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_separator(cells: List[str]) -> bool:
    return all(re.match(r"^:?-+:?$", c) for c in cells if c) and any(cells)


def parse_scope(text: str) -> List[Tuple[str, str, Optional[int], Optional[int]]]:
    terms = []
    for raw in text.split(","):
        m = SCOPE_TERM_RE.match(raw.strip().strip("`"))
        if m:
            lo = int(m.group(3)) if m.group(3) else None
            hi = int(m.group(4)) if m.group(4) else None
            terms.append((m.group(1), m.group(2), lo, hi))
    return terms


def parse_register(text: str) -> Register:
    reg = Register()
    sections: Dict[str, Section] = {}
    heading = ""
    mode: Optional[str] = None
    unscoped: Optional[Section] = None
    for number, line in enumerate(text.splitlines(), start=1):
        m = HEAD_RE.match(line)
        if m:
            heading, mode = m.group(2), None
            continue
        m = SCOPE_RE.match(line)
        if m:
            sec = sections.get(heading)
            if sec is None:
                sec = sections[heading] = Section(heading)
                reg.sections.append(sec)
            sec.scope = parse_scope(m.group(1))
            continue
        if not line.lstrip().startswith("|"):
            mode = None
            continue
        cells = _cells(line)
        head = [c.lower() for c in cells]
        if head[:4] == ["uid", "disposition", "target", "why"]:
            mode = "rows"
            continue
        if head[:4] == ["path", "disposition", "target", "why"]:
            mode = "code"
            continue
        if mode is None or _is_separator(cells):
            continue
        if mode == "rows":
            sec = sections.get(heading)
            if sec is None:
                if unscoped is None:
                    unscoped = Section("(no scoped section)")
                    reg.sections.append(unscoped)
                sec = unscoped
            sec.rows.append(Row(number, cells))
        else:
            reg.code_rows.append(Row(number, cells))
    return reg


def _clean(cell: str) -> str:
    return cell.replace("`", "").strip()


def _in_scope(scope, uid: str) -> bool:
    m = UID_RE.match(uid)
    if not m:
        return False
    for set_name, kind, lo, hi in scope:
        if m.group(1) == set_name and m.group(2) == kind:
            if lo is None or lo <= int(m.group(3)) <= hi:
                return True
    return False


# ------------------------------------------------------------------ checks --

def check_row_target(ctx: Context, word: str, target: str) -> Optional[str]:
    """None when the Target fits the disposition word, else what is wrong."""
    t = _clean(target)
    if word == "retired":
        return None if t == "—" else "a retired row's Target is the dash"
    terms = [x.strip() for x in t.split(",") if x.strip()]
    if not terms:
        return "Target is empty"
    for term in terms:
        if word == "carried":
            if not re.match(r"^VNT(:[A-Z]+-\d{4})?$", term):
                return f"'{term}' is not VNT or a VNT: UID"
        elif word == "moved":
            if not re.match(r"^RCT:(SYS|IMP)-\d{4}$", term):
                return f"'{term}' is not an RCT:SYS or RCT:IMP UID"
            if term not in ctx.rct_uids:
                return f"{term} does not exist in the contract"
        elif word == "superseded":
            if re.match(r"^D\d+$", term):
                if term not in ctx.decisions:
                    return f"{term} is not a decision in the plan"
            else:
                m = re.match(r"^ARCH §(\d+(?:\.\d+)*)$", term)
                if not m:
                    return f"'{term}' is not D<n> or ARCH §<n>"
                if m.group(1) not in ctx.arch_sections:
                    return f"ARCH §{m.group(1)} is not a section of the architecture"
    return None


def check_code_target(ctx: Context, word: str, target: str) -> Optional[str]:
    t = target.strip()
    if word == "retired":
        return None if _clean(t) == "—" else "a retired row's Target is the dash"
    refs = ARCH_REF_RE.findall(t)
    if not refs:
        return "Target cites no ARCH §<n>"
    for ref in refs:
        if ref not in ctx.arch_sections:
            return f"ARCH §{ref} is not a section of the architecture"
    if word == "replaced":
        paths = [p for p in re.findall(r"`([^`]+)`", t) if "/" in p]
        if not paths:
            return "a replaced row names the new file in backticks"
        for p in paths:
            if p not in ctx.arch_text:
                return f"{p} is not named in the architecture"
    return None


def _read_seed_names(root: Path) -> Optional[List[str]]:
    """File names of the tree at the seed tag, or None when the tag is missing."""
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", "--name-only", SEED_TAG],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return done.stdout.splitlines()


def read_seed_entries(root: Path) -> Optional[List[str]]:
    """Code entries of the tree at the seed tag, or None when the tag is missing."""
    names = _read_seed_names(root)
    return None if names is None else list_code_entries(names)


def read_seed_files(root: Path) -> Optional[List[str]]:
    """Every file of the seed tree under the code roots, or None when the tag is missing."""
    names = _read_seed_names(root)
    return None if names is None else list_seed_files(names)


def list_seed_files(names: List[str]) -> List[str]:
    """Files of a tree under the source roots and scripts/, without ignored names."""
    out: List[str] = []
    for name in names:
        if not any(name.startswith(rel + "/") for rel in CODE_ROOTS + CODE_FILE_ROOTS):
            continue
        parts = name.split("/")
        if any(part in IGNORED_NAMES for part in parts) or name.endswith(".pyc"):
            continue
        out.append(name)
    return sorted(out)


def list_code_entries(names: List[str]) -> List[str]:
    """Entries the code table must cover, from the file names of a tree: everything
    directly under the four source roots and every file directly under scripts/.
    Directories end in /."""
    out: Set[str] = set()
    for name in names:
        for rel in CODE_ROOTS + CODE_FILE_ROOTS:
            if not name.startswith(rel + "/"):
                continue
            first, _, rest = name[len(rel) + 1:].partition("/")
            if first in IGNORED_NAMES or first.endswith(".pyc"):
                continue
            if rest:
                if rel in CODE_FILE_ROOTS:
                    continue
                out.add(f"{rel}/{first}/")
            else:
                out.add(f"{rel}/{first}")
    return sorted(out)


def _code_path(root: Path, cell: str) -> str:
    p = _clean(cell).replace("\\", "/")
    if p and not p.endswith("/") and (root / p).is_dir():
        p += "/"
    return p


def _existed(ctx: Context, path: str) -> bool:
    """A row may name a path that is in the seed tree, even if it is gone now."""
    if (ctx.root / path).exists():
        return True
    return any(
        e == path or e.startswith(path) or (e.endswith("/") and path.startswith(e))
        for e in ctx.code_entries or []
    )


def check_code(ctx: Context, reg: Register, findings: List[str]) -> None:
    seen: Dict[str, int] = {}
    paths: List[str] = []
    for row in reg.code_rows:
        cells = (row.cells + ["", "", "", ""])[:4]
        path = _code_path(ctx.root, cells[0])
        word = _clean(cells[1])
        if len(row.cells) != 4:
            findings.append(f"C-WORD {path}: code row at line {row.line} has {len(row.cells)} cells, expected 4")
        if path in seen:
            findings.append(f"C-CODE {path}: listed twice (lines {seen[path]} and {row.line})")
            continue
        seen[path] = row.line
        if not _existed(ctx, path):
            findings.append(f"C-CODE {path}: no such path under modules/vantage or in {SEED_TAG}")
            continue
        paths.append(path)
        if word not in CODE_WORDS:
            findings.append(f"C-WORD {path}: '{word}' is not a code disposition word")
            continue
        problem = check_code_target(ctx, word, cells[2])
        if problem:
            findings.append(f"C-TARGET {path}: {problem}")
        if word == "retired" and _clean(cells[3]) in ("", "—"):
            findings.append(f"C-WHY {path}: a retired row needs a Why")
    if ctx.code_entries is None:
        findings.append(f"C-SEED {SEED_TAG}: tag not found")
    for entry in ctx.code_entries or []:
        best = None
        for p in paths:
            if p == entry or (p.endswith("/") and entry.startswith(p)):
                if best is None or len(p) > len(best):
                    best = p
        if best is not None:
            continue
        if entry.endswith("/") and ctx.seed_files is not None:
            # A directory with no row is covered when every file under it has a row.
            files = [f for f in ctx.seed_files if f.startswith(entry)]
            uncovered = [
                f for f in files
                if not any(p == f or (p.endswith("/") and f.startswith(p)) for p in paths)
            ]
            if files and not uncovered:
                continue
            if uncovered:
                for f in uncovered:
                    findings.append(f"C-CODE {f}: not covered by any row")
                continue
        findings.append(f"C-CODE {entry}: not covered by any row")


def owner_of(ctx: Context, reg: Register, uid: str) -> Optional[Section]:
    """The section that must dispose uid. An IMP follows its first SW."""
    key = uid
    if ctx.universe.get(uid) == "IMP":
        sws = ctx.serves.get(uid) or []
        if not sws:
            return None
        key = sws[0]
    for sec in reg.sections:
        if _in_scope(sec.scope, key):
            return sec
    return None


def _section_members(ctx: Context, pairs: Set[Tuple[str, str]], label: str) -> Set[str]:
    """Live rows of the given (set, kind) pairs that lie in the whole section `label`."""
    out: Set[str] = set()
    for uid, kind in ctx.universe.items():
        if (uid.split(":")[0], kind) not in pairs:
            continue
        have = ctx.sections.get(uid, "")
        if not label.startswith("§"):
            if have == label:
                out.add(uid)
        elif have.startswith("§") and (have == label or have.startswith(label + ".")):
            out.add(uid)
    return out


def expand_section_row(ctx: Context, cell: str, why: str) -> Tuple[List[str], List[str]]:
    """The universe rows a section row covers, and what is wrong with it."""
    uids: List[str] = []
    problems: List[str] = []
    pairs: Set[Tuple[str, str]] = set()
    for raw in cell.split(","):
        term = raw.strip()
        m = RANGE_RE.match(term)
        if m:
            lo, hi = int(m.group(3)), int(m.group(4))
            if lo > hi:
                problems.append(f"'{term}' is reversed")
                continue
        else:
            m = UID_RE.match(term)
            if not m:
                problems.append(f"'{term}' is not a range or a UID")
                continue
            lo = hi = int(m.group(3))
        if m.group(2) == "IMP":
            problems.append(f"'{term}' names IMP rows; implementation rows inherit")
            continue
        got = sorted(
            u for u in ctx.universe
            if u.split(":")[0] == m.group(1) and ctx.universe[u] == m.group(2)
            and lo <= int(u[-4:]) <= hi
        )
        if not got:
            problems.append(f"'{term}' expands to no row of the universe")
            continue
        uids += got
        pairs.add((m.group(1), m.group(2)))
    label = None
    m = WHY_LABEL_RE.match(why)
    if m:
        label = m.group(1)
    else:
        for known in sorted(set(ctx.sections.values()), key=len, reverse=True):
            if not known.startswith("§") and why.startswith(known + " — "):
                label = known
                break
    if label is None:
        problems.append("the Why does not start with a section label followed by ' — '")
    elif len(pairs) > 1:
        problems.append("the terms mix sets or kinds")
    elif pairs:
        want = _section_members(ctx, pairs, label)
        have = set(uids)
        if want - have:
            problems.append(f"{sorted(want - have)[0]} is in {label} but not covered")
        elif have - want:
            problems.append(f"{sorted(have - want)[0]} is not in {label}")
    return uids, problems


def run_checks(ctx: Context, reg: Register) -> Tuple[List[str], List[str]]:
    """Returns (findings, summary lines)."""
    findings: List[str] = []
    listed: Dict[str, str] = {}  # uid -> word
    first_line: Dict[str, int] = {}
    in_section: Dict[str, Set[str]] = {sec.name: set() for sec in reg.sections}

    for sec in reg.sections:
        for row in sec.rows:
            cells = (row.cells + ["", "", "", ""])[:4]
            cell = _clean(cells[0])
            word = _clean(cells[1])
            section_row = ".." in cell
            uids = [cell]
            if section_row:
                uids, problems = expand_section_row(ctx, cell, cells[3].strip())
                findings += [f"C-RANGE {cell}: {p}" for p in problems]
                if len(row.cells) != 4:
                    findings.append(f"C-WORD {cell}: row at line {row.line} has {len(row.cells)} cells, expected 4")
                if word not in ROW_WORDS:
                    findings.append(f"C-WORD {cell}: '{word}' is not a row disposition word")
                else:
                    problem = check_row_target(ctx, word, cells[2])
                    if problem:
                        findings.append(f"C-TARGET {cell}: {problem}")
                    if word == "retired" and cells[3].strip().partition(" — ")[2].strip() in ("", "—"):
                        findings.append(f"C-WHY {cell}: a retired row needs a Why")
            for uid in uids:
                if uid in first_line:
                    findings.append(
                        f"C-DUPLICATE {uid}: listed twice (lines {first_line[uid]} and {row.line})"
                    )
                    continue
                first_line[uid] = row.line
                if not section_row and len(row.cells) != 4:
                    findings.append(f"C-WORD {uid}: row at line {row.line} has {len(row.cells)} cells, expected 4")
                if uid not in ctx.universe:
                    findings.append(f"C-UNKNOWN {uid}: not a live row of either set")
                    continue
                if owner_of(ctx, reg, uid) is not sec:
                    findings.append(f"C-UNKNOWN {uid}: outside the scope of the section '{sec.name}'")
                    continue
                listed[uid] = word
                in_section[sec.name].add(uid)
                if section_row:
                    continue
                if word not in ROW_WORDS:
                    findings.append(f"C-WORD {uid}: '{word}' is not a row disposition word")
                    continue
                problem = check_row_target(ctx, word, cells[2])
                if problem:
                    findings.append(f"C-TARGET {uid}: {problem}")
                if word == "retired" and _clean(cells[3]) in ("", "—"):
                    findings.append(f"C-WHY {uid}: a retired row needs a Why")

    inherited: Set[str] = set()
    for uid in sorted(u for u, k in ctx.universe.items() if k == "IMP"):
        sws = ctx.serves.get(uid) or []
        words = [listed.get(sw) for sw in sws]
        all_listed = bool(sws) and all(w is not None for w in words)
        agree = all_listed and len(set(words)) == 1
        if uid in listed:
            if agree:
                findings.append(
                    f"C-REDUNDANT {uid}: every SW row it serves is '{words[0]}'; it inherits, do not list it"
                )
        elif agree:
            inherited.add(uid)
        elif all_listed:
            pairs = ", ".join(f"{sw} {w}" for sw, w in zip(sws, words))
            findings.append(f"C-INHERIT {uid}: its SW rows disagree ({pairs}); list it")
        else:
            findings.append(f"C-MISSING {uid}: no disposition, and a SW row it serves has none")
    for uid in sorted(ctx.universe):
        if ctx.universe[uid] != "IMP" and uid not in listed:
            findings.append(f"C-MISSING {uid}: no disposition")

    check_code(ctx, reg, findings)

    summary: List[str] = []
    members: Dict[str, Set[str]] = {sec.name: set() for sec in reg.sections}
    members["(no section)"] = set()
    for uid in ctx.universe:
        sec = owner_of(ctx, reg, uid)
        members[sec.name if sec else "(no section)"].add(uid)
    tot = [0, 0, 0, 0]
    for name, uids in members.items():
        if not uids and name == "(no section)":
            continue
        n_listed = len(uids & set(listed))
        n_inh = len(uids & inherited)
        row = [len(uids), n_listed, n_inh, len(uids) - n_listed - n_inh]
        tot = [a + b for a, b in zip(tot, row)]
        summary.append(
            f"{name}: universe {row[0]}, listed {row[1]}, inherited {row[2]}, missing {row[3]}"
        )
    summary.append(
        f"total: universe {tot[0]}, listed {tot[1]}, inherited {tot[2]}, missing {tot[3]}"
    )
    return findings, summary


# ---------------------------------------------------------------- selftest --

BASE_SCOPES = {
    "4.1 Concept and system": "SIM:CN, SIM:SYS",
    "4.2 Software": "SIM:SW-0001..0002",
}
BASE_ROWS: Dict[str, List[Tuple[str, str, str, str]]] = {
    "4.1 Concept and system": [
        ("SIM:CN-0001", "carried", "VNT", "kept"),
        ("SIM:CN-0002", "moved", "RCT:SYS-0001", "now in the contract"),
        ("SIM:SYS-0001", "superseded", "D13", "viewer is out"),
    ],
    "4.2 Software": [
        ("SIM:SW-0001", "carried", "VNT", "kept"),
        ("SIM:SW-0002", "carried", "VNT", "kept"),
    ],
}
BASE_CODE: List[Tuple[str, str, str, str]] = [
    ("src/simcore/", "reused", "Runner, ARCH §3.3", "kept"),
    ("src/simcore/bus/", "corrected", "Sample buffers, ARCH §3.4", "gains buffers"),
    ("src/simengine/main.cpp", "corrected", "Supervisor, ARCH §3.7", "supervise flag"),
    ("src/adas_sim/__init__.py", "reused", "Launcher, ARCH §3.1", "package root"),
    ("include/simcore/h.hpp", "replaced", "`include/vantage/new.h`, ARCH §11", "new header"),
    ("src/simengine/pkg/a.py", "reused", "Runner, ARCH §3.3", "kept"),
    ("src/simengine/pkg/b.py", "reused", "Runner, ARCH §3.3", "kept"),
    ("scripts/a.py", "retired", "—", "no longer needed"),
]
SELF_ARCH = "## 3. Parts\n### 3.1 Launcher\n### 3.3 Runner\n### 3.4 Buffers\n### 3.7 Supervisor\n## 11. Code\ninclude/vantage/new.h\n"


SELF_SEED = [
    "src/simcore/bus/x.cpp",
    "src/simengine/main.cpp",
    "src/adas_sim/__init__.py",
    "src/simengine/pkg/a.py",
    "src/simengine/pkg/b.py",
    "include/simcore/h.hpp",
    "scripts/a.py",
    "scripts/sub/deep.py",
    "src/simcore/__pycache__/x.pyc",
]


def render_register(rows, code) -> str:
    out = []
    for name, entries in rows.items():
        out += [f"### {name}", "", f"Scope: {BASE_SCOPES[name]}", ""]
        out += ["| UID | Disposition | Target | Why |", "|---|---|---|---|"]
        out += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in entries]
        out.append("")
    out += ["### Code", "", "| Path | Disposition | Target | Why |", "|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in code]
    return "\n".join(out) + "\n"


def make_tree(root: Path) -> None:
    for rel in (
        "src/simcore/bus/x.cpp",
        "src/simengine/main.cpp",
        "src/adas_sim/__init__.py",
        "include/simcore/h.hpp",
        "scripts/a.py",
    ):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")


def make_context(root: Path) -> Context:
    universe = {
        "SIM:CN-0001": "CN",
        "SIM:CN-0002": "CN",
        "SIM:SYS-0001": "SYS",
        "SIM:SW-0001": "SW",
        "SIM:SW-0002": "SW",
        "SIM:IMP-0001": "IMP",
    }
    serves = {"SIM:IMP-0001": ["SIM:SW-0001", "SIM:SW-0002"]}
    return Context(
        universe, serves, {"D13"}, {"3", "3.1", "3.3", "3.4", "3.7", "11"}, SELF_ARCH,
        {"RCT:SYS-0001"}, root, list_code_entries(SELF_SEED),
        {"SIM:CN-0001": "§1", "SIM:CN-0002": "§2", "SIM:SYS-0001": "§1"},
        list_seed_files(SELF_SEED),
    )


def planted_cases() -> List[Tuple[str, str, str, str]]:
    """(check id, uid or path expected in the finding, register text, label)."""
    def rows(mod=None):
        r = {k: list(v) for k, v in BASE_ROWS.items()}
        if mod:
            mod(r)
        return r

    def code(mod=None):
        c = list(BASE_CODE)
        if mod:
            mod(c)
        return c

    def setrow(sec, idx, **kw):
        def f(r):
            a, b, c, d = r[sec][idx]
            r[sec][idx] = (a, kw.get("word", b), kw.get("target", c), kw.get("why", d))
        return f

    cases = [
        ("C-MISSING", "SIM:CN-0002", render_register(rows(lambda r: r["4.1 Concept and system"].pop(1)), code())),
        ("C-DUPLICATE", "SIM:CN-0001",
         render_register(rows(lambda r: r["4.1 Concept and system"].append(("SIM:CN-0001", "carried", "VNT", "x"))), code())),
        ("C-UNKNOWN", "SIM:CN-9999",
         render_register(rows(lambda r: r["4.1 Concept and system"].append(("SIM:CN-9999", "carried", "VNT", "x"))), code())),
        ("C-WORD", "SIM:CN-0001", render_register(rows(setrow("4.1 Concept and system", 0, word="kept")), code())),
        ("C-TARGET", "SIM:CN-0002",
         render_register(rows(setrow("4.1 Concept and system", 1, target="RCT:SYS-9999")), code())),
        ("C-WHY", "SIM:SYS-0001",
         render_register(rows(setrow("4.1 Concept and system", 2, word="retired", target="—", why="")), code())),
        ("C-INHERIT", "SIM:IMP-0001",
         render_register(rows(setrow("4.2 Software", 1, word="retired", target="—")), code())),
        ("C-REDUNDANT", "SIM:IMP-0001",
         render_register(rows(lambda r: r["4.2 Software"].append(("SIM:IMP-0001", "carried", "VNT", "x"))), code())),
        ("C-CODE", "scripts/a.py", render_register(rows(), code(lambda c: c.pop()))),
        ("C-CODE", "src/simengine/pkg/b.py",
         render_register(rows(), code(lambda c: c.remove(BASE_CODE[6])))),
        ("C-RANGE", "SIM:CN-0001..0002",
         render_register(rows(lambda r: r["4.1 Concept and system"].__setitem__(
             slice(0, 2), [("SIM:CN-0001..0002", "carried", "VNT", "§1 — one section")])), code())),
    ]
    return cases


def selftest() -> List[str]:
    """Plants one violation per check. Returns the failures (empty = all caught)."""
    failures: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_tree(root)
        ctx = make_context(root)
        base, _ = run_checks(ctx, parse_register(render_register(BASE_ROWS, BASE_CODE)))
        if base:
            failures.append(f"baseline is not clean: {base}")
        for check, where, text in planted_cases():
            found, _ = run_checks(ctx, parse_register(text))
            if not any(f.startswith(f"{check} {where}:") for f in found):
                failures.append(f"{check} planted at {where} was not caught")
    return failures


# -------------------------------------------------------------------- main --

def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Check the Vantage migration register (D15).")
    parser.add_argument("--register", type=Path, default=ROOT / "docs" / "VANTAGE_Migration_Register.md")
    parser.add_argument("--selftest", action="store_true", help="plant one violation per check")
    args = parser.parse_args(argv)

    if args.selftest:
        failures = selftest()
        for f in failures:
            print(f"SELFTEST FAIL: {f}")
        print(f"selftest: {len(planted_cases())} planted violations, {len(failures)} not caught")
        return 1 if failures else 0

    ctx = load_context()
    reg = parse_register(_read(args.register))
    findings, summary = run_checks(ctx, reg)
    for line in summary:
        print(line)
    for line in findings:
        print(line)
    print(f"{len(findings)} findings")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
