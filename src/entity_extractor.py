"""
Модуль извлечения сущностей из текстовых фрагментов.
На первом этапе используется GLiNER + простые regex-правила для кода.
"""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ExtractedEntity:
    text: str
    label: str
    score: float | None = None
    start: int | None = None
    end: int | None = None


class EntityExtractor:
    DEFAULT_LABELS = [
        "ФИО человека",
        "тема проекта",
        "тема работы",
        "название проекта",
        "дисциплина",
    ]

    CODE_PATTERNS = [
        re.compile(r"```[\s\S]*?```"),
        re.compile(r"(?:class|def|import|from|if __name__|for |while |return ).+", re.MULTILINE),
    ]

    NAME_INITIALS_PATTERN = re.compile(
        r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.?"
    )

    def extract_name_initials(self, text: str) -> list[dict[str, Any]]:
        results = []

        for match in self.NAME_INITIALS_PATTERN.finditer(text):
            name = match.group(0)

            results.append({
                "text": name,
                "label": self.classify_name_role(text, name, match.start(), match.end()),
                "score": 1.0,
                "start": match.start(),
                "end": match.end(),
                "source": "regex",
            })

        return results

    def __init__(self, model_name: str = "urchade/gliner_multi-v2.1"):
        from gliner import GLiNER

        self.model_name = model_name
        self.model = GLiNER.from_pretrained(model_name)

    def extract_entities(self, text: str, labels: list[str] | None = None) -> list[dict[str, Any]]:
        labels = labels or self.DEFAULT_LABELS

        entities = self.model.predict_entities(text, labels)

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

            if label == "ФИО человека":
                label = self.classify_name_role(
                    text=text,
                    name=text_val,
                    start=ent.get("start") or 0,
                    end=ent.get("end") or 0
                )

            results.append({
                "text": text_val,
                "label": label,
                "score": score,
                "start": ent.get("start"),
                "end": ent.get("end"),
                "source": "gliner",
            })

        return results

    def extract_code_blocks(self, text: str) -> list[dict[str, Any]]:
        results = []

        for pattern in self.CODE_PATTERNS:
            for match in pattern.finditer(text):
                code = match.group(0).strip()
                if code:
                    results.append({
                        "text": code,
                        "label": "фрагмент программного кода",
                        "score": None,
                        "start": match.start(),
                        "end": match.end(),
                    })

        return results

    def extract_from_text(self, text: str) -> dict[str, list[dict[str, Any]]]:
        entities = self.extract_entities(text)
        regex_names = self.extract_name_initials(text)

        all_entities = entities + regex_names
        all_entities = self.deduplicate_entities(all_entities)

        return {
            "entities": all_entities,
            "code_blocks": self.extract_code_blocks(text),
        }
    
    def enrich_chunk(self, chunk):
        result = self.extract_from_text(chunk.text)

        chunk.metadata["entities"] = result["entities"]
        chunk.metadata["code_blocks"] = result["code_blocks"]

        # 🔥 ВРЕМЕННО
        if "Ардашов" in chunk.text:
            print("\nDEBUG CHUNK:")
            print(chunk.text[:200])
            print("ENTITIES:", result["entities"])

        return chunk
    
    def enrich_chunks(self, chunks: list):
        """
        Извлечь сущности из списка чанков.
        """
        enriched = []

        for chunk in chunks:
            enriched.append(self.enrich_chunk(chunk))

        return enriched
    
    def enrich_chunks_dict(self, chunks_dict: dict[str, list]):
        """
        Извлечь сущности для всех чанков всех документов.
        """
        enriched_dict = {}

        for file_path, chunks in chunks_dict.items():
            enriched_dict[file_path] = self.enrich_chunks(chunks)

        return enriched_dict
    
    def classify_name_role(self, text: str, name: str, start: int = 0, end: int = 0) -> str:
        role_markers = [
            ("ФИО студента", [
                "студент", "обучающийся", "обучающаяся",
                "автор", "выполнил", "выполнила", "исполнитель"
            ]),
            ("ФИО куратора", [
                "куратор", "руководитель", "научный руководитель",
                "преподаватель", "проверил", "проверила"
            ]),
            ("ответственный", [
                "ответственный", "ответственная"
            ]),
        ]

        # Берём небольшой контекст вокруг имени
        context_start = max(0, start - 120)
        context_end = min(len(text), end + 40)
        context = text[context_start:context_end].lower()
        name_lower = name.lower()

        # Если имя есть в контексте, стараемся взять строку, где находится имя
        lines = context.splitlines()
        candidate_lines = [line for line in lines if name_lower in line]

        # Если строка потерялась из-за обрезки, используем весь контекст
        candidates = candidate_lines if candidate_lines else [context]

        best_role = None
        best_distance = 10**9

        for candidate in candidates:
            name_pos = candidate.find(name_lower)

            for role, markers in role_markers:
                for marker in markers:
                    marker_pos = candidate.rfind(marker, 0, name_pos if name_pos != -1 else len(candidate))

                    if marker_pos != -1:
                        distance = abs((name_pos if name_pos != -1 else len(candidate)) - marker_pos)

                        if distance < best_distance:
                            best_distance = distance
                            best_role = role

        return best_role or "ФИО"
    
    def deduplicate_entities(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_text = {}

        for ent in entities:
            key = ent.get("text", "").strip().lower()
            label = ent.get("label", "").strip().lower()

            if key not in by_text:
                by_text[key] = ent
                continue

            old_label = by_text[key].get("label", "").strip().lower()

            if old_label == "неизвестно" and label != "неизвестно":
                by_text[key] = ent

        return list(by_text.values())
    
    def extract_document_structure(self, chunks: list) -> dict:
        """
        Собирает структуру документа:
        дисциплина -> темы -> студент, если найден рядом.
        """
        current_discipline = None
        topics = []

        for chunk in chunks:
            entities = chunk.metadata.get("entities", [])

            # 1. Обновляем текущую дисциплину
            for ent in entities:
                if ent.get("label") == "дисциплина":
                    current_discipline = ent.get("text")

            # 2. Ищем студентов в текущем чанке
            students = [
                ent.get("text")
                for ent in entities
                if ent.get("label") == "ФИО студента"
            ]

            # 3. Ищем темы
            for ent in entities:
                if ent.get("label") in ["тема проекта", "тема работы", "название проекта"]:
                    topics.append({
                        "topic": ent.get("text"),
                        "discipline": current_discipline,
                        "students": students,
                        "chunk_index": chunk.chunk_index,
                        "file_path": chunk.file_path,
                    })

        return {
            "discipline": current_discipline,
            "topics": topics,
        }
    
    def extract_all_documents_structure(self, chunks_dict: dict[str, list]) -> dict:
        """
        Собирает структуру по всем документам.
        """
        result = {}

        for file_path, chunks in chunks_dict.items():
            result[file_path] = self.extract_document_structure(chunks)

        return result