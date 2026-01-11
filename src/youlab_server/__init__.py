"""
YouLab Server - Context-engineered Letta agents with comprehensive observability.

A production-ready foundation for building multi-agent systems with Letta,
optimized for memory block management and context engineering.
"""

from youlab_server.agents.base import BaseAgent
from youlab_server.agents.default import create_default_agent
from youlab_server.config.settings import Settings
from youlab_server.memory.blocks import HumanBlock, PersonaBlock
from youlab_server.memory.manager import MemoryManager
from youlab_server.observability.logging import configure_logging
from youlab_server.observability.tracing import Tracer

__version__ = "0.1.0"

__all__ = [
    "BaseAgent",
    "HumanBlock",
    "MemoryManager",
    "PersonaBlock",
    "Settings",
    "Tracer",
    "configure_logging",
    "create_default_agent",
]
