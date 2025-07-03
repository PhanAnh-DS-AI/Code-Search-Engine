from src.cache.cache_client import BaseCache

# Create a cache instance for popular repositories
popular_cache = BaseCache()

def get_popular_repos(key: str, fallback_fn):
    """
    Get popular repositories from cache, or use fallback_fn to fetch and cache them.
    :param key: Cache key (e.g., "popular_daily", "popular_weekly")
    :param fallback_fn: Function to fetch data if cache miss
    :return: List of popular repositories
    """
    if popular_cache.has(key):
        print(f"Cache hit for popular: {key}")
        return popular_cache.get(key)
    print(f"Cache miss for popular: {key}. Querying DB...")
    repos = fallback_fn()
    popular_cache.set(key, repos)
    return repos

def fetch_popular_repos():
    # Simulate fetching from DB or API
    return [
        {
            "title": "codex",
            "short_des": "Lightweight coding agent that runs in your terminal",
            "tags": ["(none)"],
            "date": "2025-04-13T00:00:00Z",
            "meta_data": {
                "stars": 27261,
                "owner": "openai",
                "url": "https://github.com/openai/codex",
                "id": 965415649
            },
            "score": 1
        },
        {
            "title": "open-r1",
            "short_des": "Fully open reproduction of DeepSeek-R1",
            "tags": ["(none)"],
            "date": "2025-01-24T00:00:00Z",
            "meta_data": {
                "stars": 24574,
                "owner": "huggingface",
                "url": "https://github.com/huggingface/open-r1",
                "id": 921777121
            },
            "score": 1
        },
        # ...add more mock repos as needed
    ]