"""Smoke tests for the FastAPI app surface."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "bull-vs-bear"
    assert "config" in body
    # Non-secret config summary must not leak the API key.
    assert "google_api_key" not in body["config"]


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Bull vs Bear"
