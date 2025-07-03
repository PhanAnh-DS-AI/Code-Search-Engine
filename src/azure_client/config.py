import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from sentence_transformers import SentenceTransformer
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
load_dotenv()

search_endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
search_key = os.getenv("AZURE_AI_SEARCH_KEY")
index_name = os.getenv("AZURE_AI_SEARCH_INDEX")
index_github = os.getenv("AZURE_AI_SEARCH_GITHUB")

# Search Client

search_client = SearchClient(
    endpoint=search_endpoint,
    index_name=index_name,
    credential=AzureKeyCredential(search_key),
    api_version="2024-11-01-Preview"
)

index_search_field = SearchIndexClient(
    endpoint = search_endpoint,
    credential = AzureKeyCredential(search_key),
)

# Github example client

github_ex_client = SearchClient(
    endpoint=search_endpoint,
    index_name=index_github,
    credential=AzureKeyCredential(search_key),
    api_version="2024-11-01-Preview"
)

model = SentenceTransformer("BAAI/bge-small-en-v1.5")
EMBEDDING_SIZE=384



