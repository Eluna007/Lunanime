import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests import Request, Session

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
KWIK_URL = "https://kwik.si"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Referer": BASE_URL + "/",
}


def _unpack_kwik(js: str) -> str:
    """Unpack p,a,c,k,e,d JS and extract m3u8 URL."""
    match = re.search(r"return p\}\('(.+)',(\d+),(\d+),'([^']+)'", js, re.DOTALL)
    if not match:
        return ""
    p, a, c, k_str = match.group(1), int(match.group(2)), int(match.group(3)), match.group(4).split("|")

    def replace_word(word: str) -> str:
        if not word:
            return word
        try:
            idx = int(word, a)
        except ValueError:
            try:
                idx = int(word, 36)
            except ValueError:
                return word
        replacement = k_str[idx] if idx < len(k_str) else ""
        return replacement if replacement else word

    result = re.sub(r'\b\w+\b', lambda m: replace_word(m.group(0)), p)
    m3u8 = re.search(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', result)
    return m3u8.group(0) if m3u8 else ""


class AnimePaheProvider(BaseProvider):
    NAME = "animepahe"
    BASE_URL = BASE_URL
    FILTER_CAPS = FilterCapabilities.NO_QUERY

    def _generate_new_session(self):
        """animepahe.ru sits behind DDoS-Guard; reuse the user's Firefox
        cookies (same approach as the WeebCentral/MangaFire scrapers)."""
        session = super()._generate_new_session()
        session.headers.update(HEADERS)
        try:
            from lunanime.firefox_cookies import _find_firefox_profile, _read_cookies
            profile = _find_firefox_profile()
            if profile:
                for domain in ("animepahe.ru", "kwik.si"):
                    for name, value in _read_cookies(profile, domain).items():
                        session.cookies.set(name, value, domain=f".{domain}")
        except Exception:
            pass
        return session

    def get_search(self, query: str, filters: Filters = Filters()) -> List[ProviderSearchResult]:
        try:
            req = Request("GET", API_URL, params={"m": "search", "q": query}, headers=HEADERS)
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
                languages={LanguageTypeEnum.SUB},
            ))
        return results

    def get_info(self, identifier: str) -> ProviderInfoResult:
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

    def get_video(self, identifier: str, episode: Episode, lang: LanguageTypeEnum) -> List[ProviderStream]:
        # Find the episode session
        ep_num = float(episode)
        page = 1
        ep_session = None
        while True:
            try:
                req = Request("GET", API_URL, params={
                    "m": "release", "id": identifier,
                    "sort": "episode_asc", "page": page,
                }, headers=HEADERS)
                data = self._request_page(req).json()
            except Exception:
                return []
            for ep in data.get("data", []):
                if float(ep.get("episode") or ep.get("episode2") or -1) == ep_num:
                    ep_session = ep.get("session")
                    break
            if ep_session or page >= data.get("last_page", 1):
                break
            page += 1

        if not ep_session:
            return []

        try:
            req = Request("GET", f"{BASE_URL}/play/{identifier}/{ep_session}", headers=HEADERS)
            res = self._request_page(req)
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception:
            return []

        streams = []
        for link in soup.select("a[data-src]"):
            kwik_url = link.get("data-src", "")
            if not kwik_url or "kwik" not in kwik_url:
                continue
            quality_text = link.get_text(strip=True)
            quality = 720
            qm = re.search(r'(\d{3,4})p', quality_text)
            if qm:
                quality = int(qm.group(1))
            try:
                kres = self._request_page(Request("GET", kwik_url, headers={
                    **HEADERS, "Referer": BASE_URL + "/",
                }))
                m3u8_url = _unpack_kwik(kres.text)
                if not m3u8_url:
                    # fallback: search for source directly
                    m3u8_match = re.search(r'source\s+src=["\']([^"\']+\.m3u8[^"\']*)["\']', kres.text)
                    if m3u8_match:
                        m3u8_url = m3u8_match.group(1)
                if m3u8_url:
                    streams.append(ProviderStream(
                        url=m3u8_url, resolution=quality,
                        episode=episode, language=lang,
                        referrer=KWIK_URL + "/",
                    ))
            except Exception:
                continue

        return streams
