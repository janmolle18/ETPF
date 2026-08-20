import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseDocumentProcessor(ABC):
    @abstractmethod
    async def process(self, document_id: uuid.UUID, file_path: str) -> Dict[str, Any]:
        """
        Process the document (Image or PDF) to extract text, layout blocks, and structured fields.
        
        Returns a dict with:
        - raw_text: str
        - layout_data: dict (bounding boxes, layout structure)
        - extracted_data: dict (vendor, total, line items, etc.)
        """
        pass
