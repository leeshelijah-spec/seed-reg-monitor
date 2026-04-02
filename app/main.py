from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routes.web import router
from .services.scheduler import create_scheduler


scheduler = create_scheduler() if settings.scheduler_enabled else None
READ_ONLY_ALLOWED_METHODS = {"GET", "HEAD", "OPTIONS"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if scheduler and not scheduler.running:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler and scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Seed Regulation Monitor", lifespan=lifespan)


@app.middleware("http")
async def enforce_read_only_mode(request: Request, call_next):
    if settings.read_only_mode and request.method not in READ_ONLY_ALLOWED_METHODS:
        return JSONResponse(
            status_code=403,
            content={"detail": "Read-only mode is enabled. Write operations are blocked."},
        )
    return await call_next(request)


app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    favicon_path = Path("app") / "favicon.ico"
    return FileResponse(favicon_path)


@app.get("/health")
def health():
    return {"status": "ok", "scheduler_enabled": settings.scheduler_enabled}
