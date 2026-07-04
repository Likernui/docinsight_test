"""
Правила извлечения фрагментов программного кода.
"""

import re
from typing import Any


class CodeRulesMixin:
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
