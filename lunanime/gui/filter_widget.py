from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QCheckBox, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from anipy_api.provider.filter import Filters, Season, Status, MediaType, FilterCapabilities
import datetime


def _current_season() -> Season:
    month = datetime.date.today().month
    if month in (12, 1, 2):
        return Season.WINTER
    elif month in (3, 4, 5):
        return Season.SPRING
    elif month in (6, 7, 8):
        return Season.SUMMER
    return Season.FALL


class FilterWidget(QWidget):
    filters_changed = pyqtSignal(object)   # emits Filters

    def __init__(self, parent=None):
        super().__init__(parent)
        self._caps = FilterCapabilities(0)
        self._setup_ui()
        self.setVisible(False)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 4)
        layout.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(10)

        # Year
        self._year_label = QLabel("Year:")
        self._year_combo = QComboBox()
        cur = datetime.date.today().year
        self._year_combo.addItem("Any", None)
        for y in range(cur, 1990, -1):
            self._year_combo.addItem(str(y), y)
        row.addWidget(self._year_label)
        row.addWidget(self._year_combo)

        # Season
        self._season_label = QLabel("Season:")
        self._season_combo = QComboBox()
        self._season_combo.addItem("Any", None)
        for s in Season:
            self._season_combo.addItem(s.name.capitalize(), s)
        row.addWidget(self._season_label)
        row.addWidget(self._season_combo)

        # Status
        self._status_label = QLabel("Status:")
        self._status_combo = QComboBox()
        self._status_combo.addItem("Any", None)
        self._status_combo.addItem("Ongoing", Status.ONGOING)
        self._status_combo.addItem("Completed", Status.COMPLETED)
        self._status_combo.addItem("Upcoming", Status.UPCOMING)
        row.addWidget(self._status_label)
        row.addWidget(self._status_combo)

        # Type
        self._type_label = QLabel("Type:")
        self._type_combo = QComboBox()
        self._type_combo.addItem("Any", None)
        self._type_combo.addItem("TV", MediaType.TV)
        self._type_combo.addItem("Movie", MediaType.MOVIE)
        self._type_combo.addItem("OVA", MediaType.OVA)
        self._type_combo.addItem("ONA", MediaType.ONA)
        self._type_combo.addItem("Special", MediaType.SPECIAL)
        row.addWidget(self._type_label)
        row.addWidget(self._type_combo)

        # Current season shortcut
        self._cur_season_btn = QPushButton("This Season")
        self._cur_season_btn.setProperty("flat", True)
        self._cur_season_btn.setFixedWidth(100)
        self._cur_season_btn.clicked.connect(self._set_current_season)
        row.addWidget(self._cur_season_btn)

        row.addStretch()

        reset_btn = QPushButton("Reset")
        reset_btn.setProperty("flat", True)
        reset_btn.setFixedWidth(70)
        reset_btn.clicked.connect(self.reset)
        row.addWidget(reset_btn)

        layout.addLayout(row)

    def set_capabilities(self, caps: FilterCapabilities):
        self._caps = caps
        has_year = bool(caps & FilterCapabilities.YEAR)
        has_season = bool(caps & FilterCapabilities.SEASON)
        has_status = bool(caps & FilterCapabilities.STATUS)
        has_type = bool(caps & FilterCapabilities.MEDIA_TYPE)

        self._year_label.setVisible(has_year)
        self._year_combo.setVisible(has_year)
        self._season_label.setVisible(has_season)
        self._season_combo.setVisible(has_season)
        self._status_label.setVisible(has_status)
        self._status_combo.setVisible(has_status)
        self._type_label.setVisible(has_type)
        self._type_combo.setVisible(has_type)
        self._cur_season_btn.setVisible(has_season or has_year)

    def get_filters(self) -> Filters:
        return Filters(
            year=self._year_combo.currentData(),
            season=self._season_combo.currentData(),
            status=self._status_combo.currentData(),
            media_type=self._type_combo.currentData(),
        )

    def _set_current_season(self):
        season = _current_season()
        year = datetime.date.today().year
        for i in range(self._season_combo.count()):
            if self._season_combo.itemData(i) == season:
                self._season_combo.setCurrentIndex(i)
        for i in range(self._year_combo.count()):
            if self._year_combo.itemData(i) == year:
                self._year_combo.setCurrentIndex(i)

    def reset(self):
        self._year_combo.setCurrentIndex(0)
        self._season_combo.setCurrentIndex(0)
        self._status_combo.setCurrentIndex(0)
        self._type_combo.setCurrentIndex(0)
