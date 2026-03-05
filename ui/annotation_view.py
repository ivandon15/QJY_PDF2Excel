import json
import os
import pathlib
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea
)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt, QRect, QPoint

REGIONS_FILE = str(pathlib.Path(__file__).parent.parent / "regions.json")

COLORS = [
    QColor(255, 50, 50),
    QColor(50, 180, 255),
    QColor(50, 220, 80),
    QColor(255, 180, 0),
    QColor(200, 80, 255),
]


class AnnotationView(QWidget):
    def __init__(self):
        super().__init__()
        self.saved_rects = []
        self._load_regions()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("保存区域")
        self.save_btn.clicked.connect(self._save_regions)
        self.clear_btn = QPushButton("清除全部")
        self.clear_btn.clicked.connect(self._clear_regions)
        self.status_label = QLabel("拖拽画框；右键点击框可删除")
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.status_label)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.canvas = _Canvas(self)
        self.canvas.rects_changed.connect(self._on_rects_changed)
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)
        layout.addWidget(scroll)

    def set_image(self, qimg: QImage):
        self.canvas.set_image(qimg, list(self.saved_rects))

    def _on_rects_changed(self, count):
        self.status_label.setText(f"已画 {count} 个框，右键删除；点保存生效")

    def _load_regions(self):
        self.saved_rects = []
        if os.path.exists(REGIONS_FILE):
            with open(REGIONS_FILE) as f:
                data = json.load(f)
            for r in data.get("regions", []):
                x, y, w, h = r["rect"]
                self.saved_rects.append(QRect(x, y, w, h))

    def _save_regions(self):
        rects = self.canvas.rects
        if not rects:
            self.status_label.setText("请先画至少一个框")
            return
        data = {
            "image_size": [1600, 900],
            "regions": [
                {"name": f"region_{i+1}", "rect": [r.x(), r.y(), r.width(), r.height()]}
                for i, r in enumerate(rects)
            ]
        }
        with open(REGIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        self.saved_rects = list(rects)
        self.status_label.setText(f"已保存 {len(rects)} 个区域")

    def _clear_regions(self):
        self.canvas.rects = []
        self.canvas.update()
        self.saved_rects = []
        if os.path.exists(REGIONS_FILE):
            os.remove(REGIONS_FILE)
        self.status_label.setText("已清除全部区域")


from PyQt6.QtCore import pyqtSignal


class _Canvas(QWidget):
    rects_changed = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(parent)
        self.pixmap = None
        self.rects = []
        self._drag_start = None
        self._current_drag = None
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMinimumSize(400, 300)

    def set_image(self, qimg: QImage, saved_rects=None):
        self.pixmap = QPixmap.fromImage(qimg)
        self.setFixedSize(self.pixmap.size())
        self.rects = list(saved_rects) if saved_rects else []
        self._current_drag = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.pixmap:
            painter.drawPixmap(0, 0, self.pixmap)
        else:
            painter.fillRect(self.rect(), QColor(40, 40, 40))
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "点击左侧缩略图加载页面")

        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        painter.setFont(font)

        for i, r in enumerate(self.rects):
            color = COLORS[i % len(COLORS)]
            pen = QPen(color, 2)
            painter.setPen(pen)
            painter.drawRect(r)
            painter.fillRect(r.x(), r.y(), 22, 20, color)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(r.x() + 4, r.y() + 15, str(i + 1))

        if self._current_drag:
            pen = QPen(QColor(255, 255, 100), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(self._current_drag)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
            self._current_drag = None
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self._delete_rect_at(event.pos())

    def mouseMoveEvent(self, event):
        if self._drag_start:
            self._current_drag = QRect(self._drag_start, event.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start:
            rect = QRect(self._drag_start, event.pos()).normalized()
            if rect.width() > 5 and rect.height() > 5:
                self.rects.append(rect)
                self.rects_changed.emit(len(self.rects))
            self._drag_start = None
            self._current_drag = None
            self.update()

    def _delete_rect_at(self, pos: QPoint):
        for i, r in enumerate(self.rects):
            if r.contains(pos):
                self.rects.pop(i)
                self.rects_changed.emit(len(self.rects))
                self.update()
                return
