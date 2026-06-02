from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QPushButton, QGridLayout, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
import datetime

from .anime_card import AnimeCard
from .workers import TrendingWorker, InfoWorker, ImageWorker
from ..db import get_history, get_favorites
from ..providers import get_provider


def _current_season():
    from anipy_api.provider.filter import Season
    m = datetime.date.today().month
    if m in (12, 1, 2):   return Season.WINTER
    elif m in (3, 4, 5):  return Season.SPRING
    elif m in (6, 7, 8):  return Season.SUMMER
    return Season.FALL


class _HScrollSection(QWidget):
    """A labeled horizontal scroll row of anime cards."""
    card_clicked = pyqtSignal(object, object)   # (provider_name, result-like dict)

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
        while self._row.count() > 1:   # keep the trailing stretch
            item = self._row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_card(self, provider_name, result):
        card = AnimeCard(result)
        card.clicked.connect(lambda r, pn=provider_name: self.card_clicked.emit(pn, r))
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

        # Seasonal
        season_name = _current_season().name.capitalize()
        year = datetime.date.today().year
        self._seasonal_section = _HScrollSection(f"🌸  {season_name} {year}")
        self._seasonal_section.card_clicked.connect(self._on_trending_card)
        layout.addWidget(self._seasonal_section)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("color: #2a2a3a;")
        layout.addWidget(sep3)

        # Trending
        self._trending_section = _HScrollSection("🔥  Trending")
        self._trending_section.card_clicked.connect(self._on_trending_card)
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
            card = self._continue_section.add_card(entry["provider"], result)
            card._history_entry = entry
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
            card = self._fav_section.add_card(fav["provider"], result)
            card._history_entry = fav
            if fav.get("image_url"):
                card.load_image(fav["image_url"])

    # ── Seasonal ───────────────────────────────────────────────────────────────

    def _load_seasonal(self):
        self._seasonal_section.set_placeholder("Loading...")
        try:
            provider = get_provider("allmanga")
        except Exception:
            self._seasonal_section.set_placeholder("Provider unavailable.")
            return

        from anipy_api.provider.filter import Filters
        season = _current_season()
        year = datetime.date.today().year
        w = TrendingWorker(provider, season=season, year=year, limit=20)
        w.results_ready.connect(
            lambda r: self._fill_section(self._seasonal_section, provider, r)
        )
        w.error.connect(lambda e: self._seasonal_section.set_placeholder(f"Error: {e}"))
        w.start()
        self._workers.append(w)

    # ── Trending ───────────────────────────────────────────────────────────────

    def _load_trending(self):
        self._trending_section.set_placeholder("Loading...")
        try:
            provider = get_provider("allmanga")
        except Exception:
            self._trending_section.set_placeholder("Provider unavailable.")
            return

        w = TrendingWorker(provider, limit=24)
        w.results_ready.connect(
            lambda r: self._fill_section(self._trending_section, provider, r)
        )
        w.error.connect(lambda e: self._trending_section.set_placeholder(f"Error: {e}"))
        w.start()
        self._workers.append(w)

    def _fill_section(self, section, provider, results):
        section.clear()
        if not results:
            section.set_placeholder("Nothing found.")
            return
        for result in results:
            card = section.add_card(provider.NAME, result)
            card._provider = provider
            card._result = result
            # Lazy-load cover via get_info
            w = InfoWorker(provider, result.identifier)
            w.info_ready.connect(lambda info, c=card: c.load_image(info.image) if info.image else None)
            w.start()
            self._workers.append(w)

    # ── Click handlers ─────────────────────────────────────────────────────────

    def _on_history_card(self, provider_name, result):
        try:
            provider = get_provider(provider_name)
            self.anime_selected.emit(provider, result)
        except Exception:
            pass

    def _on_trending_card(self, provider_name, result):
        try:
            provider = get_provider(provider_name)
            self.anime_selected.emit(provider, result)
        except Exception:
            pass
