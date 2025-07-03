import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import logging
from typing import List, Dict, Any
from src.qdrant.config import qd_client, COLLECTION_NAME, EMBEDDING_SIZE
from src.qdrant.push_data import load_data, push_points
from src.qdrant.qdrant_search import search_query, full_text_search, hybrid_search_func, get_data_from_collection


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QdrantClientWrapper:
    def __init__(
        self,
        client=qd_client,
        collection_name: str = COLLECTION_NAME,
        embedding_size: int = EMBEDDING_SIZE
    ):
        self.client = client
        self.collection_name = collection_name
        self.embedding_size = embedding_size

    def create_collection(self) -> None:
        """Create the collection with payload index for text field."""
        try:
            if self.client.collection_exists(self.collection_name):
                logger.info(f"Collection '{self.collection_name}' already exists.")
            else:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={"size": self.embedding_size, "distance": "Cosine"}
                )
                # Create payload index for text field
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="text",
                    field_schema="text" 
                )
                logger.info(f"Collection '{self.collection_name}' created with text index.")
        except Exception as e:
            logger.error(f"Error creating collection: {str(e)}")
            raise

    def recreate_collection(self, confirm: bool = False) -> None:
        """Delete and recreate the collection with confirmation."""
        if not confirm:
            logger.warning("Recreate collection requires confirmation. Set confirm=True.")
            return
        try:
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config={"size": self.embedding_size, "distance": "Cosine"}
            )
            # Recreate payload index for text field
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="text",
                field_schema="text" 
            )
            logger.info(f"Collection '{self.collection_name}' recreated with text index.")
        except Exception as e:
            logger.error(f"Error recreating collection: {str(e)}")
            raise

    def load_and_push_data(self, data_path: str, encoding: str = "utf-8") -> None:
        try:
            data = load_data(data_path, encoding)
            if data:
                push_points(data)
            else:
                logger.warning("No data loaded to push.")
        except Exception as e:
            logger.error(f"Error in load_and_push_data: {str(e)}")
            raise

    def search_vector(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            return search_query(query, limit)
        except Exception as e:
            logger.error(f"Error in search: {str(e)}")
            return []
        
    def text_search(self, query:str, limit:int = 5) -> List[Dict[str,Any]]:
        try:
            return full_text_search(query, limit)
        except Exception as e:
            logger.error(f"Error in search: {str(e)}")
            return []

    def hybrid_search(self, query: str, limit: int = 5, alpha: float = 0.5) -> List[Dict[str, Any]]:
        try:
            return hybrid_search_func(query, limit=limit, alpha=alpha)
        except Exception as e:
            logger.error(f"Error in hybrid_search: {str(e)}")
            return []

    def get_collection_info(self) -> Dict[str, Any]:
        try:
            points, _ = qd_client.scroll(collection_name=COLLECTION_NAME, limit=10, with_payload=True)
            for point in points:
                print(point.payload)
            return get_data_from_collection()
        except Exception as e:
            logger.error(f"Error getting collection info: {str(e)}")
            return {}