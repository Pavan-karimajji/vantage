# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`UT-D8-4` (`docs/sim_implementation_plan.md`, `sim_player.md` §5, point
3: "a Campaign is exactly `sim batch`... anything Campaign can do, CI can
do, because it is the same command"): the invocation `CampaignWidget`
shows, run verbatim through the real `sim batch` argument parser, decodes
to the EXACT `recordings`/`pipeline`/`search`/`config`/`jobs` the widget
itself would pass to `core.batch.run_batch` -- proven at the argument
level (`core.batch.run_batch` itself launches real subprocesses needing a
real `dll:`/`stubdll:` build, `core/batch.py`'s own test boundary, same
as every other DLL-gated claim this session draws)."""

from __future__ import annotations

import shlex
from pathlib import Path

from adas_sim.player.shell.shell.campaign import batch_invocation_text
from adas_sim.cli.batch import build_parser
from adas_sim.orchestrate.batch import expand_recordings


def _parse_shown_invocation(text: str):
    assert text.startswith("sim batch ")
    argv = shlex.split(text)[2:]  # drop "sim" "batch"
    args = build_parser().parse_args(argv)
    return args


def test_shown_invocation_round_trips_recordings_and_pipeline(tmp_path):
    recordings = [tmp_path / "a.mcap", tmp_path / "b.mcap"]
    pipeline_path = tmp_path / "p.yaml"
    text = batch_invocation_text(recordings, pipeline_path)

    args = _parse_shown_invocation(text)
    assert expand_recordings(args.recordings) == recordings
    assert args.pipeline == pipeline_path
    assert args.jobs == 1
    assert args.search == []
    assert args.config is None


def test_shown_invocation_round_trips_search_config_and_jobs(tmp_path):
    recordings = [tmp_path / "a.mcap"]
    pipeline_path = tmp_path / "p.yaml"
    search = [tmp_path / "lib1", tmp_path / "lib2"]
    config = tmp_path / "cfg"
    text = batch_invocation_text(recordings, pipeline_path, search=search, config=config, jobs=4)

    args = _parse_shown_invocation(text)
    assert args.search == search
    assert args.config == config
    assert args.jobs == 4


def test_shown_invocation_survives_a_path_with_a_space(tmp_path):
    """`shlex.join`/`shlex.split` are the round-trip pair this test
    exists to prove -- a naive `" ".join(str(p) for p in ...)` would
    silently corrupt a path containing a space, exactly the class of bug
    a copy-pasted command must never carry."""
    weird_dir = tmp_path / "has space"
    weird_dir.mkdir()
    recording = weird_dir / "a.mcap"
    pipeline_path = tmp_path / "p.yaml"
    text = batch_invocation_text([recording], pipeline_path)

    args = _parse_shown_invocation(text)
    assert expand_recordings(args.recordings) == [recording]
