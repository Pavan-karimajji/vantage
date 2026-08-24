# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-28` `SI-22 launcher` -- `UT-LNC-05`/`UT-LNC-06` (`launcher/write.py`,
`SW-0343`/`SW-0346`/`SW-0347`). The real end-to-end `launch()` through
`simengine` (`IT-21`) needs a built `echo_stub`/`simengine` pair and lives
in `tests/system/test_lnc_launch.py`, same split `test_d15b_cli_resim.py`
already uses for the resim CLI it wraps."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
import yaml

from adas_sim.graph.build import Pipeline
from adas_sim.launcher.classify import LaunchBlocked
from adas_sim.launcher.model import Selection
from adas_sim.launcher.write import launch, to_run_config
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.runspec.manifest import load_run_spec

_CHAIN_NAMES = ("vdy", "perception", "fusion", "aeb")


def _manifest(*, component: str, inputs=(), outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _stub(name: str, manifest: ComponentManifest) -> InProcessSilComponent:
    component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
    component.init()
    return component


def _chain_pipeline(tmp_path: Path, modes_: tuple[str, str, str, str]) -> Pipeline:
    stages = []
    components = {}
    for i, (name, mode) in enumerate(zip(_CHAIN_NAMES, modes_)):
        inputs = {} if i == 0 else {"in": f"{_CHAIN_NAMES[i - 1]}.out"}
        port_specs_in = [] if i == 0 else [PortSpec(name="in", proto_type="test.A")]
        manifest = _manifest(component=name, inputs=port_specs_in, outputs=[PortSpec(name="out", proto_type="test.A")])
        stages.append({"name": name, "mode": mode, "impl": f"stub:{name}", "inputs": inputs})
        components[name] = _stub(name, manifest)
    data = {"version": 1, "name": "chain4", "stages": stages}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    any_measured = "measured" in modes_

    class _FakeRecording:
        def topics(self):
            return {"out": None} if any_measured else {}

    return Pipeline.load(path, components=components, recording=_FakeRecording() if any_measured else None)


# ---------------------------------------------------------------------------
# UT-LNC-06 -- SW-0347: the launcher and the command line share the schema
# ---------------------------------------------------------------------------


def test_a_written_config_loads_unmodified_headlessly(tmp_path):
    selection = Selection(base_pipeline=_chain_pipeline(tmp_path, ("simulate",) * 4), project="my_project")
    out_path = tmp_path / "run" / "config.yaml"

    to_run_config(selection, out_path)
    reloaded = Pipeline.load(out_path, components={n: _stub(n, _manifest(component=n)) for n in _CHAIN_NAMES})

    assert [s.name for s in reloaded.stages] == list(_CHAIN_NAMES)
    assert reloaded.name == "chain4"


def test_recording_and_config_are_written_relative_to_the_file(tmp_path):
    recording = tmp_path / "recordings" / "in.mcap"
    recording.parent.mkdir(parents=True)
    recording.write_bytes(b"")
    config = tmp_path / "cfg" / "base.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("{}", encoding="utf-8")

    selection = Selection(
        base_pipeline=_chain_pipeline(tmp_path, ("simulate",) * 4),
        recordings=(recording,), selected_recording=recording, config=config,
    )
    out_path = tmp_path / "run" / "config.yaml"
    to_run_config(selection, out_path)

    raw = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert not Path(raw["recording"]).is_absolute()
    assert not Path(raw["config"]).is_absolute()

    spec = load_run_spec(out_path)
    assert spec.recording == recording.resolve()
    assert spec.config == config.resolve()
    assert spec.project == "base"


def test_no_launcher_only_fields_leak_into_the_written_file(tmp_path):
    """`SW-0347`: `layout` is launcher-only display state and must never
    appear in the written file -- nothing headless reads it."""
    selection = Selection(base_pipeline=_chain_pipeline(tmp_path, ("simulate",) * 4)).set_layout("2x2")
    out_path = tmp_path / "config.yaml"
    to_run_config(selection, out_path)

    raw = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert "layout" not in raw


# ---------------------------------------------------------------------------
# UT-LNC-05 -- SW-0346: one action yields a complete run (screens/actions)
# ---------------------------------------------------------------------------


def test_one_action_flow_add_recordings_layout_modes_save(tmp_path):
    recording = tmp_path / "in.mcap"
    recording.write_bytes(b"")
    selection = Selection(base_pipeline=_chain_pipeline(tmp_path, ("simulate",) * 4))

    # The whole "add recordings, choose a layout, set modes, save" flow is
    # reachable as a plain chain of Selection calls -- no second screen's
    # worth of state lives outside this one object.
    selection = (
        selection
        .add_recording(recording)
        .select_recording(recording)
        .set_layout("2x2")
        .set_mode("perception", "measured")
    )
    out_path = tmp_path / "config.yaml"
    written = to_run_config(selection, out_path)

    assert written == out_path
    assert out_path.is_file()
    raw = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert raw["recording"] == "in.mcap"
    assert next(s for s in raw["stages"] if s["name"] == "perception")["mode"] == "measured"


# ---------------------------------------------------------------------------
# IMP-0343 -- launch() takes a path, never a Selection; blocks on BROKEN
# ---------------------------------------------------------------------------


def test_launch_signature_takes_only_a_path():
    import inspect

    params = list(inspect.signature(launch).parameters)
    assert params[0] == "path"
    assert "selection" not in params
    assert "Selection" not in str(inspect.signature(launch))


def test_launch_raises_launch_blocked_on_an_unwaived_broken_chain(tmp_path):
    """`launch()` re-loads and re-classifies `path` itself (never trusts
    the `Selection` that wrote it) -- `Pipeline.load` is mocked to the
    equivalent broken in-process pipeline here because a REAL reload needs
    a resolvable `dll:`/`stubdll:` binary, which `IT-21`
    (`tests/system/test_lnc_launch.py`) exercises for real; this test is
    only about `launch()`'s own gate, proven never to reach
    `cli.resim.run`."""
    selection = _selection_with_broken_chain(tmp_path)
    out_path = tmp_path / "config.yaml"
    to_run_config(selection, out_path)

    with mock.patch("adas_sim.launcher.write.Pipeline.load", return_value=selection.working_pipeline):
        with mock.patch("adas_sim.cli.resim.run") as resim_run:
            with pytest.raises(LaunchBlocked):
                launch(out_path)
            resim_run.assert_not_called()


def _selection_with_broken_chain(tmp_path: Path) -> Selection:
    selection = Selection(base_pipeline=_chain_pipeline(tmp_path, ("simulate", "simulate", "measured", "simulate")))
    return selection.set_mode("perception", "measured")
