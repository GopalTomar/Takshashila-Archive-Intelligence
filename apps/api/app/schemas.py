"""Pydantic request/response schemas. API keys are NEVER present in any
response schema — providers expose only ``has_key`` + a masked hint.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ─── Search ────────────────────────────────────────────────
class SearchFiltersIn(BaseModel):
    author: str | None = None
    document_type: str | None = None
    collection_key: str | None = None
    language: str | None = None
    source_key: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    topic_key: str | None = None
    entity_name: str | None = None
    include_demo: bool = False
    document_id: int | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., max_length=2000)
    mode: str = "hybrid"  # keyword|semantic|hybrid
    top_k: int = Field(10, ge=1, le=100)
    hybrid_weight: float = Field(0.5, ge=0.0, le=1.0)
    filters: SearchFiltersIn = SearchFiltersIn()


# ─── Ask (RAG) ─────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., max_length=4000)
    provider_id: str
    model_id: str
    archive_only: bool = True
    reasoning: str | None = None
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(1200, ge=64, le=8192)
    top_k: int = Field(8, ge=1, le=50)
    mode: str = "hybrid"
    filters: SearchFiltersIn = SearchFiltersIn()
    save_session: bool = False


# ─── Providers / settings ──────────────────────────────────
class ProviderKeyIn(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=500)
    base_url: str | None = None


class ProviderConfigIn(BaseModel):
    base_url: str | None = None
    default_model: str | None = None


class RetrievalSettingsIn(BaseModel):
    chunk_target_chars: int | None = Field(None, ge=200, le=8000)
    chunk_overlap_chars: int | None = Field(None, ge=0, le=2000)
    top_k: int | None = Field(None, ge=1, le=100)
    hybrid_weight: float | None = Field(None, ge=0.0, le=1.0)


# ─── Ingestion ─────────────────────────────────────────────
class CrawlRequest(BaseModel):
    source_key: str
    seed_urls: list[str] | None = None
    max_pages: int | None = Field(None, ge=1, le=5000)
    confirm: bool = False  # required for non-fixture live crawls


class IngestUrlRequest(BaseModel):
    source_key: str
    url: str
    confirm: bool = False


# ─── Notes / sessions ──────────────────────────────────────
class NoteIn(BaseModel):
    body: str = Field(..., max_length=20000)
    document_id: int | None = None
    session_id: int | None = None


class SavedSearchIn(BaseModel):
    name: str
    query: str
    filters: SearchFiltersIn = SearchFiltersIn()


# ─── Review ────────────────────────────────────────────────
class ReviewIn(BaseModel):
    review_status: str
