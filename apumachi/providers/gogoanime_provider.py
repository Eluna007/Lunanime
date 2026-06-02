import re
from typing import List
from urllib.parse import urljoin, quote_plus

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

BASE_URL = "https://anitaku.pe"
AJAX_URL = "https://ajax.gogocdn.net"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Referer": BASE_URL + "/",
    "X-Requested-With": "XMLHttpRequest",
}


def _get_movie_id(soup: BeautifulSoup) -> str:
    tag = soup.select_one("#movie_id") or soup.select_one("input[name='movie_id']")
    if tag:
        return tag.get("value", "")
    match = re.search(r'"id"\s*:\s*(\d+)', str(soup))
    return match.group(1) if match else ""


class GogoAnimeProvider(BaseProvider):
    NAME = "gogoanime"
    BASE_URL = BASE_URL
    FILTER_CAPS = FilterCapabilities.NO_QUERY

    def get_search(self, query: str, filters: Filters = Filters()) -> List[ProviderSearchResult]:
        try:
            req = Request("GET", f"{BASE_URL}/search.html",
                         params={"keyword": query}, headers=HEADERS)
            res = self._request_page(req)
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception:
            return []

        results = []
        for item in soup.select("ul.items li"):
            a = item.select_one("p.name a")
            if not a:
                continue
            name = a.get_text(strip=True)
            href = a.get("href", "")
            slug = href.strip("/").split("/")[-1]
            if not slug:
                continue
            results.append(ProviderSearchResult(
                identifier=slug,
                name=name,
                languages={LanguageTypeEnum.SUB},
            ))
        return results

    def get_info(self, identifier: str) -> ProviderInfoResult:
        try:
            req = Request("GET", f"{BASE_URL}/category/{identifier}", headers=HEADERS)
            res = self._request_page(req)
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception:
            return ProviderInfoResult(name=identifier)

        info = ProviderInfoResult()
        title_tag = soup.select_one(".anime_info_body_bg h1")
        info.name = title_tag.get_text(strip=True) if title_tag else identifier

        img = soup.select_one(".anime_info_body_bg img")
        if img:
            info.image = img.get("src", "")

        for p in soup.select(".anime_info_body_bg p"):
            cls = p.get("class", [])
            if "type-1" in cls:
                info.synopsis = p.get_text(strip=True)
            text = p.get_text()
            if "Status:" in text:
                if "Ongoing" in text:
                    info.status = Status.ONGOING
                elif "Completed" in text:
                    info.status = Status.COMPLETED
            if "Released:" in text:
                m = re.search(r'\d{4}', text)
                if m:
                    info.release_year = int(m.group())
            if "Genre:" in text:
                info.genres = [a.get_text(strip=True) for a in p.select("a")]

        return info

    def get_episodes(self, identifier: str, lang: LanguageTypeEnum) -> List[Episode]:
        try:
            req = Request("GET", f"{BASE_URL}/category/{identifier}", headers=HEADERS)
            res = self._request_page(req)
            soup = BeautifulSoup(res.text, "html.parser")
            movie_id = _get_movie_id(soup)
            if not movie_id:
                return []
            ep_end_tag = soup.select_one("ul#episode_page li:last-child a")
            ep_end = ep_end_tag.get("ep_end", "0") if ep_end_tag else "0"
        except Exception:
            return []

        try:
            req = Request("GET", f"{AJAX_URL}/ajax/load-list-episode", params={
                "ep_start": 0, "ep_end": ep_end,
                "id": movie_id, "default_ep": 0, "alias": identifier,
            }, headers=HEADERS)
            res = self._request_page(req)
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception:
            return []

        episodes = []
        for li in soup.select("li"):
            a = li.select_one("a")
            if not a:
                continue
            href = a.get("href", "").strip()
            m = re.search(r'-episode-(\d+(?:\.\d+)?)', href)
            if m:
                episodes.append(parsenum(m.group(1)))
        return sorted(set(episodes))

    def get_video(self, identifier: str, episode: Episode, lang: LanguageTypeEnum) -> List[ProviderStream]:
        ep_num = int(episode) if episode == int(episode) else episode
        ep_slug = f"{identifier}-episode-{ep_num}"
        try:
            req = Request("GET", f"{BASE_URL}/{ep_slug}", headers=HEADERS)
            res = self._request_page(req)
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception:
            return []

        streams = []
        # Find embed links (vidstreaming / gogoplay / streamwish)
        for link in soup.select(".play-video iframe, a.active[data-video]"):
            embed_url = link.get("src") or link.get("data-video") or ""
            if not embed_url:
                continue
            if embed_url.startswith("//"):
                embed_url = "https:" + embed_url
            try:
                eres = self._request_page(Request("GET", embed_url, headers={
                    **HEADERS, "Referer": BASE_URL + "/",
                }))
                # Look for direct m3u8 source
                m3u8_match = re.search(
                    r'(?:file|src)\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', eres.text
                )
                if m3u8_match:
                    streams.append(ProviderStream(
                        url=m3u8_match.group(1), resolution=1080,
                        episode=episode, language=lang,
                        referrer=embed_url,
                    ))
            except Exception:
                continue

        return streams
