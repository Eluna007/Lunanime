from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QComboBox, QScrollArea, QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QBrush, QColor

from anipy_api.provider.base import LanguageTypeEnum
from anipy_api.player.player import get_player, list_players

from .workers import (EpisodesWorker, StreamWorker, ImageWorker,
                       AutoPlayWorker, DownloadWorker, TrackingWorker)
from .workers import InfoWorker as InfoWorker_local
from .. import db

QUALITY_OPTIONS = ["best", "1080", "720", "480", "360", "worst"]
DEFAULT_DOWNLOAD_DIR = Path.home() / "Lunanime Downloads"


class AnimeView(QWidget):
    back_requested = pyqtSignal()
    download_started = pyqtSignal(object, object, object)   # name, episode, worker

    def __init__(self, parent=None):
        super().__init__(parent)
        self._provider = None
        self._result = None
        self._episodes = []
        self._current_stream = None
        self._current_player = None
        self._autoplay_worker = None
        self._cover_image_url = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────────────────
        topbar = QWidget()
        topbar.setStyleSheet("background-color: #16161e; border-bottom: 1px solid #2a2a3a;")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(16, 10, 16, 10)

        back_btn = QPushButton("← Back")
        back_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #c084fc; border: none; font-size: 13px; }"
            "QPushButton:hover { color: #d8a4ff; }"
        )
        back_btn.setFixedWidth(80)
        back_btn.clicked.connect(self.back_requested)
        tb.addWidget(back_btn)
        tb.addStretch()

        self.fav_btn = QPushButton("♥ Favorite")
        self.fav_btn.setProperty("flat", True)
        self.fav_btn.setFixedWidth(100)
        self.fav_btn.clicked.connect(self._toggle_favorite)
        tb.addWidget(self.fav_btn)

        root.addWidget(topbar)

        # ── Splitter: info | episodes ──────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Left: cover + info
        left = QScrollArea()
        left.setWidgetResizable(True)
        left.setFixedWidth(300)
        lc = QWidget()
        ll = QVBoxLayout(lc)
        ll.setContentsMargins(16, 16, 16, 16)
        ll.setSpacing(12)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(268, 380)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("background-color: #1e1e2e; border-radius: 8px; color: #555566;")
        self.cover_label.setText("Loading...")
        ll.addWidget(self.cover_label)

        self.title_label = QLabel()
        self.title_label.setObjectName("titleLabel")
        self.title_label.setWordWrap(True)
        ll.addWidget(self.title_label)

        self.meta_label = QLabel()
        self.meta_label.setObjectName("subtitleLabel")
        self.meta_label.setWordWrap(True)
        ll.addWidget(self.meta_label)

        self.genres_label = QLabel()
        self.genres_label.setStyleSheet("color: #9090a0; font-size: 11px;")
        self.genres_label.setWordWrap(True)
        ll.addWidget(self.genres_label)

        self.synopsis_label = QLabel()
        self.synopsis_label.setWordWrap(True)
        self.synopsis_label.setStyleSheet("color: #b0b0c0; font-size: 12px;")
        ll.addWidget(self.synopsis_label)

        ll.addStretch()
        left.setWidget(lc)
        splitter.addWidget(left)

        # Right: controls + episode list
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 16, 16, 16)
        rl.setSpacing(10)

        ep_header = QLabel("Episodes")
        ep_header.setObjectName("sectionLabel")
        rl.addWidget(ep_header)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)

        ctrl.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("SUB", LanguageTypeEnum.SUB)
        self.lang_combo.addItem("DUB", LanguageTypeEnum.DUB)
        self.lang_combo.currentIndexChanged.connect(self._reload_episodes)
        ctrl.addWidget(self.lang_combo)

        ctrl.addSpacing(8)
        ctrl.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        for q in QUALITY_OPTIONS:
            self.quality_combo.addItem(q, q)
        ctrl.addWidget(self.quality_combo)

        ctrl.addSpacing(8)
        ctrl.addWidget(QLabel("Player:"))
        self.player_combo = QComboBox()
        try:
            for p in list_players():
                self.player_combo.addItem(p.NAME, p.NAME)
        except Exception:
            self.player_combo.addItem("mpv", "mpv")
        ctrl.addWidget(self.player_combo)

        ctrl.addStretch()
        rl.addLayout(ctrl)

        # Auto-play row
        ap_row = QHBoxLayout()
        from PyQt6.QtWidgets import QCheckBox
        self.autoplay_check = QCheckBox("Auto-play next episode")
        ap_row.addWidget(self.autoplay_check)
        ap_row.addStretch()
        rl.addLayout(ap_row)

        # Status
        self.ep_status = QLabel("Select an episode to watch.")
        self.ep_status.setObjectName("subtitleLabel")
        rl.addWidget(self.ep_status)

        # Resume hint
        self.resume_label = QLabel("")
        self.resume_label.setStyleSheet("color: #c084fc; font-size: 12px;")
        rl.addWidget(self.resume_label)

        # Episode list
        self.ep_list = QListWidget()
        self.ep_list.itemDoubleClicked.connect(self._play_episode)
        self.ep_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ep_list.customContextMenuRequested.connect(self._ep_context_menu)
        rl.addWidget(self.ep_list, 1)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        play_btn = QPushButton("▶  Watch Selected")
        play_btn.clicked.connect(self._play_selected)
        btn_row.addWidget(play_btn, 1)

        dl_btn = QPushButton("⬇  Download")
        dl_btn.setProperty("flat", True)
        dl_btn.setFixedWidth(120)
        dl_btn.clicked.connect(self._download_selected)
        btn_row.addWidget(dl_btn)

        rl.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setSizes([300, 600])
        root.addWidget(splitter, 1)

    # ── Load anime ─────────────────────────────────────────────────────────────

    def load_anime(self, provider, result):
        self._provider = provider
        self._result = result
        self._episodes = []
        self._current_stream = None
        self._cover_image_url = None
        self.ep_list.clear()
        self.resume_label.setText("")
        self.ep_status.setText("Loading...")
        self.cover_label.setText("Loading...")
        self.cover_label.setPixmap(QPixmap())
        self.title_label.setText(result.name)
        self.meta_label.setText(f"Provider: {provider.NAME}")
        self.synopsis_label.setText("")
        self.genres_label.setText("")

        # Update favorite button
        self._refresh_fav_btn()

        # Restore saved preferences
        prefs = db.get_anime_prefs(provider.NAME, result.identifier)
        if prefs:
            for i in range(self.lang_combo.count()):
                if self.lang_combo.itemData(i).value == prefs.get("lang"):
                    self.lang_combo.setCurrentIndex(i)
                    break
            for i in range(self.quality_combo.count()):
                if self.quality_combo.itemData(i) == prefs.get("quality"):
                    self.quality_combo.setCurrentIndex(i)
                    break

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
            self.synopsis_label.setText(
                info.synopsis[:500] + ("…" if len(info.synopsis) > 500 else "")
            )
        if info.image:
            self._cover_image_url = info.image
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

    # ── Episodes ───────────────────────────────────────────────────────────────

    def _reload_episodes(self):
        if not self._provider or not self._result:
            return
        lang = self.lang_combo.currentData()
        self.ep_list.clear()
        self.resume_label.setText("")
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

        lang = self.lang_combo.currentData()
        last_ep = db.get_last_episode(
            self._provider.NAME, self._result.identifier, lang.value
        )
        watched = db.get_watched_episodes(self._provider.NAME, self._result.identifier)

        self.ep_status.setText(f"{len(episodes)} episode{'s' if len(episodes) != 1 else ''}")

        for ep in episodes:
            ep_label = f"Episode {int(ep) if ep == int(ep) else ep}"
            is_watched = ep in watched
            label = ("✓ " if is_watched else "  ") + ep_label
            if last_ep is not None and ep == last_ep:
                label += "  (last played)"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ep)
            if is_watched:
                item.setForeground(QBrush(QColor("#86efac")))
            self.ep_list.addItem(item)

        # Show resume hint and select last episode
        if last_ep is not None:
            self.resume_label.setText(f"Last watched: Episode {int(last_ep) if last_ep == int(last_ep) else last_ep}")
            # Try to select next episode
            next_ep_idx = None
            for i, ep in enumerate(episodes):
                if ep > last_ep:
                    next_ep_idx = i
                    break
            if next_ep_idx is not None:
                self.ep_list.setCurrentRow(next_ep_idx)
            else:
                # Select the last watched
                for i, ep in enumerate(episodes):
                    if ep == last_ep:
                        self.ep_list.setCurrentRow(i)
                        break

    # ── Playback ───────────────────────────────────────────────────────────────

    def _play_selected(self):
        item = self.ep_list.currentItem()
        if item:
            self._play_episode(item)

    def _play_episode(self, item: QListWidgetItem):
        ep = item.data(Qt.ItemDataRole.UserRole)
        lang = self.lang_combo.currentData()
        quality = self.quality_combo.currentData()
        self.ep_status.setText(f"Fetching stream for Episode {ep}...")

        # Save prefs
        db.save_anime_prefs(
            self._provider.NAME, self._result.identifier,
            lang.value, quality
        )

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

        self._current_stream = stream
        player_name = self.player_combo.currentData() or "mpv"
        try:
            player = get_player(Path(player_name))
            from anipy_api.anime import Anime
            anime = Anime(
                self._provider,
                self._result.name,
                self._result.identifier,
                self._result.languages,
            )
            player.play_title(anime, stream)
            self._current_player = player
            self.ep_status.setText(
                f"Playing Episode {stream.episode} @ {stream.resolution}p"
            )

            # Save to history
            db.save_history(
                self._provider.NAME,
                self._result.identifier,
                self._result.name,
                stream.episode,
                stream.language.value,
                self.quality_combo.currentData(),
                self._cover_image_url,
            )
            db.mark_watched(self._provider.NAME, self._result.identifier, stream.episode)
            self._refresh_episode_watched_state(stream.episode)

            # Sync to AniList / MAL (background, silent)
            self._tracking_worker = TrackingWorker(
                self._result.name, int(stream.episode),
                self._provider.NAME, self._result.identifier,
            )
            self._tracking_worker.start()

            # Auto-play watcher
            if self.autoplay_check.isChecked():
                self._autoplay_worker = AutoPlayWorker(player)
                self._autoplay_worker.done.connect(self._on_player_finished)
                self._autoplay_worker.start()

        except Exception as e:
            self.ep_status.setText(f"Player error: {e}")

    def _on_player_finished(self):
        if not self.autoplay_check.isChecked():
            return
        self._advance_episode()

    def _advance_episode(self):
        current_row = self.ep_list.currentRow()
        next_row = current_row + 1
        if next_row < self.ep_list.count():
            self.ep_list.setCurrentRow(next_row)
            self._play_episode(self.ep_list.currentItem())

    def _refresh_episode_watched_state(self, episode):
        """Update a single episode row's label without reloading the full list."""
        for i in range(self.ep_list.count()):
            item = self.ep_list.item(i)
            ep = item.data(Qt.ItemDataRole.UserRole)
            if ep == episode:
                ep_label = f"Episode {int(ep) if ep == int(ep) else ep}"
                item.setText("✓ " + ep_label + "  (last played)")
                item.setForeground(QBrush(QColor("#86efac")))
                break

    def _ep_context_menu(self, pos):
        item = self.ep_list.itemAt(pos)
        if not item:
            return
        ep = item.data(Qt.ItemDataRole.UserRole)
        watched = db.is_episode_watched(self._provider.NAME, self._result.identifier, ep)

        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        play_action   = menu.addAction("▶  Play")
        menu.addSeparator()
        toggle_action = menu.addAction("✗  Mark Unwatched" if watched else "✓  Mark Watched")
        mark_all_to   = menu.addAction("✓  Mark all up to here as Watched")
        menu.addSeparator()
        dl_action     = menu.addAction("⬇  Download")

        action = menu.exec(self.ep_list.mapToGlobal(pos))
        if action == play_action:
            self._play_episode(item)
        elif action == toggle_action:
            if watched:
                db.mark_unwatched(self._provider.NAME, self._result.identifier, ep)
            else:
                db.mark_watched(self._provider.NAME, self._result.identifier, ep)
            self._reload_episodes()
        elif action == mark_all_to:
            row = self.ep_list.row(item)
            for i in range(row + 1):
                ep_i = self.ep_list.item(i).data(Qt.ItemDataRole.UserRole)
                db.mark_watched(self._provider.NAME, self._result.identifier, ep_i)
            self._reload_episodes()
        elif action == dl_action:
            self.ep_list.setCurrentItem(item)
            self._download_selected()

    # ── Download ───────────────────────────────────────────────────────────────

    def _download_selected(self):
        item = self.ep_list.currentItem()
        if not item:
            self.ep_status.setText("Select an episode to download.")
            return

        ep = item.data(Qt.ItemDataRole.UserRole)
        lang = self.lang_combo.currentData()
        quality = self.quality_combo.currentData()
        self.ep_status.setText(f"Fetching stream for download...")

        self._dl_stream_worker = StreamWorker(
            self._provider, self._result.identifier, ep, lang, quality
        )
        self._dl_stream_worker.stream_ready.connect(
            lambda stream: self._start_download(stream, ep, lang)
        )
        self._dl_stream_worker.error.connect(
            lambda e: self.ep_status.setText(f"Stream error: {e}")
        )
        self._dl_stream_worker.start()

    def _start_download(self, stream, episode, lang):
        if not stream:
            self.ep_status.setText("No stream found for download.")
            return

        DEFAULT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c for c in self._result.name if c.isalnum() or c in " _-")
        filename = f"{safe_name} E{int(episode) if episode == int(episode) else episode} [{lang.value}]"
        download_path = DEFAULT_DOWNLOAD_DIR / filename

        worker = DownloadWorker(stream, download_path)

        # Log to db when done
        worker.done.connect(
            lambda path: db.log_download(
                self._provider.NAME, self._result.identifier,
                self._result.name, episode, lang.value, path
            )
        )

        worker.start()
        self.ep_status.setText(f"Download started for Episode {episode}.")
        self.download_started.emit(self._result.name, episode, worker)

    # ── Favorites ──────────────────────────────────────────────────────────────

    def _toggle_favorite(self):
        if not self._provider or not self._result:
            return
        provider = self._provider.NAME
        identifier = self._result.identifier
        if db.is_favorite(provider, identifier):
            db.remove_favorite(provider, identifier)
        else:
            db.add_favorite(provider, identifier, self._result.name, self._cover_image_url)
        self._refresh_fav_btn()

    def _refresh_fav_btn(self):
        if not self._provider or not self._result:
            return
        is_fav = db.is_favorite(self._provider.NAME, self._result.identifier)
        self.fav_btn.setText("♥ Unfavorite" if is_fav else "♡ Favorite")
