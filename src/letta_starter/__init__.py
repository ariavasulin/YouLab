"""
LettaStarter - Context-engineered Letta agents with comprehensive observability.

A production-ready foundation for building multi-agent systems with Letta,
optimized for memory block management and context engineering.
"""

from letta_starter.agents.base import BaseAgent
from letta_starter.agents.default import create_default_agent
from letta_starter.config.settings import Settings
from letta_starter.memory.blocks import HumanBlock, PersonaBlock
from letta_starter.memory.manager import MemoryManager
from letta_starter.observability.logging import configure_logging
from letta_starter.observability.tracing import Tracer

__version__ = "0.1.0"

__all__ = [
    "BaseAgent",
    "create_default_agent",
    "Settings",
    "PersonaBlock",
    "HumanBlock",
    "MemoryManager",
    "configure_logging",
    "Tracer",
]
