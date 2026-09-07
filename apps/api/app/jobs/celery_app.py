"""Celery application (used in Docker with Redis)."""
from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()
celery_app = Celery("takshashila", broker=settings.redis_url or "redis://localhost:6379/0",
                    backend=settings.redis_url or "redis://localhost:6379/0")
celery_app.conf.update(task_track_started=True, task_acks_late=True, worker_max_tasks_per_child=50)


@celery_app.task(name="run_job", bind=True, max_retries=3)
def run_job_task(self, job_id: int):  # pragma: no cover - exercised in Docker
    from app.jobs.tasks import run_job
    run_job(job_id)
