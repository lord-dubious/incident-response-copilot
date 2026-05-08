from incident_response_copilot.models import IncidentTriageRequest, Severity
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


def test_triage_replaces_same_incident_id(tmp_path):
    repo = IncidentRepository(tmp_path / "test.sqlite3")
    repo.ensure_seeded()
    first = repo.triage(
        IncidentTriageRequest(
            id="inc_repeat",
            title="Low signal",
            signal_source="manual.note",
            description="Informational alert",
            severity_hint=Severity.LOW,
        )
    )
    second = repo.triage(
        IncidentTriageRequest(
            id="inc_repeat",
            title="Credential dump",
            signal_source="edr.alert",
            description="Credential dump and API token access detected",
        )
    )
    assert first.incident.severity == Severity.LOW
    assert second.incident.severity == Severity.CRITICAL
    assert repo.detail("inc_repeat") is not None
    assert repo.summary().incident_count == 4
