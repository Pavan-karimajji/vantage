# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 layering test: UT-B3-17 (docs/sim_implementation_plan.md) --
distinct from `test_a1_package.py`'s `UT-A1-6` (which only flags
`adas_sim.<view|render|cli|app>` imports): a bare `import PySide6` in a
lower-layer module would slip past that AST scan entirely, so this test
names the Qt package itself."""

from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent.parent / "src" / "adas_sim"

_LOWER_LAYER = ("core", "model", "contracts", "io", "check")
_QT_PACKAGES = ("PySide6", "PyQt5", "PyQt6")


def test_no_qt_module_imported_by_any_lower_layer_file():
    """UT-B3-17: no Qt module is imported by anything under core/, model/,
    contracts/ or io/ or check/ -- Qt retired from this framework entirely
    with the rest of the Python scene/render/player tree (`SM-12`)."""
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
                    if name.split(".")[0] in _QT_PACKAGES:
                        violations.append(f"{path}: imports {name}")
    assert not violations, "\n".join(violations)
