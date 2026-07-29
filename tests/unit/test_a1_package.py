# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A1 package-skeleton tests: UT-A1-1, UT-A1-2, UT-A1-6, UT-A1-9
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_ROOT = SIM_ROOT / "src" / "adas_sim"

#: sim_api_reference.md §1's package map, byte for byte.
EXPECTED_SUBPACKAGES = {
    "core", "model", "scene", "contracts", "io", "sources",
    "view", "render", "check", "cli", "app",
}

#: UT-A1-2: importing any subpackage must not pull these in as a side effect.
FORBIDDEN_AT_IMPORT = ("PySide6", "matplotlib", "mcap", "google.protobuf")

#: UT-A1-6: the import direction sim_api_reference.md §1 requires.
_LOWER_LAYER = ("core", "model", "scene", "contracts", "io", "check")
_UPPER_LAYER = ("view", "render", "cli", "app")


def test_import_adas_sim_succeeds_with_nonempty_version():
    """UT-A1-1."""
    import adas_sim

    assert isinstance(adas_sim.__version__, str)
    assert adas_sim.__version__


def test_subpackages_import_without_heavy_dependencies():
    """UT-A1-2: no subpackage import pulls in Qt, matplotlib, mcap or protobuf."""
    imports = "; ".join(f"import adas_sim.{name}" for name in sorted(EXPECTED_SUBPACKAGES))
    code = (
        f"import sys; sys.path.insert(0, {str(SRC_ROOT.parent)!r}); "
        f"{imports}; "
        "print(','.join(sorted(sys.modules)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, check=True,
    )
    modules = set(result.stdout.strip().split(","))
    for forbidden in FORBIDDEN_AT_IMPORT:
        hit = [m for m in modules if m == forbidden or m.startswith(forbidden + ".")]
        assert not hit, f"{forbidden} was imported as a side effect: {hit}"


def test_subpackage_set_matches_api_reference():
    """UT-A1-9: the subpackage set on disk equals sim_api_reference.md §1's list --
    neither doc nor tree may drift alone."""
    on_disk = {p.name for p in SRC_ROOT.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert on_disk == EXPECTED_SUBPACKAGES


def test_lower_layer_never_imports_view_render_cli_or_app():
    """UT-A1-6: import-direction test over the module graph (module-graph scan,
    sim_api_reference.md §1)."""
    violations = []
    for sub in _LOWER_LAYER:
        for path in sorted((SRC_ROOT / sub).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    parts = name.split(".")
                    if parts[0] == "adas_sim" and len(parts) > 1 and parts[1] in _UPPER_LAYER:
                        violations.append(f"{path}: imports {name}")
    assert not violations, "\n".join(violations)
