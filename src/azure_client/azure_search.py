import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.llm.llm_helpers import llm_preprocess, query_generate_related
from src.llm.utils import filter_results
from src.azure_client.boosted_score import sort_results_by_boosted_score
from src.azure_client.config import index_search_field, index_name,  search_client, model
from src.cache.cache_client import text_search_cache, hybrid_search_cache
from src.cache.utils import *
from azure.search.documents.models import VectorizedQuery
from typing import List
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def normalize_query(query: str) -> str:
    query = query.strip().lower()
    return re.sub(r'\s+', ' ', query) 

def get_field_index(exclude: List[str] = ["vector", "id"]) -> List[str]:
    index = index_search_field.get_index(name=index_name)
    exclude_set = set(exclude)
    return [
        f.name for f in index.fields
        if getattr(f, "retrievable", True) and f.name not in exclude_set
    ]

# # ======== FULL TEXT SEARCH ========
def full_text_search(query: str, top_k: int = 50):
    # _, parse_query = llm_preprocess(query)
    # print(f"Parsed query: {parse_query}")

    # final_query = parse_query.get("rewritten_query") or query
    results = search_client.search(
        search_text=query, 
        top=top_k,
        select= get_field_index()
        )
    results_return = []

    for result in results:
         results_return.append(result)

    return results_return

## ======== FULL TEXT SEARCH WITH CACHE ========
def text_search_with_semantic_cache(query, cache, top_k=50, threshold=0.8):
    """
    Perform text search with semantic cache.
    If cache hit, return cached result. If miss, query DB and cache the result.
    """
    _, llm_result = llm_preprocess(query)
    rewritten_query = llm_result.get("rewritten_query") or query
    intent_str, query_vector, reasoning = get_intent_and_vector(rewritten_query)
    result = find_in_cache(query_vector, cache, threshold=threshold)
    logger.info(f"Checking result in cache: {result}")

    if result is not None:
        cached_result, sim = result
    else:
        cached_result, sim = None, None

    logger.info(f"Similarity score: {sim}")
    logger.info(f"Cache result: {cached_result}")

    if cached_result:
        print("Cache hit!")
        return cached_result
    else:
        print("Cache miss. Querying DB...")
        results = search_client.search(
            search_text=query, 
            top=top_k,
            select= get_field_index()
            )
        results_return = []

        for result in results:
            results_return.append(result)
            
        cache[query_vector] = results_return
        
        # # Debug cache info after adding
        # try:
        #     num_repos = len(results_return)
        # except Exception:
        #     try:
        #         num_repos = len(list(results_return))
        #     except Exception:
        #         num_repos = "unknown"
        # print(
        #     f"Key (intent vector, first 5 dims) AFTER CACHE MISS: {query_vector[:5]}... | length: {len(query_vector)} | Num repos: {num_repos}")
        
        # # DEbug total repos in cache
        # print("\n===== DEBUG: TOTAL REPOS IN CACHE AFTER CACHE MISS ======")
        # total_repos = 0
        # for v in cache.values():
        #     try:
        #         total_repos += len(v)
        #     except Exception:
        #         try:
        #             total_repos += len(list(v))
        #         except Exception:
        #             pass
        # print(f"Total repos in all cache values: {total_repos}")
        
        return results_return


def vector_search(query: str, top_k: int = 50):
    vector_embedding = model.encode(query).tolist()
    vector_query = VectorizedQuery(
        vector=vector_embedding,                  
        k_nearest_neighbors=top_k,      
        fields="vector"
    )

    results = search_client.search(
        search_text=None,
        vector_queries=[vector_query],
        top=top_k,
        select=get_field_index()
    )
    results_return = []

    for result in results:
         results_return.append(result)
    return results_return


def hybrid_search(query: str, top_k: int = 50):
    query = normalize_query(query)
    _, parse_query = llm_preprocess(query)

    search_text_rewritten = parse_query.get("rewritten_query") or query
    filters = parse_query.get("filters", {})
    topics = filters.get("topics", [])
    query_vector_required = parse_query.get("query_vector_required", True)

    if query_vector_required:
        vector_embedding = model.encode(search_text_rewritten).tolist()
        # Hybrid Search function
        vector_query = VectorizedQuery(
            vector=vector_embedding,
            k_nearest_neighbors=top_k,
            fields="vector"
        )

        results = search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            top=top_k,
            select=get_field_index()
        )
        results = list(results)  # Convert from iterator
    else:
        results = full_text_search(search_text_rewritten)
        if not results:
            vector_results = vector_search(search_text_rewritten)
            if vector_results and vector_results[0].get("@search.score", 0) >= 0.5:
                results = vector_results
            else:
                logger.info("No result found.")
                return None

    filtered_results = filter_results(results, filters)
    ranked_results = sort_results_by_boosted_score(filtered_results)

    try:
        _, related_queries_obj = query_generate_related(query)
        suggest_filters = related_queries_obj.related_queries
    except Exception as e:
        logger.warning(f"Failed to generate related queries: {e}")
        suggest_filters = []

    # Debug 
    # from  pprint import pprint
    # print(f"Parsed query: {parse_query}")
    # pprint(f"Filter Result: {filtered_results}")
    # pprint(f"Suggest filters: {suggest_filters}")
    # pprint(f"Suggest Topics: {topics}")

    return {
        "result": ranked_results,
        "suggest_filter": suggest_filters,
        "suggest_topic": topics
    }

def hybrid_search_with_semantic_cache(query, cache, top_k=50, threshold=0.8):
    query = normalize_query(query)
    _, parse_query = llm_preprocess(query)
    rewritten_query = parse_query.get("rewritten_query") or query
    intent_str, query_vector, reasoning = get_intent_and_vector(rewritten_query)
    filters = parse_query.get("filters", {})
    topics = filters.get("topics", [])
    query_vector_required = parse_query.get("query_vector_required", True)
    
    if query_vector_required:
        result = find_in_cache(query_vector, cache, threshold=threshold)
        logger.info(f"Checking result in cache: {result}")

        if result is not None:
            cached_result, sim = result
        else:
            cached_result, sim = None, None

        logger.info(f"Similarity score: {sim}")
        logger.info(f"Cache result: {cached_result}")

        if cached_result:
            print("Cache hit!")
            return cached_result
        else:
            print("Cache miss. Querying DB...")
    
    pass

def search_by_tag(tag: str, top_k: int = 50) -> list[dict]:
    """s
    Search for repositories that contain an exact tag match.

    Args:
        tag (str): The tag to search for (must match exactly).
        top_k (int): Max number of results to return.

    Returns:
        List of matching documents.
    """
    # Use OData filter to match tag exactly in the collection
    filter_expr = f"tags/any(t: t eq '{tag}')"

    results = search_client.search(
        search_text="",  # empty disables full-text search
        filter=filter_expr,
        top=top_k
    )
    results_unranked = [doc for doc in results]
    ranked_results = sort_results_by_boosted_score(results_unranked)

    return ranked_results

if __name__ == "__main__":
    from pprint import pprint

    query_1 = "Azure AI search engine with python and pytorch more than 100 stars in 2024"
    query_2 = "Machine Learning with Azure AI"
    query_3 = "JavaScript libraries for data visualization"
    print("\n--- First run ---")
    result_1 = text_search_with_semantic_cache(query_1, text_search_cache.cache, top_k= 5)
    pprint(result_1)

    print("\n--- Second run ---")
    result_2 = text_search_with_semantic_cache(query_3, text_search_cache.cache, top_k= 5)
    pprint(result_2)



    # print("\n🧠 Vector Search:")
    # print(vector_search(user_query))
    # from  pprint import pprint

    # pprint("\n🔁 Hybrid Search:")
    # pprint(hybrid_search(user_query, top_k=1))

    # name = get_field_index()
    # print(name)
    
