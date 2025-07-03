import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from cachetools import TTLCache, TLRUCache
from typing import List
from src.cache.cache_client import BaseCache
from typing import Callable, List
from src.azure_client.azure_search import normalize_query, get_field_index
from src.llm.llm_helpers import llm_preprocess
from src.azure_client.config import search_client, model
from azure.search.documents.models import VectorizedQuery
from datetime import datetime, timedelta
# Create repo cache

topic_cache = BaseCache()

def get_topic_repo_id(topic:str, fallback_fn) -> List[str]:
    
    if topic in topic_cache:
        print(f"Cache hit for topic {topic}")
        return topic_cache[topic]
    
    print(f"Cache miss for topic: {topic}. Querying DB...")
    repo_ids = fallback_fn(topic)  
    topic_cache[topic] = repo_ids
    return repo_ids

def query_cosmosdb_by_topic(topic: str, top_k: int = 100) -> List[str]:
    filter_expr = f"tags/any(t: t eq '{topic}')"
    results = search_client.search(search_text="", filter=filter_expr, top=top_k)
    return [r["rid"] for r in results]


def hybrid_search_with_filter(query: str, top_k: int = 50, filter_str:str = None) -> List[dict]:

    query = normalize_query(query)
    _, parse_query = llm_preprocess(query)

    rewrite_query = parse_query.get("rewritten_query") or query
    filters = parse_query.get("filters", {})
    topics = filters.get("topics", [])

    vector_embedding = model.encode(rewrite_query).tolist()
    vector_query = VectorizedQuery(
        vector=vector_embedding,                  
        k_nearest_neighbors=top_k,      
        weight= 0.7,
        fields="vector"
    )

    results = search_client.search(
        search_text=None,
        vector_queries=[vector_query],
        filter=filter_str,
        top=top_k,
        select=get_field_index()
    )
    
    results = list(results)  
    
    return {"results":results,
            "topics":topics
            }


def recommend_with_cache_and_vector(query: str, topic: str, top_k: int = 10):
    repo_ids = get_topic_repo_id(topic, fallback_fn=query_cosmosdb_by_topic)

    print(f"Debug Repos ID {repo_ids}")

    if not repo_ids:
        print("No repo found for topic.")
        return []

    # Chuyển list repo_ids thành filter string cho Azure Search
    filter_str = " or ".join([f"rid eq '{rid}'" for rid in repo_ids])

    print(f"Debug filter_str {filter_str}")

    return hybrid_search_with_filter(query, top_k=top_k, filter_str=filter_str)


if __name__ == "__main__":
    import pprint
    query = "Azure AI Search engine, with python and pytorch more than 100 stars in 2024"
    topic = "ai"

    # results = recommend_with_cache_and_vector(query, topic, top_k=5)
    testing = query_cosmosdb_by_topic(topic=topic, top_k= 5)
    pprint.pprint(testing)