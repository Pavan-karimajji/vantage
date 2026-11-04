# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""One `adas_recording` for the lab and the engine (`VNT-WP-19-22` part E). `simengine` is linked with one build of the `adas-interfaces`
package (`adas_recording.path` beside it) and the lab's `index.json` names another (`interfaces_python`). Two builds of the package are
two writers: the first one a process imports stays, so which a test got depended on the order the tests ran in (a build without the
`config_bundle` argument failed `write_recording` in a worker that met it first). The two folders must hold the same
`adas_recording/writer.py`, byte for byte; the lab is rebuilt against the current package until they do.
"""
from __future__ import annotations

from adas_sim.io.recording_writer import find_recording_package
from tests.support.lab_cases import lab_case

WRITER = ("adas_recording", "writer.py")


def test_the_labs_recording_writer_is_the_one_the_engine_was_linked_with():
    lab = lab_case("running_example", "cut_c")
    assert lab.interfaces_python is not None, "the lab's index.json names no interfaces_python"
    engine = find_recording_package()
    lab_writer, engine_writer = lab.interfaces_python.joinpath(*WRITER), engine.joinpath(*WRITER)
    assert lab_writer.read_bytes() == engine_writer.read_bytes(), (
        f"the lab's adas_recording ({lab.interfaces_python}) is not the engine's ({engine}): rebuild the lab "
        f"(build.bat -t sil -p vs2026 in vantage-lab) so it takes the current adas-interfaces")
