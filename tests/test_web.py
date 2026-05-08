from fastapi.testclient import TestClient

from incident_response_copilot.config import Settings
from incident_response_copilot.main import create_app


def test_dashboard_assets(tmp_path):
    c = TestClient(create_app(Settings(database_path=tmp_path / "test.sqlite3")))
    assert "Response Copilot" in c.get("/").text
    assert c.get("/static/styles.css").status_code == 200
    assert "/api/summary" in c.get("/static/app.js").text
