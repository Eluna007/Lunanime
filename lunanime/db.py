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
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                service TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                expires_at TEXT,
                username TEXT,
                user_id TEXT
            );
            CREATE TABLE IF NOT EXISTS tracking_ids (
                provider TEXT NOT NULL,
                identifier TEXT NOT NULL,
                anilist_id INTEGER,
                mal_id INTEGER,
                PRIMARY KEY(provider, identifier)
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS watched_episodes (
                provider TEXT NOT NULL,
                identifier TEXT NOT NULL,
                episode REAL NOT NULL,
                marked_at TEXT NOT NULL,
                PRIMARY KEY(provider, identifier, episode)
            );
            CREATE TABLE IF NOT EXISTS manga_history (
                manga_id TEXT NOT NULL,
                chapter_id TEXT NOT NULL,
                chapter_num TEXT NOT NULL,
                title TEXT NOT NULL,
                marked_at TEXT NOT NULL,
                source TEXT,
                cover_url TEXT,
                PRIMARY KEY(manga_id, chapter_id)
            );
        """)
        # Migrate pre-existing databases
        cols = {r[1] for r in c.execute("PRAGMA table_info(manga_history)")}
        for col in ("source", "cover_url"):
            if col not in cols:
                c.execute(f"ALTER TABLE manga_history ADD COLUMN {col} TEXT")


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


# ── OAuth tokens ──────────────────────────────────────────────────────────────

def save_oauth_token(service, access_token, refresh_token=None,
                     expires_at=None, username=None, user_id=None):
    with _conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO oauth_tokens
            (service, access_token, refresh_token, expires_at, username, user_id)
            VALUES (?,?,?,?,?,?)
        """, (service, access_token, refresh_token, expires_at, username, user_id))


def get_oauth_token(service) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM oauth_tokens WHERE service=?", (service,)).fetchone()
    return dict(row) if row else None


def delete_oauth_token(service):
    with _conn() as c:
        c.execute("DELETE FROM oauth_tokens WHERE service=?", (service,))


# ── Tracking IDs ──────────────────────────────────────────────────────────────

def save_tracking_id(provider, identifier, anilist_id=None, mal_id=None):
    with _conn() as c:
        c.execute("""
            INSERT INTO tracking_ids (provider, identifier, anilist_id, mal_id)
            VALUES (?,?,?,?)
            ON CONFLICT(provider, identifier) DO UPDATE SET
                anilist_id = COALESCE(excluded.anilist_id, anilist_id),
                mal_id     = COALESCE(excluded.mal_id, mal_id)
        """, (provider, identifier, anilist_id, mal_id))


def get_tracking_id(provider, identifier, service: str):
    col = "anilist_id" if service == "anilist" else "mal_id"
    with _conn() as c:
        row = c.execute(
            f"SELECT {col} FROM tracking_ids WHERE provider=? AND identifier=?",
            (provider, identifier)
        ).fetchone()
    return row[col] if row and row[col] else None


# ── App settings key-value ────────────────────────────────────────────────────

def save_setting(key, value):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?,?)", (key, value))


def get_setting(key) -> str | None:
    with _conn() as c:
        row = c.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


# ── Watched episodes ──────────────────────────────────────────────────────────

def mark_watched(provider, identifier, episode):
    with _conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO watched_episodes (provider, identifier, episode, marked_at)
            VALUES (?,?,?,?)
        """, (provider, identifier, episode, datetime.now().isoformat()))


def mark_unwatched(provider, identifier, episode):
    with _conn() as c:
        c.execute("DELETE FROM watched_episodes WHERE provider=? AND identifier=? AND episode=?",
                  (provider, identifier, episode))


def get_watched_episodes(provider, identifier) -> set:
    with _conn() as c:
        rows = c.execute(
            "SELECT episode FROM watched_episodes WHERE provider=? AND identifier=?",
            (provider, identifier)
        ).fetchall()
    return {r["episode"] for r in rows}


def is_episode_watched(provider, identifier, episode) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM watched_episodes WHERE provider=? AND identifier=? AND episode=?",
            (provider, identifier, episode)
        ).fetchone()
    return row is not None


# ── Manga read history ────────────────────────────────────────────────────────

def mark_chapter_read(manga_id, chapter_id, chapter_num, title,
                      source=None, cover_url=None):
    with _conn() as c:
        c.execute("""
            INSERT INTO manga_history
            (manga_id, chapter_id, chapter_num, title, marked_at, source, cover_url)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(manga_id, chapter_id) DO UPDATE SET
                marked_at = excluded.marked_at,
                source    = COALESCE(excluded.source, source),
                cover_url = COALESCE(excluded.cover_url, cover_url)
        """, (manga_id, chapter_id, chapter_num, title,
              datetime.now().isoformat(), source, cover_url))


def get_continue_reading(limit=20):
    """Most recently read manga, one row each, with last chapter info."""
    with _conn() as c:
        rows = c.execute("""
            SELECT manga_id, title, chapter_num, source, cover_url,
                   MAX(marked_at) as marked_at
            FROM manga_history
            GROUP BY manga_id
            ORDER BY marked_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_read_chapters(manga_id) -> set:
    with _conn() as c:
        rows = c.execute(
            "SELECT chapter_id FROM manga_history WHERE manga_id=?", (manga_id,)
        ).fetchall()
    return {r["chapter_id"] for r in rows}


def unmark_chapter_read(manga_id, chapter_id):
    with _conn() as c:
        c.execute("DELETE FROM manga_history WHERE manga_id=? AND chapter_id=?",
                  (manga_id, chapter_id))


def is_chapter_read(manga_id, chapter_id) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM manga_history WHERE manga_id=? AND chapter_id=?",
            (manga_id, chapter_id)
        ).fetchone()
    return row is not None
