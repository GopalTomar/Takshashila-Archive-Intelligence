"""Research notebook: notes, saved searches, research sessions.
Research sessions never store API keys (spec 38)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import loads
from app.db.base import get_db
from app.db.models import ResearchNote, ResearchSession, SavedSearch
from app.schemas import NoteIn, SavedSearchIn

router = APIRouter(prefix="/api", tags=["notebook"])


@router.get("/notes")
def list_notes(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(ResearchNote).order_by(ResearchNote.created_at.desc())).scalars().all()
    return {"notes": [{
        "id": n.id, "body": n.body, "document_id": n.document_id, "session_id": n.session_id,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    } for n in rows]}


@router.post("/notes")
def create_note(body: NoteIn, db: Session = Depends(get_db)) -> dict:
    n = ResearchNote(body=body.body, document_id=body.document_id, session_id=body.session_id)
    db.add(n)
    db.commit()
    return {"id": n.id}


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)) -> dict:
    n = db.get(ResearchNote, note_id)
    if n:
        db.delete(n)
        db.commit()
    return {"deleted": note_id}


@router.get("/saved-searches")
def list_saved(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(SavedSearch).order_by(SavedSearch.created_at.desc())).scalars().all()
    return {"saved_searches": [{
        "id": s.id, "name": s.name, "query": s.query, "filters": loads(s.filters),
    } for s in rows]}


@router.post("/saved-searches")
def create_saved(body: SavedSearchIn, db: Session = Depends(get_db)) -> dict:
    import json
    s = SavedSearch(name=body.name, query=body.query, filters=json.dumps(body.filters.model_dump()))
    db.add(s)
    db.commit()
    return {"id": s.id}


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(ResearchSession).order_by(ResearchSession.created_at.desc())).scalars().all()
    return {"sessions": [_session_dict(s) for s in rows]}


@router.get("/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)) -> dict:
    s = db.get(ResearchSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return _session_dict(s, full=True)


def _session_dict(s: ResearchSession, full: bool = False) -> dict:
    d = {
        "id": s.id, "title": s.title, "question": s.question,
        "provider_id": s.provider_id, "model_id": s.model_id,
        "retrieval_mode": s.retrieval_mode, "confidence": s.confidence,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
    if full:
        d["answer"] = s.answer
        d["citations"] = loads(s.citations_json)
        d["sources"] = loads(s.sources_json)
    return d
