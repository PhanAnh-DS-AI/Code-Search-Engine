import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.azure_client.config import model
from src.llm.llm_helpers import agent_intent_query
from sklearn.metrics.pairwise import cosine_similarity
from src.cache.cache_client import text_search_cache
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)

def get_intent_and_vector(query):
    """
    Returns (intent_str, vector_tuple, reasoning) for a query.
    """
    intent_obj = agent_intent_query(query)
    if isinstance(intent_obj, dict):
        intent_str = intent_obj.get("intent", "")
        reasoning = intent_obj.get("reasoning", "")
    else:
        intent_str = str(intent_obj)
        reasoning = ""
    if not intent_str:
        raise ValueError("Intent string is empty or invalid!")
    vector = model.encode(intent_str)
    logger.info(f"Intent string: {intent_str}")
    logger.info(f"Intent vector for query '{query}': {vector[:5]}... (length: {len(vector)})")
    logger.info(f"LLM reasoning: {reasoning}")
    return intent_str, tuple(vector), reasoning


def find_in_cache(query_vector, cache, threshold=0.8):
    """
    Search for a cached result by cosine similarity.
    Prints debug info for all cache items and similarity scores.
    """
    import numpy as np
    query_vector_np = np.array(query_vector)
    print(f"\n===== DEBUG: SEMANTIC CACHE CONTENT =====")
    for key, value in cache.items():
        # Get TTL
        try:
            ttl_left = text_search_cache.cache.get_ttl(key)
        except Exception:
            ttl_left = None
        # Get number of repos safely
        try:
            num_repos = len(value)
        except Exception:
            try:
                num_repos = len(list(value))
            except Exception:
                num_repos = "unknown"
        # Print cache info
        ttl_info = f"TTL left: {ttl_left:.2f} seconds" if ttl_left is not None else "No TTL info"
        print(f"Key (intent vector, first 5 dims): {key[:5]}... | length: {len(key)} | Num repos: {num_repos} | {ttl_info}")
        # Print repo info if possible
        try:
            for repo in value:
                title = repo.get('title', '') if hasattr(repo, 'get') else getattr(repo, 'title', '')
                stars = repo.get('meta_data', {}).get('stars', 0) if hasattr(repo, 'get') else getattr(getattr(repo, 'meta_data', {}), 'get', lambda x, d=None: 0)('stars', 0)
                print(f"  - {title} | {stars} stars")
        except Exception:
            pass

    print(f"\nQuery vector (first 5): {query_vector_np[:5]}")
    for cached_vector, result in cache.items():
        cached_vector_np = np.array(cached_vector)
        logger.info(f"Comparing with cached vector (first 5): {cached_vector_np[:5]}")
        sim = cosine_similarity([query_vector_np], [cached_vector_np])[0][0]
        logger.info(f"Cosine similarity: {sim}")
        if sim > threshold:
            print("Cache HIT!")
            return result, sim
    print("Cache MISS!")
    return None