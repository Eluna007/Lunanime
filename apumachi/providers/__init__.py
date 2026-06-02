from .allmanga_provider import AllMangaProvider

PROVIDERS = {
    "allmanga": AllMangaProvider,
}

def get_provider(name: str):
    return PROVIDERS[name]()

def list_provider_names():
    return list(PROVIDERS.keys())
