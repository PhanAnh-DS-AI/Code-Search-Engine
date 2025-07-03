import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.qdrant.config import embedding_model
from typing import Union, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def embed_texts(texts: Union[str, List[str]], batch_size: int = 32) -> List[List[float]]:
    try:
        if isinstance(texts, str):
            texts = [texts]
        elif not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
            raise ValueError("Input must be a string or list of strings.")

        logger.info(f"Embedding {len(texts)} texts")
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = embedding_model.encode(batch, convert_to_numpy=True)
            embeddings.extend(batch_embeddings.tolist())
        return embeddings
    except Exception as e:
        logger.error(f"Error embedding texts: {str(e)}")
        raise

def embed_single_text(text: str) -> List[float]:
    return embed_texts(text)[0]

# Test
# if __name__ == "__main__":
#     sample_texts = ["hello world", "semantic search engine"]
#     embeddings = embed_texts(sample_texts)
#     print(embeddings)
