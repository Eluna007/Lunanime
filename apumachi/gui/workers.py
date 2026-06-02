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


class JikanResult:
    """Lightweight result from Jikan (MyAnimeList) API."""
    def __init__(self, mal_id: int, name: str, image_url: str, score: float = 0.0, episodes: int = 0):
        self.mal_id = mal_id
        self.name = name
        self.image_url = image_url
        self.score = score
        self.episodes = episodes


class JikanWorker(QThread):
    """Fetches seasonal anime from Jikan (unofficial MAL REST API, no auth)."""
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    _BASE = "https://api.jikan.moe/v4"

    def __init__(self, mode: str = "now", season: str = None, year: int = None, limit: int = 25):
        super().__init__()
        self.mode = mode        # "now" (current season), "season" (specific), "top" (all-time popular)
        self.season = season    # "winter"/"spring"/"summer"/"fall"
        self.year = year
        self.limit = limit

    def run(self):
        try:
            import requests, time
            if self.mode == "top":
                url = f"{self._BASE}/top/anime"
                params = {"limit": self.limit, "filter": "airing"}
            elif self.mode == "season" and self.season and self.year:
                url = f"{self._BASE}/seasons/{self.year}/{self.season.lower()}"
                params = {"limit": self.limit}
            else:
                url = f"{self._BASE}/seasons/now"
                params = {"limit": self.limit}

            resp = requests.get(url, params=params, timeout=15,
                                headers={"Accept": "application/json"})
            # Jikan rate-limits: 3 req/s — retry once on 429
            if resp.status_code == 429:
                time.sleep(1)
                resp = requests.get(url, params=params, timeout=15,
                                    headers={"Accept": "application/json"})
            resp.raise_for_status()
            data = resp.json().get("data", [])
            results = []
            for item in data[:self.limit]:
                title = (item.get("title_english") or item.get("title") or "Unknown")
                image = item.get("images", {}).get("jpg", {}).get("large_image_url", "")
                score = item.get("score") or 0.0
                episodes = item.get("episodes") or 0
                results.append(JikanResult(item["mal_id"], title, image, score, episodes))
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


class OAuthWorker(QThread):
    """Runs an OAuth connect flow in a thread (opens browser, waits for callback)."""
    success = pyqtSignal(str)   # username
    error   = pyqtSignal(str)

    def __init__(self, service: str, client_id: str, client_secret: str = ""):
        super().__init__()
        self.service = service
        self.client_id = client_id
        self.client_secret = client_secret

    def run(self):
        try:
            from apumachi import tracking
            if self.service == "anilist":
                result = tracking.anilist_connect(self.client_id, self.client_secret)
            else:
                result = tracking.mal_connect(self.client_id)
            if result:
                self.success.emit(result["username"])
            else:
                self.error.emit("No authorisation code received (timed out).")
        except Exception as e:
            self.error.emit(str(e))


class TrackingWorker(QThread):
    """Syncs a watched episode to AniList and/or MAL. Silent failures."""

    def __init__(self, title: str, episode: int, provider: str, identifier: str):
        super().__init__()
        self.title      = title
        self.episode    = int(episode)
        self.provider   = provider
        self.identifier = identifier

    def run(self):
        from apumachi import tracking
        try:
            tracking.anilist_sync(self.title, self.episode, self.provider, self.identifier)
        except Exception:
            pass
        try:
            tracking.mal_sync(self.title, self.episode, self.provider, self.identifier)
        except Exception:
            pass


# ── AllManga manga workers ────────────────────────────────────────────────────

_AM_API   = "https://api.allanime.day/api"
_AM_REF   = "https://allmanga.to/"

_AM_SEARCH_HASH   = "a24c500a1b765c68ae1d8dd85174931f661c71369c89b92b88b75a725afc471c"
_AM_DETAILS_HASH  = "043448386c7a686bc2aabfbb6b80f6074e795d350df48015023b079527b0848a"
_AM_CHAPTERS_HASH = "b08f9a5e0df79ef28d2c6aab09b7d1e299ed3e94f3c2b3c2bf5d2b1f77e5d37c"
_AM_PAGES_HASH    = "a9f84027b57d48b9d8baf46c3a7b68eca5f9b827c37de95e5b1a1ef9fd1db7e3"


class MangaResult:
    def __init__(self, manga_id, title, description, cover_url, status, tags):
        self.manga_id    = manga_id
        self.title       = title
        self.name        = title   # AnimeCard compat
        self.description = description
        self.cover_url   = cover_url
        self.image_url   = cover_url
        self.status      = status
        self.tags        = tags


class MangaChapter:
    def __init__(self, chapter_id, chapter_num, title, lang, pages, scanlator=""):
        self.chapter_id  = chapter_id
        self.chapter_num = chapter_num
        self.title       = title
        self.lang        = lang
        self.pages       = pages
        self.scanlator   = scanlator


def _am_post(variables: dict, hash_: str) -> dict:
    import json, requests
    params = {
        "variables": json.dumps(variables),
        "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": hash_}}),
    }
    r = requests.get(_AM_API, params=params,
                     headers={"Referer": _AM_REF}, timeout=15)
    r.raise_for_status()
    return r.json()


class MangaSearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query: str, limit: int = 26):
        super().__init__()
        self.query = query
        self.limit = limit

    def run(self):
        try:
            results = []
            page = 1
            while True:
                data = _am_post({
                    "search": {"query": self.query, "isManga": True},
                    "limit": self.limit,
                    "page": page,
                    "translationType": "scan",
                    "countryOrigin": "ALL",
                }, _AM_SEARCH_HASH)
                edges = data.get("data", {}).get("shows", {}).get("edges", [])
                if not edges:
                    break
                for item in edges:
                    thumbnail = item.get("thumbnail") or ""
                    if thumbnail and not thumbnail.startswith("http"):
                        thumbnail = "https://cdn.allanime.day/" + thumbnail.lstrip("/")
                    results.append(MangaResult(
                        manga_id=item["_id"],
                        title=item.get("name", ""),
                        description=(item.get("description") or "")[:400],
                        cover_url=thumbnail,
                        status=item.get("status", ""),
                        tags=(item.get("genres") or [])[:6],
                    ))
                page += 1
                if page > 3:
                    break
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class MangaChaptersWorker(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, manga_id: str, lang: str = "en"):
        super().__init__()
        self.manga_id = manga_id
        self.lang = lang

    def run(self):
        try:
            data = _am_post({"_id": self.manga_id}, _AM_DETAILS_HASH)
            show = data["data"]["show"]
            raw = show.get("availableChaptersDetail", {})
            # chapters keyed by "sub"/"scan" — use "sub" as primary
            chapter_list = raw.get("sub") or raw.get("scan") or raw.get("dub") or []
            chapters = []
            for ch_str in chapter_list:
                chapters.append(MangaChapter(
                    chapter_id=ch_str,
                    chapter_num=ch_str,
                    title="",
                    lang=self.lang,
                    pages=0,
                    scanlator="",
                ))
            # Sort numerically where possible
            def _sort_key(c):
                try:
                    return float(c.chapter_num)
                except ValueError:
                    return 0.0
            chapters.sort(key=_sort_key)
            self.results_ready.emit(chapters)
        except Exception as e:
            self.error.emit(str(e))


class MangaPagesWorker(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, chapter_id: str, data_saver: bool = False,
                 manga_id: str = "", lang: str = "en"):
        super().__init__()
        self.chapter_id = chapter_id
        self.data_saver = data_saver
        self.manga_id   = manga_id
        self.lang       = lang

    def run(self):
        try:
            data = _am_post({
                "showId": self.manga_id,
                "chapterString": self.chapter_id,
                "translationType": "scan",
            }, _AM_PAGES_HASH)
            episode = data["data"]["episode"]
            source_urls = episode.get("sourceUrls", [])
            urls = []
            for src in source_urls:
                raw_url = src.get("sourceUrl", "")
                if not raw_url:
                    continue
                # Decrypt if it looks like a hex-encoded path
                if all(c in "0123456789abcdefABCDEF" for c in raw_url.replace("--", "")):
                    import requests, json as _json
                    from apumachi.providers.allmanga_provider import _decrypt_source
                    path = _decrypt_source(raw_url.replace("--", ""))
                    r = requests.get(
                        f"https://allanime.day{path}",
                        headers={"Referer": _AM_REF}, timeout=15,
                    )
                    if r.ok:
                        for link_obj in r.json().get("links", []):
                            link = link_obj.get("link", "")
                            if link:
                                urls.append(link)
                else:
                    urls.append(raw_url)
            self.results_ready.emit(urls)
        except Exception as e:
            self.error.emit(str(e))
