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
        header = [
            f"# {self.script_name}",
            f"# generated {_dt.datetime.now().isoformat(timespec='seconds')}",
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

def reference_tool_root() -> pathlib.Path | None:
    """Locate an installation of the reference resim/wiring console.

    Resolution order, most explicit first:

    1. ``ADAS_SIM_REFERENCE_TOOL`` -- an environment variable, so a machine
       with the tool somewhere unusual (or an Ubuntu box with a share mounted)
       needs no edit here;
    2. ``docs/py/reference_tool_path.txt`` -- an untracked one-line file, for a
       developer who does not want to set an environment variable;
    3. conventional install locations, by *directory shape* rather than by a
       hard-coded vendor path.

    No machine-specific path is written into this file or into any design
    document (``DC-2``): a design that only re-checks on one person's laptop is
    not re-checkable, and an absolute Windows path is an instruction that
    cannot be followed on Ubuntu.

    Returns ``None`` when nothing is found; callers must then ``skip``.
    """
    env = os.environ.get("ADAS_SIM_REFERENCE_TOOL")
    if env:
        p = pathlib.Path(env).expanduser()
        return p if p.is_dir() else None

    pointer = PY_DIR / "reference_tool_path.txt"
    if pointer.is_file():
        p = pathlib.Path(pointer.read_text(encoding="utf-8").strip()).expanduser()
        if p.is_dir():
            return p

    # Shape test: a reference installation is a directory containing both a
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
