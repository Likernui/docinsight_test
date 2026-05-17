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

    def search_across_files(self, query: str, top_k: int = 10, per_file: int = 3, min_score: float = 0.0) -> dict:
        all_results = self.search(query, top_k=top_k * 2, min_score=min_score)
        grouped: dict[str, list[SearchResult]] = {}
        for result in all_results:
            if len(grouped.get(result.file_path, [])) < per_file:
                grouped.setdefault(result.file_path, []).append(result)
            if sum(len(v) for v in grouped.values()) >= top_k:
                break
        return grouped

    def get_context(self, result: SearchResult, before: int = 1, after: int = 1) -> list[SearchResult]:
        file_chunks = [c for c in self.index.get_all_chunks() if c.file_path == result.file_path]
        file_chunks.sort(key=lambda c: c.chunk_index)
        idx = next((i for i, c in enumerate(file_chunks) if c.faiss_id == result.faiss_id), None)
        if idx is None:
            return []
        start, end = max(0, idx - before), min(len(file_chunks), idx + after + 1)
        context = []
        for i in range(start, end):
            chunk = file_chunks[i]
            context.append(SearchResult(
                text=chunk.text, file_path=chunk.file_path,
                chunk_index=chunk.chunk_index, score=1.0 if i == idx else 0.0,
                metadata=chunk.metadata))
        return context
