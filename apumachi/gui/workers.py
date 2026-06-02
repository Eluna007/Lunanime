from PyQt6.QtCore import QThread, pyqtSignal
from anipy_api.provider.base import LanguageTypeEnum


class SearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, provider, query: str):
        super().__init__()
        self.provider = provider
        self.query = query

    def run(self):
        try:
            results = self.provider.get_search(self.query)
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class InfoWorker(QThread):
    info_ready = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, provider, identifier: str):
        super().__init__()
        self.provider = provider
        self.identifier = identifier

    def run(self):
        try:
            info = self.provider.get_info(self.identifier)
            self.info_ready.emit(info)
        except Exception as e:
            self.error.emit(str(e))


class EpisodesWorker(QThread):
    episodes_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, provider, identifier: str, lang: LanguageTypeEnum):
        super().__init__()
        self.provider = provider
        self.identifier = identifier
        self.lang = lang

    def run(self):
        try:
            episodes = self.provider.get_episodes(self.identifier, self.lang)
            self.episodes_ready.emit(episodes)
        except Exception as e:
            self.error.emit(str(e))


class StreamWorker(QThread):
    stream_ready = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, provider, identifier: str, episode, lang: LanguageTypeEnum, quality):
        super().__init__()
        self.provider = provider
        self.identifier = identifier
        self.episode = episode
        self.lang = lang
        self.quality = quality

    def run(self):
        try:
            from anipy_api.anime import Anime
            anime = Anime(self.provider, "", self.identifier, {self.lang})
            stream = anime.get_video(self.episode, self.lang, self.quality)
            self.stream_ready.emit(stream)
        except Exception as e:
            self.error.emit(str(e))


class ImageWorker(QThread):
    image_ready = pyqtSignal(bytes)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            import requests
            res = requests.get(self.url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": self.url,
            })
            if res.ok:
                self.image_ready.emit(res.content)
        except Exception:
            pass
