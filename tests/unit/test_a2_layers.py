# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: IMP-0149 -- UT-CFG-02."""

from __future__ import annotations

from pathlib import Path

from adas_sim.config.layers import Layer, merge


def test_set_one_value_in_all_four_layers_last_wins_with_layer_recorded(tmp_path):
    """UT-CFG-02: set one value in all four layers; read the resolved value
    and its recorded layer."""
    package = tmp_path / "package.yaml"
    project = tmp_path / "project.yaml"
    run = tmp_path / "run.yaml"
    for path, value in ((package, 1), (project, 2), (run, 3)):
        path.write_text(f"threshold: {value}\n", encoding="utf-8")

    resolved = merge([
        (Layer.PACKAGE, package, {"threshold": 1}),
        (Layer.PROJECT, project, {"threshold": 2}),
        (Layer.RUN, run, {"threshold": 3}),
        (Layer.CLI, Path("<cli>"), {"threshold": 4}),
    ])

    assert resolved["threshold"].value == 4
    assert resolved["threshold"].layer is Layer.CLI


def test_a_leaf_only_one_layer_declares_keeps_its_own_layer(tmp_path):
    """A per-LEAF merge, never a per-file replace: a layer silent on a leaf
    does not overwrite an earlier layer's value for it."""
    package = tmp_path / "package.yaml"
    package.write_text("a: 1\nb: 2\n", encoding="utf-8")
    project = tmp_path / "project.yaml"
    project.write_text("a: 9\n", encoding="utf-8")

    resolved = merge([
        (Layer.PACKAGE, package, {"a": 1, "b": 2}),
        (Layer.PROJECT, project, {"a": 9}),
    ])

    assert resolved["a"].value == 9 and resolved["a"].layer is Layer.PROJECT
    assert resolved["b"].value == 2 and resolved["b"].layer is Layer.PACKAGE


def test_nested_leaves_flatten_to_dotted_paths_with_correct_lines(tmp_path):
    package = tmp_path / "package.yaml"
    package.write_text("nested:\n  key: value\n", encoding="utf-8")

    resolved = merge([(Layer.PACKAGE, package, {"nested": {"key": "value"}})])

    assert resolved["nested.key"].value == "value"
    assert resolved["nested.key"].line == 2
    assert resolved["nested.key"].file == package
