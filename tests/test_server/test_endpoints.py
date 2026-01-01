"""Tests for FastAPI endpoints."""


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_200(self, test_client):
        """Test health endpoint returns 200."""
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, test_client):
        """Test health response has expected fields."""
        response = test_client.get("/health")
        data = response.json()

        assert "status" in data
        assert "letta_connected" in data
        assert "version" in data

    def test_health_connected_status(self, test_client, mock_agent_manager):
        """Test health shows connected when Letta is available."""
        mock_agent_manager.check_letta_connection = lambda: True

        response = test_client.get("/health")
        data = response.json()

        assert data["status"] == "ok"
        assert data["letta_connected"] is True

    def test_health_degraded_status(self, test_client, mock_agent_manager):
        """Test health shows degraded when Letta unavailable."""
        mock_agent_manager.check_letta_connection = lambda: False

        response = test_client.get("/health")
        data = response.json()

        assert data["status"] == "degraded"
        assert data["letta_connected"] is False


class TestCreateAgentEndpoint:
    """Tests for POST /agents endpoint."""

    def test_create_agent_success(self, test_client, mock_agent_manager):
        """Test successful agent creation."""
        mock_agent_manager.create_agent = lambda **_kw: "new-agent-id"
        mock_agent_manager.get_agent_info = lambda _aid: {
            "agent_id": "new-agent-id",
            "user_id": "user123",
            "agent_type": "tutor",
            "agent_name": "youlab_user123_tutor",
            "created_at": None,
        }

        response = test_client.post("/agents", json={"user_id": "user123"})

        assert response.status_code == 201
        data = response.json()
        assert data["agent_id"] == "new-agent-id"
        assert data["user_id"] == "user123"

    def test_create_agent_with_name(self, test_client, mock_agent_manager):
        """Test agent creation with user name."""
        mock_agent_manager.create_agent = lambda **_kw: "new-agent-id"
        mock_agent_manager.get_agent_info = lambda _aid: {
            "agent_id": "new-agent-id",
            "user_id": "user123",
            "agent_type": "tutor",
            "agent_name": "youlab_user123_tutor",
            "created_at": None,
        }

        response = test_client.post(
            "/agents",
            json={
                "user_id": "user123",
                "user_name": "Alice",
            },
        )

        assert response.status_code == 201

    def test_create_agent_missing_user_id(self, test_client):
        """Test agent creation fails without user_id."""
        response = test_client.post("/agents", json={})
        assert response.status_code == 422  # Validation error

    def test_create_agent_invalid_type(self, test_client, mock_agent_manager):
        """Test agent creation fails with invalid type."""

        def raise_value_error(**kw):
            raise ValueError("Unknown agent type: bad_type")

        mock_agent_manager.create_agent = raise_value_error

        response = test_client.post(
            "/agents",
            json={
                "user_id": "user123",
                "agent_type": "bad_type",
            },
        )

        assert response.status_code == 400


class TestGetAgentEndpoint:
    """Tests for GET /agents/{agent_id} endpoint."""

    def test_get_agent_success(self, test_client, mock_agent_manager):
        """Test successful agent retrieval."""
        mock_agent_manager.get_agent_info = lambda _aid: {
            "agent_id": "agent-123",
            "user_id": "user123",
            "agent_type": "tutor",
            "agent_name": "youlab_user123_tutor",
            "created_at": 1703880000,
        }

        response = test_client.get("/agents/agent-123")

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent-123"

    def test_get_agent_not_found(self, test_client, mock_agent_manager):
        """Test 404 for nonexistent agent."""
        mock_agent_manager.get_agent_info = lambda _aid: None

        response = test_client.get("/agents/nonexistent")

        assert response.status_code == 404


class TestListAgentsEndpoint:
    """Tests for GET /agents endpoint."""

    def test_list_all_agents(self, test_client, mock_agent_manager):
        """Test listing all agents."""
        # Create mock with new resource-based API: client.agents.list()
        mock_agents_resource = type(
            "AgentsResource",
            (),
            {
                "list": lambda _self: [
                    type(
                        "Agent",
                        (),
                        {
                            "name": "youlab_user1_tutor",
                            "id": "agent-1",
                            "metadata": {
                                "youlab_user_id": "user1",
                                "youlab_agent_type": "tutor",
                            },
                        },
                    )(),
                ]
            },
        )()
        mock_agent_manager.client = type(
            "Client",
            (),
            {"agents": mock_agents_resource},
        )()

        response = test_client.get("/agents")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data

    def test_list_agents_by_user(self, test_client, mock_agent_manager):
        """Test listing agents filtered by user_id."""
        mock_agent_manager.list_user_agents = lambda _uid: [
            {
                "agent_id": "agent-1",
                "user_id": _uid,
                "agent_type": "tutor",
                "agent_name": f"youlab_{_uid}_tutor",
                "created_at": None,
            }
        ]

        response = test_client.get("/agents?user_id=user123")

        assert response.status_code == 200
        data = response.json()
        assert len(data["agents"]) == 1
        assert data["agents"][0]["user_id"] == "user123"


class TestChatEndpoint:
    """Tests for POST /chat endpoint."""

    def test_chat_success(self, test_client, mock_agent_manager):
        """Test successful chat message."""
        mock_agent_manager.get_agent_info = lambda _aid: {
            "agent_id": "agent-123",
            "user_id": "user123",
            "agent_type": "tutor",
            "agent_name": "youlab_user123_tutor",
            "created_at": None,
        }
        mock_agent_manager.send_message = lambda _aid, _msg: "Hello! I'm your coach."

        response = test_client.post(
            "/chat",
            json={
                "agent_id": "agent-123",
                "message": "Hello!",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Hello! I'm your coach."
        assert data["agent_id"] == "agent-123"

    def test_chat_with_context(self, test_client, mock_agent_manager):
        """Test chat with chat_id and chat_title."""
        mock_agent_manager.get_agent_info = lambda _aid: {
            "agent_id": "agent-123",
            "user_id": "user123",
            "agent_type": "tutor",
            "agent_name": "youlab_user123_tutor",
            "created_at": None,
        }
        mock_agent_manager.send_message = lambda _aid, _msg: "Response"

        response = test_client.post(
            "/chat",
            json={
                "agent_id": "agent-123",
                "message": "Hello!",
                "chat_id": "chat-456",
                "chat_title": "Essay Brainstorming",
            },
        )

        assert response.status_code == 200

    def test_chat_agent_not_found(self, test_client, mock_agent_manager):
        """Test 404 when agent doesn't exist."""
        mock_agent_manager.get_agent_info = lambda _aid: None

        response = test_client.post(
            "/chat",
            json={
                "agent_id": "nonexistent",
                "message": "Hello!",
            },
        )

        assert response.status_code == 404

    def test_chat_empty_response(self, test_client, mock_agent_manager):
        """Test fallback message for empty response."""
        mock_agent_manager.get_agent_info = lambda _aid: {
            "agent_id": "agent-123",
            "user_id": "user123",
            "agent_type": "tutor",
            "agent_name": "youlab_user123_tutor",
            "created_at": None,
        }
        mock_agent_manager.send_message = lambda _aid, _msg: ""

        response = test_client.post(
            "/chat",
            json={
                "agent_id": "agent-123",
                "message": "Hello!",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "No response from agent."


class TestChatStreamEndpoint:
    """Tests for POST /chat/stream endpoint."""

    def test_stream_returns_sse(self, test_client, mock_agent_manager):
        """Streaming endpoint returns SSE content type."""

        def mock_stream(*args, **kwargs):
            yield 'data: {"type": "message", "content": "Hello"}\n\n'
            yield 'data: {"type": "done"}\n\n'

        mock_agent_manager.stream_message = mock_stream
        mock_agent_manager.get_agent_info = lambda agent_id: {"agent_id": agent_id}

        response = test_client.post(
            "/chat/stream",
            json={"agent_id": "agent-123", "message": "Hello"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert response.headers["cache-control"] == "no-cache"

    def test_stream_content(self, test_client, mock_agent_manager):
        """Streaming endpoint yields SSE events."""
        events = [
            'data: {"type": "status", "content": "Thinking..."}\n\n',
            'data: {"type": "message", "content": "Hello!"}\n\n',
            'data: {"type": "done"}\n\n',
        ]

        def mock_stream(*args, **kwargs):
            yield from events

        mock_agent_manager.stream_message = mock_stream
        mock_agent_manager.get_agent_info = lambda agent_id: {"agent_id": agent_id}

        response = test_client.post(
            "/chat/stream",
            json={"agent_id": "agent-123", "message": "Hello"},
        )

        content = response.text
        assert 'data: {"type": "status"' in content
        assert 'data: {"type": "message"' in content
        assert 'data: {"type": "done"' in content

    def test_stream_agent_not_found(self, test_client, mock_agent_manager):
        """Streaming endpoint returns 404 for unknown agent."""
        mock_agent_manager.get_agent_info = lambda _aid: None

        response = test_client.post(
            "/chat/stream",
            json={"agent_id": "unknown-agent", "message": "Hello"},
        )

        assert response.status_code == 404
        assert "Agent not found" in response.json()["detail"]

    def test_stream_missing_agent_id(self, test_client):
        """Streaming endpoint requires agent_id."""
        response = test_client.post(
            "/chat/stream",
            json={"message": "Hello"},
        )

        assert response.status_code == 422

    def test_stream_missing_message(self, test_client):
        """Streaming endpoint requires message."""
        response = test_client.post(
            "/chat/stream",
            json={"agent_id": "agent-123"},
        )

        assert response.status_code == 422

    def test_stream_with_optional_fields(self, test_client, mock_agent_manager):
        """Streaming endpoint accepts optional fields."""

        def mock_stream(*args, **kwargs):
            yield 'data: {"type": "done"}\n\n'

        mock_agent_manager.stream_message = mock_stream
        mock_agent_manager.get_agent_info = lambda agent_id: {"agent_id": agent_id}

        response = test_client.post(
            "/chat/stream",
            json={
                "agent_id": "agent-123",
                "message": "Hello",
                "chat_id": "chat-456",
                "chat_title": "My Chat",
                "enable_thinking": False,
            },
        )

        assert response.status_code == 200
