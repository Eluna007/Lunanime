"""
AniList and MAL tracking clients.

AniList  — OAuth Authorization Code + GraphQL  (requires client_id + client_secret)
MAL      — OAuth PKCE + REST v2               (requires client_id only)

Tokens are stored in the local SQLite DB via lunanime.db helpers.
"""
import hashlib
import os
import secrets
import base64
import webbrowser
import datetime
import requests

from .auth import redirect_uri, get_oauth_code
from . import db as _db


# ── AniList ───────────────────────────────────────────────────────────────────

ANILIST_GQL = "https://graphql.anilist.co"
ANILIST_AUTH_URL = "https://anilist.co/api/v2/oauth/authorize"
ANILIST_TOKEN_URL = "https://anilist.co/api/v2/oauth/token"

_AL_VIEWER_Q = "{ Viewer { id name } }"
_AL_SEARCH_Q = """
query ($title: String) {
  Page(perPage: 5) {
    media(search: $title, type: ANIME, sort: SEARCH_MATCH) {
      id title { romaji english }
    }
  }
}
"""
_AL_UPDATE_M = """
mutation ($mediaId: Int, $progress: Int) {
  SaveMediaListEntry(mediaId: $mediaId, progress: $progress, status: CURRENT) { id }
}
"""


def anilist_connect(client_id: str, client_secret: str) -> dict | None:
    """Open browser → local callback → exchange code → return token dict."""
    url = (
        f"{ANILIST_AUTH_URL}?client_id={client_id}"
        f"&redirect_uri={redirect_uri('anilist')}"
        f"&response_type=code"
    )
    webbrowser.open(url)
    code = get_oauth_code("anilist", timeout=180)
    if not code:
        return None

    resp = requests.post(ANILIST_TOKEN_URL, json={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri("anilist"),
        "code": code,
    }, timeout=15)
    resp.raise_for_status()
    token_data = resp.json()
    access_token = token_data["access_token"]

    # Fetch username
    viewer = _al_gql(_AL_VIEWER_Q, {}, access_token)
    username = viewer["data"]["Viewer"]["name"]
    user_id  = str(viewer["data"]["Viewer"]["id"])

    # AniList tokens don't expire (no expiry field)
    _db.save_oauth_token("anilist", access_token,
                         refresh_token=None, expires_at=None,
                         username=username, user_id=user_id)
    return {"username": username}


def anilist_disconnect():
    _db.delete_oauth_token("anilist")


def anilist_status() -> dict | None:
    return _db.get_oauth_token("anilist")


def anilist_sync(title: str, episode: int,
                 provider: str = None, identifier: str = None):
    """Find anime on AniList by title and update progress. Silent on failure."""
    token_row = _db.get_oauth_token("anilist")
    if not token_row:
        return
    token = token_row["access_token"]

    # Try cached ID first
    al_id = _db.get_tracking_id(provider, identifier, "anilist") if provider else None

    if al_id is None:
        results = _al_gql(_AL_SEARCH_Q, {"title": title}, token)
        media = results["data"]["Page"]["media"]
        if not media:
            return
        al_id = media[0]["id"]
        if provider and identifier:
            _db.save_tracking_id(provider, identifier, anilist_id=al_id)

    _al_gql(_AL_UPDATE_M, {"mediaId": al_id, "progress": episode}, token)


def _al_gql(query: str, variables: dict, token: str) -> dict:
    resp = requests.post(
        ANILIST_GQL,
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ── MyAnimeList (PKCE) ────────────────────────────────────────────────────────

MAL_AUTH_URL  = "https://myanimelist.net/v1/oauth2/authorize"
MAL_TOKEN_URL = "https://myanimelist.net/v1/oauth2/token"
MAL_API       = "https://api.myanimelist.net/v2"


def _pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def mal_connect(client_id: str) -> dict | None:
    """Open browser → local callback → exchange code (PKCE) → return token dict."""
    verifier, challenge = _pkce_pair()
    state = secrets.token_hex(8)

    url = (
        f"{MAL_AUTH_URL}?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri('mal')}"
        f"&code_challenge={challenge}"
        f"&code_challenge_method=S256"
        f"&state={state}"
    )
    webbrowser.open(url)
    code = get_oauth_code("mal", timeout=180)
    if not code:
        return None

    resp = requests.post(MAL_TOKEN_URL, data={
        "client_id": client_id,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri("mal"),
        "code_verifier": verifier,
    }, timeout=15)
    resp.raise_for_status()
    token_data = resp.json()

    access_token  = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_in    = token_data.get("expires_in", 2592000)  # 30 days default
    expires_at    = (datetime.datetime.utcnow() +
                     datetime.timedelta(seconds=expires_in)).isoformat()

    user = _mal_get("/users/@me", access_token)
    username = user.get("name", "")
    user_id  = str(user.get("id", ""))

    _db.save_oauth_token("mal", access_token, refresh_token, expires_at, username, user_id)
    # Store client_id so we can refresh later
    _db.save_setting("mal_client_id", client_id)
    return {"username": username}


def mal_disconnect():
    _db.delete_oauth_token("mal")


def mal_status() -> dict | None:
    return _db.get_oauth_token("mal")


def mal_sync(title: str, episode: int,
             provider: str = None, identifier: str = None):
    """Find anime on MAL by title and update progress. Silent on failure."""
    token_row = _db.get_oauth_token("mal")
    if not token_row:
        return
    token = _mal_ensure_token(token_row)
    if not token:
        return

    mal_id = _db.get_tracking_id(provider, identifier, "mal") if provider else None

    if mal_id is None:
        data = _mal_get(f"/anime?q={requests.utils.quote(title)}&limit=5&fields=id,title",
                        token)
        items = data.get("data", [])
        if not items:
            return
        mal_id = items[0]["node"]["id"]
        if provider and identifier:
            _db.save_tracking_id(provider, identifier, mal_id=mal_id)

    _mal_patch(f"/anime/{mal_id}/my_list_status", token, {
        "status": "watching",
        "num_watched_episodes": episode,
    })


def _mal_ensure_token(token_row: dict) -> str | None:
    """Refresh MAL token if expired, return valid access_token or None."""
    if token_row.get("expires_at"):
        try:
            exp = datetime.datetime.fromisoformat(token_row["expires_at"])
            if datetime.datetime.utcnow() < exp - datetime.timedelta(hours=1):
                return token_row["access_token"]
        except ValueError:
            pass

    # Refresh
    client_id = _db.get_setting("mal_client_id")
    if not client_id or not token_row.get("refresh_token"):
        return None
    try:
        resp = requests.post(MAL_TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": token_row["refresh_token"],
            "client_id": client_id,
        }, timeout=15)
        resp.raise_for_status()
        td = resp.json()
        expires_at = (datetime.datetime.utcnow() +
                      datetime.timedelta(seconds=td.get("expires_in", 2592000))).isoformat()
        _db.save_oauth_token("mal", td["access_token"], td.get("refresh_token"),
                             expires_at, token_row.get("username"), token_row.get("user_id"))
        return td["access_token"]
    except Exception:
        return None


def _mal_get(path: str, token: str) -> dict:
    resp = requests.get(f"{MAL_API}{path}",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=15)
    resp.raise_for_status()
    return resp.json()


def _mal_patch(path: str, token: str, data: dict):
    resp = requests.patch(f"{MAL_API}{path}",
                          headers={"Authorization": f"Bearer {token}"},
                          data=data, timeout=15)
    resp.raise_for_status()
