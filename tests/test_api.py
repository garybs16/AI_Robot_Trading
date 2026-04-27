import sys
from pathlib import Path

from fastapi.testclient import TestClient

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from api.app import create_app


def test_health_endpoint():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["live_trading_enabled"] is False


def test_events_endpoint_returns_list():
    client = TestClient(create_app())
    response = client.get("/events?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json()["events"], list)


def test_kill_switch_lifecycle():
    client = TestClient(create_app())
    activate = client.post("/kill-switch", json={"reason": "test api"})
    assert activate.status_code == 200
    assert client.get("/health").json()["kill_switch_active"] is True
    clear = client.delete("/kill-switch")
    assert clear.status_code == 200
    assert client.get("/health").json()["kill_switch_active"] is False

