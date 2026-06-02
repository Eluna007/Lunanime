"""
Build an HTTP session that:
1. Impersonates Firefox's TLS fingerprint via curl-cffi
2. Injects cookies from the user's real Firefox profile

This bypasses Cloudflare / DDoS-Guard on sites the user has already visited
in their browser. If curl-cffi is unavailable, falls back to plain requests.
"""
import os
import shutil
import sqlite3
import tempfile
from configparser import ConfigParser
from pathlib import Path


def _find_firefox_profile() -> Path | None:
    home = Path.home()
    candidates = [
        home / ".mozilla" / "firefox",
        home / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
        home / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
        home / ".var" / "app" / "org.mozilla.firefox" / "data" / "profiles",
    ]

    for ff_dir in candidates:
        if not ff_dir.exists():
            continue

        ini = ff_dir / "profiles.ini"
        if ini.exists():
            cfg = ConfigParser()
            cfg.read(ini)
            for section in cfg.sections():
                if cfg.get(section, "Default", fallback="0") == "1":
                    rel = cfg.get(section, "IsRelative", fallback="1")
                    path = cfg.get(section, "Path", fallback="")
                    if path:
                        p = (ff_dir / path) if rel == "1" else Path(path)
                        if (p / "cookies.sqlite").exists():
                            return p

        for p in ff_dir.iterdir():
            if p.is_dir() and (p / "cookies.sqlite").exists():
                return p

    return None


def _read_cookies(profile: Path, domain: str) -> dict[str, str]:
    db = profile / "cookies.sqlite"
    if not db.exists():
        return {}

    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    try:
        shutil.copy2(db, tmp.name)
        conn = sqlite3.connect(tmp.name)
        cur = conn.cursor()
        cur.execute(
            "SELECT name, value FROM moz_cookies WHERE host LIKE ? OR host LIKE ?",
            (f"%{domain}", f"%.{domain}"),
        )
        cookies = {name: value for name, value in cur.fetchall()}
        conn.close()
    finally:
        os.unlink(tmp.name)

    return cookies


_FF_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0"

_BASE_HEADERS = {
    "User-Agent": _FF_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


def make_session(domain: str, extra_headers: dict | None = None):
    """
    Return a session with Firefox TLS fingerprint + real Firefox cookies.
    Uses curl-cffi if available (recommended), otherwise plain requests.
    """
    profile = _find_firefox_profile()
    cookies = _read_cookies(profile, domain) if profile else {}

    headers = {**_BASE_HEADERS, **(extra_headers or {})}

    try:
        from curl_cffi.requests import Session
        session = Session(impersonate="firefox")
        session.headers.update(headers)
        for name, value in cookies.items():
            session.cookies.set(name, value, domain=f".{domain}")
        return session
    except ImportError:
        import requests
        session = requests.Session()
        session.headers.update(headers)
        for name, value in cookies.items():
            session.cookies.set(name, value, domain=f".{domain}")
        return session
