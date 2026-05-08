from incident_response_copilot.repository import IncidentRepository


def test_seed_and_detail(tmp_path):
    repo = IncidentRepository(tmp_path / "test.sqlite3")
    repo.ensure_seeded()
    repo.ensure_seeded()
    assert repo.summary().open_task_count == 3
    detail = repo.detail("inc_siem_bruteforce")
    assert detail is not None
    assert detail.timeline
    assert any(task.requires_approval for task in detail.tasks)
