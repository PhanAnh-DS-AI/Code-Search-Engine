import os
import logging
import json
from github import Github, GithubException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GithubClient: 
    def __init__(self):
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is not set.")
        self.client = Github(token)
        logger.info("GitHub client initialized.")

    def fetch_repo_details(self, owner: str, repo_name: str):
        try:
            repository = self.client.get_repo(f"{owner}/{repo_name}")
            return repository
        except GithubException as e:
            logger.error(f"Failed to fetch repository details: {e}")
            return None

    def fetch_repo_topics(self, owner: str, repo_name: str):
        try:
            repository = self.client.get_repo(f"{owner}/{repo_name}")
            topics = repository.get_topics()
            return topics
        except GithubException as e:
            logger.error(f"Error fetching repository topics: {e}")
            return None

    def fetch_repo_readme(self, owner: str, repo_name: str):
        try:
            repository = self.client.get_repo(f"{owner}/{repo_name}")
            readme = repository.get_readme()
            content = readme.decoded_content.decode(encoding="utf-8")
            return content
        except GithubException as e:
            logger.error(f"Error fetching repository README: {e}")
            return None

    def search_diverse_repos(self, max_repos=5000):
        queries = [
            # Push Data 1 - 716
            "stars:>1000",
            "stars:50..200",
            "stars:<50",
            "created:>2023-01-01",
            "language:go pushed:>2024-01-01",
            "language:python",
            "language:rust",
            "language:typescript",
            "language:cpp",
            "topic:web",
            "topic:cli",
            "topic:ai",
            "topic:game",
            "topic:education",
            # Push Data 717 - 1716
            "in:description \"trí tuệ nhân tạo\"",
            "in:readme \"mã nguồn mở\"",
            "language:go in:readme \"hướng dẫn\"",
            "topic:ai",
            "in:description NLP OR deep learning",
            "language:go stars:>50",
            # Push Data 1717 - 2716
            "language:go in:readme tiếng việt",
            "language:go in:description tiếng việt",
            "language:go in:readme \"hướng dẫn\"",
            "language:go in:readme \"mã nguồn\"",
            "language:go topic:vietnamese",
            "language:go in:description \"ứng dụng\"",
            "language:go topic:vn",
            # Push Data 2717 - 3716
            "topic:nextjs",
            "language:typescript topic:frontend",
            "language:javascript in:description \"responsive\"",
            # Push Data 3717 - 4716
            "qdrant in:readme",
            "qdrant topic:qdrant",
            "elasticsearch topic:elasticsearch",
            "elasticsearch in:readme",
            "vector search in:readme",
            "semantic search in:readme",
            "embedding search stars:>10",
            "pinecone vector database",
            "weaviate topic:weaviate",
            "milvus vector search",
            "retrieval augmented generation",
            "rag search in:description",
            "semantic ranking in:readme",
            "hybrid search topic:search",
        ]

        all_repos = []
        seen = set()
        for query in queries:
            logger.info(f"🔍 Searching query: {query}")
            page = 0
            while True:
                try:
                    results = self.client.search_repositories(query=query, sort="updated", order="desc")
                    repos = results.get_page(page)
                except GithubException as e:
                    logger.warning(f"⚠️  Search failed for query '{query}': {e}")
                    break

                if not repos:
                    logger.info(f"ℹ️  No more repos found for query '{query}'")
                    break

                for repo in repos:
                    if repo.id not in seen:
                        all_repos.append(repo)
                        seen.add(repo.id)
                    if len(all_repos) >= max_repos:
                        logger.info(f"✅ Collected {max_repos} unique repos.")
                        return all_repos

                page += 1
                if page >= 10:
                    logger.info(f"⏭️  Reached max page limit for query '{query}'")
                    break
        logger.info(f"✅ Finished. Total unique repos collected: {len(all_repos)}")
        return all_repos



if __name__ == "__main__":
    github_client = GithubClient()
    repos = github_client.search_diverse_repos(max_repos=5000)
    print(f"Total unique repos collected: {len(repos)}")
    # Example: print first 5 repo names
    for repo in repos[:5]:
        print(f"{repo.full_name} | ⭐ {repo.stargazers_count}")

    # Lưu ra file JSON
    repo_dicts = []
    for repo in repos:
        repo_dicts.append({
            "id": repo.id,
            "full_name": repo.full_name,
            "description": repo.description,
            "stargazers_count": repo.stargazers_count,
            "language": repo.language,
            "topics": repo.get_topics(),
            "html_url": repo.html_url,
            "created_at": str(repo.created_at),
            "updated_at": str(repo.updated_at),
        })
    with open("github_repos.json", "w", encoding="utf-8") as f:
        json.dump(repo_dicts, f, ensure_ascii=False, indent=2)
    print("✅ Saved to github_repos.json")