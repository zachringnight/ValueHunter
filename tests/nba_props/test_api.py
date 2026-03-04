"""Tests for the REST API."""

import pytest

from nba_props.api.app import create_app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.1.0"
        assert "timestamp" in data


class TestModelsEndpoint:
    def test_list_models(self, client):
        response = client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        model_names = [m["model_name"] for m in data["models"]]
        assert "minutes_model" in model_names
        assert "three_pa_model" in model_names
        assert "make_rate_model" in model_names


class TestDecisionsEndpoint:
    def test_decisions_returns_structure(self, client):
        response = client.post("/v1/decisions?date=2026-01-15")
        assert response.status_code == 200
        data = response.json()
        assert data["date"] == "2026-01-15"
        assert "decisions" in data
        assert "total" in data
        assert "bets" in data
        assert "passes" in data


class TestBetsEndpoint:
    def test_bets_returns_structure(self, client):
        response = client.get("/v1/bets/2026-01-15")
        assert response.status_code == 200
        data = response.json()
        assert data["date"] == "2026-01-15"
        assert "bets" in data
        assert isinstance(data["bets"], list)


class TestBacktestEndpoint:
    def test_backtest_queued(self, client):
        response = client.post(
            "/v1/backtest/run",
            json={
                "start_date": "2025-11-01",
                "end_date": "2025-12-31",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["start_date"] == "2025-11-01"
        assert data["end_date"] == "2025-12-31"


class TestFeatureSnapshotEndpoint:
    def test_missing_snapshot_404(self, client):
        response = client.get("/v1/feature_snapshot/99999")
        assert response.status_code == 404
