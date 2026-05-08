from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "northaccessbfsg",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.scan_worker"],
)

celery_app.conf.update(
    accept_content=["json"],
    enable_utc=True,
    result_serializer="json",
    task_serializer="json",
    task_track_started=True,
    timezone="UTC",
)
