"""
AnimeUnity provider for animeunity.so
Scrapes their HTML pages to extract episode and video data.
"""
import json
import re
import m3u8
from typing import List, Optional
from urllib.parse import urljoin, quote

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

BASE_URL = "https://www.animeunity.so"
API_URL = f"{BASE_URL}/archivio"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Referer": BASE_URL + "/",
    "X-Requested-With": "XMLHttpRequest",
}


class AnimeUnityProvider(BaseProvider):
    NAME = "animeunity"
    BASE_URL = BASE_URL
    FILTER_CAPS = FilterCapabilities.NO_QUERY

    def _api_request(self, endpoint: str, params: dict = None, data: dict = None):
        req = Request(
            "POST" if data else "GET",
            f"{BASE_URL}{endpoint}",
            params=params,
            json=data,
            headers=HEADERS,
        )
        return self._request_page(req)

    def get_search(self, query: str, filters: Filters = Filters()) -> List[ProviderSearchResult]:
        try:
            res = self._api_request(
                "/archivio",
                data={"title": query, "start": 0, "length": 30},
            )
            data = res.json()
        except Exception:
            return []

        results = []
        items = data.get("data", data if isinstance(data, list) else [])
        for item in items:
            slug = item.get("slug") or item.get("id")
            name = item.get("title_eng") or item.get("title") or item.get("title_it", "")
            if not slug or not name:
                continue

            langs = {LanguageTypeEnum.SUB}
            if item.get("dub") or item.get("language", "").lower() == "ita":
                langs.add(LanguageTypeEnum.DUB)

            results.append(ProviderSearchResult(
                identifier=str(slug),
                name=name,
                languages=langs,
            ))
        return results

    def get_info(self, identifier: str) -> ProviderInfoResult:
        req = Request("GET", f"{BASE_URL}/anime/{identifier}", headers=HEADERS)
        try:
            res = self._request_page(req)
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception:
            return ProviderInfoResult(name=identifier)

        info = ProviderInfoResult()

        title_tag = soup.select_one("h1.title, h2.title, .info-title h1")
        info.name = title_tag.get_text(strip=True) if title_tag else identifier

        img_tag = soup.select_one(".cover img, .poster img, img[alt*='cover']")
        if img_tag:
            src = img_tag.get("src") or img_tag.get("data-src", "")
            info.image = src if src.startswith("http") else BASE_URL + src

        desc_tag = soup.select_one(".description, .synopsis, p.plot")
        info.synopsis = desc_tag.get_text(strip=True) if desc_tag else None

        genre_tags = soup.select("a[href*='/genre/'], .genres a, .tags a")
        info.genres = [g.get_text(strip=True) for g in genre_tags] or None

        year_match = re.search(r"\b(19|20)\d{2}\b", res.text)
        info.release_year = int(year_match.group()) if year_match else None

        json_match = re.search(r'"status"\s*:\s*"([^"]+)"', res.text)
        if json_match:
            status_map = {
                "In Corso": Status.ONGOING,
                "Concluso": Status.COMPLETED,
                "Annunciato": Status.UPCOMING,
            }
            info.status = status_map.get(json_match.group(1))

        return info

    def get_episodes(self, identifier: str, lang: LanguageTypeEnum) -> List[Episode]:
        req = Request("GET", f"{BASE_URL}/anime/{identifier}", headers=HEADERS)
        try:
            res = self._request_page(req)
        except Exception:
            return []

        # AnimeUnity embeds episode data as JSON in the page
        match = re.search(r'episodes\s*=\s*(\[.*?\])', res.text, re.DOTALL)
        if not match:
            # Try alternate JSON embedding pattern
            match = re.search(r'"episodes"\s*:\s*(\[.*?\])', res.text, re.DOTALL)
        if not match:
            # Try to find episode links directly
            soup = BeautifulSoup(res.text, "html.parser")
            ep_links = soup.select("a[href*='/episode']")
            episodes = []
            for link in ep_links:
                num_match = re.search(r'episode[s]?[-/](\d+(?:\.\d+)?)', link.get("href", ""))
                if num_match:
                    episodes.append(parsenum(num_match.group(1)))
            return sorted(set(episodes)) if episodes else []

        try:
            ep_data = json.loads(match.group(1))
            episodes = []
            for ep in ep_data:
                num = ep.get("number") or ep.get("episode") or ep.get("num")
                if num is not None:
                    episodes.append(parsenum(str(num)))
            return sorted(set(episodes))
        except json.JSONDecodeError:
            return []

    def get_video(self, identifier: str, episode: Episode, lang: LanguageTypeEnum) -> List[ProviderStream]:
        ep_num = int(episode) if episode == int(episode) else episode
        req = Request(
            "GET",
            f"{BASE_URL}/anime/{identifier}/episode-{ep_num}",
            headers=HEADERS,
        )
        try:
            res = self._request_page(req)
        except Exception:
            return []

        streams = []

        # Look for embedded video player JSON (common pattern on AnimeUnity)
        video_match = re.search(r'"file"\s*:\s*"([^"]+\.m3u8[^"]*)"', res.text)
        if video_match:
            url = video_match.group(1).replace("\\/", "/")
            try:
                hls_req = Request("GET", url, headers={"Referer": BASE_URL + "/"})
                hls_res = self._request_page(hls_req)
                content = m3u8.M3U8(hls_res.text, base_uri=urljoin(url, "."))
                if content.playlists:
                    for pl in content.playlists:
                        streams.append(ProviderStream(
                            url=urljoin(content.base_uri, pl.uri),
                            resolution=pl.stream_info.resolution[1] if pl.stream_info.resolution else 720,
                            episode=episode,
                            language=lang,
                            referrer=BASE_URL,
                        ))
                    return streams
            except Exception:
                pass
            streams.append(ProviderStream(
                url=url, resolution=1080,
                episode=episode, language=lang,
                referrer=BASE_URL,
            ))

        # Fallback: look for scws embed
        scws_match = re.search(r'https://scws\.[^/"\']+/[^"\']+', res.text)
        if not streams and scws_match:
            embed_url = scws_match.group(0)
            streams.append(ProviderStream(
                url=embed_url, resolution=1080,
                episode=episode, language=lang,
                referrer=BASE_URL,
            ))

        return streams
