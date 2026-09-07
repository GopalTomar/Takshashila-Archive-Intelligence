"""AI provider registry API: list providers/models, configure keys (encrypted),
and run REAL connection tests. API keys are never returned — only ``has_key``
and a masked hint.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedder
from app.ai.registry import (
    DEFAULT_CATALOG,
    build_provider,
    has_credentials,
    resolve_credentials,
)
from app.config import get_settings
from app.db.base import get_db
from app.db.models import AiModel, AiProvider
from app.schemas import ProviderConfigIn, ProviderKeyIn
from app.security.crypto import encrypt_secret, mask_secret

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("")
def list_providers(db: Session = Depends(get_db)) -> dict:
    out = []
    for pid, info in DEFAULT_CATALOG.items():
        api_key, base_url = resolve_credentials(db, pid)
        row = db.execute(select(AiProvider).where(AiProvider.provider_id == pid)).scalar_one_or_none()
        models = db.execute(select(AiModel).where(AiModel.provider_id == pid)).scalars().all()
        out.append({
            "provider_id": pid,
            "provider_name": info.provider_name,
            "adapter": info.adapter,
            "base_url": base_url,
            "has_key": has_credentials(db, pid),
            "key_hint": mask_secret(api_key) if api_key else "",
            "availability_status": row.availability_status if row else "unknown",
            "default_model": (row.default_model if row else None)
            or (info.default_models[0].model_id if info.default_models else None),
            "models": [_model_dict(m) for m in models] or [
                _cap_dict(m) for m in info.default_models
            ],
        })
    return {"providers": out}


def _model_dict(m: AiModel) -> dict:
    return {
        "model_id": m.model_id, "display_name": m.display_name,
        "supports_streaming": m.supports_streaming, "supports_tools": m.supports_tools,
        "supports_structured_output": m.supports_structured_output,
        "supports_reasoning": m.supports_reasoning, "supports_embeddings": m.supports_embeddings,
        "supports_vision": m.supports_vision, "context_window": m.context_window,
        "pricing_info": m.pricing_info, "availability_status": m.availability_status,
        "is_embedding": m.is_embedding,
    }


def _cap_dict(m) -> dict:
    d = asdict(m)
    return d


@router.put("/{provider_id}/key")
def set_key(provider_id: str, body: ProviderKeyIn, db: Session = Depends(get_db)) -> dict:
    if provider_id not in DEFAULT_CATALOG:
        raise HTTPException(status_code=404, detail="unknown provider")
    info = DEFAULT_CATALOG[provider_id]
    row = db.execute(select(AiProvider).where(AiProvider.provider_id == provider_id)).scalar_one_or_none()
    if not row:
        row = AiProvider(provider_id=provider_id, provider_name=info.provider_name, adapter=info.adapter)
        db.add(row)
    row.api_key_encrypted = encrypt_secret(body.api_key)
    if body.base_url:
        row.base_url = body.base_url
    db.commit()
    # Never echo the key back.
    return {"provider_id": provider_id, "has_key": True, "key_hint": mask_secret(body.api_key)}


@router.delete("/{provider_id}/key")
def delete_key(provider_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.execute(select(AiProvider).where(AiProvider.provider_id == provider_id)).scalar_one_or_none()
    if row:
        row.api_key_encrypted = None
        db.commit()
    return {"provider_id": provider_id, "has_key": has_credentials(db, provider_id)}


@router.put("/{provider_id}/config")
def set_config(provider_id: str, body: ProviderConfigIn, db: Session = Depends(get_db)) -> dict:
    if provider_id not in DEFAULT_CATALOG:
        raise HTTPException(status_code=404, detail="unknown provider")
    info = DEFAULT_CATALOG[provider_id]
    row = db.execute(select(AiProvider).where(AiProvider.provider_id == provider_id)).scalar_one_or_none()
    if not row:
        row = AiProvider(provider_id=provider_id, provider_name=info.provider_name, adapter=info.adapter)
        db.add(row)
    if body.base_url is not None:
        row.base_url = body.base_url
    if body.default_model is not None:
        row.default_model = body.default_model
    db.commit()
    return {"provider_id": provider_id, "base_url": row.base_url, "default_model": row.default_model}


@router.post("/{provider_id}/test")
def test_connection(provider_id: str, db: Session = Depends(get_db)) -> dict:
    """Makes a REAL minimal request to the provider. Never faked."""
    if provider_id not in DEFAULT_CATALOG:
        raise HTTPException(status_code=404, detail="unknown provider")
    provider = build_provider(db, provider_id)
    result = provider.test_connection()
    row = db.execute(select(AiProvider).where(AiProvider.provider_id == provider_id)).scalar_one_or_none()
    if row:
        row.availability_status = "ok" if result.ok else "error"
        db.commit()
    return {"provider_id": provider_id, "ok": result.ok, "detail": result.detail, "models_seen": result.models_seen}


@router.post("/{provider_id}/refresh-models")
def refresh_models(provider_id: str, db: Session = Depends(get_db)) -> dict:
    """Fetch live models from the provider (spec 70) and upsert them."""
    if provider_id not in DEFAULT_CATALOG:
        raise HTTPException(status_code=404, detail="unknown provider")
    provider = build_provider(db, provider_id)
    live = provider.list_models()
    added = 0
    for m in live:
        exists = db.execute(
            select(AiModel).where(AiModel.provider_id == provider_id, AiModel.model_id == m.model_id)
        ).scalar_one_or_none()
        if not exists:
            db.add(AiModel(
                provider_id=provider_id, model_id=m.model_id, display_name=m.display_name,
                availability_status="ok",
            ))
            added += 1
        else:
            exists.availability_status = "ok"
    db.commit()
    return {"provider_id": provider_id, "live_models": len(live), "added": added}


@router.get("/embeddings/status")
def embeddings_status(db: Session = Depends(get_db)) -> dict:
    return asdict(get_embedder(db).status())
