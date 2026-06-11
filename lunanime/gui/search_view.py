from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QComboBox, QScrollArea, QLabel,
    QGridLayout, QListWidget, QListWidgetItem, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent

from .workers import SearchWorker, InfoWorker
from .anime_card import AnimeCard
from .filter_widget import FilterWidget
from ..providers import get_provider, list_provider_names


class SearchView(QWidget):
    anime_selected = pyqtSignal(object, object)  # (provider, search_result)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_provider = None
        self._worker = None
        self._info_workers = []
        self._grid_mode = True
        self._results = []
        self._cards = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

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

        # Filter toggle
        self._filter_btn = QPushButton("Filters ▾")
        self._filter_btn.setProperty("flat", True)
        self._filter_btn.setFixedWidth(90)
        self._filter_btn.clicked.connect(self._toggle_filters)
        header.addWidget(self._filter_btn)

        # Grid/List toggle
        self._view_btn = QPushButton("☰")
        self._view_btn.setProperty("flat", True)
        self._view_btn.setFixedWidth(40)
        self._view_btn.setToolTip("Toggle grid/list view")
        self._view_btn.clicked.connect(self._toggle_view)
        header.addWidget(self._view_btn)

        layout.addLayout(header)

        # ── Filter widget ──
        self._filter_widget = FilterWidget()
        layout.addWidget(self._filter_widget)

        # ── Status label ──
        self.status_label = QLabel("Pick a provider and search for an anime.")
        self.status_label.setObjectName("subtitleLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # ── Grid scroll area ──
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.results_container = QWidget()
        self.results_layout = QGridLayout(self.results_container)
        self.results_layout.setSpacing(12)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.results_container)

        # ── List widget ──
        self._list_widget = QListWidget()
        self._list_widget.itemDoubleClicked.connect(self._list_item_clicked)
        self._list_widget.setVisible(False)

        layout.addWidget(self.scroll, 1)
        layout.addWidget(self._list_widget, 1)

        self._on_provider_changed()

    def _toggle_filters(self):
        visible = not self._filter_widget.isVisible()
        self._filter_widget.setVisible(visible)
        self._filter_btn.setText("Filters ▴" if visible else "Filters ▾")

    def _toggle_view(self):
        self._grid_mode = not self._grid_mode
        self._view_btn.setText("⊞" if self._grid_mode else "☰")
        self.scroll.setVisible(self._grid_mode)
        self._list_widget.setVisible(not self._grid_mode)
        if self._results:
            self._render_results(self._results)

    def _on_provider_changed(self):
        name = self.provider_combo.currentData()
        if name:
            self._current_provider = get_provider(name)
            caps = getattr(self._current_provider, 'FILTER_CAPS', None)
            if caps is not None:
                self._filter_widget.set_capabilities(caps)
            self._clear_results()

    def _do_search(self):
        query = self.search_input.text().strip()
        if not self._current_provider:
            return

        self._clear_results()
        self.status_label.setText("Searching...")

        if self._worker and self._worker.isRunning():
            self._worker.retire()

        filters = self._filter_widget.get_filters() if self._filter_widget.isVisible() else None
        self._worker = SearchWorker(self._current_provider, query, filters=filters)
        self._worker.results_ready.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_results(self, results):
        self._results = results
        self._clear_results()
        if not results:
            self.status_label.setText("No results found.")
            return
        self.status_label.setText(f"{len(results)} results")
        self._render_results(results)

    def _render_results(self, results):
        self._clear_results()
        if self._grid_mode:
            for result in results:
                card = AnimeCard(result)
                card.clicked.connect(self._card_clicked)
                self._cards.append(card)
                w = InfoWorker(self._current_provider, result.identifier)
                w.info_ready.connect(lambda info, c=card: c.load_image(info.image) if info.image else None)
                w.start()
                self._info_workers.append(w)
            self._relayout_grid()
        else:
            for result in results:
                item = QListWidgetItem(result.name)
                item.setData(Qt.ItemDataRole.UserRole, result)
                self._list_widget.addItem(item)

    def _relayout_grid(self):
        cols = max(1, (self.scroll.viewport().width() - 12) // 162)
        for i, card in enumerate(self._cards):
            self.results_layout.addWidget(card, i // cols, i % cols)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._cards and self._grid_mode:
            self._relayout_grid()

    def _list_item_clicked(self, item):
        result = item.data(Qt.ItemDataRole.UserRole)
        if result:
            self.anime_selected.emit(self._current_provider, result)

    def _card_clicked(self, result):
        self.anime_selected.emit(self._current_provider, result)

    def _on_error(self, msg):
        self.status_label.setText(f"Error: {msg}")

    def _clear_results(self):
        self._cards = []
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._list_widget.clear()

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()
