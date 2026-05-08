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


def test_triage_creates_high_risk_incident(tmp_path):
    c = client(tmp_path)
    response = c.post(
        "/api/incidents/triage",
        json={
            "id": "inc_live_admin_login",
            "title": "Suspicious production admin login spike",
            "signal_source": "siem.alert",
            "description": "Multiple failed admin logins followed by a production login from a new ASN",
            "metadata": {"environment": "production", "failed_logins": 37},
        },
    )
    assert response.status_code == 200
    detail = response.json()
    assert detail["incident"]["id"] == "inc_live_admin_login"
    assert detail["incident"]["severity"] == "high"
    assert detail["incident"]["status"] == "containment"
    assert len(detail["evidence"]) == 2
    assert any(task["requires_approval"] for task in detail["tasks"])
    assert (
        c.get("/api/incidents/inc_live_admin_login").json()["incident"]["title"]
        == "Suspicious production admin login spike"
    )


def test_triage_handles_kubernetes_policy_signal(tmp_path):
    c = client(tmp_path)
    detail = c.post(
        "/api/incidents/triage",
        json={
            "title": "Unexpected namespace egress",
            "signal_source": "k8s.flow",
            "description": "Kubernetes egress traffic is not covered by NetworkPolicy",
        },
    ).json()
    assert detail["incident"]["id"].startswith("inc_live_")
    assert detail["incident"]["severity"] == "medium"
    assert any("NetworkPolicy" in task["title"] for task in detail["tasks"])


def test_triage_accepts_explicit_severity_hint(tmp_path):
    c = client(tmp_path)
    detail = c.post(
        "/api/incidents/triage",
        json={
            "title": "Malware callback reported by sandbox",
            "signal_source": "sandbox.report",
            "description": "Suspicious callback indicator",
            "severity_hint": "critical",
        },
    ).json()
    assert detail["incident"]["severity"] == "critical"
    assert detail["incident"]["status"] == "containment"
