# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`window_state` (`IMP-0150`, `SYS-0124`, `SYS-0125`): what the launcher window shows, as plain data computed by the launcher model --
each stage's offered modes, its library and whether one exists for this platform, and, per recording, what the recording can feed. The
window draws this and decides nothing (`SYS-0122`)."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from adas_sim.launcher.availability import ModuleAvailability, check_all
from adas_sim.launcher.cuts import StageFacts, stage_facts, topic_index
from adas_sim.launcher.model import Selection

ALL_MODES = ("simulate", "measured", "off")


@dataclass(frozen=True, slots=True)
class StageView:
    name: str
    mode: str
    modes: tuple[str, ...]  # the modes the window offers: `measured` only where the selected recording can feed the stage
    availability: ModuleAvailability


@dataclass(frozen=True, slots=True)
class WindowState:
    stages: tuple[StageView, ...]
    recordings: tuple[Path, ...]
    selected: Path | None
    cuts: Mapping[Path, tuple[StageFacts, ...]]  # per added recording, what it can feed; empty for a file that is no recording


def window_state(selection: Selection) -> WindowState:
    pipeline = selection.working_pipeline
    measurable = selection._measurable()
    availability = {item.stage: item for item in check_all(selection)}
    stages = tuple(
        StageView(stage.name, stage.mode, ALL_MODES if stage.name in measurable else tuple(m for m in ALL_MODES if m != "measured"),
                  availability[stage.name])
        for stage in pipeline.stages
    )
    cuts: dict[Path, tuple[StageFacts, ...]] = {}
    for recording in selection.recordings:
        try:
            cuts[recording] = stage_facts(selection, topic_index(Path(recording)))
        except Exception:  # a file that is no recording feeds nothing
            cuts[recording] = ()
    return WindowState(stages, tuple(selection.recordings), selection.selected_recording, cuts)
