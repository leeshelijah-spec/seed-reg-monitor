from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routes.web import router
from .services.scheduler import create_scheduler


scheduler = create_scheduler() if settings.scheduler_enabled else None


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
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "scheduler_enabled": settings.scheduler_enabled}
