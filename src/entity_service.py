"""
Сервисный слой для извлечения сущностей.

Здесь собраны выбор чанков, запуск GLiNER worker, объединение результатов
и подготовка строк для пользовательского интерфейса.
"""

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.preprocessor import TextChunk
from src.query_profiles import QueryProfile, get_profiles


PRIORITY_ENTITY_MARKERS = [
    "студент", "студенты", "обучающийся", "автор", "авторы",
    "выполнил", "выполнила", "разработчик", "разработчики",
    "руководитель", "куратор", "преподаватель", "проверил",
    "тема", "название проекта", "дисциплина",
    "группа", "команда", "участник", "участники",
    "список использованной литературы", "список литературы",
    "список источников", "источники", "references", "bibliography",
]

SOURCE_SECTION_MARKERS = [
    "список использованной литературы",
    "список литературы",
    "список источников",
    "references",
    "bibliography",
]


@dataclass
class EntityExtractionResult:
    chunks: dict[str, list[TextChunk]]
    status_suffix: str
    warning: str | None = None
    selected_count: int = 0


class EntityService:
    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(project_root or Path(__file__).resolve().parents[1])

    def extract(
        self,
        chunks: dict[str, list[TextChunk]],
        mode: str = "priority",
        batch_size: int = 8,
        requested_types: list[str] | tuple[str, ...] | None = None,
    ) -> EntityExtractionResult:
        try:
            selected = self.select_chunks(chunks, mode=mode, requested_types=requested_types)
            enriched = self.enrich_chunks_in_subprocess(selected, batch_size=batch_size)
            merged = self.merge_enriched_chunks(chunks, enriched)
            selected_count = self.count_chunks(selected)

            if mode == "priority":
                suffix = f"сущности извлечены из {selected_count} приоритетных чанков, batch={batch_size}"
            elif mode == "search":
                suffix = f"сущности извлечены из результатов поиска: {selected_count} чанков"
            else:
                suffix = f"сущности извлечены полностью, batch={batch_size}"

            return EntityExtractionResult(
                chunks=merged,
                status_suffix=suffix,
                selected_count=selected_count,
            )
        except Exception as e:
            return EntityExtractionResult(
                chunks=chunks,
                status_suffix="без извлечения сущностей",
                warning=str(e),
            )

    def extract_from_search_results(
        self,
        chunks: dict[str, list[TextChunk]],
        search_results: list[Any],
        batch_size: int = 8,
    ) -> EntityExtractionResult:
        selected = self.chunks_from_search_results(chunks, search_results)
        if not selected:
            return EntityExtractionResult(
                chunks=chunks,
                status_suffix="не удалось сопоставить результаты поиска с чанками",
                selected_count=0,
            )

        result = self.extract(selected, mode="search", batch_size=batch_size)
        if result.warning:
            return EntityExtractionResult(
                chunks=chunks,
                status_suffix=result.status_suffix,
                warning=result.warning,
                selected_count=result.selected_count,
            )

        return EntityExtractionResult(
            chunks=self.merge_enriched_chunks(chunks, result.chunks),
            status_suffix=result.status_suffix,
            selected_count=result.selected_count,
        )

    def select_chunks(
        self,
        chunks: dict[str, list[TextChunk]],
        mode: str = "priority",
        requested_types: list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, list[TextChunk]]:
        if mode == "full":
            return chunks

        markers = self.priority_markers(requested_types)
        selected = {}

        for file_path, chunk_list in chunks.items():
            chosen = []
            seen = set()

            for chunk in chunk_list[:3]:
                chosen.append(chunk)
                seen.add(chunk.chunk_index)

            for chunk in chunk_list:
                if chunk.chunk_index in seen:
                    continue

                text_lower = chunk.text.lower()
                if any(marker in text_lower for marker in markers):
                    chosen.append(chunk)
                    seen.add(chunk.chunk_index)

                    if any(marker in text_lower for marker in SOURCE_SECTION_MARKERS):
                        start = chunk.chunk_index + 1
                        end = min(len(chunk_list), chunk.chunk_index + 3)
                        for followup in chunk_list[start:end]:
                            if followup.chunk_index not in seen:
                                chosen.append(followup)
                                seen.add(followup.chunk_index)

            selected[file_path] = chosen

        return selected

    def priority_markers(self, requested_types: list[str] | tuple[str, ...] | None = None) -> list[str]:
        markers = set(PRIORITY_ENTITY_MARKERS)
        profiles = get_profiles(requested_types)

        for profile in profiles:
            markers.update(self.markers_from_profile(profile))

        return sorted(markers)

    def markers_from_profile(self, profile: QueryProfile) -> set[str]:
        markers = set()

        for label in profile.labels:
            markers.add(label.lower())

        return {marker for marker in markers if marker}

    def chunks_from_search_results(
        self,
        chunks: dict[str, list[TextChunk]],
        search_results: list[Any],
    ) -> dict[str, list[TextChunk]]:
        selected = {}
        seen = set()

        for result in search_results:
            key = (result.file_path, result.chunk_index)
            if key in seen:
                continue

            for chunk in chunks.get(result.file_path, []):
                if chunk.chunk_index == result.chunk_index:
                    selected.setdefault(result.file_path, []).append(chunk)
                    seen.add(key)
                    break

        return selected

    def enrich_chunks_in_subprocess(
        self,
        chunks: dict[str, list[TextChunk]],
        batch_size: int = 8,
    ) -> dict[str, list[TextChunk]]:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "chunks.json"
            output_path = Path(tmpdir) / "enriched.json"

            self.write_chunks_json(input_path, chunks)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.gliner_worker",
                    str(input_path),
                    str(output_path),
                    str(batch_size),
                ],
                cwd=self.project_root,
                text=True,
                capture_output=True,
            )

            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                if completed.returncode < 0:
                    signal_number = -completed.returncode
                    detail = f"процесс завершился сигналом {signal_number}. {detail}"
                raise RuntimeError(detail or f"код возврата {completed.returncode}")

            return self.read_chunks_json(output_path)

    def merge_enriched_chunks(
        self,
        original_chunks: dict[str, list[TextChunk]],
        enriched_chunks: dict[str, list[TextChunk]],
    ) -> dict[str, list[TextChunk]]:
        enriched_by_key = {}

        for file_path, chunk_list in enriched_chunks.items():
            for chunk in chunk_list:
                enriched_by_key[(file_path, chunk.chunk_index)] = chunk

        merged = {}
        for file_path, chunk_list in original_chunks.items():
            merged[file_path] = []
            for chunk in chunk_list:
                enriched = enriched_by_key.get((file_path, chunk.chunk_index))
                if enriched is not None:
                    merged[file_path].append(enriched)
                else:
                    chunk.metadata.setdefault("entities", [])
                    merged[file_path].append(chunk)

        return merged

    def enrich_chunks_regex_only(
        self,
        chunks: dict[str, list[TextChunk]],
        include_sources: bool = True,
        source_texts: dict[str, str] | None = None,
    ) -> dict[str, list[TextChunk]]:
        from src.entity import EntityExtractor

        extractor = EntityExtractor(load_model=False)
        enriched = {}

        for file_path, chunk_list in chunks.items():
            enriched[file_path] = []
            source_section_start = extractor.find_source_section_start(chunk_list)

            for index, chunk in enumerate(chunk_list):
                if include_sources:
                    chunk.metadata["entities"] = [
                        entity
                        for entity in chunk.metadata.get("entities", [])
                        if entity.get("label") != "источник"
                    ]

                if include_sources and source_section_start is not None and index >= source_section_start:
                    chunk.metadata.setdefault("entities", [])
                    enriched[file_path].append(chunk)
                    continue

                entities = extractor.extract_regex_entities(
                    chunk.text,
                    bottom_section=False,
                    include_sources=False,
                )
                existing_entities = chunk.metadata.get("entities", [])
                chunk.metadata["entities"] = extractor.normalize_entity_records(
                    extractor.deduplicate_entities(existing_entities + entities),
                    chunk.chunk_index,
                )
                enriched[file_path].append(chunk)

            extractor.attach_title_person_entities(enriched[file_path])

            if include_sources:
                extractor.attach_document_source_block(
                    enriched[file_path],
                    document_text=(source_texts or {}).get(file_path),
                )

        return enriched

    def flatten_entities(self, chunks: dict[str, list[TextChunk]]) -> list[dict[str, Any]]:
        rows_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}

        for file_path, chunk_list in chunks.items():
            document = Path(file_path).name or file_path

            for chunk in chunk_list:
                for entity in chunk.metadata.get("entities", []):
                    row = self.entity_to_row(entity, chunk, document, file_path)
                    if row is None:
                        continue

                    key_value = row["metadata"].get("code") or row["metadata"].get("text") or row["value"]
                    key = (row["type"], str(key_value).strip().lower(), row["document"], row["source"])
                    existing = rows_by_key.get(key)

                    if existing is None:
                        rows_by_key[key] = row
                        continue

                    existing["chunk_indexes"] = sorted(
                        set(existing["chunk_indexes"]) | set(row["chunk_indexes"])
                    )
                    existing["metadata"]["chunk_indexes"] = existing["chunk_indexes"]

                    if row["confidence"] is not None:
                        existing["confidence"] = (
                            row["confidence"]
                            if existing["confidence"] is None
                            else max(existing["confidence"], row["confidence"])
                        )

                    for name in ("source_count", "title", "code", "text"):
                        if name in row["metadata"]:
                            existing["metadata"].setdefault(name, row["metadata"][name])

        return sorted(
            rows_by_key.values(),
            key=lambda row: (row["document"].lower(), row["type"].lower(), row["value"].lower()),
        )

    def entity_to_row(
        self,
        entity: dict[str, Any],
        chunk: TextChunk,
        document: str,
        file_path: str,
    ) -> dict[str, Any] | None:
        label = str(entity.get("label", "")).strip()
        if not label:
            return None

        text = str(entity.get("text", "")).strip()
        title = str(entity.get("title", "")).strip()
        code = str(entity.get("code", "")).strip()

        if label == "фрагмент программного кода":
            value = title or (text.splitlines()[0] if text else "фрагмент кода")
        elif label == "источник":
            value = title or (text.splitlines()[0] if text else "Список источников")
        else:
            value = text

        value = str(value).strip()
        if not value:
            return None

        chunk_indexes = entity.get("chunk_indexes")
        if isinstance(chunk_indexes, list) and chunk_indexes:
            normalized_indexes = sorted({int(index) for index in chunk_indexes})
        else:
            normalized_indexes = [int(chunk.chunk_index)]

        metadata = {
            "document_path": file_path,
            "chunk_indexes": normalized_indexes,
            "section": chunk.metadata.get("section"),
            "start": entity.get("start"),
            "end": entity.get("end"),
        }

        for name, value in (("title", title), ("code", code), ("text", text)):
            if value:
                metadata[name] = value
        if entity.get("source_count") is not None:
            metadata["source_count"] = entity.get("source_count")
        if entity.get("from_title") is not None:
            metadata["from_title"] = bool(entity.get("from_title"))

        score = entity.get("score")
        confidence = float(score) if score is not None else None

        return {
            "type": label,
            "value": value,
            "document": document,
            "chunk_indexes": normalized_indexes,
            "confidence": confidence,
            "source": str(entity.get("source") or "unknown"),
            "metadata": metadata,
        }

    def write_chunks_json(self, path: Path, chunks: dict[str, list[TextChunk]]) -> None:
        data = {}
        for file_path, chunk_list in chunks.items():
            data[file_path] = [
                {
                    "text": chunk.text,
                    "file_path": chunk.file_path,
                    "chunk_index": chunk.chunk_index,
                    "metadata": chunk.metadata,
                }
                for chunk in chunk_list
            ]

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def read_chunks_json(self, path: Path) -> dict[str, list[TextChunk]]:
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

    def count_chunks(self, chunks: dict[str, list[TextChunk]]) -> int:
        return sum(len(items) for items in chunks.values())
