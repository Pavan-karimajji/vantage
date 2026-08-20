# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Evidence for FR-SIM-45 and FR-SIM-46 -- the cost of binding an opaque DLL.

FR-SIM-45 records the complaint this platform is designed against: developers
could not flexibly tweak the inputs of a run, and the tool felt
over-configured. "Over-configured" is a feeling until it is a number.

This script produces the number. It reads a comparable console's own shipped
DLL-wrapper example and measures, per wrapped function call, how many
configuration elements a human had to author to bind one ``exec()``: argument
positions, per-field value-handling rules, glob patterns and URI rewrite rules.

Two design decisions rest on the result:

* ``R-SIM-15`` -- the per-port override verb list is **closed** (const / hold /
  offset / scale). The comparable tool's open pattern-and-rewrite grammar is
  what an unbounded one becomes.
* ``arch 5.16.1`` -- ``sim probe`` plus a manifest removes the mapping step
  entirely for components we own, so this cost is never paid by default.

The measurement is of a *tool doing something reasonable* -- the comparable
wrapper is verbose because the DLL is opaque and it recovers signatures from
debug symbols. The finding is not that it is badly built; it is that we must
not inherit its cost when our binaries are not opaque.

Usage
-----
    python docs/py/FR_SIM_45_argument_binding_survey.py
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET

from _common import Report, read_text, comparable_tool_root, comparable_tool_schema


def main() -> int:
    rep = Report("FR_SIM_45_argument_binding_survey")
    rep.line("FR-SIM-45 -- how much hand-written config does binding one exec() cost?")
    rep.line("Measured on a comparable console's own shipped DLL-wrapper example.")

    root = comparable_tool_root()
    if root is None:
        rep.skip("no comparable tool installation found "
                 "(set ADAS_SIM_COMPARABLE_TOOL to a directory)")
        return rep.finish()

    schema = comparable_tool_schema()
    call_tag = schema["call_config_tag"]
    gui_tag = schema["gui_state_tag"]
    #: Element tags that represent one authored decision in the binding config.
    authored_tags = tuple(schema["authored_tags"])

    projects = (sorted((root / "Examples").rglob(f"*{schema['project_ext']}"))
                if (root / "Examples").is_dir() else [])
    wrapper_projects = [p for p in projects if call_tag in read_text(p)]
    if not wrapper_projects:
        rep.skip("no example project wires a DLL wrapper -- nothing to measure")
        return rep.finish()

    grand_total = 0
    grand_calls = 0

    for proj in wrapper_projects:
        text = read_text(proj)
        rep.heading(f"{proj.name}")

        # Total file size vs. the part that is actually pipeline wiring.
        gui_state = re.search(rf"<{gui_tag}>.*?</{gui_tag}>", text, re.S)
        gui_chars = len(gui_state.group(0)) if gui_state else 0
        rep.line(f"file size            {len(text):>6} chars")
        rep.line(f"window/dock state    {gui_chars:>6} chars "
                 f"({(gui_chars / len(text) * 100):.0f}% of the project file)")
        rep.line("  ^ arch 5.16.4: window layout must not live in the pipeline file")

        try:
            tree = ET.fromstring(text)
        except ET.ParseError as exc:
            rep.fail(f"{proj.name}: unparseable XML ({exc})")
            continue

        rows = []
        for call in tree.iter(call_tag):
            fn = (call.findtext("FunctionName") or "?").strip()
            counts = {tag: sum(1 for _ in call.iter(tag)) for tag in authored_tags}
            authored = sum(counts.values())
            grand_total += authored
            grand_calls += 1
            rows.append([fn, *(counts[tag] for tag in authored_tags), authored])

        if rows:
            rep.line("")
            rep.table(
                ["wrapped function", "args", "field rules", "uri rewrites",
                 "triggers", "authored"],
                rows,
            )

    # -- the finding -------------------------------------------------------
    rep.heading("Finding")
    if grand_calls:
        avg = grand_total / grand_calls
        rep.line(f"{grand_calls} wrapped call(s), {grand_total} authored config "
                 f"elements, mean {avg:.1f} per call.")
        rep.line("")
        rep.line("Each element is a decision a human made and a future reader must")
        rep.line("re-derive. None of it is recoverable from the binary, because the")
        rep.line("binary does not describe itself.")
        rep.line("")
        rep.line("Here (R-SIM-4): adasManifest() names every port and its schema, so")
        rep.line("the equivalent cost is 0 -- `sim probe <lib>` prints the port set")
        rep.line("and the pipeline wires by name. The cost above is paid only by")
        rep.line("`impl: legacy:` stages, for binaries that cannot carry a manifest.")
        rep.line("")
        rep.line("R-SIM-15 consequence: the override grammar stays CLOSED at four")
        rep.line("verbs. The rules measured above are what an open grammar becomes.")
        if avg >= 5:
            rep.ok(f"mean {avg:.1f} authored elements per exec() confirms the "
                   "over-configuration finding recorded in FR-SIM-45")
    else:
        rep.line("no wrapped calls found")

    return rep.finish()


if __name__ == "__main__":
    sys.exit(main())
