"""
ui/preview_panel.py — 缩略图列表 + 大图预览
"""
import io
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QScrollArea,
)
from PyQt6.QtGui import QPixmap, QImage, QIcon
from PyQt6.QtCore import Qt, QSize


class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._images: list[tuple[bytes, str]] = []  # [(bytes, ext), ...]
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 左侧缩略图列表
        self.thumb_list = QListWidget()
        self.thumb_list.setIconSize(QSize(160, 90))
        self.thumb_list.setFixedWidth(200)
        self.thumb_list.setSpacing(2)
        self.thumb_list.itemClicked.connect(self._on_click)
        layout.addWidget(self.thumb_list)

        # 右侧大图预览
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label = QLabel("← 点击左侧缩略图预览")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("color: #888; font-size: 14px;")
        scroll.setWidget(self.preview_label)
        layout.addWidget(scroll, stretch=1)

    def load_images(self, images: list[tuple[int, bytes, str]]):
        """加载图片列表 [(index, bytes, ext), ...]"""
        self._images = [(b, e) for _, b, e in images]
        self.thumb_list.clear()
        self.preview_label.setText("← 点击左侧缩略图预览")

        for i, (img_bytes, _ext) in enumerate(self._images):
            qimg = QImage.fromData(img_bytes)
            if qimg.isNull():
                item = QListWidgetItem(f"图片 {i + 1}")
            else:
                pixmap = QPixmap.fromImage(qimg).scaled(
                    160, 90,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                item = QListWidgetItem(QIcon(pixmap), f"图片 {i + 1}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.thumb_list.addItem(item)

    def clear(self):
        self._images = []
        self.thumb_list.clear()
        self.preview_label.setText("")

    def _on_click(self, item: QListWidgetItem):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self._images):
            img_bytes, _ = self._images[idx]
            qimg = QImage.fromData(img_bytes)
            if not qimg.isNull():
                pixmap = QPixmap.fromImage(qimg)
                # 按预览区宽度缩放
                max_w = self.preview_label.parent().width() - 20
                if pixmap.width() > max_w:
                    pixmap = pixmap.scaledToWidth(
                        max_w, Qt.TransformationMode.SmoothTransformation
                    )
                self.preview_label.setPixmap(pixmap)
                self.preview_label.resize(pixmap.size())
