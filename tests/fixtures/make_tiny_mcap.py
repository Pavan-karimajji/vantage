# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Generates `tiny.mcap`, the framework's own self-contained test fixture: a
synthetic 20-tick recording, committed alongside this script so the suite
needs no real component build (sim_implementation_plan.md §3.3). Never
hand-crafted -- regenerate with `python tests/fixtures/make_tiny_mcap.py`.

The generator writes through the one Python recording writer
(`RCT:IMP-0048`), so it needs a built `simengine` target (its
`adas_recording.path`). The committed `tiny.mcap` was written by the retired
`McapWriter` and is still a valid input -- it states `source_kind` and an origin
for every topic -- so it has not been regenerated.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from adas_sim.diagnostics.console import reconfigure_console_utf8  # noqa: E402
from adas_sim.io.base import Provenance, TopicInfo  # noqa: E402
from adas_sim.io.recording_writer import recording_writer  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent / "tiny.mcap"
TICK_COUNT = 20
DT_NS = 50_000_000  # 20 Hz, matching the live bridge's own pacing

TOPICS = {
    "/source/veh_dyn": TopicInfo(schema_name="adas_sim.test.VehDyn", provenance=Provenance.MEASURED),
    "/source/gen_object_list": TopicInfo(schema_name="adas_sim.test.DfObjList", provenance=Provenance.MEASURED),
    "/df/aeb.outputs": TopicInfo(schema_name="adas_sim.test.AebOutputs", provenance=Provenance.SIMULATED),
}


def build(out_path: Path = OUT_PATH) -> Path:
    module = recording_writer()
    specs = {topic: module.TopicSpec(info.schema_name, b"", info.provenance.value) for topic, info in TOPICS.items()}
    manifest = {
        "source_kind": "synthetic", "run_kind": "resim", "run_id": "20260729T000000Z-t1ny0000",
        "scenario": "fixtures/tiny.yaml", "project": "base", "pipeline": "df_only.yaml", "seed": 0,
        "components": [{"name": "df", "build_id": "tiny-fixture"}],
        "record_policies": {topic: "full" for topic in TOPICS},
    }
    with module.McapRecorder(out_path, specs, manifest) as writer:
        for tick in range(TICK_COUNT):
            t_us = tick * DT_NS // 1000
            writer.write("/source/veh_dyn", t_us, bytes([tick % 256, 0, 0, 0]))
            writer.write("/source/gen_object_list", t_us, bytes([tick % 256]))
            writer.write("/df/aeb.outputs", t_us, bytes([tick % 256, 1]))
    return out_path


def main() -> int:
    reconfigure_console_utf8()
    path = build()
    print(f"wrote {path} ({path.stat().st_size} bytes, {TICK_COUNT} ticks, {len(TOPICS)} topics)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
