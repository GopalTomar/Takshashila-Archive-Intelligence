"""Crawl orchestration: run a crawl for a source, ingest discovered documents,
record CrawlRun/CrawlItem rows, and write human + machine crawl reports.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import REPO_ROOT, get_settings
from app.db.models import CrawlItem, CrawlRun, ProcessingStatus
from app.ingestion.crawler import Crawler
from app.ingestion.pipeline import ingest_document_bytes
from app.ingestion.sources import get_source_config, sync_source_to_db
from app.logging_config import get_logger

log = get_logger("crawl")


def _reports_dir() -> Path:
    d = REPO_ROOT / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_crawl(
    db: Session,
    source_key: str,
    *,
    seed_urls: list[str] | None = None,
    allow_private: bool | None = None,
    max_pages: int | None = None,
) -> CrawlRun:
    cfg = get_source_config(source_key)
    if not cfg:
        raise ValueError(f"unknown source: {source_key}")
    source = sync_source_to_db(db, cfg)

    rules = cfg.get("crawl_rules", {}) or {}
    seeds = seed_urls if seed_urls is not None else (cfg.get("seed_urls") or [])
    allowed_domains = cfg.get("allowed_domains") or []
    exts = cfg.get("file_extensions") or [".pdf"]
    is_fixtures = source_key == "fixtures"
    allow_private = is_fixtures if allow_private is None else allow_private

    run = CrawlRun(
        source_key=source_key, status=ProcessingStatus.running,
        seed_urls=json.dumps(seeds), started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.flush()

    if not seeds:
        run.status = ProcessingStatus.skipped
        run.finished_at = datetime.now(timezone.utc)
        run.stats = json.dumps({"note": "no seed URLs configured — nothing crawled"})
        db.commit()
        log.info("crawl_no_seeds", source=source_key)
        return run

    crawler = Crawler(
        allowed_domains=allowed_domains,
        file_extensions=exts,
        max_pages=max_pages or rules.get("max_pages", 100),
        max_depth=rules.get("max_depth", 3),
        requests_per_second=rules.get("requests_per_second", 1.0),
        respect_robots=rules.get("respect_robots", True),
        allow_private=allow_private,
    )

    report_dict = {}
    try:
        for item in crawler.crawl(seeds):
            if item.outcome == "report":
                continue
            ci = CrawlItem(
                run_id=run.id, url=item.url, http_status=item.http_status,
                content_type=item.content_type, file_size=item.file_size,
                outcome=item.outcome, reason=item.reason,
            )
            if item.outcome == "downloaded" and item.content:
                try:
                    doc = ingest_document_bytes(
                        db, source=source, content=item.content, source_url=item.url,
                        content_type=item.content_type, is_demo=is_fixtures,
                    )
                    ci.document_id = doc.id
                    if doc.sha256 and doc.document_id and ci.reason is None:
                        ci.outcome = "downloaded"
                except Exception as exc:  # ingestion failure shouldn't abort crawl
                    ci.outcome = "failed"
                    ci.reason = f"ingest error: {exc}"
                    log.warning("ingest_failed", url=item.url, error=str(exc))
            db.add(ci)
            db.flush()
        report_dict = crawler.last_report.to_dict()
        run.status = ProcessingStatus.succeeded
    except Exception as exc:
        run.status = ProcessingStatus.failed
        run.error = str(exc)
        log.error("crawl_failed", source=source_key, error=str(exc))

    run.finished_at = datetime.now(timezone.utc)
    run.stats = json.dumps(report_dict)
    db.commit()

    _write_reports(source_key, run, report_dict)
    return run


def _write_reports(source_key: str, run: CrawlRun, report: dict) -> None:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    base = _reports_dir() / f"crawl-{source_key}-{date}"
    payload = {
        "source": source_key,
        "run_id": run.id,
        "status": run.status.value if run.status else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "report": report,
    }
    base.with_suffix(".json").write_text(json.dumps(payload, indent=2))

    lines = [
        f"# Crawl report — {source_key}",
        "",
        f"- Run ID: {run.id}",
        f"- Status: {payload['status']}",
        f"- Started: {payload['started_at']}",
        f"- Finished: {payload['finished_at']}",
        "",
        "## Results",
        "",
    ]
    for k, v in report.items():
        if k == "errors":
            continue
        lines.append(f"- {k.replace('_', ' ').title()}: {v}")
    if report.get("errors"):
        lines += ["", "## Errors", ""]
        lines += [f"- {e}" for e in report["errors"][:50]]
    base.with_suffix(".md").write_text("\n".join(lines) + "\n")
