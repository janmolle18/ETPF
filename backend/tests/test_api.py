import io
import uuid
import pytest
from httpx import AsyncClient


async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


async def test_list_documents_empty(client: AsyncClient):
    response = await client.get("/api/v1/documents/")
    assert response.status_code == 200
    assert response.json() == []


async def test_upload_creates_document(client: AsyncClient):
    content = b"fake PNG bytes"
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("receipt.png", io.BytesIO(content), "image/png")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "receipt.png"
    assert data["content_type"] == "image/png"
    assert data["status"] in ("PENDING", "PROCESSING", "COMPLETED")


async def test_upload_appears_in_list(client: AsyncClient):
    content = b"fake PNG bytes"
    await client.post(
        "/api/v1/documents/upload",
        files={"file": ("listed.png", io.BytesIO(content), "image/png")},
    )
    response = await client.get("/api/v1/documents/")
    assert response.status_code == 200
    docs = response.json()
    assert len(docs) >= 1
    assert any(d["filename"] == "listed.png" for d in docs)


async def test_get_document_by_id(client: AsyncClient):
    content = b"fake PNG bytes"
    upload = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("getme.png", io.BytesIO(content), "image/png")},
    )
    doc_id = upload.json()["id"]

    response = await client.get(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 200
    assert response.json()["id"] == doc_id


async def test_get_document_not_found(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/documents/{fake_id}")
    assert response.status_code == 404


async def test_delete_document(client: AsyncClient):
    content = b"fake PNG bytes"
    upload = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("delete_me.png", io.BytesIO(content), "image/png")},
    )
    doc_id = upload.json()["id"]

    delete_response = await client.delete(f"/api/v1/documents/{doc_id}")
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/documents/{doc_id}")
    assert get_response.status_code == 404


async def test_delete_document_not_found(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    response = await client.delete(f"/api/v1/documents/{fake_id}")
    assert response.status_code == 404
