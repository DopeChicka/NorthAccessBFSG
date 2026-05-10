from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.compliance import router as compliance_router
from app.api.compliance_mapping import router as compliance_mapping_router
from app.api.delta import router as delta_router
from app.api.discovery import router as discovery_router
from app.api.evidence import router as evidence_router
from app.api.health import router as health_router
from app.api.journeys import router as journeys_router
from app.api.public import router as public_router
from app.api.reports import router as reports_router
from app.api.review import router as review_router
from app.api.scans import router as scans_router
from app.core.config import settings
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def configure_cors(app: FastAPI, origins: list[str]) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

configure_cors(app, settings.frontend_origins)

app.include_router(health_router)
app.include_router(scans_router)
app.include_router(compliance_router)
app.include_router(compliance_mapping_router)
app.include_router(delta_router)
app.include_router(evidence_router)
app.include_router(discovery_router)
app.include_router(journeys_router)
app.include_router(review_router)
app.include_router(reports_router)
app.include_router(public_router)
