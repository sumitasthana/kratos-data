"""
conftest.py — pytest configuration for Kratos Data test suite
==============================================================
Provides a session-scoped asyncio event loop so that the session-scoped
`engine` fixture in test_demo.py shares the same loop with all async tests.

Without this, pytest-asyncio 0.23 creates a fresh function-scoped loop per
test; the session-scoped engine's connection pool is bound to the *first*
test's loop, which is already closed by the time the second test runs —
producing "RuntimeError: Event loop is closed" cascade errors.
"""

import asyncio

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop shared by all async tests and fixtures."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
