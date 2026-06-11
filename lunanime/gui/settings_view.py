from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QGroupBox, QPushButton, QLineEdit,
    QFormLayout, QScrollArea,
)
from PyQt6.QtCore import Qt
import json, os

from .workers import OAuthWorker
from .. import db as _db

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".lunanime_settings.json")
_LEGACY_SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".apumachi_settings.json")

DEFAULTS = {
    "default_provider": "allmanga",
    "default_language": "sub",
    "default_quality": "best",
    "default_player": "mpv",
}


def load_settings() -> dict:
    for path in (SETTINGS_FILE, _LEGACY_SETTINGS_FILE):
        if os.path.exists(path):
            try:
                with open(path) as f:
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
        self._oauth_worker = None
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        title = QLabel("Settings")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        # ── Playback ──────────────────────────────────────────────────────────
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

        # ── Providers ─────────────────────────────────────────────────────────
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

        # ── AniList account ───────────────────────────────────────────────────
        layout.addWidget(self._build_tracker_group(
            "AniList",
            "anilist",
            needs_secret=True,
            instructions=(
                "1. Go to <b>anilist.co/settings/developer</b><br>"
                "2. Create a new client<br>"
                "3. Set <b>Redirect URI</b> to: <code>http://localhost:6789/anilist</code><br>"
                "4. Paste your Client ID and Secret below, then click Connect."
            ),
        ))

        # ── MyAnimeList account ────────────────────────────────────────────────
        layout.addWidget(self._build_tracker_group(
            "MyAnimeList",
            "mal",
            needs_secret=False,
            instructions=(
                "1. Go to <b>myanimelist.net/apiconfig</b><br>"
                "2. Create app — App Type: <b>other</b><br>"
                "3. Set <b>App Redirect URL</b> to: <code>http://localhost:6789/mal</code><br>"
                "4. Paste your Client ID below, then click Connect."
            ),
        ))

        # ── Save ──────────────────────────────────────────────────────────────
        save_btn = QPushButton("Save Settings")
        save_btn.setFixedWidth(160)
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subtitleLabel")
        layout.addWidget(self.status_label)

        layout.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    # ── Tracker group builder ─────────────────────────────────────────────────

    def _build_tracker_group(self, display_name: str, service: str,
                              needs_secret: bool, instructions: str) -> QGroupBox:
        group = QGroupBox(display_name)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        hint = QLabel(instructions)
        hint.setWordWrap(True)
        hint.setOpenExternalLinks(True)
        hint.setStyleSheet("font-size: 11px; color: #9090a0;")
        layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(8)

        client_id_edit = QLineEdit()
        client_id_edit.setPlaceholderText("Client ID")
        saved_id = _db.get_setting(f"{service}_client_id") or ""
        client_id_edit.setText(saved_id)
        form.addRow("Client ID:", client_id_edit)

        secret_edit = None
        if needs_secret:
            secret_edit = QLineEdit()
            secret_edit.setPlaceholderText("Client Secret")
            secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
            saved_secret = _db.get_setting(f"{service}_client_secret") or ""
            secret_edit.setText(saved_secret)
            form.addRow("Client Secret:", secret_edit)

        layout.addLayout(form)

        # Status + buttons row
        status_row = QHBoxLayout()
        status_lbl = QLabel()
        status_lbl.setObjectName("subtitleLabel")
        status_row.addWidget(status_lbl, 1)

        connect_btn = QPushButton("Connect")
        connect_btn.setFixedWidth(90)
        disconnect_btn = QPushButton("Disconnect")
        disconnect_btn.setProperty("danger", True)
        disconnect_btn.setFixedWidth(100)
        status_row.addWidget(connect_btn)
        status_row.addWidget(disconnect_btn)
        layout.addLayout(status_row)

        # Populate current status
        self._refresh_tracker_status(service, status_lbl, connect_btn, disconnect_btn)

        def on_connect():
            cid = client_id_edit.text().strip()
            sec = secret_edit.text().strip() if secret_edit else ""
            if not cid:
                status_lbl.setText("Enter a Client ID first.")
                return
            _db.save_setting(f"{service}_client_id", cid)
            if needs_secret and sec:
                _db.save_setting(f"{service}_client_secret", sec)

            status_lbl.setText("Opening browser… waiting for auth…")
            connect_btn.setEnabled(False)

            worker = OAuthWorker(service, cid, sec)
            worker.success.connect(lambda username: self._on_oauth_success(
                service, username, status_lbl, connect_btn, disconnect_btn))
            worker.error.connect(lambda err: self._on_oauth_error(
                err, status_lbl, connect_btn))
            worker.start()
            self._oauth_worker = worker

        def on_disconnect():
            from lunanime import tracking
            if service == "anilist":
                tracking.anilist_disconnect()
            else:
                tracking.mal_disconnect()
            self._refresh_tracker_status(service, status_lbl, connect_btn, disconnect_btn)

        connect_btn.clicked.connect(on_connect)
        disconnect_btn.clicked.connect(on_disconnect)

        return group

    def _refresh_tracker_status(self, service, status_lbl, connect_btn, disconnect_btn):
        token = _db.get_oauth_token(service)
        if token and token.get("username"):
            status_lbl.setText(f"✓ Connected as {token['username']}")
            status_lbl.setStyleSheet("color: #86efac; font-size: 12px;")
            connect_btn.setEnabled(False)
            disconnect_btn.setEnabled(True)
        else:
            status_lbl.setText("Not connected")
            status_lbl.setStyleSheet("color: #707080; font-size: 12px;")
            connect_btn.setEnabled(True)
            disconnect_btn.setEnabled(False)

    def _on_oauth_success(self, service, username, status_lbl, connect_btn, disconnect_btn):
        self._refresh_tracker_status(service, status_lbl, connect_btn, disconnect_btn)

    def _on_oauth_error(self, err, status_lbl, connect_btn):
        status_lbl.setText(f"Error: {err}")
        status_lbl.setStyleSheet("color: #f87171; font-size: 12px;")
        connect_btn.setEnabled(True)

    # ── Save playback/provider settings ──────────────────────────────────────

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
