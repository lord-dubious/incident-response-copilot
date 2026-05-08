from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    TRIAGE = "triage"
    CONTAINMENT = "containment"
    RESOLVED = "resolved"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class Incident(BaseModel):
    id: str
    title: str
    severity: Severity
    status: IncidentStatus
    started_at: datetime = Field(default_factory=utcnow)
    summary: str


class IncidentTriageRequest(BaseModel):
    id: str | None = None
    title: str
    signal_source: str
    description: str
    severity_hint: Severity | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    id: str
    incident_id: str
    source: str
    description: str
    confidence: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineEvent(BaseModel):
    id: str
    incident_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    message: str
    actor: str


class ResponseTask(BaseModel):
    id: str
    incident_id: str
    title: str
    status: TaskStatus
    owner: str
    requires_approval: bool


class PlaybookStep(BaseModel):
    id: str
    incident_id: str
    title: str
    rationale: str
    human_review_note: str


class IncidentDetail(BaseModel):
    incident: Incident
    evidence: list[EvidenceItem]
    timeline: list[TimelineEvent]
    tasks: list[ResponseTask]
    playbook: list[PlaybookStep]


class IncidentSummary(BaseModel):
    incident_count: int
    critical_count: int
    open_task_count: int
    approval_task_count: int
    evidence_count: int
