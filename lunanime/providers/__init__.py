from .allmanga_provider import AllMangaProvider
from .animepahe_provider import AnimePaheProvider

PROVIDERS = {
    "allmanga": AllMangaProvider,
    "animepahe": AnimePaheProvider,
}

def get_provider(name: str):
    return PROVIDERS[name]()

def list_provider_names():
    return list(PROVIDERS.keys())
