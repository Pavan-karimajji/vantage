# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Loads `catalogue.yaml` -- CARLA blueprint id -> classification token
(`S-C2` slice 5, see that file's own docstring for the "not yet verified
against a real blueprint library" caveat)."""

from __future__ import annotations

from pathlib import Path

import yaml

_CATALOGUE_PATH = Path(__file__).with_name("catalogue.yaml")


def load_catalogue(path: Path | None = None) -> dict:
    raw = yaml.safe_load((path or _CATALOGUE_PATH).read_text(encoding="utf-8"))
    return {"prefixes": dict(raw.get("prefixes", {})), "default": raw.get("default", "UNCLASSIFIED")}


def classification_for_blueprint(blueprint_id: str, catalogue: dict) -> str:
    """Longest matching prefix wins (a more specific entry, e.g.
    `"vehicle.tesla.cybertruck"`, must win over the general `"vehicle."`
    catch-all) -- `catalogue["default"]` when nothing matches, never a
    guess (`R-SIM-25`)."""
    best_prefix = ""
    best_token = catalogue["default"]
    for prefix, token in catalogue["prefixes"].items():
        if blueprint_id.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix, best_token = prefix, token
    return best_token
