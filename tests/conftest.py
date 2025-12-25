"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_persona_data():
    """Sample persona data for testing."""
    return {
        "name": "TestAgent",
        "role": "Test assistant",
        "capabilities": ["Testing", "Validation"],
        "tone": "professional",
        "verbosity": "concise",
    }


@pytest.fixture
def sample_human_data():
    """Sample human data for testing."""
    return {
        "name": "TestUser",
        "role": "Developer",
        "current_task": "Running tests",
        "preferences": ["Clear output", "Fast response"],
    }
