import datetime
import uuid
from typing import Any, Dict, Optional
from sqlalchemy import String, Text, DateTime, JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class DialectJSON(TypeDecorator):
    """Uses JSONB on PostgreSQL, falls back to JSON on SQLite and other backends."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)

    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    layout_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        DialectJSON(), nullable=True
    )

    extracted_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        DialectJSON(), nullable=True
    )

    # timezone=True stores TIMESTAMPTZ on PostgreSQL
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "filename": self.filename,
            "content_type": self.content_type,
            "status": self.status,
            "file_path": self.file_path,
            "raw_text": self.raw_text,
            "layout_data": self.layout_data,
            "extracted_data": self.extracted_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
