# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A4 boundary test: UT-A4-11 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent.parent / "src" / "adas_sim"

#: The one format name that exists so far. Grown as later stages add codecs.
_FORMAT_TOKENS = ("mcap",)
_NO_FORMAT_PACKAGES = ("core", "model", "scene", "contracts", "check")


def test_no_module_outside_io_names_a_format():
    """UT-A4-11: no module outside `io/` names a format (R-SIM-14)."""
    violations = []
    for package in _NO_FORMAT_PACKAGES:
        for path in sorted((SRC_ROOT / package).rglob("*.py")):
            text = path.read_text(encoding="utf-8").lower()
            for token in _FORMAT_TOKENS:
                if token in text:
                    violations.append(f"{path}: mentions format token {token!r}")
    assert not violations, "\n".join(violations)
