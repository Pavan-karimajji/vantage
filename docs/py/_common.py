# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Shared helpers for the frozen design-evidence scripts in ``docs/py``.

Deliberately dependency-free: standard library only, so a check runs on a
machine with no virtualenv, on Windows or Ubuntu alike
(``docs/sim_portability.md``).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import sys
from typing import Iterable

# --------------------------------------------------------------------------
# Locations. Everything is derived from this file's own position, never from
# the current working directory -- a script must behave identically whether it
# is run from the repo root, from modules/sim, or from docs/py.
# --------------------------------------------------------------------------

PY_DIR = pathlib.Path(__file__).resolve().parent
DOCS_DIR = PY_DIR.parent
SIM_DIR = DOCS_DIR.parent
LOGS_DIR = PY_DIR / "logs"

# The design documents contain em-dashes, arrows and check marks. A Windows
# console defaults to cp1252 and raises UnicodeEncodeError on all three, while
# a Linux terminal defaults to UTF-8 and does not -- so a script that works on
# one developer's machine crashes on another's. Force UTF-8 with replacement
# on both, which is the whole of sim_portability.md's console rule in one call.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):        # already wrapped, or not a tty
        pass

#: Exit code meaning "the external artefact this survey needs is not present".
#: Never a failure -- surveys are evidence, and evidence can be unavailable.
EXIT_SKIPPED = 0
EXIT_FAILED = 1


class Report:
    """Collects lines for both stdout and a committed log file.

    A survey writes its findings through a ``Report`` so that the log under
    ``logs/`` is byte-identical to what a human saw on the console. Anything
    printed outside the report would exist in one place and not the other.
    """

    def __init__(self, script_name: str) -> None:
        self.script_name = script_name
        self.lines: list[str] = []
        self.failures: list[str] = []
        self.skipped_reason: str | None = None

    # -- emitting ---------------------------------------------------------

    def line(self, text: str = "") -> None:
        self.lines.append(text)
        print(text)

    def heading(self, text: str) -> None:
        self.line()
        self.line(text)
        self.line("-" * len(text))

    def table(self, headers: Iterable[str], rows: Iterable[Iterable[str]]) -> None:
        headers = [str(h) for h in headers]
        rows = [[str(c) for c in r] for r in rows]
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))
        fmt = "  ".join("{:<%d}" % w for w in widths)
        self.line(fmt.format(*headers).rstrip())
        self.line(fmt.format(*["-" * w for w in widths]).rstrip())
        for row in rows:
            self.line(fmt.format(*row).rstrip())

    # -- outcomes ---------------------------------------------------------

    def fail(self, text: str) -> None:
        """Record a check failure. Any failure makes the script exit non-zero."""
        self.failures.append(text)
        self.line(f"FAIL  {text}")

    def ok(self, text: str) -> None:
        self.line(f"ok    {text}")

    def skip(self, reason: str) -> None:
        """Declare the script inapplicable on this machine, with the reason."""
        self.skipped_reason = reason
        self.line(f"SKIPPED  {reason}")

    # -- finishing --------------------------------------------------------

    def write_log(self) -> pathlib.Path:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = _dt.date.today().isoformat()
        path = LOGS_DIR / f"{self.script_name}.{stamp}.log"
        # Deliberately NO wall-clock in the body. The filename already carries
        # the date, and a run whose results are unchanged must produce a
        # byte-identical log -- otherwise every re-run shows a diff containing
        # only its own timestamp, and a log diff that is usually noise is a log
        # diff nobody reads. Same reasoning as P-4's golden files, and as
        # UT-D2-3, which bans embedded timestamps in figure output.
        header = [
            f"# {self.script_name}",
            f"# platform  {sys.platform}",
            f"# python    {sys.version.split()[0]}",
            "",
        ]
        # Newline is forced to "\n" so a log committed from Windows and one
        # committed from Ubuntu do not differ by line ending alone.
        path.write_text("\n".join(header + self.lines) + "\n",
                        encoding="utf-8", newline="\n")
        return path

    def finish(self) -> int:
        self.line()
        if self.skipped_reason:
            self.line(f"RESULT  skipped -- {self.skipped_reason}")
        elif self.failures:
            self.line(f"RESULT  {len(self.failures)} failure(s)")
        else:
            self.line("RESULT  pass")
        log = self.write_log()
        print(f"\nlog: {log}")
        return EXIT_FAILED if self.failures else EXIT_SKIPPED


# --------------------------------------------------------------------------
# External artefacts
# --------------------------------------------------------------------------

def comparable_tool_root() -> pathlib.Path | None:
    """Locate an installation of a comparable resim/wiring console.

    Resolution order, most explicit first:

    1. ``ADAS_SIM_COMPARABLE_TOOL`` -- an environment variable, so a machine
       with the tool somewhere unusual (or an Ubuntu box with a share mounted)
       needs no edit here;
    2. ``docs/py/comparable_tool_path.txt`` -- an untracked one-line file, for a
       developer who does not want to set an environment variable;
    3. conventional install locations, by *directory shape* rather than by a
       hard-coded vendor path.

    No machine-specific path is written into this file or into any design
    document (``DC-2``): a design that only re-checks on one person's laptop is
    not re-checkable, and an absolute Windows path is an instruction that
    cannot be followed on Ubuntu.

    Returns ``None`` when nothing is found; callers must then ``skip``.
    """
    env = os.environ.get("ADAS_SIM_COMPARABLE_TOOL")
    if env:
        p = pathlib.Path(env).expanduser()
        return p if p.is_dir() else None

    pointer = PY_DIR / "comparable_tool_path.txt"
    if pointer.is_file():
        p = pathlib.Path(pointer.read_text(encoding="utf-8").strip()).expanduser()
        if p.is_dir():
            return p

    # Shape test: a comparable installation is a directory containing both a
    # Components/ and a Machines/ subdirectory. Searching by shape keeps any
    # vendor or organisation name out of this file entirely.
    roots = [pathlib.Path.home(), pathlib.Path("/opt")]
    drive = os.environ.get("SystemDrive")
    if drive:
        roots.append(pathlib.Path(drive + "/"))
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for depth1 in root.iterdir():
                if not depth1.is_dir():
                    continue
                for cand in (depth1, *(p for p in depth1.iterdir() if p.is_dir())):
                    if (cand / "Components").is_dir() and (cand / "Machines").is_dir():
                        return cand
        except (PermissionError, OSError):
            continue
    return None


def read_text(path: pathlib.Path) -> str:
    """Read a file that may carry a UTF-8 BOM, as reference XML does."""
    return path.read_text(encoding="utf-8-sig", errors="replace")


# --------------------------------------------------------------------------
# Comparable-tool schema tokens (project-file extension, XML element names).
# These are the vendor's own naming choices, so -- exactly like
# comparable_tool_root() above -- this file never hard-codes them. The
# built-in defaults below are generic placeholders with no real-vendor
# fingerprint; a developer surveying an actual installation supplies its
# real schema through one of the overrides, same two-step order as
# comparable_tool_root(): an env var, then an untracked local file.
# --------------------------------------------------------------------------

_DEFAULT_SCHEMA = {
    # Extension of one project/pipeline file.
    "project_ext": ".ctproj",
    # Element wrapping one bound function call within a project file.
    "call_config_tag": "CallConfig",
    # Element wrapping the tool's own window/dock layout state -- incidental
    # to the survey's finding, measured only to show it does not belong in
    # the pipeline file (arch 5.16.4).
    "gui_state_tag": "GuiLayoutState",
    # One element per authored binding decision inside a CallConfig.
    "authored_tags": [
        "ArgBinding",        # one per DLL function argument
        "FieldMappingRule",  # one per struct-field mapping rule
        "UriRewriteRule",    # one per URI rewrite
        "TriggerBinding",    # when the call fires
    ],
}


def comparable_tool_schema() -> dict:
    """Resolve the comparable tool's own schema tokens.

    Same override order as ``comparable_tool_root()``: ``ADAS_SIM_COMPARABLE_
    TOOL_SCHEMA`` (a JSON file) first, then the untracked
    ``docs/py/comparable_tool_schema.json``, else the generic default above.
    No real vendor tag name is ever checked into this file.
    """
    env = os.environ.get("ADAS_SIM_COMPARABLE_TOOL_SCHEMA")
    candidates = [pathlib.Path(env).expanduser()] if env else []
    candidates.append(PY_DIR / "comparable_tool_schema.json")
    for cand in candidates:
        if cand.is_file():
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            merged = dict(_DEFAULT_SCHEMA)
            merged.update(data)
            return merged
    return dict(_DEFAULT_SCHEMA)


def comparable_tool_concept_map() -> dict[str, str] | None:
    """Resolve the comparable tool's component/machine name -> concept map.

    Unlike ``comparable_tool_schema()`` there is no meaningful generic
    default here: the map's keys *are* the vendor's own component and
    machine inventory (FR-SIM-46's finding), so no such inventory is
    checked into this repo. A developer re-running the survey against a
    real installation supplies it via ``ADAS_SIM_COMPARABLE_TOOL_CONCEPT_MAP``
    (a JSON file of ``{discovered-name: concept-mapping-text}``) or the
    untracked ``docs/py/comparable_tool_concept_map.json``. Returns ``None``
    when neither is present; callers must then ``skip``.
    """
    env = os.environ.get("ADAS_SIM_COMPARABLE_TOOL_CONCEPT_MAP")
    candidates = [pathlib.Path(env).expanduser()] if env else []
    candidates.append(PY_DIR / "comparable_tool_concept_map.json")
    for cand in candidates:
        if cand.is_file():
            try:
                return json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
    return None
