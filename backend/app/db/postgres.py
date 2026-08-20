import logging
import uuid
from typing import Any, List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings
from app.db.models import Base, Document
from app.db.base import BaseDocumentRepository

logger = logging.getLogger(__name__)

# Create asynchronous engine and sessionmaker
async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def get_session() -> AsyncSession:
    """Return a new session instance from the current sessionmaker."""
    return AsyncSessionLocal()


async def init_db() -> None:
    """Initialize the database. Falls back to SQLite if Postgres is unavailable."""
    global async_engine, AsyncSessionLocal
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Connected to PostgreSQL successfully.")
    except Exception as e:
        logger.warning(
            "PostgreSQL connection failed (%s). Falling back to SQLite (etpf.db).", e
        )
        sqlite_url = "sqlite+aiosqlite:///etpf.db"
        async_engine = create_async_engine(sqlite_url, echo=False)
        AsyncSessionLocal = async_sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.warning("SQLite database active at etpf.db — not for production.")


class PostgresDocumentRepository(BaseDocumentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, filename: str, content_type: str, file_path: str) -> Document:
        doc = Document(
            filename=filename,
            content_type=content_type,
            file_path=file_path,
            status="PENDING"
        )
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def get_by_id(self, doc_id: uuid.UUID) -> Optional[Document]:
        result = await self.session.execute(
            select(Document).where(Document.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 100) -> List[Document]:
        result = await self.session.execute(
            select(Document)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, doc_id: uuid.UUID, **kwargs: Any) -> Optional[Document]:
        doc = await self.get_by_id(doc_id)
        if not doc:
            return None
        
        for key, value in kwargs.items():
            if hasattr(doc, key):
                setattr(doc, key, value)
                
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def delete(self, doc_id: uuid.UUID) -> bool:
        doc = await self.get_by_id(doc_id)
        if not doc:
            return False
            
        await self.session.delete(doc)
        await self.session.commit()
        return True
