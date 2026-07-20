"""Shared deterministic test configuration."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Keep async HTTP tests on the installed asyncio backend."""
    return "asyncio"
