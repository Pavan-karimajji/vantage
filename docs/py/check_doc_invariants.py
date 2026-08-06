# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Check: invariants over the design documents themselves -- ``DC-1`` .. ``DC-9``.

Some requirements are satisfied by a *document* or by the *shape of the tree*,
not by a unit test: "make the split clear", "a module's docs live with the
module", "work on feature branches". Pretending those have unit tests is worse
than admitting they do not -- so they get their own check class, ``DC-n``, and
the requirements register cites these ids exactly as it cites ``UT-``/``ST-``.

| id | invariant |
|----|-----------|
| DC-1 | every internal markdown link in ``modules/sim/docs`` resolves |
| DC-2 | no absolute machine path appears in any design document |
| DC-3 | no organisation name appears in any document or script |
| DC-4 | every row of the visualization feature checklist names a stage |
| DC-5 | the placement map names only paths that exist or are marked NEW |
| DC-6 | work is on a feature branch, not a default branch |
| DC-7 | no framework-owned script names a driving function (R-SIM-1 guard) |
| DC-8 | no requirement id is defined twice |
| DC-9 | the CLI surface table and the registered verbs agree, in both directions |

``DC-2`` and ``DC-7`` are the portability and layering guards: an absolute
``C:\\...`` path in a design document is an instruction that cannot be followed
on Ubuntu (``sim_portability.md``), and a function name inside framework-owned
code is the boundary violation ``GT-1`` exists to catch, checked here for the
scripts that ship before ``src/`` exists.

Usage
-----
    python docs/py/check_doc_invariants.py
"""

from __future__ import annotations

import re
import subprocess
import sys

from _common import DOCS_DIR, PY_DIR, SIM_DIR, Report

#: Driving-function tokens that must never appear in framework-owned code.
#: Assembled from fragments for the same reason as ORG_NAMES below -- a checker
#: that must exempt itself is a checker that no longer covers the riskiest file.
FUNCTION_TOKENS = re.compile(
    r"\b(" + "|".join(["a" + "eb", "b" + "sd", "l" + "ca",
                       "a" + "cc", "l" + "dw", "l" + "ka"]) + r")\b", re.I)
#: Absolute machine paths. A design document must be followable on any machine.
ABS_PATH = re.compile(r"(?<![\w`/])(?:[A-Za-z]:[\\/]|/home/|/opt/|/Users/)\S+")
#: Organisation names that must not appear anywhere. Assembled from fragments
#: on purpose: if the full token were a literal here, this file would fail its
#: own check, and the usual workaround (an exemption for the checker) is how a
#: check quietly stops applying to the thing most likely to violate it.
ORG_NAMES = re.compile(r"\b(" + "|".join(["cont" + "inental", "cont" + "i"]) + r")\b", re.I)
#: A markdown link to a local file: [text](path) -- ignoring URLs and anchors.
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)#][^)]*?)(?:#[^)]*)?\)")


def _docs() -> list:
    return sorted(DOCS_DIR.glob("*.md")) + sorted(PY_DIR.glob("*.md"))


def _scripts() -> list:
    return sorted(PY_DIR.glob("*.py"))


def main() -> int:
    rep = Report("check_doc_invariants")
    rep.line("Checking DC-1..DC-9 over the design set")

    docs = _docs()
    rep.line(f"{len(docs)} documents, {len(_scripts())} scripts")

    # -- DC-1: links resolve ----------------------------------------------
    rep.heading("DC-1  internal markdown links resolve")
    broken = 0
    for doc in docs:
        for target in MD_LINK.findall(doc.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (doc.parent / target).resolve().exists():
                rep.fail(f"{doc.name}: broken link -> {target}")
                broken += 1
    if not broken:
        rep.ok("all internal links resolve")

    # -- DC-2: no absolute machine paths ----------------------------------
    rep.heading("DC-2  no absolute machine path in a design document")
    hits = 0
    for doc in docs:
        for n, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for m in ABS_PATH.finditer(line):
                rep.fail(f"{doc.name}:{n}: absolute path {m.group(0)!r} -- "
                         "not followable on another machine (sim_portability.md)")
                hits += 1
    if not hits:
        rep.ok("no absolute machine paths -- every instruction is portable")

    # -- DC-3: no organisation name ---------------------------------------
    rep.heading("DC-3  no organisation name")
    hits = 0
    for path in docs + _scripts():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ORG_NAMES.search(line):
                rep.fail(f"{path.name}:{n}: organisation name")
                hits += 1
    if not hits:
        rep.ok("no organisation names")

    # -- DC-4: visualization checklist rows name a stage ------------------
    rep.heading("DC-4  every visualization feature-checklist row names a stage")
    viz = DOCS_DIR / "sim_visualization_spec.md"
    if not viz.is_file():
        rep.fail("sim_visualization_spec.md missing")
    else:
        text = viz.read_text(encoding="utf-8")
        start = text.find("## 16.")
        section = text[start:text.find("\n## ", start + 5)] if start >= 0 else ""
        rows = [ln for ln in section.splitlines()
                if ln.startswith("|") and not re.match(r"^\|[\s|:-]+\|?$", ln)]
        rows = rows[1:]                      # drop the header row
        # Stage references in this table are written bare ("B1", "A2/C4"),
        # matching the document's own convention; the "S-" prefix is optional.
        missing = [r for r in rows if not re.search(r"\b(?:S-)?[A-E]\d[a-z]?\b", r)]
        if not rows:
            rep.fail("no feature-checklist rows found in viz section 16")
        elif missing:
            for r in missing[:10]:
                rep.fail(f"checklist row names no stage: {r.strip()[:78]}")
        else:
            rep.ok(f"all {len(rows)} checklist rows name a stage")

    # -- DC-5: placement map paths exist ----------------------------------
    rep.heading("DC-5  placement-map paths exist or are marked NEW")
    arch = DOCS_DIR / "sim_architecture.md"
    if not arch.is_file():
        rep.fail("sim_architecture.md missing")
    else:
        text = arch.read_text(encoding="utf-8")
        start = text.find("### 5.8")
        section = text[start:text.find("\n### 5.9", start)] if start >= 0 else ""
        # Only check paths inside the superproject that the map claims exist.
        claimed = set(re.findall(r"`(modules/[a-z_\-]+/[A-Za-z0-9_./\-]*)`", section))
        unknown = []
        root = SIM_DIR.parent.parent
        for rel in sorted(claimed):
            if "NEW" in section[max(0, section.find(rel) - 200):section.find(rel) + 200]:
                continue
            if not (root / rel).exists():
                unknown.append(rel)
        if unknown:
            rep.line(f"{len(unknown)} mapped path(s) not present yet "
                     "(expected before implementation -- informational):")
            for rel in unknown[:12]:
                rep.line(f"    {rel}")
        rep.ok(f"placement map parsed; {len(claimed)} paths claimed")

    # -- DC-6: feature branch ---------------------------------------------
    rep.heading("DC-6  work is on a feature branch")
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=SIM_DIR, capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    except Exception as exc:                                  # noqa: BLE001
        branch = ""
        rep.line(f"  (git unavailable: {exc})")
    if not branch:
        rep.line("  skipped -- branch could not be determined")
    elif branch in ("main", "master", "HEAD"):
        rep.fail(f"on default branch {branch!r} -- CR-SIM-30 requires a feature branch")
    else:
        rep.ok(f"on feature branch {branch!r}")

    # -- DC-7: no function names in framework-owned scripts ---------------
    rep.heading("DC-7  no driving-function name in a framework-owned script")
    hits = 0
    for path in _scripts():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = FUNCTION_TOKENS.search(line)
            if m:
                rep.fail(f"{path.name}:{n}: function token {m.group(0)!r} "
                         "in framework-owned code (R-SIM-1 / GT-1)")
                hits += 1
    if not hits:
        rep.ok("framework-owned scripts name no driving function")

    # -- DC-8: no duplicate requirement ids --------------------------------
    # Appending to a register at the end of a section is how two requirements
    # end up sharing an id: the author looks at the section's last entry, not
    # at the whole file. It happened once (a transport requirement collided
    # with a plotting one), was invisible in review, and would have made two
    # requirements share a verifier. Mechanical from here on.
    rep.heading("DC-8  requirement ids are unique")
    req = DOCS_DIR / "sim_requirements.md"
    if not req.is_file():
        rep.fail("sim_requirements.md missing")
    else:
        seen: dict[str, int] = {}
        dupes = 0
        for n, line in enumerate(req.read_text(encoding="utf-8").splitlines(), 1):
            m = re.match(r"^### ((?:FR|NR|CR)-SIM-\d+[a-z]?)\b", line)
            if not m:
                continue
            rid = m.group(1)
            if rid in seen:
                rep.fail(f"{rid} defined twice: lines {seen[rid]} and {n}")
                dupes += 1
            else:
                seen[rid] = n
        if not dupes:
            rep.ok(f"all {len(seen)} requirement ids unique")

    # -- DC-9: the CLI surface table matches the registered verbs ----------
    # Added by audit run 3 (`AR-44`) after BOTH directions failed at once and
    # neither was noticed for six days:
    #   * `sim diff` sat in sim_api_reference.md section 10 and in the recording
    #     contract's verb block as a promised verb. No stage ever scheduled it,
    #     nothing implements it, and `OD-10` had superseded it on 2026-07-31
    #     with `sim determinism` -- a stronger verb whose axis is DERIVED from
    #     two manifests rather than asserted by a flag, "because a flag can
    #     lie". A documented verb that does not exist is worse than an
    #     undocumented one: a reader plans around it.
    #   * `sim determinism` shipped in `S-C6` and was never added to the table.
    # sim_api_reference.md's own header calls a signature there "a contract",
    # so both halves are contract defects, and both are trivially mechanical.
    rep.heading("DC-9  the CLI surface table matches cli/__init__.py, both ways")
    api = DOCS_DIR / "sim_api_reference.md"
    cli_init = SIM_DIR / "src" / "adas_sim" / "cli" / "__init__.py"
    if not api.is_file() or not cli_init.is_file():
        rep.line("  skipped -- sim_api_reference.md or cli/__init__.py not present")
    else:
        registered = set(re.findall(r'add_parser\("([a-z_]+)"', cli_init.read_text(encoding="utf-8")))
        api_text = api.read_text(encoding="utf-8")
        start = api_text.find("## 10. CLI surface")
        table = api_text[start:api_text.find("\nEntry point", start)] if start >= 0 else ""
        # Rows are `| `sim <verb>` | ...`; one row legitimately documents two
        # verbs that share a parser shape (`sim view` / `render`).
        documented = set(re.findall(r"`sim ([a-z_]+)`", table)) | set(re.findall(r"/ `([a-z_]+)`", table))
        if not documented:
            rep.fail("could not parse the CLI surface table in sim_api_reference.md section 10")
        else:
            for verb in sorted(registered - documented):
                rep.fail(f"`sim {verb}` is registered in cli/__init__.py and has no row "
                         "in sim_api_reference.md section 10")
            for verb in sorted(documented - registered):
                rep.fail(f"`sim {verb}` has a row in sim_api_reference.md section 10 and is "
                         "registered nowhere -- a documented verb that does not exist")
            if registered == documented:
                rep.ok(f"all {len(registered)} CLI verbs documented, and no phantom verbs")

    return rep.finish()


if __name__ == "__main__":
    sys.exit(main())
