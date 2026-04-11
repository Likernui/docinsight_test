#!/usr/bin/env python3
"""
Тестовое окно для проверки модулей:
- text_extractor.py (загрузка документов)
- preprocessor.py (очистка и разбиение на чанки)

Запуск:
    python test_gui.py
"""

import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QFileDialog,
    QLabel,
    QProgressBar,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTabWidget,
    QComboBox,
    QSpinBox,
    QGroupBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import html as html_module

from src.text_extractor import DocumentLoader
from src.preprocessor import TextPreprocessor


class WorkerThread(QThread):
    """Поток для длительных операций — использует только сигналы, не callback'и"""
    progress = pyqtSignal(int, int, str)  # current, total, filename
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, operation, *args, **kwargs):
        super().__init__()
        self.operation = operation
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            # Если операция поддерживает progress_callback, подставляем свой
            result = self.operation(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class TestWindow(QMainWindow):
    """Тестовое окно для проверки загрузки документов и предобработки"""

    def __init__(self):
        super().__init__()
        self.loader = DocumentLoader()
        self.file_paths = []
        self.extracted_texts = {}
        
        # Препроцессор и чанки
        self.preprocessor = TextPreprocessor()
        self.chunks = {}  # {file_path: [TextChunk, ...]}
        
        self._init_ui()
        self._setup_styles()

    def _init_ui(self):
        """Инициализация интерфейса"""
        self.setMinimumSize(1200, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Заголовок (по центру)
        title = QLabel("🧪 Тест DocInsight — Загрузка + Предобработка")
        title.setObjectName("title")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Разделитель
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # ===== ЛЕВАЯ ПАНЕЛЬ =====
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # --- СЕКЦИЯ: ЗАГРУЗКА ФАЙЛОВ ---
        load_group = QGroupBox("📁 Загрузка документов")
        load_layout = QVBoxLayout(load_group)

        self.btn_load = QPushButton("📁 Выбрать файлы")
        self.btn_load.setFixedHeight(45)
        self.btn_load.setStyleSheet("font-size: 14px;")
        self.btn_load.clicked.connect(self._load_files)
        load_layout.addWidget(self.btn_load)

        self.lbl_file_count = QLabel("Загружено файлов: 0")
        self.lbl_file_count.setObjectName("file_count")
        self.lbl_file_count.setFont(QFont("Arial", 11))
        load_layout.addWidget(self.lbl_file_count)

        self.file_list = QListWidget()
        self.file_list.setAlternatingRowColors(False)
        load_layout.addWidget(self.file_list)

        # Прогресс бар
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        load_layout.addWidget(self.progress)

        # Кнопки извлечения
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_extract = QPushButton("⚙️ Извлечь текст")
        self.btn_extract.setFixedHeight(40)
        self.btn_extract.clicked.connect(self._extract_all)
        self.btn_extract.setEnabled(False)
        btn_layout.addWidget(self.btn_extract)

        load_layout.addLayout(btn_layout)
        left_layout.addWidget(load_group)

        # --- СЕКЦИЯ: ПРЕДОБРАБОТКА ---
        preprocess_group = QGroupBox("🔧 Предобработка текста")
        preprocess_layout = QVBoxLayout(preprocess_group)

        # Размер чанка
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Размер чанка:"))
        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(200, 2000)
        self.chunk_size_spin.setValue(500)
        self.chunk_size_spin.setSingleStep(50)
        size_layout.addWidget(self.chunk_size_spin)
        size_layout.addWidget(QLabel("симв."))
        preprocess_layout.addLayout(size_layout)

        # Overlap
        overlap_layout = QHBoxLayout()
        overlap_layout.addWidget(QLabel("Overlap:"))
        self.chunk_overlap_spin = QSpinBox()
        self.chunk_overlap_spin.setRange(0, 5)
        self.chunk_overlap_spin.setValue(2)
        self.chunk_overlap_spin.setSingleStep(1)
        overlap_layout.addWidget(self.chunk_overlap_spin)
        overlap_layout.addWidget(QLabel("предл."))
        preprocess_layout.addLayout(overlap_layout)

        # Кнопка предобработки
        self.btn_preprocess = QPushButton("🔪 Предобработать")
        self.btn_preprocess.setFixedHeight(40)
        self.btn_preprocess.clicked.connect(self._preprocess_all)
        self.btn_preprocess.setEnabled(False)
        preprocess_layout.addWidget(self.btn_preprocess)

        left_layout.addWidget(preprocess_group)

        # Кнопка очистки
        self.btn_clear = QPushButton("🗑️ Очистить всё")
        self.btn_clear.setFixedHeight(40)
        self.btn_clear.clicked.connect(self._clear)
        left_layout.addWidget(self.btn_clear)

        # ===== ПРАВАЯ ПАНЕЛЬ =====
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Переключатель файлов
        file_selector_layout = QHBoxLayout()
        file_selector_layout.addWidget(QLabel("Файл:"))
        self.file_selector = QComboBox()
        self.file_selector.setFixedWidth(400)
        self.file_selector.currentIndexChanged.connect(self._on_file_selected)
        file_selector_layout.addWidget(self.file_selector)
        file_selector_layout.addStretch()
        right_layout.addLayout(file_selector_layout)

        # Вкладки
        self.tabs = QTabWidget()

        # Вкладка 1: Результат (сырой текст)
        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setFont(QFont("Menlo", 10))
        self.txt_result.setPlaceholderText("Здесь появится полный текст извлечённых документов...")
        self.txt_result.document().setMaximumBlockCount(1000000)
        self.tabs.addTab(self.txt_result, "📄 Сырой текст")

        # Вкладка 2: Чанки
        self.txt_chunks = QTextEdit()
        self.txt_chunks.setReadOnly(True)
        self.txt_chunks.setFont(QFont("Menlo", 10))
        self.txt_chunks.setPlaceholderText("Здесь появятся чанки после предобработки...")
        self.txt_chunks.document().setMaximumBlockCount(1000000)
        self.tabs.addTab(self.txt_chunks, "🔪 Чанки")

        # Вкладка 3: Статистика
        self.txt_stats = QTextEdit()
        self.txt_stats.setReadOnly(True)
        self.txt_stats.setFont(QFont("Menlo", 10))
        self.txt_stats.setPlaceholderText("Статистика по файлам и чанкам...")
        self.tabs.addTab(self.txt_stats, "📊 Статистика")

        right_layout.addWidget(self.tabs)

        # Добавляем панели в splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        # Статус бар
        self.statusBar().showMessage("Готов к работе")

    def _setup_styles(self):
        """Настройка стилей"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
            }

            QLabel#title {
                color: #e94560;
                padding: 10px 0;
            }

            QLabel#subtitle {
                color: #888;
                font-size: 13px;
                margin-bottom: 15px;
            }

            QGroupBox {
                color: #e94560;
                font-size: 13px;
                font-weight: bold;
                border: 2px solid #0f3460;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }

            QPushButton {
                background-color: #0f3460;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e94560;
            }
            QPushButton:pressed {
                background-color: #c73e54;
            }
            QPushButton:disabled {
                background-color: #2a2a4a;
                color: #666;
            }

            QTextEdit {
                background-color: #16213e;
                color: #eee;
                border: 2px solid #0f3460;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border: 2px solid #e94560;
            }

            QListWidget {
                background-color: #16213e;
                color: #eee;
                border: 2px solid #0f3460;
                border-radius: 8px;
                padding: 8px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #0f3460;
            }
            QListWidget::item:hover {
                background-color: #1a3a5c;
            }

            QProgressBar {
                background-color: #16213e;
                border: none;
                border-radius: 8px;
                text-align: center;
                color: #eee;
                font-weight: bold;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #e94560;
                border-radius: 8px;
            }

            QComboBox, QSpinBox {
                background-color: #16213e;
                color: #eee;
                border: 2px solid #0f3460;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #16213e;
                color: #eee;
                border: 2px solid #0f3460;
                selection-background-color: #0f3460;
            }

            QLabel#file_count {
                color: #888;
                font-size: 12px;
                padding: 5px;
            }

            QStatusBar {
                background-color: #16213e;
                color: #888;
                border-top: 1px solid #0f3460;
            }

            QTabWidget::pane {
                border: 2px solid #0f3460;
                border-radius: 8px;
                background-color: #16213e;
            }
            QTabBar::tab {
                background-color: #1a1a2e;
                color: #888;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #16213e;
                color: #e94560;
            }
            QTabBar::tab:hover {
                color: #eee;
            }
        """)

    def _load_files(self):
        """Открыть диалог выбора файлов"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы",
            "",
            "Все файлы (*.docx *.pdf *.png *.jpg *.jpeg)"
        )

        if files:
            self.file_paths.extend(files)
            self._update_file_list()
            self.btn_extract.setEnabled(True)
            self.statusBar().showMessage(f"Добавлено файлов: {len(self.file_paths)}")

    def _update_file_list(self):
        """Обновить список файлов в UI"""
        self.file_list.clear()

        for file_path in self.file_paths:
            file_name = Path(file_path).name
            item = QListWidgetItem(f"📄 {file_name}")
            item.setData(Qt.ItemDataRole.UserRole, file_path)

            # Статус обработки
            if file_path in self.extracted_texts:
                text = self.extracted_texts[file_path]
                if text.strip():
                    item.setText(f"✅ {file_name} ({len(text)} симв.)")
                else:
                    item.setText(f"⚠️ {file_name} (пусто)")

            self.file_list.addItem(item)

        self.lbl_file_count.setText(f"Загружено файлов: {len(self.file_paths)}")

    def _extract_all(self):
        """Извлечь текст из всех файлов"""
        if not self.file_paths:
            QMessageBox.warning(self, "Внимание", "Сначала выберите файлы!")
            return

        self._log(f"Начало извлечения текста из {len(self.file_paths)} файлов...")
        self.progress.setVisible(True)
        self.progress.setMaximum(0)  # Бесконечный прогресс
        self.progress.setValue(0)
        self.btn_extract.setEnabled(False)
        self.btn_load.setEnabled(False)
        self.statusBar().showMessage("Извлечение текста...")

        def on_finished(results):
            self.extracted_texts = results
            self.btn_extract.setEnabled(True)
            self.btn_load.setEnabled(True)
            self.btn_preprocess.setEnabled(True)
            self.progress.setVisible(False)
            self.statusBar().showMessage("Текст извлечён!")

            self._update_file_list()
            self._update_file_selector()

            total_chars = sum(len(t) for t in results.values())
            total_chars_no_spaces = sum(len(t.replace(' ', '').replace('\n', '')) for t in results.values())
            total_words = sum(len(t.split()) for t in results.values())

            self._show_stats(results, total_chars, total_chars_no_spaces, total_words)

            if results:
                first_file = list(results.keys())[0]
                first_name = Path(first_file).name
                first_text = results[first_file]
                self._show_raw_result(first_name, first_text)
                self._log(f"Всего извлечено: {total_chars} символов, {total_words} слов")

        def on_error(error):
            self._log(f"Ошибка: {error}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка извлечения текста:\n{error}")
            self.btn_extract.setEnabled(True)
            self.btn_load.setEnabled(True)
            self.progress.setVisible(False)

        self.worker = WorkerThread(
            self.loader.load_multiple,
            self.file_paths
        )
        self.worker.finished.connect(on_finished)
        self.worker.error.connect(on_error)
        self.worker.start()

    def _preprocess_all(self):
        """Предобработать все извлечённые тексты"""
        if not self.extracted_texts:
            QMessageBox.warning(self, "Внимание", "Сначала извлеките текст!")
            return

        # Обновляем параметры препроцессора
        self.preprocessor = TextPreprocessor(
            chunk_size=self.chunk_size_spin.value(),
            overlap_sentences=self.chunk_overlap_spin.value()
        )

        self._log(f"Начало предобработки {len(self.extracted_texts)} файлов...")
        self.progress.setVisible(True)
        self.progress.setMaximum(0)  # Бесконечный прогресс
        self.progress.setValue(0)
        self.btn_preprocess.setEnabled(False)
        self.btn_extract.setEnabled(False)
        self.statusBar().showMessage("Предобработка текста...")

        def on_finished(results):
            self.chunks = results
            self.btn_preprocess.setEnabled(True)
            self.btn_load.setEnabled(True)
            self.btn_extract.setEnabled(True)
            self.progress.setVisible(False)

            # Считаем
            total_chunks = sum(len(c) for c in results.values())
            total_chunk_chars = sum(
                len(chunk.text)
                for chunks_list in results.values()
                for chunk in chunks_list
            )

            self.statusBar().showMessage(f"Предобработка завершена! Создано чанков: {total_chunks}")
            self._log(
                f"Создано {total_chunks} чанков, "
                f"{total_chunk_chars} символов в чанках"
            )

            # Сначала показываем чанки первого файла
            if results:
                first_file = list(results.keys())[0]
                file_name = Path(first_file).name
                file_chunks = results[first_file]
                self._show_chunks(file_name, file_chunks)

            # Потом обновляем статистику
            total_chars = sum(len(t) for t in self.extracted_texts.values())
            self._show_stats_with_chunks(
                self.extracted_texts, results, total_chars, total_chunks
            )

            # Обновляем список файлов
            self._update_file_list()

        def on_error(error):
            self._log(f"Ошибка: {error}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка предобработки:\n{error}")
            self.btn_preprocess.setEnabled(True)
            self.btn_extract.setEnabled(True)
            self.progress.setVisible(False)

        self.worker = WorkerThread(
            self.preprocessor.process_documents,
            self.extracted_texts
        )
        self.worker.finished.connect(on_finished)
        self.worker.error.connect(on_error)
        self.worker.start()

    def _show_raw_result(self, file_name, text):
        """Показать сырой текст"""
        if len(text) > 50000:
            html_text = f'''
            <div style="background-color: #1a1a2e; padding: 20px; border-radius: 8px;">
                <div style="color: #e94560; font-size: 18px; font-weight: bold; margin-bottom: 15px;">
                    📄 {file_name} (СЫРОЙ ТЕКСТ)
                </div>
                <div style="color: #888; font-size: 12px; margin-bottom: 20px; padding: 10px; background-color: #0f3460; border-radius: 6px;">
                    <b>Символов:</b> <span style="color: #e94560;">{len(text)}</span> |
                    <b>Слов:</b> <span style="color: #e94560;">{len(text.split())}</span> |
                    <b>Строк:</b> <span style="color: #e94560;">{len(text.splitlines())}</span>
                </div>
                <div style="color: #eee; line-height: 1.6; white-space: pre-wrap; font-size: 11px; font-family: monospace;">
                    {text}
                </div>
            </div>
            '''
        else:
            html_text = f'''
            <div style="background-color: #1a1a2e; padding: 20px; border-radius: 8px;">
                <div style="color: #e94560; font-size: 18px; font-weight: bold; margin-bottom: 15px;">
                    📄 {file_name} (СЫРОЙ ТЕКСТ)
                </div>
                <div style="color: #888; font-size: 12px; margin-bottom: 20px; padding: 10px; background-color: #0f3460; border-radius: 6px;">
                    <b>Символов:</b> <span style="color: #e94560;">{len(text)}</span> |
                    <b>Слов:</b> <span style="color: #e94560;">{len(text.split())}</span> |
                    <b>Строк:</b> <span style="color: #e94560;">{len(text.splitlines())}</span>
                </div>
                <div style="color: #eee; line-height: 1.8; white-space: pre-wrap; font-size: 13px;">
                    {text}
                </div>
            </div>
            '''
        self.txt_result.setHtml(html_text)
        self.txt_result.verticalScrollBar().setValue(0)

    def _show_chunks(self, file_name, chunks):
        """Показать ВСЕ чанки файла списком с прокруткой"""
        if not chunks:
            self.txt_chunks.setHtml('''
            <div style="background-color: #1a1a2e; padding: 20px; border-radius: 8px;">
                <div style="color: #888; font-size: 14px;">Нет чанков</div>
            </div>
            ''')
            return

        total = len(chunks)
        html_text = f'''
        <div style="background-color: #1a1a2e; padding: 20px; border-radius: 8px;">
            <div style="color: #e94560; font-size: 18px; font-weight: bold; margin-bottom: 15px;">
                🔪 {file_name} — {total} чанков
            </div>
        '''

        for chunk in chunks:
            html_text += f'''
            <div style="background-color: #16213e; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #e94560;">
                <div style="color: #e94560; font-size: 13px; font-weight: bold; margin-bottom: 8px;">
                    Чанк #{chunk.chunk_index + 1} из {total}
                </div>
                <div style="color: #888; font-size: 11px; margin-bottom: 8px;">
                    <b>Символов:</b> <span style="color: #e94560;">{len(chunk.text)}</span> |
                    <b>Слов:</b> <span style="color: #e94560;">{len(chunk.text.split())}</span>
                </div>
                <div style="color: #eee; line-height: 1.6; white-space: pre-wrap; font-size: 12px; background-color: #0f3460; padding: 10px; border-radius: 6px;">
                    {html_module.escape(chunk.text)}
                </div>
            </div>
            '''

        html_text += '</div>'
        self.txt_chunks.setHtml(html_text)
        self.txt_chunks.verticalScrollBar().setValue(0)

    def _update_file_selector(self):
        """Обновить переключатель файлов"""
        self.file_selector.clear()
        for file_path in self.file_paths:
            file_name = Path(file_path).name
            self.file_selector.addItem(f"📄 {file_name}", file_path)

    def _on_file_selected(self, index):
        """При выборе файла показать его текст и чанки"""
        if index >= 0 and index < len(self.file_paths):
            file_path = self.file_paths[index]
            file_name = Path(file_path).name

            # Сырой текст
            if file_path in self.extracted_texts:
                text = self.extracted_texts[file_path]
                self._show_raw_result(file_name, text)

            # Чанки
            if file_path in self.chunks:
                chunks = self.chunks[file_path]
                self._show_chunks(file_name, chunks)

    def _show_stats(self, results, total_chars, total_chars_no_spaces, total_words):
        """Показать статистику по файлам (без чанков)"""
        html_text = f'''
        <div style="background-color: #1a1a2e; padding: 20px; border-radius: 8px;">
            <div style="color: #e94560; font-size: 18px; font-weight: bold; margin-bottom: 20px;">
                📊 Статистика извлечения текста
            </div>

            <div style="background-color: #0f3460; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <div style="color: #eee; font-size: 14px;">
                    <div style="margin-bottom: 10px;">
                        <b>Всего файлов:</b> <span style="color: #e94560; font-size: 16px;">{len(results)}</span>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <b>Всего символов:</b> <span style="color: #e94560; font-size: 16px;">{total_chars}</span>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <b>Без пробелов:</b> <span style="color: #e94560; font-size: 16px;">{total_chars_no_spaces}</span>
                    </div>
                    <div>
                        <b>Всего слов:</b> <span style="color: #e94560; font-size: 16px;">{total_words}</span>
                    </div>
                </div>
            </div>

            <div style="color: #888; font-size: 13px; margin-bottom: 10px;">
                <b>Детали по файлам:</b>
            </div>
        '''

        for file_path, text in results.items():
            file_name = Path(file_path).name
            chars = len(text)
            words = len(text.split())
            lines = len(text.splitlines())

            status_icon = "✅" if text.strip() else "⚠️"

            html_text += f'''
            <div style="background-color: #16213e; padding: 12px; margin: 8px 0; border-radius: 6px; border-left: 4px solid {'#e94560' if text.strip() else '#888'};">
                <div style="color: #eee; font-size: 14px; font-weight: bold; margin-bottom: 8px;">
                    {status_icon} {file_name}
                </div>
                <div style="color: #888; font-size: 12px; display: flex; gap: 20px;">
                    <span>Символов: <b style="color: #e94560;">{chars}</b></span>
                    <span>Слов: <b style="color: #e94560;">{words}</b></span>
                    <span>Строк: <b style="color: #e94560;">{lines}</b></span>
                </div>
            </div>
            '''

        html_text += '</div>'
        self.txt_stats.setHtml(html_text)

    def _show_stats_with_chunks(self, texts, chunks, total_chars, total_chunks):
        """Показать статистику с информацией о чанках"""
        total_chunk_chars = sum(
            len(chunk.text)
            for chunks_list in chunks.values()
            for chunk in chunks_list
        )
        avg_chunk_size = total_chunk_chars // total_chunks if total_chunks > 0 else 0

        html_text = f'''
        <div style="background-color: #1a1a2e; padding: 20px; border-radius: 8px;">
            <div style="color: #e94560; font-size: 18px; font-weight: bold; margin-bottom: 20px;">
                📊 Статистика: Извлечение + Предобработка
            </div>

            <div style="background-color: #0f3460; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <div style="color: #eee; font-size: 14px;">
                    <div style="margin-bottom: 8px;">
                        <b>📁 Файлов:</b> <span style="color: #e94560; font-size: 16px;">{len(texts)}</span>
                    </div>
                    <div style="margin-bottom: 8px;">
                        <b>📝 Символов (сырой):</b> <span style="color: #e94560; font-size: 16px;">{total_chars}</span>
                    </div>
                    <div style="margin-bottom: 8px;">
                        <b>🔪 Всего чанков:</b> <span style="color: #e94560; font-size: 16px;">{total_chunks}</span>
                    </div>
                    <div style="margin-bottom: 8px;">
                        <b>📏 Средний размер чанка:</b> <span style="color: #e94560; font-size: 16px;">{avg_chunk_size} симв.</span>
                    </div>
                    <div>
                        <b>📊 Символов в чанках:</b> <span style="color: #e94560; font-size: 16px;">{total_chunk_chars}</span>
                    </div>
                </div>
            </div>

            <div style="color: #888; font-size: 13px; margin-bottom: 10px;">
                <b>Параметры предобработки:</b>
            </div>
            <div style="background-color: #16213e; padding: 10px; border-radius: 6px; margin-bottom: 20px; color: #eee; font-size: 13px;">
                Стратегия: <b style="color: #e94560;">DOCX-структурное / предложения</b> |
                Размер чанка: <b style="color: #e94560;">{self.chunk_size_spin.value()}</b> |
                Overlap: <b style="color: #e94560;">{self.chunk_overlap_spin.value()}</b> предл.
            </div>

            <div style="color: #888; font-size: 13px; margin-bottom: 10px;">
                <b>Детали по файлам:</b>
            </div>
        '''

        for file_path in texts.keys():
            file_name = Path(file_path).name
            raw_text = texts[file_path]
            file_chunks = chunks.get(file_path, [])

            chars = len(raw_text)
            words = len(raw_text.split())
            num_chunks = len(file_chunks)

            chunk_sizes = [len(c.text) for c in file_chunks] if file_chunks else []
            avg_size = sum(chunk_sizes) // len(chunk_sizes) if chunk_sizes else 0
            min_size = min(chunk_sizes) if chunk_sizes else 0
            max_size = max(chunk_sizes) if chunk_sizes else 0

            status_icon = "✅" if raw_text.strip() else "⚠️"

            html_text += f'''
            <div style="background-color: #16213e; padding: 12px; margin: 8px 0; border-radius: 6px; border-left: 4px solid {'#e94560' if raw_text.strip() else '#888'};">
                <div style="color: #eee; font-size: 14px; font-weight: bold; margin-bottom: 8px;">
                    {status_icon} {file_name}
                </div>
                <div style="color: #888; font-size: 12px; display: flex; gap: 20px; margin-bottom: 5px;">
                    <span>Символов: <b style="color: #e94560;">{chars}</b></span>
                    <span>Слов: <b style="color: #e94560;">{words}</b></span>
                </div>
                <div style="color: #e94560; font-size: 12px;">
                    🔪 Чанков: <b>{num_chunks}</b> |
                    Средний: <b>{avg_size}</b> |
                    Мин: <b>{min_size}</b> |
                    Макс: <b>{max_size}</b>
                </div>
            </div>
            '''

        html_text += '</div>'
        self.txt_stats.setHtml(html_text)

    def _log(self, message):
        """Логирование в статус бар"""
        self.statusBar().showMessage(message)
        print(f"[LOG] {message}")

    def _clear(self):
        """Очистка"""
        self.file_paths = []
        self.extracted_texts = {}
        self.chunks = {}
        self.file_list.clear()
        self.file_selector.clear()
        self.lbl_file_count.setText("Загружено файлов: 0")
        self.btn_extract.setEnabled(False)
        self.btn_preprocess.setEnabled(False)
        self.btn_load.setEnabled(True)
        self.txt_result.clear()
        self.txt_result.setPlaceholderText("Здесь появится полный текст извлечённых документов...")
        self.txt_chunks.clear()
        self.txt_chunks.setPlaceholderText("Здесь появятся чанки после предобработки...")
        self.txt_stats.clear()
        self.txt_stats.setPlaceholderText("Статистика по файлам и чанкам...")
        self.statusBar().showMessage("Очищено")


def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
