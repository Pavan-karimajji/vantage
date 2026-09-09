#!/usr/bin/env python3
"""Bootstrap stub - docs/imp_design.md §2.4 (supersedes the pre-WP-03
~516-line build orchestrator, now `adas_build_tools`, published from
`modules/toolchain` and installed per-component via pip+venv).

Physically identical across every component in this repo (df, vdy,
interfaces, mathlib, perception-core, shared_config, sim) - propagating a
future fix means editing modules/toolchain/copy_files/scripts/build.py,
running sync_copy_files.py, and committing the fan-out into every
component's own repo (R-BUILD-6), same discipline as build.bat/build.sh.

Runs on bare system Python, stdlib only (venv, subprocess, pathlib, sys,
os, time) - it cannot assume anything else is installed yet, that's the
whole reason this file stays this small. Its only job: find or create a
.venv, make sure the pinned version of adas_build_tools is installed into
it, then exec into it and forward argv/exit-code untouched - never any
build logic of its own.

Usage: python build.py -t <target> -p <platform> [-P <project>] [--clean]
       python build.py config
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Default `toolchain` git remote pip installs a version from, by tag
# (docs/imp_design.md §4, decided 2026-09-08 - no package index, no
# server). Overridable for anyone whose network reaches a mirror instead.
# Used only for a "vX.Y.Z" pin (see install_pinned()) - a bare "X.Y.Z" pin
# installs via Conan instead (§5 addendum, §9.8), needing no git remote at
# all.
TOOLCHAIN_GIT_URL = os.environ.get(
    "ADAS_TOOLCHAIN_GIT_URL", "https://github.com/Pavan-karimajji/toolchain")

# Conan remote a bare "X.Y.Z" pin installs adas-build-tools from (§5
# addendum, §9.8) - the same remote every other adas-* package already
# needs reachable, so a machine that can build this repo at all can also
# install this package this way.
ADAS_LOCAL_REMOTE = os.environ.get("ADAS_LOCAL_REMOTE", "adas-local")

# How long a second, concurrent invocation waits for the first to finish
# bootstrapping .venv before giving up (TCT-10).
LOCK_TIMEOUT_S = 600


def find_component_root():
    """The directory containing this scripts/build.py file's parent (the
    component root) - this file is still copy-distributed and lives at a
    fixed location relative to the component, unlike the package it
    bootstraps (docs/imp_design.md §2.4 step 1)."""
    return Path(__file__).resolve().parent.parent


def read_pin(component_root):
    """conf/build_tools.version, one line, stripped. Missing file is a hard
    error naming the expected path - never a silently-assumed default
    version (docs/imp_design.md §2.4 step 2, TCT-06)."""
    pin_path = component_root / "conf" / "build_tools.version"
    if not pin_path.is_file():
        sys.exit(
            f"ERROR: no build-tools version pin found at {pin_path}.\n"
            f"Add one - e.g. a Conan-published version (§5 addendum):\n"
            f"          echo 1.0.3> \"{pin_path}\"\n"
            f"       or a git tag (§4):\n"
            f"          echo v1.0.0> \"{pin_path}\""
        )
    return pin_path.read_text(encoding="utf-8").strip()


def venv_paths(component_root):
    """`.venv`'s location and the platform-correct interpreter path
    (docs/imp_design.md §2.4 step 3, TCT-08)."""
    venv_dir = component_root / ".venv"
    if sys.platform.startswith("win"):
        interpreter = venv_dir / "Scripts" / "python.exe"
    else:
        interpreter = venv_dir / "bin" / "python"
    return venv_dir, interpreter


def venv_is_current(venv_dir, pin):
    """True if the last SUCCESSFUL install into `venv_dir` already matches
    `pin` (docs/imp_design.md §2.4 step 4) - read from a marker file written
    only on success by install_pinned(), never assumed."""
    marker = venv_dir / "adas_build_tools.version"
    return marker.is_file() and marker.read_text(encoding="utf-8").strip() == pin


def _venv_targets_current_python(venv_dir, interpreter):
    """False for a missing/corrupted interpreter, or one built from a
    DIFFERENT system Python than the one running this stub right now - both
    cases must recreate .venv rather than trust it as-is (TCT-07)."""
    if not interpreter.is_file():
        return False
    cfg = venv_dir / "pyvenv.cfg"
    if not cfg.is_file():
        return False
    home = None
    for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().startswith("home"):
            home = line.split("=", 1)[1].strip()
            break
    if not home:
        return False
    return Path(home).resolve() == Path(sys.executable).resolve().parent


def _acquire_lock(component_root):
    """A directory-create-based lock (atomic on every platform this repo
    targets) so two simultaneous invocations against the same empty .venv
    don't race each other into a corrupted install (TCT-10) - the second
    process waits, then finds .venv already current and does nothing."""
    lock_dir = component_root / ".venv.lock"
    deadline = time.monotonic() + LOCK_TIMEOUT_S
    while True:
        try:
            lock_dir.mkdir()
            return lock_dir
        except FileExistsError:
            if time.monotonic() > deadline:
                sys.exit(
                    f"ERROR: timed out after {LOCK_TIMEOUT_S}s waiting for the .venv "
                    f"bootstrap lock at {lock_dir} (held by another build). Remove it "
                    f"by hand only if you're sure no other build is actually running."
                )
            time.sleep(0.5)


def install_pinned(venv_dir, pin):
    """Installs `pin` into `venv_dir` via one of two mechanisms, chosen by
    the pin's own shape (docs/imp_design.md §5 addendum, §9.8) - a "vX.Y.Z"
    git tag installs via `pip install git+<toolchain-url>@<pin>` (§4,
    original mechanism, needs the toolchain git remote reachable); a bare
    "X.Y.Z" installs via Conan (`conan download` -> `conan cache path` ->
    `pip install <wheel>`), reusing whatever adas-local infrastructure is
    already required for every other adas-* package - for a machine that
    can't reach the toolchain git remote (docs/imp_design.md §5's original
    motivation) but already has adas-local configured for its C++ deps.
    The marker is written only after a successful install, so a failed
    install is retried next run rather than silently treated as current
    (TCT-09)."""
    _, interpreter = venv_paths(venv_dir.parent)
    if pin.startswith("v"):
        proc = subprocess.run(
            [str(interpreter), "-m", "pip", "install", "--quiet",
             f"git+{TOOLCHAIN_GIT_URL}@{pin}"],
        )
        if proc.returncode != 0:
            sys.exit(f"ERROR: pip install of adas-build-tools@{pin} failed (exit {proc.returncode}).")
    else:
        _install_pinned_via_conan(interpreter, pin)
    (venv_dir / "adas_build_tools.version").write_text(pin, encoding="utf-8")


def _install_pinned_via_conan(interpreter, pin):
    """Conan-based half of install_pinned() (docs/imp_design.md §5
    addendum, §9.8). `adas-build-tools/<pin>`'s package_id() calls
    self.info.clear(), so it always collapses to one fixed hash regardless
    of settings - never hardcoded here, queried fresh via `conan list`
    each time, since relying on a literal would silently break the moment
    Conan's own hashing of an empty ConanInfo ever changed."""
    if shutil.which("conan") is None:
        sys.exit(
            "ERROR: conf/build_tools.version names a bare version "
            f"({pin!r}), which installs via Conan, but 'conan' isn't on "
            "PATH. Install Conan first, or pin a \"vX.Y.Z\" git tag "
            "instead (§4)."
        )

    ref = f"adas-build-tools/{pin}"
    proc = subprocess.run(["conan", "download", ref, "-r", ADAS_LOCAL_REMOTE])
    if proc.returncode != 0:
        sys.exit(
            f"ERROR: conan download of {ref} from '{ADAS_LOCAL_REMOTE}' "
            f"failed (exit {proc.returncode})."
        )

    list_proc = subprocess.run(
        ["conan", "list", f"{ref}:*", "--format=json"],
        capture_output=True, text=True,
    )
    if list_proc.returncode != 0:
        sys.exit(
            f"ERROR: conan list of {ref} failed (exit {list_proc.returncode}):\n"
            f"{list_proc.stderr}"
        )
    data = json.loads(list_proc.stdout)
    package_ids = [
        package_id
        for cache_data in data.values()
        for revision_data in cache_data.get(ref, {}).get("revisions", {}).values()
        for package_id in revision_data.get("packages", {})
    ]
    if not package_ids:
        sys.exit(f"ERROR: no built packages found for {ref} on '{ADAS_LOCAL_REMOTE}'.")

    path_proc = subprocess.run(
        ["conan", "cache", "path", f"{ref}:{package_ids[0]}"],
        capture_output=True, text=True,
    )
    if path_proc.returncode != 0:
        sys.exit(
            f"ERROR: conan cache path of {ref}:{package_ids[0]} failed "
            f"(exit {path_proc.returncode}):\n{path_proc.stderr}"
        )
    package_dir = Path(path_proc.stdout.strip())
    wheels = list(package_dir.glob("adas_build_tools-*.whl"))
    if not wheels:
        sys.exit(f"ERROR: no adas_build_tools wheel found in {package_dir}.")

    proc = subprocess.run(
        [str(interpreter), "-m", "pip", "install", "--quiet", str(wheels[0])],
    )
    if proc.returncode != 0:
        sys.exit(f"ERROR: pip install of {wheels[0]} failed (exit {proc.returncode}).")


def ensure_venv(component_root, pin):
    """Creates `.venv` if absent or if it targets a different Python
    (TCT-07), then installs `pin` into it if not already current
    (docs/imp_design.md §2.4 step 5)."""
    lock_dir = _acquire_lock(component_root)
    try:
        venv_dir, interpreter = venv_paths(component_root)
        if not _venv_targets_current_python(venv_dir, interpreter):
            if venv_dir.exists():
                shutil.rmtree(venv_dir)
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        if not venv_is_current(venv_dir, pin):
            install_pinned(venv_dir, pin)
        return venv_dir
    finally:
        lock_dir.rmdir()


def exec_into_venv(venv_dir, argv):
    """Runs adas_build_tools.cli from inside `venv_dir` with `argv`
    forwarded untouched, propagating its exit code unmodified
    (docs/imp_design.md §2.4 step 7) - os.execv on POSIX; Windows has no
    true exec-replace, so subprocess.run + sys.exit there."""
    _, interpreter = venv_paths(venv_dir.parent)
    if os.name == "posix":
        os.execv(str(interpreter), [str(interpreter), "-m", "adas_build_tools.cli", *argv])
    else:
        proc = subprocess.run([str(interpreter), "-m", "adas_build_tools.cli", *argv])
        sys.exit(proc.returncode)


def main():
    component_root = find_component_root()
    pin = read_pin(component_root)
    venv_dir = ensure_venv(component_root, pin)
    exec_into_venv(venv_dir, sys.argv[1:])


if __name__ == "__main__":
    main()
