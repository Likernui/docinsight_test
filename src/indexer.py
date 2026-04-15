"""
Модуль индексации: векторизация чанков и построение FAISS-индекса для семантического поиска.
"""

import json
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import faiss


@dataclass
class IndexedChunk:
    """Чанк с информацией о позиции в FAISS-индексе."""
    text: str
    file_path: str
    chunk_index: int
    faiss_id: int
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class Vectorizer:
    """
    Обёртка над sentence-transformers для кодирования текста в эмбеддинги.
    Модель загружается лениво и кэшируется на уровне класса.
    """

    DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
    _model_cache: dict = {}

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str = None):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._embedding_dim = None

    @property
    def model(self):
        if self._model is None:
            if self.model_name in Vectorizer._model_cache:
                self._model = Vectorizer._model_cache[self.model_name]
            else:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, device=self.device)
                Vectorizer._model_cache[self.model_name] = self._model
        return self._model

    @property
    def embedding_dim(self):
        if self._embedding_dim is None:
            self._embedding_dim = self.model.get_sentence_embedding_dimension()
        return self._embedding_dim

    def encode(self, texts: list[str], batch_size: int = 32, show_progress: bool = False) -> np.ndarray:
        embeddings = self.model.encode(
            texts, batch_size=batch_size, show_progress_bar=show_progress,
            convert_to_numpy=True, normalize_embeddings=True
        )
        return embeddings

    def encode_single(self, text: str) -> np.ndarray:
        return self.encode([text])[0]


class VectorIndex:
    """FAISS-индекс для хранения и поиска векторов."""

    def __init__(self, embedding_dim: int):
        self.embedding_dim = embedding_dim
        self.index = faiss.IndexFlatIP(embedding_dim)
        self._id_to_chunk: dict[int, IndexedChunk] = {}
        self._next_id = 0

    @property
    def size(self) -> int:
        return self.index.ntotal

    def add(self, embeddings: np.ndarray, chunks: list) -> list[int]:
        if len(embeddings) == 0:
            return []
        embeddings = np.asarray(embeddings, dtype=np.float32)
        faiss_ids = list(range(self._next_id, self._next_id + len(embeddings)))
        self.index.add(embeddings)
        for fid, chunk in zip(faiss_ids, chunks):
            self._id_to_chunk[fid] = IndexedChunk(
                text=chunk.text, file_path=chunk.file_path,
                chunk_index=chunk.chunk_index, faiss_id=fid,
                metadata=getattr(chunk, 'metadata', {})
            )
        self._next_id += len(embeddings)
        return faiss_ids

    def search(self, query_embedding: np.ndarray, top_k: int = 10):
        query_embedding = np.asarray(query_embedding, dtype=np.float32)
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        scores, indices = self.index.search(query_embedding, min(top_k, self.size))
        scores, indices = scores[0], indices[0]
        chunks = [self._id_to_chunk[fid] for fid in indices if fid >= 0]
        return scores, indices, chunks

    def get_all_chunks(self) -> list[IndexedChunk]:
        return [self._id_to_chunk[i] for i in sorted(self._id_to_chunk.keys())]

    def save(self, directory: str):
        Path(directory).mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(Path(directory) / "faiss.index"))
        mapping = {}
        for fid, chunk in self._id_to_chunk.items():
            mapping[str(fid)] = {"text": chunk.text, "file_path": chunk.file_path,
                                 "chunk_index": chunk.chunk_index, "metadata": chunk.metadata}
        with open(Path(directory) / "id_mapping.json", "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        meta = {"embedding_dim": self.embedding_dim, "size": self.size, "next_id": self._next_id}
        with open(Path(directory) / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, directory: str) -> "VectorIndex":
        d = Path(directory)
        with open(d / "meta.json", "r", encoding="utf-8") as f:
            meta = json.load(f)
        index = cls(embedding_dim=meta["embedding_dim"])
        index.index = faiss.read_index(str(d / "faiss.index"))
        index._next_id = meta["next_id"]
        with open(d / "id_mapping.json", "r", encoding="utf-8") as f:
            mapping = json.load(f)
        for fid_str, data in mapping.items():
            fid = int(fid_str)
            index._id_to_chunk[fid] = IndexedChunk(
                text=data["text"], file_path=data["file_path"],
                chunk_index=data["chunk_index"], faiss_id=fid,
                metadata=data.get("metadata", {}))
        return index


class IndexBuilder:
    """Пайплайн: чанки → векторизация → FAISS."""

    def __init__(self, model_name: str = Vectorizer.DEFAULT_MODEL, device: str = None, batch_size: int = 32):
        self.vectorizer = Vectorizer(model_name=model_name, device=device)
        self.batch_size = batch_size

    def build_from_chunks(self, chunks_dict: dict[str, list], show_progress: bool = False) -> VectorIndex:
        index = VectorIndex(embedding_dim=self.vectorizer.embedding_dim)
        all_texts, all_chunks = [], []
        for fp, chunks in chunks_dict.items():
            for chunk in chunks:
                all_texts.append(chunk.text)
                all_chunks.append(chunk)
        if not all_texts:
            return index
        print(f"Векторизация {len(all_texts)} чанков...")
        embeddings = self.vectorizer.encode(all_texts, batch_size=self.batch_size, show_progress=show_progress)
        index.add(embeddings, all_chunks)
        print(f"Индекс создан: {index.size} векторов, размерность {self.vectorizer.embedding_dim}")
        return index
