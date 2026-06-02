from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QGroupBox, QPushButton, QLineEdit,
    QCheckBox, QFormLayout,
)
from PyQt6.QtCore import Qt
import json, os

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".apumachi_settings.json")

DEFAULTS = {
    "default_provider": "allmanga",
    "default_language": "sub",
    "default_quality": "best",
    "default_player": "mpv",
}


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                return {**DEFAULTS, **json.load(f)}
        except Exception:
            pass
    return dict(DEFAULTS)


def save_settings(data: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


class SettingsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        title = QLabel("Settings")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        # ── Playback group ──
        pb_group = QGroupBox("Playback")
        pb_form = QFormLayout(pb_group)
        pb_form.setSpacing(12)

        self.player_combo = QComboBox()
        from anipy_api.player.player import list_players
        try:
            for p in list_players():
                self.player_combo.addItem(p.NAME, p.NAME)
        except Exception:
            self.player_combo.addItem("mpv", "mpv")
        _set_combo(self.player_combo, self.settings.get("default_player", "mpv"))
        pb_form.addRow("Default player:", self.player_combo)

        self.quality_combo = QComboBox()
        for q in ["best", "1080", "720", "480", "360", "worst"]:
            self.quality_combo.addItem(q, q)
        _set_combo(self.quality_combo, self.settings.get("default_quality", "best"))
        pb_form.addRow("Default quality:", self.quality_combo)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("SUB", "sub")
        self.lang_combo.addItem("DUB", "dub")
        _set_combo(self.lang_combo, self.settings.get("default_language", "sub"))
        pb_form.addRow("Default language:", self.lang_combo)

        layout.addWidget(pb_group)

        # ── Provider group ──
        pv_group = QGroupBox("Providers")
        pv_form = QFormLayout(pv_group)
        pv_form.setSpacing(12)

        self.provider_combo = QComboBox()
        from ..providers import list_provider_names
        for name in list_provider_names():
            self.provider_combo.addItem(name.capitalize(), name)
        _set_combo(self.provider_combo, self.settings.get("default_provider", "allmanga"))
        pv_form.addRow("Default provider:", self.provider_combo)

        layout.addWidget(pv_group)

        # ── Save button ──
        save_btn = QPushButton("Save Settings")
        save_btn.setFixedWidth(160)
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subtitleLabel")
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _save(self):
        self.settings["default_player"] = self.player_combo.currentData()
        self.settings["default_quality"] = self.quality_combo.currentData()
        self.settings["default_language"] = self.lang_combo.currentData()
        self.settings["default_provider"] = self.provider_combo.currentData()
        save_settings(self.settings)
        self.status_label.setText("Settings saved.")

    def get_settings(self) -> dict:
        return self.settings


def _set_combo(combo: QComboBox, value: str):
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return
