from src.cache.cache_client import BaseCache

# Create a cache instance for trending repositories
trending_cache = BaseCache()

def get_trending_repos(key: str, fallback_fn):
    """
    Get trending repositories from cache, or use fallback_fn to fetch and cache them.
    :param key: Cache key (e.g., "trending_daily", "trending_weekly")
    :param fallback_fn: Function to fetch data if cache miss
    :return: List of trending repositories
    """
    if trending_cache.has(key):
        print(f"Cache hit for trending: {key}")
        return trending_cache.get(key)
    print(f"Cache miss for trending: {key}. Querying DB...")
    repos = fallback_fn()
    trending_cache.set(key, repos)
    return repos