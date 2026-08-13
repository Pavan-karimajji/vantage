# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A2 `ProjectModel.resolve` tests: UT-A2-7, UT-A2-10
(docs/sim_implementation_plan.md). S-C5's real multi-file bundle hash
(UT-C5-4, UT-C5-5) is added below, in the same module rather than a new
file -- it exercises the same `ProjectModel`/bundle-directory machinery."""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

import pytest
import yaml

from adas_sim.diagnostics.errors import AuthoringError, ProvenanceWarning
from adas_sim.config.project import ProjectModel, bundle_bytes_for_recording, extract_embedded_bundle

#: modules/interfaces/scripts, sibling submodule -- not a pip dependency of
#: adas_sim (R-SIM-11: a component's build must not require adas_sim, and
#: symmetrically adas_sim's own package must not require interfaces). Only
#: this test file reaches across, to prove the two independent hash
#: implementations agree (S-C5's own cross-implementation proof, absent a
#: real df_sil build in this environment -- see test_c5_relocatability.py).
_INTERFACES_SCRIPTS = Path(__file__).resolve().parents[3] / "interfaces" / "scripts"

_EGO_TEMPLATE = (
    "EGO_LENGTH_M: {length}\n"
    "EGO_WIDTH_M: {width}\n"
    "EGO_WHEELBASE_M: {wheelbase}\n"
    "EGO_OVERHANG_FRONT_M: {overhang}\n"
)


def _make_bundle(root: Path, name: str, *, project: str, length: float, width: float,
                  wheelbase: float, overhang: float) -> Path:
    bundle_dir = root / name
    (bundle_dir / "vehicle").mkdir(parents=True)
    (bundle_dir / "vehicle" / "ego_params.yaml").write_text(
        _EGO_TEMPLATE.format(length=length, width=width, wheelbase=wheelbase, overhang=overhang),
        encoding="utf-8",
    )
    (bundle_dir / "manifest.yaml").write_text(f"project: {project}\n", encoding="utf-8")
    return bundle_dir


def test_resolution_order_explicit_beats_embedded_beats_library_beats_checkout(tmp_path):
    """UT-A2-7 / UT-C5-2: with all four sources present, explicit wins; with
    three, the embedded bundle wins; bundle_origin reports which."""
    explicit_dir = _make_bundle(tmp_path, "explicit", project="fx", length=1.0, width=1.0, wheelbase=1.0, overhang=0.1)
    embedded_dir = _make_bundle(tmp_path, "embedded", project="fx", length=2.0, width=2.0, wheelbase=2.0, overhang=0.2)
    library_dir = _make_bundle(tmp_path, "library", project="fx", length=3.0, width=3.0, wheelbase=3.0, overhang=0.3)

    all_four = ProjectModel.resolve(explicit=explicit_dir, recording=embedded_dir, library_dir=library_dir, project="fx")
    assert all_four.bundle_origin == "explicit"
    assert all_four.ego().length_m == 1.0

    three = ProjectModel.resolve(recording=embedded_dir, library_dir=library_dir, project="fx")
    assert three.bundle_origin == "embedded"
    assert three.ego().length_m == 2.0

    two = ProjectModel.resolve(library_dir=library_dir, project="fx")
    assert two.bundle_origin == "library"
    assert two.ego().length_m == 3.0

    none_given = ProjectModel.resolve(project="base")
    assert none_given.bundle_origin == "checkout"
    assert none_given.project == "base"


def test_bundle_dir_is_the_winning_tiers_own_directory_and_none_for_checkout(tmp_path):
    """`AR-55`: `bundle_dir` is what lets a component's own
    layer code (`df/sim/layers/bsd.py`'s calibration reader) read ITS OWN
    calibration from the SAME directory this model resolved from, instead
    of separately computing a source-checkout-only path. `None` only for
    `checkout` -- that tier never resolved a packed-bundle-shaped directory
    at all (ego came from `shared_config`'s own tree)."""
    library_dir = _make_bundle(tmp_path, "library", project="fx", length=3.0, width=3.0, wheelbase=3.0, overhang=0.3)

    resolved = ProjectModel.resolve(library_dir=library_dir, project="fx")
    assert resolved.bundle_dir == library_dir

    checkout = ProjectModel.resolve(project="base")
    assert checkout.bundle_dir is None


def test_project_mismatch_emits_provenance_warning_and_still_resolves(tmp_path):
    """UT-A2-10 / UT-C5-3: a project mismatch degrades visibly (a warning) and
    the run continues -- it never raises and never silently substitutes
    (R-SIM-3a)."""
    other_project_dir = _make_bundle(
        tmp_path, "other", project="cus1", length=5.0, width=5.0, wheelbase=5.0, overhang=0.5
    )

    with pytest.warns(ProvenanceWarning):
        resolved = ProjectModel.resolve(explicit=other_project_dir, project="base")

    assert resolved.project == "cus1"
    assert resolved.ego().length_m == 5.0


def test_manifestless_library_bundle_reports_unknown_and_does_not_warn(tmp_path):
    """UT-C5-3: a real `S-C5`-packed bundle carries no
    `manifest.yaml`. Named "config" -- the exact directory name every real
    build packs into, and the value `ProjectModel` used to fall back to
    (`bundle_dir.name`) before this fix. Without a `known_project`, the
    honest answer is `"unknown"` (`R-SIM-25`), never that directory name.

    **And it must NOT warn** -- `AR-51`'s second half, which reversed this
    test's original assertion. `unknown` is an **absence**, not a
    **disagreement**: warning here printed *"is for project 'unknown', not
    the requested 'base'"*, which asserts a conflict between a value and a
    value we have just said we do not have. Three reasons it is wrong, in
    order:

    1. **The claim is false.** We do not know the bundle is not `base`.
    2. **It fires on every real packed bundle** on every path that does not
       supply `known_project`, which is the always-on condition
       `R-SIM-3a`/`NR-SIM-4` exist to prevent -- a warning that is always on
       trains a reader to ignore the one that matters. Measured: suite
       warnings went 8 -> 10 when the first half landed, in the direction
       the finding existed to reverse, including on fixtures whose directory
       name matched the request and which were silent before it.
    3. **The disclosure already exists and is the sanctioned one.**
       `resolved.project == "unknown"` reaches the HUD and the run manifest.
       `R-SIM-25` asks for `unknown` in the field; it does not ask for a
       warning on top of it.

    A *genuine* mismatch is unaffected and still warns -- see
    `test_manifestless_library_bundle_known_project_mismatch_still_warns`
    below, and `test_project_mismatch_emits_provenance_warning_and_still_
    resolves` above. Those two are what `R-SIM-3a` actually requires.
    """
    library_dir = tmp_path / "config"
    _make_real_bundle(library_dir)

    with warnings.catch_warnings():
        warnings.simplefilter("error", ProvenanceWarning)
        resolved = ProjectModel.resolve(library_dir=library_dir, project="base")

    assert resolved.project == "unknown"
    assert resolved.project != "config"


def test_manifestless_library_bundle_uses_known_project_and_never_warns_when_it_matches(tmp_path):
    """UT-C5-3: a caller that already loaded the component
    (`core/diagnostics.py`'s `_bundle_diagnoses`) supplies `known_project`
    from the DLL's own `adasManifest().project`. A correct real bundle then
    resolves to the real project and `ProvenanceWarning` does not fire --
    the defect measured four times against the real `df_sil` build tree."""
    library_dir = tmp_path / "config"
    _make_real_bundle(library_dir)

    with warnings.catch_warnings():
        warnings.simplefilter("error", ProvenanceWarning)
        resolved = ProjectModel.resolve(library_dir=library_dir, project="base", known_project="base")

    assert resolved.project == "base"


def test_manifestless_library_bundle_known_project_mismatch_still_warns(tmp_path):
    """UT-C5-3: `known_project` reports the truth, it does not
    silence a real mismatch -- a library genuinely built for `cus1` loaded
    against a run requesting `base` still warns, exactly as `R-SIM-3a`
    requires."""
    library_dir = tmp_path / "config"
    _make_real_bundle(library_dir)

    with pytest.warns(ProvenanceWarning):
        resolved = ProjectModel.resolve(library_dir=library_dir, project="base", known_project="cus1")

    assert resolved.project == "cus1"


def test_config_source_force_embedded_wins_over_a_higher_priority_explicit(tmp_path):
    """UT-C5-8: `force="embedded"` (`--config-source embedded`) resolves
    the recording's own bundle even though an `explicit` bundle -- which
    would normally win -- is also given. Forcing a tier is not merely a
    priority nudge; it is a different tier selected outright."""
    explicit_dir = _make_bundle(tmp_path, "explicit", project="fx", length=1.0, width=1.0, wheelbase=1.0, overhang=0.1)
    embedded_dir = _make_bundle(tmp_path, "embedded", project="fx", length=2.0, width=2.0, wheelbase=2.0, overhang=0.2)

    resolved = ProjectModel.resolve(explicit=explicit_dir, recording=embedded_dir, project="fx", force="embedded")
    assert resolved.bundle_origin == "embedded"
    assert resolved.ego().length_m == 2.0


def test_config_source_force_checkout_ignores_every_other_source(tmp_path):
    explicit_dir = _make_bundle(tmp_path, "explicit", project="base", length=9.0, width=9.0, wheelbase=9.0, overhang=0.9)

    resolved = ProjectModel.resolve(explicit=explicit_dir, project="base", force="checkout")
    assert resolved.bundle_origin == "checkout"
    assert resolved.ego().length_m != 9.0  # the real checkout value, not the ignored explicit one


def test_config_source_force_raises_naming_the_forced_tier_when_nothing_is_there(tmp_path):
    """`R-SIM-3a`'s "an override that is silent recreates the exact
    confusion the bundle exists to remove" -- forcing a tier that has
    nothing to resolve must fail loudly, never silently fall through to
    another tier the caller did not ask for."""
    with pytest.raises(AuthoringError, match="embedded"):
        ProjectModel.resolve(project="base", force="embedded")  # no recording= given at all


def test_config_source_force_raises_when_the_forced_directory_has_no_bundle(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(AuthoringError, match="library"):
        ProjectModel.resolve(library_dir=empty_dir, project="base", force="library")


def test_embedded_bundle_bytes_extracted_from_a_recording_resolve_with_no_checkout(tmp_path):
    """UT-C5-9: a recording's own embedded bundle bytes -- the actual
    thing `Recorder.open`'s `config_bundle_bytes` embeds and `RecordingReader.
    config_bundle_bytes()` reads back -- round-trip through
    `extract_embedded_bundle` into a real directory `ProjectModel.resolve`
    can read, with no checkout ever consulted (a nonexistent project name
    proves the checkout tier was never reached, not merely unused)."""
    source_bundle = _make_bundle(
        tmp_path, "source", project="fx", length=4.0, width=1.5, wheelbase=2.5, overhang=0.4,
    )
    embedded_bytes = bundle_bytes_for_recording(source_bundle)

    extracted_dir = tmp_path / "extracted_from_recording"
    extract_embedded_bundle(embedded_bytes, extracted_dir)

    resolved = ProjectModel.resolve(recording=extracted_dir, project="no_such_project_UT_C5_9")
    assert resolved.bundle_origin == "embedded"
    assert resolved.project == "fx"
    assert resolved.ego().length_m == 4.0
    assert resolved.ego().wheelbase_m == 2.5


def _make_real_bundle(bundle_dir: Path, *, newline: str = "\n") -> None:
    """A real S-C5-shaped bundle (default.yaml + vehicle/ego_params.yaml +
    fixture.ports.yaml, no manifest.yaml) -- as opposed to `_make_bundle`
    above, which is UT-A2-7/UT-A2-10's own synthetic fixture shape."""
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "vehicle").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "default.yaml").write_bytes(f"aeb:{newline}  AEB_TTC_BRAKE_THRESHOLD_S: 1.2{newline}".encode())
    (bundle_dir / "vehicle" / "ego_params.yaml").write_bytes(
        _EGO_TEMPLATE.format(length=4.5, width=1.8, wheelbase=2.7, overhang=0.9).replace("\n", newline).encode()
    )
    (bundle_dir / "fixture.ports.yaml").write_bytes(f"component: fixture{newline}".encode())


def test_bundle_sha256_is_stable_across_mixed_line_endings_and_iteration_order(tmp_path):
    """UT-C5-5, P-9: a bundle written with CRLF line endings hashes
    identically to the same content written with LF -- the property that
    makes a bundle built on Windows and one built on Ubuntu agree."""
    lf_dir = tmp_path / "lf"
    crlf_dir = tmp_path / "crlf"
    _make_real_bundle(lf_dir, newline="\n")
    _make_real_bundle(crlf_dir, newline="\r\n")

    lf = ProjectModel.resolve(library_dir=lf_dir, project="lf")
    crlf = ProjectModel.resolve(library_dir=crlf_dir, project="crlf")
    assert lf.bundle_sha256 == crlf.bundle_sha256
    assert len(lf.bundle_sha256) == 64  # a sha256 hex digest


def test_bundle_sha256_changes_on_case_only_rename(tmp_path):
    """UT-C5-4, P-3: sorted-path hashing means a case-only rename is a
    different bundle, never silently treated as the same file on a
    case-insensitive filesystem's behalf."""
    bundle_dir = tmp_path / "bundle"
    _make_real_bundle(bundle_dir)
    before = ProjectModel.resolve(library_dir=bundle_dir, project="bundle").bundle_sha256

    os.rename(bundle_dir / "default.yaml", bundle_dir / "Default.yaml")
    after = ProjectModel.resolve(library_dir=bundle_dir, project="bundle").bundle_sha256

    assert before != after


def test_bundle_sha256_excludes_its_own_file(tmp_path):
    """Writing bundle.sha256 into the directory and re-resolving must not
    change the hash on the next read -- it is computed OVER the other
    files, never over itself (a self-referential hash cannot be verified)."""
    bundle_dir = tmp_path / "bundle"
    _make_real_bundle(bundle_dir)
    first = ProjectModel.resolve(library_dir=bundle_dir, project="bundle").bundle_sha256

    (bundle_dir / "bundle.sha256").write_text(first + "\n", encoding="utf-8")
    second = ProjectModel.resolve(library_dir=bundle_dir, project="bundle").bundle_sha256

    assert first == second


def test_bundle_bytes_for_recording_round_trips_file_contents(tmp_path):
    """The embedded `/meta/config_bundle` blob (R-SIM-6) is a flat relpath
    -> content mapping that reconstructs every bundle file, newline-
    normalized -- what `sim view` on a colleague's recording relies on with
    no build present."""
    bundle_dir = tmp_path / "bundle"
    _make_real_bundle(bundle_dir, newline="\r\n")

    blob = bundle_bytes_for_recording(bundle_dir)
    mapping = yaml.safe_load(blob.decode("utf-8"))

    assert mapping["default.yaml"] == "aeb:\n  AEB_TTC_BRAKE_THRESHOLD_S: 1.2\n"
    assert mapping["vehicle/ego_params.yaml"].startswith("EGO_LENGTH_M: 4.5")
    assert mapping["fixture.ports.yaml"] == "component: fixture\n"


def test_bundle_sha256_agrees_with_pack_config_bundle_py(tmp_path):
    """S-C5's own cross-implementation proof: `interfaces/scripts/
    pack_config_bundle.py` (build-time, stdlib-only) and `adas_sim.model.
    project` (read-time) implement the P-9 algorithm independently --
    proven to agree here, over a bundle the FORMER actually packs. The
    stronger, full proof (adasInit(NULL) against a real compiled df_sil) is
    `tests/system/test_c5_relocatability.py`."""
    if not _INTERFACES_SCRIPTS.is_dir():
        pytest.skip(f"interfaces submodule not checked out at {_INTERFACES_SCRIPTS}")
    sys.path.insert(0, str(_INTERFACES_SCRIPTS))
    import pack_config_bundle  # noqa: PLC0415

    default_yaml = tmp_path / "src_default.yaml"
    default_yaml.write_text("aeb:\n  AEB_MAX_AGE_OBJECTS_S: 0.2\n", encoding="utf-8")
    ego_yaml = tmp_path / "src_ego.yaml"
    ego_yaml.write_text(_EGO_TEMPLATE.format(length=4.5, width=1.8, wheelbase=2.7, overhang=0.9).replace("\n", "\r\n"), encoding="utf-8")
    ports_yaml = tmp_path / "fixture.ports.yaml"
    ports_yaml.write_text("component: fixture\n", encoding="utf-8")

    bundle_dir = tmp_path / "packed"
    packed_digest = pack_config_bundle.pack(
        out=bundle_dir, default_yaml=default_yaml, ego_yaml=ego_yaml, ports_yaml=ports_yaml
    )

    read_digest = ProjectModel.resolve(library_dir=bundle_dir, project="packed").bundle_sha256
    assert read_digest == packed_digest
