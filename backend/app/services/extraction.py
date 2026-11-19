"""Text extraction (FR-09): PyMuPDF, python-docx, OCR and plain text.

OCR for photos and scanned PDF pages uses Tesseract when it is installed, otherwise GPT vision
when OpenAI is switched on (services/ai/vision.py).
"""
import io
import logging
from functools import lru_cache

from flask import current_app

from .text import clean_text

log = logging.getLogger(__name__)

MIN_PAGE_TEXT = 25  # characters; below this a PDF page is treated as scanned
VISION_MAX_PAGES = 10  # GPT vision reads at most this many scanned pages per PDF (time and cost)


class ExtractionError(Exception):
    """Raised when no usable text can be produced. The message is shown to the user."""


@lru_cache(maxsize=4)
def _ocr_available(tesseract_cmd: str) -> bool:
    try:
        import pytesseract

        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def tesseract_available() -> bool:
    return _ocr_available(current_app.config.get("TESSERACT_CMD", ""))


def ocr_provider() -> str | None:
    """Who reads text from images and scans: 'tesseract', 'openai' (GPT vision) or None."""
    from .ai.vision import vision_available

    if tesseract_available():
        return "tesseract"
    if vision_available():
        return "openai"
    return None


def ocr_available() -> bool:
    return ocr_provider() is not None


def _read_image_text(image, provider: str) -> str:
    """OCR one image with Tesseract or GPT vision. Raises ExtractionError if GPT can't be reached."""
    if provider == "tesseract":
        return _ocr_image(image)
    from .ai.vision import read_text

    try:
        return read_text(image)
    except Exception as exc:
        log.warning("GPT vision could not read the image: %s", exc)
        raise ExtractionError("The text in this image couldn't be read right now (the AI service didn't answer). "
                              "Please retry in a minute.") from exc


METHOD_FOR = {"tesseract": "TESSERACT_OCR", "openai": "OPENAI_VISION"}


def _prepare_for_ocr(image):
    """Basic pre-processing to help Tesseract with phone photos and faint scans (risk R2)."""
    from PIL import ImageOps

    img = ImageOps.exif_transpose(image).convert("L")
    if img.width < 1200:
        scale = 1200 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    return ImageOps.autocontrast(img)


def _ocr_image(image) -> str:
    import pytesseract

    return pytesseract.image_to_string(_prepare_for_ocr(image))


def _extract_pdf(data: bytes) -> tuple[str, str]:
    import pymupdf as fitz
    from PIL import Image

    max_pages = current_app.config.get("MAX_PDF_PAGES", 50)
    provider = ocr_provider()
    can_ocr = provider is not None
    parts, ocr_pages, text_pages = [], 0, 0
    with fitz.open(stream=data, filetype="pdf") as pdf:
        for index, page in enumerate(pdf):
            if index >= max_pages:
                break
            text = page.get_text("text") or ""
            if len(text.strip()) >= MIN_PAGE_TEXT:
                parts.append(text)
                text_pages += 1
            elif can_ocr and (provider != "openai" or ocr_pages < VISION_MAX_PAGES):
                pix = page.get_pixmap(dpi=200)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                parts.append(_read_image_text(image, provider))
                ocr_pages += 1
            else:
                parts.append(text)
    text = clean_text("\n\n".join(parts))
    if not text and not can_ocr:
        raise ExtractionError(
            "This PDF looks scanned (no text layer) and OCR is not installed on the server. "
            "Install Tesseract to read scanned documents, or enter the details manually."
        )
    method = METHOD_FOR[provider] if ocr_pages > text_pages else "PYMUPDF"
    return text, method


def _extract_docx(data: bytes) -> tuple[str, str]:
    import docx

    document = docx.Document(io.BytesIO(data))
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(dict.fromkeys(cells)))  # merged cells repeat their text
    return clean_text("\n".join(parts)), "PYTHON_DOCX"


def _extract_txt(data: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return clean_text(data.decode(encoding)), "PLAIN_TEXT"
        except UnicodeDecodeError:
            continue
    raise ExtractionError("The text file uses an unsupported encoding.")


def _extract_image(data: bytes) -> tuple[str, str]:
    from PIL import Image

    provider = ocr_provider()
    if provider is None:
        raise ExtractionError(
            "OCR is not installed on the server, so text can't be read from images. "
            "Install Tesseract (see backend/README.md), or enter the details manually."
        )
    with Image.open(io.BytesIO(data)) as image:
        return clean_text(_read_image_text(image, provider)), METHOD_FOR[provider]


_EXTRACTORS = {"PDF": _extract_pdf, "DOCX": _extract_docx, "TXT": _extract_txt, "PNG": _extract_image, "JPG": _extract_image}


def extract_text(data: bytes, file_type: str) -> tuple[str, str]:
    """Return (text, extraction_method). Raises ExtractionError with a user-friendly message."""
    try:
        return _EXTRACTORS[file_type](data)
    except ExtractionError:
        raise
    except Exception as exc:
        log.exception("Extraction failed for %s", file_type)
        raise ExtractionError("The document could not be read. It may be corrupted.") from exc
