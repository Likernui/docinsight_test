"""
Правила извлечения библиографических источников.
"""

import re
from typing import Any


class SourceRulesMixin:
    def extract_sources(self, text: str, bottom_section: bool = False) -> list[dict[str, Any]]:
        source_section = self._extract_source_section_text(text)

        if source_section:
            items = self._source_items_from_text(source_section)
            return self._source_block_entity(text, source_section, items)

        if not bottom_section:
            return []

        fallback_items = self._fallback_source_items_from_text(text)

        return self._source_block_entity(text, text, fallback_items, title="Список источников")

    def _extract_source_section_text(self, text: str) -> str:
        normalized_text = text.replace("\u200b", " ")
        match = self._source_section_match(normalized_text)
        if not match:
            return ""

        section_start = match.end()
        tail = normalized_text[section_start:]
        next_section = self.NEXT_SECTION_PATTERN.search(tail)
        section_end = section_start + next_section.start() if next_section else len(normalized_text)
        return normalized_text[section_start:section_end].strip()

    def _source_section_match(self, text: str):
        matches = [
            match
            for pattern in (self.SOURCE_SECTION_PATTERN, self.SOURCE_SHORT_HEADING_PATTERN)
            if (match := pattern.search(text))
        ]
        return min(matches, key=lambda match: match.start()) if matches else None

    def _split_source_items(self, section_text: str) -> list[tuple[str, int]]:
        matches = [
            match
            for match in self.SOURCE_ITEM_MARKER_PATTERN.finditer(section_text)
            if not self._is_inside_source_citation_number(section_text, match.start())
        ]
        if not matches:
            return self._split_unnumbered_source_items(section_text)

        items = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(section_text)
            item = section_text[start:end]
            items.append((item, start))

        return items

    def _is_inside_source_citation_number(self, text: str, marker_start: int) -> bool:
        prefix = text[max(0, marker_start - 12):marker_start]
        normalized = prefix.replace("\u00a0", " ")
        return bool(re.search(r"(?:№|N)\s*$", normalized, re.IGNORECASE))

    def _split_unnumbered_source_items(self, section_text: str) -> list[tuple[str, int]]:
        items = []
        current_lines = []
        current_start = 0
        cursor = 0

        def flush():
            nonlocal current_lines, current_start
            if not current_lines:
                return

            item = self._clean_source_text(" ".join(current_lines))
            if item:
                items.append((item, current_start))
            current_lines = []

        for line in section_text.splitlines(keepends=True):
            line_start = cursor
            cursor += len(line)
            stripped = self._clean_source_text(self._trim_source_item(line.strip()))
            if not stripped:
                continue

            starts_item = self._looks_like_source_start(stripped)
            if starts_item and current_lines:
                flush()

            if not current_lines:
                current_start = line_start

            current_lines.append(stripped)

        flush()
        return items

    def _source_items_from_text(self, source_text: str) -> list[str]:
        items = []
        seen = set()

        for raw_item, _ in self._split_source_items(source_text):
            item = self._clean_source_text(self._trim_source_item(raw_item))
            if len(item) < 10 or not self._looks_like_source(item):
                continue

            key = re.sub(r"\W+", "", item.lower())
            if not key or key in seen:
                continue

            seen.add(key)
            items.append(item)

        return items

    def _fallback_source_items_from_text(self, text: str) -> list[str]:
        items = []
        seen = set()

        for item in self._source_items_from_text(text):
            if not self.EXPLICIT_SOURCE_PATTERN.search(item):
                continue
            key = re.sub(r"\W+", "", item.lower())
            if key and key not in seen:
                seen.add(key)
                items.append(item)

        for line in text.splitlines():
            stripped = line.strip()
            if not self.EXPLICIT_SOURCE_PATTERN.search(stripped):
                continue

            source_text = self._clean_source_text(self._trim_source_item(stripped))
            source_text = re.sub(r"^\s*(?:\[\d{1,2}\]|\d{1,2}[.)])\s*", "", source_text)
            if len(source_text) < 10 or not self._looks_like_source(source_text):
                continue

            key = re.sub(r"\W+", "", source_text.lower())
            if key and key not in seen:
                seen.add(key)
                items.append(source_text)

        return items

    def _trim_source_item(self, source_text: str) -> str:
        next_section = self.NEXT_SECTION_PATTERN.search(source_text)
        if next_section:
            source_text = source_text[:next_section.start()]

        return source_text

    def _looks_like_source_start(self, source_text: str) -> bool:
        lowered = source_text.lower()
        if lowered.startswith("описание:"):
            return False
        if self.URL_PATTERN.search(source_text) or self.DOI_PATTERN.search(source_text):
            return True
        if "электронный ресурс" in lowered or "гост" in lowered or "//" in source_text:
            return True
        if re.search(r"\b(?:19|20)\d{2}\b", source_text) and (
            self.NAME_INITIALS_PATTERN.search(source_text)
            or re.search(r"\b(?:москва|санкт-петербург|спб|екатеринбург|томск|изд|с\.)\b", lowered)
            or len(source_text) >= 60
        ):
            return True
        return False

    def _looks_like_bibliography_text(self, text: str) -> bool:
        lowered = text.lower()
        if self._source_section_match(text.replace("\u200b", " ")):
            return True

        source_clues = sum([
            len(self.URL_PATTERN.findall(text)) >= 1,
            len(self.DOI_PATTERN.findall(text)) >= 1,
            lowered.count("дата обращения") >= 1,
            lowered.count("электронный ресурс") >= 1,
            lowered.count("//") >= 2,
            lowered.count("описание:") >= 2,
        ])
        return source_clues >= 2

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
        if len(source_text) > 1400:
            return False
        if self.SOURCE_NOISE_PATTERN.search(source_text):
            return False
        if self.SCHEDULE_ITEM_PATTERN.search(source_text):
            return False
        if self.URL_PATTERN.search(source_text) or self.DOI_PATTERN.search(source_text):
            return True
        if "arxiv" in lowered or "//" in source_text:
            return True
        if re.fullmatch(r"[А-ЯЁA-Z][А-ЯЁа-яёA-Za-z\s-]+,\s*(?:19|20)\d{2}", source_text.strip()):
            return False
        if re.search(
            r"\b(?:электрон|учеб|пособ|стать[яи]|журнал|изд|москва|санкт-петербург|"
            r"спб|режим\s+доступа|doi|гост|конференц|монограф)\b",
            lowered,
        ):
            return True
        if re.search(r"\b(?:19|20)\d{2}\b", source_text) and (
            "–" in source_text
            or "-" in source_text
            or "." in source_text
            or "," in source_text
        ):
            return bool(
                self.NAME_INITIALS_PATTERN.search(source_text)
                or "//" in source_text
                or len(source_text) >= 60
                or re.search(r"\b(?:москва|санкт-петербург|спб|екатеринбург|томск|изд|с\.)\b", lowered)
            )
        return False

    def find_source_section_start(self, chunks: list) -> int | None:
        for index, chunk in enumerate(chunks):
            if self._source_section_match(chunk.text.replace("\u200b", " ")):
                return index
        return None

    def attach_document_source_block(self, chunks: list, document_text: str | None = None) -> None:
        start_index = self.find_source_section_start(chunks)
        if not chunks:
            return

        has_source_heading = start_index is not None
        if not has_source_heading:
            start_index = max(0, len(chunks) - 4)

        combined_text = document_text if document_text else "\n".join(chunk.text for chunk in chunks[start_index:])
        source_entities = self.extract_sources(
            combined_text,
            bottom_section=not has_source_heading,
        )
        if not source_entities:
            return

        entity = source_entities[0]
        entity["chunk_indexes"] = [chunks[start_index].chunk_index]
        chunks[start_index].metadata.setdefault("entities", []).append(entity)
