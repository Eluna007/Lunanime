from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont

from .styles import DARK_STYLE
from .search_view import SearchView
from .anime_view import AnimeView
from .settings_view import SettingsView


NAV_ITEMS = [
    ("search",   "🔍  Search"),
    ("settings", "⚙  Settings"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ApuMachi")
        self.resize(1100, 720)
        self.setMinimumSize(800, 560)
        self.setStyleSheet(DARK_STYLE)
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # ── Sidebar ──
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        logo = QLabel("ApuMachi")
        logo.setStyleSheet("font-size: 17px; font-weight: bold; color: #c084fc; padding: 20px 16px 12px;")
        sb_layout.addWidget(logo)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a2a3a;")
        sb_layout.addWidget(sep)

        self._nav_buttons = {}
        for key, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setCheckable(False)
            btn.clicked.connect(lambda _, k=key: self._nav_to(k))
            sb_layout.addWidget(btn)
            self._nav_buttons[key] = btn

        sb_layout.addStretch()

        provider_hint = QLabel("Providers:\nAllManga · KAA\nAnimeUnity")
        provider_hint.setStyleSheet("font-size: 10px; color: #444455; padding: 10px 16px;")
        sb_layout.addWidget(provider_hint)

        h.addWidget(sidebar)

        # ── Main stack ──
        self.stack = QStackedWidget()
        h.addWidget(self.stack, 1)

        self.search_view = SearchView()
        self.search_view.anime_selected.connect(self._open_anime)
        self.stack.addWidget(self.search_view)   # index 0

        self.anime_view = AnimeView()
        self.anime_view.back_requested.connect(lambda: self._nav_to("search"))
        self.stack.addWidget(self.anime_view)    # index 1

        self.settings_view = SettingsView()
        self.stack.addWidget(self.settings_view) # index 2

        self._nav_to("search")

    def _nav_to(self, key: str):
        mapping = {"search": 0, "anime": 1, "settings": 2}
        idx = mapping.get(key, 0)
        self.stack.setCurrentIndex(idx)
        for k, btn in self._nav_buttons.items():
            btn.setProperty("active", "true" if k == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _open_anime(self, provider, result):
        self.anime_view.load_anime(provider, result)
        self._nav_to("anime")
