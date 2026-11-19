"""OCR with GPT vision when Tesseract isn't installed (the OpenAI call is faked: no network)."""
import io

import pytest
from PIL import Image

from app.services import extraction
from app.services.ai import vision
from app.services.ai.local import LocalAnalyzer
from conftest import upload

RECEIPT = ("TAX INVOICE - Officeworks Footscray\nDate: 02/11/2026\nA4 notebooks x3 $12.00\n"
           "USB-C cable $19.00\nTotal $31.00 paid by card. Keep this receipt for returns.")


@pytest.fixture
def gpt_vision(client, monkeypatch):
    """Switch the app to OpenAI without Tesseract; GPT 'reads' RECEIPT from every image."""
    app = client.application
    app.config.update(AI_PROVIDER="openai", OPENAI_API_KEY="test-key")
    app.extensions["analyzer"] = LocalAnalyzer()  # keep the analysis itself offline
    monkeypatch.setattr(extraction, "tesseract_available", lambda: False)
    seen = []
    monkeypatch.setattr(vision, "read_text", lambda image: seen.append(image.size) or RECEIPT)
    return seen


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def scanned_pdf(pages: int) -> bytes:
    import pymupdf

    pdf = pymupdf.open()
    for _ in range(pages):
        pdf.new_page().insert_image(pymupdf.Rect(0, 0, 200, 150), stream=png())  # image only, no text layer
    return pdf.tobytes()


def test_photo_is_read_by_gpt_vision(client, auth, gpt_vision):
    file_id = upload(client, auth, "receipt.png", png()).get_json()["file_id"]
    analysis = client.get(f"/api/documents/{file_id}/analysis", headers=auth).get_json()
    assert analysis["status"] == "AWAITING_REVIEW"
    assert analysis["suggestions"]["category"] == "Finance"
    doc = client.get(f"/api/documents/{file_id}", headers=auth).get_json()
    assert doc["extraction_method"] == "OPENAI_VISION"
    assert len(gpt_vision) == 1


def test_scanned_pdf_pages_are_read_by_gpt_vision(client, auth, gpt_vision):
    file_id = upload(client, auth, "scan.pdf", scanned_pdf(2)).get_json()["file_id"]
    doc = client.get(f"/api/documents/{file_id}", headers=auth).get_json()
    assert doc["status"] == "AWAITING_REVIEW" and doc["extraction_method"] == "OPENAI_VISION"
    assert len(gpt_vision) == 2


def test_gpt_vision_reads_at_most_the_page_limit(client, auth, gpt_vision, monkeypatch):
    monkeypatch.setattr(extraction, "VISION_MAX_PAGES", 2)
    upload(client, auth, "long_scan.pdf", scanned_pdf(4))
    assert len(gpt_vision) == 2


def test_vision_error_gives_a_retry_message(client, auth, gpt_vision, monkeypatch):
    def down(image):
        raise RuntimeError("timeout")

    monkeypatch.setattr(vision, "read_text", down)
    file_id = upload(client, auth, "receipt.png", png()).get_json()["file_id"]
    analysis = client.get(f"/api/documents/{file_id}/analysis", headers=auth).get_json()
    assert analysis["status"] == "FAILED" and "retry" in analysis["error_message"]


def test_health_reports_who_does_ocr(client, gpt_vision):
    data = client.get("/api/health").get_json()
    assert data["ocr_available"] is True and data["ocr_provider"] == "openai"


def test_no_ocr_without_tesseract_or_openai(client, monkeypatch):
    monkeypatch.setattr(extraction, "tesseract_available", lambda: False)
    data = client.get("/api/health").get_json()
    assert data["ocr_available"] is False and data["ocr_provider"] is None
