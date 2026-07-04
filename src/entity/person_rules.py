"""
Правила извлечения ФИО и ролей участников проекта.
"""

import re
from typing import Any


class PersonRulesMixin:
    def extract_supervisor_fields(self, text: str) -> list[dict[str, Any]]:
        if self._looks_like_bibliography_text(text):
            return []
        return self._extract_role_fields(text, self.SUPERVISOR_MARKER_PATTERN, "ФИО куратора")

    def extract_student_fields(self, text: str) -> list[dict[str, Any]]:
        if self._looks_like_bibliography_text(text):
            return []
        return self._extract_role_fields(text, self.STUDENT_MARKER_PATTERN, "ФИО студента")

    def _extract_role_fields(
        self,
        text: str,
        marker_pattern: re.Pattern,
        label: str,
    ) -> list[dict[str, Any]]:
        results = []
        lines = text.splitlines(keepends=True)
        line_starts = []
        cursor = 0

        for line in lines:
            line_starts.append(cursor)
            cursor += len(line)

        for index, line in enumerate(lines):
            if not marker_pattern.search(line):
                continue

            window_end_index = min(len(lines), index + 4)
            window = "".join(lines[index:window_end_index])
            window_start = line_starts[index]
            window, window_start = self._role_window(text=window, start=window_start, label=label)

            for entity in self._extract_person_names_from_text(
                window,
                absolute_start=window_start,
                label=label,
            ):
                results.append(entity)
                if label == "ФИО куратора":
                    break

        return self.deduplicate_entities(results)

    def _role_window(self, text: str, start: int, label: str) -> tuple[str, int]:
        if label == "ФИО куратора":
            marker = self.SUPERVISOR_MARKER_PATTERN.search(text)
            if marker:
                return text[marker.end():], start + marker.end()
            return text, start

        supervisor_marker = self.SUPERVISOR_MARKER_PATTERN.search(text)
        if supervisor_marker:
            text = text[:supervisor_marker.start()]

        return text, start

    def _extract_person_names_from_text(
        self,
        text: str,
        absolute_start: int,
        label: str,
    ) -> list[dict[str, Any]]:
        results = []
        seen_spans = []

        for name, local_start, local_end, source in self._person_name_candidates(text):
            if not self._is_plausible_person_name(name):
                continue

            name = re.sub(r"\s+", " ", name).strip()
            start = absolute_start + local_start
            end = absolute_start + local_end
            overlapping = self._overlapping_person_entity(results, start, end, name)
            if overlapping:
                overlapping["source"] = self._merge_sources(overlapping.get("source"), source)
                continue

            if any(not (end <= old_start or start >= old_end) for old_start, old_end in seen_spans):
                continue

            seen_spans.append((start, end))
            results.append({
                "text": name,
                "label": label,
                "score": 0.95 if source == "natasha" else 1.0,
                "start": start,
                "end": end,
                "source": source,
            })

        return results

    def _person_name_candidates(self, text: str) -> list[tuple[str, int, int, str]]:
        candidates = []

        names_extractor = self.names_extractor
        if names_extractor is not None:
            for match in names_extractor(text):
                name, start, end = self._normalize_natasha_name_match(text, match.start, match.stop)
                candidates.append((name, start, end, "natasha"))

        for pattern in (self.NAME_INITIALS_PATTERN, self.RUSSIAN_PERSON_NAME_PATTERN):
            for match in pattern.finditer(text):
                candidates.append((match.group(0).strip(), match.start(), match.end(), "regex"))

        return sorted(
            candidates,
            key=lambda item: (item[1], -(item[2] - item[1]), item[3] != "regex"),
        )

    def _normalize_natasha_name_match(self, text: str, start: int, end: int) -> tuple[str, int, int]:
        value = text[start:end].strip()
        full_initials = self.NAME_INITIALS_PATTERN.match(text[start:])
        if full_initials and full_initials.end() > len(value):
            end = start + full_initials.end()
            value = full_initials.group(0).strip()

        return value, start, end

    def attach_title_person_entities(self, chunks: list, title_chunk_count: int = 3) -> None:
        if not chunks:
            return

        title_chunks = chunks[:title_chunk_count]
        title_text = "\n".join(chunk.text for chunk in title_chunks)
        if not title_text.strip() or self._looks_like_bibliography_text(title_text):
            return

        title_entities = self.extract_title_person_fields(title_text)
        if not title_entities:
            return

        person_labels = {"ФИО студента", "ФИО куратора"}
        title_indexes = [chunk.chunk_index for chunk in title_chunks]

        for chunk in title_chunks:
            chunk.metadata["entities"] = [
                entity
                for entity in chunk.metadata.get("entities", [])
                if entity.get("label") not in person_labels
            ]

        normalized = self.normalize_entity_records(title_entities, chunks[0].chunk_index)
        for entity in normalized:
            entity["chunk_indexes"] = title_indexes
            entity["from_title"] = True

        chunks[0].metadata.setdefault("entities", []).extend(normalized)

    def extract_title_person_fields(self, text: str) -> list[dict[str, Any]]:
        markers = self._title_role_markers(text)
        if not markers:
            return []

        results = []
        student_marker_seen = False
        student_found = False
        for index, marker in enumerate(markers):
            label, match = marker
            segment_start = match.end()
            segment_end = markers[index + 1][1].start() if index + 1 < len(markers) else len(text)
            segment = text[segment_start:segment_end]
            segment, offset = self._trim_title_role_segment(segment, label)

            segment_entities = self._extract_title_person_names_from_text(
                segment,
                absolute_start=segment_start + offset,
                label=label,
            )

            if label == "ФИО студента":
                student_marker_seen = True
                student_found = student_found or bool(segment_entities)
                results.extend(segment_entities)
                continue

            if (
                label == "ФИО куратора"
                and student_marker_seen
                and not student_found
                and len(segment_entities) >= 2
            ):
                for entity in segment_entities[:-1]:
                    entity["label"] = "ФИО студента"
                student_found = True

            results.extend(segment_entities)

        return self.deduplicate_entities(results)

    def _extract_title_person_names_from_text(
        self,
        text: str,
        absolute_start: int,
        label: str,
    ) -> list[dict[str, Any]]:
        results = []
        seen_spans = []

        for name, local_start, local_end, source in self._title_person_name_candidates(text):
            if not self._is_plausible_person_name(name):
                continue

            start = absolute_start + local_start
            end = absolute_start + local_end
            name = re.sub(r"\s+", " ", name).strip()
            overlapping = self._overlapping_person_entity(results, start, end, name)
            if overlapping:
                overlapping["source"] = self._merge_sources(overlapping.get("source"), source)
                continue

            if any(not (end <= old_start or start >= old_end) for old_start, old_end in seen_spans):
                continue

            seen_spans.append((start, end))
            results.append({
                "text": name,
                "label": label,
                "score": 1.0,
                "start": start,
                "end": end,
                "source": "regex" if source == "structured" else source,
            })

        return results

    def _overlapping_person_entity(
        self,
        entities: list[dict[str, Any]],
        start: int,
        end: int,
        name: str,
    ) -> dict[str, Any] | None:
        normalized = re.sub(r"\s+", " ", name).strip().lower()
        for entity in entities:
            old_start = entity.get("start")
            old_end = entity.get("end")
            old_text = re.sub(r"\s+", " ", entity.get("text", "")).strip().lower()
            if old_start is None or old_end is None:
                continue
            if end <= old_start or start >= old_end:
                continue
            if normalized == old_text:
                return entity
        return None

    def _title_person_name_candidates(self, text: str) -> list[tuple[str, int, int, str]]:
        return sorted(
            self._structured_russian_name_candidates(text) + self._person_name_candidates(text),
            key=lambda item: (item[1], item[3] != "structured", -(item[2] - item[1])),
        )

    def _structured_russian_name_candidates(self, text: str) -> list[tuple[str, int, int, str]]:
        candidates = []
        word_pattern = re.compile(r"[А-ЯЁ][а-яё]{2,}")
        words = list(word_pattern.finditer(text))
        index = 0

        while index < len(words):
            current = words[index]
            sequence = [current]
            next_index = index + 1

            while next_index < len(words) and words[next_index].start() - sequence[-1].end() <= 3:
                sequence.append(words[next_index])
                next_index += 1

            if len(sequence) >= 2:
                candidates.extend(self._split_structured_name_sequence(sequence, text))

            index = max(next_index, index + 1)

        return candidates

    def _split_structured_name_sequence(self, sequence: list[re.Match], text: str) -> list[tuple[str, int, int, str]]:
        candidates = []
        index = 0

        while index + 1 < len(sequence):
            end_index = index + 2
            if index + 2 < len(sequence) and self._looks_like_patronymic(sequence[index + 2].group(0)):
                end_index = index + 3
            elif sequence[index + 1].group(0).lower() not in self.COMMON_FIRST_NAMES:
                index += 1
                continue

            start = sequence[index].start()
            end = sequence[end_index - 1].end()
            candidates.append((text[start:end], start, end, "structured"))
            index = end_index

        return candidates

    def _looks_like_patronymic(self, word: str) -> bool:
        return bool(re.search(r"(?:вич|вна|чна)$", word.lower()))

    def _title_role_markers(self, text: str) -> list[tuple[str, re.Match]]:
        markers = []
        for match in self.STUDENT_MARKER_PATTERN.finditer(text):
            markers.append(("ФИО студента", match))
        for match in self.SUPERVISOR_MARKER_PATTERN.finditer(text):
            markers.append(("ФИО куратора", match))
        return sorted(markers, key=lambda item: item[1].start())

    def _trim_title_role_segment(self, segment: str, label: str) -> tuple[str, int]:
        offset = 0
        underline = re.search(r"_{3,}", segment)

        if underline and label == "ФИО студента":
            segment = segment[:underline.start()]

        if underline and label == "ФИО куратора":
            offset = underline.end()
            segment = segment[offset:]

        stop = re.search(
            r"(?:^|\n)\s*(?:тюмень,\s*(?:19|20)\d{2}|содержание|аннотация|введение)\b",
            segment,
            re.IGNORECASE,
        )
        if stop:
            segment = segment[:stop.start()]

        return segment, offset
