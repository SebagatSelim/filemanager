"""AI folder recommendation (teacher feedback: "suggest which EXISTING folder the uploaded file should go in").

For a newly analysed document we give every folder the user already has a score from 0 to 1:

  score = 0.40 x similar documents   documents already in that folder that look like this one
        + 0.35 x folder name match   folder name words found in the title, subject, keywords or category
        + 0.25 x AI path match       the folder is the AI's folder, has the same name, or is a parent of it

The AI analyser can also suggest a brand-new folder path. That option gets a fixed score
(NEW_FOLDER_SCORE), so an existing folder is recommended first whenever it fits at least that well.
The best 3 options are returned with a short reason the user can read.
"""
import re

import numpy as np
import sqlalchemy as sa

from ..extensions import db
from ..models import File
from .ai import get_embedder
from .folders import clean_segments, folder_paths
from .index import cosine_scores, get_index
from .text import tokenize

SIMILAR_WEIGHT, NAME_WEIGHT, AI_PATH_WEIGHT = 0.40, 0.35, 0.25
NEW_FOLDER_SCORE = 0.45   # an existing folder must score at least this to beat a new AI folder
MIN_SCORE = 0.15          # folders below this are not worth showing
MIN_SIMILARITY = 0.25     # a stored document counts as "similar" from this cosine similarity


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _document_words(file: File) -> set[str]:
    meta = file.meta
    parts = [file.original_name.rsplit(".", 1)[0].replace("_", " ")]
    if meta is not None:
        parts += [meta.title or "", meta.subject or "", meta.category or "", meta.document_type or ""]
    parts += [k.keyword for k in file.keywords]
    return set(tokenize(" ".join(parts)))


def _name_score(path: list[str], words: set[str]) -> tuple[float, list[str]]:
    """How many words of the folder's own name (and, less, of its parents) appear in the document."""
    own = tokenize(path[-1])
    parents = tokenize(" ".join(path[:-1]))
    own_hits = [w for w in own if w in words]
    parent_hits = [w for w in parents if w in words]
    own_share = len(own_hits) / len(own) if own else 0.0
    parent_share = len(parent_hits) / len(parents) if parents else own_share
    return 0.7 * own_share + 0.3 * parent_share, own_hits or parent_hits


def _ai_path_score(path: list[str], ai_path: list[str]) -> float:
    """1 = the folder IS the AI's path, 0.8 = same top folder and same folder name at a different depth
    (e.g. an existing "University/.../Semester 1/Database Systems" for the AI's "University/Database Systems"),
    partial credit = a parent folder of the AI's path."""
    keys, ai_keys = [_key(p) for p in path], [_key(p) for p in ai_path]
    if not ai_keys:
        return 0.0
    if keys == ai_keys:
        return 1.0
    if len(ai_keys) > 1 and len(keys) > 1 and keys[0] == ai_keys[0] and keys[-1] == ai_keys[-1]:
        return 0.8
    if len(keys) < len(ai_keys) and ai_keys[:len(keys)] == keys:
        return 0.6 * len(keys) / len(ai_keys)
    return 0.0


def _similar_documents_by_folder(file: File) -> dict[int, list[tuple[float, str]]]:
    """folder_id -> [(similarity, document name)] for stored documents that look like this file."""
    if file.embedding is None:
        return {}
    index = get_index(file.user_id, get_embedder().name)
    if not index.file_ids:
        return {}
    scores = cosine_scores(index, file.embedding.embedding)
    rows = db.session.execute(
        sa.select(File.file_id, File.folder_id, File.generated_name, File.original_name)
        .where(File.user_id == file.user_id, File.status == "STORED")
    ).all()
    info = {r.file_id: (r.folder_id, r.generated_name or r.original_name) for r in rows}
    result: dict[int, list[tuple[float, str]]] = {}
    for i in np.argsort(-scores)[:20]:  # the 20 most similar documents are plenty
        file_id, similarity = index.file_ids[i], float(scores[i])
        if file_id == file.file_id or similarity < MIN_SIMILARITY or file_id not in info:
            continue
        folder_id, name = info[file_id]
        if folder_id is not None:
            result.setdefault(folder_id, []).append((similarity, name))
    return result


def recommend_folders(file: File, limit: int = 3) -> list[dict]:
    """Best folders for this document, best first:
    [{folder_id, path, score, reason, is_new}]   (folder_id is None for a new folder)."""
    meta = file.meta
    ai_path = clean_segments(meta.suggested_folder_path or "") if meta is not None else []
    paths = folder_paths(file.user_id)
    words = _document_words(file)
    similar = _similar_documents_by_folder(file)

    options = []
    for folder_id, path in paths.items():
        matches = sorted(similar.get(folder_id, []), reverse=True)
        # Cosine similarities of related documents are usually 0.25-0.5, so x2 turns them into a 0-1 score.
        similar_score = min(1.0, matches[0][0] * 2) if matches else 0.0
        name_score, name_hits = _name_score(path, words)
        ai_score = _ai_path_score(path, ai_path)
        score = SIMILAR_WEIGHT * similar_score + NAME_WEIGHT * name_score + AI_PATH_WEIGHT * ai_score
        if score < MIN_SCORE:
            continue
        if matches:
            count = len(matches)
            reason = (f'{count} similar document{"s are" if count > 1 else " is"} already here, '
                      f'e.g. "{matches[0][1]}"')
        elif ai_score >= 0.8:
            reason = "Matches the folder the AI chose from the document's content"
        elif name_hits:
            reason = "Folder name matches the document: " + ", ".join(sorted(set(name_hits)))
        else:
            reason = "Part of the folder path the AI suggested"
        options.append({"folder_id": folder_id, "path": path, "score": round(min(score, 1.0), 4),
                        "reason": reason, "is_new": False})

    ai_exists = any([_key(p) for p in path] == [_key(p) for p in ai_path] for path in paths.values())
    if ai_path and not ai_exists:
        options.append({"folder_id": None, "path": ai_path, "score": NEW_FOLDER_SCORE,
                        "reason": "New folder suggested by the AI from the document's content", "is_new": True})

    options.sort(key=lambda o: (o["score"], not o["is_new"]), reverse=True)
    return options[:limit]
