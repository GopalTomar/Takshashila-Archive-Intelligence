"""Job task implementations (transport-agnostic).

Each task takes a job_id, opens its own DB session, updates the ProcessingJob
row's status/progress, and records errors explicitly. Tasks are idempotent
where possible and retryable (retry_count is tracked). The same functions are
called by the in-process runner and by Celery.
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone

from app.db.base import SessionLocal
from app.db.models import ProcessingJob, ProcessingStatus
from app.ingestion.crawl_service import run_crawl
from app.logging_config import get_logger

log = get_logger("jobs")


def _load_payload(job: ProcessingJob) -> dict:
    return json.loads(job.payload) if job.payload else {}


def _set_status(db, job, status, **fields):
    job.status = status
    for k, v in fields.items():
        setattr(job, k, v)
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


def run_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(ProcessingJob, job_id)
        if not job:
            log.warning("job_missing", job_id=job_id)
            return
        _set_status(db, job, ProcessingStatus.running)
        payload = _load_payload(job)
        try:
            handler = _HANDLERS.get(job.job_type)
            if not handler:
                raise ValueError(f"unknown job_type: {job.job_type}")
            result = handler(db, job, payload)
            _set_status(db, job, ProcessingStatus.succeeded, result=json.dumps(result or {}))
        except Exception as exc:  # noqa: BLE001
            log.error("job_failed", job_id=job_id, error=str(exc))
            _set_status(
                db, job, ProcessingStatus.failed,
                error_type=type(exc).__name__,
                error_message=f"{exc}\n{traceback.format_exc()[-1500:]}",
                retry_count=job.retry_count + 1,
            )
    finally:
        db.close()


def _handle_crawl(db, job: ProcessingJob, payload: dict) -> dict:
    run = run_crawl(
        db, payload["source_key"],
        seed_urls=payload.get("seed_urls"),
        allow_private=payload.get("allow_private"),
        max_pages=payload.get("max_pages"),
    )
    job.document_id = None
    return {"crawl_run_id": run.id, "status": run.status.value, "stats": json.loads(run.stats or "{}")}


_HANDLERS = {
    "crawl": _handle_crawl,
}


def enqueue(db, job_type: str, payload: dict, document_id: int | None = None) -> ProcessingJob:
    """Create a ProcessingJob row and dispatch it via the configured runner."""
    from app.jobs.runner import dispatch

    job = ProcessingJob(
        job_type=job_type, status=ProcessingStatus.pending,
        payload=json.dumps(payload), document_id=document_id,
    )
    db.add(job)
    db.commit()
    dispatch(job.id)
    return job
