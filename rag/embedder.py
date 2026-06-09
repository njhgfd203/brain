"""Ленивый синглтон sentence-transformers модели с e5-префиксами."""
from __future__ import annotations

from typing import TYPE_CHECKING

from bot.config import settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer as _ST

_model: "_ST | None" = None


def get_model() -> "_ST":
    """Лениво загружает модель один раз; возвращает кэшированный экземпляр."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Эмбеддинги для индексации: добавляет префикс 'passage: ' к каждому тексту."""
    model = get_model()
    prefixed = [f"passage: {t}" for t in texts]
    vectors = model.encode(prefixed, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    """Эмбеддинг для поиска: добавляет префикс 'query: '."""
    model = get_model()
    vector = model.encode(f"query: {text}", normalize_embeddings=True)
    return vector.tolist()
