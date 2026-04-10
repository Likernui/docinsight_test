#!/usr/bin/env python3
"""
Тестовое окно для проверки модуля загрузки документов.
Пункты 2.1 и 2.2 из плана.

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
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from src.text_extractor import DocumentLoader


class WorkerThread(QThread):
    """Поток для длительных операций"""
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
            result = self.operation(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class TestWindow(QMainWindow):
    """Тестовое окно для проверки загрузки документов"""

    def __init__(self):
        super().__init__()
        self.loader = DocumentLoader()
        self.file_paths = []
        self.extracted_texts = {}
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
        title = QLabel("🧪 Тест модуля загрузки документов")
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

        # Кнопка выбора файлов
        self.btn_load = QPushButton("📁 Выбрать файлы")
        self.btn_load.setFixedHeight(50)
        self.btn_load.setStyleSheet("font-size: 15px;")
        self.btn_load.clicked.connect(self._load_files)
        left_layout.addWidget(self.btn_load)

        # Счётчик файлов
        self.lbl_file_count = QLabel("Загружено файлов: 0")
        self.lbl_file_count.setObjectName("file_count")
        self.lbl_file_count.setFont(QFont("Arial", 11))
        left_layout.addWidget(self.lbl_file_count)

        # Список файлов
        self.file_list = QListWidget()
        self.file_list.setAlternatingRowColors(False)
        left_layout.addWidget(self.file_list)

        # Прогресс бар
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        left_layout.addWidget(self.progress)

        # Кнопки извлечения
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_extract = QPushButton("⚙️ Извлечь все")
        self.btn_extract.setFixedHeight(45)
        self.btn_extract.clicked.connect(self._extract_all)
        self.btn_extract.setEnabled(False)
        btn_layout.addWidget(self.btn_extract)

        left_layout.addLayout(btn_layout)

        # Кнопка очистки
        self.btn_clear = QPushButton("🗑️ Очистить")
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

        # Вкладка 1: Результат
        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setFont(QFont("Menlo", 10))
        self.txt_result.setPlaceholderText("Здесь появится полный текст извлечённых документов...")
        self.txt_result.document().setMaximumBlockCount(1000000)  # Увеличиваем лимит
        self.tabs.addTab(self.txt_result, "📄 Результат")

        # Вкладка 2: Статистика
        self.txt_stats = QTextEdit()
        self.txt_stats.setReadOnly(True)
        self.txt_stats.setFont(QFont("Menlo", 10))
        self.txt_stats.setPlaceholderText("Статистика по файлам...")
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

            QComboBox {
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
            # Добавляем файлы к существующим, а не заменяем
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
        self.progress.setMaximum(len(self.file_paths))
        self.progress.setValue(0)
        self.btn_extract.setEnabled(False)
        self.btn_load.setEnabled(False)
        self.statusBar().showMessage("Извлечение текста...")

        def progress_callback(current, total, filename):
            self.progress.setValue(current)
            self.statusBar().showMessage(f"Обработка: {Path(filename).name}")
            # Обновляем список файлов
            self._update_file_list()

        def on_finished(results):
            self.extracted_texts = results
            self.btn_extract.setEnabled(True)
            self.btn_load.setEnabled(True)
            self.progress.setVisible(False)
            self.statusBar().showMessage("Текст извлечён!")

            # Обновляем список файлов
            self._update_file_list()

            # Обновляем переключатель файлов
            self._update_file_selector()

            # Считаем статистику
            total_chars = sum(len(t) for t in results.values())
            total_chars_no_spaces = sum(len(t.replace(' ', '').replace('\n', '')) for t in results.values())
            total_words = sum(len(t.split()) for t in results.values())

            # Показываем статистику
            self._show_stats(results, total_chars, total_chars_no_spaces, total_words)

            # Показываем первый файл во вкладке результат
            if results:
                first_file = list(results.keys())[0]
                first_name = Path(first_file).name
                first_text = results[first_file]
                self._show_result(first_name, first_text)

                self._log(f"Всего извлечено: {total_chars} символов, {total_words} слов")

        def on_error(error):
            self._log(f"Ошибка: {error}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка извлечения текста:\n{error}")
            self.btn_extract.setEnabled(True)
            self.btn_load.setEnabled(True)
            self.progress.setVisible(False)

        self.worker = WorkerThread(
            self.loader.load_multiple,
            self.file_paths,
            progress_callback=progress_callback
        )
        self.worker.finished.connect(on_finished)
        self.worker.error.connect(on_error)
        self.worker.start()

    def _show_result(self, file_name, text):
        """Показать результат (полный текст)"""
        # Для очень больших текстов используем простой формат
        if len(text) > 50000:
            html_text = f'''
            <div style="background-color: #1a1a2e; padding: 20px; border-radius: 8px;">
                <div style="color: #e94560; font-size: 18px; font-weight: bold; margin-bottom: 15px;">
                    📄 {file_name}
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
                    📄 {file_name}
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
        self.txt_result.verticalScrollBar().setValue(0)  # Прокрутка в начало
        self.tabs.setCurrentWidget(self.txt_result)

    def _update_file_selector(self):
        """Обновить переключатель файлов"""
        self.file_selector.clear()
        for file_path in self.file_paths:
            file_name = Path(file_path).name
            self.file_selector.addItem(f"📄 {file_name}", file_path)

    def _on_file_selected(self, index):
        """При выборе файла показать его текст"""
        if index >= 0 and index < len(self.file_paths):
            file_path = self.file_paths[index]
            if file_path in self.extracted_texts:
                file_name = Path(file_path).name
                text = self.extracted_texts[file_path]
                self._show_result(file_name, text)

    def _show_stats(self, results, total_chars, total_chars_no_spaces, total_words):
        """Показать статистику по всем файлам"""
        html_text = f'''
        <div style="background-color: #1a1a2e; padding: 20px; border-radius: 8px;">
            <div style="color: #e94560; font-size: 18px; font-weight: bold; margin-bottom: 20px;">
                📊 Статистика обработки
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

        # Таблица по файлам
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

    def _log(self, message):
        """Логирование в статус бар"""
        self.statusBar().showMessage(message)
        print(f"[LOG] {message}")

    def _clear(self):
        """Очистка"""
        self.file_paths = []
        self.extracted_texts = {}
        self.file_list.clear()
        self.file_selector.clear()
        self.lbl_file_count.setText("Загружено файлов: 0")
        self.btn_extract.setEnabled(False)
        self.btn_load.setEnabled(True)
        self.txt_result.clear()
        self.txt_result.setPlaceholderText("Здесь появится полный текст извлечённых документов...")
        self.txt_stats.clear()
        self.txt_stats.setPlaceholderText("Статистика по файлам...")
        self.statusBar().showMessage("Очищено")


def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
