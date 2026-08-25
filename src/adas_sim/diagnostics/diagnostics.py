# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Environment facts behind `sim doctor` (`DG-3`).

Kept out of `cli/` (`GT-9`) so every fact is reachable from a plain script with
no argparse involved.

`doctor_report()` always reports the registered codecs' capabilities, which
need no input. Everything else is triggered independently by what the caller
supplies, so `sim doctor` with no flags stays the environment report:

- `--pipeline`/`--search` -- which library each `dll:`/`stubdll:` stage
  resolves to, by which pattern, listing every directory searched (`P-5`).
  Uses `Pipeline.parse_stages`, which reads stage declarations without
  resolving components, so a broken stem is reported rather than crashing
  `sim doctor` before it can report anything.
- plus `--config` -- whether the viewer and the SUT would agree on the config
  bundle (`R-SIM-3a`'s core fear): the SUT's real `config_bundle_sha256`,
  read by loading the library, against `ProjectModel`'s own resolution.
- `--config-source embedded|library|checkout` -- force that comparison onto
  one tier instead of the normal priority order. A forced tier that cannot
  resolve is reported as a problem naming the tier, never silently ignored.
- `--recording` (with `--pipeline`) -- which cuts the recording supports
  (`R-SIM-12`, `R-SIM-23`), and whether its extension is readable at all.
- `--plugin-root` -- each stage's plug-in bundle: component, api, sha256,
  origin, root. A component with no `sim/` plug-ins is reported, not a problem.

`"problems"` collects findings that would break a real run (`UT-D6-8`), each naming the
file. `cli/doctor.py` exits non-zero exactly when that list is non-empty.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from importlib import metadata
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from adas_sim.resolve.probe import probe_manifest
from adas_sim.resolve.library import resolve_library_report
from adas_sim.graph.build import Pipeline, Stage
from adas_sim.diagnostics.errors import AuthoringError, SimError
from adas_sim.session.session import Session
from adas_sim.plugins.registry import (
    codec_info,
    is_registered_recording_extension,
    reader_for,
    registered_extensions,
)
from adas_sim.resolve.plugins import PluginBundle
from adas_sim.config.project import ProjectModel, extract_embedded_bundle

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
            # `probe_manifest` (`resolve/probe.py`, `SW-0409`): reads
            # `adasManifest()` only -- a diagnosis never opens a handle.
            sut_manifest = probe_manifest(lib_path)
        except SimError as exc:
            results.append({
                "stage": entry["stage"], "ok": False,
                "detail": f"could not load {lib_path} to read its manifest: {exc}",
            })
            continue
        sut_sha = sut_manifest.config_bundle_sha256
        bundle_dir = lib_path.parent / "config"
        try:
            # known_project=sut_manifest.project: a real S-C5-packed
            # bundle carries no manifest.yaml of its own, so without this the
            # library tier fell back to bundle_dir.name ("config", the
            # directory every build packs into) and ProvenanceWarning fired
            # on every correct bundle. The loaded library's own manifest is
            # the one place that project genuinely lives.
            viewer = ProjectModel.resolve(
                explicit=config_path, library_dir=bundle_dir, recording=embedded_bundle_dir,
                project=project, force=config_source, known_project=sut_manifest.project,
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


#: `ST-D6-4` (`sim_sil_contract.md` section 10, `NR-SIM-48`): the thirteen
#: rows of "what a component owes the framework," stated the same way every
#: other `sim doctor` check is -- generic over a `component_root` a caller
#: supplies, never a hardcoded name (`R-SIM-1`). Each entry: the row's own
#: number, a short label matching section 10's own table, whether it is
#: `"required"`/`"conditional"`/`"optional"` (section 10's own legend), and a
#: callable answering `present` for a given `component_root`. Required rows
#: absent are unconditionally a gap; conditional/optional rows are reported
#: present-or-absent WITHOUT this tool guessing "legitimate" for an absence
#: it cannot itself justify (`vdy`'s "nothing to draw" is a fact about `vdy`,
#: not something the framework may know, R-SIM-1) -- a human reads the
#: report and makes that call, section 10's own "three readings" already
#: does this by hand for `df`/`vdy`/`perception-core`.
def _has_files(directory: Path, *, suffix: str | None = None) -> bool:
    if not directory.is_dir():
        return False
    return any(p.is_file() and (suffix is None or p.suffix == suffix) for p in directory.rglob("*"))


def _config_bundle_packed(component_root: Path, component_name: str) -> bool:
    sil_cmake = component_root / "src" / "platform" / f"{component_name}_sil" / "CMakeLists.txt"
    if not sil_cmake.is_file():
        return False
    return "adas_pack_config_bundle" in sil_cmake.read_text(encoding="utf-8", errors="replace")


def _period_us_declared(component_root: Path) -> bool:
    project_dir = component_root / "src" / "project"
    if not project_dir.is_dir():
        return False
    for default_yaml in project_dir.glob("*/default.yaml"):
        if "_PERIOD_US" in default_yaml.read_text(encoding="utf-8", errors="replace"):
            return True
    return False


def _scenarios_with_expectations(component_root: Path) -> bool:
    tests_dir = component_root / "tests"
    if not tests_dir.is_dir():
        return False
    for scenario in tests_dir.rglob("*.yaml"):
        if "expect:" in scenario.read_text(encoding="utf-8", errors="replace"):
            return True
    return False


def component_checklist(component_root: Path) -> list[dict[str, object]]:
    """`sim doctor --component <root>` (`ST-D6-4`): each of section 10's
    thirteen rows, checked mechanically against a real component tree.
    `component_root` is a path (e.g. `modules/df`), like every other
    `sim doctor` input -- never a bare name this module would have to guess
    a superproject layout to resolve (`R-SIM-11`). The component's own name
    is read from `conf/ports.yaml`'s `component:` field when present (rows
    4/6 need it to name a real directory), falling back to `component_root`'s
    own directory name otherwise -- best-effort, stated as such, since a
    missing `conf/ports.yaml` is itself row 2's own finding."""
    ports_yaml = component_root / "conf" / "ports.yaml"
    component_name = component_root.name
    if ports_yaml.is_file():
        for line in ports_yaml.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("component:"):
                component_name = stripped.split(":", 1)[1].strip()
                break

    rows: list[tuple[int, str, str, bool]] = [
        (1, "conf/build.yml", "required", (component_root / "conf" / "build.yml").is_file()),
        (2, "conf/ports.yaml", "required", ports_yaml.is_file()),
        (3, "src/component/** port structs", "required", _has_files(component_root / "src" / "component", suffix=".hpp")),
        (4, "src/platform/<name>_sil/", "required",
         (component_root / "src" / "platform" / f"{component_name}_sil").is_dir()),
        (5, "src/project/<p>/default.yaml", "required",
         any((component_root / "src" / "project").glob("*/default.yaml"))),
        (6, "config bundle packed beside the library", "required", _config_bundle_packed(component_root, component_name)),
        (7, "<COMPONENT>_<FN>_PERIOD_US in calibration", "required", _period_us_declared(component_root)),
        (8, "sim/plugin.yaml + sim/layers/**", "conditional",
         (component_root / "sim" / "plugin.yaml").is_file() and _has_files(component_root / "sim" / "layers")),
        (9, "sim/ingest/**", "conditional", _has_files(component_root / "sim" / "ingest")),
        (10, "sim/pipelines/**", "optional", _has_files(component_root / "sim" / "pipelines")),
        (11, "sim/viewpoints.yaml, sim/sensor_models/**", "optional",
         (component_root / "sim" / "viewpoints.yaml").is_file() or _has_files(component_root / "sim" / "sensor_models")),
        (12, "sim/tolerance.yaml", "conditional", (component_root / "sim" / "tolerance.yaml").is_file()),
        (13, "scenarios with expect: blocks", "conditional", _scenarios_with_expectations(component_root)),
    ]

    return [
        {
            "row": n, "artifact": artifact, "kind": kind, "present": present,
            # Required + absent is the one case this tool CAN call unconditionally --
            # every other absence is reported, never judged (see this function's own
            # docstring on why).
            "gap": kind == "required" and not present,
        }
        for n, artifact, kind, present in rows
    ]


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
    component_root: Path | None = None,
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

    if component_root is not None:
        # ST-D6-4: deliberately NOT wired into `problems` -- section 10's
        # own text calls this "deliberately not a gate," so a required row's
        # absence is reported (and printed loudly by cli/doctor.py) but
        # never makes `sim doctor`'s exit code non-zero.
        report["component_checklist"] = component_checklist(component_root)

    report["problems"] = problems
    return report
