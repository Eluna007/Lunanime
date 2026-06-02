from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QComboBox, QScrollArea, QFrame, QSizePolicy,
    QTextEdit, QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QFont

from anipy_api.provider.base import LanguageTypeEnum
from anipy_api.player.player import get_player, list_players

from .workers import EpisodesWorker, StreamWorker, ImageWorker


QUALITY_OPTIONS = ["best", "1080", "720", "480", "360", "worst"]


class AnimeView(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._provider = None
        self._result = None
        self._episodes = []
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ──
        topbar = QWidget()
        topbar.setStyleSheet("background-color: #16161e; border-bottom: 1px solid #2a2a3a;")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(16, 10, 16, 10)

        back_btn = QPushButton("← Back")
        back_btn.setProperty("flat", True)
        back_btn.setStyleSheet("QPushButton { background: transparent; color: #c084fc; border: none; font-size: 13px; }"
                               "QPushButton:hover { color: #d8a4ff; }")
        back_btn.setFixedWidth(80)
        back_btn.clicked.connect(self.back_requested)
        topbar_layout.addWidget(back_btn)
        topbar_layout.addStretch()

        root.addWidget(topbar)

        # ── Content splitter: info left | episodes right ──
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Left panel: cover + info
        left = QScrollArea()
        left.setWidgetResizable(True)
        left.setFixedWidth(300)
        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(268, 380)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("background-color: #1e1e2e; border-radius: 8px; color: #555566;")
        self.cover_label.setText("Loading...")
        left_layout.addWidget(self.cover_label)

        self.title_label = QLabel()
        self.title_label.setObjectName("titleLabel")
        self.title_label.setWordWrap(True)
        left_layout.addWidget(self.title_label)

        self.meta_label = QLabel()
        self.meta_label.setObjectName("subtitleLabel")
        self.meta_label.setWordWrap(True)
        left_layout.addWidget(self.meta_label)

        self.genres_label = QLabel()
        self.genres_label.setStyleSheet("color: #9090a0; font-size: 11px;")
        self.genres_label.setWordWrap(True)
        left_layout.addWidget(self.genres_label)

        self.synopsis_label = QLabel()
        self.synopsis_label.setWordWrap(True)
        self.synopsis_label.setStyleSheet("color: #b0b0c0; font-size: 12px; line-height: 1.4;")
        left_layout.addWidget(self.synopsis_label)

        left_layout.addStretch()
        left.setWidget(left_content)
        splitter.addWidget(left)

        # Right panel: controls + episode list
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        ep_header = QLabel("Episodes")
        ep_header.setObjectName("sectionLabel")
        right_layout.addWidget(ep_header)

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("SUB", LanguageTypeEnum.SUB)
        self.lang_combo.addItem("DUB", LanguageTypeEnum.DUB)
        self.lang_combo.currentIndexChanged.connect(self._reload_episodes)
        controls.addWidget(QLabel("Language:"))
        controls.addWidget(self.lang_combo)

        controls.addSpacing(16)
        controls.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        for q in QUALITY_OPTIONS:
            self.quality_combo.addItem(q, q)
        controls.addWidget(self.quality_combo)

        controls.addSpacing(16)
        controls.addWidget(QLabel("Player:"))
        self.player_combo = QComboBox()
        try:
            for p in list_players():
                self.player_combo.addItem(p.NAME, p.NAME)
        except Exception:
            self.player_combo.addItem("mpv", "mpv")
        controls.addWidget(self.player_combo)

        controls.addStretch()
        right_layout.addLayout(controls)

        # Status
        self.ep_status = QLabel("Select an episode to watch.")
        self.ep_status.setObjectName("subtitleLabel")
        right_layout.addWidget(self.ep_status)

        # Episode list
        self.ep_list = QListWidget()
        self.ep_list.setAlternatingRowColors(False)
        self.ep_list.itemDoubleClicked.connect(self._play_episode)
        right_layout.addWidget(self.ep_list, 1)

        # Play button
        play_btn = QPushButton("▶  Watch Selected Episode")
        play_btn.clicked.connect(self._play_selected)
        right_layout.addWidget(play_btn)

        splitter.addWidget(right)
        splitter.setSizes([300, 600])
        root.addWidget(splitter, 1)

    def load_anime(self, provider, result):
        self._provider = provider
        self._result = result
        self._episodes = []
        self.ep_list.clear()
        self.ep_status.setText("Loading episodes...")
        self.cover_label.setText("Loading...")
        self.title_label.setText(result.name)
        self.meta_label.setText(f"Provider: {provider.NAME}")
        self.synopsis_label.setText("")
        self.genres_label.setText("")

        # Load info
        self._info_worker = InfoWorker_local(provider, result.identifier)
        self._info_worker.info_ready.connect(self._apply_info)
        self._info_worker.start()

        self._reload_episodes()

    def _apply_info(self, info):
        if info.name:
            self.title_label.setText(info.name)
        parts = []
        if info.release_year:
            parts.append(str(info.release_year))
        if info.status:
            parts.append(info.status.name.capitalize())
        self.meta_label.setText("  ·  ".join(parts))
        if info.genres:
            self.genres_label.setText("  ·  ".join(info.genres[:6]))
        if info.synopsis:
            self.synopsis_label.setText(info.synopsis[:500] + ("…" if len(info.synopsis) > 500 else ""))
        if info.image:
            self._img_worker = ImageWorker(info.image)
            self._img_worker.image_ready.connect(self._set_cover)
            self._img_worker.start()

    def _set_cover(self, data: bytes):
        pix = QPixmap()
        pix.loadFromData(data)
        if not pix.isNull():
            pix = pix.scaled(268, 380, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                             Qt.TransformationMode.SmoothTransformation)
            self.cover_label.setPixmap(pix.copy(0, 0, 268, 380))

    def _reload_episodes(self):
        if not self._provider or not self._result:
            return
        lang = self.lang_combo.currentData()
        self.ep_list.clear()
        self.ep_status.setText("Loading episodes...")

        self._ep_worker = EpisodesWorker(self._provider, self._result.identifier, lang)
        self._ep_worker.episodes_ready.connect(self._on_episodes)
        self._ep_worker.error.connect(lambda e: self.ep_status.setText(f"Error: {e}"))
        self._ep_worker.start()

    def _on_episodes(self, episodes):
        self._episodes = episodes
        self.ep_list.clear()
        if not episodes:
            self.ep_status.setText("No episodes found for this language.")
            return
        self.ep_status.setText(f"{len(episodes)} episode{'s' if len(episodes) != 1 else ''}")
        for ep in episodes:
            label = f"Episode {ep}" if ep == int(ep) else f"Episode {ep}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ep)
            self.ep_list.addItem(item)

    def _play_selected(self):
        item = self.ep_list.currentItem()
        if item:
            self._play_episode(item)

    def _play_episode(self, item: QListWidgetItem):
        ep = item.data(Qt.ItemDataRole.UserRole)
        lang = self.lang_combo.currentData()
        quality = self.quality_combo.currentData()
        self.ep_status.setText(f"Fetching stream for Episode {ep}...")

        self._stream_worker = StreamWorker(
            self._provider, self._result.identifier, ep, lang, quality
        )
        self._stream_worker.stream_ready.connect(self._launch_player)
        self._stream_worker.error.connect(lambda e: self.ep_status.setText(f"Stream error: {e}"))
        self._stream_worker.start()

    def _launch_player(self, stream):
        if not stream:
            self.ep_status.setText("No stream found. Try a different quality or provider.")
            return

        player_name = self.player_combo.currentData() or "mpv"
        try:
            player = get_player(player_name)
            from anipy_api.anime import Anime
            anime = Anime(
                self._provider,
                self._result.name,
                self._result.identifier,
                self._result.languages,
            )
            player.play_title(anime, stream)
            self.ep_status.setText(f"Playing Episode {stream.episode} @ {stream.resolution}p")
        except Exception as e:
            self.ep_status.setText(f"Player error: {e}")


# local import alias to avoid circular
from .workers import InfoWorker as InfoWorker_local
