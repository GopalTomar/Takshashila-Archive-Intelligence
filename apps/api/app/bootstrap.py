"""Application bootstrap helpers.

``init_db`` creates tables when not using migrations (tests / quick local dev).
In Docker/production, Alembic migrations own the schema. ``seed_registry``
populates the AI provider/model catalog and topic taxonomy idempotently.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.registry import DEFAULT_CATALOG
from app.db.base import Base, engine
from app.db.models import AiModel, AiProvider, Topic
from app.ingestion.taxonomy import load_taxonomy


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def seed_registry(db: Session) -> None:
    # Providers + models.
    for pid, info in DEFAULT_CATALOG.items():
        row = db.execute(select(AiProvider).where(AiProvider.provider_id == pid)).scalar_one_or_none()
        if not row:
            db.add(AiProvider(
                provider_id=pid, provider_name=info.provider_name, adapter=info.adapter,
                base_url=info.default_base_url or None,
                default_model=(info.default_models[0].model_id if info.default_models else None),
            ))
        for m in info.default_models:
            exists = db.execute(
                select(AiModel).where(AiModel.provider_id == pid, AiModel.model_id == m.model_id)
            ).scalar_one_or_none()
            if not exists:
                db.add(AiModel(
                    provider_id=pid, model_id=m.model_id, display_name=m.display_name,
                    supports_streaming=m.supports_streaming, supports_tools=m.supports_tools,
                    supports_structured_output=m.supports_structured_output,
                    supports_reasoning=m.supports_reasoning, supports_embeddings=m.supports_embeddings,
                    supports_vision=m.supports_vision, context_window=m.context_window,
                    pricing_info=m.pricing_info, availability_status=m.availability_status,
                    is_embedding=m.is_embedding,
                ))
    # Topics from taxonomy.
    for topic in load_taxonomy().get("topics", []):
        exists = db.execute(select(Topic).where(Topic.key == topic["id"])).scalar_one_or_none()
        if not exists:
            db.add(Topic(key=topic["id"], label=topic["label"]))
    db.commit()
