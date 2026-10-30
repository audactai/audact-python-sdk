"""
Shared pytest configuration and fixtures for the Audact Python SDK test suite.

This module is automatically loaded by pytest before any test collection.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# asyncio mode is set to "auto" in pyproject.toml so every async test
# function is collected automatically.  No explicit @pytest.mark.asyncio
# decoration is required on individual test methods — but those decorators
# are kept in the test modules for documentation clarity.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Pin anyio to the asyncio backend (for compatibility with anyio-based tests)."""
    return "asyncio"
