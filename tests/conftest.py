"""Pytest configuration and fixtures."""

import pytest
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure async backend for pytest-asyncio."""
    return "asyncio"
