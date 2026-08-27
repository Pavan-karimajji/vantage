# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji
# @file check_engine_boundary.py
# @brief
#   ANL-SW-80 (SIM_Software_Test_Spec_v0.1.md, serves SW-0419) --
#   cross-repo-facing as ANL-SM-04 (VIZ_Sync_Plan_v0.1.md SM-02, "D-10's
#   only cost"): a consumer
#   linking `adas-sim::io` acquires no engine dependency and no first-party
#   component. Checked by parsing the resolved Conan graph, the same
#   pattern `modules/viz/scripts/check_no_sim_edge.py` (ANL-VZ-05) already
#   uses, mirror-imaged: that check proves the toolkit's graph excludes
#   `adas-sim`; this one proves `adas-sim`'s own graph excludes every other
#   first-party `adas-*` package. That is sufficient by construction --
#   `simcore`'s `io` component is a named subset VIEW over the one
#   `simcore.a` artifact (conf/build.yml's own note), not a second binary,
#   so as long as `adas-sim` itself pulls in no first-party dependency, ANY
#   consumer linking `adas-sim::io` inherits that same empty first-party
#   set transitively -- there is no separate "engine" package to check
#   against yet, and the escape hatch (splitting `io` into its own Conan
#   package) is written into SM-02's own box for the day that stops holding.

import argparse
import json
import subprocess
import sys
from pathlib import Path

SELF_NAME = "adas-sim"
FIRST_PARTY_PREFIX = "adas-"


def _ref_name(ref: str) -> str:
    # "adas-sim/0.1.0" -> "adas-sim"; a #revision suffix (if present) never
    # reaches this far since it trails the version, not the name.
    return ref.split("/", 1)[0]


def refs_from_graph(graph: dict) -> list[str]:
    return [node.get("ref", "") for node in graph["graph"]["nodes"].values() if node.get("ref")]


def resolved_refs_live(recipe_dir: Path) -> list[str]:
    proc = subprocess.run(
        ["conan", "graph", "info", ".", "-s", "build_type=Release", "-o", "project=base", "--format=json"],
        cwd=recipe_dir, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        sys.exit(f"check_engine_boundary: FAIL -- `conan graph info` itself failed (exit {proc.returncode})")
    return refs_from_graph(json.loads(proc.stdout))


def check_anl_sm_04(refs: list[str]) -> list[str]:
    if not refs:
        return ["check_engine_boundary: FAIL -- zero resolved refs, scope is stale"]
    names = {_ref_name(ref) for ref in refs}
    if SELF_NAME not in names:
        return [f"check_engine_boundary: FAIL -- {SELF_NAME} itself is not in its own resolved "
                f"graph, scope is stale: {sorted(names)}"]
    forbidden = sorted(n for n in names if n.startswith(FIRST_PARTY_PREFIX) and n != SELF_NAME)
    if forbidden:
        return [f"ANL-SW-80 / ANL-SM-04 FAIL: resolved graph contains first-party package(s) "
                f"{forbidden} -- a consumer linking `adas-sim::io` must acquire no engine "
                f"dependency and no first-party component"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe-dir", type=Path, default=None)
    parser.add_argument("--graph-json", type=Path, default=None,
                         help="Skip the live `conan graph info` call and check this canned "
                              "JSON file instead (test-only override).")
    args = parser.parse_args()

    if args.graph_json is not None:
        refs = refs_from_graph(json.loads(args.graph_json.read_text(encoding="utf-8")))
    else:
        recipe_dir = args.recipe_dir
        if recipe_dir is None:
            recipe_dir = Path(__file__).resolve().parent.parent
        refs = resolved_refs_live(recipe_dir)

    errors = check_anl_sm_04(refs)
    if errors:
        print("check_engine_boundary: FAIL", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print("check_engine_boundary: PASS -- ANL-SW-80 / ANL-SM-04, adas-sim's own resolved graph "
          "carries no first-party package beyond itself")
    return 0


if __name__ == "__main__":
    sys.exit(main())
