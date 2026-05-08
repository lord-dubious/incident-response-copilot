from fastapi.testclient import TestClient

from incident_response_copilot.config import Settings
from incident_response_copilot.main import create_app


def client(tmp_path):
    return TestClient(create_app(Settings(database_path=tmp_path / "test.sqlite3")))


def test_summary_and_incidents(tmp_path):
    c = client(tmp_path)
    assert c.get("/api/health").json() == {"status": "ok"}
    summary = c.get("/api/summary").json()
    assert summary["incident_count"] == 3
    assert summary["critical_count"] == 1
    assert summary["approval_task_count"] == 3
    assert len(c.get("/api/incidents").json()) == 3


def test_incident_detail_and_reset(tmp_path):
    c = client(tmp_path)
    detail = c.get("/api/incidents/inc_malware_callback").json()
    assert detail["incident"]["severity"] == "critical"
    assert len(detail["evidence"]) == 2
    assert c.get("/api/incidents/missing").status_code == 404
    assert c.post("/api/demo/reset").json()["incident_count"] == 3
