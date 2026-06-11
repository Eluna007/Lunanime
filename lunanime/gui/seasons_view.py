import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QScrollArea, QGridLayout,
    QFrame, QButtonGroup,
)
from PyQt6.QtCore import Qt, pyqtSignal

from .anime_card import AnimeCard
from .workers import AniListWorker, AniListResult, JikanWorker, JikanResult, SearchWorker
from ..providers import get_provider, list_provider_names


_SEASONS = ["Winter", "Spring", "Summer", "Fall"]
_SEASON_MONTHS = {"Winter": 12, "Spring": 3, "Summer": 6, "Fall": 9}

_ANILIST_SEASON = {"Winter": "WINTER", "Spring": "SPRING", "Summer": "SUMMER", "Fall": "FALL"}
_JIKAN_SEASON   = {"Winter": "winter", "Spring": "spring", "Summer": "summer", "Fall": "fall"}


def _current_season_and_year():
    m = datetime.date.today().month
    y = datetime.date.today().year
    if m in (12, 1, 2):   return "Winter", (y if m == 12 else y)
    elif m in (3, 4, 5):  return "Spring", y
    elif m in (6, 7, 8):  return "Summer", y
    return "Fall", y


def _prev_season(season: str, year: int):
    idx = _SEASONS.index(season)
    if idx == 0:
        return _SEASONS[-1], year - 1
    return _SEASONS[idx - 1], year


def _next_season(season: str, year: int):
    idx = _SEASONS.index(season)
    if idx == len(_SEASONS) - 1:
        return _SEASONS[0], year + 1
    return _SEASONS[idx + 1], year


class SeasonsView(QWidget):
    anime_selected = pyqtSignal(object, object)   # (provider, result)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._search_workers = []
        self._cards = []
        cur_season, cur_year = _current_season_and_year()
        self._season = cur_season
        self._year = cur_year
        self._setup_ui()
        self._fetch()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # ── Top controls ──────────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)

        # Prev / Next season
        prev_btn = QPushButton("◀ Prev")
        prev_btn.setProperty("flat", True)
        prev_btn.setFixedWidth(80)
        prev_btn.clicked.connect(self._go_prev)
        ctrl.addWidget(prev_btn)

        # Season picker
        self._season_combo = QComboBox()
        for s in _SEASONS:
            self._season_combo.addItem(s, s)
        self._season_combo.setCurrentText(self._season)
        self._season_combo.currentIndexChanged.connect(self._on_combo_changed)
        ctrl.addWidget(self._season_combo)

        # Year picker
        self._year_combo = QComboBox()
        cur_year = datetime.date.today().year
        for y in range(cur_year, 1999, -1):
            self._year_combo.addItem(str(y), y)
        self._year_combo.setCurrentText(str(self._year))
        self._year_combo.currentIndexChanged.connect(self._on_combo_changed)
        ctrl.addWidget(self._year_combo)

        next_btn = QPushButton("Next ▶")
        next_btn.setProperty("flat", True)
        next_btn.setFixedWidth(80)
        next_btn.clicked.connect(self._go_next)
        ctrl.addWidget(next_btn)

        ctrl.addSpacing(20)

        # Source toggle: AniList / MAL
        src_label = QLabel("Source:")
        ctrl.addWidget(src_label)

        self._src_anilist = QPushButton("AniList")
        self._src_anilist.setProperty("flat", True)
        self._src_anilist.setCheckable(True)
        self._src_anilist.setChecked(True)
        self._src_anilist.setFixedWidth(70)
        ctrl.addWidget(self._src_anilist)

        self._src_mal = QPushButton("MAL")
        self._src_mal.setProperty("flat", True)
        self._src_mal.setCheckable(True)
        self._src_mal.setFixedWidth(70)
        ctrl.addWidget(self._src_mal)

        self._src_group = QButtonGroup(self)
        self._src_group.setExclusive(True)
        self._src_group.addButton(self._src_anilist)
        self._src_group.addButton(self._src_mal)
        self._src_anilist.clicked.connect(self._fetch)
        self._src_mal.clicked.connect(self._fetch)

        ctrl.addSpacing(20)

        # Provider for playback
        ctrl.addWidget(QLabel("Play via:"))
        self._provider_combo = QComboBox()
        for name in list_provider_names():
            self._provider_combo.addItem(name.capitalize(), name)
        ctrl.addWidget(self._provider_combo)

        ctrl.addStretch()
        layout.addLayout(ctrl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a2a3a;")
        layout.addWidget(sep)

        # ── Title ─────────────────────────────────────────────────────────────
        self._title_label = QLabel()
        self._title_label.setObjectName("titleLabel")
        layout.addWidget(self._title_label)

        self._status_label = QLabel("Loading...")
        self._status_label.setObjectName("subtitleLabel")
        layout.addWidget(self._status_label)

        # ── Grid ──────────────────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(12)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, 1)

        self._update_title()

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _go_prev(self):
        self._season, self._year = _prev_season(self._season, self._year)
        self._sync_combos()
        self._fetch()

    def _go_next(self):
        nxt_s, nxt_y = _next_season(self._season, self._year)
        # Don't go past current season
        cur_s, cur_y = _current_season_and_year()
        if nxt_y > cur_y or (nxt_y == cur_y and _SEASONS.index(nxt_s) > _SEASONS.index(cur_s)):
            return
        self._season, self._year = nxt_s, nxt_y
        self._sync_combos()
        self._fetch()

    def _on_combo_changed(self):
        self._season = self._season_combo.currentData()
        self._year   = self._year_combo.currentData()
        self._fetch()

    def _sync_combos(self):
        self._season_combo.blockSignals(True)
        self._year_combo.blockSignals(True)
        self._season_combo.setCurrentText(self._season)
        self._year_combo.setCurrentText(str(self._year))
        self._season_combo.blockSignals(False)
        self._year_combo.blockSignals(False)

    def _update_title(self):
        source = "AniList" if self._src_anilist.isChecked() else "MAL"
        self._title_label.setText(f"{self._season} {self._year}  —  {source}")

    # ── Data fetching ──────────────────────────────────────────────────────────

    def _fetch(self):
        self._clear_grid()
        self._update_title()
        self._status_label.setText("Loading...")

        if self._worker and self._worker.isRunning():
            self._worker.retire()

        if self._src_anilist.isChecked():
            self._worker = AniListWorker(
                mode="seasonal",
                season=_SeasonShim(self._season),
                year=self._year,
                limit=50,
            )
        else:
            self._worker = JikanWorker(
                mode="season",
                season=_JIKAN_SEASON[self._season],
                year=self._year,
                limit=50,
            )

        self._worker.results_ready.connect(self._on_results)
        self._worker.error.connect(lambda e: self._status_label.setText(f"Error: {e}"))
        self._worker.start()

    def _on_results(self, results):
        self._clear_grid()
        if not results:
            self._status_label.setText("No results found.")
            return
        self._status_label.setText(f"{len(results)} anime")
        for result in results:
            card = AnimeCard(result)
            card.clicked.connect(self._on_card_clicked)
            self._cards.append(card)
            if result.image_url:
                card.load_image(result.image_url)
        self._relayout_grid()

    def _relayout_grid(self):
        cols = max(1, (self._scroll.viewport().width() - 12) // 162)
        for i, card in enumerate(self._cards):
            self._grid.addWidget(card, i // cols, i % cols)

    def _on_card_clicked(self, result):
        provider_name = self._provider_combo.currentData() or "allmanga"
        try:
            provider = get_provider(provider_name)
        except Exception:
            return

        self._status_label.setText(f"Searching '{result.name}' on {provider_name}...")
        w = SearchWorker(provider, result.name)
        w.results_ready.connect(lambda results, p=provider: self._on_search_done(p, results))
        w.error.connect(lambda e: self._status_label.setText(f"Search error: {e}"))
        w.start()
        self._search_workers.append(w)

    def _on_search_done(self, provider, results):
        self._status_label.setText(f"{self._season} {self._year}")
        if results:
            self.anime_selected.emit(provider, results[0])

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _clear_grid(self):
        self._cards = []
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._cards:
            self._relayout_grid()


class _SeasonShim:
    """Shim so AniListWorker can use a plain string season like the anipy enum."""
    def __init__(self, name: str):
        self.name = name.upper()
