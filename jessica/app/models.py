"""Data model — see docs/Jessica_Backend_Proposal.md §4."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB, "postgresql")


def now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # = Supabase auth user id
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="owner")


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    plan: Mapped[str] = mapped_column(String(40), default="free")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(80))
    credits: Mapped[int] = mapped_column(Integer, default=3)  # free first review(s)
    owner: Mapped[User] = relationship(back_populates="workspaces")


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"), index=True)
    anon_id: Mapped[str | None] = mapped_column(String(36), index=True)  # pre-signup owner
    filename: Mapped[str] = mapped_column(String(400))
    mime: Mapped[str] = mapped_column(String(120))
    storage_path: Mapped[str] = mapped_column(String(600))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    clauses: Mapped[list | None] = mapped_column(JSONType)  # [{ref, heading, text}]
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(40), index=True)  # review | ask | draft | purge
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONType)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    perspective: Mapped[str] = mapped_column(String(200))
    grade: Mapped[int | None] = mapped_column(Integer)
    letter: Mapped[str | None] = mapped_column(String(2))
    rubric: Mapped[dict | None] = mapped_column(JSONType)
    issues: Mapped[list | None] = mapped_column(JSONType)
    summary: Mapped[str | None] = mapped_column(Text)
    email_draft: Mapped[str | None] = mapped_column(Text)


class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    role: Mapped[str] = mapped_column(String(12))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSONType)


class Draft(Base, TimestampMixin):
    __tablename__ = "drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    template_id: Mapped[str] = mapped_column(String(80))
    intake: Mapped[dict] = mapped_column(JSONType)
    storage_path: Mapped[str | None] = mapped_column(String(600))


class Matter(Base, TimestampMixin):
    __tablename__ = "matters"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    review_id: Mapped[str | None] = mapped_column(ForeignKey("reviews.id"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new | claimed | done
    assigned_lawyer: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(64), index=True)  # user id or anon id
    action: Mapped[str] = mapped_column(String(40))
    object_type: Mapped[str] = mapped_column(String(40))
    object_id: Mapped[str] = mapped_column(String(36))
    ip: Mapped[str | None] = mapped_column(String(64))


class LLMCall(Base, TimestampMixin):
    __tablename__ = "llm_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str | None] = mapped_column(String(36), index=True)
    purpose: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[int] = mapped_column(Integer, default=1)
