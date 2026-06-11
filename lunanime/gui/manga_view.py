"""
Manga search + detail view.
- Left: search results grid (AnimeCard-compatible covers)
- Right: detail panel with chapter list when a manga is selected
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QGridLayout, QListWidget,
    QListWidgetItem, QSplitter, QComboBox, QFrame, QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QBrush, QColor

from .anime_card import AnimeCard
from .workers import (MangaSearchWorker, MangaChaptersWorker,
                      ImageWorker, MangaResult, MangaChapter,
                      WeebCentralSearchWorker, WeebCentralChaptersWorker, WeebCentralMetaWorker,
                      MangaFireSearchWorker, MangaFireChaptersWorker,
                      MangaPillSearchWorker, MangaPillChaptersWorker,
                      MangaDexBrowseWorker)
from .home_view import _HScrollSection
from .. import db

# source key -> (display name, search worker, chapters worker)
MANGA_SOURCES = {
    "mangadex":    ("MangaDex",    MangaSearchWorker,       MangaChaptersWorker),
    "weebcentral": ("WeebCentral", WeebCentralSearchWorker, WeebCentralChaptersWorker),
    "mangafire":   ("MangaFire",   MangaFireSearchWorker,   MangaFireChaptersWorker),
    "mangapill":   ("MangaPill",   MangaPillSearchWorker,   MangaPillChaptersWorker),
}


class MangaView(QWidget):
    read_chapter = pyqtSignal(object, list, object)  # (MangaResult, chapters, chapter)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_worker   = None
        self._chapters_worker = None
        self._meta_worker     = None
        self._current_manga   = None
        self._chapters        = []
        self._result_cards    = []
        self._source          = "mangadex"
        self._browse_workers  = []
        self._discover_loaded = False
        self._setup_ui()
        self._show_discover()

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
        self._search_input.setPlaceholderText("Search manga on MangaDex…")
        self._search_input.returnPressed.connect(self._do_search)
        self._search_input.textChanged.connect(self._on_search_text_changed)
        bar.addWidget(self._search_input, 1)

        search_btn = QPushButton("Search")
        search_btn.setFixedWidth(90)
        search_btn.clicked.connect(self._do_search)
        bar.addWidget(search_btn)

        self._source_combo = QComboBox()
        for key, (name, _, _) in MANGA_SOURCES.items():
            self._source_combo.addItem(name, key)
        self._source_combo.setFixedWidth(120)
        self._source_combo.currentIndexChanged.connect(self._on_source_changed)
        bar.addWidget(self._source_combo)

        root.addWidget(bar_widget)

        # ── Status ────────────────────────────────────────────────────────────
        self._status = QLabel("Search for a manga title to get started.")
        self._status.setObjectName("subtitleLabel")
        self._status.setContentsMargins(20, 6, 20, 2)
        root.addWidget(self._status)

        # ── Splitter: results | detail ────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Left: stack of discover page (0) and results grid (1)
        self._left_stack = QStackedWidget()

        discover_scroll = QScrollArea()
        discover_scroll.setWidgetResizable(True)
        discover_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        discover_inner = QWidget()
        dl = QVBoxLayout(discover_inner)
        dl.setContentsMargins(16, 10, 8, 10)
        dl.setSpacing(18)

        self._continue_section = _HScrollSection("▶  Continue Reading")
        self._continue_section.card_clicked.connect(self._on_discover_card)
        dl.addWidget(self._continue_section)

        self._trending_section = _HScrollSection("🔥  Trending  (MangaDex)")
        self._trending_section.card_clicked.connect(self._on_discover_card)
        dl.addWidget(self._trending_section)

        self._hot_section = _HScrollSection("⭐  Hot New  (MangaDex)")
        self._hot_section.card_clicked.connect(self._on_discover_card)
        dl.addWidget(self._hot_section)

        dl.addStretch()
        discover_scroll.setWidget(discover_inner)
        self._left_stack.addWidget(discover_scroll)   # 0

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._results_container = QWidget()
        self._results_grid = QGridLayout(self._results_container)
        self._results_grid.setSpacing(10)
        self._results_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._results_grid.setContentsMargins(16, 10, 8, 10)
        left_scroll.setWidget(self._results_container)
        self._left_stack.addWidget(left_scroll)       # 1

        splitter.addWidget(self._left_stack)

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

    # ── Discover (trending / hot / continue reading) ─────────────────────────

    def _show_discover(self):
        self._left_stack.setCurrentIndex(0)
        self._status.setText("Browse, or search for a manga title.")
        self.refresh_continue_reading()
        if not self._discover_loaded:
            self._discover_loaded = True
            self._load_browse_section(self._trending_section, "trending")
            self._load_browse_section(self._hot_section, "hot")

    def _load_browse_section(self, section, mode):
        section.set_placeholder("Loading…")
        w = MangaDexBrowseWorker(mode=mode, limit=20)
        w.results_ready.connect(lambda r, sec=section: self._fill_section(sec, r))
        w.error.connect(lambda e, sec=section: sec.set_placeholder(f"Error: {e}"))
        w.start()
        self._browse_workers.append(w)

    def _fill_section(self, section, results):
        section.clear()
        if not results:
            section.set_placeholder("Nothing found.")
            return
        for manga in results:
            manga.source = "mangadex"
            card = section.add_card(manga)
            if manga.cover_url:
                card.load_image(manga.cover_url)

    def refresh_continue_reading(self):
        entries = db.get_continue_reading(limit=20)
        self._continue_section.clear()
        if not entries:
            self._continue_section.set_placeholder("Nothing read yet — chapters you open show up here.")
            return
        for e in entries:
            manga = MangaResult(e["manga_id"], e["title"],
                                "", e.get("cover_url") or "", "", [])
            manga.source = e.get("source") or "mangadex"
            card = self._continue_section.add_card(manga)
            card.setToolTip(f"{e['title']} — Ch. {e['chapter_num']}")
            if manga.cover_url:
                card.load_image(manga.cover_url)

    def _on_discover_card(self, manga):
        source = getattr(manga, "source", "mangadex")
        if source not in MANGA_SOURCES:
            source = "mangadex"
        self._source_combo.blockSignals(True)
        self._source_combo.setCurrentIndex(list(MANGA_SOURCES).index(source))
        self._source_combo.blockSignals(False)
        self._source = source
        self._on_manga_selected(manga)

    # ── Search ────────────────────────────────────────────────────────────────

    def _on_search_text_changed(self, text):
        if not text.strip() and self._left_stack.currentIndex() == 1:
            self._clear_results()
            self._show_discover()

    def _on_source_changed(self):
        self._source = self._source_combo.currentData()
        name = MANGA_SOURCES[self._source][0]
        self._search_input.setPlaceholderText(f"Search manga on {name}…")
        self._clear_results()
        self._current_manga = None
        self._ch_list.clear()
        if not self._search_input.text().strip():
            self._show_discover()

    def _do_search(self):
        query = self._search_input.text().strip()
        if not query:
            return
        self._clear_results()
        self._left_stack.setCurrentIndex(1)
        source_name, search_cls, _ = MANGA_SOURCES[self._source]
        self._status.setText(f"Searching {source_name}…")
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.retire()
        self._search_worker = search_cls(query)
        self._search_worker.results_ready.connect(self._on_results)
        self._search_worker.error.connect(lambda e: self._status.setText(f"Error: {e}"))
        self._search_worker.start()

    def _on_results(self, results):
        self._clear_results()
        self._status.setText(f"{len(results)} results" if results else "No results found.")
        for manga in results:
            card = AnimeCard(manga)
            card.clicked.connect(self._on_manga_selected)
            self._result_cards.append(card)
            if manga.cover_url:
                card.load_image(manga.cover_url)
        self._relayout_results()

    def _relayout_results(self):
        cols = max(1, (self._results_container.width() - 24) // 162)
        for i, card in enumerate(self._result_cards):
            self._results_grid.addWidget(card, i // cols, i % cols)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._result_cards:
            self._relayout_results()

    def _clear_results(self):
        self._result_cards = []
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
        if self._source == "weebcentral":
            mw = WeebCentralMetaWorker(manga.manga_id)
            mw.meta_ready.connect(self._on_wc_meta)
            mw.start()
            self._meta_worker = mw
        elif manga.cover_url:
            w = ImageWorker(manga.cover_url)
            w.image_ready.connect(self._set_cover)
            w.start()
        self._reload_chapters()

    def _on_wc_meta(self, cover_url: str, description: str):
        if description and self._current_manga:
            self._manga_desc.setText(description)
        if cover_url and self._current_manga:
            self._current_manga.cover_url = cover_url
        if cover_url:
            w = ImageWorker(cover_url)
            w.image_ready.connect(self._set_cover)
            w.start()
        else:
            self._cover_label.setText("No cover")

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
            self._chapters_worker.retire()
        chapters_cls = MANGA_SOURCES[self._source][2]
        self._chapters_worker = chapters_cls(self._current_manga.manga_id, lang)
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
                item.setForeground(QBrush(QColor("#86efac")))
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
                                     ch.chapter_num, self._current_manga.title,
                                     source=self._source,
                                     cover_url=self._current_manga.cover_url or None)
            self._on_chapters(self._chapters)
        elif action == mark_up_action:
            row = self._ch_list.row(item)
            for i in range(row + 1):
                c = self._ch_list.item(i).data(Qt.ItemDataRole.UserRole)
                if c:
                    db.mark_chapter_read(self._current_manga.manga_id, c.chapter_id,
                                         c.chapter_num, self._current_manga.title,
                                         source=self._source,
                                         cover_url=self._current_manga.cover_url or None)
            self._on_chapters(self._chapters)

    def focus_search(self):
        self._search_input.setFocus()
        self._search_input.selectAll()
