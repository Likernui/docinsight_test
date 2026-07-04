"""
Регулярные выражения и справочники для извлечения сущностей.
"""

import re


class EntityPatternsMixin:
    DEFAULT_LABELS = [
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
        r"^[ \t]*(?:"
        r"#|//|return\b|if\b|elif\b|else:|for\b|while\b|try:|except\b|finally:|with\b|await\b|yield\b|"
        r"from\b|import\b|class\b|def\b|async\s+def\b|"
        r"[A-Za-z_][A-Za-z0-9_.]*\s*(?:=|\(|\[)|"
        r"['\"][^'\"]+['\"]\s*:|"
        r"[)\]}],?|"
        r"\.[A-Za-z_][A-Za-z0-9_]*"
        r").+",
        re.IGNORECASE,
    )

    NAME_INITIALS_PATTERN = re.compile(
        r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.?"
    )
    RUSSIAN_PERSON_NAME_PATTERN = re.compile(
        r"\b[А-ЯЁ][а-яё]{2,}(?:\s+[А-ЯЁ][а-яё]{2,}){1,2}\b"
    )
    PERSON_NAME_STOP_WORDS = (
        "фио", "студент", "студентов", "студентки", "участник", "участники",
        "руководител", "куратор", "преподавател", "дисциплин", "тема",
        "проект", "работ", "группа", "отчет", "разработк", "список",
        "качество", "аудио", "видео", "модель", "модели", "данные",
        "кнопка", "окно", "название", "серьезность", "серьёзность",
        "воспроизводимость", "голос",
    )
    COMMON_FIRST_NAMES = {
        "алексей", "александр", "альберт", "андрей", "артем", "артём",
        "виталий", "елена", "илья", "марина", "михаил", "павел", "юрий",
    }

    SUPERVISOR_MARKER_PATTERN = re.compile(
        r"\b(?:научны[йе]\s+руководител[ьи]|руководител[ьи](?:\s+проекта)?|куратор(?:ы)?|"
        r"науч\.\s*рук\.?|преподавател[ьи]|старши[йе]\s+преподавател[ьи]|доцент|ассистент|проверил[аи]?)\b",
        re.IGNORECASE,
    )
    STUDENT_MARKER_PATTERN = re.compile(
        r"\b(?:выполнил[аи]?|выполнили|обучающ(?:ийся|аяся)|"
        r"участник(?:и)?|исполнитель|разработчик(?:и)?)\b",
        re.IGNORECASE,
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
        r"(?:^|\n|[.!?]\s+)\s*(?:\d{1,2}\.?\s*)?(?:"
        r"список\s+(?:использованн(?:ой|ых)\s+)?(?:литературы|источников)|"
        r"список\s+литературы\s+и\s+источников|"
        r"использованн(?:ая|ые)\s+(?:литература|источники)|"
        r"библиографический\s+список|перечень\s+источников|references|bibliography"
        r")\s*[:.]?\s*(?=\n|$|\d{1,2}[.)]|\[\d{1,2}\])",
        re.IGNORECASE,
    )
    SOURCE_SHORT_HEADING_PATTERN = re.compile(
        r"(?:^|\n)\s*(?:\d{1,2}\.?\s*)?(?:литература|источники)\s*(?:\n|$)",
        re.IGNORECASE,
    )
    SOURCE_ITEM_MARKER_PATTERN = re.compile(
        r"(?:^|(?<=\n)|(?<=\s))(?<![№\d.])"
        r"(?:\[(\d{1,2})\]|(\d{1,2})[.)])[\s\u200b]*(?=[A-ZА-ЯЁ])"
    )
    DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
    URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
    EXPLICIT_SOURCE_PATTERN = re.compile(
        r"\[электронный\s+ресурс\]|\bURL\s*:|\bDOI\b|https?://|www\.",
        re.IGNORECASE,
    )
    SCHEDULE_ITEM_PATTERN = re.compile(
        r"\bс\s+\d{1,2}\.\d{1,2}\.\d{4}\s+по\s+\d{1,2}\.\d{1,2}\.\d{4}\b|"
        r"\b(?:полностью\s+выполнено|частично\s+выполнено|не\s+выполнено|ответственный)\b",
        re.IGNORECASE,
    )
    NEXT_SECTION_PATTERN = re.compile(
        r"(?:^|\n|[.!?]\s+)\s*\d{0,2}\.?\s*"
        r"(?:ТЕХНИЧЕСКОЕ\s+ЗАДАНИЕ|ПЛАН-ГРАФИК|[Пп]лан-график|"
        r"ПРИЛОЖЕНИ[ЕЯ]|[Пп]риложени[ея]|ТЕСТ-НАБОР|[Тт]ест-набор|"
        r"ХОД\s+РАБОТЫ|[Хх]од\s+работы|[Оо]писание\s+разработки|"
        r"[Аа]рхитектура\s+проекта)\b[^\n]*(?:\n|$)?"
    )
    SOURCE_NOISE_PATTERN = re.compile(
        r"\b(?:таблица|атрибуты\s+сущности|тип\s+данных|описание\s+атрибута|"
        r"create\s+table|foreign\s+key|primary\s+key|varchar|serial|"
        r"тюмень,\s*(?:19|20)\d{2})\b",
        re.IGNORECASE,
    )
