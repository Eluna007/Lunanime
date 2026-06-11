import re
from typing import List
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from requests import Request

from anipy_api.provider.base import (
    BaseProvider,
    ProviderSearchResult,
    ProviderInfoResult,
    ProviderStream,
    LanguageTypeEnum,
    Episode,
)
from anipy_api.provider.filter import FilterCapabilities, Filters, Status
from anipy_api.provider.utils import parsenum

BASE_URL = "https://animepahe.ru"
API_URL = f"{BASE_URL}/api"
DDG_CHECK_URL = "https://check.ddos-guard.net/check.js"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Referer": BASE_URL + "/",
}

_UNBASE_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _unbase(word: str, radix: int) -> int:
    """Decode a packed-JS word in the given radix (supports radix > 36)."""
    if radix <= 36:
        return int(word, radix)
    val = 0
    for ch in word:
        val = val * radix + _UNBASE_ALPHABET.index(ch)
    return val


def _unpack_kwik(js: str) -> str:
    """Unpack p,a,c,k,e,d JS and extract the HLS source URL."""
    match = re.search(r"return p\}\('(.+)',(\d+),(\d+),'([^']+)'", js, re.DOTALL)
    if not match:
        return ""
    p, a, k_str = match.group(1), int(match.group(2)), match.group(4).split("|")

    def replace_word(word_match):
        word = word_match.group(0)
        try:
            idx = _unbase(word, a)
        except ValueError:
            return word
        if idx < len(k_str) and k_str[idx]:
            return k_str[idx]
        return word

    result = re.sub(r'\b\w+\b', replace_word, p)
    source = re.search(r"const source=\\?'([^'\\]+)\\?'", result)
    if source:
        return source.group(1)
    m3u8 = re.search(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', result)
    return m3u8.group(0) if m3u8 else ""


class AnimePaheProvider(BaseProvider):
    NAME = "animepahe"
    BASE_URL = BASE_URL
    FILTER_CAPS = FilterCapabilities.NO_QUERY

    def _generate_new_session(self):
        session = super()._generate_new_session()
        session.headers.update(HEADERS)
        self._ddg_ready = False
        # Bonus: reuse the user's Firefox DDoS-Guard cookies when present
        try:
            from lunanime.firefox_cookies import _find_firefox_profile, _read_cookies
            profile = _find_firefox_profile()
            if profile:
                for domain in ("animepahe.ru", "kwik.si", "kwik.cx"):
                    for name, value in _read_cookies(profile, domain).items():
                        session.cookies.set(name, value, domain=f".{domain}")
                if any(c.name.startswith("__ddg") for c in session.cookies):
                    self._ddg_ready = True
        except Exception:
            pass
        return session

    def _ensure_ddg_cookie(self):
        """Acquire a __ddg2_ cookie via the DDoS-Guard well-known check
        endpoint (same flow the Aniyomi AnimePahe extension uses)."""
        if getattr(self, "_ddg_ready", False):
            return
        self._ddg_ready = True
        try:
            js = self._request_page(Request("GET", DDG_CHECK_URL)).text
            # body contains the per-site path inside the first quoted string
            parts = js.split("'")
            if len(parts) >= 2 and parts[1].startswith("/"):
                # response's set-cookie lands in the session automatically
                self._request_page(Request("GET", BASE_URL + parts[1]))
        except Exception:
            pass

    def get_search(self, query: str, filters: Filters = Filters()) -> List[ProviderSearchResult]:
        self._ensure_ddg_cookie()
        try:
            req = Request("GET", API_URL,
                          params={"m": "search", "l": 8, "q": query}, headers=HEADERS)
            data = self._request_page(req).json()
        except Exception:
            return []
        results = []
        for item in data.get("data", []):
            session = item.get("session", "")
            name = item.get("title", "")
            if not session or not name:
                continue
            results.append(ProviderSearchResult(
                identifier=session,
                name=name,
                languages={LanguageTypeEnum.SUB, LanguageTypeEnum.DUB},
            ))
        return results

    def get_info(self, identifier: str) -> ProviderInfoResult:
        self._ensure_ddg_cookie()
        try:
            req = Request("GET", API_URL, params={"m": "series", "id": identifier}, headers=HEADERS)
            data = self._request_page(req).json()
        except Exception:
            return ProviderInfoResult(name=identifier)
        status_map = {"Currently Airing": Status.ONGOING, "Finished Airing": Status.COMPLETED}
        return ProviderInfoResult(
            name=data.get("title"),
            image=data.get("poster"),
            synopsis=data.get("synopsis"),
            genres=data.get("genres", "").split(", ") if data.get("genres") else None,
            status=status_map.get(data.get("status", ""), None),
            release_year=data.get("year"),
        )

    def get_episodes(self, identifier: str, lang: LanguageTypeEnum) -> List[Episode]:
        self._ensure_ddg_cookie()
        episodes = []
        page = 1
        while True:
            try:
                req = Request("GET", API_URL, params={
                    "m": "release", "id": identifier,
                    "sort": "episode_asc", "page": page,
                }, headers=HEADERS)
                data = self._request_page(req).json()
            except Exception:
                break
            for ep in data.get("data", []):
                num = ep.get("episode") or ep.get("episode2")
                if num is not None:
                    episodes.append(parsenum(str(num)))
            if page >= data.get("last_page", 1):
                break
            page += 1
        return sorted(set(episodes))

    def _find_episode_session(self, identifier: str, episode: Episode):
        ep_num = float(episode)
        page = 1
        while True:
            try:
                req = Request("GET", API_URL, params={
                    "m": "release", "id": identifier,
                    "sort": "episode_asc", "page": page,
                }, headers=HEADERS)
                data = self._request_page(req).json()
            except Exception:
                return None
            for ep in data.get("data", []):
                if float(ep.get("episode") or ep.get("episode2") or -1) == ep_num:
                    return ep.get("session")
            if page >= data.get("last_page", 1):
                return None
            page += 1

    def get_video(self, identifier: str, episode: Episode, lang: LanguageTypeEnum) -> List[ProviderStream]:
        self._ensure_ddg_cookie()
        ep_session = self._find_episode_session(identifier, episode)
        if not ep_session:
            return []

        try:
            req = Request("GET", f"{BASE_URL}/play/{identifier}/{ep_session}", headers=HEADERS)
            res = self._request_page(req)
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception:
            return []

        # Quality buttons live in #resolutionMenu; data-audio marks dubs
        buttons = soup.select("div#resolutionMenu button[data-src]")
        if not buttons:
            buttons = soup.select("a[data-src], button[data-src]")

        want_dub = lang == LanguageTypeEnum.DUB
        matching = [b for b in buttons
                    if (b.get("data-audio") == "eng") == want_dub]
        if not matching:
            matching = buttons

        streams = []
        for btn in matching:
            kwik_url = btn.get("data-src", "")
            if not kwik_url or "kwik" not in kwik_url:
                continue
            quality = 720
            res_attr = btn.get("data-resolution", "") or btn.get_text(strip=True)
            qm = re.search(r'(\d{3,4})', res_attr)
            if qm:
                quality = int(qm.group(1))
            try:
                kres = self._request_page(Request("GET", kwik_url, headers={
                    **HEADERS, "Referer": BASE_URL + "/",
                }))
                m3u8_url = _unpack_kwik(kres.text)
                if not m3u8_url:
                    m3u8_match = re.search(
                        r'source\s*[=:]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', kres.text)
                    if m3u8_match:
                        m3u8_url = m3u8_match.group(1)
                if m3u8_url:
                    parsed = urlparse(kwik_url)
                    streams.append(ProviderStream(
                        url=m3u8_url, resolution=quality,
                        episode=episode, language=lang,
                        referrer=f"{parsed.scheme}://{parsed.netloc}/",
                    ))
            except Exception:
                continue

        return streams
