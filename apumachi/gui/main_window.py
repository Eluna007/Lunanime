from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QKeySequence, QShortcut

from .styles import DARK_STYLE, LIGHT_STYLE
from .search_view import SearchView
from .anime_view import AnimeView
from .home_view import HomeView
from .downloads_view import DownloadsView
from .settings_view import SettingsView


NAV_ITEMS = [
    ("home",      "🏠  Home"),
    ("search",    "🔍  Search"),
    ("downloads", "⬇  Downloads"),
    ("settings",  "⚙  Settings"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ApuMachi")
        self.resize(1100, 720)
        self.setMinimumSize(800, 560)
        self._dark_mode = True
        self.setStyleSheet(DARK_STYLE)
        self._build_ui()
        self._setup_shortcuts()

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

        # Theme toggle
        self._theme_btn = QPushButton("☀ Light")
        self._theme_btn.setProperty("flat", True)
        self._theme_btn.clicked.connect(self._toggle_theme)
        sb_layout.addWidget(self._theme_btn)

        provider_hint = QLabel("Providers:\nAllManga · KAA\nAnimeUnity")
        provider_hint.setStyleSheet("font-size: 10px; color: #444455; padding: 10px 16px;")
        sb_layout.addWidget(provider_hint)

        h.addWidget(sidebar)

        # ── Main stack ──
        self.stack = QStackedWidget()
        h.addWidget(self.stack, 1)

        self.home_view = HomeView()
        self.home_view.anime_selected.connect(self._open_anime)
        self.stack.addWidget(self.home_view)     # index 0

        self.search_view = SearchView()
        self.search_view.anime_selected.connect(self._open_anime)
        self.stack.addWidget(self.search_view)   # index 1

        self.downloads_view = DownloadsView()
        self.stack.addWidget(self.downloads_view) # index 2

        self.settings_view = SettingsView()
        self.stack.addWidget(self.settings_view) # index 3

        self.anime_view = AnimeView()
        self.anime_view.back_requested.connect(self._on_anime_back)
        self.anime_view.download_started.connect(self._on_download_started)
        self.stack.addWidget(self.anime_view)    # index 4

        self._prev_nav_key = "home"
        self._nav_to("home")
        self.home_view.refresh()

    def _setup_shortcuts(self):
        # Ctrl+F → focus search
        sc_search = QShortcut(QKeySequence("Ctrl+F"), self)
        sc_search.activated.connect(self._focus_search)

        # Escape → back / close anime view
        sc_esc = QShortcut(QKeySequence("Escape"), self)
        sc_esc.activated.connect(self._on_escape)

        # N → next episode (when anime view is active)
        sc_next = QShortcut(QKeySequence("N"), self)
        sc_next.activated.connect(self._next_episode)

    def _focus_search(self):
        self._nav_to("search")
        self.search_view.focus_search()

    def _on_escape(self):
        if self.stack.currentIndex() == 4:
            self._on_anime_back()

    def _next_episode(self):
        if self.stack.currentIndex() == 4:
            self.anime_view._advance_episode()

    def _nav_to(self, key: str):
        mapping = {"home": 0, "search": 1, "downloads": 2, "settings": 3, "anime": 4}
        idx = mapping.get(key, 0)
        self.stack.setCurrentIndex(idx)
        for k, btn in self._nav_buttons.items():
            active = k == key or (key == "anime" and k == self._prev_nav_key)
            btn.setProperty("active", "true" if active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if key != "anime":
            self._prev_nav_key = key

    def _open_anime(self, provider, result):
        self.anime_view.load_anime(provider, result)
        self._nav_to("anime")

    def _on_anime_back(self):
        self._nav_to(self._prev_nav_key)
        if self._prev_nav_key == "home":
            self.home_view.refresh()

    def _on_download_started(self, name, episode, worker):
        self.downloads_view.add_active_download(name, episode, worker)

    def _toggle_theme(self):
        self._dark_mode = not self._dark_mode
        if self._dark_mode:
            self.setStyleSheet(DARK_STYLE)
            self._theme_btn.setText("☀ Light")
        else:
            self.setStyleSheet(LIGHT_STYLE)
            self._theme_btn.setText("🌙 Dark")
