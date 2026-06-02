"""
Manga page reader — vertical scroll, lazy image loading.
Navigation: prev/next chapter buttons, keyboard left/right, chapter selector.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QComboBox, QProgressBar, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QKeyEvent

from .workers import MangaPagesWorker, ImageWorker
from .. import db


class _PageLabel(QLabel):
    """Single manga page label that loads its image lazily."""
    def __init__(self, url: str, reader_width: int):
        super().__init__()
        self._url = url
        self._reader_width = reader_width
        self._loaded = False
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setStyleSheet("background: #0a0a0a;")
        self.setMinimumHeight(60)
        self.setText("…")

    def load(self):
        if self._loaded:
            return
        self._loaded = True
        w = ImageWorker(self._url)
        w.image_ready.connect(self._set_image)
        w.start()
        self._iw = w

    def _set_image(self, data: bytes):
        pix = QPixmap()
        pix.loadFromData(data)
        if pix.isNull():
            self.setText("⚠ Failed")
            return
        scaled = pix.scaledToWidth(
            self._reader_width - 8,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled)
        self.setFixedHeight(scaled.height())


class MangaReaderView(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manga      = None
        self._chapters   = []
        self._chapter    = None
        self._pages      = []
        self._page_labels = []
        self._pages_worker = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────────────────
        topbar = QWidget()
        topbar.setStyleSheet("background:#16161e; border-bottom:1px solid #2a2a3a;")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.setSpacing(8)

        back_btn = QPushButton("← Back")
        back_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#c084fc;border:none;font-size:13px;}"
            "QPushButton:hover{color:#d8a4ff;}"
        )
        back_btn.setFixedWidth(80)
        back_btn.clicked.connect(self.back_requested)
        tb.addWidget(back_btn)

        self._title_label = QLabel()
        self._title_label.setObjectName("sectionLabel")
        tb.addWidget(self._title_label)

        tb.addStretch()

        self._prev_btn = QPushButton("◀ Prev Ch")
        self._prev_btn.setProperty("flat", True)
        self._prev_btn.setFixedWidth(90)
        self._prev_btn.clicked.connect(self._go_prev)
        tb.addWidget(self._prev_btn)

        self._ch_combo = QComboBox()
        self._ch_combo.setMinimumWidth(180)
        self._ch_combo.currentIndexChanged.connect(self._on_combo_changed)
        tb.addWidget(self._ch_combo)

        self._next_btn = QPushButton("Next Ch ▶")
        self._next_btn.setProperty("flat", True)
        self._next_btn.setFixedWidth(90)
        self._next_btn.clicked.connect(self._go_next)
        tb.addWidget(self._next_btn)

        self._datasaver_btn = QPushButton("Data Saver: Off")
        self._datasaver_btn.setProperty("flat", True)
        self._datasaver_btn.setFixedWidth(120)
        self._datasaver_btn.setCheckable(True)
        self._datasaver_btn.toggled.connect(self._toggle_datasaver)
        tb.addWidget(self._datasaver_btn)

        root.addWidget(topbar)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(3)
        self._progress.setStyleSheet(
            "QProgressBar{background:#0f0f13;border:none;}"
            "QProgressBar::chunk{background:#c084fc;}"
        )
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # ── Page scroll area ──────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea{background:#0a0a0a;border:none;}")

        self._pages_container = QWidget()
        self._pages_container.setStyleSheet("background:#0a0a0a;")
        self._pages_layout = QVBoxLayout(self._pages_container)
        self._pages_layout.setContentsMargins(0, 0, 0, 0)
        self._pages_layout.setSpacing(2)
        self._pages_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._pages_container)
        root.addWidget(self._scroll, 1)

        self._scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)

    # ── Public API ────────────────────────────────────────────────────────────

    def open(self, manga, chapters: list, chapter):
        self._manga    = manga
        self._chapters = chapters
        self._chapter  = chapter
        self._data_saver = False

        # Populate chapter combo
        self._ch_combo.blockSignals(True)
        self._ch_combo.clear()
        for ch in chapters:
            label = f"Ch. {ch.chapter_num}"
            if ch.title:
                label += f" — {ch.title}"
            self._ch_combo.addItem(label, ch)
        # Select current
        for i, ch in enumerate(chapters):
            if ch.chapter_id == chapter.chapter_id:
                self._ch_combo.setCurrentIndex(i)
                break
        self._ch_combo.blockSignals(False)

        self._load_chapter(chapter)

    # ── Chapter loading ───────────────────────────────────────────────────────

    def _load_chapter(self, chapter):
        self._chapter = chapter
        ch_label = f"Ch. {chapter.chapter_num}"
        if chapter.title:
            ch_label += f" — {chapter.title}"
        self._title_label.setText(f"{self._manga.title}  /  {ch_label}")
        self._clear_pages()
        self._progress.setVisible(True)

        if self._pages_worker and self._pages_worker.isRunning():
            self._pages_worker.terminate()
        self._pages_worker = MangaPagesWorker(
            chapter.chapter_id, self._data_saver,
            manga_id=self._manga.manga_id if self._manga else "",
            lang=chapter.lang,
        )
        self._pages_worker.results_ready.connect(self._on_pages)
        self._pages_worker.error.connect(lambda e: self._on_error(e))
        self._pages_worker.start()

    def _on_pages(self, urls: list):
        self._progress.setVisible(False)
        self._pages = urls
        self._page_labels = []
        w = self._scroll.viewport().width() or 800
        for url in urls:
            lbl = _PageLabel(url, w)
            self._pages_layout.addWidget(lbl)
            self._page_labels.append(lbl)
        # Load first few pages immediately
        for lbl in self._page_labels[:3]:
            lbl.load()
        # Scroll to top
        self._scroll.verticalScrollBar().setValue(0)
        # Mark chapter as read
        if self._manga and self._chapter:
            db.mark_chapter_read(self._manga.manga_id, self._chapter.chapter_id,
                                 self._chapter.chapter_num, self._manga.title)
        # Update nav buttons
        idx = self._ch_combo.currentIndex()
        self._prev_btn.setEnabled(idx > 0)
        self._next_btn.setEnabled(idx < len(self._chapters) - 1)

    def _on_error(self, err: str):
        self._progress.setVisible(False)
        lbl = QLabel(f"⚠ Failed to load pages: {err}")
        lbl.setStyleSheet("color:#f87171; padding:20px;")
        self._pages_layout.addWidget(lbl)

    def _clear_pages(self):
        while self._pages_layout.count():
            item = self._pages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._page_labels = []
        self._pages = []

    # ── Lazy loading on scroll ────────────────────────────────────────────────

    def _on_scroll(self, value):
        vp_height = self._scroll.viewport().height()
        for lbl in self._page_labels:
            if lbl.geometry().top() < value + vp_height + 800:
                lbl.load()

    # ── Navigation ────────────────────────────────────────────────────────────

    def _go_prev(self):
        idx = self._ch_combo.currentIndex()
        if idx > 0:
            self._ch_combo.setCurrentIndex(idx - 1)

    def _go_next(self):
        idx = self._ch_combo.currentIndex()
        if idx < self._ch_combo.count() - 1:
            self._ch_combo.setCurrentIndex(idx + 1)

    def _on_combo_changed(self, idx):
        ch = self._ch_combo.itemData(idx)
        if ch and ch.chapter_id != (self._chapter.chapter_id if self._chapter else None):
            self._load_chapter(ch)

    def _toggle_datasaver(self, on: bool):
        self._data_saver = on
        self._datasaver_btn.setText("Data Saver: On" if on else "Data Saver: Off")
        if self._chapter:
            self._load_chapter(self._chapter)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_N):
            self._go_next()
        elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_P):
            self._go_prev()
        elif event.key() == Qt.Key.Key_Escape:
            self.back_requested.emit()
        else:
            super().keyPressEvent(event)
