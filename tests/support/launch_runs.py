# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`F-LAUNCH` (`VANTAGE_Test_Spec.md`): the launcher model driven from Python on a lab case. `pipeline_file` writes the run
configuration (a pipeline file, `Pipeline.load`'s input) the lab case's own run setup implies -- every stage with its library, its mode,
wiring, trigger, buffer depths, bulk and previous-cycle ports, and the run-setup values -- so a `Selection` of it is the selection of
that case, and the setup the launcher writes can be compared with the lab's.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from tests.support.lab_cases import LabCase


def pipeline_file(case: LabCase, directory: Path, *, name: str = "lab", modes: dict[str, str] | None = None,
                  drop_livemeas: bool = True) -> tuple[Path, tuple[Path, ...]]:
    """`(pipeline path, search directories)` of `case`: the lab setup's stages as a run configuration beside a copy of the
    recording. `modes` overrides stage modes (the lab case's own `measured` list otherwise)."""
    setup = json.loads(case.setup.read_text(encoding="utf-8"))
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    recording = directory / case.recording.name
    if not recording.exists():
        shutil.copyfile(case.recording, recording)
    stages = []
    for stage in setup["stages"]:
        if stage["mode"] == "off":
            continue
        library = case.libraries[stage["name"]]
        depths = {port["name"]: port["buffer_depth"] for port in stage["ports"]}
        entry = {
            "name": stage["name"], "mode": (modes or {}).get(stage["name"], stage["mode"]),
            "impl": f"dll:{library.stem}",
            "inputs": {wired["port"]: (f"source.{wired['producer_port']}" if wired["producer"] == "source"
                                       else f"{wired['producer']}.{wired['producer_port']}") for wired in stage.get("inputs", [])},
            "trigger": stage["trigger"], "buffer_depth": depths,
            "bulk": [port["name"] for port in stage["ports"] if port.get("bulk")],
            "previous_cycle": [wired["port"] for wired in stage.get("inputs", []) if wired.get("previous_cycle")],
        }
        if not entry["bulk"]:
            del entry["bulk"]
        if not entry["previous_cycle"]:
            del entry["previous_cycle"]
        stages.append(entry)
    run_setup = {"readiness_limit_steps": setup["readiness_limit_steps"], "fallback_max_gap": setup["fallback_max_gap"]}
    livemeas = setup["outputs"].get("livemeas")
    if livemeas is not None and not drop_livemeas:
        run_setup["livemeas"] = livemeas
    path = directory / f"{name}.yaml"
    path.write_text(yaml.safe_dump({"name": name, "project": "base", "recording": recording.name, "run_setup": run_setup,
                                    "stages": stages}, sort_keys=False), encoding="utf-8")
    search = tuple(sorted({library.parent for library in case.libraries.values()}))
    return path, search
