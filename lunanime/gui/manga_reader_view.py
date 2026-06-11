"""
Manga page reader — vertical scroll, lazy image loading.
Navigation: prev/next chapter buttons, keyboard left/right, chapter selector.
Zoom: +/- buttons, Ctrl+scroll, keyboard +/- and 0 to reset.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QComboBox, QProgressBar, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QPixmap, QKeyEvent, QWheelEvent

from .workers import (MangaPagesWorker, WeebCentralPagesWorker,
                      MangaFirePagesWorker, MangaPillPagesWorker,
                      MangakakalotPagesWorker, MangaKatanaPagesWorker,
                      ReadAllComicsPagesWorker, ImageWorker)
from .. import db

# source key -> (pages worker, referer needed by the image CDN)
_PAGE_SOURCES = {
    "mangadex":      (MangaPagesWorker,         ""),
    "weebcentral":   (WeebCentralPagesWorker,   "https://weebcentral.com/"),
    "mangafire":     (MangaFirePagesWorker,     "https://mangafire.to/"),
    "mangapill":     (MangaPillPagesWorker,     "https://mangapill.com/"),
    "mangakakalot":  (MangakakalotPagesWorker,  "https://www.mangakakalot.gg/"),
    "mangakatana":   (MangaKatanaPagesWorker,   "https://mangakatana.com/"),
    "readallcomics": (ReadAllComicsPagesWorker, "https://readallcomics.com/"),
}

_ZOOM_MIN = 0.3
_ZOOM_MAX = 2.0
_ZOOM_STEP = 0.1


class _PageLabel(QLabel):
    """Single manga page label — lazy loads image, supports rescaling."""
    def __init__(self, url: str, referer: str = ""):
        super().__init__()
        self._url = url
        self._referer = referer
        self._loaded = False
        self._raw: bytes | None = None
        self._display_width = 800
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setStyleSheet("background: #0a0a0a;")
        self.setMinimumHeight(60)
        self.setText("…")

    def load(self):
        if self._loaded:
            return
        self._loaded = True
        w = ImageWorker(self._url, referer=self._referer)
        w.image_ready.connect(self._set_image)
        w.start()
        self._iw = w

    def rescale(self, width: int):
        self._display_width = width
        if self._raw:
            self._render()

    def _set_image(self, data: bytes):
        self._raw = data
        self._render()

    def _render(self):
        if not self._raw:
            return
        pix = QPixmap()
        pix.loadFromData(self._raw)
        if pix.isNull():
            self.setText("⚠ Failed")
            return
        scaled = pix.scaledToWidth(
            max(1, self._display_width),
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self.setFixedHeight(scaled.height())


class MangaReaderView(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manga        = None
        self._chapters     = []
        self._chapter      = None
        self._pages        = []
        self._page_labels  = []
        self._pages_worker = None
        self._data_saver   = False
        self._zoom         = 1.0
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

        # Zoom controls
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setProperty("flat", True)
        zoom_out_btn.setFixedWidth(32)
        zoom_out_btn.setToolTip("Zoom out (−)")
        zoom_out_btn.clicked.connect(self._zoom_out)
        tb.addWidget(zoom_out_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(44)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_label.setStyleSheet("color:#9090a0; font-size:11px;")
        self._zoom_label.mousePressEvent = lambda _: self._zoom_reset()
        self._zoom_label.setToolTip("Click to reset zoom")
        self._zoom_label.setCursor(Qt.CursorShape.PointingHandCursor)
        tb.addWidget(self._zoom_label)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setProperty("flat", True)
        zoom_in_btn.setFixedWidth(32)
        zoom_in_btn.setToolTip("Zoom in (+)")
        zoom_in_btn.clicked.connect(self._zoom_in)
        tb.addWidget(zoom_in_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color:#2a2a3a;")
        tb.addWidget(sep)

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
        self._manga      = manga
        self._chapters   = chapters
        self._chapter    = chapter
        self._data_saver = False
        self._zoom       = 1.0
        self._zoom_label.setText("100%")

        self._ch_combo.blockSignals(True)
        self._ch_combo.clear()
        for ch in chapters:
            label = f"Ch. {ch.chapter_num}"
            if ch.title:
                label += f" — {ch.title}"
            self._ch_combo.addItem(label, ch)
        for i, ch in enumerate(chapters):
            if ch.chapter_id == chapter.chapter_id:
                self._ch_combo.setCurrentIndex(i)
                break
        self._ch_combo.blockSignals(False)

        self._load_chapter(chapter)

    # ── Zoom ─────────────────────────────────────────────────────────────────

    def _effective_width(self) -> int:
        vp_w = self._scroll.viewport().width() or 800
        return max(1, int((vp_w - 8) * self._zoom))

    def _apply_zoom(self):
        self._zoom_label.setText(f"{int(self._zoom * 100)}%")
        w = self._effective_width()
        for lbl in self._page_labels:
            lbl.rescale(w)

    def _zoom_in(self):
        self._zoom = min(_ZOOM_MAX, round(self._zoom + _ZOOM_STEP, 2))
        self._apply_zoom()

    def _zoom_out(self):
        self._zoom = max(_ZOOM_MIN, round(self._zoom - _ZOOM_STEP, 2))
        self._apply_zoom()

    def _zoom_reset(self):
        self._zoom = 1.0
        self._apply_zoom()

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
            self._pages_worker.retire()

        source = getattr(self._manga, "source", "mangadex")
        pages_cls, self._page_referer = _PAGE_SOURCES.get(source, _PAGE_SOURCES["mangadex"])
        self._pages_worker = pages_cls(chapter.chapter_id, self._data_saver)
        self._pages_worker.results_ready.connect(self._on_pages)
        self._pages_worker.error.connect(lambda e: self._on_error(e))
        self._pages_worker.start()

    def _on_pages(self, urls: list):
        self._progress.setVisible(False)
        self._pages = urls
        self._page_labels = []
        w = self._effective_width()
        for url in urls:
            lbl = _PageLabel(url, referer=getattr(self, "_page_referer", ""))
            lbl.rescale(w)
            self._pages_layout.addWidget(lbl)
            self._page_labels.append(lbl)
        for lbl in self._page_labels[:3]:
            lbl.load()
        self._scroll.verticalScrollBar().setValue(0)
        if self._manga and self._chapter:
            db.mark_chapter_read(self._manga.manga_id, self._chapter.chapter_id,
                                 self._chapter.chapter_num, self._manga.title,
                                 source=getattr(self._manga, "source", "mangadex"),
                                 cover_url=getattr(self._manga, "cover_url", "") or None)
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

    # ── Input handling ────────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self._zoom_in()
            else:
                self._zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        k = event.key()
        if k in (Qt.Key.Key_Right, Qt.Key.Key_N):
            self._go_next()
        elif k in (Qt.Key.Key_Left, Qt.Key.Key_P):
            self._go_prev()
        elif k in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self._zoom_in()
        elif k == Qt.Key.Key_Minus:
            self._zoom_out()
        elif k == Qt.Key.Key_0:
            self._zoom_reset()
        elif k == Qt.Key.Key_Escape:
            self.back_requested.emit()
        else:
            super().keyPressEvent(event)
