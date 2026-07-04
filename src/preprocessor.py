"""
Модуль предобработки текста: очистка и разбиение на фрагменты (чанки).

Особенности:
- Разбиение по предложениям с overlap из целых предложений
- Для DOCX/PDF/изображений используется уже извлечённый текст
"""

import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    """
    Один фрагмент текста с метаданными.
    
    Attributes:
        text: Очищенный текст чанка
        file_path: Путь к исходному файлу
        chunk_index: Индекс чанка (0, 1, 2...)
        metadata: Дополнительные метаданные (раздел, страница и т.д.)
    """
    text: str
    file_path: str
    chunk_index: int
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def __len__(self):
        return len(self.text)
    
    def __repr__(self):
        preview = self.text[:50].replace('\n', ' ')
        return f"TextChunk(index={self.chunk_index}, preview='{preview}...')"


class TextCleaner:
    """
    Очистка текста от мусора и нормализация.
    """
    
    _MULTI_NEWLINES = re.compile(r'\n{3,}')
    _MULTI_SPACES = re.compile(r' {2,}')
    _HYPHEN_BREAK = re.compile(r'-\s*\n')
    
    @classmethod
    def clean(cls, text: str) -> str:
        """
        Очистить текст от мусора и нормализовать.
        
        Args:
            text: Сырой текст
            
        Returns:
            Очищенный текст
        """
        if not text or not text.strip():
            return ""

        # Word often stores code indentation as non-breaking spaces.
        text = text.replace('\u00a0', ' ')
        
        # Убираем переносы слов в конце строки
        text = cls._HYPHEN_BREAK.sub('', text)
        
        # Схлопываем множественные переносы
        text = cls._MULTI_NEWLINES.sub('\n\n', text)
        
        # Схлопываем множественные пробелы, но сохраняем ведущие отступы.
        # Они важны для программного кода внутри отчетов.
        lines = text.split('\n')
        lines = [
            line.rstrip() if line[:1].isspace() else cls._MULTI_SPACES.sub(' ', line).strip()
            for line in lines
        ]
        text = '\n'.join(lines)
        
        return text.strip()


def split_sentences(text: str) -> list[str]:
    """
    Разбить текст на предложения, сохраняя структуру.
    
    Делит по точкам/!/?, но сохраняет переносы строк как отдельные "предложения"
    если они выглядят как заголовки.
    
    Returns:
        Список предложений
    """
    # Не режем нумерованные списки после "1. ", иначе источник превращается
    # в отдельный маркер "1." и отдельный текст пункта.
    marker = "\uE000"
    protected = re.sub(
        r"(?:(?<=^)|(?<=\s))(\d{1,2})\.\s+(?=[A-ZА-ЯЁ])",
        rf"\1.{marker}",
        text,
    )

    sentences = re.split(r'(?<=[.!?])[\s\n]+', protected)
    return [
        sentence.replace(marker, " ").strip()
        for sentence in sentences
        if sentence.strip()
    ]


class StructuralChunker:
    """
    Разбиение текста на чанки.
    
    - Overlap = целые предложения, не обрезанные символы
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        overlap_sentences: int = 2,
    ):
        """
        Args:
            chunk_size: Целевой размер чанка в символах
            overlap_sentences: Количество предложений для overlap (2 = последние 2 предложения повторяются)
        """
        self.chunk_size = chunk_size
        self.overlap_sentences = overlap_sentences
    
    def chunk_from_text(
        self,
        text: str,
        file_path: str = '',
        metadata: dict = None
    ) -> list[TextChunk]:
        """
        Разбиение сырого текста (PDF, изображения, произвольный текст).
        
        Args:
            text: Текст для разбиения
            file_path: Путь к исходному файлу
            metadata: Метаданные
            
        Returns:
            Список TextChunk
        """
        return self._chunk_sentences(text, file_path, metadata)
    
    def _chunk_sentences(
        self,
        text: str,
        file_path: str,
        metadata: dict = None
    ) -> list[TextChunk]:
        """
        Разбить текст на чанки по предложениям с overlap из целых предложений.
        
        Алгоритм:
        1. Делим текст на предложения
        2. Копим предложения пока не наберём ~chunk_size
        3. Сохраняем чанк
        4. Новый чанк начинаем с последних overlap_sentences предложений предыдущего
        """
        if not text or not text.strip():
            return []
        
        sentences = split_sentences(text)
        if not sentences:
            return []
        
        chunks = []
        current_sentences = []
        current_len = 0
        
        for sentence in sentences:
            current_sentences.append(sentence)
            current_len += len(sentence)
            
            # Если набрали достаточно — сохраняем чанк
            if current_len >= self.chunk_size:
                chunk_text = ' '.join(current_sentences)
                
                chunk_metadata = (metadata.copy() if metadata else {})
                chunks.append(TextChunk(
                    text=chunk_text.strip(),
                    file_path=file_path,
                    chunk_index=len(chunks),
                    metadata=chunk_metadata
                ))
                
                # Overlap = последние N предложений
                if self.overlap_sentences > 0 and len(current_sentences) >= self.overlap_sentences:
                    overlap = current_sentences[-self.overlap_sentences:]
                    current_sentences = overlap
                    current_len = sum(len(s) for s in current_sentences)
                else:
                    current_sentences = []
                    current_len = 0
        
        # Последний чанк
        if current_sentences:
            chunk_text = ' '.join(current_sentences)
            
            chunk_metadata = (metadata.copy() if metadata else {})
            chunks.append(TextChunk(
                text=chunk_text.strip(),
                file_path=file_path,
                chunk_index=len(chunks),
                metadata=chunk_metadata
            ))
        
        return chunks


class TextPreprocessor:
    """
    Полный пайплайн предобработки: очистка + разбиение на чанки.
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        overlap_sentences: int = 2,
    ):
        """
        Args:
            chunk_size: Целевой размер чанка в символах
            overlap_sentences: Количество предложений для overlap
        """
        self.cleaner = TextCleaner()
        self.chunker = StructuralChunker(
            chunk_size=chunk_size,
            overlap_sentences=overlap_sentences
        )
    
    def process(
        self,
        text: str,
        file_path: str = '',
        metadata: dict = None
    ) -> list[TextChunk]:
        """
        Полный пайплайн: очистить текст и разбить на чанки.
        
        Args:
            text: Сырой текст
            file_path: Путь к файлу
            metadata: Дополнительные метаданные
            
        Returns:
            Список чанков
        """
        cleaned = self.cleaner.clean(text)
        if not cleaned:
            return []
        
        # Для всех форматов используем уже извлечённый текст,
        # потому что DocumentLoader уже достал и параграфы, и таблицы.
        return self.chunker.chunk_from_text(cleaned, file_path, metadata)
    
    def process_documents(
        self,
        documents: dict[str, str],
        progress_callback=None
    ) -> dict[str, list[TextChunk]]:
        """
        Обработать несколько документов.
        
        Args:
            documents: Словарь {file_path: text}
            progress_callback: Callback(current, total, filename)
            
        Returns:
            Словарь {file_path: [TextChunk, ...]}
        """
        results = {}
        total = len(documents)
        
        for i, (file_path, text) in enumerate(documents.items()):
            from pathlib import Path
            filename = Path(file_path).name if file_path else 'unknown'
            
            chunks = self.process(text, file_path)
            results[file_path] = chunks
            
            if progress_callback:
                progress_callback(i + 1, total, filename)
        
        return results
