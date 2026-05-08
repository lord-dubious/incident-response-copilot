from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from incident_response_copilot.api import router as api_router
from incident_response_copilot.config import Settings
from incident_response_copilot.repository import IncidentRepository
from incident_response_copilot.web import ASSET_ROOT
from incident_response_copilot.web import router as web_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    repository = IncidentRepository(settings.database_path)
    repository.ensure_seeded()
    app = FastAPI(title="Incident Response Copilot", version="0.1.0")
    app.state.repository = repository
    app.mount("/static", StaticFiles(directory=ASSET_ROOT), name="static")
    app.include_router(web_router)
    app.include_router(api_router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("incident_response_copilot.main:app", host="127.0.0.1", port=8060, reload=False)
