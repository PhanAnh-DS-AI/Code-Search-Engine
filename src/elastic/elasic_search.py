import sys
import os
import re
import logging
from elasticsearch import Elasticsearch
from dotenv import load_dotenv 

# ===== Load env and setup path ===== #
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
load_dotenv()

from src.elastic.config import es_client 
from src.qdrant.config import COLLECTION_NAME  
from src.elastic.schema import SearchResult, SearchTextResponse 

# ===== Logging setup ===== #
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def normalize_query(query: str) -> str:
    """Clean and normalize query for search."""
    query = query.strip().lower()
    return re.sub(r'\s+', ' ', query)

def es_text_search(query: str, limit: int = 5) -> SearchTextResponse:
    """Perform full-text search on Elasticsearch index."""
    if not es_client.indices.exists(index=COLLECTION_NAME):
        logger.error(f"Elasticsearch index '{COLLECTION_NAME}' does not exist.")
        return []

    normalized_query = normalize_query(query)

    try:
        response = es_client.search(
            index=COLLECTION_NAME,
            size=limit,
            query={
                "multi_match": {
                    "query": normalized_query,
                    "fields": ["repo_name^3", "description^2", "tags"],
                    "fuzziness": "AUTO"
                }
            },
            highlight={
                "fields": {
                    "repo_name": {},
                    "description": {},
                    "tags": {}
                }
            }
        )

        hits = response.get("hits", {}).get("hits", [])
        results = []

        for hit in hits:
            source = hit.get("_source", {})
            # print("DEBUG SOURCE:", json.dumps(source, indent=2))  
            result = SearchResult(
                score=hit.get("_score"),
                title=source.get("title"),
                short_des=source.get("short_des"),
                tags=source.get("tags", []),
                date=source.get("date"),
                meta_data=source.get("meta_data"), 
                highlight=hit.get("highlight", {})
            )
            results.append(result)

        logger.info(f"[Full-text Search] Found {len(results)} results for query: '{query}'")
        return results

    except Exception as e:
        logger.exception(f"Failed to search query: {query}")
        return []


def search_repos_by_tag(tag_query: str, limit: int = 5) -> SearchTextResponse:
    try:
        response = es_client.search(
            index=COLLECTION_NAME,
            size=limit,
            query={
                "match": {
                    "tags": {
                        "query": tag_query,
                        "operator": "and"
                    }
                }
            }
        )

        results = []
        hits = response.get("hits", {}).get("hits", [])
        for hit in hits:
            source = hit.get("_source", {})
            result = SearchResult(
                score=hit.get("_score"),
                title=source.get("title"),
                short_des=source.get("short_des"),
                tags=source.get("tags", []),
                date=source.get("date"),
                meta_data=source.get("meta_data")
            )
            results.append(result)

        logger.info(f"[Tag Search] Found {len(results)} results for tag: '{tag_query}'")
        return results

    except Exception as e:
        logger.exception(f"Error in tag search: {e}")
        return []

def get_top_repos_by_stars(limit: int = 10) -> SearchTextResponse:
    try:
        response = es_client.search(
            index=COLLECTION_NAME,
            size=limit,
            sort=[
                {"meta_data.stars": {"order": "desc"}}
            ],
            _source_includes=["title", "short_des", "tags", "date", "meta_data"]
        )

        hits = response.get("hits", {}).get("hits", [])
        results = []

        for hit in hits:
            source = hit.get("_source", {})
            result = SearchResult(
                score=hit.get("_score"),
                title=source.get("title"),
                short_des=source.get("short_des"),
                tags=source.get("tags", []),
                date=source.get("date"),
                meta_data=source.get("meta_data")
            )
            results.append(result)

        logger.info(f"[Top Stars] Retrieved top {len(results)} repos by stars")
        return results

    except Exception as e:
        logger.exception(f"[Elastic] Error in get_top_repos_by_stars: {str(e)}")
        return []

# if __name__ == "__main__":
#     # response = es_text_search(query="Tensorflow")
#     # tag_query = search_repos_by_tag(query="Tensorflow")
    # print("=== Top Repos by Stars ===")
    # top_starred = get_top_repos_by_stars()
    # for repo in top_starred:
    #     print(f"{repo}")
