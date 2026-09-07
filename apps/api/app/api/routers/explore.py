"""Timeline, entities, collections, topics — evidence-backed exploration."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serializers import document_summary
from app.db.base import get_db
from app.db.models import (
    ArchiveCollection,
    Document,
    DocumentEntity,
    DocumentEvent,
    DocumentTopic,
    Entity,
    Event,
    Topic,
)

router = APIRouter(prefix="/api", tags=["explore"])


@router.get("/topics")
def list_topics(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(
        select(Topic, func.count(DocumentTopic.id))
        .outerjoin(DocumentTopic, DocumentTopic.topic_id == Topic.id)
        .group_by(Topic.id).order_by(Topic.label)
    ).all()
    return {"topics": [{"key": t.key, "label": t.label, "document_count": c} for t, c in rows]}


@router.get("/collections")
def list_collections(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(
        select(ArchiveCollection, func.count(Document.id))
        .outerjoin(Document, Document.collection_id == ArchiveCollection.id)
        .group_by(ArchiveCollection.id)
    ).all()
    return {"collections": [{
        "collection_key": c.collection_key, "name": c.name, "description": c.description,
        "is_demo": c.is_demo, "document_count": n,
    } for c, n in rows]}


@router.get("/entities")
def list_entities(
    entity_type: str | None = None, q: str | None = None,
    limit: int = 100, db: Session = Depends(get_db),
) -> dict:
    stmt = (
        select(Entity, func.count(DocumentEntity.id))
        .outerjoin(DocumentEntity, DocumentEntity.entity_id == Entity.id)
        .group_by(Entity.id).order_by(func.count(DocumentEntity.id).desc()).limit(limit)
    )
    if entity_type:
        stmt = stmt.where(Entity.entity_type == entity_type)
    if q:
        stmt = stmt.where(Entity.name.ilike(f"%{q}%"))
    rows = db.execute(stmt).all()
    return {"entities": [{
        "id": e.id, "type": e.entity_type, "name": e.name,
        "mention_count": n, "latitude": e.latitude, "longitude": e.longitude,
        "coord_precision": e.coord_precision,
    } for e, n in rows]}


@router.get("/entities/{entity_id}")
def entity_detail(entity_id: int, db: Session = Depends(get_db)) -> dict:
    e = db.get(Entity, entity_id)
    if not e:
        raise HTTPException(status_code=404, detail="entity not found")
    docs = db.execute(
        select(Document, DocumentEntity.page_number, DocumentEntity.mention)
        .join(DocumentEntity, DocumentEntity.document_id == Document.id)
        .where(DocumentEntity.entity_id == entity_id)
    ).all()
    return {
        "id": e.id, "type": e.entity_type, "name": e.name, "description": e.description,
        "coordinates": ({"lat": e.latitude, "lon": e.longitude, "precision": e.coord_precision,
                         "source": e.coord_source} if e.latitude is not None else None),
        "documents": [{**document_summary(d), "page": pg, "mention": mn} for d, pg, mn in docs],
    }


@router.get("/map/entities")
def map_entities(db: Session = Depends(get_db)) -> dict:
    """Only entities with REAL coordinates (never invented) appear on the map."""
    rows = db.execute(
        select(Entity).where(Entity.latitude.is_not(None), Entity.longitude.is_not(None))
    ).scalars().all()
    return {"points": [{
        "id": e.id, "name": e.name, "type": e.entity_type,
        "lat": e.latitude, "lon": e.longitude,
        "precision": e.coord_precision, "source": e.coord_source,
    } for e in rows],
        "note": "Only entities with verified/supplied coordinates are shown. Coordinates are never fabricated.",
    }


@router.get("/timeline")
def timeline(db: Session = Depends(get_db)) -> dict:
    events = db.execute(select(Event).order_by(Event.event_date)).scalars().all()
    out = []
    for ev in events:
        doc_count = db.execute(
            select(func.count(DocumentEvent.id)).where(DocumentEvent.event_id == ev.id)
        ).scalar() or 0
        out.append({
            "event_key": ev.event_key, "title": ev.title, "description": ev.description,
            "date": ev.event_date, "date_precision": ev.date_precision.value,
            "source": ev.source.value, "verified": ev.verified,
            "label": "verified" if ev.verified else "AI-extracted (unverified)",
            "document_count": doc_count, "is_demo": ev.is_demo,
        })
    return {"events": out, "note": "Events are labelled AI-extracted until a human verifies them."}
