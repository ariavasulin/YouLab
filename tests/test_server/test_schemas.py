"""Tests for request/response schemas."""

import pytest
from pydantic import ValidationError

from letta_starter.server.schemas import (
    AgentResponse,
    ChatRequest,
    CreateAgentRequest,
    HealthResponse,
)


class TestCreateAgentRequest:
    """Tests for CreateAgentRequest schema."""

    def test_minimal_request(self):
        """Test request with only required fields."""
        request = CreateAgentRequest(user_id="user123")
        assert request.user_id == "user123"
        assert request.agent_type == "tutor"  # Default
        assert request.user_name is None

    def test_full_request(self):
        """Test request with all fields."""
        request = CreateAgentRequest(
            user_id="user123",
            agent_type="custom",
            user_name="Alice",
        )
        assert request.user_id == "user123"
        assert request.agent_type == "custom"
        assert request.user_name == "Alice"

    def test_user_id_required(self):
        """Test that user_id is required."""
        with pytest.raises(ValidationError):
            CreateAgentRequest()


class TestAgentResponse:
    """Tests for AgentResponse schema."""

    def test_full_response(self):
        """Test response with all fields."""
        response = AgentResponse(
            agent_id="agent-123",
            user_id="user123",
            agent_type="tutor",
            agent_name="youlab_user123_tutor",
            created_at=1703880000,
        )
        assert response.agent_id == "agent-123"
        assert response.created_at == 1703880000

    def test_minimal_response(self):
        """Test response without optional fields."""
        response = AgentResponse(
            agent_id="agent-123",
            user_id="user123",
            agent_type="tutor",
            agent_name="youlab_user123_tutor",
        )
        assert response.created_at is None


class TestChatRequest:
    """Tests for ChatRequest schema."""

    def test_minimal_request(self):
        """Test request with only required fields."""
        request = ChatRequest(
            agent_id="agent-123",
            message="Hello!",
        )
        assert request.agent_id == "agent-123"
        assert request.message == "Hello!"
        assert request.chat_id is None
        assert request.chat_title is None

    def test_full_request(self):
        """Test request with all fields."""
        request = ChatRequest(
            agent_id="agent-123",
            message="Hello!",
            chat_id="chat-456",
            chat_title="Essay Brainstorming",
        )
        assert request.chat_id == "chat-456"
        assert request.chat_title == "Essay Brainstorming"


class TestHealthResponse:
    """Tests for HealthResponse schema."""

    def test_healthy_response(self):
        """Test healthy status response."""
        response = HealthResponse(
            status="ok",
            letta_connected=True,
        )
        assert response.status == "ok"
        assert response.letta_connected is True
        assert response.version == "0.1.0"  # Default

    def test_degraded_response(self):
        """Test degraded status response."""
        response = HealthResponse(
            status="degraded",
            letta_connected=False,
        )
        assert response.status == "degraded"
        assert response.letta_connected is False
