from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

ASSET_ROOT = Path(__file__).parent / "web_assets"
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return (ASSET_ROOT / "index.html").read_text(encoding="utf-8")
