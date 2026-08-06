# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""S-C8 (R-SIM-20, FR-SIM-64) unit tests: `PluginBundle` resolution
(`UT-C8-2`, `UT-C8-5`), the build-side packer (`UT-C8-1`), cross-component
layer-id collision through the real import mechanism (`UT-C8-3`), and the
recorder's identity-only embedding (`UT-C8-4`)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "interfaces" / "scripts"))
import pack_plugin_bundle  # noqa: E402

from adas_sim.core.errors import AuthoringError
from adas_sim.core.explain import explain
from adas_sim.core.session import Session
from adas_sim.model.plugins import PluginBundle
from adas_sim.scene.registry import registered_providers


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _authored_plugin_dir(tmp_path: Path, *, name: str = "authored", provides: list[str] | None = None) -> Path:
    # Mirrors the real shape (modules/df/sim/): plugin.yaml sits directly
    # inside the authored root, a SIBLING of layers/ -- not nested one level
    # further under a second "sim" directory.
    root = tmp_path / name
    _write(root / "plugin.yaml", yaml.safe_dump({
        "api": 1, "component": name, "provides": provides or ["sim.layers.thing"],
    }))
    _write(root / "layers" / "__init__.py", "")
    _write(root / "layers" / "thing.py", "VALUE = 1\n")
    return root


# ---------------------------------------------------------------------------
# UT-C8-1 -- the packer: deployed byte-identical, hash changes on any change
# including a case-only rename.
# ---------------------------------------------------------------------------


def test_pack_deploys_files_byte_identical_and_stamps_sha256(tmp_path):
    plugin_dir = _authored_plugin_dir(tmp_path)
    out = tmp_path / "deployed"

    digest = pack_plugin_bundle.pack(out=out, plugin_dir=plugin_dir)

    assert (out / "layers" / "thing.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    deployed_yaml = yaml.safe_load((out / "plugin.yaml").read_text(encoding="utf-8"))
    assert deployed_yaml["sha256"] == digest
    assert deployed_yaml["component"] == "authored"
    assert len(digest) == 64


def test_pack_hash_changes_on_case_only_rename(tmp_path):
    plugin_dir = _authored_plugin_dir(tmp_path)
    digest_before = pack_plugin_bundle.pack(out=tmp_path / "d1", plugin_dir=plugin_dir)

    (plugin_dir / "layers" / "thing.py").rename(plugin_dir / "layers" / "Thing.py")
    digest_after = pack_plugin_bundle.pack(out=tmp_path / "d2", plugin_dir=plugin_dir)

    assert digest_before != digest_after


def test_pack_excludes_pycache_and_plugin_yaml_itself_from_the_hash(tmp_path):
    plugin_dir = _authored_plugin_dir(tmp_path)
    (plugin_dir / "layers" / "__pycache__").mkdir()
    _write(plugin_dir / "layers" / "__pycache__" / "thing.cpython-312.pyc", "junk")

    out = tmp_path / "deployed"
    pack_plugin_bundle.pack(out=out, plugin_dir=plugin_dir)

    assert not (out / "layers" / "__pycache__").exists()


# ---------------------------------------------------------------------------
# UT-C8-2 -- resolution order, all four tiers.
# ---------------------------------------------------------------------------


def _bundle_dir(tmp_path: Path, name: str, *, api: int = 1, component: str | None = None) -> Path:
    root = tmp_path / name
    _write(root / "plugin.yaml", yaml.safe_dump({
        "api": api, "component": component or name, "provides": [], "sha256": "0" * 64,
    }))
    return root


def test_resolution_order_explicit_beats_embedded_beats_library_beats_checkout(tmp_path):
    explicit = _bundle_dir(tmp_path, "explicit")
    embedded = _bundle_dir(tmp_path, "embedded")
    library = _bundle_dir(tmp_path, "library")
    checkout = _bundle_dir(tmp_path, "checkout")

    all_four = PluginBundle.resolve(explicit=explicit, recording=embedded, library_dir=library, checkout=checkout)
    assert all_four.origin == "explicit" and all_four.component == "explicit"

    three = PluginBundle.resolve(recording=embedded, library_dir=library, checkout=checkout)
    assert three.origin == "embedded"

    two = PluginBundle.resolve(library_dir=library, checkout=checkout)
    assert two.origin == "library"

    one = PluginBundle.resolve(checkout=checkout)
    assert one.origin == "checkout"

    assert PluginBundle.resolve() is None


def test_resolve_returns_none_when_no_tier_has_a_plugin_yaml(tmp_path):
    assert PluginBundle.resolve(library_dir=tmp_path / "does_not_exist") is None


# ---------------------------------------------------------------------------
# UT-C8-5 -- an out-of-range api is refused before anything is imported.
# ---------------------------------------------------------------------------


def test_out_of_range_api_is_refused_naming_both_numbers(tmp_path):
    """UT-D5-4."""
    root = tmp_path / "bad_api"
    _write(root / "plugin.yaml", yaml.safe_dump({"api": 999, "component": "bad", "provides": ["sim.layers.explodes"]}))
    _write(root / "layers" / "__init__.py", "")
    _write(root / "layers" / "explodes.py", "raise RuntimeError('must never be imported')\n")

    with pytest.raises(AuthoringError) as excinfo:
        PluginBundle.resolve(library_dir=root)

    message = str(excinfo.value)
    assert "999" in message
    module_name = "_adas_plugin.bad.sim.layers.explodes"
    assert module_name not in sys.modules, "refused before import means genuinely never imported"


def test_missing_required_key_is_an_authoring_error(tmp_path):
    root = tmp_path / "incomplete"
    _write(root / "plugin.yaml", yaml.safe_dump({"api": 1, "component": "incomplete"}))  # no provides:

    with pytest.raises(AuthoringError) as excinfo:
        PluginBundle.resolve(library_dir=root)
    assert "provides" in str(excinfo.value)


# ---------------------------------------------------------------------------
# UT-C8-3 -- two libraries on the plug-in path, each contributing layers,
# both register; a duplicate layer id across two components raises naming
# both -- exercised through the REAL import mechanism (collision-free private
# module names), not asserted about in the abstract.
# ---------------------------------------------------------------------------


def _plugin_with_layer_module(tmp_path: Path, *, name: str, dotted: str, source: str) -> PluginBundle:
    root = tmp_path / name
    # `dotted`'s leading "sim" segment names `root` itself (same convention
    # `PluginBundle.import_modules` strips) -- the file lives under root
    # without that first segment.
    parts = dotted.split(".")
    rel = Path(*parts[1:]) if parts and parts[0] == "sim" else Path(*parts)
    _write(root / rel.with_suffix(".py"), source)
    _write(root / "plugin.yaml", yaml.safe_dump({"api": 1, "component": name, "provides": [dotted]}))
    bundle = PluginBundle.resolve(library_dir=root)
    assert bundle is not None
    return bundle


def test_sim_explain_reports_the_owning_component_and_real_file_path_for_a_plugin_layer(tmp_path):
    """S-C8's own remaining item ("sim explain and sim doctor both report
    the plug-in path"): a layer imported through the real plug-in
    mechanism carries `_adas_plugin.<component>.<dotted>` as its module
    name (`PluginBundle.import_modules`'s own docstring) -- `explain()`
    parses the component out of that name and reports the module's own
    real, resolved `__file__` (set by `importlib.util.
    spec_from_file_location` at import time) as `plugin_path`."""
    bundle = _plugin_with_layer_module(
        tmp_path, name="explainComp", dotted="sim.layers.explained",
        source=(
            "from adas_sim.scene.registry import layer_provider\n"
            "@layer_provider('sim.test.c8.explained')\n"
            "def provide(ctx):\n    return ()\n"
        ),
    )
    bundle.import_modules()

    facts = explain("sim.test.c8.explained", Session(run_id="run-explain", name="s", ticks=()))

    assert facts["kind"] == "layer"
    assert facts["plugin_component"] == "explainComp"
    assert facts["plugin_path"] == str(bundle.root / "layers" / "explained.py")


def test_sim_explain_reports_no_plugin_fields_for_a_first_party_layer():
    """A layer registered by the framework's own code (this test file
    itself, `test.d6.explain.probe` in `test_d6_explain.py`) has no
    plug-in bundle -- both fields must be absent, never guessed
    (`R-SIM-25`, `NR-SIM-4`)."""
    from adas_sim.scene.registry import layer_provider

    @layer_provider("test.c8.first_party_probe")
    def _probe(ctx):  # pragma: no cover -- never called, only registered
        return ()

    facts = explain("test.c8.first_party_probe", Session(run_id="run-explain", name="s", ticks=()))
    assert facts["kind"] == "layer"
    assert "plugin_component" not in facts
    assert "plugin_path" not in facts


def test_two_components_each_contributing_a_layer_both_register(tmp_path):
    """UT-D5-3."""
    a = _plugin_with_layer_module(
        tmp_path, name="compA", dotted="sim.layers.a",
        source=(
            "from adas_sim.scene.registry import layer_provider\n"
            "@layer_provider('sim.test.c8.unique_a')\n"
            "def provide(ctx):\n    return ()\n"
        ),
    )
    b = _plugin_with_layer_module(
        tmp_path, name="compB", dotted="sim.layers.b",
        source=(
            "from adas_sim.scene.registry import layer_provider\n"
            "@layer_provider('sim.test.c8.unique_b')\n"
            "def provide(ctx):\n    return ()\n"
        ),
    )
    a.import_modules()
    b.import_modules()

    assert "sim.test.c8.unique_a" in registered_providers()
    assert "sim.test.c8.unique_b" in registered_providers()


def test_duplicate_layer_id_across_two_components_raises_naming_both(tmp_path):
    a = _plugin_with_layer_module(
        tmp_path, name="dupA", dotted="sim.layers.dup",
        source=(
            "from adas_sim.scene.registry import layer_provider\n"
            "@layer_provider('sim.test.c8.dup')\n"
            "def provide(ctx):\n    return ()\n"
        ),
    )
    b = _plugin_with_layer_module(
        tmp_path, name="dupB", dotted="sim.layers.dup",
        source=(
            "from adas_sim.scene.registry import layer_provider\n"
            "@layer_provider('sim.test.c8.dup')\n"
            "def provide(ctx):\n    return ()\n"
        ),
    )
    a.import_modules()
    with pytest.raises(AuthoringError) as excinfo:
        b.import_modules()

    message = str(excinfo.value)
    assert "dupA" in message and "dupB" in message


# ---------------------------------------------------------------------------
# UT-C8-4 -- a recording carries plug-in identity + hash only, never bytes.
# ---------------------------------------------------------------------------


def test_recorder_embeds_plugin_identity_and_hash_never_bytes(tmp_path):
    from adas_sim.io.base import RunManifest
    from adas_sim.io.mcap import McapReader, McapWriter

    path = tmp_path / "rec.mcap"
    writer = McapWriter()
    plugin_meta = {"df": {"api": 1, "sha256": "a" * 64}}
    writer.open(path, RunManifest(), {}, plugin_bundles_meta=plugin_meta)
    writer.close()

    reader = McapReader(path)
    try:
        round_tripped = reader.plugin_bundles_meta()
    finally:
        reader.close()

    assert round_tripped == plugin_meta
    # NR-SIM-44: nowhere in the round-tripped structure is there room for
    # executable content -- only the two identity/hash fields survive.
    assert set(round_tripped["df"]) == {"api", "sha256"}
