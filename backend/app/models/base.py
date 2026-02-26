import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class RunStatus(str, enum.Enum):
    pending = "pending"
    ingesting = "ingesting"
    analyzing = "analyzing"
    capturing = "capturing"
    generating = "generating"
    completed = "completed"
    failed = "failed"


class DraftStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    github_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    github_username: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    runs: Mapped[list["Run"]] = relationship(back_populates="user")
    drafts: Mapped[list["Draft"]] = relationship(back_populates="user")
    tokens: Mapped[list["Token"]] = relationship(back_populates="user")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    repo_url: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status", native_enum=False),
        default=RunStatus.pending,
        server_default="pending",
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    screenshots: Mapped[list | None] = mapped_column(JSON, nullable=True)
    post_draft: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="runs")
    drafts: Mapped[list["Draft"]] = relationship(back_populates="run")


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String, default="linkedin", server_default="linkedin")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    first_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_urls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    alt_texts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[DraftStatus] = mapped_column(
        Enum(DraftStatus, name="draft_status", native_enum=False),
        default=DraftStatus.draft,
        server_default="draft",
    )
    published_url: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    run: Mapped["Run"] = relationship(back_populates="drafts")
    user: Mapped["User"] = relationship(back_populates="drafts")


class Token(Base):
    __tablename__ = "tokens"
    __table_args__ = (UniqueConstraint("user_id", "platform", name="uq_tokens_user_platform"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String, nullable=False)
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="tokens")
