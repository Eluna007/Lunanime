from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QComboBox, QScrollArea, QLabel,
    QGridLayout, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QKeyEvent

from .workers import SearchWorker, InfoWorker
from .anime_card import AnimeCard
from ..providers import get_provider, list_provider_names


class SearchView(QWidget):
    anime_selected = pyqtSignal(object, object)  # (provider, search_result)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_provider = None
        self._worker = None
        self._info_workers = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # ── Header bar ──
        header = QHBoxLayout()
        header.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search anime...")
        self.search_input.returnPressed.connect(self._do_search)
        header.addWidget(self.search_input, 1)

        self.provider_combo = QComboBox()
        for name in list_provider_names():
            self.provider_combo.addItem(name.capitalize(), name)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        header.addWidget(self.provider_combo)

        search_btn = QPushButton("Search")
        search_btn.setFixedWidth(90)
        search_btn.clicked.connect(self._do_search)
        header.addWidget(search_btn)

        layout.addLayout(header)

        # ── Status / hint ──
        self.status_label = QLabel("Pick a provider and search for an anime.")
        self.status_label.setObjectName("subtitleLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # ── Results scroll area ──
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.results_container = QWidget()
        self.results_layout = QGridLayout(self.results_container)
        self.results_layout.setSpacing(12)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll.setWidget(self.results_container)
        layout.addWidget(self.scroll, 1)

        # Init provider
        self._on_provider_changed()

    def _on_provider_changed(self):
        name = self.provider_combo.currentData()
        if name:
            self._current_provider = get_provider(name)
            self._clear_results()

    def _do_search(self):
        query = self.search_input.text().strip()
        if not query or not self._current_provider:
            return

        self._clear_results()
        self.status_label.setText("Searching...")

        if self._worker and self._worker.isRunning():
            self._worker.terminate()

        self._worker = SearchWorker(self._current_provider, query)
        self._worker.results_ready.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_results(self, results):
        self._clear_results()
        if not results:
            self.status_label.setText("No results found.")
            return

        self.status_label.setText(f"{len(results)} results")
        cols = max(1, self.scroll.width() // 162)

        for i, result in enumerate(results):
            card = AnimeCard(result)
            card.clicked.connect(self._card_clicked)
            self.results_layout.addWidget(card, i // cols, i % cols)

            # Fetch cover image via get_info in background
            w = InfoWorker(self._current_provider, result.identifier)
            w.info_ready.connect(lambda info, c=card: self._apply_cover(info, c))
            w.start()
            self._info_workers.append(w)

    def _apply_cover(self, info, card):
        if info.image:
            card.load_image(info.image)

    def _card_clicked(self, result):
        self.anime_selected.emit(self._current_provider, result)

    def _on_error(self, msg):
        self.status_label.setText(f"Error: {msg}")

    def _clear_results(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-flow grid on resize if there are results (simple re-trigger)
