#!/usr/bin/env python3
"""
Тестовый скрипт для проверки модуля загрузки документов.

Проверяет:
- Извлечение текста из DOCX (пункт 2.1)
- Извлечение текста из PDF (пункт 2.1)
- OCR для изображений (пункт 2.2)

Использование:
    python test_document_loader.py
"""

import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent))

from src.text_extractor import DocumentLoader, DocxExtractor, PdfExtractor, ImageExtractor


def test_docx_extraction():
    """Тест извлечения текста из DOCX файлов."""
    print("=" * 60)
    print("ТЕСТ 1: Извлечение текста из DOCX (пункт 2.1)")
    print("=" * 60)

    # Ищем DOCX файлы в корневой папке
    root_dir = Path(__file__).parent
    docx_files = list(root_dir.glob("*.docx"))

    # Фильтруем временные файлы
    docx_files = [f for f in docx_files if not f.name.startswith('~$')]

    if not docx_files:
        print("\n⚠️  DOCX файлы не найдены")
        print(f"   Проверьте папку: {root_dir}")
        print()
        return

    extractor = DocxExtractor()

    for file_path in docx_files:
        print(f"\n📄 Файл: {file_path.name}")
        print("-" * 60)
        try:
]            print(f"✅ Успешно! Символов: {len(text)}")
            print(f"   Слов: {len(text.split())}")
            print(f"\nПервые 500 символов:")
            print(f"   {text[:500]}...")
        except Exception as e:
            print(f"❌ Ошибка: {e}")

    print()


def test_pdf_extraction():
    """Тест извлечения текста из PDF файлов."""
    print("=" * 60)
    print("ТЕСТ 2: Извлечение текста из PDF (пункт 2.1)")
    print("=" * 60)

    # Ищем PDF файлы в корневой папке
    root_dir = Path(__file__).parent
    pdf_files = list(root_dir.glob("*.pdf"))

    if not pdf_files:
        print("\n⚠️  PDF файлы не найдены в директории")
        print("   Для теста добавьте .pdf файлы в папку проекта")
        print()
        return

    extractor = PdfExtractor()

    for file_path in pdf_files:
        print(f"\n📄 Файл: {file_path.name}")
        print("-" * 60)
        try:
            text = extractor.extract(str(file_path))
            print(f"✅ Успешно! Символов: {len(text)}")
            print(f"   Слов: {len(text.split())}")
            print(f"\nПервые 500 символов:")
            print(f"   {text[:500]}...")
        except Exception as e:
            print(f"❌ Ошибка: {e}")

    print()


def test_ocr_extraction():
    """Тест OCR для изображений."""
    print("=" * 60)
    print("ТЕСТ 3: OCR для сканированных документов (пункт 2.2)")
    print("=" * 60)

    # Ищем изображения в корневой папке и в data/
    root_dir = Path(__file__).parent
    image_files = list(root_dir.glob("*.jpg")) + \
                  list(root_dir.glob("*.png"))

    # Также проверяем изображения в data/
    data_dir = root_dir / "data"
    if data_dir.exists():
        image_files.extend(list(data_dir.glob("*.jpg")))
        image_files.extend(list(data_dir.glob("*.png")))

    if not image_files:
        print("\n⚠️  Изображения не найдены в директории")
        print("   Для теста добавьте .jpg или .png файлы в папку проекта")
        print()
        return

    extractor = ImageExtractor(languages=['ru', 'en'])

    for file_path in image_files:
        print(f"\n🖼️  Файл: {file_path.name}")
        print("-" * 60)
        try:
            text = extractor.extract(str(file_path))
            if text.strip():
                print(f"✅ Успешно! Символов: {len(text)}")
                print(f"   Слов: {len(text.split())}")
                print(f"\nРаспознанный текст:")
                print(f"   {text[:500]}...")
            else:
                print("⚠️  Текст не распознан (возможно, изображение без текста)")
        except Exception as e:
            print(f"❌ Ошибка: {e}")

    print()


def test_universal_loader():
    """Тест универсального загрузчика."""
    print("=" * 60)
    print("ТЕСТ 4: Универсальный загрузчик (все форматы)")
    print("=" * 60)

    loader = DocumentLoader()

    # Собираем все файлы из корневой папки
    root_dir = Path(__file__).parent
    all_files = []

    # DOCX (исключая временные)
    for f in root_dir.glob("*.docx"):
        if not f.name.startswith('~$'):
            all_files.append(str(f))

    # Изображения из data/
    data_dir = root_dir / "data"
    if data_dir.exists():
        for img in data_dir.glob("*.png"):
            all_files.append(str(img))
        for img in data_dir.glob("*.jpg"):
            all_files.append(str(img))

    if not all_files:
        print("\n⚠️  Файлы не найдены для теста")
        print()
        return

    print(f"\n📁 Всего файлов: {len(all_files)}")
    print("-" * 60)

    def progress_callback(current, total, filename):
        print(f"  Прогресс: {current}/{total} — {Path(filename).name}")

    results = loader.load_multiple(all_files, progress_callback=progress_callback)

    print("\n📊 Результаты:")
    print("-" * 60)
    for file_path, text in results.items():
        status = "✅" if text.strip() else "⚠️ "
        print(f"{status} {Path(file_path).name}: {len(text)} символов")

    print()


def main():
    """Запуск всех тестов."""
    print("\n" + "=" * 60)
    print("DOCINSIGHT — Тестирование модуля загрузки документов")
    print("Пункты 2.1 и 2.2 из плана")
    print("=" * 60 + "\n")

    # Тест 1: DOCX
    test_docx_extraction()

    # Тест 2: PDF
    test_pdf_extraction()

    # Тест 3: OCR
    test_ocr_extraction()

    # Тест 4: Универсальный загрузчик
    test_universal_loader()

    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)


if __name__ == "__main__":
    main()
