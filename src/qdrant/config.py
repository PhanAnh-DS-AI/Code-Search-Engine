import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME","data")
EMBEDDING_SIZE = 1024

# Create Client
qd_client = QdrantClient(
    url=QDRANT_URL, 
    api_key=QDRANT_API_KEY
)
collections = qd_client.get_collections()
# print("✅ Connected to Qdrant Cloud.")
# print("📦 Existing collections:", [c.name for c in collections.collections])

# Embedding model 
embedding_model = SentenceTransformer("BAAI/bge-large-en-v1.5")
print(embedding_model)

