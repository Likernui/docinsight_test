"""
Модуль извлечения сущностей из текстовых фрагментов.

Класс EntityExtractor координирует GLiNER, regex-правила и нормализацию
результатов. Частные правила вынесены в соседние модули пакета entity.
"""

import re
from typing import Any

from src.entity.code_rules import CodeRulesMixin
from src.entity.patterns import EntityPatternsMixin
from src.entity.person_rules import PersonRulesMixin
from src.entity.source_rules import SourceRulesMixin


class EntityExtractor(
    EntityPatternsMixin,
    PersonRulesMixin,
    SourceRulesMixin,
    CodeRulesMixin,
):
    def extract_labeled_fields(self, text: str) -> list[dict[str, Any]]:
        results = []

        for label, pattern in self.LABELED_FIELD_PATTERNS:
            for match in pattern.finditer(text):
                value, start, end = self._clean_labeled_value(match.group(1), match.start(1))

                if len(value) < 5:
                    continue

                results.append({
                    "text": value,
                    "label": label,
                    "score": 1.0,
                    "start": start,
                    "end": end,
                    "source": "regex",
                })

        return results

    def extract_technologies(self, text: str) -> list[dict[str, Any]]:
        results = []
        seen = set()

        for canonical, pattern in self.TECHNOLOGY_PATTERNS:
            for match in pattern.finditer(text):
                key = canonical.lower()
                if key in seen:
                    continue
                seen.add(key)
                results.append({
                    "text": canonical,
                    "label": "технология",
                    "score": 1.0,
                    "start": match.start(),
                    "end": match.end(),
                    "source": "regex",
                })

        return results

    def _clean_labeled_value(self, value: str, absolute_start: int) -> tuple[str, int, int]:
        raw = value.strip()
        lower = raw.lower()
        cut_at = len(raw)

        for marker in self.FIELD_STOP_MARKERS:
            marker_pos = lower.find(marker)
            if marker_pos > 0:
                prefix = raw[:marker_pos].rstrip()
                if prefix.endswith(".") or prefix.endswith(";"):
                    cut_at = min(cut_at, marker_pos)

        cleaned = raw[:cut_at].strip(" \t\r\n:;,.")
        leading_trim = len(raw[:cut_at]) - len(raw[:cut_at].lstrip())
        start = absolute_start + leading_trim
        end = start + len(cleaned)
        return cleaned, start, end

    def extract_regex_entities(
        self,
        text: str,
        bottom_section: bool = False,
        include_sources: bool = True,
    ) -> list[dict[str, Any]]:
        code_entities = [
            self._code_block_to_entity(block)
            for block in self.extract_code_blocks(text)
        ]
        source_entities = self.extract_sources(text, bottom_section=bottom_section) if include_sources else []

        return (
            self.extract_student_fields(text)
            + self.extract_supervisor_fields(text)
            + self.extract_labeled_fields(text)
            + self.extract_technologies(text)
            + source_entities
            + code_entities
        )

    def __init__(self, model_name: str = "urchade/gliner_multi-v2.1", load_model: bool = True):
        self.model_name = model_name
        self._model = None
        self._names_extractor = None
        self._names_extractor_failed = False
        if load_model:
            self.model

    @property
    def model(self):
        if self._model is None:
            from gliner import GLiNER
            self._model = GLiNER.from_pretrained(self.model_name)
        return self._model

    @property
    def names_extractor(self):
        if self._names_extractor_failed:
            return None

        if self._names_extractor is None:
            try:
                from natasha import MorphVocab, NamesExtractor
                self._names_extractor = NamesExtractor(MorphVocab())
            except Exception:
                self._names_extractor_failed = True
                return None

        return self._names_extractor

    def extract_entities(self, text: str, labels: list[str] | None = None) -> list[dict[str, Any]]:
        labels = labels or self.DEFAULT_LABELS

        entities = self.model.predict_entities(text, labels)
        return self._normalize_entities(text, entities)

    def extract_entities_batch(
        self,
        texts: list[str],
        labels: list[str] | None = None,
        batch_size: int = 8,
    ) -> list[list[dict[str, Any]]]:
        labels = labels or self.DEFAULT_LABELS

        if not texts:
            return []

        entities_by_text = self.model.inference(
            texts,
            labels,
            batch_size=batch_size,
        )

        return [
            self._normalize_entities(text, entities)
            for text, entities in zip(texts, entities_by_text)
        ]

    def _normalize_entities(self, text: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []

        for ent in entities:
            text_val = ent.get("text", "").strip()
            score = float(ent.get("score", 0))

            # ❌ фильтруем мусор
            if score < 0.6:
                continue

            if len(text_val) < 5:
                continue

            if text_val.lower() in ["тема", "тема работы", "дисциплина"]:
                continue

            label = ent.get("label", "")
            if label in {"источник", "ФИО человека", "ФИО студента", "ФИО куратора", "ФИО"}:
                continue
            if label == "технология" and not self._is_plausible_gliner_technology(text, text_val):
                continue

            results.append({
                "text": text_val,
                "label": label,
                "score": score,
                "start": ent.get("start"),
                "end": ent.get("end"),
                "source": "gliner",
            })

        return results

    def _is_plausible_person_name(self, value: str) -> bool:
        normalized = re.sub(r"\s+", " ", value).strip()
        lowered = normalized.lower()

        if any(stop_word in lowered for stop_word in self.PERSON_NAME_STOP_WORDS):
            return False
        if re.search(r"[\d/:@]|https?://|www\.", normalized, re.IGNORECASE):
            return False
        if not re.search(r"[А-ЯЁ][а-яё]", normalized):
            return False

        return bool(
            re.fullmatch(r"[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.?", normalized)
            or re.fullmatch(r"[А-ЯЁ][а-яё]{2,}(?:\s+[А-ЯЁ][а-яё]{2,}){1,2}", normalized)
        )

    def _is_plausible_gliner_technology(self, text: str, value: str) -> bool:
        normalized = value.strip().lower()
        if normalized in self.KNOWN_TECHNOLOGIES:
            return True

        if len(value) < 3 or len(value) > 60:
            return False
        if re.search(r"[А-ЯЁа-яё]", value):
            return False
        if not re.search(r"[A-Z0-9+#.-]", value):
            return False

        pos = text.lower().find(normalized)
        if pos == -1:
            return False

        context = text[max(0, pos - 120): pos + len(value) + 120].lower()
        return any(marker in context for marker in self.TECHNOLOGY_CONTEXT_MARKERS)

    def enrich_chunks(self, chunks: list, batch_size: int = 8):
        """
        Извлечь сущности из списка чанков.
        """
        texts = [chunk.text for chunk in chunks]
        gliner_entities = self.extract_entities_batch(texts, batch_size=batch_size)

        enriched = []

        last_source_chunk_start = max(0, len(chunks) - 3)
        source_section_start = self.find_source_section_start(chunks)

        for index, (chunk, entities) in enumerate(zip(chunks, gliner_entities)):
            if source_section_start is not None and index >= source_section_start:
                chunk.metadata["entities"] = []
                enriched.append(chunk)
                continue

            bottom_section = index >= last_source_chunk_start
            regex_entities = self.extract_regex_entities(
                chunk.text,
                bottom_section=bottom_section,
                include_sources=False,
            )
            all_entities = self.deduplicate_entities(entities + regex_entities)
            all_entities = self.normalize_entity_records(all_entities, chunk.chunk_index)

            chunk.metadata["entities"] = all_entities
            enriched.append(chunk)

        self.attach_title_person_entities(enriched)
        return enriched

    def enrich_chunks_dict(self, chunks_dict: dict[str, list], batch_size: int = 8):
        """
        Извлечь сущности для всех чанков всех документов.
        """
        enriched_dict = {}

        for file_path, chunks in chunks_dict.items():
            enriched_dict[file_path] = self.enrich_chunks(chunks, batch_size=batch_size)

        return enriched_dict
    
    def deduplicate_entities(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_key = {}
        role_names = {
            ent.get("text", "").strip().lower()
            for ent in entities
            if ent.get("label") in {"ФИО студента", "ФИО куратора", "ответственный"}
        }

        for ent in entities:
            text = ent.get("text", "").strip().lower()
            label = ent.get("label", "").strip().lower()
            key = (text, label)

            if not text:
                continue
            if label == "фио" and text in role_names:
                continue

            if key not in by_key:
                by_key[key] = ent
                continue

            old = by_key[key]
            old_source = old.get("source")
            source = ent.get("source")

            old["source"] = self._merge_sources(old_source, source)

            if old_source != "regex" and source == "regex":
                ent["source"] = old["source"]
                by_key[key] = ent
                continue

            old_score = old.get("score") or 0
            score = ent.get("score") or 0
            if source == old_source and score > old_score:
                ent["source"] = old["source"]
                by_key[key] = ent

        return self._resolve_person_role_conflicts(list(by_key.values()))

    def _merge_sources(self, old_source: str | None, source: str | None) -> str:
        order = ["regex", "natasha", "gliner"]
        values = {
            item
            for raw in (old_source, source)
            for item in str(raw or "").split("+")
            if item
        }

        known = [item for item in order if item in values]
        unknown = sorted(values - set(order))
        return "+".join(known + unknown) or "unknown"

    def _resolve_person_role_conflicts(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        person_labels = {"ФИО студента", "ФИО куратора"}
        by_name = {}
        result = []

        for ent in entities:
            if ent.get("label") not in person_labels:
                result.append(ent)
                continue

            key = ent.get("text", "").strip().lower()
            if not key:
                continue

            old = by_name.get(key)
            if old is None or self._person_role_rank(ent) > self._person_role_rank(old):
                by_name[key] = ent

        return result + self._drop_short_person_name_variants(list(by_name.values()))

    def _person_role_rank(self, entity: dict[str, Any]) -> tuple[int, float]:
        source_rank = {
            "regex": 3,
            "natasha": 3,
            "gliner": 1,
        }
        rank = max(
            [source_rank.get(source, 0) for source in str(entity.get("source") or "").split("+")]
            or [0]
        )
        return (rank, float(entity.get("score") or 0))

    def _drop_short_person_name_variants(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        sorted_entities = sorted(
            entities,
            key=lambda ent: (
                ent.get("label", ""),
                len(ent.get("text", "")),
                self._person_role_rank(ent),
            ),
            reverse=True,
        )

        for ent in sorted_entities:
            text = re.sub(r"\s+", " ", ent.get("text", "").strip().lower())
            label = ent.get("label")
            if any(
                old.get("label") == label
                and re.sub(r"\s+", " ", old.get("text", "").strip().lower()).startswith(text + " ")
                for old in result
            ):
                continue
            result.append(ent)

        return result

    def normalize_entity_records(
        self,
        entities: list[dict[str, Any]],
        chunk_index: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized = []

        for ent in entities:
            text = str(ent.get("text", "")).strip()
            label = str(ent.get("label", "")).strip()
            if not text or not label:
                continue

            item = dict(ent)
            item["text"] = text
            item["label"] = label
            item.setdefault("source", "unknown")

            chunk_indexes = item.get("chunk_indexes")
            if isinstance(chunk_indexes, list):
                item["chunk_indexes"] = sorted({int(i) for i in chunk_indexes})
            elif chunk_index is not None:
                item["chunk_indexes"] = [int(chunk_index)]
            else:
                item["chunk_indexes"] = []

            normalized.append(item)

        return normalized

