import uuid
from abc import ABC, abstractmethod
from typing import Any, List, Optional
from app.db.models import Document


class BaseDocumentRepository(ABC):
    @abstractmethod
    async def create(self, filename: str, content_type: str, file_path: str) -> Document:
        """Create a new document entry in the database."""
        pass

    @abstractmethod
    async def get_by_id(self, doc_id: uuid.UUID) -> Optional[Document]:
        """Fetch a document by its unique UUID."""
        pass

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> List[Document]:
        """List all documents with optional pagination."""
        pass

    @abstractmethod
    async def update(self, doc_id: uuid.UUID, **kwargs: Any) -> Optional[Document]:
        """Update fields on a document and save changes."""
        pass

    @abstractmethod
    async def delete(self, doc_id: uuid.UUID) -> bool:
        """Delete a document by its UUID."""
        pass
