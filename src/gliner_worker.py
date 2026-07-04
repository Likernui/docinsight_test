"""
Отдельный процесс для GLiNER.

Если ML-стек аварийно завершится, основной Qt GUI продолжит работать.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.entity import EntityExtractor
from src.preprocessor import TextChunk


def _load_chunks(path: str) -> dict[str, list[TextChunk]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = {}
    for file_path, items in data.items():
        chunks[file_path] = [
            TextChunk(
                text=item["text"],
                file_path=item["file_path"],
                chunk_index=item["chunk_index"],
                metadata=item.get("metadata") or {},
            )
            for item in items
        ]
    return chunks


def _dump_chunks(path: str, chunks: dict[str, list[TextChunk]]) -> None:
    data = {}
    for file_path, items in chunks.items():
        data[file_path] = [
            {
                "text": chunk.text,
                "file_path": chunk.file_path,
                "chunk_index": chunk.chunk_index,
                "metadata": chunk.metadata,
            }
            for chunk in items
        ]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print("Запуск: python -m src.gliner_worker input.json output.json [batch_size]", file=sys.stderr)
        return 2

    batch_size = int(sys.argv[3]) if len(sys.argv) == 4 else 8

    chunks = _load_chunks(sys.argv[1])
    extractor = EntityExtractor()
    enriched = extractor.enrich_chunks_dict(chunks, batch_size=batch_size)
    _dump_chunks(sys.argv[2], enriched)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
