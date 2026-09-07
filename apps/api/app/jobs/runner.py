"""Job dispatch.

Long tasks must never block the API request. Two backends:
  * Celery (when REDIS_URL is set and JOBS_INLINE is false) — production/Docker.
  * In-process thread pool — local dev/tests without Redis.

Both run the same ``run_job(job_id)`` implementation from tasks.py.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.config import get_settings
from app.logging_config import get_logger

log = get_logger("jobs.runner")
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="job")


def dispatch(job_id: int) -> None:
    settings = get_settings()
    if settings.use_celery:
        try:
            from app.jobs.celery_app import run_job_task
            run_job_task.delay(job_id)
            return
        except Exception as exc:  # pragma: no cover - falls back if broker down
            log.warning("celery_dispatch_failed_falling_back_inline", error=str(exc))
    # In-process.
    from app.jobs.tasks import run_job
    _executor.submit(run_job, job_id)


def run_now(job_id: int) -> None:
    """Synchronous execution (tests / acceptance script)."""
    from app.jobs.tasks import run_job
    run_job(job_id)
