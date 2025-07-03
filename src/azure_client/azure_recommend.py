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


# --- Pydantic models ---

class MetaData(BaseModel):
    stars: Optional[int]
    owner: Optional[str]
    url: Optional[str]
    id: Optional[int]

class RepoDoc(BaseModel):
    title: Optional[str]
    short_des: Optional[str]
    tags: Optional[List[str]]
    date: Optional[str]
    meta_data: Optional[MetaData]
    score: Optional[float]

class RecommendationResponse(BaseModel):
    trending: List[RepoDoc]
    popular: List[RepoDoc]
    topics: Dict[str, List[RepoDoc]]
    suggested_filters: List[str]
    limit: int

# --- Helper functions ---

def flatten_metadata(doc: dict) -> dict:
    new_doc = dict(doc)
    meta = doc.get("meta_data", {})
    if isinstance(meta, dict):
        new_doc["meta_data"] = {
            "stars": meta.get("stars", 0),
            "owner": meta.get("owner", ""),
            "url": meta.get("url", ""),
            "id": meta.get("id", None)
        }
    new_doc["score"] = doc.get("@search.score", 0.0)
    return new_doc  

# --- Search logic ---

# def search_with_sort(top: int, sort_fields: List[str]) -> List[RepoDoc]:
#     try:
#         results = search_client.search(search_text="*", top=4500)
#         docs = [RepoDoc(**flatten_metadata(doc)) for doc in results]

#         logger.info(f"[search_with_sort] Retrieved {len(docs)} documents before sorting.")

#         for field in reversed(sort_fields):
#             docs.sort(key=lambda x: getattr(x, field, 0) or 0, reverse=True)

#         for doc in docs[:top]:
#             stars = doc.meta_data.stars if doc.meta_data and doc.meta_data.stars is not None else "N/A"
#             logger.info(f"  -> {doc.title} | stars: {stars}")

#         return docs[:top]
#     except Exception as e:
#         logger.error(f"Error in search_with_sort: {e}")
#         return []

def search_with_sort(top: int, sort_fields: List[str]) -> List[RepoDoc]:
    try:
        results = search_client.search(search_text="*")
        docs = [RepoDoc(**flatten_metadata(doc)) for doc in results]

        logger.info(f"[search_with_sort] Retrieved {len(docs)} documents before sorting.")

        for field in reversed(sort_fields):
            if field == "stars":
                docs.sort(key=lambda x: (x.meta_data.stars if x.meta_data and x.meta_data.stars is not None else 0), reverse=True)
            else:
                docs.sort(key=lambda x: getattr(x, field, 0) or 0, reverse=True)

        for doc in docs[:top]:
            stars = doc.meta_data.stars if doc.meta_data and doc.meta_data.stars is not None else "N/A"
            logger.info(f"  -> {doc.title} | stars: {stars}")

        return docs[:top]
    except Exception as e:
        logger.error(f"Error in search_with_sort: {e}")
        return []
    

def search_with_sort_and_date_filter(top: int, from_date: str, sort_fields: List[str]) -> List[RepoDoc]:
    try:
        filter_expr = f"date ge {from_date}"
        logger.info(f"[search_with_sort_and_date_filter] filter_expr = {filter_expr}, Type = {type(filter_expr)}")

        results = search_client.search(search_text="*", filter=filter_expr)
        docs = [RepoDoc(**flatten_metadata(doc)) for doc in results]

        logger.info(f"[search_with_sort_and_date_filter] Retrieved {len(docs)} results")

        for field in reversed(sort_fields):
            if field == "stars":
                docs.sort(key=lambda x: (x.meta_data.stars if x.meta_data and x.meta_data.stars is not None else 0), reverse=True)
            else:
                docs.sort(key=lambda x: getattr(x, field, 0) or 0, reverse=True)

        for doc in docs[:top]:
            stars = doc.meta_data.stars if doc.meta_data and doc.meta_data.stars is not None else "N/A"
            logger.info(f"  -> {doc.title} | stars: {stars} | date: {doc.date}")

        return docs[:top]

    except Exception as e:
        logger.error(f"Error in search_with_sort_and_date_filter: {e}")
        return []


def search_by_tag(tag: str, top: int) -> List[RepoDoc]:
    try:
        filter_expr = f"tags/any(t: t eq '{tag}')"
        results = search_client.search(search_text="*", top=top, filter=filter_expr)

        docs = [RepoDoc(**flatten_metadata(doc)) for doc in results]

        logger.info(f"[search_by_tag] Tag '{tag}': found {len(docs)} documents.")
        for doc in docs:
            stars = doc.meta_data.stars if doc.meta_data and doc.meta_data.stars is not None else "N/A"
            logger.info(f"  -> {doc.title} | stars: {stars} | score: {doc.score}")

        return docs

    except Exception as e:
        logger.error(f"Error in search_by_tag({tag}): {e}")
        return []


# --- Main function ---

def get_top_tags(size: int = 10) -> List[str]:
    try:
        results = search_client.search(search_text="*", facets=[f"tags,count:{size}"], top=0)
        tags_facet = results.get_facets().get("tags", [])
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
    recs = handle_recommendations(limit=1)
    pprint.pprint(recs)
    # topics = ["machine learning", "web3", "frontend"]
    # topic_recs = {}
    # for topic in topics:
    #     topic_recs[topic] = search_by_tag(topic, top=1)
    
    # pprint.pprint(topic_recs)