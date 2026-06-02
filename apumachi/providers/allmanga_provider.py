import json
import hashlib
import base64
import m3u8
from copy import deepcopy
from typing import List, Optional
from urllib.parse import urljoin

import Levenshtein
from requests import Request
from requests.exceptions import HTTPError
from Cryptodome.Cipher import AES

from anipy_api.provider.base import (
    BaseProvider,
    ProviderSearchResult,
    ProviderInfoResult,
    ProviderStream,
    LanguageTypeEnum,
    ExternalSub,
    Episode,
)
from anipy_api.provider.filter import (
    BaseFilter,
    FilterCapabilities,
    Filters,
    MediaType,
    Season,
    Status,
)
from anipy_api.provider.utils import get_language_name, parsenum


API_URL = "https://api.allanime.day/api"
REFERER = "https://allmanga.to/"
BASE_URL = "https://allmanga.to"


def _decode_tobeparsed(tbp: str):
    raw = base64.b64decode(tbp)
    key = hashlib.sha256("Xot36i3lK3:v1".encode()).digest()
    iv, ciphertext, tag = raw[1:13], raw[13:-16], raw[-16:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    return json.loads(cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8"))


def _decrypt_source(provider_id: str) -> str:
    decrypted = ""
    for hex_val in [provider_id[i:i + 2] for i in range(0, len(provider_id), 2)]:
        xor = int(hex_val, 16) ^ 56
        decrypted += chr(int(oct(xor)[2:].zfill(3), 8))
    return decrypted


class AllMangaFilter(BaseFilter):
    def _apply_query(self, query: str):
        if query:
            self._request.json["variables"]["search"].update({"query": query})

    def _apply_year(self, year: int):
        self._request.json["variables"]["search"].update({"year": int(year)})

    def _apply_season(self, season: Season):
        self._request.json["variables"]["search"].update({"season": season.name.capitalize()})

    def _apply_status(self, status: Status): ...

    def _apply_media_type(self, media_type: MediaType):
        mapping = {
            MediaType.TV: "TV",
            MediaType.SPECIAL: "Special",
            MediaType.MOVIE: "Movie",
            MediaType.OVA: "OVA",
            MediaType.ONA: "ONA",
        }
        self._request.json["variables"]["search"].update({"types": [mapping[media_type]]})


class AllMangaProvider(BaseProvider):
    NAME = "allmanga"
    BASE_URL = BASE_URL
    FILTER_CAPS = (
        FilterCapabilities.YEAR
        | FilterCapabilities.MEDIA_TYPE
        | FilterCapabilities.SEASON
        | FilterCapabilities.NO_QUERY
    )

    def get_search(self, query: str, filters: Filters = Filters()) -> List[ProviderSearchResult]:
        req = Request(
            "POST",
            API_URL,
            json={
                "variables": {
                    "search": {},
                    "limit": 26,
                    "page": 1,
                    "translationType": "sub",
                    "countryOrigin": "ALL",
                },
                "extensions": json.dumps({
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "a24c500a1b765c68ae1d8dd85174931f661c71369c89b92b88b75a725afc471c"
                    }
                }),
            },
            headers={"Referer": REFERER},
        )
        req = AllMangaFilter(req).apply(query, filters)
        results = []
        page = 1
        while True:
            req.json["variables"]["page"] = page
            final_req = deepcopy(req)
            final_req.params["variables"] = json.dumps(final_req.json["variables"])
            res = self._request_page(final_req).json()
            edges = res["data"]["shows"]["edges"]
            if not edges:
                break
            for a in edges:
                langs = {LanguageTypeEnum.SUB}
                if a.get("availableEpisodes", {}).get("dub", 0) > 0:
                    langs |= {LanguageTypeEnum.DUB}
                results.append(ProviderSearchResult(
                    identifier=a["_id"],
                    name=a["name"],
                    languages=langs,
                ))
            page += 1

        if query:
            results.sort(
                key=lambda x: Levenshtein.ratio(query, x.name, processor=str.lower),
                reverse=True,
            )
        return results

    def get_episodes(self, identifier: str, lang: LanguageTypeEnum) -> List[Episode]:
        req = Request(
            "POST",
            API_URL,
            json={
                "variables": json.dumps({"_id": identifier}),
                "extensions": json.dumps({
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "043448386c7a686bc2aabfbb6b80f6074e795d350df48015023b079527b0848a"
                    }
                }),
            },
            headers={"Referer": REFERER},
        )
        result = self._request_page(req).json()
        key = "dub" if lang == LanguageTypeEnum.DUB else "sub"
        episodes = result["data"]["show"]["availableEpisodesDetail"][key]
        return sorted([parsenum(e) for e in episodes])

    def get_info(self, identifier: str) -> ProviderInfoResult:
        req = Request(
            "POST",
            API_URL,
            json={
                "variables": json.dumps({"_id": identifier}),
                "extensions": json.dumps({
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "043448386c7a686bc2aabfbb6b80f6074e795d350df48015023b079527b0848a"
                    }
                }),
            },
            headers={"Referer": REFERER},
        )
        data = self._request_page(req).json()["data"]["show"]
        status_map = {"Releasing": Status.ONGOING, "Finished": Status.COMPLETED}
        return ProviderInfoResult(
            name=data.get("name"),
            image=data.get("thumbnail"),
            genres=data.get("genres"),
            status=status_map.get(data.get("status", ""), None),
            synopsis=data.get("description"),
            release_year=data.get("airedStart", {}).get("year"),
            alternative_names=data.get("altNames"),
        )

    def get_video(self, identifier: str, episode: Episode, lang: LanguageTypeEnum) -> List[ProviderStream]:
        tt = "dub" if lang == LanguageTypeEnum.DUB else "sub"
        req = Request(
            "POST",
            API_URL,
            json={
                "variables": json.dumps({
                    "showId": identifier,
                    "translationType": tt,
                    "episodeString": str(episode),
                }),
                "extensions": json.dumps({
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "d405d0edd690624b66baba3068e0edc3ac90f1597d898a1ec8db4e5c43c00fec"
                    }
                }),
            },
            headers={"Referer": "https://youtu-chan.com/"},
        )
        result = self._request_page(req).json()
        streams = []
        providers_allowed = ["Yt-mp4", "S-Mp4", "Uv-mp4", "Ak", "Default"]

        if "tobeparsed" in result["data"]:
            data = _decode_tobeparsed(result["data"]["tobeparsed"])
        else:
            data = result["data"]

        for src in data["episode"]["sourceUrls"]:
            if src["sourceName"] not in providers_allowed:
                continue

            if "tools.fast4speed.rsvp" in src["sourceUrl"]:
                streams.append(ProviderStream(
                    url=src["sourceUrl"], resolution=1080,
                    episode=episode, language=lang, referrer=BASE_URL,
                ))
                continue

            decrypted_path = _decrypt_source(
                src["sourceUrl"].replace("--", "")
            ).replace("clock", "clock.json")

            clock_req = Request(
                "GET",
                f"https://allanime.day{decrypted_path}",
                headers={"Referer": REFERER},
            )
            try:
                for _ in range(3):
                    raw = self._request_page(clock_req)
                    if raw.text:
                        break
                else:
                    continue
                links_data = raw.json()
            except (HTTPError, Exception):
                continue

            for link_obj in links_data.get("links", []):
                link = link_obj["link"]
                subs = {}
                for sub in link_obj.get("subtitles", []):
                    subs[sub["label"]] = ExternalSub(
                        url=sub["src"], shortcode=sub["lang"],
                        codec="vtt", lang=get_language_name(sub["lang"]) or sub["label"],
                    )

                if "repackager.wixmp.com" in link:
                    link = link.split(".urlset")[0].replace("repackager.wixmp.com/", "")
                    parts = link.split(",")
                    p1, p2 = parts[0], parts[-1]
                    for qual in parts[1:-1]:
                        streams.append(ProviderStream(
                            url=p1 + qual + p2,
                            resolution=int(qual.replace("p", "")),
                            episode=episode, language=lang, referrer=BASE_URL,
                        ))
                    continue

                referer = link_obj.get("headers", {}).get("Referer", BASE_URL)
                try:
                    hls_res = self._request_page(Request("GET", link, headers={"Referer": referer}))
                except HTTPError:
                    continue

                content = m3u8.M3U8(hls_res.text, base_uri=urljoin(link, "."))
                if not content.playlists:
                    streams.append(ProviderStream(
                        url=link, resolution=1080,
                        episode=episode, language=lang,
                        subtitle=subs or None, referrer=referer,
                    ))
                else:
                    for pl in content.playlists:
                        streams.append(ProviderStream(
                            url=urljoin(content.base_uri, pl.uri),
                            resolution=pl.stream_info.resolution[1],
                            episode=episode, language=lang,
                            subtitle=subs or None, referrer=referer,
                        ))
        return streams
