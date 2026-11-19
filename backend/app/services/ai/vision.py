"""Reads the text in photos and scanned PDF pages with OpenAI's vision model.

Used instead of Tesseract OCR when Tesseract is not installed but GPT is switched on
(AI_PROVIDER=openai with an OPENAI_API_KEY), so scans and phone photos still work.
"""
import base64
import io
import logging

from flask import current_app

log = logging.getLogger(__name__)

PROMPT = ("Transcribe all readable text in this document image exactly as written, in reading order. "
          "Keep line breaks. Reply with the text only, no comments. If there is no readable text, reply with nothing.")
MAX_SIDE = 2000  # pixels; larger images cost more and are not read any better


def vision_available() -> bool:
    cfg = current_app.config
    return cfg["AI_PROVIDER"] == "openai" and bool(cfg["OPENAI_API_KEY"])


def _client():
    ext = current_app.extensions
    if "vision_client" not in ext:
        from openai import OpenAI

        ext["vision_client"] = OpenAI(api_key=current_app.config["OPENAI_API_KEY"], timeout=90, max_retries=2)
    return ext["vision_client"]


def _as_data_url(image) -> str:
    from PIL import ImageOps

    img = ImageOps.exif_transpose(image).convert("RGB")
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def read_text(image) -> str:
    """Return the text GPT reads in one image (PIL Image). Raises on API errors."""
    response = _client().chat.completions.create(
        model=current_app.config["OPENAI_MODEL"],
        temperature=0,
        max_tokens=4000,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": _as_data_url(image), "detail": "high"}},
        ]}],
    )
    return response.choices[0].message.content or ""
