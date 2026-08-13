# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""IMP-0367 / ANL-SW-24 [ANL-SW-71's sibling] (docs/v2/SIM_Implementation_Plan_v0.1.md
WP-01) -- every measured claim in this module's documents and benchmarks
(`render/bench.py`'s frame-time budget, `WP-26`; a determinism report's
timing, `R-SIM-24`) records **platform, shell, CPU and build type** beside
the number, not the number alone. A measurement with no provenance cannot
be reproduced or refuted -- it can only be believed, which is exactly what
`R-SIM-25`'s evidence chain exists to stop.

This module owns the provenance capture; it takes no measurement itself --
a benchmark calls `measure_provenance()` once and stores the result beside
its own number, the same way a run manifest stores a config-bundle hash
beside a run rather than re-deriving it.
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Provenance:
    platform: str  # platform.platform(), e.g. "Windows-11-10.0.26200"
    shell: str  # the invoking shell, e.g. "powershell", "bash", "cmd"
    cpu: str  # platform.processor(), or "unknown" where the OS does not report one
    build_type: str  # "Debug"/"Release"/"unknown" -- from CMAKE_BUILD_TYPE, else unknown
    python: str  # platform.python_version()


def _detect_shell() -> str:
    """Best-effort, not authoritative -- a measurement's shell field is
    provenance for a human comparing two runs, not a security boundary."""
    if os.environ.get("PSModulePath"):
        return "powershell"
    shell = os.environ.get("SHELL", "")
    if shell:
        return os.path.basename(shell)
    comspec = os.environ.get("COMSPEC", "")
    if comspec:
        return os.path.basename(comspec)
    return "unknown"


def _detect_cpu() -> str:
    cpu = platform.processor()
    if cpu:
        return cpu
    # Windows' platform.processor() is sometimes empty under some shells;
    # the environment variable is the documented fallback.
    return os.environ.get("PROCESSOR_IDENTIFIER", "unknown")


def _detect_build_type() -> str:
    return os.environ.get("CMAKE_BUILD_TYPE", "unknown")


def measure_provenance() -> Provenance:
    return Provenance(
        platform=platform.platform(),
        shell=_detect_shell(),
        cpu=_detect_cpu(),
        build_type=_detect_build_type(),
        python=platform.python_version(),
    )


def format_measurement(value: float, unit: str, *, provenance: Provenance | None = None) -> str:
    """One reportable line: the number, its unit and the four provenance
    fields, in the shape `render/bench.py`'s `conf/budget.yaml` (IMP-0323)
    and any future measured-claim table can quote directly."""
    p = provenance or measure_provenance()
    return (
        f"{value} {unit}  "
        f"(platform={p.platform}, shell={p.shell}, cpu={p.cpu}, "
        f"build_type={p.build_type}, python={p.python})"
    )


def main(argv: list[str] | None = None) -> int:
    """Prints this machine's provenance line, for a human wiring up a new
    benchmark to check the fields look right before trusting the number
    beside them."""
    print(format_measurement(0.0, "sentinel"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
