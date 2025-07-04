from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
import logging

from src.data.github_client import GithubClient
from src.qdrant.config import qd_client
from src.data.data_utils import collect_repo_data_and_store_many, sync_qdrant_to_elasticsearch
from src.data.schema import RepoDoc, MetaData

app = FastAPI()
logger = logging.getLogger(__name__)

COLLECTION_NAME = "your_collection_name"

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.data.fetch_data:app", host="0.0.0.0", port=8000, reload=True)

def safe_string(val):
    return val if val else "(unknown)"

def safe_int(val):
    return int(val) if val is not None else 0

def safe_list(val):
    return val if val else ["(none)"]

def collect_repo_data_and_store_many(collection_name, qd_client, repos, embed_func=None, extra_store_func=None):
    """
    - repos: list các object repo (PyGithub)
    - embed_func: hàm nhận text và trả về vector embedding (nếu có)
    - extra_store_func: hàm lưu thêm (ví dụ lưu lên CosmosDB hoặc Elasticsearch), nhận (collection_name, doc, repo_id)
    """
    for repo in repos:
        try:
            name = getattr(repo, "name", None)
            description = getattr(repo, "description", "") or ""
            owner = getattr(repo.owner, "login", None)
            repo_id = getattr(repo, "id", None)
            stars = getattr(repo, "stargazers_count", 0)
            url = getattr(repo, "html_url", "")
            created_at = getattr(repo, "created_at", None)
            topics = []
            if hasattr(repo, "get_topics"):
                try:
                    topics = repo.get_topics()
                except Exception as e:
                    logger.warning(f"⚠️ Failed to fetch topics for {owner}/{name}: {e}")

            if not all([name, owner, repo_id, created_at]):
                logger.warning(f"⚠️ Skipping incomplete repo: {name}")
                continue

            text = f"{name} {description}"
            vector = embed_func(text) if embed_func else None

            meta = MetaData(
                stars=int(stars),
                owner=owner,
                url=url,
                id=int(repo_id)
            )
            doc = RepoDoc(
                title=name,
                short_des=description,
                tags=topics if topics else [],
                date=str(created_at.date()) if created_at else "",
                meta_data=meta,
                score=0.0
            )
            payload = doc.to_dict()

            # Lưu vào Qdrant
            if vector is not None:
                qd_client.upsert_vector(collection_name, str(repo_id), vector, payload)
            else:
                qd_client.upsert_payload(collection_name, str(repo_id), payload)
            logger.info(f"✅ Repo '{name}' inserted into Qdrant")

            # Lưu thêm vào CosmosDB hoặc nơi khác nếu cần
            if extra_store_func:
                extra_store_func(collection_name, payload, str(repo_id))

        except Exception as e:
            logger.error(f"❌ Error processing repo: {e}")

def sync_qdrant_to_cosmosdb(collection_name, qd_client, cosmosdb_func):
    """
    - cosmosdb_func: hàm nhận (collection_name, doc, repo_id) để lưu lên CosmosDB
    """
    points = qd_client.scroll_all_points(collection_name, 1000)
    for payload in points:
        meta = payload.get("meta_data", {})
        repo_id = str(meta.get("id", ""))
        doc = {
            "title": payload.get("title", ""),
            "short_des": payload.get("short_des", ""),
            "tags": payload.get("tags", []),
            "date": payload.get("date", ""),
            "meta_data": meta,
        }
        try:
            cosmosdb_func(collection_name, doc, repo_id)
            logger.info(f"✅ Synced repo ID {repo_id} from Qdrant to CosmosDB")
        except Exception as e:
            logger.warning(f"⚠️ Failed to sync repo ID {repo_id} to CosmosDB: {e}")