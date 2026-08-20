# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Evidence for FR-SIM-46 -- "one tool, not two".

FR-SIM-46 asks whether the project-scale player and the developer-facing
DLL-resim/wiring tool should be one product or two. Architecture section 5.16
answers "one engine, two faces", and its central claim is a *mapping*: nearly
every concept in a comparable console corresponds to something this
architecture already has, and the single genuine difference (binding to an
opaque binary) is a stage adapter rather than a second product.

That claim is only worth anything if it was measured. This script measures it:
it enumerates the comparable installation's own component/machine inventory and
its shipped example pipelines, and prints them beside the concept each maps to
here. Re-run it against a newer release of that tool to find concepts we have not
accounted for -- those are the rows that would reopen the two-tool question.

Usage
-----
    python docs/py/FR_SIM_46_comparable_tool_survey.py

Set ``ADAS_SIM_COMPARABLE_TOOL`` if the installation is not in a conventional
place. Skips cleanly when it is absent.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

from _common import (
    Report,
    read_text,
    comparable_tool_root,
    comparable_tool_schema,
    comparable_tool_concept_map,
)

#: A mapping value carrying one of these markers is *accounted for*, not a gap.
ACCOUNTED_MARKERS = ("PARKED", "OUT OF SCOPE", "--")


def main() -> int:
    rep = Report("FR_SIM_46_comparable_tool_survey")
    rep.line("FR-SIM-46 -- comparable console concept inventory vs. this architecture")
    rep.line("Answers: is there a concept over there with no home over here?")

    root = comparable_tool_root()
    if root is None:
        rep.skip("no comparable tool installation found "
                 "(set ADAS_SIM_COMPARABLE_TOOL to a directory)")
        return rep.finish()
    rep.line(f"root: {root}")

    concept_map = comparable_tool_concept_map()
    if concept_map is None:
        rep.skip("no comparable-tool concept map supplied (set "
                 "ADAS_SIM_COMPARABLE_TOOL_CONCEPT_MAP to a JSON file, or add "
                 "docs/py/comparable_tool_concept_map.json) -- the map's keys "
                 "are the installation's own component/machine inventory, so "
                 "no default ships in this repo")
        return rep.finish()
    project_ext = comparable_tool_schema()["project_ext"]

    # -- 1. inventory ------------------------------------------------------
    discovered: list[tuple[str, str]] = []
    for kind, sub in (("component", "Components"), ("machine", "Machines")):
        d = root / sub
        if not d.is_dir():
            continue
        for entry in sorted(p.name for p in d.iterdir() if p.is_dir()):
            discovered.append((kind, entry))

    if not discovered:
        rep.skip(f"{root} has no Components/ or Machines/ directory -- "
                 "not a comparable tool installation")
        return rep.finish()

    # An installation ships only the subset of components it was licensed for,
    # but the example projects REFERENCE every component the tool knows about.
    # Surveying only what is installed under-counts the concept inventory --
    # this is how the timeline-bookmark gap was found.
    installed = {name for _, name in discovered}
    for proj in (sorted((root / "Examples").rglob(f"*{project_ext}"))
                 if (root / "Examples").is_dir() else []):
        try:
            tree = ET.fromstring(read_text(proj))
        except ET.ParseError:
            continue
        container = tree.find("Components")
        for comp in (container.findall("Component") if container is not None else []):
            stem = comp.findtext("DllPath", "").rsplit("\\", 1)[-1]
            stem = stem[:-4] if stem.lower().endswith(".dll") else stem
            if stem and stem not in installed:
                installed.add(stem)
                discovered.append(("referenced", stem))
    discovered.sort(key=lambda kv: (kv[0], kv[1].lower()))

    rep.heading("1. Inventory, mapped")
    rows, real_gaps = [], []
    for kind, name in discovered:
        key = name.lower()
        mapped = next((v for k, v in concept_map.items() if k in key), None)
        if mapped is None:
            real_gaps.append(name)
            mapped = "?? UNMAPPED -- review"
        rows.append([kind, name, mapped])
    rep.table(["kind", "reference name", "maps to here"], rows)

    # -- 2. shipped example pipelines -------------------------------------
    # Parsed as XML, not by regex: <Name> appears inside many unrelated config
    # blocks, and a regex pairing it with the next <DllPath> silently spans
    # them. (This script's first draft did exactly that -- kept as a caution.)
    rep.heading("2. Shipped example pipelines -- how a chain is actually wired")
    examples = root / "Examples"
    if examples.is_dir():
        for proj in sorted(examples.rglob(f"*{project_ext}")):
            try:
                tree = ET.fromstring(read_text(proj))
            except ET.ParseError as exc:
                rep.fail(f"{proj.name}: unparseable XML ({exc})")
                continue
            container = tree.find("Components")
            if container is None:
                continue
            stages = [
                (c.findtext("Name", "?").strip(),
                 c.findtext("DllPath", "").rsplit("\\", 1)[-1])
                for c in container.findall("Component")
            ]
            if not stages:
                continue
            rep.line(f"\n  {proj.relative_to(examples)}  ({len(stages)} stages)")
            for name, dll in stages:
                rep.line(f"      {name:<22} {dll}")
    else:
        rep.line("  (no Examples/ directory)")

    # -- 3. the finding ----------------------------------------------------
    rep.heading("3. Finding")
    if real_gaps:
        rep.line("Concepts with no counterpart and no recorded decision:")
        for name in real_gaps:
            rep.line(f"  - {name}")
        rep.line("")
        rep.line("Each must become (a) a stage in sim_implementation_plan.md, or")
        rep.line("(b) a recorded park in sim_requirements.md section 10.")
        rep.line("An unreviewed entry here is what reopens the two-tool question,")
        rep.line("so this list must be empty or explained -- never merely present.")
        rep.fail(f"{len(real_gaps)} unreviewed comparable-tool concept(s)")
    else:
        rep.ok("every discovered concept maps to a stage, codec, renderer, or a "
               "recorded park/out-of-scope decision -- arch 5.16's table is "
               "complete for this release")

    for marker, label in (("PARKED", "parked"),
                          ("OUT OF SCOPE", "out of scope (no requirement yet)")):
        hits = sorted({v for v in concept_map.values() if marker in v})
        rep.line(f"\nDeliberately {label}: {len(hits)}")
        for h in hits:
            rep.line(f"  - {h}")

    return rep.finish()


if __name__ == "__main__":
    sys.exit(main())
