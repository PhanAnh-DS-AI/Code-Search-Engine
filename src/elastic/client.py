import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import logging
from dotenv import load_dotenv
from typing import List, Dict, Any
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError
from src.elastic.elasic_search import es_text_search, search_repos_by_tag, get_top_repos_by_stars, SearchTextResponse

load_dotenv()

ES_CLOUD_ID = os.getenv("ES_CLOUD_ID")
ES_USER = os.getenv("ES_USER")
ES_PASSWORD = os.getenv("ES_PASSWORD")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ElasticClient:
    def __init__(self):
        self.client = None
        self.connect()

    def connect(self):
        try:
            self.client = Elasticsearch(
                cloud_id=ES_CLOUD_ID,
                basic_auth=(ES_USER, ES_PASSWORD),
                request_timeout=30,
            )
            if not self.client.ping():
                raise ConnectionError("Elasticsearch cluster is not responding.")
            logger.info("[Elastic] Connection established.")
        except Exception as e:
            logger.exception(f"[Elastic] Failed to connect: {e}")
            raise

    def get_client(self) -> Elasticsearch:
        return self.client

    def index_exists(self, index_name: str) -> bool:
        return self.client.indices.exists(index=index_name)

    def text_search(self, query: str, limit:int = 5) -> List[Dict[str, Any]]:
        try:
            return es_text_search(query, limit)
        except Exception as e:
            logger.error(f"Error in search: {str(e)}")
            return []
    
    def tag_search(self, query: str, limit:int = 5) -> List[Dict[str, Any]]:
        try:
            return search_repos_by_tag(query, limit)
        except Exception as e:
            logger.error(f"Error in search: {str(e)}")
            return []
        
    def list_top_repo(self, limit:int = 10) -> SearchTextResponse:
        try:
            return get_top_repos_by_stars(limit)
        except Exception as e:
            logger.error(f"Error: {str(e)}")

# if __name__ == "__main__":
#     es_client = ElasticClient()
#     # query = "I Love AI"
#     # response =  es_client.text_search(query,)
#     response = es_client.get_top_repos_by_stars()
#     print(response)
