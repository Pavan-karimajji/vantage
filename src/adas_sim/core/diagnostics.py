# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Environment facts behind `sim doctor` (DG-3).

Kept out of `cli/` (GT-9: the CLI is argument parsing and dispatch only) so
every fact here is reachable from a plain script with no argparse involved.
Seeded at S-A1 with the environment questions that matter before anything
else exists; grows one field per later stage that adds something worth
checking (pipeline/recording resolution, codec capabilities, bundle hashes).

**S-D6 completion (`UT-D6-8`).** `doctor_report()` gains four checks.
Codec capabilities need no input and are always reported; the other three
are optional and independently triggered -- each fires only when the
caller supplies enough to check it, so `sim doctor` with no flags stays
the S-A1 report plus the (input-independent) codec table:

- every registered codec's capabilities (`io.registry.codec_info`) --
  always reported, no flag needed.
- `--pipeline`/`--search`: which library each `dll:`/`stubdll:` stage's
  `impl:` stem resolves to, and by which pattern, listing every directory
  searched (`P-5`) -- `contracts.loader.resolve_library_report`, which
  (unlike `resolve_library`) answers this on success too. `Pipeline.
  parse_stages` (new) reads a pipeline's stage declarations with NO
  component resolution, precisely so a broken stem can be reported
  instead of crashing `sim doctor` itself before `Pipeline.load`'s own
  `_resolve_components` would otherwise raise.
- the same, plus `--config`: whether the viewer and the SUT would agree on
  the config bundle (`R-SIM-3a`'s core fear) -- the SUT's own real
  `config_bundle_sha256` (read by actually loading the resolved library,
  same as `sim probe`) compared against `model.project.ProjectModel`'s own
  resolution using the SAME `--config`/library-packed bundle.
- `--recording` (with `--pipeline`): which cuts the recording supports
  (`Session.feasible_cuts`, `R-SIM-12`/`R-SIM-23`), and whether the
  recording's own extension is even readable at all.
- `--config-source embedded|library|checkout` (`UT-C5-8`): forces the
  bundle-agreement check above to compare against exactly one tier rather
  than the normal explicit -> embedded -> library -> checkout priority
  order -- `model.project.ProjectModel.resolve`'s own `force=` parameter,
  `--recording`'s embedded bundle bytes extracted to a temp directory via
  `model.project.extract_embedded_bundle` (`UT-C5-9`) when `embedded` is
  forced. A forced tier that cannot resolve is reported as a problem
  naming the tier, never silently ignored.
- `--pipeline`, plus optional `--plugin-root` (`S-C8`): each resolved
  stage's own plug-in bundle (`model.plugins.PluginBundle.resolve`,
  explicit -> library `sim/` -> checkout -- no `embedded` tier here,
  `_plugin_diagnoses`'s own docstring on why) -- component, api, sha256,
  origin, root. A component with no `sim/` plug-ins is reported
  (`found: False`), never treated as a problem.

`"problems"` collects every finding that would break a real run --
`UT-D6-8`'s own three: a broken `impl:` stem, a bundle disagreement, and an
unreadable recording codec -- each message naming the file. `cli/doctor.py`
exits non-zero exactly when this list is non-empty.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from importlib import metadata
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from adas_sim.contracts.component import CtypesSilComponent
from adas_sim.contracts.loader import resolve_library_report
from adas_sim.contracts.pipeline import Pipeline, Stage
from adas_sim.core.errors import AuthoringError, SimError
from adas_sim.core.session import Session
from adas_sim.io.registry import (
    codec_info,
    is_registered_recording_extension,
    reader_for,
    registered_extensions,
)
from adas_sim.model.plugins import PluginBundle
from adas_sim.model.project import ProjectModel, extract_embedded_bundle

ConfigSource = Literal["embedded", "library", "checkout"]


def _install_mode() -> str:
    try:
        dist = metadata.distribution("adas-sim")
    except metadata.PackageNotFoundError:
        return "not installed"
    try:
        direct_url = dist.read_text("direct_url.json") or ""
    except OSError:
        direct_url = ""
    if '"editable": true' in direct_url:
        return "editable"
    return "standard"


def _library_diagnoses(stages: Sequence[Stage], search: Sequence[Path]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for stage in stages:
        if stage.mode == "off" or not stage.impl:
            continue
        kind, _, stem = stage.impl.partition(":")
        if kind not in ("dll", "stubdll"):
            continue
        report = resolve_library_report(stem, search=search)
        results.append({
            "stage": stage.name,
            "stem": stem,
            "resolved": str(report.resolved) if report.resolved is not None else "",
            "matched_pattern": report.matched_pattern or "",
            "candidate_patterns": list(report.candidate_patterns),
            "directories_searched": [str(d) for d in report.directories_searched],
            "ok": report.resolved is not None,
        })
    return results


def _bundle_diagnoses(
    library_diagnoses: Sequence[dict[str, object]], *,
    config_path: Path | None, project: str, config_source: ConfigSource | None = None,
    embedded_bundle_dir: Path | None = None,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for entry in library_diagnoses:
        if not entry["ok"]:
            continue  # nothing to load -- the library finding above already reports the real problem
        lib_path = Path(str(entry["resolved"]))
        try:
            sut_sha = CtypesSilComponent(lib_path).manifest.config_bundle_sha256
        except SimError as exc:
            results.append({
                "stage": entry["stage"], "ok": False,
                "detail": f"could not load {lib_path} to read its manifest: {exc}",
            })
            continue
        bundle_dir = lib_path.parent / "config"
        try:
            viewer = ProjectModel.resolve(
                explicit=config_path, library_dir=bundle_dir, recording=embedded_bundle_dir,
                project=project, force=config_source,
            )
        except AuthoringError as exc:
            results.append({
                "stage": entry["stage"], "ok": False,
                "detail": f"--config-source {config_source} could not resolve: {exc}",
            })
            continue
        agree = bool(sut_sha) and sut_sha == viewer.bundle_sha256
        results.append({
            "stage": entry["stage"],
            "sut_config_bundle_sha256": sut_sha or "(unresolved -- adasInit(NULL) will fail)",
            "viewer_bundle_sha256": viewer.bundle_sha256,
            "viewer_bundle_origin": viewer.bundle_origin,
            "ok": agree,
        })
    return results


def _plugin_diagnoses(
    library_diagnoses: Sequence[dict[str, object]], *, plugin_root: Path | None = None,
) -> list[dict[str, object]]:
    """S-C8's own remaining item: `sim doctor` reports each resolved
    stage's plug-in bundle -- **explicit -> library `sim/` -> checkout**
    (`PluginBundle.resolve`, the same tiers `_bundle_diagnoses` above
    already reports for the CONFIG bundle, R-SIM-20's "the two are the
    same mechanism applied to configuration and to plug-ins"). No
    `embedded` tier here (unlike the config bundle): `sim doctor` diagnoses
    a LIBRARY/pipeline, not a loaded `Session`, so there is no recording in
    play to embed a plug-in bundle in -- `embedded` stays `ProjectModel`'s
    own concern. A component with no `sim/` plug-ins at any tier is a
    legitimate state (`PluginBundle.resolve`'s own docstring), reported as
    `found: False`, never added to `problems`."""
    results: list[dict[str, object]] = []
    for entry in library_diagnoses:
        if not entry["ok"]:
            continue  # nothing to load -- the library finding above already reports the real problem
        lib_path = Path(str(entry["resolved"]))
        library_plugin_dir = lib_path.parent / "sim"
        bundle = PluginBundle.resolve(explicit=plugin_root, library_dir=library_plugin_dir)
        if bundle is None:
            results.append({
                "stage": entry["stage"], "found": False,
                "detail": f"no plugin.yaml at {plugin_root or library_plugin_dir} -- "
                          "this component contributes no sim/ plug-ins",
            })
            continue
        results.append({
            "stage": entry["stage"], "found": True, "component": bundle.component,
            "api": bundle.api, "sha256": bundle.sha256, "origin": bundle.origin, "root": str(bundle.root),
        })
    return results


def _codec_diagnoses() -> list[dict[str, object]]:
    return [{"extension": ext, **(codec_info(ext) or {})} for ext in registered_extensions()]


def _recording_diagnosis(
    recording_path: Path, pipeline: Pipeline | None,
) -> dict[str, object]:
    if not is_registered_recording_extension(recording_path.suffix):
        return {
            "path": str(recording_path), "ok": False,
            "detail": f"{recording_path.suffix!r} is not a registered recording codec extension",
        }
    info = codec_info(recording_path.suffix) or {}
    if not info.get("has_reader"):
        return {
            "path": str(recording_path), "ok": False,
            "detail": f"codec {recording_path.suffix!r} has no reader -- write-only, cannot open this recording",
        }
    result: dict[str, object] = {"path": str(recording_path), "ok": True, "detail": ""}
    if pipeline is not None:
        session = Session.open(recording_path)
        result["feasible_cuts"] = [
            {"stage": cut.stage, "feasible": cut.feasible, "missing": list(cut.missing)}
            for cut in session.feasible_cuts(pipeline)
        ]
    return result


def doctor_report(
    *,
    pipeline_path: Path | None = None,
    search: Sequence[Path] = (),
    recording_path: Path | None = None,
    config_path: Path | None = None,
    project: str = "base",
    config_source: ConfigSource | None = None,
    plugin_root: Path | None = None,
) -> dict[str, object]:
    """Gather `sim doctor`'s facts (DG-3). With no arguments, exactly the
    S-A1 slice (interpreter, install mode, platform, console encoding, line
    endings) -- every check below fires only when given enough to check it,
    so a bare `sim doctor` is unchanged from before this stage."""
    report: dict[str, object] = {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "adas_sim_install_mode": _install_mode(),
        "platform": sys.platform,
        "stdout_encoding": getattr(sys.stdout, "encoding", None),
        "stderr_encoding": getattr(sys.stderr, "encoding", None),
        "os_line_separator": repr(os.linesep),
        "codecs": _codec_diagnoses(),
    }

    problems: list[str] = []

    pipeline: Pipeline | None = None
    if pipeline_path is not None:
        # Library resolution first, off the raw stage declarations
        # (Pipeline.parse_stages, no dll:/stubdll: lookup) -- Pipeline.load
        # itself raises on the first stage whose library does not resolve
        # (_resolve_components), which would otherwise make "a broken
        # stem" undiagnosable: the exact condition sim doctor exists to
        # report would instead crash it.
        stages = Pipeline.parse_stages(pipeline_path)
        libraries = _library_diagnoses(stages, search)
        report["libraries"] = libraries
        for entry in libraries:
            if not entry["ok"]:
                problems.append(
                    f"stage '{entry['stage']}': impl: stem '{entry['stem']}' did not resolve "
                    f"(tried {entry['candidate_patterns']} under {entry['directories_searched']})"
                )

        try:
            pipeline = Pipeline.load(pipeline_path, search=search)
        except SimError as exc:
            report["pipeline_load_error"] = str(exc)
            problems.append(f"pipeline '{pipeline_path}' failed to load: {exc}")
        else:
            # --config-source embedded (UT-C5-8) needs a real directory to
            # compare against, not the recording file itself -- extract its
            # embedded bundle bytes (UT-C5-9's own mechanism) into a temp
            # dir that lives only for the duration of this one comparison.
            with TemporaryDirectory(prefix="adas_sim_doctor_bundle_") as tmp_dir:
                embedded_bundle_dir: Path | None = None
                if config_source == "embedded" and recording_path is not None:
                    reader = reader_for(recording_path)
                    try:
                        bundle_bytes = getattr(reader, "config_bundle_bytes", lambda: b"")()
                    finally:
                        reader.close()
                    embedded_bundle_dir = Path(tmp_dir)
                    extract_embedded_bundle(bundle_bytes, embedded_bundle_dir)
                bundles = _bundle_diagnoses(
                    libraries, config_path=config_path, project=project,
                    config_source=config_source, embedded_bundle_dir=embedded_bundle_dir,
                )
            report["bundles"] = bundles
            for entry in bundles:
                if not entry["ok"]:
                    detail = entry.get("detail") or (
                        f"SUT bundle {entry.get('sut_config_bundle_sha256')} != "
                        f"viewer bundle {entry.get('viewer_bundle_sha256')} (origin={entry.get('viewer_bundle_origin')})"
                    )
                    problems.append(f"stage '{entry['stage']}': config bundle mismatch -- {detail}")

            report["plugins"] = _plugin_diagnoses(libraries, plugin_root=plugin_root)

    if recording_path is not None:
        recording = _recording_diagnosis(recording_path, pipeline)
        report["recording"] = recording
        if not recording["ok"]:
            problems.append(f"recording '{recording_path}': {recording['detail']}")

    report["problems"] = problems
    return report
