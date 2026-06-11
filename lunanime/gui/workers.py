from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from anipy_api.provider.base import LanguageTypeEnum

# In-memory image cache shared across all ImageWorker instances
_IMAGE_CACHE: dict[str, bytes] = {}
_IMAGE_CACHE_MAX = 200

# Strong references to running workers. A QThread that loses its last
# Python reference while running is destroyed mid-run, which aborts the
# entire application ("QThread: Destroyed while thread is still running").
_ACTIVE_WORKERS: set = set()


class Worker(QThread):
    """Base for all background workers: keeps itself alive while running
    and offers retire() to drop a stale worker without terminate()."""

    def start(self, *args):
        _ACTIVE_WORKERS.add(self)
        self.finished.connect(lambda: _ACTIVE_WORKERS.discard(self))
        super().start(*args)

    _RESULT_SIGNALS = ("results_ready", "error", "info_ready", "episodes_ready",
                       "stream_ready", "image_ready", "meta_ready", "done",
                       "progress", "info", "success")

    def retire(self):
        """Detach result listeners; the thread finishes on its own and its
        late results are ignored. Safer than terminate(), which can kill
        the thread mid-request and corrupt state."""
        for name in self._RESULT_SIGNALS:
            sig = getattr(self, name, None)
            if sig is not None:
                try:
                    sig.disconnect()
                except TypeError:
                    pass  # no connections on this signal


class SearchWorker(Worker):
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


class InfoWorker(Worker):
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


class EpisodesWorker(Worker):
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


class StreamWorker(Worker):
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


class ImageWorker(Worker):
    image_ready = pyqtSignal(bytes)

    def __init__(self, url: str, referer: str = ""):
        super().__init__()
        self.url = url
        self.referer = referer or url

    def run(self):
        if self.url in _IMAGE_CACHE:
            self.image_ready.emit(_IMAGE_CACHE[self.url])
            return
        try:
            import requests
            res = requests.get(self.url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": self.referer,
            })
            if res.ok:
                if len(_IMAGE_CACHE) >= _IMAGE_CACHE_MAX:
                    # evict oldest entry
                    _IMAGE_CACHE.pop(next(iter(_IMAGE_CACHE)))
                _IMAGE_CACHE[self.url] = res.content
                self.image_ready.emit(res.content)
        except Exception:
            pass


class TrendingWorker(Worker):
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


class AniListWorker(Worker):
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


class JikanWorker(Worker):
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


class AutoPlayWorker(Worker):
    done = pyqtSignal()

    def __init__(self, player):
        super().__init__()
        self.player = player

    def run(self):
        try:
            self.player.wait()
        except Exception:
            pass
        self.done.emit()


class DownloadWorker(Worker):
    progress = pyqtSignal(float)
    info = pyqtSignal(str)
    done = pyqtSignal(str)       # emits final path
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
            self.done.emit(str(path))
        except Exception as e:
            self.error.emit(str(e))


class OAuthWorker(Worker):
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
            from lunanime import tracking
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


class TrackingWorker(Worker):
    """Syncs a watched episode to AniList and/or MAL. Silent failures."""

    def __init__(self, title: str, episode: int, provider: str, identifier: str):
        super().__init__()
        self.title      = title
        self.episode    = int(episode)
        self.provider   = provider
        self.identifier = identifier

    def run(self):
        from lunanime import tracking
        try:
            tracking.anilist_sync(self.title, self.episode, self.provider, self.identifier)
        except Exception:
            pass
        try:
            tracking.mal_sync(self.title, self.episode, self.provider, self.identifier)
        except Exception:
            pass


# ── MangaDex workers ──────────────────────────────────────────────────────────

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
        self.pages       = pages    # int count (filled after page fetch)
        self.scanlator   = scanlator


_MDX = "https://api.mangadex.org"
_CDN = "https://uploads.mangadex.org"


class MangaSearchWorker(Worker):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query: str, limit: int = 20):
        super().__init__()
        self.query = query
        self.limit = limit

    def run(self):
        try:
            import requests
            params = {
                "title": self.query, "limit": self.limit,
                "contentRating[]": ["safe", "suggestive"],
                "includes[]": ["cover_art"],
                "order[relevance]": "desc",
            }
            r = requests.get(f"{_MDX}/manga", params=params, timeout=15)
            r.raise_for_status()
            self.results_ready.emit(_parse_manga_list(r.json()["data"]))
        except Exception as e:
            self.error.emit(str(e))


class MangaDexBrowseWorker(Worker):
    """Browse MangaDex without a query: trending (most followed) or
    hot (most followed among recently created titles)."""
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, mode: str = "trending", limit: int = 20):
        super().__init__()
        self.mode = mode    # "trending" | "hot"
        self.limit = limit

    def run(self):
        try:
            import requests
            from datetime import datetime, timedelta
            params = {
                "limit": self.limit,
                "contentRating[]": ["safe", "suggestive"],
                "includes[]": ["cover_art"],
                "order[followedCount]": "desc",
                "hasAvailableChapters": "true",
            }
            if self.mode == "hot":
                since = datetime.utcnow() - timedelta(days=90)
                params["createdAtSince"] = since.strftime("%Y-%m-%dT%H:%M:%S")
            r = requests.get(f"{_MDX}/manga", params=params, timeout=15)
            r.raise_for_status()
            self.results_ready.emit(_parse_manga_list(r.json()["data"]))
        except Exception as e:
            self.error.emit(str(e))


class MangaChaptersWorker(Worker):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, manga_id: str, lang: str = "en"):
        super().__init__()
        self.manga_id = manga_id
        self.lang = lang

    def run(self):
        try:
            import requests
            chapters, offset, limit = [], 0, 100
            while True:
                r = requests.get(f"{_MDX}/manga/{self.manga_id}/feed", params={
                    "translatedLanguage[]": [self.lang],
                    "order[chapter]": "asc",
                    "limit": limit, "offset": offset,
                    "includes[]": ["scanlation_group"],
                    "contentRating[]": ["safe", "suggestive", "erotica"],
                }, timeout=15)
                r.raise_for_status()
                data = r.json()
                batch = data["data"]
                for ch in batch:
                    attrs = ch["attributes"]
                    num   = attrs.get("chapter") or "?"
                    title = attrs.get("title") or ""
                    lang  = attrs.get("translatedLanguage", "en")
                    pages = attrs.get("pages", 0)
                    group = ""
                    for rel in ch.get("relationships", []):
                        if rel["type"] == "scanlation_group":
                            group = rel.get("attributes", {}).get("name", "") or ""
                    chapters.append(MangaChapter(ch["id"], num, title, lang, pages, group))
                offset += len(batch)
                if offset >= data["total"] or len(batch) < limit:
                    break
            self.results_ready.emit(chapters)
        except Exception as e:
            self.error.emit(str(e))


class MangaPagesWorker(Worker):
    results_ready = pyqtSignal(list)   # list of page URLs
    error = pyqtSignal(str)

    def __init__(self, chapter_id: str, data_saver: bool = False):
        super().__init__()
        self.chapter_id = chapter_id
        self.data_saver = data_saver

    def run(self):
        try:
            import requests
            r = requests.get(f"{_MDX}/at-home/server/{self.chapter_id}", timeout=15)
            r.raise_for_status()
            d = r.json()
            base  = d["baseUrl"]
            ch    = d["chapter"]
            mode  = "data-saver" if self.data_saver else "data"
            files = ch["dataSaver"] if self.data_saver else ch["data"]
            hash_ = ch["hash"]
            urls  = [f"{base}/{mode}/{hash_}/{f}" for f in files]
            self.results_ready.emit(urls)
        except Exception as e:
            self.error.emit(str(e))


def _parse_manga_list(data: list) -> list:
    results = []
    for m in data:
        attrs = m["attributes"]
        title = (attrs.get("title", {}).get("en")
                 or next(iter(attrs.get("title", {}).values()), "Unknown"))
        desc  = (attrs.get("description", {}).get("en") or "")[:400]
        status = attrs.get("status", "")
        tags  = [t["attributes"]["name"].get("en", "")
                 for t in attrs.get("tags", [])][:6]
        cover_url = ""
        for rel in m.get("relationships", []):
            if rel["type"] == "cover_art" and rel.get("attributes"):
                fn = rel["attributes"].get("fileName", "")
                cover_url = f"{_CDN}/covers/{m['id']}/{fn}.256.jpg"
                break
        results.append(MangaResult(m["id"], title, desc, cover_url, status, tags))
    return results


# ── WeebCentral workers ───────────────────────────────────────────────────────

_WC_BASE = "https://weebcentral.com"


def _wc_session():
    from lunanime.firefox_cookies import make_session
    return make_session("weebcentral.com", {"Referer": _WC_BASE + "/"})


class WeebCentralSearchWorker(Worker):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query: str, limit: int = 20):
        super().__init__()
        self.query = query
        self.limit = limit

    def run(self):
        try:
            import re
            import requests as _requests
            from bs4 import BeautifulSoup
            from lunanime.firefox_cookies import _FF_UA

            # WeebCentral doesn't need cookies (returns 200 without them).
            # Use plain requests — curl-cffi impersonate strips custom HTMX headers.
            s = _requests.Session()
            s.headers.update({
                "User-Agent": _FF_UA,
                "HX-Request": "true",
                "HX-Target": "search-results",
                "HX-Current-URL": f"{_WC_BASE}/search",
                "Referer": f"{_WC_BASE}/search",
                "Accept": "text/html, */*",
            })
            r = s.get(
                f"{_WC_BASE}/search/data",
                params={"text": self.query, "author": "", "display_mode": "Minimal Display"},
                timeout=15,
            )
            r.raise_for_status()

            # Results are <article> elements; title is in <a data-tip="...">
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for article in soup.select("article"):
                a = article.select_one("a[href*='/series/']")
                if not a:
                    continue
                href = a.get("href", "")
                m = re.search(r'/series/([^/?#]+)', href)
                if not m:
                    continue
                mid = m.group(1)
                if mid.lower() == "random":
                    continue
                title = a.get("data-tip", "").strip() or a.get_text(strip=True).strip() or mid
                tags = [s.get_text(strip=True).rstrip(",") for s in article.select("section span")]
                status_divs = article.select("section div")
                status = next((d.get_text(strip=True).lower() for d in status_divs
                               if d.get_text(strip=True).lower() in ("complete", "ongoing", "hiatus")), "")
                results.append(MangaResult(mid, title, "", "", status, tags[:6]))
                if len(results) >= self.limit:
                    break

            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class WeebCentralMetaWorker(Worker):
    """Fetches cover URL and description for a WeebCentral series."""
    meta_ready = pyqtSignal(str, str)   # cover_url, description
    error = pyqtSignal(str)

    def __init__(self, manga_id: str):
        super().__init__()
        self.manga_id = manga_id

    def run(self):
        try:
            import requests as _requests
            from bs4 import BeautifulSoup
            from lunanime.firefox_cookies import _FF_UA

            s = _requests.Session()
            s.headers.update({
                "User-Agent": _FF_UA,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
                "Referer": _WC_BASE + "/",
            })
            r = s.get(f"{_WC_BASE}/series/{self.manga_id}", timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            cover_url = ""
            og = soup.find("meta", property="og:image")
            if og:
                cover_url = og.get("content", "")
            if not cover_url:
                img = soup.select_one("section img, article img, .cover img, img.cover")
                if img:
                    cover_url = img.get("src", "") or img.get("data-src", "")

            desc = ""
            og_desc = soup.find("meta", property="og:description")
            if og_desc:
                desc = og_desc.get("content", "").strip()
            if not desc:
                p = soup.select_one("section p, .description p, p.synopsis")
                if p:
                    desc = p.get_text(strip=True)

            self.meta_ready.emit(cover_url, desc)
        except Exception as e:
            self.error.emit(str(e))


class WeebCentralChaptersWorker(Worker):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, manga_id: str, lang: str = "en"):
        super().__init__()
        self.manga_id = manga_id
        self.lang = lang

    def run(self):
        try:
            from bs4 import BeautifulSoup
            session = _wc_session()
            # manga_id is the series ID portion: /series/{id}/...
            r = session.get(
                f"{_WC_BASE}/series/{self.manga_id}/full-chapter-list",
                timeout=15,
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            chapters = []
            for a in soup.select("a[href*='/chapters/']"):
                href = a.get("href", "")
                # href like https://weebcentral.com/chapters/XXXXX
                ch_id = href.rstrip("/").split("/")[-1]
                # chapter number from text like "Chapter 001" or span
                text = a.get_text(" ", strip=True)
                import re
                num_m = re.search(r'[Cc]hapter\s+(\d+(?:\.\d+)?)', text)
                num = num_m.group(1) if num_m else text.split()[-1] if text else "?"
                title_span = a.select_one("span:not(.sr-only)")
                ch_title = title_span.get_text(strip=True) if title_span else ""
                chapters.append(MangaChapter(ch_id, num, ch_title, self.lang, 0, ""))
            # chapters are newest-first from the page; reverse to ascending
            chapters.reverse()
            self.results_ready.emit(chapters)
        except Exception as e:
            self.error.emit(str(e))


class WeebCentralPagesWorker(Worker):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, chapter_id: str, data_saver: bool = False):
        super().__init__()
        self.chapter_id = chapter_id
        self.data_saver = data_saver

    def run(self):
        try:
            from bs4 import BeautifulSoup
            session = _wc_session()
            r = session.get(
                f"{_WC_BASE}/chapters/{self.chapter_id}/images",
                params={"reading_style": "long_strip"},
                timeout=15,
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            urls = []
            for img in soup.select("img[src]"):
                src = img.get("src", "")
                if src and ("weebcentral" in src or "weebcdn" in src or src.startswith("http")):
                    urls.append(src)
            if not urls:
                # try data-src lazy loaded
                for img in soup.select("img[data-src]"):
                    src = img.get("data-src", "")
                    if src:
                        urls.append(src)
            self.results_ready.emit(urls)
        except Exception as e:
            self.error.emit(str(e))


# ── MangaFire workers ─────────────────────────────────────────────────────────

_MF_BASE = "https://mangafire.to"


def _mf_session():
    from lunanime.firefox_cookies import make_session
    return make_session("mangafire.to", {"Referer": _MF_BASE + "/"})


class MangaFireSearchWorker(Worker):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query: str, limit: int = 20):
        super().__init__()
        self.query = query
        self.limit = limit

    def run(self):
        try:
            import re
            from bs4 import BeautifulSoup
            session = _mf_session()
            r = session.get(f"{_MF_BASE}/filter",
                            params={"keyword": self.query, "page": 1},
                            timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for item in soup.select(".original.card-lg .unit, .manga-list .unit, .card"):
                a = item.select_one("a[href*='/manga/']")
                if not a:
                    continue
                href = a.get("href", "")
                m = re.search(r'/manga/([^/?#]+)', href)
                if not m:
                    continue
                manga_id = m.group(1)
                img = item.select_one("img")
                cover = img.get("src", "") or img.get("data-src", "") if img else ""
                title_el = item.select_one(".title, h3, h2, .name")
                title = title_el.get_text(strip=True) if title_el else manga_id
                results.append(MangaResult(manga_id, title, "", cover, "", []))
                if len(results) >= self.limit:
                    break
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class MangaFireChaptersWorker(Worker):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, manga_id: str, lang: str = "en"):
        super().__init__()
        self.manga_id = manga_id
        self.lang = lang

    def run(self):
        try:
            import re
            from bs4 import BeautifulSoup
            session = _mf_session()
            r = session.get(f"{_MF_BASE}/manga/{self.manga_id}", timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            chapters = []
            # MangaFire chapter list is in a #en-chapters (or #ja-chapters etc) div
            lang_map = {"en": "en", "es": "es", "fr": "fr", "pt-br": "pt", "de": "de"}
            lang_code = lang_map.get(self.lang, "en")
            ch_container = soup.select_one(f"#{lang_code}-chapters, .chapter-list")
            if not ch_container:
                ch_container = soup
            for li in ch_container.select("li, .item"):
                a = li.select_one("a[href*='/read/']")
                if not a:
                    continue
                href = a.get("href", "")
                m = re.search(r'/read/([^/?#]+)/([^/?#]+)', href)
                if not m:
                    continue
                ch_id = href  # full URL as ID
                num_text = a.get_text(strip=True)
                nm = re.search(r'(\d+(?:\.\d+)?)', num_text)
                num = nm.group(1) if nm else "?"
                chapters.append(MangaChapter(href, num, "", self.lang, 0, ""))
            chapters.reverse()
            self.results_ready.emit(chapters)
        except Exception as e:
            self.error.emit(str(e))


class MangaFirePagesWorker(Worker):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, chapter_url: str, data_saver: bool = False):
        super().__init__()
        self.chapter_url = chapter_url
        self.data_saver = data_saver

    def run(self):
        try:
            import re
            from bs4 import BeautifulSoup
            session = _mf_session()
            r = session.get(self.chapter_url, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            urls = []
            # Pages are in a .reader-images container or similar
            for img in soup.select(".reader-images img, #chapter-images img, .chapter-images img"):
                src = img.get("src", "") or img.get("data-src", "")
                if src:
                    urls.append(src)
            if not urls:
                # Fallback: look for JSON data in script tags
                for script in soup.select("script"):
                    text = script.string or ""
                    matches = re.findall(r'"(https?://[^"]+\.(?:jpg|png|webp)[^"]*)"', text)
                    urls.extend(matches)
                    if urls:
                        break
            self.results_ready.emit(urls)
        except Exception as e:
            self.error.emit(str(e))

# ── MangaPill workers ─────────────────────────────────────────────────────────

_MP_BASE = "https://mangapill.com"
MANGAPILL_REFERER = _MP_BASE + "/"

_MP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Referer": MANGAPILL_REFERER,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class MangaPillSearchWorker(Worker):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query: str, limit: int = 20):
        super().__init__()
        self.query = query
        self.limit = limit

    def run(self):
        try:
            import re
            import requests
            from bs4 import BeautifulSoup
            r = requests.get(f"{_MP_BASE}/search",
                             params={"q": self.query, "type": "", "status": ""},
                             headers=_MP_HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            results, seen = [], set()
            for a in soup.select("a[href^='/manga/']"):
                href = a.get("href", "")
                m = re.match(r'^/manga/(\d+/[^/?#]+)', href)
                if not m or m.group(1) in seen:
                    continue
                manga_id = m.group(1)
                # cards contain the cover <img>; plain text links are duplicates
                img = a.select_one("img")
                container = a.parent
                title_el = (container.select_one("a div, .font-black, .mt-3 a")
                            if container else None)
                title = (a.get_text(strip=True)
                         or (title_el.get_text(strip=True) if title_el else "")
                         or manga_id.split("/")[-1].replace("-", " ").title())
                cover = ""
                if img:
                    cover = img.get("data-src", "") or img.get("src", "")
                if not img and not a.get_text(strip=True):
                    continue
                seen.add(manga_id)
                results.append(MangaResult(manga_id, title, "", cover, "", []))
                if len(results) >= self.limit:
                    break
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class MangaPillChaptersWorker(Worker):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, manga_id: str, lang: str = "en"):
        super().__init__()
        self.manga_id = manga_id
        self.lang = lang

    def run(self):
        try:
            import re
            import requests
            from bs4 import BeautifulSoup
            r = requests.get(f"{_MP_BASE}/manga/{self.manga_id}",
                             headers=_MP_HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            chapters = []
            for a in soup.select("a[href^='/chapters/']"):
                href = a.get("href", "")
                m = re.match(r'^/chapters/([^?#]+)', href)
                if not m:
                    continue
                ch_id = m.group(1)
                text = a.get_text(strip=True)
                nm = re.search(r'(\d+(?:\.\d+)?)', text)
                num = nm.group(1) if nm else text or "?"
                chapters.append(MangaChapter(ch_id, num, "", "en", 0, ""))
            # page lists newest-first; flip to ascending like other sources
            chapters.reverse()
            self.results_ready.emit(chapters)
        except Exception as e:
            self.error.emit(str(e))


class MangaPillPagesWorker(Worker):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, chapter_id: str, data_saver: bool = False):
        super().__init__()
        self.chapter_id = chapter_id
        self.data_saver = data_saver

    def run(self):
        try:
            import requests
            from bs4 import BeautifulSoup
            r = requests.get(f"{_MP_BASE}/chapters/{self.chapter_id}",
                             headers=_MP_HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            urls = []
            for img in soup.select("picture img, img.js-page"):
                src = img.get("data-src", "") or img.get("src", "")
                if src.startswith("http"):
                    urls.append(src)
            self.results_ready.emit(urls)
        except Exception as e:
            self.error.emit(str(e))
