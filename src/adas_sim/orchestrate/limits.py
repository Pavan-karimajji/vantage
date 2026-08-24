# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SW-0248`: per-run wall-time and memory limits are configurable, and a
breach of either is reported distinctly -- never folded into a plain `FAIL`.

Wall-time is already `orchestrate/batch.py`'s own `timeout_s` (a subprocess
`TimeoutExpired` classifies `RecordingOutcome.outcome == "timeout"`,
`SW-0242`) -- this module adds the other half, a **memory** cap, without
touching the closed 4-value `OUTCOMES` vocabulary (`R-SIM-19`): a memory
breach still reports `outcome="fail"` (the process did not crash and did not
merely run long; the parent deliberately ended it) but carries
`limit_breach="memory"` on `RecordingOutcome`, so a report reader (and
`SW-0248`'s own Accept clause) can tell "the module failed" apart from "we
killed it for using too much memory" without inventing a fifth outcome.

`rss_bytes(pid)` is a small, dependency-free process-memory reader --
this codebase carries no `psutil` dependency, and adding one for a single
polled number is more than this need justifies. POSIX reads `/proc/<pid>/
status`; Windows uses `ctypes` against `GetProcessMemoryInfo` (no new
dependency, `ctypes` is stdlib). Returns `None` when the platform has
neither path (reported as `unknown`, never a guessed number, `NR-SIM-4`)."""

from __future__ import annotations

import sys
from dataclasses import dataclass


def rss_bytes(pid: int) -> int | None:
    """Current resident set size for `pid`, or `None` if it cannot be read
    (process exited, unsupported platform, permission denied)."""
    if sys.platform == "win32":
        return _rss_bytes_windows(pid)
    return _rss_bytes_proc(pid)


def _rss_bytes_proc(pid: int) -> int | None:
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    # "VmRSS:	   12345 kB"
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _rss_bytes_windows(pid: int) -> int | None:
    import ctypes
    from ctypes import wintypes

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_VM_READ = 0x0010
    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid,
    )
    if not handle:
        return None
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        if not ok:
            return None
        return int(counters.WorkingSetSize)
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


@dataclass(frozen=True, slots=True)
class MemoryLimit:
    """`SW-0248`'s own memory cap, plus how often it is checked -- both
    explicit rather than a hard-coded poll rate, since a tight poll on a
    thousand-recording batch has its own cost."""

    limit_bytes: int
    poll_interval_s: float = 0.5


def breach_reason(rss: int | None, limit: MemoryLimit) -> bool:
    """`True` when `rss` is known and at or above `limit.limit_bytes` --
    an unknown `rss` (platform cannot report it) never triggers a breach,
    matching this module's own `unknown != violation` discipline."""
    return rss is not None and rss >= limit.limit_bytes
