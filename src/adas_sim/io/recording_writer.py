# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`RCT:IMP-0051` -- how this package's Python side reaches the one Python recording writer, `adas_recording` of the
`adas-interfaces` package (`RCT_Architecture.md` section 6a).

Each target's build writes `adas_recording.path` beside its `simengine` (`src/simengine/CMakeLists.txt`): one line,
the `python/` folder of the `adas-interfaces` package in that target's own lock. This module reads that file beside
the `simengine` the Python side runs (the one `engine.bridge` resolves), puts the folder on `sys.path` and returns
the writer module. There is no sibling checkout, no search and no environment variable (`R-SIM-11`); a missing file
or folder is an error naming the build to run.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

from adas_sim.diagnostics.errors import EnvironmentError_

#: The file each target's build writes beside its `simengine`.
PATH_FILE = "adas_recording.path"

_BUILD_HINT = (
    "build the simengine target for this platform (scripts/build.py -t sil -p <platform>); that build writes "
    f"{PATH_FILE} beside the executable"
)


def find_recording_package(search: Sequence[Path] = ()) -> Path:
    """The `python/` folder of the `adas-interfaces` package this build was linked with."""
    from adas_sim.engine.bridge import resolve_simengine_executable  # deferred: bridge imports the io package

    engine = resolve_simengine_executable(search)
    path_file = engine.parent / PATH_FILE
    if not path_file.is_file():
        raise EnvironmentError_(
            expected=f"{PATH_FILE} beside {engine}", found="no such file", where=str(path_file), hint=_BUILD_HINT,
        )
    folder = Path(path_file.read_text(encoding="utf-8").strip())
    if not (folder / "adas_recording" / "writer.py").is_file():
        raise EnvironmentError_(
            expected=f"adas_recording/writer.py under {folder} (named by {path_file})",
            found="no such file", where=str(folder), hint=_BUILD_HINT,
        )
    return folder


def recording_writer(search: Sequence[Path] = ()) -> ModuleType:
    """The module `adas_recording.writer` (`McapRecorder`, `TopicSpec`, `RecordingError`)."""
    folder = find_recording_package(search)
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    import adas_recording.writer as writer

    return writer
