"""Семантический поиск по ChromaDB-коллекции 'brain'."""
from __future__ import annotations

import logging

from bot.config import settings
from rag.embedder import embed_query
from rag.indexer import get_collection

logger = logging.getLogger(__name__)


def search(query: str, top_k: int | None = None) -> list[dict]:
    """Возвращает топ-K чанков, семантически близких к query.

    Каждый элемент: {"text", "source_file", "domain", "title", "distance"}.
    """
    if top_k is None:
        top_k = settings.top_k_results

    collection = get_collection()
    emb = embed_query(query)

    try:
        results = collection.query(
            query_embeddings=[emb],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        logger.exception("ChromaDB query failed")
        return []

    docs = results.get("documents") or [[]]
    metas = results.get("metadatas") or [[]]
    dists = results.get("distances") or [[]]

    hits: list[dict] = []
    for doc, meta, dist in zip(docs[0], metas[0], dists[0]):
        hits.append(
            {
                "text": doc,
                "source_file": meta.get("source_file", ""),
                "domain": meta.get("domain", ""),
                "title": meta.get("title", ""),
                "distance": dist,
            }
        )

    return hits
