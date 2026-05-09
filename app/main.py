from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.compliance import router as compliance_router
from app.api.compliance_mapping import router as compliance_mapping_router
from app.api.discovery import router as discovery_router
from app.api.evidence import router as evidence_router
from app.api.health import router as health_router
from app.api.reports import router as reports_router
from app.api.review import router as review_router
from app.api.scans import router as scans_router
from app.core.config import settings
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(scans_router)
app.include_router(compliance_router)
app.include_router(compliance_mapping_router)
app.include_router(evidence_router)
app.include_router(discovery_router)
app.include_router(review_router)
app.include_router(reports_router)
