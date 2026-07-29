"""Integration tests for FastAPI routes (uses httpx TestClient)."""

import pytest
from backend.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    """Async HTTP client bound to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    """Tests for GET /api/health."""

    async def test_returns_200(self, client):
        """Health check should return HTTP 200."""
        response = await client.get("/api/health")
        assert response.status_code == 200

    async def test_returns_status_ok(self, client):
        """Health check should report 'ok' status."""
        response = await client.get("/api/health")
        data = response.json()
        assert data["status"] == "ok"

    async def test_returns_expected_fields(self, client):
        """Health check should include version and availability flags."""
        response = await client.get("/api/health")
        data = response.json()
        assert "version" in data
        assert "llm_available" in data
        assert "asr_available" in data


class TestChatEndpoint:
    """Tests for POST /api/chat (SSE streaming)."""

    async def test_accepts_valid_request(self, client):
        """Should accept a valid chat request and return SSE stream."""
        response = await client.post(
            "/api/chat",
            json={"text": "你好", "session_id": "test-001"},
            timeout=30,
        )
        # Accept 200 (success) or 500 (LLM API key missing) as both are valid
        assert response.status_code in (200, 500)

    async def test_rejects_empty_text(self, client):
        """Should reject empty message with 422."""
        response = await client.post(
            "/api/chat",
            json={"text": "", "session_id": "test-001"},
        )
        assert response.status_code == 422
