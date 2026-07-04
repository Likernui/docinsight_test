"""
Модуль семантического поиска по FAISS-индексу.
"""

from dataclasses import dataclass


@dataclass
class SearchResult:
    """Результат одного семантического запроса."""
    text: str
    file_path: str
    chunk_index: int
    score: float
    faiss_id: int | None = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def __repr__(self):
        preview = self.text[:60].replace('\n', ' ')
        return f"SearchResult(score={self.score:.3f}, file={self.file_path}, preview='{preview}...')"


class SemanticSearch:
    """Семантический поиск по FAISS-индексу."""

    def __init__(self, index, vectorizer):
        self.index = index
        self.vectorizer = vectorizer

    def search(self, query: str, top_k: int = 5, min_score: float = 0.0) -> list[SearchResult]:
        query_embedding = self.vectorizer.encode_single(query)
        scores, faiss_ids, chunks = self.index.search(query_embedding, top_k)
        results = []
        for score, faiss_id, chunk in zip(scores, faiss_ids, chunks):
            if score >= min_score:
                results.append(SearchResult(
                    text=chunk.text, file_path=chunk.file_path,
                    chunk_index=chunk.chunk_index, score=float(score), faiss_id=int(faiss_id),
                    metadata=chunk.metadata))
        return results
