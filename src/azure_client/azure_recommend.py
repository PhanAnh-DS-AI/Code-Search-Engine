import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from typing import List
from src.azure_client.config import search_client
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RepoDoc(BaseModel):
    title: Optional[str]
    short_des: Optional[str]
    tags: Optional[List[str]]
    date: Optional[str]
    stars: Optional[int]
    owner: Optional[str]
    url: Optional[str]
    id: Optional[int]
    score: Optional[float]

class RecommendationResponse(BaseModel):
    trending: List[RepoDoc]
    popular: List[RepoDoc]
    topics: Dict[str, List[RepoDoc]]
    suggested_filters: List[str]
    limit: int

# --- Search logic ---

def search_with_sort(top: int, sort_fields: List[str]) -> List[RepoDoc]:
    try:
        # Compose order_by string for Azure Search
        order_by = [f"{field} desc" for field in sort_fields]
        # print(f"[DEBUG] order_by: {order_by}")

        results = list(search_client.search(search_text="*", top=top, order_by=order_by))
        # print(f"[DEBUG] Raw results from Azure Search:")
        # for doc in results:
        #     print(doc)

        docs = [RepoDoc(**doc) for doc in results]
        
        logger.info(f"[search_with_sort] Retrieved {len(docs)} documents (sorted in Azure Search).")
        for doc in docs:
            # print(f"[DEBUG] RepoDoc: {doc.model_dump()}")
            stars = doc.stars if doc.stars is not None else "N/A"
            logger.info(f"  -> {doc.title} | stars: {stars}")
        return docs
    except Exception as e:
        import traceback
        logger.error(f"Error in search_with_sort: {e}")
        print("[DEBUG] Exception occurred in search_with_sort:")
        traceback.print_exc()
        return []

def search_with_sort_and_date_filter(top: int, from_date: str, sort_fields: List[str]) -> List[RepoDoc]:
    try:
        filter_expr = f"date ge {from_date}"
        order_by = [f"{field} desc" for field in sort_fields]
        logger.info(f"[search_with_sort_and_date_filter] filter_expr = {filter_expr}, order_by = {order_by}")
        results = search_client.search(search_text="*", filter=filter_expr, top=top, order_by=order_by)
        docs = [RepoDoc(**doc) for doc in results]
        logger.info(f"[search_with_sort_and_date_filter] Retrieved {len(docs)} results (sorted in Azure Search)")
        for doc in docs:
            stars = doc.stars if doc.stars is not None else "N/A"
            logger.info(f"  -> {doc.title} | stars: {stars} | date: {doc.date}")
        return docs
    except Exception as e:
        logger.error(f"Error in search_with_sort_and_date_filter: {e}")
        return []


def search_by_tag(tag: str, top: int) -> List[RepoDoc]:
    try:
        filter_expr = f"tags/any(t: t eq '{tag}')"
        order_by = ["stars desc"]
        results = search_client.search(search_text="*", top=top, filter=filter_expr, order_by=order_by)
        docs = [RepoDoc(**doc) for doc in results]
        logger.info(f"[search_by_tag] Tag '{tag}': found {len(docs)} documents (sorted in Azure Search).")
        for doc in docs:
            stars = doc.stars if doc.stars is not None else "N/A"
            logger.info(f"  -> {doc.title} | stars: {stars} | score: {doc.score}")
        return docs
    except Exception as e:
        logger.error(f"Error in search_by_tag({tag}): {e}")
        return []


# --- Main function ---

def get_top_tags(size: int = 10) -> List[str]:
    try:
        results = search_client.search(search_text="*", facets=[f"tags,count:{size}"], top=0)
        facets = results.get_facets() if hasattr(results, 'get_facets') else None
        tags_facet = facets.get("tags", []) if facets else []
        return [item["value"] for item in tags_facet if item["value"] != "(none)"]
    except Exception as e:
        logger.error(f"Error retrieving top tags: {e}")
        return []


def get_recommendations(top: int = 10) -> Dict[str, Any]:
    try:
        trending = search_with_sort_and_date_filter(top, "2025-01-01T00:00:00Z", ["stars", "date"])
        popular = search_with_sort(top, ["stars"])

        topics = get_top_tags(size=3) or ["machine learning", "web3", "frontend"]
        topic_recs = {topic: search_by_tag(topic, top) for topic in topics}

        return {
            "trending": trending,
            "popular": popular,
            "topics": topic_recs
        }

    except Exception as e:
        logger.error(f"Error in get_recommendations: {e}")
        return {}


# =========== GET RECOMMENDATION HANDLER ===========

FALLBACK_TAGS = ["machine learning", "web3", "frontend", "blockchain", "deep learning"]

def handle_recommendations(limit: int = 25) -> Dict:
    try:
        logger.info(f"[handle_recommendations] Generating recommendations with limit={limit}")
        
        recommendations = get_recommendations(top=limit)
        
        suggested_filters = get_top_tags(size=10)
        if not suggested_filters:
            logger.warning("[handle_recommendations] Using fallback filters.")
            suggested_filters = FALLBACK_TAGS

        response = {
            "trending": [doc.model_dump() for doc in recommendations.get("trending", [])],
            "popular": [doc.model_dump() for doc in recommendations.get("popular", [])],
            "topics": {
                topic: [doc.model_dump() for doc in recs]
                for topic, recs in recommendations.get("topics", {}).items()
            },
            "suggested_filters": suggested_filters,
            "limit": limit
        }

        return response

    except Exception as e:
        logger.error(f"Error in handle_recommendations: {e}")
        return {
            "error": "Failed to get recommendations",
            "trending": [],
            "popular": [],
            "topics": {},
            "suggested_filters": FALLBACK_TAGS,
            "limit": limit
        }


if __name__ == "__main__":
    import pprint
    # recs = search_with_sort_and_date_filter( top=5, from_date="2025-01-01T00:00:00Z", sort_fields=["stars", "date"])
    # recs = search_with_sort(top=5,sort_fields=["stars"])
    recs = handle_recommendations(limit=10)
    pprint.pprint(f"Recommendations Response:{recs}")
    # topics = ["machine learning", "web3", "frontend"]
    # topic_recs = {}
    # for topic in topics:
    #     topic_recs[topic] = search_by_tag(topic, top=1)
    
    # pprint.pprint(topic_recs)