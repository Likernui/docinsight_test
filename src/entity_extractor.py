"""
Модуль извлечения сущностей из текстовых фрагментов.
На первом этапе используется GLiNER + простые regex-правила для кода.
"""

import re
from typing import Any


class EntityExtractor:
    DEFAULT_LABELS = [
        "ФИО человека",
        "тема проекта",
        "тема работы",
        "название проекта",
        "дисциплина",
        "технология",
    ]

    FENCED_CODE_PATTERN = re.compile(
        r"```[A-Za-z0-9_+#.-]*[ \t]*\n(?P<code>[\s\S]*?)```"
    )

    CODE_BLOCK_START_PATTERN = re.compile(
        r"^[ \t]*(?:class|def|async\s+def|public\s+class|function|import|from|for |while |if __name__|#include|SELECT |CREATE TABLE).+",
        re.IGNORECASE,
    )
    CODE_CONTINUATION_PATTERN = re.compile(
        r"^[ \t]*(?:return |if |elif |else:|for |while |try:|except |with |await |yield |[A-Za-z_][A-Za-z0-9_]*\s*=).+",
        re.IGNORECASE,
    )

    NAME_INITIALS_PATTERN = re.compile(
        r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.?"
    )

    FIELD_STOP_MARKERS = (
        "выполнил", "выполнила", "студент", "студентка", "обучающийся",
        "руководитель", "куратор", "преподаватель", "дисциплина",
        "тема", "название проекта", "группа",
    )

    LABELED_FIELD_PATTERNS = [
        (
            "тема проекта",
            re.compile(
                r"(?:тема\s+(?:проекта|работы)|название\s+проекта)\s*[:\-]\s*(.+?)(?=\n|$)",
                re.IGNORECASE,
            ),
        ),
        (
            "дисциплина",
            re.compile(
                r"дисциплина\s*[:\-]\s*(.+?)(?=\n|$)",
                re.IGNORECASE,
            ),
        ),
    ]

    TECHNOLOGY_PATTERNS = [
        ("Python", re.compile(r"\bpython\b", re.IGNORECASE)),
        ("JavaScript", re.compile(r"\b(?:javascript|js)\b", re.IGNORECASE)),
        ("TypeScript", re.compile(r"\b(?:typescript|ts)\b", re.IGNORECASE)),
        ("Java", re.compile(r"\bjava\b", re.IGNORECASE)),
        ("C++", re.compile(r"\bc\+\+\b", re.IGNORECASE)),
        ("C#", re.compile(r"\bc#\b", re.IGNORECASE)),
        ("PHP", re.compile(r"\bphp\b", re.IGNORECASE)),
        ("HTML", re.compile(r"\bhtml\b", re.IGNORECASE)),
        ("CSS", re.compile(r"\bcss\b", re.IGNORECASE)),
        ("SQL", re.compile(r"\bsql\b", re.IGNORECASE)),
        ("PostgreSQL", re.compile(r"\bpostgres(?:ql)?\b", re.IGNORECASE)),
        ("MySQL", re.compile(r"\bmysql\b", re.IGNORECASE)),
        ("SQLite", re.compile(r"\bsqlite\b", re.IGNORECASE)),
        ("Django", re.compile(r"\bdjango\b", re.IGNORECASE)),
        ("FastAPI", re.compile(r"\bfastapi\b", re.IGNORECASE)),
        ("Flask", re.compile(r"\bflask\b", re.IGNORECASE)),
        ("React", re.compile(r"\breact(?:\.js)?\b", re.IGNORECASE)),
        ("Vue", re.compile(r"\bvue(?:\.js)?\b", re.IGNORECASE)),
        ("Angular", re.compile(r"\bangular\b", re.IGNORECASE)),
        ("Node.js", re.compile(r"\bnode(?:\.js)?\b", re.IGNORECASE)),
        ("Docker", re.compile(r"\bdocker\b", re.IGNORECASE)),
        ("Git", re.compile(r"\bgit\b", re.IGNORECASE)),
        ("PyQt6", re.compile(r"\bpyqt6\b", re.IGNORECASE)),
        ("PyQt", re.compile(r"\bpyqt\b", re.IGNORECASE)),
        ("Qt", re.compile(r"\bqt\b", re.IGNORECASE)),
        ("OpenCV", re.compile(r"\bopencv\b", re.IGNORECASE)),
        ("EasyOCR", re.compile(r"\beasyocr\b", re.IGNORECASE)),
        ("PyMuPDF", re.compile(r"\bpymupdf\b", re.IGNORECASE)),
        ("FAISS", re.compile(r"\bfaiss\b", re.IGNORECASE)),
        ("sentence-transformers", re.compile(r"\bsentence-transformers\b", re.IGNORECASE)),
        ("GLiNER", re.compile(r"\bgliner\b", re.IGNORECASE)),
        ("PyTorch", re.compile(r"\b(?:pytorch|torch)\b", re.IGNORECASE)),
        ("Transformers", re.compile(r"\btransformers\b", re.IGNORECASE)),
        ("YOLO", re.compile(r"\byolo\b", re.IGNORECASE)),
    ]
    KNOWN_TECHNOLOGIES = {name.lower() for name, _ in TECHNOLOGY_PATTERNS}
    TECHNOLOGY_CONTEXT_MARKERS = (
        "технолог", "стек", "фреймворк", "framework", "library", "библиотек",
        "модель", "llm", "инструмент", "использовал", "реализован", "сервис",
    )

    SOURCE_SECTION_PATTERN = re.compile(
        r"(?:^|\n)\s*(?:\d{1,2}\.?\s*)?(?:список\s+(?:использованной\s+)?(?:литературы|источников)|использованн(?:ая|ые)\s+литература|источники|references|bibliography)\s*(?:\n|$)",
        re.IGNORECASE,
    )
    SOURCE_ITEM_MARKER_PATTERN = re.compile(r"(?:^|\s)(?:\[(\d{1,2})\]|(\d{1,2})[.)][\s\u200b]*)(?=[A-ZА-ЯЁ])")
    DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
    URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
    NEXT_SECTION_PATTERN = re.compile(
        r"(?:^|\n)\s*\d{1,2}\.?\s*(?:план-график|приложени[ея])\b[^\n]*(?:\n|$)",
        re.IGNORECASE,
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

    def extract_sources(self, text: str, bottom_section: bool = False) -> list[dict[str, Any]]:
        source_section = self._extract_source_section_text(text)

        if source_section:
            items = self._source_items_from_text(source_section)
            return self._source_block_entity(text, source_section, items)

        if not bottom_section:
            return []

        fallback_items = [
            item
            for item in self._source_items_from_text(text)
            if self.URL_PATTERN.search(item) or self.DOI_PATTERN.search(item)
        ]

        for line in text.splitlines():
            stripped = line.strip()
            if not (self.URL_PATTERN.search(stripped) or self.DOI_PATTERN.search(stripped)):
                continue

            source_text = self._clean_source_text(stripped)
            if len(source_text) < 10:
                continue
            fallback_items.append(source_text)

        return self._source_block_entity(text, text, fallback_items, title="Список источников")

    def _extract_source_section_text(self, text: str) -> str:
        normalized_text = text.replace("\u200b", " ")
        match = self.SOURCE_SECTION_PATTERN.search(normalized_text)
        if not match:
            return ""

        section_start = match.end()
        tail = normalized_text[section_start:]
        next_section = self.NEXT_SECTION_PATTERN.search(tail)
        section_end = section_start + next_section.start() if next_section else len(normalized_text)
        return normalized_text[section_start:section_end].strip()

    def _split_source_items(self, section_text: str) -> list[tuple[str, int]]:
        matches = list(self.SOURCE_ITEM_MARKER_PATTERN.finditer(section_text))
        if not matches:
            cleaned = self._clean_source_text(section_text)
            return [(cleaned, 0)] if cleaned else []

        items = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(section_text)
            item = section_text[start:end]
            items.append((item, start))

        return items

    def _source_items_from_text(self, source_text: str) -> list[str]:
        items = []
        seen = set()

        for raw_item, _ in self._split_source_items(source_text):
            item = self._clean_source_text(raw_item)
            if len(item) < 10 or not self._looks_like_source(item):
                continue

            key = re.sub(r"\W+", "", item.lower())
            if not key or key in seen:
                continue

            seen.add(key)
            items.append(item)

        return items

    def _source_block_entity(
        self,
        full_text: str,
        source_text: str,
        items: list[str],
        title: str = "Список использованной литературы",
    ) -> list[dict[str, Any]]:
        if not items:
            return []

        deduped = []
        seen = set()
        for item in items:
            key = re.sub(r"\W+", "", item.lower())
            if key and key not in seen:
                seen.add(key)
                deduped.append(item)

        if not deduped:
            return []

        block_text = title + "\n" + "\n".join(
            f"{index}. {item}"
            for index, item in enumerate(deduped, start=1)
        )
        start = full_text.find(source_text)
        if start == -1:
            start = None

        return [{
            "text": block_text,
            "label": "источник",
            "score": 1.0,
            "start": start,
            "end": start + len(source_text) if start is not None else None,
            "source": "regex",
            "title": title,
            "source_count": len(deduped),
        }]

    def _clean_source_text(self, source_text: str) -> str:
        source_text = re.sub(r"\s+", " ", source_text)
        return source_text.strip(" \t\r\n;.")

    def _looks_like_source(self, source_text: str) -> bool:
        lowered = source_text.lower()
        if self.URL_PATTERN.search(source_text) or self.DOI_PATTERN.search(source_text):
            return True
        if "arxiv" in lowered or "//" in source_text:
            return True
        if re.search(r"\b(?:19|20)\d{2}\b", source_text) and (
            "–" in source_text
            or "-" in source_text
            or "." in source_text
            or "," in source_text
        ):
            return True
        return False

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
            self.extract_name_initials(text)
            + self.extract_labeled_fields(text)
            + self.extract_technologies(text)
            + source_entities
            + code_entities
        )

    def __init__(self, model_name: str = "urchade/gliner_multi-v2.1", load_model: bool = True):
        self.model_name = model_name
        self._model = None
        if load_model:
            self.model

    @property
    def model(self):
        if self._model is None:
            from gliner import GLiNER
            self._model = GLiNER.from_pretrained(self.model_name)
        return self._model

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
            if label == "источник":
                continue
            if label == "технология" and not self._is_plausible_gliner_technology(text, text_val):
                continue

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

    def extract_code_blocks(self, text: str) -> list[dict[str, Any]]:
        results = []
        occupied_spans = []

        for match in self.FENCED_CODE_PATTERN.finditer(text):
            code = match.group("code").strip()
            if not code:
                continue

            title = self.summarize_code_block(code)
            results.append({
                "text": code,
                "label": "фрагмент программного кода",
                "score": None,
                "start": match.start(),
                "end": match.end(),
                "source": "regex",
                "title": title,
            })
            occupied_spans.append((match.start(), match.end()))

        results.extend(self.extract_plain_code_blocks(text, occupied_spans))

        return results

    def extract_plain_code_blocks(
        self,
        text: str,
        occupied_spans: list[tuple[int, int]] | None = None,
    ) -> list[dict[str, Any]]:
        occupied_spans = occupied_spans or []
        results = []
        current_lines = []
        current_start = None
        cursor = 0

        def is_occupied(pos: int) -> bool:
            return any(start <= pos < end for start, end in occupied_spans)

        def flush(end_pos: int):
            nonlocal current_lines, current_start
            if current_start is None:
                return

            code_lines = [line.rstrip() for line in current_lines if line.strip()]
            code = "\n".join(code_lines).strip()
            if len(code_lines) >= 2 and len(code) >= 20:
                title = self.summarize_code_block(code)
                results.append({
                    "text": code,
                    "label": "фрагмент программного кода",
                    "score": None,
                    "start": current_start,
                    "end": end_pos,
                    "source": "regex",
                    "title": title,
                })

            current_lines = []
            current_start = None

        for line in text.splitlines(keepends=True):
            line_start = cursor
            line_end = cursor + len(line)
            cursor = line_end

            if is_occupied(line_start):
                flush(line_start)
                continue

            stripped = line.strip()
            starts_block = bool(self.CODE_BLOCK_START_PATTERN.match(line))
            continues_block = current_start is not None and (
                line[:1].isspace() or self.CODE_CONTINUATION_PATTERN.match(line)
            )

            if stripped and (
                starts_block
                or continues_block
            ):
                if current_start is None:
                    current_start = line_start
                current_lines.append(line.rstrip("\n"))
            else:
                flush(line_start)

        flush(len(text))
        return results

    def summarize_code_block(self, code: str) -> str:
        patterns = [
            (r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)", "класс"),
            (r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)", "функция"),
            (r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)", "функция"),
            (r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b", "цикл"),
            (r"\b(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=", "переменная"),
            (r"\bCREATE\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)", "таблица"),
        ]

        for pattern, kind in patterns:
            match = re.search(pattern, code, re.IGNORECASE)
            if match:
                return f"{kind} {match.group(1)}"

        for line in code.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:80]

        return "фрагмент кода"

    def _code_block_to_entity(self, block: dict[str, Any]) -> dict[str, Any]:
        title = block.get("title") or "фрагмент кода"

        return {
            "text": title,
            "label": "фрагмент программного кода",
            "score": 1.0,
            "start": block.get("start"),
            "end": block.get("end"),
            "source": "regex",
            "title": title,
            "code": block.get("text"),
        }

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

        self.attach_document_source_block(enriched)
        return enriched

    def find_source_section_start(self, chunks: list) -> int | None:
        for index, chunk in enumerate(chunks):
            if self.SOURCE_SECTION_PATTERN.search(chunk.text.replace("\u200b", " ")):
                return index
        return None

    def attach_document_source_block(self, chunks: list) -> None:
        start_index = self.find_source_section_start(chunks)
        if start_index is None:
            return

        related_chunks = chunks[start_index:]
        combined_text = "\n".join(chunk.text for chunk in related_chunks)
        source_entities = self.extract_sources(combined_text, bottom_section=True)
        if not source_entities:
            return

        entity = source_entities[0]
        entity["chunk_indexes"] = [chunk.chunk_index for chunk in related_chunks]
        chunks[start_index].metadata.setdefault("entities", []).append(entity)
    
    def enrich_chunks_dict(self, chunks_dict: dict[str, list], batch_size: int = 8):
        """
        Извлечь сущности для всех чанков всех документов.
        """
        enriched_dict = {}

        for file_path, chunks in chunks_dict.items():
            enriched_dict[file_path] = self.enrich_chunks(chunks, batch_size=batch_size)

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

            if old_source != "regex" and source == "regex":
                by_key[key] = ent
                continue

            old_score = old.get("score") or 0
            score = ent.get("score") or 0
            if source == old_source and score > old_score:
                by_key[key] = ent

        return list(by_key.values())

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
