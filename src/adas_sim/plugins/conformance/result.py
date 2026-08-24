# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""One result shape shared by all four conformance kits (`SW-0358`) -- so a
caller checking "did my plug-in pass?" never learns four different answer
shapes for four extension points that share one requirement."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConformanceResult:
    ok: bool
    problems: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.ok
