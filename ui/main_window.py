"""
ui/main_window.py — 主窗口

Tab1: 预览（缩略图 + 大图）
Tab2: 结果（进度 + 实时表格 + 操作按钮）
工具栏: 打开文件 | 修改Prompt | 设置
"""
import os
import threading
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QToolBar, QPushButton, QLabel,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialog,
)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot

from config import load_config, save_config
from ui.preview_panel import PreviewPanel
from ui.progress_panel import ProgressPanel
from ui.prompts_dialog import PromptsDialog
from ui.settings_panel import SettingsPanel
from core.file_reader import extract_images
from core.session import Session


_COL_LABELS = [
    ("url", "URL"),
    ("title", "标题"),
    ("views", "播放量"),
    ("danmaku", "弹幕量"),
    ("date", "发布时间"),
    ("has_playlist", "是否有合集"),
    ("likes", "点赞量"),
    ("coins", "投币量"),
    ("favorites", "收藏量"),
    ("shares", "转发量"),
    ("comments", "评论数"),
    ("description", "视频描述"),
    ("tags", "视频标签"),
    ("notes", "备注"),
]


class MainWindow(QMainWindow):
    # 信号（子线程 → 主线程）
    sig_log_info = pyqtSignal(str)
    sig_log_ok = pyqtSignal(str)
    sig_log_warn = pyqtSignal(str)
    sig_log_error = pyqtSignal(str)
    sig_progress_stage = pyqtSignal(str)
    sig_progress_range = pyqtSignal(int)
    sig_progress_value = pyqtSignal(int)
    sig_row_ready = pyqtSignal(dict)
    sig_done = pyqtSignal(str)  # 完成消息

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF2Excel v2")
        self.resize(1280, 820)

        self._all_images: list[tuple[int, bytes, str]] = []
        self._file_path: str = ""
        self._results: list[dict] = []
        self._stop_flag = threading.Event()
        self._session: Session | None = None

        self._setup_ui()
        self._connect_signals()
        self._apply_config()

    def _setup_ui(self):
        # 工具栏
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.open_action = QAction("📂 打开文件", self)
        self.open_action.triggered.connect(self._open_file)
        toolbar.addAction(self.open_action)

        toolbar.addSeparator()

        self.prompt_action = QAction("✏️ 修改 Prompt", self)
        self.prompt_action.triggered.connect(self._edit_prompts)
        toolbar.addAction(self.prompt_action)

        toolbar.addSeparator()

        self.settings_action = QAction("⚙️ 设置", self)
        self.settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(self.settings_action)

        toolbar.addSeparator()

        self.file_label = QLabel("  未打开文件")
        self.file_label.setStyleSheet("color: #888;")
        toolbar.addWidget(self.file_label)

        # 中心区域
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: 预览
        self.preview_panel = PreviewPanel()
        self.tabs.addTab(self.preview_panel, "📷 预览")

        # Tab 2: 结果
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)
        result_layout.setContentsMargins(4, 4, 4, 4)
        result_layout.setSpacing(6)

        # 操作按钮行
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("▶ 开始提取")
        self.start_btn.setFixedHeight(32)
        self.start_btn.clicked.connect(self._start_extraction)
        self.stop_btn = QPushButton("⏹ 终止")
        self.stop_btn.setFixedHeight(32)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_extraction)
        self.export_btn = QPushButton("📊 导出 Excel")
        self.export_btn.setFixedHeight(32)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_excel)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.export_btn)
        result_layout.addLayout(btn_row)

        # 进度面板
        self.progress_panel = ProgressPanel()
        self.progress_panel.setFixedHeight(200)
        result_layout.addWidget(self.progress_panel)

        # 结果表格
        self.table = QTableWidget(0, len(_COL_LABELS))
        self.table.setHorizontalHeaderLabels([label for _, label in _COL_LABELS])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(0, 320)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        result_layout.addWidget(self.table, stretch=1)

        self.tabs.addTab(result_widget, "📋 结果")

    def _connect_signals(self):
        self.sig_log_info.connect(self.progress_panel.log_info)
        self.sig_log_ok.connect(self.progress_panel.log_ok)
        self.sig_log_warn.connect(self.progress_panel.log_warn)
        self.sig_log_error.connect(self.progress_panel.log_error)
        self.sig_progress_stage.connect(self.progress_panel.set_stage)
        self.sig_progress_range.connect(self.progress_panel.set_range)
        self.sig_progress_value.connect(self.progress_panel.set_value)
        self.sig_row_ready.connect(self._add_table_row)
        self.sig_done.connect(self._on_done)

    def _apply_config(self):
        cfg = load_config()
        if cfg.get("api_key"):
            os.environ["ANTHROPIC_API_KEY"] = cfg["api_key"]

    # ── File loading ────────────────────────────────────────────────────────────

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "",
            "PDF & Word 文件 (*.pdf *.docx);;PDF 文件 (*.pdf);;Word 文件 (*.docx)",
        )
        if not path:
            return
        try:
            images = extract_images(path)
        except Exception as e:
            QMessageBox.critical(self, "读取失败", str(e))
            return

        if not images:
            QMessageBox.warning(self, "提示", "该文件中未找到任何图片")
            return

        self._file_path = path
        self._all_images = images
        self._results = []
        self.file_label.setText(f"  {Path(path).name}  ({len(images)} 张图片)")
        self.preview_panel.load_images(images)
        self.table.setRowCount(0)
        self.progress_panel.reset()
        self.export_btn.setEnabled(False)
        self.tabs.setCurrentIndex(0)

    # ── Settings / Prompts ──────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("设置")
        dlg.resize(600, 500)
        layout = QVBoxLayout(dlg)
        panel = SettingsPanel(dlg)
        layout.addWidget(panel)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        dlg.exec()
        self._apply_config()

    def _edit_prompts(self):
        dlg = PromptsDialog(self)
        dlg.exec()

    # ── Extraction ──────────────────────────────────────────────────────────────

    def _start_extraction(self):
        if not self._file_path:
            QMessageBox.warning(self, "提示", "请先打开文件")
            return

        cfg = load_config()
        api_key = cfg.get("api_key", "")
        base_url = cfg.get("base_url", "")
        model1 = cfg.get("model_stage1", "")
        model2 = cfg.get("model_stage2", "")

        if not api_key or not base_url:
            QMessageBox.critical(self, "错误", "请先在「设置」中填写 API Key 和 Base URL")
            self._open_settings()
            return
        if not model1 or not model2:
            QMessageBox.critical(self, "错误", "请先在「设置」中检测并选择 Stage1 和 Stage2 模型")
            self._open_settings()
            return

        prompt1 = cfg.get("prompt1", "")
        prompt2 = cfg.get("prompt2", "")

        # 检查断点续提
        session = Session(self._file_path)
        resume = False
        if session.exists():
            data = session.load()
            n_done = len(data.get("processed", {}))
            total_c = len(data.get("candidates", []))
            reply = QMessageBox.question(
                self,
                "检测到上次进度",
                f"检测到上次提取记录：\n"
                f"  候选图片：{total_c} 张\n"
                f"  已处理：{n_done} 张\n\n"
                f"是否从上次中断处继续？\n"
                f"（选「否」将重新开始）",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            resume = (reply == QMessageBox.StandardButton.Yes)
            if not resume:
                session.delete()

        self._session = session
        self._stop_flag.clear()
        self._results = []
        self.table.setRowCount(0)
        self.progress_panel.reset()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.export_btn.setEnabled(False)
        self.tabs.setCurrentIndex(1)

        threading.Thread(
            target=self._worker,
            args=(api_key, base_url, model1, model2, prompt1, prompt2, resume),
            daemon=True,
        ).start()

    def _stop_extraction(self):
        self._stop_flag.set()
        self.stop_btn.setEnabled(False)
        self.sig_log_warn.emit("⏹ 正在终止，等待当前任务完成...")

    def _worker(
        self,
        api_key: str,
        base_url: str,
        model1: str,
        model2: str,
        prompt1: str,
        prompt2: str,
        resume: bool,
    ):
        from core.grid_filter import run_stage1
        from core.detail_extractor import run_stage2
        from core.aggregator import aggregate

        all_images = self._all_images
        session = self._session

        try:
            # ── Stage 1 ────────────────────────────────────────────
            if resume and session.is_stage1_done():
                candidates = session.get_candidates()
                self.sig_log_ok.emit(f"✅ 跳过 Stage1（上次已完成），候选 {len(candidates)} 张")
            else:
                total_imgs = len(all_images)
                from core.grid_filter import BATCH_SIZE
                total_batches = (total_imgs + BATCH_SIZE - 1) // BATCH_SIZE

                self.sig_progress_stage.emit("Stage1 过滤中")
                self.sig_progress_range.emit(total_batches)
                self.sig_log_info.emit(
                    f"📂 共 {total_imgs} 张图片，分 {total_batches} 批过滤（每批12张）..."
                )

                if not resume:
                    session.init(self._file_path, total_imgs)

                batch_done = [0]

                def stage1_cb(done, total, found):
                    batch_done[0] = done
                    self.sig_progress_value.emit(done)
                    self.sig_log_info.emit(
                        f"  批次 {done}/{total}：找到候选 {found}"
                    )

                candidates = run_stage1(
                    all_images, prompt1, model1, api_key, base_url,
                    progress_cb=stage1_cb, stop_flag=self._stop_flag,
                )
                if not self._stop_flag.is_set():
                    session.set_candidates(candidates)
                self.sig_log_ok.emit(f"✅ Stage1 完成，共 {len(candidates)} 张候选图片")

            if self._stop_flag.is_set():
                self.sig_done.emit(f"⏹ 已终止（候选 {len(candidates)} 张待提取）")
                return

            # ── Stage 2 ────────────────────────────────────────────
            self.sig_progress_stage.emit("Stage2 提取中")
            self.sig_progress_range.emit(len(candidates))
            self.sig_log_info.emit(
                f"🔍 开始精细提取 {len(candidates)} 张候选图片..."
            )

            done_count = [0]

            def stage2_cb(done, total, img_idx, result):
                done_count[0] = done
                self.sig_progress_value.emit(done)
                match = result.get("match", False)
                mark = "✓" if match else "·"
                err = f" ⚠ {result.get('error','')[:50]}" if result.get("error") else ""
                self.sig_log_info.emit(f"  图{img_idx + 1:>4} {mark}{err}")

            all_results = run_stage2(
                all_images, candidates, prompt2, model2, api_key, base_url,
                session=session, progress_cb=stage2_cb, stop_flag=self._stop_flag,
                max_workers=4,
            )

            if self._stop_flag.is_set():
                self.sig_done.emit(f"⏹ 已终止（已处理 {len(all_results)} 张）")
                return

            # ── Stage 3: 聚合 ──────────────────────────────────────
            self.sig_progress_stage.emit("聚合中")
            self.sig_log_info.emit("📊 聚合结果，URL 去重...")
            rows = aggregate(all_results, all_images)
            self._results = rows
            for row in rows:
                self.sig_row_ready.emit(row)

            session.delete()
            self.sig_done.emit(
                f"✅ 完成！共 {len(all_images)} 张图片，找到 {len(rows)} 条视频记录"
            )

        except Exception as e:
            self.sig_log_error.emit(f"❌ 错误：{e}")
            self.sig_done.emit(f"❌ 提取失败：{str(e)[:80]}")

    # ── Table ───────────────────────────────────────────────────────────────────

    @pyqtSlot(dict)
    def _add_table_row(self, row: dict):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for col, (key, _) in enumerate(_COL_LABELS):
            val = row.get(key, "")
            item = QTableWidgetItem(str(val) if val else "")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, col, item)

    @pyqtSlot(str)
    def _on_done(self, msg: str):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_panel.set_stage("完成")
        self.progress_panel.log_ok(msg)
        if self._results:
            self.export_btn.setEnabled(True)
        QMessageBox.information(self, "完成", msg)

    # ── Export ──────────────────────────────────────────────────────────────────

    def _export_excel(self):
        if not self._results:
            QMessageBox.warning(self, "提示", "没有可导出的结果")
            return
        default_name = Path(self._file_path).stem + "_extracted.xlsx" if self._file_path else "output.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Excel", default_name, "Excel 文件 (*.xlsx)"
        )
        if not path:
            return
        try:
            from core.exporter import export_excel
            export_excel(self._results, path)
            QMessageBox.information(self, "导出完成", f"已保存：\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def closeEvent(self, event):
        if self.stop_btn.isEnabled():
            self._stop_flag.set()
        super().closeEvent(event)
