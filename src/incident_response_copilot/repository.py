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
    IncidentSummary,
    PlaybookStep,
    ResponseTask,
    Severity,
    TaskStatus,
    TimelineEvent,
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

    def _load_one(self, table: str, row_id: str, model: type[ModelT]) -> ModelT | None:
        with self._connect() as conn:
            row = conn.execute(f"SELECT payload FROM {table} WHERE id = ?", (row_id,)).fetchone()
        return model.model_validate(json.loads(row["payload"])) if row else None

    def _load_all(self, table: str, model: type[ModelT]) -> list[ModelT]:
        with self._connect() as conn:
            rows = conn.execute(f"SELECT payload FROM {table} ORDER BY id").fetchall()
        return [model.model_validate(json.loads(row["payload"])) for row in rows]
