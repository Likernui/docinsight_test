"""
Высокоуровневый пайплайн обработки документов.

GUI вызывает этот модуль одним методом, а внутренние этапы остаются
скрытыми от пользовательского интерфейса.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.entity_service import EntityService
from src.indexer import IndexBuilder
from src.preprocessor import TextChunk, TextPreprocessor
from src.query_profiles import QueryProfile, get_profiles
from src.semantic_search import SearchResult, SemanticSearch
from src.text_extractor import DocumentLoader


ProgressCallback = Callable[[str], None]
CancelChecker = Callable[[], bool]


@dataclass
class PipelineOptions:
    requested_types: list[str] | None = None
    chunk_size: int = 1500
    overlap_sentences: int = 1
    index_batch_size: int = 32
    gliner_batch_size: int = 8
    min_search_score: float = 0.0


@dataclass
class PipelineResult:
    documents: dict[str, str]
    chunks: dict[str, list[TextChunk]]
    rows: list[dict[str, Any]]
    warnings: list[str]
    status: str


class PipelineCancelled(RuntimeError):
    pass


class DocumentPipeline:
    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(project_root or Path(__file__).resolve().parents[1])
        self.loader = DocumentLoader()
        self.entity_service = EntityService(self.project_root)

    def process_files(
        self,
        file_paths: list[str],
        options: PipelineOptions | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_checker: CancelChecker | None = None,
    ) -> PipelineResult:
        options = options or PipelineOptions()
        requested_types = options.requested_types or [profile.entity_type for profile in get_profiles()]
        profiles = get_profiles(requested_types)
        warnings: list[str] = []

        self._check_cancel(cancel_checker)
        self._emit(progress_callback, "Извлечение текста...")
        documents = self.loader.load_multiple(file_paths)

        self._check_cancel(cancel_checker)
        self._emit(progress_callback, "Предобработка документов...")
        preprocessor = TextPreprocessor(
            chunk_size=options.chunk_size,
            overlap_sentences=options.overlap_sentences,
        )
        chunks = preprocessor.process_documents(documents)

        self._check_cancel(cancel_checker)
        self._emit(progress_callback, "Извлечение структурных сущностей...")
        chunks = self.entity_service.enrich_chunks_regex_only(
            chunks,
            include_sources=self._profile_enabled(profiles, "sources"),
        )

        gliner_profiles = [profile for profile in profiles if profile.use_gliner]
        if gliner_profiles:
            try:
                chunks = self._extract_gliner_entities(
                    chunks=chunks,
                    profiles=gliner_profiles,
                    options=options,
                    progress_callback=progress_callback,
                    cancel_checker=cancel_checker,
                )
            except Exception as exc:
                warnings.append(str(exc))

        chunks = self.entity_service.enrich_chunks_regex_only(
            chunks,
            include_sources=self._profile_enabled(profiles, "sources"),
        )

        rows = self.entity_service.flatten_entities(chunks)
        rows = self._filter_rows(rows, profiles)
        status = f"Обработано документов: {len(documents)}, найдено строк: {len(rows)}"

        return PipelineResult(
            documents=documents,
            chunks=chunks,
            rows=rows,
            warnings=warnings,
            status=status,
        )

    def _extract_gliner_entities(
        self,
        chunks: dict[str, list[TextChunk]],
        profiles: list[QueryProfile],
        options: PipelineOptions,
        progress_callback: ProgressCallback | None,
        cancel_checker: CancelChecker | None,
    ) -> dict[str, list[TextChunk]]:
        self._check_cancel(cancel_checker)
        self._emit(progress_callback, "Построение семантического индекса...")
        index_builder = IndexBuilder(batch_size=options.index_batch_size)
        index = index_builder.build_from_chunks(chunks)

        if index.size == 0:
            return chunks

        searcher = SemanticSearch(index, index_builder.vectorizer)

        self._check_cancel(cancel_checker)
        self._emit(progress_callback, "Поиск релевантных фрагментов...")
        search_results = self._search_profiles(
            searcher=searcher,
            profiles=profiles,
            min_score=options.min_search_score,
            cancel_checker=cancel_checker,
        )

        self._check_cancel(cancel_checker)
        self._emit(progress_callback, "Извлечение сущностей...")
        if search_results:
            result = self.entity_service.extract_from_search_results(
                chunks,
                search_results,
                batch_size=options.gliner_batch_size,
            )
        else:
            result = self.entity_service.extract(
                chunks,
                mode="priority",
                batch_size=options.gliner_batch_size,
                requested_types=[profile.entity_type for profile in profiles],
            )

        if result.warning:
            raise RuntimeError(result.warning)

        return result.chunks

    def _search_profiles(
        self,
        searcher: SemanticSearch,
        profiles: list[QueryProfile],
        min_score: float,
        cancel_checker: CancelChecker | None,
    ) -> list[SearchResult]:
        by_key: dict[tuple[str, int], SearchResult] = {}

        for profile in profiles:
            for query in profile.queries:
                self._check_cancel(cancel_checker)
                for result in searcher.search(query, top_k=profile.top_k, min_score=min_score):
                    key = (result.file_path, result.chunk_index)
                    old = by_key.get(key)
                    if old is None or result.score > old.score:
                        by_key[key] = result

        return sorted(by_key.values(), key=lambda result: result.score, reverse=True)

    def _filter_rows(
        self,
        rows: list[dict[str, Any]],
        profiles: list[QueryProfile],
    ) -> list[dict[str, Any]]:
        allowed_labels = {label for profile in profiles for label in profile.labels}
        return [row for row in rows if row["type"] in allowed_labels]

    def _profile_enabled(self, profiles: list[QueryProfile], entity_type: str) -> bool:
        return any(profile.entity_type == entity_type for profile in profiles)

    def _emit(self, progress_callback: ProgressCallback | None, message: str) -> None:
        if progress_callback:
            progress_callback(message)

    def _check_cancel(self, cancel_checker: CancelChecker | None) -> None:
        if cancel_checker and cancel_checker():
            raise PipelineCancelled("Обработка отменена")
