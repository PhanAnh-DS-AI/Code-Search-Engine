from cachetools import TTLCache
import math

DEFAULT_TTL = 900  # 15 mins

class BaseCache:
    def __init__(self, ttl: int = DEFAULT_TTL):
        self.cache = TTLCache(maxsize=math.inf, ttl=ttl)

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache[key] = value

    def has(self, key):
        return key in self.cache

    def clear(self):
        self.cache.clear()

text_search_cache = BaseCache()
hybrid_search_cache = BaseCache()