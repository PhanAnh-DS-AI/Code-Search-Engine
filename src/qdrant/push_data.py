import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import json
import uuid
from typing import List, Dict, Any, Optional
from qdrant_client.models import PointStruct
from src.qdrant.config import qdrant_client, COLLECTION_NAME
from src.qdrant.embedding_vec import embed_texts
import logging

logger = logging.getLogger(__name__)

def load_data(data_path: str, encoding: str = "utf-8") -> Optional[List[Dict[str, Any]]]:
    if not isinstance(data_path, str):
        raise TypeError("data_path must be a string.")
    try:
        if data_path.endswith(".json"):
            with open(data_path, encoding=encoding) as f:
                return json.load(f)
        else:
            raise ValueError("File must be in JSON format")
    except FileNotFoundError:
        logger.error(f"File {data_path} not found")
        return None
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in {data_path}")
        return None
            


def flatten_data(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    docs = []
    for repo in raw_data:
        for branch in repo["branches"]:
            docs.append({
                "repository": repo["repository"],
                "branch_name": branch["branch_name"],
                "tags": branch["tags"],
                "last_commit": branch["last_commit"],
                "author": branch["author"],
                "created_at": branch["created_at"],
                "text": f"{repo['repository']} {branch['branch_name']} {' '.join(branch['tags'])} {branch['author']}"
            })
    return docs


def push_points(data: List[Dict[str, Any]]) -> None:
    if not data:
        logger.info("No data to push.")
        return

    # check collection exist
    if not qdrant_client.collection_exists(COLLECTION_NAME):
        logger.error(f"Collection '{COLLECTION_NAME}' does not exist")
        raise ValueError(f"Collection '{COLLECTION_NAME}' does not exist")

    docs = flatten_data(data)
    texts = [doc["text"] for doc in docs]
    embeddings = embed_texts(texts)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),  
            vector=embedding,  
            payload=doc
        )
        for embedding, doc in zip(embeddings, docs)
    ]
    try:
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        logger.info(f"Upserted {len(points)} points to collection '{COLLECTION_NAME}'")
    except Exception as e:
        logger.error(f"Error upserting points: {str(e)}")
        raise

# Testing
# if __name__ == "__main__":
#     data = load_data(data_path="mock_data/gitdata.json")
#     push_points(data)