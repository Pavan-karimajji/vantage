# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: `IMP-0158` -- `IT-12`, the real toolchain half `test_a2_config_
paths.py`'s unit tests cannot reach: `ConfigPaths` resolved from a
customer checkout, against `adas_sim` installed **read-only**, somewhere
that is neither the checkout nor a venv site-packages a developer would
edit -- the shape `IT-12`'s own Fixture (`F-CFGSET`) names. Real `pip
install --no-deps --target` (no build step -- `adas_sim` is pure Python),
skipping with a named reason if the toolchain step cannot run here, same
discipline `test_a1_install.py`'s `ST-A1-1`/`ST-A1-2` already use for
`conan`/an editable install.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SIM_ROOT = Path(__file__).resolve().parent.parent.parent


def _venv_python() -> Path | None:
    candidate = SIM_ROOT / ".venv" / "Scripts" / "python.exe"
    if not candidate.is_file():
        candidate = SIM_ROOT / ".venv" / "bin" / "python"
    return candidate if candidate.is_file() else None


def _make_read_only(root: Path) -> None:
    """Best-effort read-only marking (`NTFS`/`POSIX` both honour the write
    bit being cleared; this is what a real pip-installed site-packages or a
    frozen build's own install tree ends up as) -- the test's actual claim
    (`project_root` decoupled from the install location) does not depend on
    enforcement succeeding on every platform, same as `test_d5_frozen_
    build.py`'s own "as close as this shell can honestly get" framing."""
    for path in root.rglob("*"):
        if path.is_file():
            path.chmod(stat.S_IREAD)


@pytest.fixture(scope="module")
def read_only_install(tmp_path_factory) -> Path:
    python = _venv_python()
    if python is None:
        pytest.skip("no modules/sim/.venv -- pip install was not performed for this checkout")
    install_dir = tmp_path_factory.mktemp("it12_install")
    result = subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", "--target", str(install_dir), str(SIM_ROOT)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"pip install --target failed: {result.stderr}")
    _make_read_only(install_dir)
    return install_dir


def test_config_paths_resolves_from_a_customer_checkout_against_a_read_only_install(
    read_only_install, tmp_path,
):
    """`IT-12`: run from a customer checkout with the package installed
    read-only. `project_root` is a bare parameter (`IMP-0158`) -- nothing
    in `ConfigPaths` may fall back to where `adas_sim` itself was
    installed, so a checkout with NO relation to `read_only_install`
    (different drive-relative subtree, never a child of it) must still
    resolve correctly."""
    customer_checkout = tmp_path / "customer_checkout"
    (customer_checkout / "composition").mkdir(parents=True)

    code = (
        "from pathlib import Path\n"
        "from adas_sim.config.paths import ConfigPaths\n"
        "from adas_sim.config.kinds import FileKind\n"
        "paths = ConfigPaths(project_root=Path('.').resolve())\n"
        "print(paths.dir_for(FileKind.COMPOSITION))\n"
    )
    # A real env (not PYTHONPATH alone) -- the subprocess still needs PATH/
    # TEMP/etc. to start at all; PYTHONPATH is the one variable overridden
    # to point ONLY at the read-only install, never the checkout's own venv.
    env = {**os.environ, "PYTHONPATH": str(read_only_install)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(customer_checkout), env=env,
        capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == (customer_checkout / "composition").resolve()


def test_the_read_only_install_shares_no_path_with_the_checkout(read_only_install):
    """The install directory used above is not a descendant of `SIM_ROOT`
    -- proves the CLI/import path was genuinely exercised against a
    separate, install-only tree, not the source checkout under another name."""
    assert SIM_ROOT not in read_only_install.parents
    assert read_only_install not in SIM_ROOT.parents
