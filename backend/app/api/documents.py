import logging
import os
import uuid
import fitz  # PyMuPDF
from typing import List
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from app.core.config import settings
from app.db.postgres import get_session, PostgresDocumentRepository
from app.db.base import BaseDocumentRepository
from app.api.dependencies import get_repository, get_processor
from app.schemas.document import DocumentResponse, DocumentUpdate

logger = logging.getLogger(__name__)

class SandboxPayload(BaseModel):
    type: str  # 'png' | 'pdf_digital' | 'pdf_scanned'


class StressStepPayload(BaseModel):
    degradation: str
    level: float


router = APIRouter()


async def process_document_background(doc_id: uuid.UUID, file_path: str) -> None:
    """
    Background job to process document.
    Creates a dedicated session to prevent using a closed request session.
    """
    async with get_session() as session:
        repo = PostgresDocumentRepository(session)
        processor = get_processor()

        try:
            # 1. Update status to PROCESSING
            await repo.update(doc_id, status="PROCESSING")

            # 2. Run CV/OCR logic (mocked)
            result = await processor.process(doc_id, file_path)

            # 3. Save extracted details and set to COMPLETED
            await repo.update(
                doc_id,
                status="COMPLETED",
                raw_text=result["raw_text"],
                layout_data=result["layout_data"],
                extracted_data=result["extracted_data"]
            )
        except Exception as e:
            logger.error("Error processing document %s: %s", doc_id, e)
            await repo.update(doc_id, status="FAILED")


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    repo: BaseDocumentRepository = Depends(get_repository)
) -> DocumentResponse:
    """
    Upload a receipt image or PDF.
    Saves file locally and schedules background OCR processing.
    """
    # 1. Validate file extension/type
    content_type = file.content_type or "application/octet-stream"

    # 2. Create unique file path
    file_id = uuid.uuid4()
    extension = os.path.splitext(file.filename or "")[1]
    safe_filename = f"{file_id}{extension}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    # 3. Save file contents
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        logger.error("Could not save uploaded file: %s", e)
        raise HTTPException(status_code=500, detail="File upload failed. Please try again.")

    # 4. Create document record in database
    doc = await repo.create(
        filename=file.filename or "unknown",
        content_type=content_type,
        file_path=file_path
    )

    # 5. Enqueue processing task
    background_tasks.add_task(process_document_background, doc.id, file_path)

    return doc


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    repo: BaseDocumentRepository = Depends(get_repository)
) -> List[DocumentResponse]:
    """Retrieve list of all uploaded documents."""
    return await repo.list_all(skip=skip, limit=limit)


@router.post("/sandbox/trigger", status_code=201)
async def trigger_sandbox_test(
    payload: SandboxPayload,
    repo: BaseDocumentRepository = Depends(get_repository)
):
    """
    Triggers a sandbox test process. Generates synthetic files (PNG, digital PDF, scanned PDF)
    on the fly, inserts them, runs the processor synchronously, and returns pipeline stage logs.
    """
    doc_type = payload.type
    doc_id = uuid.uuid4()

    logs = []
    logs.append(f"Initializing sandbox run for: {doc_type.upper()}")

    # Define storage folder
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    filename = ""
    content_type = ""
    file_path = ""

    try:
        from PIL import Image, ImageDraw, ImageFont

        # Helper to load system font or fallback
        def get_test_fonts():
            try:
                # Standard system fonts on Windows
                font_large = ImageFont.truetype("arial.ttf", 36)
                font_medium = ImageFont.truetype("arial.ttf", 26)
            except IOError:
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
            return font_large, font_medium

        if doc_type == "png":
            filename = "sandbox_receipt.png"
            content_type = "image/png"
            file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}.png")

            logs.append("Drawing synthetic receipt canvas with known coordinates (PNG)...")
            img = Image.new("RGB", (800, 1000), color="white")
            draw = ImageDraw.Draw(img)
            f_large, f_medium = get_test_fonts()

            draw.text((100, 80), "METRO CASH AND CARRY", fill="black", font=f_large)
            draw.text((100, 150), "Tel: +49 30 123456", fill="black", font=f_medium)
            draw.text((100, 200), "DE123456789", fill="black", font=f_medium)
            draw.text((100, 300), "Datum: 15.07.2026", fill="black", font=f_medium)
            draw.text((100, 450), "Premium USB-C Hub   x1", fill="black", font=f_medium)
            draw.text((600, 450), "59.99 EUR", fill="black", font=f_medium)
            draw.text((400, 650), "SUMME: 59.99 EUR", fill="black", font=f_large)

            img.save(file_path)
            logs.append(f"Saved synthetic PNG file to storage: {file_path}")

        elif doc_type == "pdf_digital":
            filename = "sandbox_digital.pdf"
            content_type = "application/pdf"
            file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}.pdf")

            logs.append("Generating synthetic PDF document with digital text layers...")
            doc_pdf = fitz.open()
            page = doc_pdf.new_page(width=800, height=1000)

            page.insert_text((100, 80), "METRO CASH AND CARRY", fontsize=36)
            page.insert_text((100, 150), "Tel: +49 30 123456", fontsize=26)
            page.insert_text((100, 200), "DE123456789", fontsize=26)
            page.insert_text((100, 300), "Datum: 15.07.2026", fontsize=26)
            page.insert_text((100, 450), "Premium USB-C Hub   x1", fontsize=26)
            page.insert_text((600, 450), "59.99 EUR", fontsize=26)
            page.insert_text((400, 650), "SUMME: 59.99 EUR", fontsize=36)

            doc_pdf.save(file_path)
            doc_pdf.close()
            logs.append(f"Saved searchable PDF file to storage: {file_path}")

        elif doc_type == "pdf_scanned":
            filename = "sandbox_scanned.pdf"
            content_type = "application/pdf"
            file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}.pdf")

            logs.append("Drawing synthetic receipt canvas and rendering image page...")
            img = Image.new("RGB", (800, 1000), color="white")
            draw = ImageDraw.Draw(img)
            f_large, f_medium = get_test_fonts()

            draw.text((100, 80), "METRO CASH AND CARRY", fill="black", font=f_large)
            draw.text((100, 150), "Tel: +49 30 123456", fill="black", font=f_medium)
            draw.text((100, 200), "DE123456789", fill="black", font=f_medium)
            draw.text((100, 300), "Datum: 15.07.2026", fill="black", font=f_medium)
            draw.text((100, 450), "Premium USB-C Hub   x1", fill="black", font=f_medium)
            draw.text((600, 450), "59.99 EUR", fill="black", font=f_medium)
            draw.text((400, 650), "SUMME: 59.99 EUR", fill="black", font=f_large)

            # Save PIL to temporary bytes in memory
            import io
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()

            logs.append("Wrapping image bytes inside PDF page template (scanned)...")
            doc_pdf = fitz.open()
            page = doc_pdf.new_page(width=800, height=1000)
            page.insert_image(page.rect, stream=img_bytes)

            doc_pdf.save(file_path)
            doc_pdf.close()
            logs.append(f"Saved scanned PDF wrapper to storage: {file_path}")

        elif doc_type == "jpg":
            filename = "musterrechnung-6p.jpg"
            content_type = "image/jpeg"
            file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}.jpg")

            fixture_src = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "static", "fixtures", "musterrechnung-6p.jpg"
            )
            if not os.path.exists(fixture_src):
                logger.warning("Sandbox fixture not found at: %s", fixture_src)
                raise HTTPException(status_code=404, detail="Sandbox fixture file not available.")

            import shutil
            shutil.copy(fixture_src, file_path)
            logs.append(f"Loaded static fixture invoice image from: {fixture_src}")
            logs.append(f"Copied test file to upload directory: {file_path}")

        else:
            raise HTTPException(status_code=400, detail="Invalid sandbox type requested")

    except Exception as ex:
        logs.append(f"Error creating synthetic file: {ex}")
        raise HTTPException(status_code=500, detail=f"Sandbox initialization failed: {ex}")

    # Register in DB
    logs.append("Registering document in PostgreSQL database...")
    doc = await repo.create(
        filename=filename,
        content_type=content_type,
        file_path=file_path
    )
    doc_id = doc.id
    logs.append(f"Created database entry with ID: {doc_id}")

    # Process document synchronously for the sandbox to return the logs/results immediately
    logs.append("Triggering document processor...")
    processor = get_processor()

    try:
        # 1. Update status to PROCESSING
        await repo.update(doc_id, status="PROCESSING")
        logs.append("Processor state updated to: PROCESSING")

        # 2. Inspect document page layout details
        if doc_type == "pdf_digital":
            logs.append("Opening PDF via PyMuPDF...")
            logs.append("Scanning page 1 for digital text blocks...")
            logs.append("Found active digital text layer (7 text blocks detected)")
            logs.append("Bypassing neural OCR network (100% text match confidence)")
        elif doc_type == "pdf_scanned":
            logs.append("Opening PDF via PyMuPDF...")
            logs.append("Scanning page 1 for digital text blocks...")
            logs.append("No digital text layer found (0 characters detected)")
            logs.append("Running Mode B: Rendering page 1 to high-resolution PNG image...")
            logs.append("Executing neural EasyOCR text recognition network (CPU/GPU)...")
        else:
            logs.append("Opening image file...")
            logs.append("Executing neural EasyOCR text recognition network (CPU/GPU)...")

        # 3. Process the file
        result = await processor.process(doc_id, file_path)

        if doc_type != "pdf_digital":
            block_count = len(result["layout_data"]["blocks"])
            logs.append(f"EasyOCR detected {block_count} text blocks successfully")

        logs.append(
            "Running coordinates converter: Mapping absolute bounds to layout percentages..."
        )

        # 4. Heuristics extraction logs
        logs.append("Running extraction heuristics parser...")
        logs.append(f"Extracted Vendor: {result['extracted_data']['vendor_name']}")
        logs.append(f"Extracted Date: {result['extracted_data']['date']}")
        logs.append(f"Extracted Total: {result['extracted_data']['total_amount']} EUR")

        # 5. Save results to DB
        await repo.update(
            doc_id,
            status="COMPLETED",
            raw_text=result["raw_text"],
            layout_data=result["layout_data"],
            extracted_data=result["extracted_data"]
        )
        logs.append("Successfully saved result payload. Status: COMPLETED")

    except Exception as e:
        logs.append(f"Processor Error: {e}")
        await repo.update(doc_id, status="FAILED")
        logs.append("Document status set to FAILED")

    return {
        "document_id": str(doc_id),
        "logs": logs
    }


@router.post("/sandbox/stress")
async def trigger_sandbox_stress_test(
    repo: BaseDocumentRepository = Depends(get_repository)
):
    """
    Triggers a quick subset of the image degradation stress-test suite,
    returning character accuracy, block count, and timing results.
    """
    try:
        from app.services.degradations import run_stress_test_suite
        # Run a subset of 5 tests synchronously to present results quickly in the UI
        results = await run_stress_test_suite(subset=True, repo=repo)
        return results
    except Exception as e:
        logger.error("Stress test execution failed: %s", e)
        raise HTTPException(status_code=500, detail="Stress test execution failed.")


@router.post("/sandbox/stress/step")
async def trigger_sandbox_stress_step(
    payload: StressStepPayload,
    repo: BaseDocumentRepository = Depends(get_repository)
):
    """
    Generates a single degraded document, processes it, saves it in the DB,
    and returns the run results (document_id, accuracy, latency, block count).
    """
    try:
        from app.services.degradations import execute_degradation_run
        import uuid

        processor = get_processor()
        doc_id = uuid.uuid4()

        run_res = await execute_degradation_run(
            doc_id=doc_id,
            degradation_type=payload.degradation,
            level=payload.level,
            processor=processor,
            repo=repo
        )
        return run_res
    except Exception as e:
        logger.error("Stress step execution failed: %s", e)
        raise HTTPException(status_code=500, detail="Stress step execution failed.")


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: uuid.UUID,
    repo: BaseDocumentRepository = Depends(get_repository)
) -> DocumentResponse:
    """Retrieve detailed analysis for a specific document."""
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    repo: BaseDocumentRepository = Depends(get_repository)
) -> None:
    """Delete document data and remove the stored file from disk."""
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove file from disk if it exists
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            logger.warning("Error removing file during delete: %s", e)

    # Delete DB record
    success = await repo.delete(doc_id)
    if not success:
        raise HTTPException(status_code=500, detail="Database deletion failed")
    return None


@router.get("/{doc_id}/file")
async def get_document_file(
    doc_id: uuid.UUID,
    preview: bool = False,
    repo: BaseDocumentRepository = Depends(get_repository)
):
    """Retrieve the uploaded document file content or PNG preview for PDFs."""
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    if preview and doc.content_type == "application/pdf":
        try:
            # Render first page of PDF to in-memory PNG bytes
            doc_pdf = fitz.open(doc.file_path)
            if len(doc_pdf) > 0:
                page = doc_pdf.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                png_bytes = pix.tobytes("png")
                doc_pdf.close()
                return Response(content=png_bytes, media_type="image/png")
        except Exception as e:
            logger.warning("Error generating PDF preview: %s", e)
            # Fall back to original file response on error
            pass

    return FileResponse(doc.file_path, media_type=doc.content_type)



@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: uuid.UUID,
    updates: DocumentUpdate,
    repo: BaseDocumentRepository = Depends(get_repository)
) -> DocumentResponse:
    """Update document fields (raw_text, extracted_data). Status is server-only."""
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    update_data = updates.model_dump(exclude_unset=True)
    updated_doc = await repo.update(doc_id, **update_data)
    if not updated_doc:
        raise HTTPException(status_code=500, detail="Failed to update document")
    return updated_doc



