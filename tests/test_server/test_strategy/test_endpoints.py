"""Tests for strategy endpoints."""


class TestStrategyDocumentsEndpoint:
    """Tests for POST /strategy/documents endpoint."""

    def test_upload_document_success(self, strategy_test_client, mock_strategy_manager):
        """Test successful document upload."""
        mock_strategy_manager.upload_document = lambda **_kw: None

        response = strategy_test_client.post(
            "/strategy/documents",
            json={
                "content": "YouLab architecture overview",
                "tags": ["architecture"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True

    def test_upload_document_no_tags(self, strategy_test_client, mock_strategy_manager):
        """Test document upload without tags."""
        mock_strategy_manager.upload_document = lambda **_kw: None

        response = strategy_test_client.post(
            "/strategy/documents",
            json={
                "content": "Some content",
            },
        )

        assert response.status_code == 201

    def test_upload_document_missing_content(self, strategy_test_client):
        """Test document upload fails without content."""
        response = strategy_test_client.post(
            "/strategy/documents",
            json={},
        )

        assert response.status_code == 422  # Validation error

    def test_upload_document_letta_unavailable(self, strategy_test_client, mock_strategy_manager):
        """Test 503 when Letta is unavailable."""

        def raise_error(**_kw):
            raise RuntimeError("Letta unavailable")

        mock_strategy_manager.upload_document = raise_error

        response = strategy_test_client.post(
            "/strategy/documents",
            json={
                "content": "Test content",
            },
        )

        assert response.status_code == 503


class TestStrategyAskEndpoint:
    """Tests for POST /strategy/ask endpoint."""

    def test_ask_success(self, strategy_test_client, mock_strategy_manager):
        """Test successful question asking."""
        mock_strategy_manager.ask = lambda _question: "YouLab is a course platform."

        response = strategy_test_client.post(
            "/strategy/ask",
            json={
                "question": "What is YouLab?",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "YouLab is a course platform."

    def test_ask_empty_response(self, strategy_test_client, mock_strategy_manager):
        """Test fallback for empty response."""
        mock_strategy_manager.ask = lambda _question: ""

        response = strategy_test_client.post(
            "/strategy/ask",
            json={
                "question": "Unknown question?",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "No response from strategy agent."

    def test_ask_missing_question(self, strategy_test_client):
        """Test ask fails without question."""
        response = strategy_test_client.post(
            "/strategy/ask",
            json={},
        )

        assert response.status_code == 422  # Validation error

    def test_ask_letta_unavailable(self, strategy_test_client, mock_strategy_manager):
        """Test 503 when Letta is unavailable."""

        def raise_error(_question):
            raise RuntimeError("Letta unavailable")

        mock_strategy_manager.ask = raise_error

        response = strategy_test_client.post(
            "/strategy/ask",
            json={
                "question": "What is YouLab?",
            },
        )

        assert response.status_code == 503


class TestStrategySearchEndpoint:
    """Tests for GET /strategy/documents endpoint."""

    def test_search_documents_success(self, strategy_test_client, mock_strategy_manager):
        """Test successful document search."""
        mock_strategy_manager.search_documents = lambda **_kw: [
            "Architecture overview",
            "More architecture info",
        ]

        response = strategy_test_client.get("/strategy/documents?query=architecture")

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 2

    def test_search_documents_with_limit(self, strategy_test_client, mock_strategy_manager):
        """Test search with custom limit."""
        mock_strategy_manager.search_documents = lambda **_kw: ["Result 1"]

        response = strategy_test_client.get("/strategy/documents?query=test&limit=1")

        assert response.status_code == 200

    def test_search_documents_empty_results(self, strategy_test_client, mock_strategy_manager):
        """Test search with no results."""
        mock_strategy_manager.search_documents = lambda **_kw: []

        response = strategy_test_client.get("/strategy/documents?query=nonexistent")

        assert response.status_code == 200
        data = response.json()
        assert data["documents"] == []

    def test_search_documents_missing_query(self, strategy_test_client):
        """Test search fails without query."""
        response = strategy_test_client.get("/strategy/documents")

        assert response.status_code == 422  # Validation error


class TestStrategyHealthEndpoint:
    """Tests for GET /strategy/health endpoint."""

    def test_strategy_health_ready(self, strategy_test_client, mock_strategy_manager):
        """Test health returns ready when agent exists."""
        mock_strategy_manager.check_agent_exists = lambda: True

        response = strategy_test_client.get("/strategy/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["agent_exists"] is True

    def test_strategy_health_not_ready(self, strategy_test_client, mock_strategy_manager):
        """Test health returns not_ready when no agent."""
        mock_strategy_manager.check_agent_exists = lambda: False

        response = strategy_test_client.get("/strategy/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["agent_exists"] is False
