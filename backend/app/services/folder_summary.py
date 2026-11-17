"""AI summary of everything inside a folder (reviewer feedback: "summarise any folder contents").

It works offline: it combines the AI metadata we already saved for each document
(category, type, keywords, summary) into a short overview. If OpenAI is switched on,
GPT writes the overview paragraph instead (and we fall back to the offline text if it fails).
"""
import logging
from collections import Counter

from flask import current_app

from ..models import File

log = logging.getLogger(__name__)

MAX_FILES_LISTED = 12


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("bytes", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "bytes" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{num_bytes} bytes"


def _join(words: list[str]) -> str:
    """['a', 'b', 'c'] -> 'a, b and c'"""
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def _offline_overview(folder_name: str, files: list[File], subfolder_count: int,
                      categories: Counter, doc_types: Counter, keywords: list[str]) -> str:
    """Build the overview paragraph from the saved metadata (no AI service needed)."""
    if not files:
        if subfolder_count:
            return f'"{folder_name}" has no documents of its own, only {_plural(subfolder_count, "subfolder")}.'
        return f'"{folder_name}" is empty.'

    file_types = Counter(f.file_type for f in files)
    total_size = sum(int(f.file_size_bytes) for f in files)
    type_text = _join([f"{count} {kind}" for kind, count in file_types.most_common()])
    sentences = [f'"{folder_name}" contains {_plural(len(files), "document")} ({type_text}), {_size(total_size)} in total.']

    top_category, top_count = categories.most_common(1)[0] if categories else ("", 0)
    if top_category:
        share = "All" if top_count == len(files) else "Most" if top_count > len(files) / 2 else "Many"
        types = _join([t for t, _ in doc_types.most_common(3)])
        sentences.append(f"{share} of them are {top_category} documents, mainly {types}.")
    if keywords:
        sentences.append(f"Main topics: {', '.join(keywords[:6])}.")

    dates = sorted(f.uploaded_at for f in files if f.uploaded_at)
    if dates:
        first, last = dates[0].strftime("%d %b %Y"), dates[-1].strftime("%d %b %Y")
        sentences.append(f"Added on {first}." if first == last else f"Added between {first} and {last}.")
    return " ".join(sentences)


def _openai_overview(folder_name: str, files: list[File]) -> str | None:
    """Ask GPT for a 2-3 sentence overview. Returns None if OpenAI is off or fails."""
    config = current_app.config
    if config["AI_PROVIDER"] != "openai" or not config["OPENAI_API_KEY"]:
        return None
    lines = [f"- {f.display_name}: {(f.meta.summary if f.meta else '') or ''}" for f in files[:40]]
    try:
        from openai import OpenAI

        client = OpenAI(api_key=config["OPENAI_API_KEY"], timeout=30, max_retries=0)
        response = client.chat.completions.create(
            model=config["OPENAI_MODEL"],
            temperature=0.3,
            messages=[
                {"role": "system", "content": "Summarise the contents of a folder in 2-3 plain sentences "
                                              "for its owner. Mention the main topics. Do not invent facts."},
                {"role": "user", "content": f"Folder: {folder_name}\nDocuments:\n" + "\n".join(lines)},
            ],
        )
        return (response.choices[0].message.content or "").strip() or None
    except Exception:
        log.warning("OpenAI folder summary failed; using the offline summary.", exc_info=True)
        return None


def summarise_folder(folder_name: str, folder_path: str, files: list[File], subfolder_count: int) -> dict:
    """Return the JSON for GET /api/folders/<id>/summary."""
    categories = Counter(f.meta.category for f in files if f.meta and f.meta.category)
    doc_types = Counter(f.meta.document_type for f in files if f.meta and f.meta.document_type)
    keyword_counts = Counter(k.keyword for f in files for k in f.keywords)
    keywords = [k for k, _ in keyword_counts.most_common(10)]

    overview = None
    if files:
        overview = _openai_overview(folder_name, files)
    source = "openai" if overview else "local"
    if not overview:
        overview = _offline_overview(folder_name, files, subfolder_count, categories, doc_types, keywords)

    return {
        "name": folder_name,
        "path": folder_path,
        "overview": overview,
        "source": source,
        "document_count": len(files),
        "subfolder_count": subfolder_count,
        "total_size_bytes": sum(int(f.file_size_bytes) for f in files),
        "file_types": dict(Counter(f.file_type for f in files).most_common()),
        "categories": [{"category": c, "count": n} for c, n in categories.most_common()],
        "document_types": [{"document_type": t, "count": n} for t, n in doc_types.most_common()],
        "top_keywords": keywords,
        "documents": [
            {"file_id": f.file_id, "name": f.display_name, "title": f.meta.title if f.meta else None,
             "summary": f.meta.summary if f.meta else None, "file_type": f.file_type}
            for f in files[:MAX_FILES_LISTED]
        ],
    }
