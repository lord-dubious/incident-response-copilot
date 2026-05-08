from fastapi.testclient import TestClient

from incident_response_copilot.config import Settings
from incident_response_copilot.main import create_app


def test_dashboard_assets(tmp_path):
    c = TestClient(create_app(Settings(database_path=tmp_path / "test.sqlite3")))
    shell = c.get("/").text
    assert "Response Copilot" in shell
    assert "Create incident" in shell
    css = c.get("/static/styles.css")
    assert css.status_code == 200
    assert "triage-panel" in css.text
    app_js = c.get("/static/app.js").text
    assert "/api/summary" in app_js
    assert "/api/incidents/triage" in app_js
    assert "SAMPLE_TRIAGE" in app_js
