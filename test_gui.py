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
    QMessageBox, QListWidget, QTabWidget,
    QComboBox, QSpinBox, QGroupBox, QLineEdit, QCheckBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import html as html_module

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
        from src.text_extractor import DocumentLoader
        from src.preprocessor import TextPreprocessor
        from src.indexer import IndexBuilder
        from src.semantic_search import SemanticSearch
        from src.entity_service import EntityService

        self.TextPreprocessor = TextPreprocessor
        self.IndexBuilder = IndexBuilder
        self.SemanticSearch = SemanticSearch
        self.entity_service = EntityService(Path(__file__).parent)

        self.loader = DocumentLoader()
        self.file_paths = []
        self.extracted_texts = {}
        self.preprocessor = TextPreprocessor()
        self.chunks = {}
        self.index = None
        self.index_builder = None
        self.index_ready = False
        self.searcher = None
        self._init_ui()
        self._setup_styles()

    def _init_ui(self):
        self.setMinimumSize(1500, 950)
        self.setWindowTitle("DocInsight — Тест")

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # SIDEBAR
        sidebar = QWidget()
        sidebar.setFixedWidth(430)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(14, 14, 14, 14)
        sb.setSpacing(12)

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
        g1l.setContentsMargins(14, 16, 14, 14)
        g1l.setSpacing(10)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Размер:"))
        self.spin_size = QSpinBox()
        self.spin_size.setMinimumWidth(120)
        self.spin_size.setRange(400, 4000)
        self.spin_size.setValue(1500)
        self.spin_size.setSingleStep(100)
        r1.addWidget(self.spin_size)
        r1.addWidget(QLabel("симв."))
        g1l.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Overlap:"))
        self.spin_overlap = QSpinBox()
        self.spin_overlap.setMinimumWidth(120)
        self.spin_overlap.setRange(0, 5)
        self.spin_overlap.setValue(1)
        r2.addWidget(self.spin_overlap)
        r2.addWidget(QLabel("предл."))
        g1l.addLayout(r2)

        self.chk_entities = QCheckBox("GLiNER сущности")
        self.chk_entities.setChecked(False)
        self.chk_entities.setToolTip("На macOS GLiNER может падать из-за нативного ML-стека")
        g1l.addWidget(self.chk_entities)

        r_mode = QHBoxLayout()
        r_mode.addWidget(QLabel("Режим:"))
        self.combo_entities_mode = QComboBox()
        self.combo_entities_mode.setMinimumWidth(190)
        self.combo_entities_mode.addItem("Полный", "full")
        self.combo_entities_mode.addItem("Приоритетный", "priority")
        self.combo_entities_mode.setToolTip("Полный: все чанки. Приоритетный: первые чанки и чанки с маркерами.")
        r_mode.addWidget(self.combo_entities_mode)
        g1l.addLayout(r_mode)

        self.entities_batch_size = 8

        self.btn_preprocess = QPushButton("🔪 Предобработать")
        self.btn_preprocess.setFixedHeight(44)
        self.btn_preprocess.clicked.connect(self._preprocess_all)
        self.btn_preprocess.setEnabled(False)
        g1l.addWidget(self.btn_preprocess)
        sb.addWidget(g1)

        # Поиск
        g2 = QGroupBox("Семантический поиск")
        g2l = QVBoxLayout(g2)
        g2l.setContentsMargins(14, 16, 14, 14)
        g2l.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Запрос...")
        self.search_input.setFixedHeight(36)
        self.search_input.returnPressed.connect(self._do_search)
        g2l.addWidget(self.search_input)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Top-K:"))
        self.spin_topk = QSpinBox()
        self.spin_topk.setMinimumWidth(120)
        self.spin_topk.setRange(1, 50)
        self.spin_topk.setValue(5)
        r3.addWidget(self.spin_topk)
        r3.addStretch()
        g2l.addLayout(r3)

        self.btn_build_index = QPushButton("🧠 Построить индекс")
        self.btn_build_index.setFixedHeight(44)
        self.btn_build_index.clicked.connect(self._build_index)
        self.btn_build_index.setEnabled(False)
        g2l.addWidget(self.btn_build_index)

        self.btn_search = QPushButton("🔎 Найти")
        self.btn_search.setFixedHeight(44)
        self.btn_search.clicked.connect(self._do_search)
        self.btn_search.setEnabled(False)
        g2l.addWidget(self.btn_search)

        sb.addWidget(g2)

        self.btn_clear = QPushButton("🗑️ Очистить")
        self.btn_clear.setFixedHeight(44)
        self.btn_clear.clicked.connect(self._clear)
        sb.addWidget(self.btn_clear)
        sb.addStretch()

        root.addWidget(sidebar)

        # MAIN AREA
        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setSpacing(10)
        ml.setContentsMargins(10, 10, 10, 10)

        title = QLabel("DocInsight")
        title.setObjectName("title")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        ml.addWidget(title)

        sel = QHBoxLayout()
        sel.addWidget(QLabel("Файл:"))
        self.file_selector = QComboBox()
        self.file_selector.setMinimumWidth(700)
        self.file_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.file_selector.currentIndexChanged.connect(self._on_file_selected)
        sel.addWidget(self.file_selector)
        sel.addStretch()
        ml.addLayout(sel)

        self.tabs = QTabWidget()

        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setFont(QFont("Menlo", 10))
        self.txt_result.setPlaceholderText("Текст документа...")
        self.tabs.addTab(self.txt_result, "📄 Текст")

        self.txt_chunks = QTextEdit()
        self.txt_chunks.setReadOnly(True)
        self.txt_chunks.setFont(QFont("Menlo", 10))
        self.txt_chunks.setPlaceholderText("Чанки...")
        self.tabs.addTab(self.txt_chunks, "🔪 Чанки")

        self.txt_entities = QTextEdit()
        self.txt_entities.setReadOnly(True)
        self.txt_entities.setFont(QFont("Menlo", 10))
        self.txt_entities.setPlaceholderText("Сущности...")
        self.tabs.addTab(self.txt_entities, "🏷️ Сущности")

        self.txt_search_results = QTextEdit()
        self.txt_search_results.setReadOnly(True)
        self.txt_search_results.setFont(QFont("Menlo", 10))
        self.txt_search_results.setPlaceholderText("Результаты поиска...")
        self.tabs.addTab(self.txt_search_results, "🔎 Поиск")

        ml.addWidget(self.tabs)
        root.addWidget(main, 1)

        self.statusBar().showMessage("Готов")

    def _setup_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; }
            QLabel#title { color: #89b4fa; padding: 4px 0; }
            QPushButton {
                background-color: #313244; color: #cdd6f4;
                border: none; border-radius: 6px; padding: 8px 14px;
                font-size: 13px; font-weight: bold;
                min-height: 28px;
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
                min-height: 26px;
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
                padding: 8px 14px; border-top-left-radius: 4px;
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
        self.preprocessor = self.TextPreprocessor(
            chunk_size=self.spin_size.value(),
            overlap_sentences=self.spin_overlap.value())
        self.statusBar().showMessage("Предобработка...")
        self.progress.setVisible(True)
        self.progress.setMaximum(0)
        self.btn_preprocess.setEnabled(False)

        def done(payload):
            chunks, status_suffix, warning = payload
            self.chunks = chunks
            self._finish_preprocessing(status_suffix)
            if warning:
                QMessageBox.warning(
                    self,
                    "GLiNER недоступен",
                    "GLiNER упал в отдельном процессе, приложение продолжит без сущностей.\n\n"
                    f"{warning}"
                )

        def err(e):
            self.btn_preprocess.setEnabled(True)
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Ошибка", str(e))

        self.worker = WorkerThread(
            self._preprocess_documents,
            self.extracted_texts,
            self.chk_entities.isChecked(),
            self.combo_entities_mode.currentData(),
            self.entities_batch_size,
        )
        self.worker.finished.connect(done)
        self.worker.error.connect(err)
        self.worker.start()

    def _preprocess_documents(self, extracted_texts, extract_entities, mode, batch_size):
        chunks = self.preprocessor.process_documents(extracted_texts)

        if not extract_entities:
            return chunks, "без извлечения сущностей", None

        result = self.entity_service.extract(
            chunks,
            mode=mode,
            batch_size=batch_size,
        )
        enriched = self.entity_service.enrich_chunks_regex_only(
            result.chunks,
            include_sources=True,
            source_texts=extracted_texts,
        )
        return enriched, result.status_suffix, result.warning

    def _finish_preprocessing(self, status_suffix):
        self.btn_preprocess.setEnabled(True)
        self.progress.setVisible(False)
        self.index = None
        self.index_builder = None
        self.index_ready = False
        self.searcher = None
        self.btn_search.setEnabled(False)
        self.btn_build_index.setEnabled(True)

        total_chunks = sum(len(c) for c in self.chunks.values())

        if self.chunks:
            f = list(self.chunks.keys())[0]
            self._show_chunks(Path(f).name, self.chunks[f])
            self._show_entities(Path(f).name, self.chunks[f])

        self.statusBar().showMessage(
            f"Создано {total_chunks} чанков, {status_suffix}. Индекс еще не построен"
        )

    def _build_index(self):
        if not self.chunks:
            return

        self.statusBar().showMessage("Построение индекса...")
        self.progress.setVisible(True)
        self.progress.setMaximum(0)
        self.btn_build_index.setEnabled(False)
        self.btn_search.setEnabled(False)
        def done(payload):
            index, index_builder = payload
            self.index = index
            self.index_builder = index_builder
            self.index_ready = True
            self.searcher = self.SemanticSearch(index, self.index_builder.vectorizer)
            self.btn_search.setEnabled(True)
            self.btn_build_index.setEnabled(True)
            self.progress.setVisible(False)
            self.statusBar().showMessage(f"Индекс: {index.size} векторов")

        def err(e):
            self.btn_build_index.setEnabled(True)
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Ошибка индексации", str(e))

        self.worker = WorkerThread(self._build_index_thread, self.chunks)
        self.worker.finished.connect(done)
        self.worker.error.connect(err)
        self.worker.start()

    def _build_index_thread(self, chunks):
        index_builder = self.IndexBuilder(batch_size=32)
        index = index_builder.build_from_chunks(chunks)
        return index, index_builder

    def _do_search(self):
        if not self.index_ready or self.index is None:
            QMessageBox.warning(self, "Внимание", "Сначала постройте индекс!")
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

    def _show_entities(self, name, chunks):
        grouped = {}
        total = 0

        for chunk in chunks:
            for entity in chunk.metadata.get("entities", []):
                text = str(entity.get("text", "")).strip()
                label = str(entity.get("label", "неизвестно")).strip() or "неизвестно"

                if not text:
                    continue

                total += 1
                grouped.setdefault(label, {})
                item = grouped[label].setdefault(text, {
                    "count": 0,
                    "chunks": [],
                    "scores": [],
                    "sources": set(),
                    "blocks": [],
                })
                item["count"] += 1

                chunk_indexes = entity.get("chunk_indexes")
                if isinstance(chunk_indexes, list) and chunk_indexes:
                    item["chunks"].extend(int(i) + 1 for i in chunk_indexes)
                else:
                    item["chunks"].append(chunk.chunk_index + 1)

                score = entity.get("score")
                if score is not None:
                    item["scores"].append(float(score))

                source = entity.get("source")
                if source:
                    item["sources"].add(str(source))

                if label in {"источник", "фрагмент программного кода"}:
                    item["blocks"].append({
                        "title": entity.get("title") or text.splitlines()[0],
                        "body": entity.get("code") or text,
                        "source_count": entity.get("source_count"),
                    })

        if not total:
            self.txt_entities.setHtml(
                f"<b>🏷️ {html_module.escape(name)}</b><br><br>"
                "Сущности не найдены. Включите чекбокс <b>GLiNER сущности</b> "
                "перед предобработкой или проверьте параметры извлечения."
            )
            return

        html = f"<b>🏷️ {html_module.escape(name)}</b> — {total} сущн.<br><br>"

        for label in sorted(grouped.keys()):
            entities = grouped[label]
            label_total = sum(item["count"] for item in entities.values())

            html += (
                "<div style='margin-bottom:12px; padding:10px; "
                "background:#1e1e2e; border-radius:6px;'>"
            )
            html += (
                f"<b style='color:#a6e3a1;'>{html_module.escape(label)}</b> "
                f"<span style='color:#cdd6f4;'>({label_total})</span><br><br>"
            )

            sorted_items = sorted(
                entities.items(),
                key=lambda pair: (-pair[1]["count"], pair[0].lower()),
            )

            for text, item in sorted_items:
                chunks_text = ", ".join(str(i) for i in sorted(set(item["chunks"]))[:12])
                if len(set(item["chunks"])) > 12:
                    chunks_text += ", ..."

                details = f"чанки: {chunks_text}"
                if item["scores"]:
                    avg_score = sum(item["scores"]) / len(item["scores"])
                    details += f" | score: {avg_score:.2f}"

                if item["sources"]:
                    details += f" | {', '.join(sorted(item['sources']))}"

                if label in {"источник", "фрагмент программного кода"} and item["blocks"]:
                    block = self._best_block(item["blocks"])
                    title = html_module.escape(str(block["title"]))
                    body = html_module.escape(str(block["body"]))
                    html += (
                        f"• <b>{title}</b> "
                        f"<span style='color:#888;'>x{item['count']}; "
                        f"{html_module.escape(details)}</span>"
                        "<pre style='white-space:pre-wrap; margin:6px 0 12px 18px; "
                        "padding:8px; background:#252535; border-radius:6px; "
                        "color:#cdd6f4; font-family:Menlo, monospace; font-size:11px;'>"
                        f"{body}</pre>"
                    )
                else:
                    html += (
                        f"• <b>{html_module.escape(text)}</b> "
                        f"<span style='color:#888;'>x{item['count']}; "
                        f"{html_module.escape(details)}</span><br>"
                    )

            html += "</div>"

        self.txt_entities.setHtml(html)

    def _best_block(self, blocks):
        return max(
            blocks,
            key=lambda block: (
                int(block.get("source_count") or 0),
                len(str(block.get("body") or "")),
            ),
        )

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
            self._show_entities(name, self.chunks[fp])

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
        self.btn_build_index.setEnabled(False)
        self.btn_search.setEnabled(False)
        self.txt_result.clear()
        self.txt_chunks.clear()
        self.txt_entities.clear()
        self.txt_search_results.clear()
        self.statusBar().showMessage("Очищено")


def main():
    app = QApplication(sys.argv)
    w = TestWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
