"""API and session integration tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    root = Path(__file__).resolve().parents[1]
    with TestClient(create_app(root / "config" / "scenarios")) as test_client:
        yield test_client


def test_scenario_listing_and_tree_visualization(client):
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    assert len(response.json()["scenarios"]) == 2
    tree = client.get("/api/scenarios/fire-smoke/tree")
    assert tree.status_code == 200
    assert tree.json()["root_id"] == "fire-visible"
    assert len(tree.json()["nodes"]) == 3
    assert client.get("/api/scenarios/unknown/tree").status_code == 404


def test_frontend_is_served_by_local_api(client):
    page = client.get("/")
    assert page.status_code == 200
    assert '<html lang="es">' in page.text
    script = client.get("/js/api.js")
    assert script.status_code == 200
    assert "const API_BASE = '/api'" in script.text


def test_start_answer_protocol_and_unapproved_disclaimer(client):
    started = client.post("/api/sessions", json={"scenario_id": "fire-smoke"})
    assert started.status_code == 201
    state = started.json()
    assert state["question"] == "¿Observa fuego o humo?"
    answer = client.post(f"/api/sessions/{state['session_id']}/answers", json={"answer": True})
    assert answer.status_code == 200
    payload = answer.json()["protocol"]
    assert payload["approval_status"] == "unapproved"
    assert "no contiene instrucciones operativas aprobadas" in payload["instructions"][0]
    assert payload["approving_authority"] is None
    assert client.post(f"/api/sessions/{state['session_id']}/answers", json={"answer": False}).status_code == 409


def test_session_isolation_reset_and_invalid_ids(client):
    first = client.post("/api/sessions", json={"scenario_id": "fire-smoke"}).json()
    second = client.post("/api/sessions", json={"scenario_id": "fire-smoke"}).json()
    assert first["session_id"] != second["session_id"]
    assert client.post(f"/api/sessions/{first['session_id']}/answers", json={"answer": False}).status_code == 200
    assert client.get(f"/api/sessions/{second['session_id']}").json()["current_node_id"] == "fire-visible"
    reset = client.post(f"/api/sessions/{first['session_id']}/reset")
    assert reset.status_code == 200
    assert reset.json()["current_node_id"] == "fire-visible"
    assert reset.json()["path"] == []
    assert client.get("/api/sessions/nope").status_code == 404


def test_request_validation_and_unknown_scenario(client):
    assert client.post("/api/sessions", json={"scenario_id": "bad", "protocol": "fake"}).status_code == 422
    assert client.post("/api/sessions", json={"scenario_id": "not-configured"}).status_code == 404
    started = client.post("/api/sessions", json={"scenario_id": "fire-smoke"}).json()
    invalid = client.post(f"/api/sessions/{started['session_id']}/answers", json={"answer": "yes"})
    assert invalid.status_code == 422
    with pytest.raises(ValueError, match="must be a boolean"):
        client.app.state.decision_service.answer(started["session_id"], "yes")
    state = client.get(f"/api/sessions/{started['session_id']}").json()
    assert state["current_node_id"] == started["current_node_id"]
    assert state["path"] == []


def test_invalid_config_fails_on_load(tmp_path):
    (tmp_path / "broken.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid scenario configuration"):
        create_app(tmp_path)
