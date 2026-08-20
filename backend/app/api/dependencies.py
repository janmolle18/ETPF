from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_session, PostgresDocumentRepository
from app.db.base import BaseDocumentRepository
from app.services.base import BaseDocumentProcessor
from app.services.easyocr_processor import EasyOCRDocumentProcessor


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to yield an async database session."""
    async with get_session() as session:
        yield session


def get_repository(session: AsyncSession = Depends(get_db)) -> BaseDocumentRepository:
    """Dependency to resolve the active document repository (adapter pattern)."""
    return PostgresDocumentRepository(session)


def get_processor() -> BaseDocumentProcessor:
    """Dependency to resolve the active document CV/OCR processor."""
    return EasyOCRDocumentProcessor()
