"""Core archival data model.

Provenance-first: every document carries source URL, archived URL, local path,
checksum and retrieval date; every chunk carries document + page number so a
citation resolves to an exact page. Unknown values are stored as NULL — never
guessed. Demo/synthetic records are flagged with ``is_demo`` and kept in a
separate collection so they can never be confused with archival material.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db.base import Base
from app.db.types import Vector

EMBED_DIM = get_settings().embedding_dimensions


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── Enums (explicit statuses — ingestion is never all-or-nothing) ──
class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"
    not_applicable = "not_applicable"


class MetadataSource(str, enum.Enum):
    verified = "verified"      # human/deterministic, authoritative
    deterministic = "deterministic"  # extracted from file/PDF metadata
    ai = "ai"                  # AI-suggested, requires review
    unknown = "unknown"


class ReviewStatus(str, enum.Enum):
    unreviewed = "unreviewed"
    verified = "verified"
    needs_review = "needs_review"
    incorrect_metadata = "incorrect_metadata"
    duplicate = "duplicate"
    ocr_poor = "ocr_poor"
    source_uncertain = "source_uncertain"


class DatePrecision(str, enum.Enum):
    exact = "exact"
    month = "month"
    year = "year"
    decade = "decade"
    unknown = "unknown"


# ─── Sources & collections ─────────────────────────────────
class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(512))
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    doc_prefix: Mapped[str] = mapped_column(String(16), default="DOC")
    next_seq: Mapped[int] = mapped_column(Integer, default=1)
    rights_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    access_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    copyright_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    documents: Mapped[list["Document"]] = relationship(back_populates="source")


class ArchiveCollection(Base):
    __tablename__ = "archive_collections"
    id: Mapped[int] = mapped_column(primary_key=True)
    collection_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ─── Documents ─────────────────────────────────────────────
class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_documents_document_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), index=True)  # e.g. ARPI-00001

    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    subtitle: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    author: Mapped[str | None] = mapped_column(String(512), nullable=True)
    authors: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string list
    doc_date: Mapped[str | None] = mapped_column(String(32), nullable=True)  # ISO or partial
    date_precision: Mapped[DatePrecision] = mapped_column(Enum(DatePrecision), default=DatePrecision.unknown)
    publisher: Mapped[str | None] = mapped_column(String(512), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    collection_id: Mapped[int | None] = mapped_column(ForeignKey("archive_collections.id"), nullable=True)

    # Provenance
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    archived_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    archive_provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    archive_snapshot_timestamp: Mapped[str | None] = mapped_column(String(32), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Rights
    rights_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    access_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    copyright_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_only: Mapped[bool] = mapped_column(Boolean, default=False)

    # Processing statuses
    download_status: Mapped[ProcessingStatus] = mapped_column(Enum(ProcessingStatus), default=ProcessingStatus.pending)
    text_extraction_status: Mapped[ProcessingStatus] = mapped_column(Enum(ProcessingStatus), default=ProcessingStatus.pending)
    ocr_status: Mapped[ProcessingStatus] = mapped_column(Enum(ProcessingStatus), default=ProcessingStatus.pending)
    metadata_status: Mapped[ProcessingStatus] = mapped_column(Enum(ProcessingStatus), default=ProcessingStatus.pending)
    index_status: Mapped[ProcessingStatus] = mapped_column(Enum(ProcessingStatus), default=ProcessingStatus.pending)
    embedding_status: Mapped[ProcessingStatus] = mapped_column(Enum(ProcessingStatus), default=ProcessingStatus.pending)

    metadata_source: Mapped[MetadataSource] = mapped_column(Enum(MetadataSource), default=MetadataSource.unknown)
    review_status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.unreviewed)

    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    source: Mapped["Source"] = relationship(back_populates="documents")
    collection: Mapped["ArchiveCollection"] = relationship()
    files: Mapped[list["DocumentFile"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    pages: Mapped[list["DocumentPage"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentFile(Base):
    """A physical file belonging to a logical document. Originals are never
    overwritten; derivatives (ocr/text/thumbnail) are separate rows."""
    __tablename__ = "document_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32))  # original|ocr|text|thumbnail|derived|archived
    local_path: Mapped[str] = mapped_column(String(2048))
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checksum_algo: Mapped[str] = mapped_column(String(16), default="sha256")
    checksum_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped["Document"] = relationship(back_populates="files")


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped["Document"] = relationship(back_populates="versions")


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_number", name="uq_page"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    text_source: Mapped[str | None] = mapped_column(String(32), nullable=True)  # embedded|ocr
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="pages")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # e.g. ARPI-00001-c0007
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(512), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding = mapped_column(Vector(EMBED_DIM), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_dims: Mapped[int | None] = mapped_column(Integer, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")


# ─── Taxonomy, entities, events ────────────────────────────
class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(256))


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(256))


class DocumentTopic(Base):
    __tablename__ = "document_topics"
    __table_args__ = (UniqueConstraint("document_id", "topic_id", name="uq_doc_topic"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)  # matched keyword/snippet
    source: Mapped[MetadataSource] = mapped_column(Enum(MetadataSource), default=MetadataSource.deterministic)


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("entity_type", "name", name="uq_entity"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(512), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    coord_precision: Mapped[str | None] = mapped_column(String(32), nullable=True)  # exact|approximate|unknown
    coord_source: Mapped[str | None] = mapped_column(String(256), nullable=True)


class DocumentEntity(Base):
    __tablename__ = "document_entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mention: Mapped[str | None] = mapped_column(String(512), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[MetadataSource] = mapped_column(Enum(MetadataSource), default=MetadataSource.deterministic)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date_precision: Mapped[DatePrecision] = mapped_column(Enum(DatePrecision), default=DatePrecision.unknown)
    source: Mapped[MetadataSource] = mapped_column(Enum(MetadataSource), default=MetadataSource.ai)  # AI-extracted until verified
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class DocumentEvent(Base):
    __tablename__ = "document_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)


# ─── Citations (audit trail of what AI cited) ──────────────
class Citation(Base):
    __tablename__ = "citations"
    id: Mapped[int] = mapped_column(primary_key=True)
    ai_run_id: Mapped[int | None] = mapped_column(ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    citation_ref: Mapped[str] = mapped_column(String(32))  # c1, c2...
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    chunk_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_note: Mapped[str | None] = mapped_column(String(512), nullable=True)


# ─── Crawl / processing / AI runs ──────────────────────────
class CrawlRun(Base):
    __tablename__ = "crawl_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[ProcessingStatus] = mapped_column(Enum(ProcessingStatus), default=ProcessingStatus.pending)
    seed_urls: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stats: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON report
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list["CrawlItem"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class CrawlItem(Base):
    __tablename__ = "crawl_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(2048))
    normalized_url: Mapped[str | None] = mapped_column(String(2048), nullable=True, index=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(256), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), default="discovered")  # discovered|downloaded|failed|blocked|skipped|duplicate
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped["CrawlRun"] = relationship(back_populates="items")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True)  # crawl|ingest_document|ocr|embed|...
    status: Mapped[ProcessingStatus] = mapped_column(Enum(ProcessingStatus), default=ProcessingStatus.pending)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    result: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON progress counters
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class OcrRun(Base):
    __tablename__ = "ocr_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    engine: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[ProcessingStatus] = mapped_column(Enum(ProcessingStatus), default=ProcessingStatus.pending)
    pages_processed: Mapped[int] = mapped_column(Integer, default=0)
    mean_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiRun(Base):
    __tablename__ = "ai_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), default="ask")  # ask|summary|comparison|...
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reasoning: Mapped[str | None] = mapped_column(String(32), nullable=True)
    retrieval_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)  # keyword|semantic|hybrid
    archive_only: Mapped[bool] = mapped_column(Boolean, default=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)  # supported|partial|insufficient
    documents_retrieved: Mapped[int] = mapped_column(Integer, default=0)
    chunks_retrieved: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ─── AI provider / model registry (persisted) ──────────────
class AiProvider(Base):
    __tablename__ = "ai_providers"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    provider_name: Mapped[str] = mapped_column(String(128))
    adapter: Mapped[str] = mapped_column(String(64))  # openai_compatible|anthropic|local
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Encrypted API key (Fernet). NEVER returned by the API.
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    availability_status: Mapped[str] = mapped_column(String(32), default="unknown")  # unknown|ok|error
    default_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AiModel(Base):
    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("provider_id", "model_id", name="uq_provider_model"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    model_id: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(128))
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_tools: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_structured_output: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_reasoning: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_embeddings: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pricing_info: Mapped[str | None] = mapped_column(String(256), nullable=True)
    availability_status: Mapped[str] = mapped_column(String(32), default="unknown")
    is_embedding: Mapped[bool] = mapped_column(Boolean, default=False)


# ─── App settings (key/value; secret values encrypted) ─────
class AppSetting(Base):
    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ─── Research workspace ────────────────────────────────────
class SavedSearch(Base):
    __tablename__ = "saved_searches"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    query: Mapped[str] = mapped_column(Text)
    filters: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchSession(Base):
    __tablename__ = "research_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON (no API keys)
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retrieval_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchNote(Base):
    __tablename__ = "research_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("research_sessions.id", ondelete="SET NULL"), nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
