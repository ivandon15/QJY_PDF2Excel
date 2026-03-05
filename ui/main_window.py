import os
import json
import pathlib
import threading
import fitz
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QFileDialog,
    QPushButton, QTabWidget, QSplitter, QTableWidget,
    QTableWidgetItem, QProgressBar, QMessageBox, QLabel
)
from PyQt6.QtGui import QPixmap, QImage, QIcon
from PyQt6.QtCore import Qt, QSize, pyqtSlot, pyqtSignal

from ui.annotation_view import AnnotationView
from ui.settings_tab import SettingsTab

_REGIONS_FILE = str(pathlib.Path(__file__).parent.parent / "regions.json")


class MainWindow(QMainWindow):
    row_ready = pyqtSignal(object)
    progress_updated = pyqtSignal(int)
    extraction_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF2Excel")
        self.resize(1200, 800)
        self.pdf_doc = None
        self.pdf_path = None
        self.results = []
        self._col_keys = []  # dynamic column keys
        self._setup_ui()
        self._apply_saved_config()
        self.row_ready.connect(self._add_table_row)
        self.progress_updated.connect(self._update_progress)
        self.extraction_finished.connect(self._extraction_done)

    def _apply_saved_config(self):
        import os
        from config import load_config
        cfg = load_config()
        if cfg.get("api_key"):
            os.environ["ANTHROPIC_API_KEY"] = cfg["api_key"]
        if cfg.get("base_url"):
            os.environ["ANTHROPIC_BASE_URL"] = cfg["base_url"]

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # --- Left panel ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left.setFixedWidth(210)

        open_btn = QPushButton("打开 PDF")
        open_btn.clicked.connect(self._open_pdf)
        left_layout.addWidget(open_btn)

        self.pdf_label = QLabel("未选择文件")
        self.pdf_label.setWordWrap(True)
        left_layout.addWidget(self.pdf_label)

        self.thumb_list = QListWidget()
        self.thumb_list.setIconSize(QSize(160, 90))
        self.thumb_list.itemClicked.connect(self._on_thumb_click)
        left_layout.addWidget(self.thumb_list)

        splitter.addWidget(left)

        # --- Right panel (tabs) ---
        self.tabs = QTabWidget()
        splitter.addWidget(self.tabs)
        splitter.setSizes([210, 990])

        # Tab 1: 区域设置
        self.annotation_view = AnnotationView()
        self.tabs.addTab(self.annotation_view, "区域设置")

        # Tab 2: 提取结果
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("开始提取")
        self.run_btn.clicked.connect(self._run_extraction)
        self.export_btn = QPushButton("导出 Excel")
        self.export_btn.clicked.connect(self._export_excel)
        self.export_btn.setEnabled(False)
        self.progress = QProgressBar()
        self.progress_label = QLabel("")
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(self.progress)
        btn_row.addWidget(self.progress_label)
        result_layout.addLayout(btn_row)

        self.table = QTableWidget(0, 1)
        self.table.setHorizontalHeaderLabels(["页码"])
        self.table.horizontalHeader().setStretchLastSection(True)
        result_layout.addWidget(self.table)

        self.tabs.addTab(result_widget, "提取结果")

        # Tab 3: 设置
        self.settings_tab = SettingsTab()
        self.tabs.addTab(self.settings_tab, "设置")

    # --- PDF loading ---

    def _open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 PDF", "files", "PDF Files (*.pdf)"
        )
        if not path:
            return
        self.pdf_path = path
        if self.pdf_doc is not None:
            self.pdf_doc.close()
        self.pdf_doc = fitz.open(path)
        self.pdf_label.setText(os.path.basename(path))
        self._load_thumbnails()

    def _load_thumbnails(self):
        self.thumb_list.clear()
        for i in range(len(self.pdf_doc)):
            page = self.pdf_doc[i]
            imgs = page.get_images(full=True)
            if imgs:
                xref = imgs[0][0]
                img_data = self.pdf_doc.extract_image(xref)
                qimg = QImage.fromData(img_data["image"])
                pixmap = QPixmap.fromImage(qimg).scaled(
                    160, 90,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                item = QListWidgetItem(f"第 {i + 1} 页")
                item.setIcon(QIcon(pixmap))
                item.setData(Qt.ItemDataRole.UserRole, i)
                self.thumb_list.addItem(item)

    def _on_thumb_click(self, item):
        page_idx = item.data(Qt.ItemDataRole.UserRole)
        imgs = self.pdf_doc[page_idx].get_images(full=True)
        if imgs:
            xref = imgs[0][0]
            img_data = self.pdf_doc.extract_image(xref)
            qimg = QImage.fromData(img_data["image"])
            self.annotation_view.set_image(qimg)
            self.tabs.setCurrentIndex(0)

    # --- Extraction ---

    def _run_extraction(self):
        if not self.pdf_doc:
            QMessageBox.warning(self, "提示", "请先打开 PDF")
            return
        if not os.environ.get("ANTHROPIC_API_KEY"):
            QMessageBox.critical(self, "错误", "请先在「设置」tab 填写 API Key")
            self.tabs.setCurrentIndex(2)
            return

        prompt = self.settings_tab.get_prompt()
        if not prompt:
            QMessageBox.critical(self, "错误", "请先在「设置」tab 填写 Prompt")
            self.tabs.setCurrentIndex(2)
            return

        crop_regions = None
        if os.path.exists(_REGIONS_FILE):
            with open(_REGIONS_FILE) as f:
                data = json.load(f)
            regions = data.get("regions", [])
            if regions:
                crop_regions = regions

        self.run_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.thumb_list.setEnabled(False)
        self.results = []
        total = len(self.pdf_doc)
        self.progress.setMaximum(total)
        self.progress.setValue(0)
        self.table.setRowCount(0)
        self.tabs.setCurrentIndex(1)

        # Extract all image bytes on the main thread before handing off to worker
        page_images = []
        for i in range(total):
            try:
                page = self.pdf_doc[i]
                imgs = page.get_images(full=True)
                if imgs:
                    xref = imgs[0][0]
                    img_data = self.pdf_doc.extract_image(xref)
                    page_images.append((i, img_data["image"], img_data["ext"]))
                else:
                    page_images.append((i, None, None))
            except Exception:
                page_images.append((i, None, None))

        def process_one(args):
            from extractor import extract_from_bytes
            i, image_bytes, img_ext = args
            try:
                if image_bytes is None:
                    return i, {}
                return i, extract_from_bytes(image_bytes, img_ext, crop_regions, prompt)
            except Exception as e:
                return i, {"error": str(e)}

        def worker():
            from concurrent.futures import ThreadPoolExecutor, as_completed
            completed = 0
            futures_map = {}
            with ThreadPoolExecutor(max_workers=5) as executor:
                for args in page_images:
                    f = executor.submit(process_one, args)
                    futures_map[f] = args[0]

                for future in as_completed(futures_map):
                    i, result = future.result()
                    completed += 1
                    if result.get("match"):
                        row = {"page": i + 1}
                        row.update({k: v for k, v in result.items() if k != "match"})
                        self.results.append(row)
                        self.row_ready.emit(row)
                    self.progress_updated.emit(completed)

            self.extraction_finished.emit()

        threading.Thread(target=worker, daemon=True).start()

    @pyqtSlot(object)
    def _add_table_row(self, row):
        # Build/extend columns dynamically from row keys
        new_keys = [k for k in row if k not in self._col_keys]
        if new_keys:
            self._col_keys.extend(new_keys)
            self.table.setColumnCount(len(self._col_keys))
            self.table.setHorizontalHeaderLabels(self._col_keys)

        r = self.table.rowCount()
        self.table.insertRow(r)
        for col, key in enumerate(self._col_keys):
            item = QTableWidgetItem(str(row.get(key, "")))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, col, item)

    @pyqtSlot(int)
    def _update_progress(self, val):
        self.progress.setValue(val)
        self.progress_label.setText(f"{val}/{self.progress.maximum()}")

    @pyqtSlot()
    def _extraction_done(self):
        self.run_btn.setEnabled(True)
        self.export_btn.setEnabled(bool(self.results))
        self.thumb_list.setEnabled(True)
        self._col_keys = []  # reset for next run
        found = len(self.results)
        total = self.progress.maximum()
        QMessageBox.information(self, "完成", f"提取完成！共 {total} 页，找到 {found} 条匹配结果")

    # --- Export ---

    def _export_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存 Excel", "output.xlsx", "Excel (*.xlsx)")
        if path:
            try:
                from exporter import export_to_excel
                export_to_excel(self.results, path)
                QMessageBox.information(self, "完成", f"已导出到:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

    def closeEvent(self, event):
        if self.pdf_doc is not None:
            self.pdf_doc.close()
        super().closeEvent(event)
