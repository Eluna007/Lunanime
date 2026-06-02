import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.expanduser("~"), ".lunanime.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                identifier TEXT NOT NULL,
                name TEXT NOT NULL,
                episode REAL NOT NULL,
                lang TEXT NOT NULL,
                quality TEXT NOT NULL,
                image_url TEXT,
                watched_at TEXT NOT NULL,
                UNIQUE(provider, identifier, episode, lang)
            );
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                identifier TEXT NOT NULL,
                name TEXT NOT NULL,
                image_url TEXT,
                added_at TEXT NOT NULL,
                UNIQUE(provider, identifier)
            );
            CREATE TABLE IF NOT EXISTS anime_prefs (
                provider TEXT NOT NULL,
                identifier TEXT NOT NULL,
                lang TEXT,
                quality TEXT,
                PRIMARY KEY(provider, identifier)
            );
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                identifier TEXT NOT NULL,
                name TEXT NOT NULL,
                episode REAL NOT NULL,
                lang TEXT NOT NULL,
                path TEXT NOT NULL,
                downloaded_at TEXT NOT NULL
            );
        """)


# ── History ──────────────────────────────────────────────────────────────────

def save_history(provider, identifier, name, episode, lang, quality, image_url=None):
    with _conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO history
            (provider, identifier, name, episode, lang, quality, image_url, watched_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (provider, identifier, name, episode, lang, quality, image_url,
              datetime.now().isoformat()))


def get_history(limit=30):
    with _conn() as c:
        rows = c.execute("""
            SELECT provider, identifier, name, MAX(episode) as episode,
                   lang, quality, image_url, MAX(watched_at) as watched_at
            FROM history
            GROUP BY provider, identifier, lang
            ORDER BY watched_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_last_episode(provider, identifier, lang):
    with _conn() as c:
        row = c.execute("""
            SELECT episode FROM history
            WHERE provider=? AND identifier=? AND lang=?
            ORDER BY watched_at DESC LIMIT 1
        """, (provider, identifier, lang)).fetchone()
    return row["episode"] if row else None


def clear_history():
    with _conn() as c:
        c.execute("DELETE FROM history")


# ── Favorites ─────────────────────────────────────────────────────────────────

def add_favorite(provider, identifier, name, image_url=None):
    with _conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO favorites (provider, identifier, name, image_url, added_at)
            VALUES (?,?,?,?,?)
        """, (provider, identifier, name, image_url, datetime.now().isoformat()))


def remove_favorite(provider, identifier):
    with _conn() as c:
        c.execute("DELETE FROM favorites WHERE provider=? AND identifier=?",
                  (provider, identifier))


def is_favorite(provider, identifier):
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM favorites WHERE provider=? AND identifier=?",
            (provider, identifier)
        ).fetchone()
    return row is not None


def get_favorites():
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM favorites ORDER BY added_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Per-anime preferences ─────────────────────────────────────────────────────

def save_anime_prefs(provider, identifier, lang, quality):
    with _conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO anime_prefs (provider, identifier, lang, quality)
            VALUES (?,?,?,?)
        """, (provider, identifier, lang, quality))


def get_anime_prefs(provider, identifier):
    with _conn() as c:
        row = c.execute(
            "SELECT lang, quality FROM anime_prefs WHERE provider=? AND identifier=?",
            (provider, identifier)
        ).fetchone()
    return dict(row) if row else None


# ── Downloads log ─────────────────────────────────────────────────────────────

def log_download(provider, identifier, name, episode, lang, path):
    with _conn() as c:
        c.execute("""
            INSERT INTO downloads (provider, identifier, name, episode, lang, path, downloaded_at)
            VALUES (?,?,?,?,?,?,?)
        """, (provider, identifier, name, episode, lang, path,
              datetime.now().isoformat()))


def get_downloads():
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM downloads ORDER BY downloaded_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]
