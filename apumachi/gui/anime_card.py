from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QCursor

from .workers import ImageWorker


class AnimeCard(QWidget):
    clicked = pyqtSignal(object)  # emits ProviderSearchResult

    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self.setObjectName("animeCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(150, 230)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.poster = QLabel()
        self.poster.setFixedSize(138, 185)
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster.setStyleSheet("background-color: #1e1e2e; border-radius: 6px; color: #555566;")
        self.poster.setText("...")
        layout.addWidget(self.poster)

        name_label = QLabel(result.name)
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size: 10px; color: #c0c0d0; background: transparent;")
        name_label.setFixedHeight(30)
        layout.addWidget(name_label)

    def set_image(self, data: bytes):
        pix = QPixmap()
        pix.loadFromData(data)
        if not pix.isNull():
            pix = pix.scaled(138, 185, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                             Qt.TransformationMode.SmoothTransformation)
            pix = pix.copy(0, 0, 138, 185)
            self.poster.setPixmap(pix)
            self.poster.setText("")

    def load_image(self, url: str):
        self._img_worker = ImageWorker(url)
        self._img_worker.image_ready.connect(self.set_image)
        self._img_worker.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.result)
