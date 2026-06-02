"""
Manga search + detail view.
- Left: search results grid (AnimeCard-compatible covers)
- Right: detail panel with chapter list when a manga is selected
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QGridLayout, QListWidget,
    QListWidgetItem, QSplitter, QComboBox, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from .anime_card import AnimeCard
from .workers import (MangaSearchWorker, MangaChaptersWorker,
                      ImageWorker, MangaResult, MangaChapter,
                      ComickSearchWorker, ComickChaptersWorker, ComickPagesWorker)
from .. import db


class MangaView(QWidget):
    read_chapter = pyqtSignal(object, list, object)  # (MangaResult, chapters, chapter)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_worker   = None
        self._chapters_worker = None
        self._current_manga   = None
        self._chapters        = []
        self._source          = "mangadex"
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Search bar ────────────────────────────────────────────────────────
        bar_widget = QWidget()
        bar_widget.setStyleSheet("background: #16161e; border-bottom: 1px solid #2a2a3a;")
        bar = QHBoxLayout(bar_widget)
        bar.setContentsMargins(16, 10, 16, 10)
        bar.setSpacing(10)

        title = QLabel("Manga")
        title.setObjectName("titleLabel")
        bar.addWidget(title)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search manga…")
        self._search_input.returnPressed.connect(self._do_search)
        bar.addWidget(self._search_input, 1)

        search_btn = QPushButton("Search")
        search_btn.setFixedWidth(90)
        search_btn.clicked.connect(self._do_search)
        bar.addWidget(search_btn)

        self._source_combo = QComboBox()
        self._source_combo.addItem("MangaDex", "mangadex")
        self._source_combo.addItem("Comick", "comick")
        self._source_combo.setFixedWidth(110)
        self._source_combo.currentIndexChanged.connect(self._on_source_changed)
        bar.addWidget(self._source_combo)

        root.addWidget(bar_widget)

        # ── Status ────────────────────────────────────────────────────────────
        self._status = QLabel("Search for a manga title to get started.")  # noqa: E501
        self._status.setObjectName("subtitleLabel")
        self._status.setContentsMargins(20, 6, 20, 2)
        root.addWidget(self._status)

        # ── Splitter: results | detail ────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Left: results grid
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._results_container = QWidget()
        self._results_grid = QGridLayout(self._results_container)
        self._results_grid.setSpacing(10)
        self._results_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._results_grid.setContentsMargins(16, 10, 8, 10)
        left_scroll.setWidget(self._results_container)
        splitter.addWidget(left_scroll)

        # Right: manga detail + chapter list
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(10)

        self._cover_label = QLabel()
        self._cover_label.setFixedSize(160, 226)
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setStyleSheet("background:#1e1e2e; border-radius:8px; color:#555566;")
        self._cover_label.setText("Select a manga")

        self._manga_title = QLabel()
        self._manga_title.setObjectName("sectionLabel")
        self._manga_title.setWordWrap(True)

        self._manga_desc = QLabel()
        self._manga_desc.setWordWrap(True)
        self._manga_desc.setStyleSheet("color:#9090a0; font-size:11px;")
        self._manga_desc.setMaximumHeight(80)

        self._manga_tags = QLabel()
        self._manga_tags.setStyleSheet("color:#c084fc; font-size:10px;")
        self._manga_tags.setWordWrap(True)

        # Info row
        info_row = QHBoxLayout()
        info_row.addWidget(self._cover_label)
        info_col = QVBoxLayout()
        info_col.addWidget(self._manga_title)
        info_col.addWidget(self._manga_tags)
        info_col.addWidget(self._manga_desc)
        info_col.addStretch()
        info_row.addLayout(info_col, 1)
        rl.addLayout(info_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#2a2a3a;")
        rl.addWidget(sep)

        # Chapter controls
        ch_ctrl = QHBoxLayout()
        ch_ctrl.addWidget(QLabel("Chapters"))
        ch_ctrl.addStretch()
        self._lang_combo = QComboBox()
        self._lang_combo.addItem("English", "en")
        self._lang_combo.addItem("Spanish", "es")
        self._lang_combo.addItem("French",  "fr")
        self._lang_combo.addItem("Portuguese", "pt-br")
        self._lang_combo.addItem("German",  "de")
        self._lang_combo.addItem("Italian", "it")
        self._lang_combo.addItem("Russian", "ru")
        self._lang_combo.addItem("Japanese", "ja")
        self._lang_combo.currentIndexChanged.connect(self._reload_chapters)
        ch_ctrl.addWidget(self._lang_combo)
        rl.addLayout(ch_ctrl)

        self._ch_list = QListWidget()
        self._ch_list.itemDoubleClicked.connect(self._on_chapter_activated)
        self._ch_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._ch_list.customContextMenuRequested.connect(self._ch_context_menu)
        rl.addWidget(self._ch_list, 1)

        read_btn = QPushButton("▶  Read Selected Chapter")
        read_btn.clicked.connect(self._read_selected)
        rl.addWidget(read_btn)

        splitter.addWidget(right)
        splitter.setSizes([380, 460])
        root.addWidget(splitter, 1)

    # ── Search ────────────────────────────────────────────────────────────────

    def _on_source_changed(self):
        self._source = self._source_combo.currentData()
        self._search_input.setPlaceholderText(
            f"Search manga on {'MangaDex' if self._source == 'mangadex' else 'Comick'}…"
        )
        self._clear_results()
        self._current_manga = None
        self._ch_list.clear()
        self._status.setText("Search for a manga title to get started.")

    def _do_search(self):
        query = self._search_input.text().strip()
        if not query:
            return
        self._clear_results()
        source_name = "MangaDex" if self._source == "mangadex" else "Comick"
        self._status.setText(f"Searching {source_name}…")
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.terminate()
        if self._source == "comick":
            self._search_worker = ComickSearchWorker(query)
        else:
            self._search_worker = MangaSearchWorker(query)
        self._search_worker.results_ready.connect(self._on_results)
        self._search_worker.error.connect(lambda e: self._status.setText(f"Error: {e}"))
        self._search_worker.start()

    def _on_results(self, results):
        self._clear_results()
        self._status.setText(f"{len(results)} results" if results else "No results found.")
        cols = max(1, 380 // 162)
        for i, manga in enumerate(results):
            card = AnimeCard(manga)
            card.clicked.connect(self._on_manga_selected)
            self._results_grid.addWidget(card, i // cols, i % cols)
            if manga.cover_url:
                card.load_image(manga.cover_url)

    def _clear_results(self):
        while self._results_grid.count():
            item = self._results_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ── Manga detail ──────────────────────────────────────────────────────────

    def _on_manga_selected(self, manga: MangaResult):
        manga.source = self._source
        self._current_manga = manga
        self._manga_title.setText(manga.title)
        self._manga_desc.setText(manga.description or "No description.")
        self._manga_tags.setText("  ·  ".join(manga.tags))
        self._cover_label.setText("Loading…")
        self._cover_label.setPixmap(QPixmap())
        if manga.cover_url:
            w = ImageWorker(manga.cover_url)
            w.image_ready.connect(self._set_cover)
            w.start()
        self._reload_chapters()

    def _set_cover(self, data: bytes):
        pix = QPixmap()
        pix.loadFromData(data)
        if not pix.isNull():
            pix = pix.scaled(160, 226, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                             Qt.TransformationMode.SmoothTransformation)
            self._cover_label.setPixmap(pix.copy(0, 0, 160, 226))

    def _reload_chapters(self):
        if not self._current_manga:
            return
        self._ch_list.clear()
        self._ch_list.addItem(QListWidgetItem("Loading chapters…"))
        lang = self._lang_combo.currentData()
        if self._chapters_worker and self._chapters_worker.isRunning():
            self._chapters_worker.terminate()
        if self._source == "comick":
            self._chapters_worker = ComickChaptersWorker(self._current_manga.manga_id, lang)
        else:
            self._chapters_worker = MangaChaptersWorker(self._current_manga.manga_id, lang)
        self._chapters_worker.results_ready.connect(self._on_chapters)
        self._chapters_worker.error.connect(lambda e: self._ch_list.clear() or
                                            self._ch_list.addItem(f"Error: {e}"))
        self._chapters_worker.start()

    def _on_chapters(self, chapters: list):
        self._chapters = chapters
        self._ch_list.clear()
        read = db.get_read_chapters(self._current_manga.manga_id)
        for ch in chapters:
            is_read = ch.chapter_id in read
            ch_label = f"Ch. {ch.chapter_num}"
            if ch.title:
                ch_label += f" — {ch.title}"
            if ch.scanlator:
                ch_label += f"  [{ch.scanlator}]"
            prefix = "✓ " if is_read else "  "
            item = QListWidgetItem(prefix + ch_label)
            item.setData(Qt.ItemDataRole.UserRole, ch)
            if is_read:
                item.setForeground(item.foreground().__class__("#86efac"))
            self._ch_list.addItem(item)

    # ── Reading ───────────────────────────────────────────────────────────────

    def _read_selected(self):
        item = self._ch_list.currentItem()
        if item:
            self._on_chapter_activated(item)

    def _on_chapter_activated(self, item: QListWidgetItem):
        ch = item.data(Qt.ItemDataRole.UserRole)
        if ch and self._current_manga:
            self.read_chapter.emit(self._current_manga, self._chapters, ch)

    def _ch_context_menu(self, pos):
        item = self._ch_list.itemAt(pos)
        if not item:
            return
        ch = item.data(Qt.ItemDataRole.UserRole)
        if not ch:
            return
        is_read = db.is_chapter_read(self._current_manga.manga_id, ch.chapter_id)

        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        read_action   = menu.addAction("▶  Read")
        menu.addSeparator()
        toggle_action = menu.addAction("✗  Mark Unread" if is_read else "✓  Mark Read")
        mark_up_action = menu.addAction("✓  Mark all up to here as Read")

        action = menu.exec(self._ch_list.mapToGlobal(pos))
        if action == read_action:
            self._on_chapter_activated(item)
        elif action == toggle_action:
            if is_read:
                db.unmark_chapter_read(self._current_manga.manga_id, ch.chapter_id)
            else:
                db.mark_chapter_read(self._current_manga.manga_id, ch.chapter_id,
                                     ch.chapter_num, self._current_manga.title)
            self._on_chapters(self._chapters)
        elif action == mark_up_action:
            row = self._ch_list.row(item)
            for i in range(row + 1):
                c = self._ch_list.item(i).data(Qt.ItemDataRole.UserRole)
                if c:
                    db.mark_chapter_read(self._current_manga.manga_id, c.chapter_id,
                                         c.chapter_num, self._current_manga.title)
            self._on_chapters(self._chapters)

    def focus_search(self):
        self._search_input.setFocus()
        self._search_input.selectAll()
