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
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from warnings import warn

import yaml

from adas_sim.core.errors import ProvenanceWarning
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


def _bundle_ego(bundle_dir: Path) -> tuple[str, EgoModel] | None:
    """A bundle-shaped directory: `<dir>/vehicle/ego_params.yaml`, optionally
    `<dir>/manifest.yaml` naming its project. `None` if the shape isn't
    present -- callers fall through to the next tier.

    A real S-C5-packed bundle carries no `manifest.yaml` (the checked-in
    `<component>.ports.yaml` deliberately excludes `project:` too -- build-
    variant data must not churn a checked-in file, `test_generic_abi.cpp`'s
    `EmbeddedManifestAgreesWithCheckedInPortsYaml`), so `project` falls back
    to `bundle_dir.name` there -- meaningless for a real `.../config/`
    directory. The only place a real bundle's built project genuinely lives
    is the loaded library's own `adasManifest()`. Real cross-component
    project-agreement checking is `S-C5`'s addendum scope (`OD-11`),
    deferred; `manifest.yaml` stays only to keep this module's own
    synthetic-fixture tests (`UT-A2-7`, `UT-A2-10`) meaningful."""
    ego_path = bundle_dir / "vehicle" / "ego_params.yaml"
    if not ego_path.is_file():
        return None
    project = bundle_dir.name
    manifest_path = bundle_dir / "manifest.yaml"
    if manifest_path.is_file():
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        project = str(manifest.get("project", project))
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
    def resolve(
        cls,
        *,
        recording: Path | None = None,
        library_dir: Path | None = None,
        explicit: Path | None = None,
        project: str = "base",
    ) -> ProjectModel:
        """`project` is the source-checkout fallback's project name (R-VAR-4:
        `base` is the no-specific-program default) and, for the other three
        tiers, the caller's *expectation* -- a resolved bundle whose own
        manifest names a different project emits `ProvenanceWarning` and
        still resolves (R-SIM-3a), it never raises and never silently
        substitutes.
        """
        for origin, bundle_dir in (("explicit", explicit), ("embedded", recording), ("library", library_dir)):
            if bundle_dir is None:
                continue
            found = _bundle_ego(Path(bundle_dir))
            if found is None:
                continue
            resolved_project, ego = found
            if resolved_project != project:
                warn(
                    ProvenanceWarning(
                        f"{origin} bundle at {bundle_dir} is for project {resolved_project!r}, "
                        f"not the requested {project!r}"
                    )
                )
            sha = _bundle_sha256(Path(bundle_dir))
            return cls(project=resolved_project, bundle_sha256=sha, bundle_origin=origin, _ego=ego)

        ego = EgoModel.load(project)
        sha = _single_file_sha256(SHARED_CONFIG_PROJECTS / project / "vehicle" / "ego_params.yaml")
        return cls(project=project, bundle_sha256=sha, bundle_origin="checkout", _ego=ego)
