from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
import logging

from src.data.github_client import GithubClient
from src.qdrant.config import qd_client
from src.data.data_utils import collect_repo_data_and_store_many, sync_qdrant_to_elasticsearch

app = FastAPI()
logger = logging.getLogger(__name__)

COLLECTION_NAME = "your_collection_name"  # Đặt tên collection Qdrant của bạn ở đây

# Khởi tạo Qdrant client (giả sử bạn đã có class QdrantClient)

@app.post("/fetch-data")
async def fetch_data():
    try:
        github_client = GithubClient()
        logger.info("⏳ Fetching repos from GitHub...")
        repos = github_client.search_diverse_repos()
        logger.info(f"ℹ️ Found {len(repos)} repos.")
        collect_repo_data_and_store_many(COLLECTION_NAME, qd_client, repos)
        return PlainTextResponse("✅ Data fetched and stored into Qdrant and Elasticsearch.", status_code=200)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=f"❌ GitHub fetch/store error: {e}")

@app.post("/sync-qdrant-to-elasticsearch")
async def sync_qdrant_to_elasticsearch_api():
    try:
        logger.info("⏳ Starting sync from Qdrant to Elasticsearch...")
        sync_qdrant_to_elasticsearch(COLLECTION_NAME, qd_client)
        return PlainTextResponse("✅ Data synced from Qdrant to Elasticsearch successfully.", status_code=200)
    except Exception as e:
        logger.error(f"❌ Sync error: {e}")
        raise HTTPException(status_code=500, detail=f"❌ Sync error: {e}")

# Nếu muốn chạy file này trực tiếp:
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.fetch_api:app", host="0.0.0.0", port=8000, reload=True)