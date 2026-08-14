# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The fuzzy "did you mean" suggestion (SI-07, `N-8`, `WP-03`/`IMP-0124`).

Extracted from `diagnostics/explain.py`/`cli/explain.py`'s own previously
inline `difflib.get_close_matches` calls into one shared function, so every
caller ranks candidates the same way. The C++ side raises with the
candidate list and lets the CLI rank (`IMP-0124`) -- there is no C++
`near_matches` twin, unlike `errors.hpp`/`events.hpp`.
"""

from __future__ import annotations

import difflib
from collections.abc import Sequence


def near_matches(name: str, candidates: Sequence[str], *, n: int = 3, cutoff: float = 0.6) -> list[str]:
    """The top `n` candidates by similarity to `name`, `difflib`'s own
    ranking preserved -- re-sorting a merged candidate list alphabetically
    after truncating it separately can silently drop the actual best match
    (found the hard way, `cli/explain.py`'s own history)."""
    return difflib.get_close_matches(name, candidates, n=n, cutoff=cutoff)
