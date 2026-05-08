"""
Модуль предобработки текста: очистка и разбиение на фрагменты (чанки).

Особенности:
- Структурное разбиение для DOCX (по заголовкам Heading 1/2/3)
- Разбиение по предложениям с overlap из целых предложений
- Для PDF/изображений — разбиение по предложениям с overlap
"""

import re
from dataclasses import dataclass
from typing import Optional


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
        
        # Убираем переносы слов в конце строки
        text = cls._HYPHEN_BREAK.sub('', text)
        
        # Схлопываем множественные переносы
        text = cls._MULTI_NEWLINES.sub('\n\n', text)
        
        # Схлопываем множественные пробелы
        lines = text.split('\n')
        lines = [cls._MULTI_SPACES.sub(' ', line).strip() for line in lines]
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
    # Делим по предложениям: точка/!/?, за которыми следует пробел или \n
    sentences = re.split(r'(?<=[.!?])[\s\n]+', text)
    return [s.strip() for s in sentences if s.strip()]


class DocxSectionParser:
    """
    Структурный парсер DOCX текста.
    Извлекает заголовки и разбивает текст на секции.
    """
    
    @staticmethod
    def parse_from_docx(file_path: str) -> list[dict]:
        """
        Парсить DOCX файл в секции.
        
        Returns:
            Список [{"heading": str, "text": str}, ...]
            Первый элемент может быть {"heading": None, "text": "..."} — введение без заголовка
        """
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        
        try:
            doc = Document(file_path)
        except Exception as e:
            raise RuntimeError(f"Ошибка чтения DOCX: {e}")
        
        sections = []
        current_section = {"heading": None, "text": ""}
        
        # Собираем все параграфы с их стилями
        paragraphs_data = []
        for para in doc.paragraphs:
            style_name = para.style.name if para.style else ""
            text = para.text.strip()
            if not text:
                continue
            
            # Определяем является ли параграф заголовком
            is_heading = any([
                'Heading' in style_name,
                'Заголовок' in style_name,
                # Эвристика: жирный текст без точки в конце
                para.runs and para.runs[0].bold and len(text) < 100 and not text.endswith('.'),
                # Эвристика: центрированный текст без точки
                para.alignment == WD_ALIGN_PARAGRAPH.CENTER and len(text) < 100 and not text.endswith('.'),
            ])
            
            paragraphs_data.append({
                "text": text,
                "is_heading": is_heading,
                "style": style_name,
            })
        
        # Собираем секции
        for p in paragraphs_data:
            if p["is_heading"]:
                # Сохраняем текущую секцию
                if current_section["text"].strip():
                    sections.append(current_section)
                # Новая секция
                current_section = {"heading": p["text"], "text": ""}
            else:
                if current_section["text"]:
                    current_section["text"] += '\n' + p["text"]
                else:
                    current_section["text"] = p["text"]
        
        # Последний параграф
        if current_section["text"].strip():
            sections.append(current_section)
        
        return sections


class StructuralChunker:
    """
    Разбиение текста на чанки со структурным и семантическим подходом.
    
    - Для DOCX: структурное разбиение по заголовкам
    - Для PDF/изображений: разбиение по предложениям
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
    
    def chunk_from_docx(
        self,
        file_path: str
    ) -> list[TextChunk]:
        """
        Структурное разбиение DOCX файла.
        
        1. Парсим секции по заголовкам
        2. Внутри каждой секции делим на чанки по предложениям
        3. Overlap = целые предложения между соседними чанками
        
        Returns:
            Список TextChunk
        """
        # 1. Парсим секции
        doc_sections = DocxSectionParser.parse_from_docx(file_path)
        
        all_chunks = []
        
        # 2. Обрабатываем каждую секцию
        for section in doc_sections:
            section_heading = section["heading"]
            section_text = section["text"]
            
            if not section_text.strip():
                continue
            
            # Добавляем заголовок к тексту секции если есть
            if section_heading:
                full_text = f"{section_heading}\n{section_text}"
            else:
                full_text = section_text
            
            # 3. Делим секцию на чанки по предложениям
            section_chunks = self._chunk_sentences(
                full_text, file_path, 
                metadata={"section": section_heading or "Введение"}
            )
            
            all_chunks.extend(section_chunks)
        
        # Перенумеруем чанки
        for i, chunk in enumerate(all_chunks):
            chunk.chunk_index = i
        
        return all_chunks
    
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
                chunk_text = '. '.join(current_sentences)
                chunk_text = chunk_text.replace('. . ', '. ')  # cleanup
                
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
            chunk_text = '. '.join(current_sentences)
            chunk_text = chunk_text.replace('. . ', '. ')
            
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
    Полный пайплайн предобработки: очистка + структурное разбиение на чанки.
    
    Автоматически определяет DOCX файлы и применяет структурный анализ.
    Для остальных файлов использует разбиение по предложениям.
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
        # Очистка
        cleaned = self.cleaner.clean(text)
        if not cleaned:
            return []
        
        # Определяем формат
        #if file_path.lower().endswith('.docx'):
            # Структурное разбиение DOCX
            #return self.chunker.chunk_from_docx(file_path)
        #else:
            # Разбиение по предложениям
            #return self.chunker.chunk_from_text(cleaned, file_path, metadata)
        
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
