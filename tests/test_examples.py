"""
Verifies that ``examples/end_to_end_flow.py`` (the runnable common
flow: create agent -> provision + assign a number -> browser test call ->
list/read calls) actually executes cleanly.

Runs the script's own ``--check`` dry-run mode as a subprocess -- it mocks
every HTTP call in-process (an ``httpx.MockTransport``) so this test makes
no real network calls, but it does exercise the real, importable example
file, catching import errors, wrong method/attribute names, and model
validation mismatches that a purely-mocked unit test would not.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
END_TO_END_SCRIPT = EXAMPLES_DIR / "end_to_end_flow.py"


def test_end_to_end_flow_script_exists() -> None:
    assert END_TO_END_SCRIPT.is_file()


def test_end_to_end_flow_check_mode_without_number_provisioning() -> None:
    """``--check`` succeeds and skips number provisioning when the KYC-set
    env var is unset."""
    result = subprocess.run(
        [sys.executable, str(END_TO_END_SCRIPT), "--check"],
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr
    assert "created agent" in result.stdout
    assert "started browser call" in result.stdout
    assert "--check: OK" in result.stdout
    assert "skipping number provisioning" in result.stdout


def test_end_to_end_flow_check_mode_with_number_provisioning() -> None:
    """``--check`` also exercises the number order -> wait -> assign branch
    when ``AUDACT_EXAMPLE_KYC_SET_ID`` is set."""
    result = subprocess.run(
        [sys.executable, str(END_TO_END_SCRIPT), "--check"],
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "PATH": "/usr/bin:/bin",
            "AUDACT_EXAMPLE_KYC_SET_ID": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert result.returncode == 0, result.stderr
    assert "placed number order" in result.stdout
    assert "reached terminal status: success" in result.stdout
    assert "assigned number" in result.stdout
    assert "--check: OK" in result.stdout
