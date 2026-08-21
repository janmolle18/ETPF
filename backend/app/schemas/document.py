import datetime
import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    status: str
    file_path: str
    raw_text: Optional[str] = None
    layout_data: Optional[Dict[str, Any]] = None
    extracted_data: Optional[Dict[str, Any]] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class DocumentUpdate(BaseModel):
    raw_text: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None

