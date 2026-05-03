from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def installed_package(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, dict[str, str]]:
    tmp_path = tmp_path_factory.mktemp("installed-package")
    target_dir = tmp_path / "site"
    isolated_cwd = tmp_path / "isolated"
    isolated_cwd.mkdir()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(target_dir),
            "--no-deps",
            "--no-build-isolation",
            str(PROJECT_ROOT),
        ],
        check=True,
        cwd=isolated_cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(target_dir)
    return target_dir, isolated_cwd, env
