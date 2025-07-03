import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from typing import List, Dict, Any
from src.qdrant.config import qdrant_client, COLLECTION_NAME
from src.qdrant.embedding_vec import embed_texts
from qdrant_client.models import MatchText, FieldCondition, Filter
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def normalize_query(query: str) -> str:
    query = query.strip().lower()
    return re.sub(r'\s+', ' ', query) 


def search_query(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    if not qdrant_client.collection_exists(COLLECTION_NAME):
        logger.error(f"Collection {COLLECTION_NAME} does not exist")
    normalized_query = normalize_query(query)
    try:
        query_vec = embed_texts([normalized_query])[0]  
        hits = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vec,
            limit=limit
        )
        logger.info(f"Search completed for query: {query}")
        return [{"score": hit.score, "payload": hit.payload} for hit in hits]
    except Exception as e:
        logger.error(f"Error during search: {str(e)}")
        return []

def full_text_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    if not qdrant_client.collection_exists(COLLECTION_NAME):
        logger.error(f"Collection {COLLECTION_NAME} does not exist")
        return []
    normalized_query = normalize_query(query)
    try:
        text_filter = Filter(
            must=[FieldCondition(key="text", match=MatchText(text=normalized_query))]
        )
        scroll_result, _ = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=text_filter,
            limit=limit,
            with_vectors=False,
            with_payload=True
        )
        results = [{"score": 1.0, "payload": point.payload} for point in scroll_result]
        # logger.info(f"Full text search completed for query: {query}")
        # logger.debug(f"Scroll result: {results}")

        return results
    except Exception as e:
        logger.error(f"Error during full text search: {str(e)}")
        return []


def hybrid_search(query: str, limit: int = 5, alpha: float = 0.5) -> List[Dict[str, Any]]:
   
    vector_results = search_query(query, limit=limit * 2)  
    text_results = full_text_search(query, limit=limit * 2)

    def get_key(r):
        return r["payload"].get("id") or r["payload"].get("url") or str(r["payload"])

    combined = {}

    for r in vector_results:
        key = get_key(r)
        combined[key] = {
            "payload": r["payload"],
            "score_vector": r["score"],
            "score_text": 0.0
        }

    for r in text_results:
        key = get_key(r)
        if key in combined:
            combined[key]["score_text"] = r["score"]
        else:
            combined[key] = {
                "payload": r["payload"],
                "score_vector": 0.0,
                "score_text": r["score"]
            }

    hybrid_results = []
    for v in combined.values():
        score_hybrid = alpha * v["score_vector"] + (1 - alpha) * v["score_text"]
        hybrid_results.append({
            "payload": v["payload"],
            "score": score_hybrid
        })

    hybrid_results.sort(key=lambda x: x["score"], reverse=True)
    return hybrid_results[:limit]
    
def get_data_from_collection() -> Dict[str, Any]:
    try:
        info = qdrant_client.get_collection(collection_name=COLLECTION_NAME)
        return vars(info)
    except Exception as e:
        logger.error(f"Error getting collection info: {str(e)}")
        return {}

# Test
# if __name__ == "__main__":
#     query = "search engine"
#     results = full_text_search(query)
#     for r in results:
#         print(f"Score: {r['score']}\nPayload: {r['payload']}\n")

    # get_data_from_collection()
