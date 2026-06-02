"""
KickAssAnime provider for kickassanime.com.es
Uses their public JSON API endpoints.
"""
import json
import m3u8
from typing import List
from urllib.parse import urljoin

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

_CANDIDATE_DOMAINS = [
    "https://kickassanime.am",
    "https://kickassanime.mx",
    "https://kickassanime.com.es",
]

def _resolve_base_url() -> str:
    import requests
    for domain in _CANDIDATE_DOMAINS:
        try:
            r = requests.get(f"{domain}/api/search?q=test", timeout=5,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code < 500:
                return domain
        except Exception:
            continue
    return _CANDIDATE_DOMAINS[0]

BASE_URL = _CANDIDATE_DOMAINS[0]
API_BASE = f"{BASE_URL}/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Referer": BASE_URL + "/",
}


class KickAssAnimeProvider(BaseProvider):
    NAME = "kickassanime"
    BASE_URL = BASE_URL
    FILTER_CAPS = FilterCapabilities.NO_QUERY

    def get_search(self, query: str, filters: Filters = Filters()) -> List[ProviderSearchResult]:
        base = _resolve_base_url()
        req = Request(
            "GET",
            f"{base}/api/search",
            params={"q": query, "page": 1},
            headers=HEADERS,
        )
        try:
            res = self._request_page(req).json()
        except Exception:
            return []

        results = []
        for item in res.get("result", res if isinstance(res, list) else []):
            slug = item.get("slug") or item.get("ani_slug") or item.get("id")
            name = item.get("title") or item.get("name") or item.get("title_en", "")
            if not slug or not name:
                continue

            langs = {LanguageTypeEnum.SUB}
            if item.get("dub_available") or item.get("has_dub"):
                langs.add(LanguageTypeEnum.DUB)

            results.append(ProviderSearchResult(
                identifier=str(slug),
                name=name,
                languages=langs,
            ))
        return results

    def get_info(self, identifier: str) -> ProviderInfoResult:
        base = _resolve_base_url()
        req = Request(
            "GET",
            f"{base}/api/show/{identifier}",
            headers=HEADERS,
        )
        try:
            data = self._request_page(req).json()
        except Exception:
            return ProviderInfoResult(name=identifier)

        status_map = {
            "currently_airing": Status.ONGOING,
            "finished_airing": Status.COMPLETED,
            "not_yet_aired": Status.UPCOMING,
        }

        image = data.get("poster") or data.get("image") or data.get("thumbnail")
        if image and not image.startswith("http"):
            image = BASE_URL + image

        return ProviderInfoResult(
            name=data.get("title") or data.get("title_en"),
            image=image,
            genres=[g.get("name", g) if isinstance(g, dict) else g for g in data.get("genres", [])],
            synopsis=data.get("synopsis") or data.get("description"),
            release_year=data.get("year") or data.get("release_year"),
            status=status_map.get(data.get("status", ""), None),
            alternative_names=[data["title_jp"]] if data.get("title_jp") else [],
        )

    def get_episodes(self, identifier: str, lang: LanguageTypeEnum) -> List[Episode]:
        episodes = []
        base = _resolve_base_url()
        page = 1
        while True:
            req = Request(
                "GET",
                f"{base}/api/show/{identifier}/episodes",
                params={"page": page, "ep_details": 1},
                headers=HEADERS,
            )
            try:
                data = self._request_page(req).json()
            except Exception:
                break

            items = data.get("result", data if isinstance(data, list) else [])
            if not items:
                break

            for ep in items:
                num = ep.get("ep_no") or ep.get("number") or ep.get("episode_number")
                if num is None:
                    continue
                if lang == LanguageTypeEnum.DUB and not ep.get("dub_available"):
                    continue
                episodes.append(parsenum(str(num)))

            if not data.get("next_page") and not (isinstance(data, dict) and len(items) == 20):
                break
            page += 1

        return sorted(set(episodes))

    def get_video(self, identifier: str, episode: Episode, lang: LanguageTypeEnum) -> List[ProviderStream]:
        ep_slug = f"episode-{int(episode)}" if episode == int(episode) else f"episode-{episode}"
        base = _resolve_base_url()
        req = Request(
            "GET",
            f"{base}/api/show/{identifier}/{ep_slug}",
            headers=HEADERS,
        )
        try:
            data = self._request_page(req).json()
        except Exception:
            return []

        streams = []
        servers = data.get("servers") or data.get("links") or []

        for server in servers:
            server_name = server.get("name") or server.get("server", "")
            if lang == LanguageTypeEnum.DUB and "dub" not in server_name.lower():
                continue
            if lang == LanguageTypeEnum.SUB and "dub" in server_name.lower():
                continue

            url = server.get("src") or server.get("link") or server.get("url", "")
            if not url:
                continue

            if url.endswith(".m3u8") or "/hls/" in url or "m3u8" in url:
                try:
                    hls_req = Request("GET", url, headers={"Referer": BASE_URL + "/"})
                    res = self._request_page(hls_req)
                    content = m3u8.M3U8(res.text, base_uri=urljoin(url, "."))
                    if content.playlists:
                        for pl in content.playlists:
                            streams.append(ProviderStream(
                                url=urljoin(content.base_uri, pl.uri),
                                resolution=pl.stream_info.resolution[1] if pl.stream_info.resolution else 720,
                                episode=episode,
                                language=lang,
                                referrer=BASE_URL,
                            ))
                        continue
                except Exception:
                    pass

            streams.append(ProviderStream(
                url=url,
                resolution=server.get("resolution", 720),
                episode=episode,
                language=lang,
                referrer=BASE_URL,
            ))

        return streams
