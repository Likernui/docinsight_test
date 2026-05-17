#!/usr/bin/env python3
"""
Основной пользовательский интерфейс DocInsight.

В этом окне скрыты технические детали пайплайна: пользователь выбирает
документы, типы сущностей и получает сгруппированный результат.
"""

import sys
import html as html_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.pipeline import DocumentPipeline, PipelineCancelled, PipelineOptions


ENTITY_CHOICES = [
    ("students", "Студенты/участники"),
    ("supervisors", "Руководители"),
    ("project_topics", "Темы проектов"),
    ("disciplines", "Дисциплины"),
    ("technologies", "Технологии"),
    ("sources", "Источники"),
    ("code_fragments", "Фрагменты кода"),
]


class PipelineThread(QThread):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, file_paths: list[str], requested_types: list[str]):
        super().__init__()
        self.file_paths = file_paths
        self.requested_types = requested_types
        self.cancel_requested = False

    def request_cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> None:
        try:
            pipeline = DocumentPipeline(Path(__file__).parent)
            result = pipeline.process_files(
                self.file_paths,
                PipelineOptions(requested_types=self.requested_types),
                progress_callback=self.progress.emit,
                cancel_checker=lambda: self.cancel_requested,
            )
            self.finished.emit(result)
        except PipelineCancelled as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_paths: list[str] = []
        self.rows: list[dict] = []
        self.worker: PipelineThread | None = None

        self.setWindowTitle("DocInsight")
        self.setMinimumSize(1180, 760)
        self._init_ui()
        self._setup_styles()

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(330)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(12)

        title = QLabel("DocInsight")
        title.setObjectName("title")
        sidebar_layout.addWidget(title)

        self.btn_load = QPushButton("Выбрать документы")
        self.btn_load.clicked.connect(self._select_files)
        sidebar_layout.addWidget(self.btn_load)

        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(170)
        sidebar_layout.addWidget(self.file_list)

        group = QGroupBox("Что извлечь")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(8)
        self.checkboxes: dict[str, QCheckBox] = {}
        for key, label in ENTITY_CHOICES:
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            self.checkboxes[key] = checkbox
            group_layout.addWidget(checkbox)
        sidebar_layout.addWidget(group)

        self.btn_process = QPushButton("Обработать документы")
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self._process)
        sidebar_layout.addWidget(self.btn_process)

        self.btn_cancel = QPushButton("Отменить")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        sidebar_layout.addWidget(self.btn_cancel)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximum(0)
        sidebar_layout.addWidget(self.progress)

        self.status_label = QLabel("Выберите документы для анализа")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("muted")
        sidebar_layout.addWidget(self.status_label)
        sidebar_layout.addStretch()

        root.addWidget(sidebar)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        heading = QLabel("Результаты извлечения")
        heading.setObjectName("heading")
        main_layout.addWidget(heading)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Документ:"))
        self.document_filter = QComboBox()
        self.document_filter.addItem("Все документы", None)
        self.document_filter.currentIndexChanged.connect(self._show_current_document_entities)
        filter_row.addWidget(self.document_filter)
        filter_row.addStretch()
        main_layout.addLayout(filter_row)

        self.entities_view = QTextEdit()
        self.entities_view.setReadOnly(True)
        self.entities_view.setPlaceholderText("После обработки здесь появятся найденные сущности.")
        main_layout.addWidget(self.entities_view)

        root.addWidget(main)

    def _setup_styles(self) -> None:
        checkmark_path = (Path(__file__).parent / "assets" / "checkmark.svg").as_posix()
        stylesheet = """
            QMainWindow, QWidget { background: #11131a; color: #d8dee9; font-size: 14px; }
            QWidget { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial; }
            #title { color: #f4f7fb; font-size: 24px; font-weight: 700; margin-bottom: 4px; }
            #heading { color: #f4f7fb; font-size: 20px; font-weight: 650; }
            #muted { color: #8e98aa; }
            QPushButton {
                min-height: 36px; border-radius: 6px; border: 1px solid #3a4252;
                background: #232a36; color: #edf2f7; padding: 6px 12px;
            }
            QPushButton:hover { background: #2d3748; border-color: #63b3ed; }
            QPushButton:disabled { color: #687385; background: #1a1f29; border-color: #2a313d; }
            QGroupBox {
                border: 1px solid #303846; border-radius: 8px; margin-top: 8px;
                padding: 12px 8px 8px 8px; background: #171b24;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #a9b4c6; }
            QListWidget, QTextEdit, QComboBox {
                background: #171b24; border: 1px solid #303846; border-radius: 8px;
                selection-background-color: #30425f; selection-color: #f8fafc;
            }
            QComboBox {
                min-height: 34px; padding: 4px 10px; color: #d8dee9;
            }
            QComboBox::drop-down { border: 0; width: 28px; }
            QComboBox QAbstractItemView {
                background: #171b24; border: 1px solid #303846; color: #d8dee9;
                selection-background-color: #30425f;
            }
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background: #263247; border-radius: 4px; }
            QScrollBar:vertical { background: #11131a; width: 12px; }
            QScrollBar::handle:vertical { background: #3a4252; border-radius: 6px; min-height: 28px; }
            QProgressBar { border: 1px solid #303846; border-radius: 6px; background: #171b24; }
            QProgressBar::chunk { background: #63b3ed; border-radius: 6px; }
            QCheckBox { spacing: 8px; color: #d8dee9; }
            QCheckBox::indicator { width: 16px; height: 16px; }
            QCheckBox::indicator:unchecked { border: 1px solid #596579; background: #11131a; border-radius: 3px; }
            QCheckBox::indicator:checked {
                border: 1px solid #63b3ed; background: #63b3ed; border-radius: 3px;
                image: url("__CHECKMARK_PATH__");
            }
            QMessageBox { background: #171b24; }
            QMessageBox QLabel { color: #d8dee9; }
        """
        self.setStyleSheet(stylesheet.replace("__CHECKMARK_PATH__", checkmark_path))

    def _select_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите документы",
            "",
            "Документы (*.docx *.pdf *.png *.jpg *.jpeg)",
        )
        if not files:
            return

        for file_path in files:
            if file_path not in self.file_paths:
                self.file_paths.append(file_path)

        self._refresh_files()
        self.btn_process.setEnabled(bool(self.file_paths))
        self.status_label.setText(f"Выбрано документов: {len(self.file_paths)}")

    def _refresh_files(self) -> None:
        self.file_list.clear()
        for file_path in self.file_paths:
            self.file_list.addItem(Path(file_path).name)

    def _selected_types(self) -> list[str]:
        return [key for key, checkbox in self.checkboxes.items() if checkbox.isChecked()]

    def _process(self) -> None:
        requested_types = self._selected_types()
        if not self.file_paths:
            return
        if not requested_types:
            QMessageBox.warning(self, "Нет типов", "Выберите хотя бы один тип данных для извлечения.")
            return

        self.entities_view.clear()
        self.progress.setVisible(True)
        self.btn_process.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_load.setEnabled(False)
        self.status_label.setText("Запуск обработки...")

        self.worker = PipelineThread(self.file_paths, requested_types)
        self.worker.progress.connect(self.status_label.setText)
        self.worker.finished.connect(self._processing_done)
        self.worker.failed.connect(self._processing_failed)
        self.worker.start()

    def _cancel(self) -> None:
        if self.worker:
            self.worker.request_cancel()
            self.status_label.setText("Отмена после завершения текущего этапа...")

    def _processing_done(self, result) -> None:
        self.rows = result.rows
        self._refresh_document_filter()
        self._show_current_document_entities()
        self._reset_busy_state()
        self.status_label.setText(result.status)

        if result.warnings:
            QMessageBox.warning(
                self,
                "Часть сущностей недоступна",
                "Обработка завершена, но часть ML-извлечения не выполнена.\n\n"
                + "\n".join(result.warnings),
            )

    def _processing_failed(self, message: str) -> None:
        self._reset_busy_state()
        self.status_label.setText(message)
        if message != "Обработка отменена":
            QMessageBox.critical(self, "Ошибка обработки", message)

    def _reset_busy_state(self) -> None:
        self.progress.setVisible(False)
        self.btn_process.setEnabled(bool(self.file_paths))
        self.btn_cancel.setEnabled(False)
        self.btn_load.setEnabled(True)

    def _refresh_document_filter(self) -> None:
        current = self.document_filter.currentData()
        documents = sorted({str(row.get("document") or "") for row in self.rows if row.get("document")})

        self.document_filter.blockSignals(True)
        self.document_filter.clear()
        self.document_filter.addItem("Все документы", None)
        for document in documents:
            self.document_filter.addItem(document, document)

        index = self.document_filter.findData(current)
        self.document_filter.setCurrentIndex(index if index >= 0 else 0)
        self.document_filter.blockSignals(False)

    def _show_current_document_entities(self) -> None:
        document = self.document_filter.currentData()
        if document:
            rows = [row for row in self.rows if row.get("document") == document]
        else:
            rows = self.rows
        self._show_grouped_entities(rows, document=document)

    def _show_grouped_entities(self, rows: list[dict], document: str | None = None) -> None:
        if not rows:
            scope = html_module.escape(document) if document else "выбранных документов"
            self.entities_view.setHtml(
                "<div style='color:#d8dee9;'>"
                "<h2 style='margin:0 0 10px 0;'>Сущности не найдены</h2>"
                f"<p style='color:#8e98aa;'>Нет результатов для {scope}.</p>"
                "</div>"
            )
            return

        grouped: dict[str, dict[str, dict]] = {}
        for row in rows:
            label = str(row.get("type") or "неизвестно")
            value = str(row.get("value") or "").strip()
            if not value:
                continue

            item = grouped.setdefault(label, {}).setdefault(value, {
                "count": 0,
                "documents": set(),
                "chunks": [],
                "scores": [],
                "sources": set(),
                "blocks": [],
                "source_count": None,
            })
            item["count"] += 1
            item["documents"].add(str(row.get("document") or ""))
            item["chunks"].extend(int(index) + 1 for index in row.get("chunk_indexes") or [])

            confidence = row.get("confidence")
            if confidence is not None:
                item["scores"].append(float(confidence))

            source = row.get("source")
            if source:
                item["sources"].add(str(source))

            metadata = row.get("metadata") or {}
            if metadata.get("source_count") is not None:
                item["source_count"] = metadata["source_count"]

            if label in {"источник", "фрагмент программного кода"}:
                item["blocks"].append({
                    "title": metadata.get("title") or value,
                    "body": metadata.get("code") or metadata.get("text") or value,
                })

        total = sum(item["count"] for group in grouped.values() for item in group.values())
        html = [
            "<div style='color:#d8dee9; font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",Arial;'>",
            f"<h2 style='margin:0 0 4px 0; color:#f4f7fb;'>Найденные сущности</h2>",
            self._summary_line(total, document),
        ]

        for label in sorted(grouped.keys()):
            entities = grouped[label]
            label_total = sum(item["count"] for item in entities.values())
            html.append(
                "<div style='margin:0 0 14px 0; padding:12px; "
                "background:#1b202b; border:1px solid #303846; border-radius:8px;'>"
                f"<div style='color:#7dd3fc; font-weight:700; font-size:15px; margin-bottom:10px;'>"
                f"{html_module.escape(label)} <span style='color:#8e98aa; font-weight:500;'>({label_total})</span>"
                "</div>"
            )

            sorted_items = sorted(
                entities.items(),
                key=lambda pair: (-pair[1]["count"], pair[0].lower()),
            )

            for value, item in sorted_items:
                details = self._entity_details_text(item)

                if label in {"источник", "фрагмент программного кода"} and item["blocks"]:
                    block = item["blocks"][0]
                    title = html_module.escape(str(block["title"]))
                    body = html_module.escape(str(block["body"]))
                    extra = ""
                    if item["source_count"] is not None:
                        extra = f" | источников: {html_module.escape(str(item['source_count']))}"

                    html.append(
                        "<div style='margin:0 0 12px 0;'>"
                        f"<div style='font-weight:650; color:#eef2ff;'>{title}</div>"
                        f"<div style='color:#8e98aa; font-size:12px; margin:2px 0 6px 0;'>{details}{extra}</div>"
                        "<pre style='white-space:pre-wrap; margin:0; padding:10px; "
                        "background:#11131a; border:1px solid #2d3543; border-radius:6px; "
                        "color:#d8dee9; font-family:Menlo,Consolas,monospace; font-size:12px;'>"
                        f"{body}</pre>"
                        "</div>"
                    )
                else:
                    html.append(
                        "<div style='margin:0 0 8px 0;'>"
                        f"<span style='color:#eef2ff; font-weight:650;'>{html_module.escape(value)}</span> "
                        f"<span style='color:#8e98aa; font-size:12px;'>{details}</span>"
                        "</div>"
                    )

            html.append("</div>")

        html.append("</div>")
        self.entities_view.setHtml("".join(html))

    def _summary_line(self, total: int, document: str | None) -> str:
        if document:
            scope = f"Документ: {html_module.escape(document)}"
        else:
            scope = "Все документы"
        return (
            "<div style='color:#8e98aa; margin-bottom:14px;'>"
            f"{scope} | всего строк: {total}"
            "</div>"
        )

    def _entity_details_text(self, item: dict) -> str:
        parts = []
        if item["count"] > 1:
            parts.append(f"x{item['count']}")

        documents = sorted(doc for doc in item["documents"] if doc)
        if documents:
            shown_docs = ", ".join(documents[:3])
            if len(documents) > 3:
                shown_docs += ", ..."
            parts.append(shown_docs)

        chunks = sorted(set(item["chunks"]))
        if chunks:
            chunks_text = ", ".join(str(index) for index in chunks[:10])
            if len(chunks) > 10:
                chunks_text += ", ..."
            parts.append(f"фрагменты: {chunks_text}")

        if item["scores"]:
            avg_score = sum(item["scores"]) / len(item["scores"])
            parts.append(f"score: {avg_score:.2f}")

        if item["sources"]:
            parts.append(", ".join(sorted(item["sources"])))

        escaped = [html_module.escape(part) for part in parts]
        return " | ".join(escaped)


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
