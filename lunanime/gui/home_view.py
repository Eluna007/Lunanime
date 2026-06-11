from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QPushButton, QGridLayout, QFrame, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
import datetime

from .anime_card import AnimeCard
from .workers import InfoWorker, ImageWorker, AniListWorker, SearchWorker
from ..db import get_history, get_favorites
from ..providers import get_provider, list_provider_names


def _current_season():
    from anipy_api.provider.filter import Season
    m = datetime.date.today().month
    if m in (12, 1, 2):   return Season.WINTER
    elif m in (3, 4, 5):  return Season.SPRING
    elif m in (6, 7, 8):  return Season.SUMMER
    return Season.FALL


class _HScrollSection(QWidget):
    """A labeled horizontal scroll row of anime cards."""
    card_clicked = pyqtSignal(object)   # emits result object

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QLabel(title)
        header.setObjectName("sectionLabel")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(248)

        self._container = QWidget()
        self._row = QHBoxLayout(self._container)
        self._row.setContentsMargins(0, 4, 0, 4)
        self._row.setSpacing(10)
        self._row.addStretch()

        scroll.setWidget(self._container)
        layout.addWidget(scroll)

    def clear(self):
        while self._row.count() > 1:
            item = self._row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_card(self, result):
        card = AnimeCard(result)
        card.clicked.connect(self.card_clicked)
        self._row.insertWidget(self._row.count() - 1, card)
        return card

    def set_placeholder(self, text: str):
        self.clear()
        lbl = QLabel(text)
        lbl.setObjectName("subtitleLabel")
        self._row.insertWidget(0, lbl)


class HomeView(QWidget):
    anime_selected = pyqtSignal(object, object)   # (provider, result)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(24)

        # Provider selector for discover sections
        prov_row = QHBoxLayout()
        prov_row.addWidget(QLabel("Play via:"))
        self._provider_combo = QComboBox()
        for name in list_provider_names():
            self._provider_combo.addItem(name.capitalize(), name)
        prov_row.addWidget(self._provider_combo)
        self._status = QLabel("")
        self._status.setObjectName("subtitleLabel")
        prov_row.addSpacing(12)
        prov_row.addWidget(self._status, 1)
        layout.addLayout(prov_row)

        # Continue Watching
        self._continue_section = _HScrollSection("▶  Continue Watching")
        self._continue_section.card_clicked.connect(self._on_history_card)
        layout.addWidget(self._continue_section)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a2a3a;")
        layout.addWidget(sep)

        # Favorites
        self._fav_section = _HScrollSection("♥  Favorites")
        self._fav_section.card_clicked.connect(self._on_history_card)
        layout.addWidget(self._fav_section)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #2a2a3a;")
        layout.addWidget(sep2)

        # Seasonal (AniList)
        season_name = _current_season().name.capitalize()
        year = datetime.date.today().year
        self._seasonal_section = _HScrollSection(f"🌸  {season_name} {year}  (AniList)")
        self._seasonal_section.card_clicked.connect(self._on_discover_card)
        layout.addWidget(self._seasonal_section)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("color: #2a2a3a;")
        layout.addWidget(sep3)

        # Trending (AniList)
        self._trending_section = _HScrollSection("🔥  Trending  (AniList)")
        self._trending_section.card_clicked.connect(self._on_discover_card)
        layout.addWidget(self._trending_section)

        layout.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def refresh(self):
        self._load_continue_watching()
        self._load_favorites()
        self._load_seasonal()
        self._load_trending()

    # ── Continue watching ──────────────────────────────────────────────────────

    def _load_continue_watching(self):
        self._continue_section.clear()
        history = get_history(limit=20)
        if not history:
            self._continue_section.set_placeholder("Nothing watched yet.")
            return

        for entry in history:
            from anipy_api.provider.base import ProviderSearchResult, LanguageTypeEnum
            result = ProviderSearchResult(
                identifier=entry["identifier"],
                name=entry["name"],
                languages={LanguageTypeEnum.SUB},
            )
            result._provider_name = entry["provider"]
            card = self._continue_section.add_card(result)
            if entry.get("image_url"):
                card.load_image(entry["image_url"])

    # ── Favorites ──────────────────────────────────────────────────────────────

    def _load_favorites(self):
        self._fav_section.clear()
        favs = get_favorites()
        if not favs:
            self._fav_section.set_placeholder("No favorites yet.")
            return

        for fav in favs:
            from anipy_api.provider.base import ProviderSearchResult, LanguageTypeEnum
            result = ProviderSearchResult(
                identifier=fav["identifier"],
                name=fav["name"],
                languages={LanguageTypeEnum.SUB},
            )
            result._provider_name = fav["provider"]
            card = self._fav_section.add_card(result)
            if fav.get("image_url"):
                card.load_image(fav["image_url"])

    # ── Seasonal (AniList) ─────────────────────────────────────────────────────

    def _load_seasonal(self):
        self._seasonal_section.set_placeholder("Loading from AniList...")
        season = _current_season()
        year = datetime.date.today().year
        w = AniListWorker(mode="seasonal", season=season, year=year, limit=20)
        w.results_ready.connect(lambda r: self._fill_anilist_section(self._seasonal_section, r))
        w.error.connect(lambda e: self._seasonal_section.set_placeholder(f"AniList error: {e}"))
        w.start()
        self._workers.append(w)

    # ── Trending (AniList) ─────────────────────────────────────────────────────

    def _load_trending(self):
        self._trending_section.set_placeholder("Loading from AniList...")
        w = AniListWorker(mode="trending", limit=24)
        w.results_ready.connect(lambda r: self._fill_anilist_section(self._trending_section, r))
        w.error.connect(lambda e: self._trending_section.set_placeholder(f"AniList error: {e}"))
        w.start()
        self._workers.append(w)

    def _fill_anilist_section(self, section, results):
        section.clear()
        if not results:
            section.set_placeholder("Nothing found.")
            return
        for result in results:
            card = section.add_card(result)
            if result.image_url:
                card.load_image(result.image_url)

    # ── Click handlers ─────────────────────────────────────────────────────────

    def _on_history_card(self, result):
        """History/favorites cards already have a provider identifier."""
        try:
            provider_name = getattr(result, "_provider_name", None) or "allmanga"
            provider = get_provider(provider_name)
            self.anime_selected.emit(provider, result)
        except Exception:
            pass

    def _on_discover_card(self, anilist_result):
        """AniList card clicked — search by title on the chosen provider."""
        provider_name = self._provider_combo.currentData() or "allmanga"
        try:
            provider = get_provider(provider_name)
        except Exception:
            return

        title = anilist_result.name
        self._status.setText(f"Searching '{title}' on {provider_name}…")

        w = SearchWorker(provider, title)
        w.results_ready.connect(lambda results, p=provider, t=title: self._on_search_done(p, results, t))
        w.error.connect(lambda e: self._on_search_error(e))
        w.start()
        self._workers.append(w)

    def _on_search_done(self, provider, results, title):
        if not results:
            self._status.setText(f"'{title}' not found on this provider.")
            return
        self._status.setText("")
        # Open the best match (first result)
        self.anime_selected.emit(provider, results[0])

    def _on_search_error(self, err):
        self._status.setText(f"Search error: {err}")
