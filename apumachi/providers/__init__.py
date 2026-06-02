from .allmanga_provider import AllMangaProvider
from .kickassanime_provider import KickAssAnimeProvider
from .animeunity_provider import AnimeUnityProvider

PROVIDERS = {
    "allmanga": AllMangaProvider,
    "kickassanime": KickAssAnimeProvider,
    "animeunity": AnimeUnityProvider,
}

def get_provider(name: str):
    return PROVIDERS[name]()

def list_provider_names():
    return list(PROVIDERS.keys())
