"""Agent templates for YouLab."""

from pydantic import BaseModel, Field

from letta_starter.memory.blocks import HumanBlock, PersonaBlock


class AgentTemplate(BaseModel):
    """Template for creating agents of a specific type."""

    type_id: str = Field(..., description="Unique identifier for this template")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(default="", description="Template description")
    persona: PersonaBlock = Field(..., description="Persona block for the agent")
    human: HumanBlock = Field(default_factory=HumanBlock, description="Initial human block")


# Default tutor template for college essay coaching
TUTOR_TEMPLATE = AgentTemplate(
    type_id="tutor",
    display_name="College Essay Coach",
    description="Primary tutor for college essay writing course",
    persona=PersonaBlock(
        name="YouLab Essay Coach",
        role="AI tutor specializing in college application essays",
        capabilities=[
            "Guide students through self-discovery exercises",
            "Help brainstorm and develop essay topics",
            "Provide constructive feedback on drafts",
            "Support emotional journey of college applications",
        ],
        expertise=[
            "College admissions",
            "Personal narrative",
            "Reflective writing",
            "Strengths-based coaching",
        ],
        tone="warm",
        verbosity="adaptive",
        constraints=[
            "Never write essays for students",
            "Always ask clarifying questions before giving advice",
            "Celebrate small wins and progress",
        ],
    ),
    human=HumanBlock(),  # Empty, filled during onboarding
)


class AgentTemplateRegistry:
    """Registry for agent templates."""

    def __init__(self) -> None:
        self._templates: dict[str, AgentTemplate] = {}
        # Register built-in templates
        self.register(TUTOR_TEMPLATE)

    def register(self, template: AgentTemplate) -> None:
        """Register an agent template."""
        self._templates[template.type_id] = template

    def get(self, type_id: str) -> AgentTemplate | None:
        """Get template by type ID."""
        return self._templates.get(type_id)

    def list_types(self) -> list[str]:
        """List all registered template type IDs."""
        return list(self._templates.keys())

    def get_all(self) -> dict[str, AgentTemplate]:
        """Get all registered templates."""
        return self._templates.copy()


# Global registry instance
templates = AgentTemplateRegistry()
