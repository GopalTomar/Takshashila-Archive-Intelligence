"""Ingestion / admin: crawl jobs, single-URL ingest, demo seed, job status."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import loads
from app.db.base import get_db
from app.db.models import CrawlItem, CrawlRun, ProcessingJob, Source
from app.ingestion.fetcher import FetchError, fetch
from app.ingestion.pipeline import ingest_document_bytes
from app.ingestion.sources import get_source_config, load_sources_config, sync_source_to_db
from app.jobs.tasks import enqueue
from app.schemas import CrawlRequest, IngestUrlRequest

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


@router.get("/sources")
def list_sources() -> dict:
    out = []
    for cfg in load_sources_config():
        out.append({
            "id": cfg.get("id"), "name": cfg.get("name"),
            "base_url": cfg.get("base_url"), "seed_url_count": len(cfg.get("seed_urls") or []),
            "allowed_domains": cfg.get("allowed_domains"), "enabled": cfg.get("enabled", True),
            "notes": cfg.get("notes"),
        })
    return {"sources": out}


@router.post("/crawl")
def start_crawl(req: CrawlRequest, db: Session = Depends(get_db)) -> dict:
    cfg = get_source_config(req.source_key)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"unknown source: {req.source_key}")
    seeds = req.seed_urls if req.seed_urls is not None else (cfg.get("seed_urls") or [])
    if not seeds:
        raise HTTPException(
            status_code=400,
            detail="No seed URLs. Add verified public URLs to config/sources.yaml or pass seed_urls.",
        )
    # A live (non-fixture) crawl requires explicit confirmation.
    if req.source_key != "fixtures" and not req.confirm:
        raise HTTPException(
            status_code=400,
            detail="Live crawl requires confirm=true. Verify URLs are public and permitted first.",
        )
    job = enqueue(db, "crawl", {
        "source_key": req.source_key, "seed_urls": req.seed_urls, "max_pages": req.max_pages,
    })
    return {"job_id": job.id, "status": job.status.value, "source_key": req.source_key}


@router.post("/ingest-url")
def ingest_url(req: IngestUrlRequest, db: Session = Depends(get_db)) -> dict:
    """Ingest a single verified public document URL (synchronous, small)."""
    cfg = get_source_config(req.source_key)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"unknown source: {req.source_key}")
    if req.source_key != "fixtures" and not req.confirm:
        raise HTTPException(status_code=400, detail="confirm=true required for live ingest")
    source = sync_source_to_db(db, cfg)
    allowed = cfg.get("allowed_domains") or []
    allow_private = req.source_key == "fixtures"
    try:
        result = fetch(req.url, allowed, allow_private=allow_private, binary=True)
    except FetchError as exc:
        raise HTTPException(status_code=502, detail=f"fetch failed: {exc}")
    doc = ingest_document_bytes(
        db, source=source, content=result.content, source_url=result.url,
        content_type=result.content_type, is_demo=(req.source_key == "fixtures"),
    )
    db.commit()
    return {"document_id": doc.document_id, "sha256": doc.sha256, "pages": doc.page_count,
            "ocr_status": doc.ocr_status.value, "index_status": doc.index_status.value}


@router.get("/jobs")
def list_jobs(limit: int = 25, db: Session = Depends(get_db)) -> dict:
    jobs = db.execute(
        select(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(limit)
    ).scalars().all()
    return {"jobs": [_job_dict(j) for j in jobs]}


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_dict(job, full=True)


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    """Restart a failed ingestion job (spec 50.20)."""
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    from app.db.models import ProcessingStatus
    job.status = ProcessingStatus.pending
    job.error_type = None
    job.error_message = None
    db.commit()
    from app.jobs.runner import dispatch
    dispatch(job.id)
    return {"job_id": job.id, "status": job.status.value}


def _job_dict(j: ProcessingJob, full: bool = False) -> dict:
    d = {
        "id": j.id, "job_type": j.job_type, "status": j.status.value,
        "retry_count": j.retry_count, "error_type": j.error_type,
        "document_id": j.document_id, "created_at": j.created_at.isoformat() if j.created_at else None,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
    }
    if full:
        d["payload"] = loads(j.payload)
        d["result"] = loads(j.result)
        d["error_message"] = j.error_message
        d["progress"] = loads(j.progress)
    return d


@router.get("/crawls")
def list_crawls(limit: int = 25, db: Session = Depends(get_db)) -> dict:
    runs = db.execute(select(CrawlRun).order_by(CrawlRun.created_at.desc()).limit(limit)).scalars().all()
    return {"crawls": [{
        "id": r.id, "source_key": r.source_key, "status": r.status.value,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "stats": loads(r.stats), "error": r.error,
    } for r in runs]}


@router.get("/crawls/{crawl_id}")
def get_crawl(crawl_id: int, db: Session = Depends(get_db)) -> dict:
    run = db.get(CrawlRun, crawl_id)
    if not run:
        raise HTTPException(status_code=404, detail="crawl not found")
    items = db.execute(select(CrawlItem).where(CrawlItem.run_id == crawl_id)).scalars().all()
    return {
        "id": run.id, "source_key": run.source_key, "status": run.status.value,
        "stats": loads(run.stats),
        "items": [{"url": i.url, "outcome": i.outcome, "http_status": i.http_status,
                   "content_type": i.content_type, "reason": i.reason} for i in items],
    }


@router.post("/demo/seed")
def seed_demo_data(db: Session = Depends(get_db)) -> dict:
    from app.seed.demo import seed_demo
    ids = seed_demo(db)
    return {"seeded": ids, "note": "DEMO DATA — NOT ARCHIVAL MATERIAL"}


@router.post("/demo/clear")
def clear_demo_data(db: Session = Depends(get_db)) -> dict:
    from app.seed.demo import clear_demo
    n = clear_demo(db)
    return {"cleared": n}
