# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`ProjectModel.resolve(...)` -- configuration is the source of geometry
(R-SIM-3, sim_api_reference.md §6). Resolution order **explicit ->
embedded-in-recording -> library config/ -> source checkout**, and
`bundle_origin` always states which (R-SIM-3a): the failure this prevents is
the viewer and the SUT reading different files and agreeing only by
coincidence.

**Deferred, deliberately:** `ProjectModel.footprint()`/`.sensor()`/
`.camera()` are not implemented on this class yet. Today the only calibration
this framework may read generically is `shared_config`'s `ego_params.yaml`
(cross-component by design, docs/shared_config_plan.md); real sensor poses
and class footprints are calibration **owned by the consuming component**
(R-SIM-9 -- a driving function's own sensor-pose and class-footprint
calibration keys are that function's own data). `model/objects.py`
and `model/sensors.py` are the reusable, component-agnostic primitives a
component's own `S-B1` layer-provider code calls with **its own** resolved
calibration mapping; wiring a generic path onto `ProjectModel` itself needs a
concrete generic data source that does not exist yet, so it is not invented
here (`sim_api_reference.md` §11: internal helpers are free, but a
`ProjectModel.footprint`/`.sensor`/`.camera` bound to nothing real would be
speculative, not free).
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from warnings import warn

import yaml

from adas_sim.core.errors import AuthoringError, ProvenanceWarning
from adas_sim.model.ego import SHARED_CONFIG_PROJECTS, EgoModel

#: `sim_api_reference.md` §6 declares only `"embedded" | "library" |
#: "checkout"`, omitting the fourth, highest-priority tier its own
#: `resolve()` docstring names ("explicit -> embedded -> library ->
#: checkout") and `UT-A2-7` exercises ("with all four sources present,
#: explicit wins ... bundle_origin reports which"). Recorded as a finding in
#: docs/sim_implementation_plan.md (S-A2): a `bundle_origin` that cannot
#: report "explicit" cannot make `UT-A2-7`'s own claim true, so "explicit" is
#: added here as a fourth literal.
BundleOrigin = Literal["explicit", "embedded", "library", "checkout"]

#: What a bundle's project reads when nothing authoritative says (`R-SIM-25`,
#: `NR-SIM-4`: "a field the tool cannot fill reads `unknown`, never a
#: plausible-looking default"). A named constant rather than three string
#: literals because `_resolve_one` must be able to ask *"is this an absence?"*
#: -- and a comparison against a spelled `"unknown"` is exactly the kind of
#: literal that drifts from the value it is testing (`AR-51`).
UNKNOWN_PROJECT = "unknown"


def _bundle_ego(bundle_dir: Path, *, known_project: str | None = None) -> tuple[str, EgoModel] | None:
    """A bundle-shaped directory: `<dir>/vehicle/ego_params.yaml`, optionally
    `<dir>/manifest.yaml` naming its project. `None` if the shape isn't
    present -- callers fall through to the next tier.

    A real S-C5-packed bundle carries no `manifest.yaml` (the checked-in
    `<component>.ports.yaml` deliberately excludes `project:` too -- build-
    variant data must not churn a checked-in file, `test_generic_abi.cpp`'s
    `EmbeddedManifestAgreesWithCheckedInPortsYaml`), so a real `.../config/`
    directory has no project name to read from its own bytes at all. The only
    place a real bundle's built project genuinely lives is the loaded
    library's own `adasManifest()` -- `known_project` is that value, supplied
    by a caller that already loaded the component (`core/diagnostics.py`'s
    `_bundle_diagnoses`, `S-C5` addendum `OD-11`). **`bundle_dir.name` is
    never used as a project** (`R-SIM-25`, `AR-51`, 2026-08-06) -- it is a
    plausible-looking default from an accident of a path, exactly the shape
    that rule forbids. Falls back to `"unknown"` when neither a
    `manifest.yaml` nor a `known_project` is available. `manifest.yaml` stays
    only to keep this module's own synthetic-fixture tests (`UT-A2-7`,
    `UT-A2-10`) meaningful."""
    ego_path = bundle_dir / "vehicle" / "ego_params.yaml"
    if not ego_path.is_file():
        return None
    manifest_path = bundle_dir / "manifest.yaml"
    if manifest_path.is_file():
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        project = str(manifest.get("project", known_project or UNKNOWN_PROJECT))
    else:
        project = known_project or UNKNOWN_PROJECT
    return project, EgoModel.from_yaml_file(ego_path, project=project)


def _bundle_sha256(bundle_dir: Path) -> str:
    """S-C5, P-9: hashed over every file in `bundle_dir` (excluding
    `bundle.sha256` itself) -- sorted POSIX-relative paths, UTF-8 bytes,
    `\\n` newlines, so a bundle built on either platform hashes the same.
    Identical algorithm to `interfaces/scripts/pack_config_bundle.py`'s
    `bundle_sha256()`, implemented independently (a component's build must
    not require `adas_sim`) -- proven to agree by `ST-C5-1`, not by sharing
    code across the two repos. Generic over whatever files are actually
    present, so it covers both a real packed bundle (`default.yaml` +
    `vehicle/ego_params.yaml` + `<component>.ports.yaml`) and a
    fixture-shaped test bundle carrying only a subset."""
    files = sorted(
        p.relative_to(bundle_dir).as_posix()
        for p in bundle_dir.rglob("*")
        if p.is_file() and p.name != "bundle.sha256"
    )
    h = hashlib.sha256()
    for relpath in files:
        normalized = (bundle_dir / relpath).read_text(encoding="utf-8").replace("\r\n", "\n")
        h.update(relpath.encode("utf-8") + b"\n")
        h.update(normalized.encode("utf-8") + b"\n")
    return h.hexdigest()


def _single_file_sha256(path: Path) -> str:
    """The `checkout` tier's hash: no bundle directory exists there at all
    (a bare `shared_config` checkout, flagged as unverified provenance), so
    the honest thing to hash is the one file actually read -- never a
    directory that was never assembled."""
    normalized = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


_MISSING = object()


def _get_nested(doc: object, path: tuple[str, ...]) -> object:
    node = doc
    for part in path:
        if not isinstance(node, dict) or part not in node:
            return _MISSING
        node = node[part]
    return node


def _set_nested(doc: dict, path: tuple[str, ...], value: object) -> None:
    node = doc
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value


def materialize_derived_bundle(base_bundle_dir: Path, overrides: Mapping[str, object], dest_dir: Path) -> str:
    """`NR-SIM-6`, `UT-C5-6`: the calibration-sweep mechanism arch §5.6
    ("Overrides and sweeps") names -- `run.overrides:` must not force a
    rebuild, so a sweep run derives a NEW bundle directory from the packed
    one plus the override set, instead of editing either.

    `overrides` keys are `run.overrides:` addresses, e.g.
    `"<function>.<CALIBRATION_KEY>"` -- a real per-function `default.yaml`
    (`df`'s own, `src/project/<p>/default.yaml`) nests exactly this way,
    one top-level key per function, so a dotted address IS the YAML path,
    not a label: `("<function>", "<CALIBRATION_KEY>")`. A single-segment
    address (`"EGO_WHEELBASE_M"`) matches a flat file the same walk
    (`vehicle/ego_params.yaml` has no nesting). This module still learns
    no function name from any of this (`R-SIM-1` — no such literal
    appears here, checked by the same `GT-1` grep this docstring is
    written to keep passing) -- it resolves generically, by searching
    every YAML file already in `base_bundle_dir` for the one where that
    exact path already resolves to a value. Same discipline `R-SIM-15`
    states for a port override: **an override may change an existing
    value, never create a new key** -- a path present in zero files, or
    in more than one, is an `AuthoringError` naming the address and every
    candidate found (an ambiguous match is exactly as unsafe as a missing
    one, never guessed).

    Copies every file first (so an unrelated file -- `<component>.ports.
    yaml`, anything else the build packed -- survives untouched), then
    rewrites only the files actually patched, then recomputes and rewrites
    `bundle.sha256` the same way the real build does (`_bundle_sha256`) --
    a derived bundle is shaped exactly like a packed one, never a
    look-alike. Returns the derived bundle's own hash, so a caller can
    record both it and `base_bundle_dir`'s (`R-SIM-3a`'s "provenance stays
    exact"): `dest_dir`'s own lifetime is the caller's choice, same as
    `extract_embedded_bundle`."""
    shutil.copytree(base_bundle_dir, dest_dir, dirs_exist_ok=True)
    yaml_files = sorted(p for p in dest_dir.rglob("*.yaml"))
    docs = {path: (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) for path in yaml_files}
    touched: set[Path] = set()
    for address, value in overrides.items():
        path_parts = tuple(address.split("."))
        candidates = [path for path, doc in docs.items() if _get_nested(doc, path_parts) is not _MISSING]
        if len(candidates) != 1:
            raise AuthoringError(
                expected=f"exactly one bundle file already declaring {address!r}",
                found=f"{len(candidates)} match(es): {[p.name for p in candidates]}",
                where=f"run.overrides {address!r} against {base_bundle_dir}",
                hint="a run.overrides: entry can only change a calibration key the bundle "
                     "already declares, in exactly one file -- it never creates a new key",
            )
        _set_nested(docs[candidates[0]], path_parts, value)
        touched.add(candidates[0])
    for path in touched:
        path.write_text(yaml.safe_dump(docs[path], sort_keys=False), encoding="utf-8", newline="\n")
    sha = _bundle_sha256(dest_dir)
    (dest_dir / "bundle.sha256").write_text(sha + "\n", encoding="utf-8", newline="\n")
    return sha


def bundle_bytes_for_recording(bundle_dir: Path) -> bytes:
    """S-C5, R-SIM-6: serializes a bundle directory's files into the "few kB
    of YAML" `Recorder.open()`'s `config_bundle_bytes` embeds on `/meta/
    config_bundle` (`sim_resim_and_recording.md` §3.4) -- a flat mapping of
    bundle-relative POSIX path to file content, so a reader on a machine
    with no build can reconstruct the exact directory `adasInit` read.
    Includes `bundle.sha256` itself (unlike the hash algorithm above, which
    excludes it while computing it) -- the embedded copy is a full mirror,
    not an input to a second hash."""
    mapping = {
        p.relative_to(bundle_dir).as_posix(): p.read_text(encoding="utf-8").replace("\r\n", "\n")
        for p in sorted(bundle_dir.rglob("*"))
        if p.is_file()
    }
    return yaml.safe_dump(mapping, sort_keys=True).encode("utf-8")


def extract_embedded_bundle(config_bundle_bytes: bytes, dest_dir: Path) -> None:
    """The inverse of `bundle_bytes_for_recording` (`UT-C5-9`): writes a
    recording's own embedded config-bundle bytes (`RecordingReader.
    config_bundle_bytes()`, `/meta/config_bundle`) back out as real files
    under `dest_dir`, so `ProjectModel.resolve(recording=dest_dir)` has an
    actual directory to read -- the "embedded" tier's missing half.
    `bundle_bytes_for_recording` writes bytes INTO a recording; nothing
    wrote them back OUT until this. `dest_dir` is the caller's own choice
    (a temp directory, typically) -- this function only ever writes inside
    it, never decides its lifetime."""
    mapping = yaml.safe_load(config_bundle_bytes.decode("utf-8")) or {}
    for relpath, content in mapping.items():
        path = dest_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


@dataclass(frozen=True, slots=True)
class ProjectModel:
    project: str
    bundle_sha256: str
    bundle_origin: BundleOrigin
    _ego: EgoModel

    def __repr__(self) -> str:
        return f"<ProjectModel {self.project!r} origin={self.bundle_origin}>"

    def ego(self) -> EgoModel:
        return self._ego

    @classmethod
    def _resolve_one(
        cls, origin: BundleOrigin, bundle_dir: Path, *, project: str, known_project: str | None = None,
    ) -> ProjectModel | None:
        found = _bundle_ego(bundle_dir, known_project=known_project)
        if found is None:
            return None
        resolved_project, ego = found
        # `unknown` is an ABSENCE, never a DISAGREEMENT (`AR-51`, second half,
        # 2026-08-06). `AR-51`'s first half stopped `bundle_dir.name` being
        # reported as a project and fell back to `"unknown"` -- correct, and
        # `R-SIM-25` requires exactly that. But leaving the comparison below
        # unguarded turned the absence into a mismatch claim: a real packed
        # bundle with no `known_project` supplied warned *"is for project
        # 'unknown', not the requested 'base'"*, which asserts a conflict
        # between a value and a value we have just said we do not have. It
        # also fired on fixtures whose directory name matched the request and
        # which were therefore silent BEFORE the first half landed -- suite
        # warnings went 8 -> 10, in the direction the finding existed to fix.
        #
        # The cry-wolf failure `R-SIM-3a`/`NR-SIM-4` guard against is not about
        # which string is printed: it is that a warning which is always on
        # trains a reader to ignore the one signal that matters. A caller that
        # wants the project checked supplies `known_project`; one that cannot
        # gets `unknown` on the model and in the HUD, which is the honest
        # answer and needs no warning to say so.
        if resolved_project != project and resolved_project != UNKNOWN_PROJECT:
            warn(
                ProvenanceWarning(
                    f"{origin} bundle at {bundle_dir} is for project {resolved_project!r}, "
                    f"not the requested {project!r}"
                )
            )
        sha = _bundle_sha256(bundle_dir)
        return cls(project=resolved_project, bundle_sha256=sha, bundle_origin=origin, _ego=ego)

    @classmethod
    def _resolve_checkout(cls, project: str) -> ProjectModel:
        ego = EgoModel.load(project)
        sha = _single_file_sha256(SHARED_CONFIG_PROJECTS / project / "vehicle" / "ego_params.yaml")
        return cls(project=project, bundle_sha256=sha, bundle_origin="checkout", _ego=ego)

    @classmethod
    def resolve(
        cls,
        *,
        recording: Path | None = None,
        library_dir: Path | None = None,
        explicit: Path | None = None,
        project: str = "base",
        force: Literal["embedded", "library", "checkout"] | None = None,
        known_project: str | None = None,
    ) -> ProjectModel:
        """`project` is the source-checkout fallback's project name (R-VAR-4:
        `base` is the no-specific-program default) and, for the other three
        tiers, the caller's *expectation* -- a resolved bundle whose own
        manifest names a different project emits `ProvenanceWarning` and
        still resolves (R-SIM-3a), it never raises and never silently
        substitutes.

        `known_project`, when given, is what a real bundle without its own
        `manifest.yaml` (every `S-C5`-packed one) reports as its project --
        the loaded library's own `adasManifest().project` (`AR-51`), supplied
        by a caller that already has it (`core/diagnostics.py`, which passes
        it whichever tier ends up resolving: `--config` pointed at the same
        library-packed bundle is still that library's own project, not a
        second, different bundle). A manifest.yaml already present always
        wins over it (a fixture deliberately testing a mismatch is
        unaffected). Omitted, a manifest-less bundle reports `"unknown"`,
        never `bundle_dir.name`.

        `force`, when given, skips the normal explicit -> embedded ->
        library -> checkout priority order and resolves EXACTLY the named
        tier (`UT-C5-8`, `--config-source embedded|library|checkout` on
        the CLI, `sim_architecture.md` §5.6) -- a caller forcing
        `"embedded"` genuinely wants the recording's OWN bundle even if a
        newer library bundle is also available, and a forced tier that
        cannot actually resolve is a **hard failure, never a silent
        fall-through to a different tier** (the same "an override that is
        silent recreates the exact confusion the bundle exists to
        remove" reasoning `R-SIM-3a` already states for a project
        mismatch). `explicit=<path>` already covers the CLI's fourth form,
        `--config-source <path>` -- there is no `force="explicit"`, since
        an explicit path already IS the override, not a tier selection.
        """
        if force is not None:
            if force == "checkout":
                return cls._resolve_checkout(project)
            bundle_dir = recording if force == "embedded" else library_dir
            if bundle_dir is not None:
                resolved = cls._resolve_one(force, Path(bundle_dir), project=project, known_project=known_project)
                if resolved is not None:
                    return resolved
            raise AuthoringError(
                expected=f"a real bundle to force --config-source {force} against",
                found="no bundle there" if bundle_dir is not None else f"no {force} source was given at all",
                where="adas_sim.model.project.ProjectModel.resolve",
                hint=f"--config-source {force} was forced but that tier has nothing to resolve -- "
                     "point it at a real bundle, or drop the forced source",
            )

        for origin, bundle_dir in (("explicit", explicit), ("embedded", recording), ("library", library_dir)):
            if bundle_dir is None:
                continue
            resolved = cls._resolve_one(origin, Path(bundle_dir), project=project, known_project=known_project)
            if resolved is not None:
                return resolved

        return cls._resolve_checkout(project)
