from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from incident_response_copilot.models import IncidentDetail, IncidentSummary
from incident_response_copilot.repository import IncidentRepository

router = APIRouter(prefix="/api")


def get_repository(request: Request) -> IncidentRepository:
    return request.app.state.repository


RepositoryDep = Annotated[IncidentRepository, Depends(get_repository)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/summary", response_model=IncidentSummary)
def summary(repository: RepositoryDep) -> IncidentSummary:
    return repository.summary()


@router.post("/demo/reset", response_model=IncidentSummary)
def reset_demo(repository: RepositoryDep) -> IncidentSummary:
    repository.reset_demo_data()
    return repository.summary()


@router.get("/incidents")
def incidents(repository: RepositoryDep):
    return repository.list_incidents()


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
def incident_detail(incident_id: str, repository: RepositoryDep) -> IncidentDetail:
    detail = repository.detail(incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return detail
