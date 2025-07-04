import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import logging
from azure.cosmos import CosmosClient, PartitionKey
from src.data.github_client import GithubClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = "your_db"
CONTAINER_NAME = "your_container"

def push_to_cosmosdb(docs):
    client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    db = client.create_database_if_not_exists(DATABASE_NAME)
    container = db.create_container_if_not_exists(
        id=CONTAINER_NAME,
        partition_key=PartitionKey(path="/id"),
    )
    for doc in docs:
        try:
            container.upsert_item(doc)
            logger.info(f"✅ Inserted repo {doc['title']}")
        except Exception as e:
            logger.error(f"❌ Failed to insert: {e}")

if __name__ == "__main__":
    # github_client = GithubClient()
    # repos = github_client.search_diverse_repos(max_repos=1000)
    # docs = []
    # for repo in repos:
    #     doc = {
    #         "id": str(repo.id),
    #         "full_name": repo.full_name,
    #         "description": repo.description,
    #         "stargazers_count": repo.stargazers_count,
    #         "language": repo.language,
    #         "topics": repo.get_topics(),
    #         "html_url": repo.html_url,
    #         "created_at": str(repo.created_at),
    #         "updated_at": str(repo.updated_at),
    #     }
    #     docs.append(doc)
    # push_to_cosmosdb(docs)
    client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    db = client.create_database_if_not_exists(DATABASE_NAME)
    container = db.create_container_if_not_exists(
        id=CONTAINER_NAME,
        partition_key=PartitionKey(path="/id"),
    )

    # Tạo một document mẫu
    sample_doc = {
        "id": "test123",
        "title": "Hello CosmosDB",
        "short_des": "Đây là document test",
        "tags": ["test", "cosmosdb"],
        "date": "2024-07-04",
        "meta_data": {
            "stars": 42,
            "owner": "tester",
            "url": "https://github.com/tester/hello-cosmosdb",
            "id": 123456
        },
        "score": 0.0
    }

    try:
        container.upsert_item(sample_doc)
        print("✅ Đã push document mẫu lên Cosmos DB!")
    except Exception as e:
        print(f"❌ Lỗi khi push: {e}")