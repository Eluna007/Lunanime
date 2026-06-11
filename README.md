# Lunanime

A desktop anime streaming and manga reading app for Linux, built with PyQt6.

## Features

- **Anime**: search, browse seasonal charts, and stream episodes through an
  external player (mpv, vlc, …) with sub/dub and quality selection.
- **Manga**: search across multiple sources, read chapters in a built-in
  vertical-scroll reader with zoom and lazy page loading. The manga tab
  opens on a discover page with Continue Reading, Trending, and Hot New
  sections (clear the search box to get back to it).
- **Discover**: trending and seasonal anime from AniList and MyAnimeList
  (Jikan), playable through any configured anime provider.
- **Tracking**: optional AniList and MyAnimeList sync of watched episodes
  (OAuth, set up under Settings).
- **Library**: watch/read history, favorites, per-anime language/quality
  preferences, and episode downloads — all stored locally in
  `~/.lunanime.db`.

## Sources

| Type  | Source      | Notes                                          |
|-------|-------------|------------------------------------------------|
| Anime | AllManga    | API-based, sub + dub                            |
| Anime | AnimePahe   | Uses your Firefox cookies to pass DDoS-Guard    |
| Manga | MangaDex    | Official API, multi-language                    |
| Manga | WeebCentral | HTML source                                     |
| Manga | MangaFire   | Uses your Firefox cookies to pass Cloudflare    |
| Manga | MangaPill   | HTML source, English                            |

Sources behind Cloudflare/DDoS-Guard work by reusing cookies from your local
Firefox profile — visit the site once in Firefox if a source stops responding.

## Install

```bash
pip install -r requirements.txt
```

You also need a media player for anime playback — `mpv` is recommended.

## Run

```bash
python main.py
```

## Keyboard shortcuts

| Key          | Action                              |
|--------------|-------------------------------------|
| `Ctrl+F`     | Focus search                        |
| `Esc`        | Back (anime detail / manga reader)  |
| `N`          | Next episode (anime detail)         |
| `←` / `→`    | Previous / next chapter (reader)    |
| `+` / `-` / `0` | Zoom in / out / reset (reader)   |

## Disclaimer

Lunanime does not host any content. It aggregates publicly available
third-party sources; use it in accordance with the laws of your country.
