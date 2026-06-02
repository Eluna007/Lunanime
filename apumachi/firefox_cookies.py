"""
Read cookies from the user's Firefox profile and build a requests.Session.
Works for any Cloudflare/DDoS-Guard protected site — as long as the user
has visited the site in Firefox recently, the cf_clearance cookie is reused.
"""
import os
import shutil
import sqlite3
import tempfile
from configparser import ConfigParser
from pathlib import Path

import requests


def _find_firefox_profile() -> Path | None:
    ff_dir = Path.home() / ".mozilla" / "firefox"
    if not ff_dir.exists():
        return None

    # Parse profiles.ini to find the default profile
    ini = ff_dir / "profiles.ini"
    if ini.exists():
        cfg = ConfigParser()
        cfg.read(ini)
        # Prefer the profile marked as default
        for section in cfg.sections():
            if cfg.get(section, "Default", fallback="0") == "1":
                rel = cfg.get(section, "IsRelative", fallback="1")
                path = cfg.get(section, "Path", fallback="")
                if path:
                    p = (ff_dir / path) if rel == "1" else Path(path)
                    if (p / "cookies.sqlite").exists():
                        return p

    # Fallback: any dir that has cookies.sqlite
    for p in ff_dir.iterdir():
        if p.is_dir() and (p / "cookies.sqlite").exists():
            return p

    return None


def _read_cookies(profile: Path, domain: str) -> dict[str, str]:
    db = profile / "cookies.sqlite"
    if not db.exists():
        return {}

    # Copy so we don't conflict with Firefox's lock
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


def _firefox_useragent(profile: Path) -> str:
    """Read the UA from Firefox's prefs, fall back to a sensible Linux default."""
    prefs = profile / "prefs.js"
    if prefs.exists():
        for line in prefs.read_text(errors="ignore").splitlines():
            if "general.useragent.override" in line:
                # user_pref("general.useragent.override", "Mozilla/5.0 ...");
                start = line.find('"', line.find(",")) + 1
                end = line.rfind('"')
                if start > 0 and end > start:
                    return line[start:end]
    return (
        "Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0"
    )


def make_session(domain: str, extra_headers: dict | None = None) -> requests.Session:
    """
    Return a requests.Session loaded with Firefox cookies for *domain*.
    Falls back to a plain session with a Firefox UA if no profile is found.
    """
    session = requests.Session()

    profile = _find_firefox_profile()
    ua = _firefox_useragent(profile) if profile else (
        "Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0"
    )

    session.headers.update({
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })

    if extra_headers:
        session.headers.update(extra_headers)

    if profile:
        cookies = _read_cookies(profile, domain)
        for name, value in cookies.items():
            session.cookies.set(name, value, domain=f".{domain}")

    return session
