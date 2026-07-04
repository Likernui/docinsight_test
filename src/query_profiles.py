"""
Профили семантических запросов для поиска сущностей.

GUI не показывает эти запросы пользователю. Они нужны только для выбора
фрагментов, где с большей вероятностью есть нужные сущности.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryProfile:
    entity_type: str
    labels: tuple[str, ...]
    queries: tuple[str, ...]
    top_k: int = 8
    use_gliner: bool = True


QUERY_PROFILES: dict[str, QueryProfile] = {
    "students": QueryProfile(
        entity_type="students",
        labels=("ФИО студента",),
        queries=(
            "кто выполнил работу студенты авторы проекта",
            "выполнил студент группа авторы участники проекта",
            "ФИО студентов участников проекта",
        ),
        top_k=10,
    ),
    "supervisors": QueryProfile(
        entity_type="supervisors",
        labels=("ФИО куратора",),
        queries=(
            "руководитель проекта научный руководитель преподаватель",
            "куратор преподаватель проверил работу",
            "ФИО руководителя проекта",
        ),
        top_k=8,
    ),
    "project_topics": QueryProfile(
        entity_type="project_topics",
        labels=("тема проекта", "тема работы", "название проекта"),
        queries=(
            "тема проекта название проекта тема работы",
            "отчет реализации проекта по дисциплине",
            "разработка системы проекта название работы",
        ),
        top_k=10,
    ),
    "disciplines": QueryProfile(
        entity_type="disciplines",
        labels=("дисциплина",),
        queries=(
            "по дисциплине название дисциплины",
            "дисциплина учебный курс предмет",
            "отчет по дисциплине",
        ),
        top_k=8,
    ),
    "technologies": QueryProfile(
        entity_type="technologies",
        labels=("технология",),
        queries=(
            "стек технологий использованные технологии фреймворки библиотеки",
            "язык программирования база данных backend frontend",
            "инструменты разработки модели сервисы инфраструктура",
        ),
        top_k=12,
    ),
    "code_fragments": QueryProfile(
        entity_type="code_fragments",
        labels=("фрагмент программного кода",),
        queries=(
            "фрагмент программного кода функция класс алгоритм",
            "пример кода листинг исходный код",
            "реализация функции программный модуль",
        ),
        top_k=10,
        use_gliner=False,
    ),
    "sources": QueryProfile(
        entity_type="sources",
        labels=("источник",),
        queries=(
            "список использованной литературы источники references bibliography",
            "библиографический список литература arxiv cyberleninka",
        ),
        top_k=5,
        use_gliner=False,
    ),
}


def get_profiles(entity_types: list[str] | tuple[str, ...] | None = None) -> list[QueryProfile]:
    if not entity_types:
        return list(QUERY_PROFILES.values())

    return [QUERY_PROFILES[entity_type] for entity_type in entity_types]
