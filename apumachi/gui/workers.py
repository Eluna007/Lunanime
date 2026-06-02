from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from anipy_api.provider.base import LanguageTypeEnum


class SearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, provider, query: str, filters=None):
        super().__init__()
        self.provider = provider
        self.query = query
        self.filters = filters

    def run(self):
        try:
            from anipy_api.provider.filter import Filters
            f = self.filters or Filters()
            results = self.provider.get_search(self.query, f)
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


class TrendingWorker(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, provider, season=None, year=None, limit=24):
        super().__init__()
        self.provider = provider
        self.season = season
        self.year = year
        self.limit = limit

    def run(self):
        try:
            from anipy_api.provider.filter import Filters
            f = Filters(season=self.season, year=self.year)
            results = self.provider.get_search("", f)
            self.results_ready.emit(results[:self.limit])
        except Exception as e:
            self.error.emit(str(e))


class AniListResult:
    """Lightweight result object from AniList, compatible with AnimeCard."""
    def __init__(self, anilist_id: int, name: str, image_url: str):
        self.anilist_id = anilist_id
        self.name = name
        self.image_url = image_url


class AniListWorker(QThread):
    """Fetches trending or seasonal anime from AniList's public GraphQL API."""
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    _GQL_URL = "https://graphql.anilist.co"

    _QUERY = """
    query ($page: Int, $perPage: Int, $sort: [MediaSort], $season: MediaSeason, $year: Int) {
      Page(page: $page, perPage: $perPage) {
        media(type: ANIME, sort: $sort, season: $season, seasonYear: $year, isAdult: false) {
          id
          title { romaji english }
          coverImage { large }
        }
      }
    }
    """

    _SEASON_MAP = {
        "WINTER": "WINTER",
        "SPRING": "SPRING",
        "SUMMER": "SUMMER",
        "FALL":   "FALL",
    }

    def __init__(self, mode: str = "trending", season=None, year=None, limit: int = 24):
        super().__init__()
        self.mode = mode      # "trending" or "seasonal"
        self.season = season  # anipy Season enum or None
        self.year = year
        self.limit = limit

    def run(self):
        try:
            import requests
            sort = "TRENDING_DESC" if self.mode == "trending" else "POPULARITY_DESC"
            variables = {"page": 1, "perPage": self.limit, "sort": [sort]}
            if self.mode == "seasonal" and self.season is not None:
                variables["season"] = self._SEASON_MAP.get(self.season.name.upper(), "SUMMER")
                variables["year"] = self.year or __import__("datetime").date.today().year

            resp = requests.post(
                self._GQL_URL,
                json={"query": self._QUERY, "variables": variables},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            media_list = resp.json()["data"]["Page"]["media"]
            results = []
            for m in media_list:
                title = m["title"].get("english") or m["title"].get("romaji") or "Unknown"
                image = m["coverImage"].get("large") or ""
                results.append(AniListResult(m["id"], title, image))
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class AutoPlayWorker(QThread):
    finished = pyqtSignal()

    def __init__(self, player):
        super().__init__()
        self.player = player

    def run(self):
        try:
            self.player.wait()
        except Exception:
            pass
        self.finished.emit()


class DownloadWorker(QThread):
    progress = pyqtSignal(float)
    info = pyqtSignal(str)
    finished = pyqtSignal(str)   # emits final path
    error = pyqtSignal(str)

    def __init__(self, stream, download_path: Path, use_ffmpeg: bool = False):
        super().__init__()
        self.stream = stream
        self.download_path = download_path
        self.use_ffmpeg = use_ffmpeg

    def run(self):
        try:
            from anipy_api.download import Downloader
            dl = Downloader(
                progress_callback=lambda p: self.progress.emit(p),
                info_callback=lambda msg, exc_info=None: self.info.emit(msg),
            )
            path = dl.download(
                self.stream,
                self.download_path,
                ffmpeg=self.use_ffmpeg,
            )
            self.finished.emit(str(path))
        except Exception as e:
            self.error.emit(str(e))
