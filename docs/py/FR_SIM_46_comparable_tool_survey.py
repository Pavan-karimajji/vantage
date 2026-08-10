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

from _common import Report, read_text, comparable_tool_root

#: The mapping architecture section 5.16 asserts. Keys are matched as
#: case-insensitive substrings of a discovered component/machine directory
#: name. "--" means deliberately unmapped, which is a finding, not a bug.
CONCEPT_MAP: dict[str, str] = {
    "bsigreader":     "io/ codec (reader)               R-SIM-14",
    "bsigwriter":     "io/ codec (writer)               R-SIM-14 / S-D7",
    "rrecreader":     "io/ codec (reader)               R-SIM-14",
    "dllwrapper":     "impl: dll:  / impl: legacy:      R-SIM-10 / arch 5.16.1",
    "integratedpython": "impl: stub:                    R-SIM-10",
    "externalpython": "impl: stub:                      R-SIM-10",
    "viewer2d":       "renderer + layer providers       R-SIM-2 / R-SIM-13",
    "signalplot":     "plots panel                      viz 7.4",
    "signalexplorer": "signal explorer                  PARKED, arch 5.16.3",
    "dashboard":      "HUD                              viz 10",
    "videoplayer":    "camera/image view                viz 11.4",
    "videoreader":    "io/ codec (camera stream)        R-SIM-14",
    "signalgenerator": "impl: stub: / port override     R-SIM-15",
    "worldobjconverter": "adapter inside a source       R-SIM-14 sources/",
    "viewporttransform": "viewport                      viz 4",
    "sensorsimple":   "sensor model                     R-SIM-9",
    "map":            "world layer provider             R-SIM-2",
    "filesinfolder":  "sim batch                        NR-SIM-21 / S-D7",
    "bplmanager":     "sim batch (playlists)            NR-SIM-21 / S-D7",
    "combinator":     "sim batch (parameter sweeps)     FR-SIM-45 sweeps",
    "browser":        "inspector panel                  viz 7.2",
    "signaltable":    "signal table panel               viz 7.2 / 7.4",
    "bookmarkeditor": "user bookmarks on the timeline   viz 7.3 / FR-SIM-15",
    "ergreader":      "io/ codec (CarMaker results)     FR-SIM-50 / R-SIM-13",
    "toprimitive":    "Scene Prim (geometry from data)  R-SIM-2",
    "canreader":      "sources/ client (live bus)       OUT OF SCOPE, req 10",
    # -- Test-object generators. The comparable tool ships three (a plain
    #    object, a single-track vehicle model, a waypoint follower). Every one
    #    is a stand-in manufacturing a port's data -- exactly R-SIM-12's
    #    "mock", which belongs on the PRODUCTION side and is frozen into a
    #    recording. Independent confirmation that the stub:/mock split is the
    #    shape this class of tool converges on.
    "tosimple":       "mock -> recording, or stub:      R-SIM-12 / S-C2",
    "tosingletrack":  "mock -> recording, or stub:      R-SIM-12 / S-C2",
    "towaypoint":     "mock -> recording, or stub:      R-SIM-12 / S-C2",
    "driversimple":   "actor behaviour in sources/      R-SIM-9 / S-C2",
    "environment":    "world.* scenario binding         R-SIM-9",
    # -- Map / road network. Real future need; nothing asks for it yet.
    "opendrive":      "road-network source + world layer  OUT OF SCOPE, req 10",
    "magnoreader":    "io/ codec (vendor format)        OUT OF SCOPE, req 10",
    # -- Interactive driving input. We are open-loop by deliberate choice;
    #    live human input in the loop is FR-SIM-51 territory (parked).
    "keyboardinput":  "live input in the loop           PARKED, FR-SIM-51",
    "videowriter":    "capture / clip export            viz 9 / S-D7",
    # -- Native 3D. Foxglove SceneUpdate already carries the Scene in 3D, so
    #    interop exists; a built-in 3D viewport does not, and is not asked for.
    "viewer3d":       "Foxglove SceneUpdate (viz 11.3); native 3D PARKED",
    # -- foreign-system bridges. Each is a `sources/` client in our model
    #    (R-SIM-14 keeps io/ and sources/ separate); none is a second product,
    #    and none is scheduled -- no requirement asks for these buses yet.
    "dspace":         "sources/ client (HIL rig)        OUT OF SCOPE, req 10",
    "livecanreader":  "sources/ client (live bus)       OUT OF SCOPE, req 10",
    "ecalbridge":     "sources/ client (middleware)     OUT OF SCOPE, req 10",
    "headvisionhost": "sources/ client (vendor host)    OUT OF SCOPE, req 10",
    "next":           "sources/ client (vendor stack)   OUT OF SCOPE, req 10",
    "falconexplorer": "io/ codec (vendor format)        OUT OF SCOPE, req 10",
    "tsf":            "io/ codec (vendor format)        OUT OF SCOPE, req 10",
    "snippetextractor": "sim convert (interval cut)     S-D7",
    "birdseyeviewexporter": "render/ export (mp4/png)   viz 9 / S-D7",
    # -- host-side scripting of the tool itself. We expose the engine as a
    #    Python library instead (R-SIM-16, GT-9), so there is nothing to add.
    "machinepython":  "the framework IS a library       R-SIM-16 / GT-9",
    # -- plain file browsing. The OS does this; we do not reimplement it.
    "filesexplorer":  "-- (OS file dialog)",
    "fileexplorer":   "-- (OS file dialog)",
}

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
    for proj in sorted((root / "Examples").rglob("*.mbprj")) if (root / "Examples").is_dir() else []:
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
        mapped = next((v for k, v in CONCEPT_MAP.items() if k in key), None)
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
        for proj in sorted(examples.rglob("*.mbprj")):
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
        hits = sorted({v for v in CONCEPT_MAP.values() if marker in v})
        rep.line(f"\nDeliberately {label}: {len(hits)}")
        for h in hits:
            rep.line(f"  - {h}")

    return rep.finish()


if __name__ == "__main__":
    sys.exit(main())
