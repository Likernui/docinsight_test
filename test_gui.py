#!/usr/bin/env python3
"""
Тестовое окно для проверки модулей:
- text_extractor.py, preprocessor.py, indexer.py, semantic_search.py
Запуск: python test_gui.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QFileDialog, QLabel, QProgressBar,
    QMessageBox, QListWidget, QListWidgetItem, QTabWidget,
    QComboBox, QSpinBox, QGroupBox, QLineEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import html as html_module

from src.text_extractor import DocumentLoader
from src.preprocessor import TextPreprocessor
from src.indexer import IndexBuilder, VectorIndex
from src.semantic_search import SemanticSearch
from src.entity_extractor import EntityExtractor

class WorkerThread(QThread):
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
    def __init__(self):
        super().__init__()
        self.loader = DocumentLoader()
        self.file_paths = []
        self.extracted_texts = {}
        self.preprocessor = TextPreprocessor()
        self.entity_extractor = None
        self.chunks = {}
        self.index = None
        self.index_builder = None
        self.index_ready = False
        self.searcher = None
        self._init_ui()
        self._setup_styles()

    def _init_ui(self):
        self.setMinimumSize(1300, 750)
        self.setWindowTitle("DocInsight — Тест")

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # SIDEBAR
        sidebar = QWidget()
        sidebar.setFixedWidth(300)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(10, 10, 10, 10)
        sb.setSpacing(10)

        self.btn_load = QPushButton("📁 Выбрать файлы")
        self.btn_load.setFixedHeight(40)
        self.btn_load.clicked.connect(self._load_files)
        sb.addWidget(self.btn_load)

        self.lbl_count = QLabel("Загружено: 0")
        self.lbl_count.setStyleSheet("color: #888; font-size: 12px;")
        sb.addWidget(self.lbl_count)

        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(120)
        self.file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sb.addWidget(self.file_list)

        self.btn_extract = QPushButton("⚙️ Извлечь текст")
        self.btn_extract.setFixedHeight(38)
        self.btn_extract.clicked.connect(self._extract_all)
        self.btn_extract.setEnabled(False)
        sb.addWidget(self.btn_extract)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        sb.addWidget(self.progress)

        # Предобработка
        g1 = QGroupBox("Предобработка")
        g1l = QVBoxLayout(g1)
        g1l.setContentsMargins(8, 8, 8, 8)
        g1l.setSpacing(6)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Размер:"))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(200, 2000)
        self.spin_size.setValue(500)
        self.spin_size.setSingleStep(50)
        r1.addWidget(self.spin_size)
        r1.addWidget(QLabel("симв."))
        g1l.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Overlap:"))
        self.spin_overlap = QSpinBox()
        self.spin_overlap.setRange(0, 5)
        self.spin_overlap.setValue(2)
        r2.addWidget(self.spin_overlap)
        r2.addWidget(QLabel("предл."))
        g1l.addLayout(r2)

        self.btn_preprocess = QPushButton("🔪 Предобработать")
        self.btn_preprocess.setFixedHeight(36)
        self.btn_preprocess.clicked.connect(self._preprocess_all)
        self.btn_preprocess.setEnabled(False)
        g1l.addWidget(self.btn_preprocess)
        sb.addWidget(g1)

        # Поиск
        g2 = QGroupBox("Семантический поиск")
        g2l = QVBoxLayout(g2)
        g2l.setContentsMargins(8, 8, 8, 8)
        g2l.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Запрос...")
        self.search_input.setFixedHeight(36)
        self.search_input.returnPressed.connect(self._do_search)
        g2l.addWidget(self.search_input)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Top-K:"))
        self.spin_topk = QSpinBox()
        self.spin_topk.setRange(1, 50)
        self.spin_topk.setValue(5)
        r3.addWidget(self.spin_topk)
        r3.addStretch()
        g2l.addLayout(r3)

        self.btn_search = QPushButton("🔎 Найти")
        self.btn_search.setFixedHeight(36)
        self.btn_search.clicked.connect(self._do_search)
        self.btn_search.setEnabled(False)
        g2l.addWidget(self.btn_search)
        sb.addWidget(g2)

        self.btn_clear = QPushButton("🗑️ Очистить")
        self.btn_clear.setFixedHeight(36)
        self.btn_clear.clicked.connect(self._clear)
        sb.addWidget(self.btn_clear)
        sb.addStretch()

        root.addWidget(sidebar)

        # MAIN AREA
        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setSpacing(6)
        ml.setContentsMargins(10, 10, 10, 10)

        title = QLabel("🧪 DocInsight")
        title.setObjectName("title")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        ml.addWidget(title)

        sel = QHBoxLayout()
        sel.addWidget(QLabel("Файл:"))
        self.file_selector = QComboBox()
        self.file_selector.currentIndexChanged.connect(self._on_file_selected)
        sel.addWidget(self.file_selector)
        sel.addStretch()
        ml.addLayout(sel)

        self.tabs = QTabWidget()

        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setFont(QFont("Consolas", 10))
        self.txt_result.setPlaceholderText("Текст документа...")
        self.tabs.addTab(self.txt_result, "📄 Текст")

        self.txt_chunks = QTextEdit()
        self.txt_chunks.setReadOnly(True)
        self.txt_chunks.setFont(QFont("Consolas", 10))
        self.txt_chunks.setPlaceholderText("Чанки...")
        self.tabs.addTab(self.txt_chunks, "🔪 Чанки")

        self.txt_search_results = QTextEdit()
        self.txt_search_results.setReadOnly(True)
        self.txt_search_results.setFont(QFont("Consolas", 10))
        self.txt_search_results.setPlaceholderText("Результаты поиска...")
        self.tabs.addTab(self.txt_search_results, "🔎 Поиск")

        self.txt_stats = QTextEdit()
        self.txt_stats.setReadOnly(True)
        self.txt_stats.setFont(QFont("Consolas", 10))
        self.txt_stats.setPlaceholderText("Статистика...")
        self.tabs.addTab(self.txt_stats, "📊 Статистика")

        ml.addWidget(self.tabs)
        root.addWidget(main, 1)

        self.statusBar().showMessage("Готов")

    def _setup_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; }
            QLabel#title { color: #89b4fa; padding: 4px 0; }
            QPushButton {
                background-color: #313244; color: #cdd6f4;
                border: none; border-radius: 6px; padding: 8px 16px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #89b4fa; color: #1e1e2e; }
            QPushButton:disabled { background-color: #252535; color: #555; }
            QLineEdit {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 6px;
                padding: 6px 10px; font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #89b4fa; }
            QSpinBox, QComboBox {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 4px;
                padding: 4px 8px; font-size: 12px;
            }
            QGroupBox {
                color: #89b4fa; font-size: 12px; font-weight: bold;
                border: 1px solid #45475a; border-radius: 8px;
                margin-top: 8px; padding-top: 14px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QListWidget {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 6px;
                padding: 4px; font-size: 12px;
            }
            QListWidget::item { padding: 5px; border-radius: 3px; }
            QListWidget::item:selected { background-color: #45475a; }
            QTextEdit {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 6px;
                padding: 10px; font-size: 12px;
            }
            QProgressBar {
                background-color: #313244; border: none; border-radius: 6px;
                text-align: center; color: #cdd6f4; height: 16px;
            }
            QProgressBar::chunk { background-color: #89b4fa; border-radius: 6px; }
            QTabWidget::pane {
                border: 1px solid #45475a; border-radius: 6px;
                background-color: #313244;
            }
            QTabBar::tab {
                background-color: #252535; color: #888;
                padding: 8px 16px; border-top-left-radius: 4px;
                border-top-right-radius: 4px; font-size: 12px;
            }
            QTabBar::tab:selected { background-color: #313244; color: #89b4fa; }
            QStatusBar { background-color: #252535; color: #888; }
        """)

    def _load_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Выберите файлы", "",
            "Все файлы (*.docx *.pdf *.png *.jpg *.jpeg)")
        if files:
            new_files = [f for f in files if f not in self.file_paths]
            if not new_files:
                QMessageBox.information(self, "Информация", "Эти файлы уже загружены")
                return
            self.file_paths.extend(new_files)
            self._update_file_list()
            self.btn_extract.setEnabled(True)
            self.statusBar().showMessage(f"Добавлено файлов: {len(new_files)}")

    def _update_file_list(self):
        self.file_list.clear()
        for fp in self.file_paths:
            name = Path(fp).name
            text = self.extracted_texts.get(fp, "")
            if text.strip():
                self.file_list.addItem(f"✅ {name} ({len(text)} с.)")
            else:
                self.file_list.addItem(f"📄 {name}")
        self.lbl_count.setText(f"Загружено: {len(self.file_paths)}")

    def _extract_all(self):
        if not self.file_paths:
            return
        self.statusBar().showMessage("Извлечение...")
        self.progress.setVisible(True)
        self.progress.setMaximum(0)
        self.btn_extract.setEnabled(False)

        def done(results):
            self.extracted_texts = results
            self.btn_extract.setEnabled(True)
            self.btn_preprocess.setEnabled(True)
            self.progress.setVisible(False)
            self._update_file_list()
            self._update_file_selector()
            total = sum(len(t) for t in results.values())
            words = sum(len(t.split()) for t in results.values())
            self._show_stats(results, total, words)
            if results:
                f = list(results.keys())[0]
                self._show_raw_result(Path(f).name, results[f])
            self.statusBar().showMessage(f"Извлечено: {total} символов")

        def err(e):
            self.btn_extract.setEnabled(True)
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Ошибка", str(e))

        self.worker = WorkerThread(self.loader.load_multiple, self.file_paths)
        self.worker.finished.connect(done)
        self.worker.error.connect(err)
        self.worker.start()

    def _preprocess_all(self):
        if not self.extracted_texts:
            return
        self.preprocessor = TextPreprocessor(
            chunk_size=self.spin_size.value(),
            overlap_sentences=self.spin_overlap.value())
        self.statusBar().showMessage("Предобработка...")
        self.progress.setVisible(True)
        self.progress.setMaximum(0)
        self.btn_preprocess.setEnabled(False)

        def done(results):
            self.statusBar().showMessage("Извлечение сущностей GLiNER...")

            self.entity_extractor = EntityExtractor()
            self.chunks = self.entity_extractor.enrich_chunks_dict(results)

            structure = self.entity_extractor.extract_all_documents_structure(self.chunks)
            print("DOCUMENT STRUCTURE:")
            print(structure)

            self.btn_preprocess.setEnabled(True)
            self.progress.setVisible(False)

            total_chunks = sum(len(c) for c in self.chunks.values())

            if self.chunks:
                f = list(self.chunks.keys())[0]
                self._show_chunks(Path(f).name, self.chunks[f])

            self._show_stats_with_chunks(self.extracted_texts, self.chunks, total_chunks)
            self.statusBar().showMessage(f"Создано {total_chunks} чанков, сущности извлечены")

            self._build_index()

        def err(e):
            self.btn_preprocess.setEnabled(True)
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Ошибка", str(e))

        self.worker = WorkerThread(
            self.preprocessor.process_documents, self.extracted_texts)
        self.worker.finished.connect(done)
        self.worker.error.connect(err)
        self.worker.start()

    def _build_index(self):
        if not self.chunks:
            return

        def done(index):
            self.index = index
            self.index_ready = True
            self.searcher = SemanticSearch(index, self.index_builder.vectorizer)
            self.btn_search.setEnabled(True)
            self.statusBar().showMessage(f"Индекс: {index.size} векторов")

        def err(e):
            QMessageBox.critical(self, "Ошибка индексации", str(e))

        self.statusBar().showMessage("Построение индекса...")
        self.index_builder = IndexBuilder(batch_size=32)
        self.worker = WorkerThread(
            self.index_builder.build_from_chunks, self.chunks)
        self.worker.finished.connect(done)
        self.worker.error.connect(err)
        self.worker.start()

    def _do_search(self):
        if not self.index_ready or self.index is None:
            QMessageBox.warning(self, "Внимание", "Сначала предобработайте документы!")
            return
        query = self.search_input.text().strip()
        if not query:
            return
        self.statusBar().showMessage(f"Поиск: {query}")
        self.btn_search.setEnabled(False)

        def done(results):
            self._show_search_results(query, results)
            self.btn_search.setEnabled(True)
            self.statusBar().showMessage(f"Найдено: {len(results)}")
            self.tabs.setCurrentWidget(self.txt_search_results)

        def err(e):
            self.btn_search.setEnabled(True)
            QMessageBox.critical(self, "Ошибка поиска", str(e))

        self.worker = WorkerThread(
            self._search_thread, query, self.spin_topk.value())
        self.worker.finished.connect(done)
        self.worker.error.connect(err)
        self.worker.start()

    def _search_thread(self, query, top_k):
        return self.searcher.search(query, top_k=top_k)

    def _show_raw_result(self, name, text):
        self.txt_result.setPlainText(text)
        self.tabs.setCurrentWidget(self.txt_result)

    def _show_chunks(self, name, chunks):
        html = f"<b>🔪 {name}</b> — {len(chunks)} чанков<br><br>"
        for c in chunks:
            sec = c.metadata.get("section", "")
            tag = f"[{sec}] " if sec else ""

            html += f"<div style='margin-bottom:12px; padding:8px; background:#1e1e2e; border-radius:6px;'>"
            html += f"<b style='color:#89b4fa;'>Чанк #{c.chunk_index + 1}</b> {tag}"
            html += f" ({len(c.text)} с.)<br>"

            entities = c.metadata.get("entities", [])

            if entities:
                html += "<div style='margin-top:6px; margin-bottom:6px; color:#a6e3a1;'>"
                html += "<b>Сущности:</b><br>"

                for e in entities[:10]:
                    text = html_module.escape(str(e.get("text", "")))
                    label = html_module.escape(str(e.get("label", "")))
                    html += f"• {text} ({label})<br>"

                if len(entities) > 10:
                    html += f"... ещё {len(entities) - 10}<br>"

                html += "</div>"
            html += "<br>" + html_module.escape(c.text)
            html += "</div>"
        self.txt_chunks.setHtml(html)

    def _show_search_results(self, query, results):
        if not results:
            self.txt_search_results.setHtml("<b>Ничего не найдено</b>")
            return
        html = f"<b>🔎 Запрос:</b> {html_module.escape(query)}<br><br>"
        for i, r in enumerate(results):
            name = Path(r.file_path).name
            sec = r.metadata.get("section", "")
            tag = f"[{sec}] " if sec else ""
            color = "#a6e3a1" if r.score > 0.7 else "#f9e2af" if r.score > 0.5 else "#f38ba8"
            html += f"<div style='margin-bottom:12px; padding:8px; background:#1e1e2e; border-left:3px solid {color}; border-radius:6px;'>"
            html += f"<b style='color:{color};'>#{i+1}</b> {html_module.escape(name)} {tag}"
            html += f" — <b>{r.score*100:.0f}%</b> ({len(r.text)} с.)<br>"
            html += html_module.escape(r.text)
            html += f"</div>"
        self.txt_search_results.setHtml(html)

    def _update_file_selector(self):
        self.file_selector.clear()
        for fp in self.file_paths:
            self.file_selector.addItem(Path(fp).name, fp)

    def _on_file_selected(self, index):
        if index < 0 or index >= len(self.file_paths):
            return
        fp = self.file_paths[index]
        name = Path(fp).name
        if fp in self.extracted_texts:
            self._show_raw_result(name, self.extracted_texts[fp])
        if fp in self.chunks:
            self._show_chunks(name, self.chunks[fp])

    def _show_stats(self, results, total_chars, total_words):
        html = f"<b>📊 Извлечение текста</b><br><br>"
        html += f"Файлов: {len(results)}<br>Символов: {total_chars}<br>Слов: {total_words}<br><br>"
        for fp, text in results.items():
            html += f"<b>📄 {Path(fp).name}</b><br>"
            html += f"  Символов: {len(text)} | Слов: {len(text.split())} | Строк: {len(text.splitlines())}<br>"
        self.txt_stats.setHtml(html)

    def _show_stats_with_chunks(self, texts, chunks, total_chunks):
        total_cc = sum(len(c.text) for cl in chunks.values() for c in cl)
        avg = total_cc // total_chunks if total_chunks else 0
        html = f"<b>📊 Извлечение + Предобработка</b><br><br>"
        html += f"Файлов: {len(texts)}<br>Символов: {sum(len(t) for t in texts.values())}<br>"
        html += f"Чанков: {total_chunks}<br>Средний размер: {avg} симв.<br><br>"
        for fp in texts.keys():
            name = Path(fp).name
            nc = len(chunks.get(fp, []))
            sizes = [len(c.text) for c in chunks.get(fp, [])]
            mn = min(sizes) if sizes else 0
            mx = max(sizes) if sizes else 0
            html += f"<b>📄 {name}</b><br>"
            html += f"  Чанков: {nc} | Мин: {mn} | Макс: {mx}<br>"
        self.txt_stats.setHtml(html)

    def _clear(self):
        self.file_paths = []
        self.extracted_texts = {}
        self.chunks = {}
        self.index = None
        self.index_ready = False
        self.index_builder = None
        self.searcher = None
        self.file_list.clear()
        self.file_selector.clear()
        self.lbl_count.setText("Загружено: 0")
        self.btn_extract.setEnabled(False)
        self.btn_preprocess.setEnabled(False)
        self.btn_search.setEnabled(False)
        self.txt_result.clear()
        self.txt_chunks.clear()
        self.txt_search_results.clear()
        self.txt_stats.clear()
        self.statusBar().showMessage("Очищено")


def main():
    app = QApplication(sys.argv)
    w = TestWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
