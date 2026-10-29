from __future__ import annotations

import subprocess
import sys

import pytest

from src.common.paths import ROOT


@pytest.mark.parametrize(
    "module",
    ["src.capture", "src.measure", "src.analysis"],
)
def test_module_cli_help(module: str):
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert b"usage:" in result.stdout.lower()
