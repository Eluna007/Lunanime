import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QProgressBar, QFileDialog, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..db import get_downloads, log_download


class DownloadItem(QWidget):
    open_requested = pyqtSignal(str)

    def __init__(self, name, episode, lang, path, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        info = QVBoxLayout()
        title = QLabel(f"{name} — Episode {episode} [{lang.upper()}]")
        title.setStyleSheet("font-weight: bold;")
        info.addWidget(title)
        path_label = QLabel(path)
        path_label.setObjectName("subtitleLabel")
        path_label.setWordWrap(True)
        info.addWidget(path_label)
        layout.addLayout(info, 1)

        exists = os.path.exists(path)
        open_btn = QPushButton("Open" if exists else "Missing")
        open_btn.setFixedWidth(70)
        open_btn.setEnabled(exists)
        open_btn.clicked.connect(lambda: self.open_requested.emit(path))
        layout.addWidget(open_btn)


class ActiveDownload(QWidget):
    cancel_requested = pyqtSignal()

    def __init__(self, name, episode, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        self.title = QLabel(f"Downloading: {name} — Episode {episode}")
        self.title.setStyleSheet("font-weight: bold;")
        header.addWidget(self.title, 1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("danger", True)
        cancel_btn.setFixedWidth(70)
        cancel_btn.clicked.connect(self.cancel_requested)
        header.addWidget(cancel_btn)
        layout.addLayout(header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Starting...")
        self.status_label.setObjectName("subtitleLabel")
        layout.addWidget(self.status_label)

    def set_progress(self, pct: float):
        self.progress_bar.setValue(int(pct))

    def set_status(self, msg: str):
        self.status_label.setText(msg)


class DownloadsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_widgets = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Downloads")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        # Active downloads area
        active_label = QLabel("Active")
        active_label.setObjectName("sectionLabel")
        layout.addWidget(active_label)

        self._active_area = QVBoxLayout()
        self._active_area.setSpacing(8)
        layout.addLayout(self._active_area)

        self._no_active_label = QLabel("No active downloads.")
        self._no_active_label.setObjectName("subtitleLabel")
        layout.addWidget(self._no_active_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a2a3a;")
        layout.addWidget(sep)

        # Completed downloads
        completed_row = QHBoxLayout()
        completed_label = QLabel("Completed")
        completed_label.setObjectName("sectionLabel")
        completed_row.addWidget(completed_label)
        completed_row.addStretch()

        folder_btn = QPushButton("Open Folder")
        folder_btn.setProperty("flat", True)
        folder_btn.setFixedWidth(110)
        folder_btn.clicked.connect(self._open_download_folder)
        completed_row.addWidget(folder_btn)
        layout.addLayout(completed_row)

        self._list = QListWidget()
        layout.addWidget(self._list, 1)

        self.refresh()

    def refresh(self):
        self._list.clear()
        for dl in get_downloads():
            item = QListWidgetItem(self._list)
            widget = DownloadItem(dl["name"], dl["episode"], dl["lang"], dl["path"])
            widget.open_requested.connect(self._open_file)
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

    def add_active_download(self, name, episode, worker):
        widget = ActiveDownload(name, episode)
        widget.cancel_requested.connect(worker.terminate)
        worker.progress.connect(widget.set_progress)
        worker.info.connect(widget.set_status)
        worker.done.connect(lambda path, w=widget: self._on_finished(w, path))
        worker.error.connect(lambda err, w=widget: self._on_error(w, err))
        self._active_area.addWidget(widget)
        self._active_widgets.append(widget)
        self._no_active_label.setVisible(False)

    def _on_finished(self, widget, path):
        self._remove_active(widget)
        self.refresh()

    def _on_error(self, widget, error):
        widget.set_status(f"Error: {error}")

    def _remove_active(self, widget):
        self._active_area.removeWidget(widget)
        widget.deleteLater()
        if widget in self._active_widgets:
            self._active_widgets.remove(widget)
        self._no_active_label.setVisible(len(self._active_widgets) == 0)

    def _open_file(self, path):
        import subprocess
        subprocess.Popen(["xdg-open", path])

    def _open_download_folder(self):
        folder = os.path.join(os.path.expanduser("~"), "Lunanime Downloads")
        os.makedirs(folder, exist_ok=True)
        import subprocess
        subprocess.Popen(["xdg-open", folder])
