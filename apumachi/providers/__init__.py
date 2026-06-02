from .allmanga_provider import AllMangaProvider
from .animepahe_provider import AnimePaheProvider
from .gogoanime_provider import GogoAnimeProvider

PROVIDERS = {
    "allmanga": AllMangaProvider,
    "animepahe": AnimePaheProvider,
    "gogoanime": GogoAnimeProvider,
}

def get_provider(name: str):
    return PROVIDERS[name]()

def list_provider_names():
    return list(PROVIDERS.keys())
