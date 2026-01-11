"""Pytest configuration and fixtures."""

import pytest

from youlab_server.memory.blocks import HumanBlock, PersonaBlock


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


@pytest.fixture
def sample_agent_template_data():
    """Sample agent template data for testing."""
    return {
        "type_id": "custom",
        "display_name": "Custom Agent",
        "description": "A custom test agent",
        "persona": PersonaBlock(
            name="Custom",
            role="Custom test role",
            capabilities=["Testing", "Validation"],
            tone="professional",
        ),
        "human": HumanBlock(),
    }
