# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Generates `tiny.mcap`, the framework's own self-contained test fixture: a
synthetic 20-tick recording, committed alongside this script so the suite
needs no real component build (sim_implementation_plan.md §3.3). Never
hand-crafted -- regenerate with `python tests/fixtures/make_tiny_mcap.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from adas_sim.diagnostics.console import reconfigure_console_utf8  # noqa: E402
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.plugins.registry import writer_for  # noqa: E402
import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec

OUT_PATH = Path(__file__).resolve().parent / "tiny.mcap"
TICK_COUNT = 20
DT_NS = 50_000_000  # 20 Hz, matching the live bridge's own pacing

TOPICS = {
    "/source/veh_dyn": TopicInfo(schema_name="adas_sim.test.VehDyn", provenance=Provenance.MEASURED),
    "/source/gen_object_list": TopicInfo(schema_name="adas_sim.test.DfObjList", provenance=Provenance.MEASURED),
    "/df/aeb.outputs": TopicInfo(schema_name="adas_sim.test.AebOutputs", provenance=Provenance.SIMULATED),
}


def build(out_path: Path = OUT_PATH) -> Path:
    manifest = RunManifest(
        manifest_version=1,
        run_id="20260729T000000Z-t1ny0000",
        run_kind="resim",
        created_utc="2026-07-29T00:00:00Z",
        source_kind="synthetic",
        scenario="fixtures/tiny.yaml",
        project="base",
        pipeline="df_only.yaml",
        seed=0,
        components=(ComponentBuildInfo(name="df", library_sha256="0" * 64, build_id="tiny-fixture"),),
    )
    writer = writer_for(out_path)
    writer.open(out_path, manifest, TOPICS, config_bundle_bytes=b"EGO_LENGTH_M: 4.5\nEGO_WIDTH_M: 1.8\n")
    for tick in range(TICK_COUNT):
        t_ns = tick * DT_NS
        writer.write("/source/veh_dyn", t_ns, bytes([tick % 256, 0, 0, 0]))
        writer.write("/source/gen_object_list", t_ns, bytes([tick % 256]))
        writer.write("/df/aeb.outputs", t_ns, bytes([tick % 256, 1]))
    writer.close()
    return out_path


def main() -> int:
    reconfigure_console_utf8()
    path = build()
    print(f"wrote {path} ({path.stat().st_size} bytes, {TICK_COUNT} ticks, {len(TOPICS)} topics)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
