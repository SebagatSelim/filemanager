"""Natural-language search (FR-06), folder search and similar-document detection (FR-07)."""
import numpy as np
import sqlalchemy as sa

from ..extensions import db
from ..models import File
from .ai import get_embedder
from .folders import folder_paths, user_folders
from .index import cosine_scores, get_index
from .text import QUERY_STOPWORDS, tokenize

SEMANTIC_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.4
MIN_RELEVANCE = 0.12


def keyword_scores(query_terms: list[str], strong: list[set[str]], weak: list[set[str]]) -> np.ndarray:
    """Share of query words found in each document; title/keyword/folder hits count fully, body hits half."""
    if not query_terms:
        return np.zeros(len(strong), dtype=np.float32)
    terms = set(query_terms)
    scores = np.zeros(len(strong), dtype=np.float32)
    for i, (strong_terms, weak_terms) in enumerate(zip(strong, weak)):
        hit = sum(1.0 if t in strong_terms else 0.5 if t in weak_terms else 0.0 for t in terms)
        scores[i] = hit / len(terms)
    return scores


def search(user_id: int, query: str, limit: int = 10) -> list[tuple[int, float]]:
    """Return [(file_id, relevance 0-1)] for the user's stored documents, best first."""
    embedder = get_embedder()
    index = get_index(user_id, embedder.name)
    if not index.file_ids:
        return []
    terms = tokenize(query, stopwords=QUERY_STOPWORDS)
    semantic = np.clip(cosine_scores(index, embedder.embed_query(query)), 0, 1)
    keyword = keyword_scores(terms, index.strong_terms, index.weak_terms)
    relevance = SEMANTIC_WEIGHT * semantic + KEYWORD_WEIGHT * keyword
    # A document must share at least one word with the query, or be clearly similar in meaning.
    relevant = (keyword > 0) | (semantic >= 0.45)
    order = np.argsort(-relevance)
    results = []
    for i in order:
        if not relevant[i] or relevance[i] < MIN_RELEVANCE:
            continue
        results.append((index.file_ids[i], round(float(min(relevance[i], 1.0)), 4)))
        if len(results) >= limit:
            break
    return results


def search_folders(user_id: int, query: str, document_matches: list[tuple[int, float]],
                   limit: int = 5) -> list[dict]:
    """Folders that match the query (teacher feedback: AI search should also take you to the right folder).

    A folder is shown when the query words are in its name (or its parents' names),
    or when it holds one of the 3 documents that best match the query.
    """
    terms = set(tokenize(query, stopwords=QUERY_STOPWORDS))
    paths = folder_paths(user_id)
    if not paths:
        return []
    rows = db.session.execute(
        sa.select(File.file_id, File.folder_id).where(File.user_id == user_id, File.status == "STORED")
    ).all()
    folder_of = {r.file_id: r.folder_id for r in rows}
    parent_of = {f.folder_id: f.parent_folder_id for f in user_folders(user_id)}
    counts: dict[int, int] = {}  # documents in each folder, including its subfolders
    for folder_id in folder_of.values():
        while folder_id in parent_of:
            counts[folder_id] = counts.get(folder_id, 0) + 1
            folder_id = parent_of[folder_id]

    scores = {}
    if terms:
        for folder_id, path in paths.items():
            own_words = set(tokenize(path[-1]))
            all_words = set(tokenize(" ".join(path)))
            name_score = 0.7 * len(terms & own_words) / len(terms) + 0.3 * len(terms & all_words) / len(terms)
            if name_score >= 0.3:
                scores[folder_id] = name_score
    for file_id, relevance in document_matches[:3]:
        folder_id = folder_of.get(file_id)
        if folder_id in paths:
            scores[folder_id] = scores.get(folder_id, 0.0) + relevance

    best = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [
        {"folder_id": folder_id, "name": paths[folder_id][-1], "path": "/".join(paths[folder_id]),
         "document_count": counts.get(folder_id, 0), "relevance": round(min(score, 1.0), 4)}
        for folder_id, score in best[:limit]
    ]


def find_similar(user_id: int, vector: list[float], model_name: str, exclude_file_id: int,
                 threshold: float, limit: int = 5) -> list[tuple[int, float]]:
    """Documents whose embedding is at least `threshold` cosine-similar to `vector`."""
    index = get_index(user_id, model_name, statuses=("AWAITING_REVIEW", "STORED"))
    if not index.file_ids:
        return []
    scores = cosine_scores(index, vector)
    matches = [
        (fid, round(float(score), 4))
        for fid, score in zip(index.file_ids, scores)
        if fid != exclude_file_id and score >= threshold
    ]
    matches.sort(key=lambda item: item[1], reverse=True)
    return matches[:limit]
