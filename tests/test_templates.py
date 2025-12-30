"""Tests for agent template system."""

import pytest
from pydantic import ValidationError

from letta_starter.agents.templates import (
    TUTOR_TEMPLATE,
    AgentTemplate,
    AgentTemplateRegistry,
    templates,
)
from letta_starter.memory.blocks import HumanBlock, PersonaBlock


class TestAgentTemplate:
    """Tests for AgentTemplate model."""

    def test_create_minimal_template(self):
        """Test creating template with minimal required fields."""
        template = AgentTemplate(
            type_id="test",
            display_name="Test Agent",
            persona=PersonaBlock(role="Test role"),
        )
        assert template.type_id == "test"
        assert template.display_name == "Test Agent"
        assert template.description == ""  # Default
        assert isinstance(template.human, HumanBlock)  # Default factory

    def test_create_full_template(self, sample_agent_template_data):
        """Test creating template with all fields."""
        template = AgentTemplate(**sample_agent_template_data)
        assert template.type_id == "custom"
        assert len(template.persona.capabilities) > 0

    def test_template_type_id_required(self):
        """Test that type_id is required."""
        with pytest.raises(ValidationError):
            AgentTemplate(display_name="Test", persona=PersonaBlock(role="Role"))

    def test_template_display_name_required(self):
        """Test that display_name is required."""
        with pytest.raises(ValidationError):
            AgentTemplate(type_id="test", persona=PersonaBlock(role="Role"))

    def test_template_persona_required(self):
        """Test that persona is required."""
        with pytest.raises(ValidationError):
            AgentTemplate(type_id="test", display_name="Test")


class TestAgentTemplateRegistry:
    """Tests for AgentTemplateRegistry."""

    def test_registry_starts_with_builtin(self):
        """Test that registry includes built-in templates."""
        registry = AgentTemplateRegistry()
        assert "tutor" in registry.list_types()

    def test_register_new_template(self, sample_agent_template_data):
        """Test registering a new template."""
        registry = AgentTemplateRegistry()
        template = AgentTemplate(**sample_agent_template_data)
        registry.register(template)

        assert template.type_id in registry.list_types()
        assert registry.get(template.type_id) == template

    def test_get_existing_template(self):
        """Test getting an existing template."""
        registry = AgentTemplateRegistry()
        template = registry.get("tutor")

        assert template is not None
        assert template.type_id == "tutor"

    def test_get_nonexistent_template(self):
        """Test getting a template that doesn't exist."""
        registry = AgentTemplateRegistry()
        template = registry.get("nonexistent")

        assert template is None

    def test_list_types(self):
        """Test listing all template types."""
        registry = AgentTemplateRegistry()
        types = registry.list_types()

        assert isinstance(types, list)
        assert "tutor" in types

    def test_get_all_templates(self):
        """Test getting all templates as dict."""
        registry = AgentTemplateRegistry()
        all_templates = registry.get_all()

        assert isinstance(all_templates, dict)
        assert "tutor" in all_templates

    def test_register_overwrites_existing(self, sample_agent_template_data):
        """Test that registering with same type_id overwrites."""
        registry = AgentTemplateRegistry()

        # Modify sample data to use "tutor" type_id
        sample_agent_template_data["type_id"] = "tutor"
        sample_agent_template_data["display_name"] = "Custom Tutor"
        new_template = AgentTemplate(**sample_agent_template_data)

        registry.register(new_template)

        retrieved = registry.get("tutor")
        assert retrieved.display_name == "Custom Tutor"


class TestTutorTemplate:
    """Tests for the built-in TUTOR_TEMPLATE."""

    def test_tutor_template_exists(self):
        """Test that TUTOR_TEMPLATE is defined."""
        assert TUTOR_TEMPLATE is not None
        assert isinstance(TUTOR_TEMPLATE, AgentTemplate)

    def test_tutor_template_type_id(self):
        """Test TUTOR_TEMPLATE has correct type_id."""
        assert TUTOR_TEMPLATE.type_id == "tutor"

    def test_tutor_template_has_persona(self):
        """Test TUTOR_TEMPLATE has valid persona."""
        assert isinstance(TUTOR_TEMPLATE.persona, PersonaBlock)
        assert TUTOR_TEMPLATE.persona.name == "YouLab Essay Coach"
        assert (
            "tutor" in TUTOR_TEMPLATE.persona.role.lower()
            or "essay" in TUTOR_TEMPLATE.persona.role.lower()
        )

    def test_tutor_template_has_capabilities(self):
        """Test TUTOR_TEMPLATE has capabilities."""
        assert len(TUTOR_TEMPLATE.persona.capabilities) > 0

    def test_tutor_template_has_constraints(self):
        """Test TUTOR_TEMPLATE has constraints."""
        assert len(TUTOR_TEMPLATE.persona.constraints) > 0
        # Should include the critical constraint
        constraints_text = " ".join(TUTOR_TEMPLATE.persona.constraints).lower()
        assert "never write" in constraints_text or "not write" in constraints_text

    def test_tutor_template_persona_serializable(self):
        """Test TUTOR_TEMPLATE persona can be serialized."""
        memory_str = TUTOR_TEMPLATE.persona.to_memory_string()
        assert "[IDENTITY]" in memory_str
        assert "YouLab Essay Coach" in memory_str


class TestGlobalTemplatesRegistry:
    """Tests for the global templates registry instance."""

    def test_global_registry_exists(self):
        """Test that global templates instance exists."""
        assert templates is not None
        assert isinstance(templates, AgentTemplateRegistry)

    def test_global_registry_has_tutor(self):
        """Test global registry includes tutor template."""
        assert templates.get("tutor") is not None
