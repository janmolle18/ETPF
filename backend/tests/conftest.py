import os
import uuid
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.models import Base
from app.api.dependencies import get_db, get_processor
from app.services.mock_processor import MockDocumentProcessor
from app.core.config import settings
import app.db.postgres as _pg


class InstantMockProcessor(MockDocumentProcessor):
    """MockProcessor without the 3-second sleep for fast test execution."""

    async def process(self, document_id: uuid.UUID, file_path: str):
        return {
            "raw_text": "METRO CASH AND CARRY\nDatum: 15.07.2026\nSUMME: 59.99 EUR",
            "layout_data": {"width": 800, "height": 1200, "blocks": []},
            "extracted_data": {
                "vendor_name": "METRO CASH AND CARRY",
                "tax_id": "DE123456789",
                "phone": "+49 30 123456",
                "date": "2026-07-15",
                "total_amount": 59.99,
                "tax_amount": 9.58,
                "currency": "EUR",
                "line_items": [],
            },
        }


@pytest.fixture
def db_engine():
    """Fresh in-memory SQLite engine per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    return engine


@pytest_asyncio.fixture
async def client(db_engine, tmp_path, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP test client backed by:
    - in-memory SQLite (no PostgreSQL required)
    - InstantMockProcessor (no EasyOCR/torch required)
    - tmp_path as UPLOAD_DIR
    """
    # Create tables
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    def _test_get_session():
        return TestSession()

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(_pg, "async_engine", db_engine)
    monkeypatch.setattr(_pg, "AsyncSessionLocal", TestSession)

    from app.main import app

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_processor] = InstantMockProcessor

    with patch("app.api.documents.get_session", _test_get_session), \
         patch("app.api.documents.get_processor", InstantMockProcessor):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

    app.dependency_overrides.clear()

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db_engine.dispose()
