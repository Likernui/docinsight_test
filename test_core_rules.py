"""
Простые тесты базовых правил DocInsight.

Тесты не запускают GUI, GLiNER, PDF и OCR. Они проверяют правила,
которые важны для результата и легко ломаются при доработках.
"""

from src.entity_extractor import EntityExtractor
from src.entity_service import EntityService
from src.preprocessor import TextChunk


def make_extractor() -> EntityExtractor:
    return EntityExtractor(load_model=False)


def test_sources_extracted_as_one_block():
    print("Проверка: список литературы извлекается одной сущностью-блоком")
    extractor = make_extractor()
    text = """
Введение

Список использованной литературы
1. Иванов И.И. Основы анализа данных. - Москва, 2020.
2. Петров П.П. Машинное обучение. - Санкт-Петербург, 2021.
"""

    entities = extractor.extract_sources(text)

    assert len(entities) == 1
    assert entities[0]["label"] == "источник"
    assert entities[0]["source_count"] == 2
    assert "Иванов" in entities[0]["text"]
    assert "Петров" in entities[0]["text"]


def test_schedule_is_not_source():
    print("Проверка: план-график не считается списком источников")
    extractor = make_extractor()
    text = """
План-график выполнения проекта
1. Постановка задачи.
2. Разработка интерфейса.
3. Подготовка отчета.
"""

    entities = extractor.extract_sources(text, bottom_section=True)

    assert entities == []


def test_code_block_extracted_as_one_entity():
    print("Проверка: функция извлекается одним кодовым блоком")
    extractor = make_extractor()
    text = """
Ниже приведен фрагмент программы:

def assess_answer(answer):
    score = len(answer)
    return score
"""

    entities = extractor.extract_regex_entities(text, include_sources=False)
    code_entities = [
        entity
        for entity in entities
        if entity["label"] == "фрагмент программного кода"
    ]

    assert len(code_entities) == 1
    assert code_entities[0]["title"] == "функция assess_answer"
    assert "return score" in code_entities[0]["code"]


def test_single_return_is_ignored():
    print("Проверка: одиночный return не считается кодовым фрагментом")
    extractor = make_extractor()
    text = "Алгоритм завершает работу и возвращает результат.\nreturn score"

    entities = extractor.extract_regex_entities(text, include_sources=False)
    code_entities = [
        entity
        for entity in entities
        if entity["label"] == "фрагмент программного кода"
    ]

    assert code_entities == []


def test_flatten_entities_for_ui():
    print("Проверка: сущности преобразуются в строки для пользовательского UI")
    chunk = TextChunk(
        text="def assess_answer(answer):\n    return len(answer)",
        file_path="/tmp/report.docx",
        chunk_index=0,
        metadata={
            "entities": [
                {
                    "label": "фрагмент программного кода",
                    "text": "функция assess_answer",
                    "title": "функция assess_answer",
                    "code": "def assess_answer(answer):\n    return len(answer)",
                    "score": 1.0,
                    "source": "regex",
                    "chunk_indexes": [0],
                }
            ]
        },
    )

    rows = EntityService().flatten_entities({chunk.file_path: [chunk]})

    assert len(rows) == 1
    assert rows[0]["type"] == "фрагмент программного кода"
    assert rows[0]["value"] == "функция assess_answer"
    assert rows[0]["document"] == "report.docx"
    assert rows[0]["chunk_indexes"] == [0]
    assert rows[0]["confidence"] == 1.0
    assert rows[0]["source"] == "regex"
    assert "code" in rows[0]["metadata"]
