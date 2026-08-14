# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: IMP-0156/IMP-0157 -- UT-CFG-09, UT-CFG-10."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.config.include import expand, resolve_vars
from adas_sim.config.layers import Layer
from adas_sim.diagnostics.errors import AuthoringError


def test_inline_and_include_produce_the_same_resolved_value(tmp_path):
    """UT-CFG-09: express one configuration inline and via includes;
    compare resolved values."""
    inline = tmp_path / "inline.yaml"
    inline.write_text("version: 1\nunits:\n  - name: aeb\n    impl: dll:aeb\n", encoding="utf-8")

    fragment = tmp_path / "unit_aeb.yaml"
    fragment.write_text("name: aeb\nimpl: dll:aeb\n", encoding="utf-8")
    via_include = tmp_path / "via_include.yaml"
    via_include.write_text("version: 1\nunits:\n  - !include unit_aeb.yaml\n", encoding="utf-8")

    assert expand(inline) == expand(via_include)


def test_nested_include_resolves_relative_to_its_own_file(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "leaf.yaml").write_text("value: 42\n", encoding="utf-8")
    (tmp_path / "sub" / "mid.yaml").write_text("leaf: !include leaf.yaml\n", encoding="utf-8")
    root = tmp_path / "root.yaml"
    root.write_text("mid: !include sub/mid.yaml\n", encoding="utf-8")

    result = expand(root)

    assert result == {"mid": {"leaf": {"value": 42}}}


def test_include_cycle_is_refused(tmp_path):
    """UT-CFG-09: then create an include cycle."""
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text("b: !include b.yaml\n", encoding="utf-8")
    b.write_text("a: !include a.yaml\n", encoding="utf-8")

    with pytest.raises(AuthoringError):
        expand(a)


def test_declared_variable_resolves():
    """UT-CFG-10: use a declared variable, then an undeclared one; read the
    reported resolutions."""
    raw = {"impl": "dll:${component}"}
    resolved, used = resolve_vars(raw, {"component": "aeb"}, source=Path("<test>"), layer=Layer.RUN)

    assert resolved == {"impl": "dll:aeb"}
    assert used["component"].value == "aeb"
    assert used["component"].layer is Layer.RUN


def test_undeclared_variable_is_refused_with_no_environment_fallback(monkeypatch):
    monkeypatch.setenv("component", "should_not_be_read")
    raw = {"impl": "dll:${component}"}

    with pytest.raises(AuthoringError):
        resolve_vars(raw, {}, source=Path("<test>"), layer=Layer.RUN)
