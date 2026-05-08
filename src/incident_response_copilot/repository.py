from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from incident_response_copilot import demo_data
from incident_response_copilot.models import (
    EvidenceItem,
    Incident,
    IncidentDetail,
    IncidentStatus,
    IncidentSummary,
    IncidentTriageRequest,
    PlaybookStep,
    ResponseTask,
    Severity,
    TaskStatus,
    TimelineEvent,
    utcnow,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class IncidentRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self._connect() as conn:
            for table in ["incidents", "evidence", "timeline", "tasks", "playbook"]:
                conn.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
                )

    def reset_demo_data(self) -> None:
        self.initialize()
        with self._connect() as conn:
            for table in ["playbook", "tasks", "timeline", "evidence", "incidents"]:
                conn.execute(f"DELETE FROM {table}")
            self._insert_many(conn, "incidents", demo_data.demo_incidents())
            self._insert_many(conn, "evidence", demo_data.demo_evidence())
            self._insert_many(conn, "timeline", demo_data.demo_timeline())
            self._insert_many(conn, "tasks", demo_data.demo_tasks())
            self._insert_many(conn, "playbook", demo_data.demo_playbook())

    def ensure_seeded(self) -> None:
        self.initialize()
        with self._connect() as conn:
            if conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 0:
                self.reset_demo_data()

    def list_incidents(self) -> list[Incident]:
        return sorted(self._load_all("incidents", Incident), key=lambda row: row.started_at)

    def detail(self, incident_id: str) -> IncidentDetail | None:
        incident = self._load_one("incidents", incident_id, Incident)
        if incident is None:
            return None
        return IncidentDetail(
            incident=incident,
            evidence=[
                e for e in self._load_all("evidence", EvidenceItem) if e.incident_id == incident_id
            ],
            timeline=[
                e for e in self._load_all("timeline", TimelineEvent) if e.incident_id == incident_id
            ],
            tasks=[
                t for t in self._load_all("tasks", ResponseTask) if t.incident_id == incident_id
            ],
            playbook=[
                p for p in self._load_all("playbook", PlaybookStep) if p.incident_id == incident_id
            ],
        )

    def triage(self, payload: IncidentTriageRequest) -> IncidentDetail:
        self.initialize()
        incident_id = payload.id or self._next_incident_id()
        now = utcnow()
        severity = payload.severity_hint or self._infer_severity(payload)
        status = (
            IncidentStatus.CONTAINMENT
            if severity in {Severity.HIGH, Severity.CRITICAL}
            else IncidentStatus.TRIAGE
        )
        incident = Incident(
            id=incident_id,
            title=payload.title,
            severity=severity,
            status=status,
            started_at=now,
            summary=self._summary_for(payload, severity),
        )
        evidence = self._evidence_for(incident_id, payload, severity)
        timeline = self._timeline_for(incident_id, now, payload, severity)
        tasks = self._tasks_for(incident_id, payload, severity)
        playbook = self._playbook_for(incident_id, payload, severity)

        with self._connect() as conn:
            for table in ["playbook", "tasks", "timeline", "evidence"]:
                self._delete_children(conn, table, incident_id)
            conn.execute(
                "INSERT OR REPLACE INTO incidents (id, payload) VALUES (?, ?)",
                (incident.id, incident.model_dump_json()),
            )
            self._insert_many(conn, "evidence", evidence)
            self._insert_many(conn, "timeline", timeline)
            self._insert_many(conn, "tasks", tasks)
            self._insert_many(conn, "playbook", playbook)

        return IncidentDetail(
            incident=incident,
            evidence=evidence,
            timeline=timeline,
            tasks=tasks,
            playbook=playbook,
        )

    def summary(self) -> IncidentSummary:
        incidents = self._load_all("incidents", Incident)
        tasks = self._load_all("tasks", ResponseTask)
        evidence = self._load_all("evidence", EvidenceItem)
        return IncidentSummary(
            incident_count=len(incidents),
            critical_count=sum(i.severity == Severity.CRITICAL for i in incidents),
            open_task_count=sum(t.status != TaskStatus.DONE for t in tasks),
            approval_task_count=sum(t.requires_approval for t in tasks),
            evidence_count=len(evidence),
        )

    def _insert_many(self, conn: sqlite3.Connection, table: str, rows: Sequence[BaseModel]) -> None:
        conn.executemany(
            f"INSERT INTO {table} (id, payload) VALUES (?, ?)",
            [(str(row.model_dump()["id"]), row.model_dump_json()) for row in rows],
        )

    def _next_incident_id(self) -> str:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        return f"inc_live_{count + 1:03d}"

    def _delete_children(self, conn: sqlite3.Connection, table: str, incident_id: str) -> None:
        rows = conn.execute(f"SELECT id, payload FROM {table}").fetchall()
        for row in rows:
            payload = json.loads(row["payload"])
            if payload.get("incident_id") == incident_id:
                conn.execute(f"DELETE FROM {table} WHERE id = ?", (row["id"],))

    def _infer_severity(self, payload: IncidentTriageRequest) -> Severity:
        text = f"{payload.title} {payload.description} {json.dumps(payload.metadata, sort_keys=True)}".lower()
        if any(
            marker in text
            for marker in ["malware", "ransom", "exfil", "callback", "credential dump"]
        ):
            return Severity.CRITICAL
        if any(
            marker in text
            for marker in ["bruteforce", "failed login", "production", "admin", "privilege"]
        ):
            return Severity.HIGH
        if any(
            marker in text
            for marker in ["kubernetes", "egress", "policy", "degraded", "suspicious"]
        ):
            return Severity.MEDIUM
        return Severity.LOW

    def _summary_for(self, payload: IncidentTriageRequest, severity: Severity) -> str:
        return (
            f"Local triage classified {payload.signal_source} as {severity} based on submitted "
            "evidence. Recommendations are reviewable guidance, not automated containment."
        )

    def _evidence_for(
        self, incident_id: str, payload: IncidentTriageRequest, severity: Severity
    ) -> list[EvidenceItem]:
        confidence = {
            Severity.CRITICAL: 0.9,
            Severity.HIGH: 0.84,
            Severity.MEDIUM: 0.74,
            Severity.LOW: 0.58,
        }[severity]
        rows = [
            EvidenceItem(
                id=f"ev_{incident_id}_submitted",
                incident_id=incident_id,
                source=payload.signal_source,
                description=payload.description,
                confidence=confidence,
                metadata=payload.metadata,
            )
        ]
        if payload.metadata:
            rows.append(
                EvidenceItem(
                    id=f"ev_{incident_id}_metadata",
                    incident_id=incident_id,
                    source="triage.metadata",
                    description="Submitted metadata influenced deterministic severity and task selection.",
                    confidence=max(confidence - 0.12, 0.4),
                    metadata=payload.metadata,
                )
            )
        return rows

    def _timeline_for(
        self, incident_id: str, now, payload: IncidentTriageRequest, severity: Severity
    ) -> list[TimelineEvent]:
        return [
            TimelineEvent(
                id=f"tl_{incident_id}_received",
                incident_id=incident_id,
                timestamp=now,
                actor="copilot",
                message=f"Received {payload.signal_source} signal for local triage.",
            ),
            TimelineEvent(
                id=f"tl_{incident_id}_classified",
                incident_id=incident_id,
                timestamp=now,
                actor="copilot",
                message=f"Classified severity as {severity} and generated reviewable response tasks.",
            ),
        ]

    def _tasks_for(
        self, incident_id: str, payload: IncidentTriageRequest, severity: Severity
    ) -> list[ResponseTask]:
        tasks = [
            ResponseTask(
                id=f"task_{incident_id}_validate",
                incident_id=incident_id,
                title="Validate submitted evidence and source reliability",
                status=TaskStatus.TODO,
                owner="soc",
                requires_approval=False,
            )
        ]
        if severity in {Severity.HIGH, Severity.CRITICAL}:
            tasks.append(
                ResponseTask(
                    id=f"task_{incident_id}_containment",
                    incident_id=incident_id,
                    title="Prepare containment action for human approval",
                    status=TaskStatus.BLOCKED,
                    owner="incident-commander",
                    requires_approval=True,
                )
            )
        if "kubernetes" in payload.description.lower() or "egress" in payload.description.lower():
            tasks.append(
                ResponseTask(
                    id=f"task_{incident_id}_network_policy",
                    incident_id=incident_id,
                    title="Draft Kubernetes NetworkPolicy change in dry-run mode",
                    status=TaskStatus.TODO,
                    owner="platform",
                    requires_approval=True,
                )
            )
        return tasks

    def _playbook_for(
        self, incident_id: str, payload: IncidentTriageRequest, severity: Severity
    ) -> list[PlaybookStep]:
        return [
            PlaybookStep(
                id=f"pb_{incident_id}_validate",
                incident_id=incident_id,
                title="Validate evidence before action",
                rationale="Local triage summarizes submitted evidence but does not prove source accuracy.",
                human_review_note="Confirm evidence in the source system before containment.",
            ),
            PlaybookStep(
                id=f"pb_{incident_id}_contain",
                incident_id=incident_id,
                title="Choose containment path",
                rationale=f"Severity {severity} determines whether containment needs approval before action.",
                human_review_note="Do not run production containment from this demo workspace.",
            ),
        ]

    def _load_one(self, table: str, row_id: str, model: type[ModelT]) -> ModelT | None:
        with self._connect() as conn:
            row = conn.execute(f"SELECT payload FROM {table} WHERE id = ?", (row_id,)).fetchone()
        return model.model_validate(json.loads(row["payload"])) if row else None

    def _load_all(self, table: str, model: type[ModelT]) -> list[ModelT]:
        with self._connect() as conn:
            rows = conn.execute(f"SELECT payload FROM {table} ORDER BY id").fetchall()
        return [model.model_validate(json.loads(row["payload"])) for row in rows]
