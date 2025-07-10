import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import logging
import json
import time
import pickle
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from github import Github, GithubException
from src.data.schema import RepoDoc, MetaData
from tqdm import tqdm
from src.llm.llm_helpers import llm_generate_shortdes
from src.azure_client.config import model

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
        
        # Progress bar for queries
        with tqdm(total=len(queries), desc="🔍 Processing queries", unit="query") as pbar:
            for query in queries:
                logger.info(f"🔍 Searching query: {query}")
                page = 0
                uery_repos = 0
                    
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
                        query_repos += 1
                    if len(all_repos) >= max_repos:
                        logger.info(f"✅ Collected {max_repos} unique repos.")
                        pbar.update(1)
                        return all_repos

                page += 1
                if page >= 10:
                    logger.info(f"⏭️  Reached max page limit for query '{query}'")
                    break
                
                pbar.set_postfix({"repos": query_repos, "total": len(all_repos)})
                pbar.update(1)
                
        logger.info(f"✅ Finished. Total unique repos collected: {len(all_repos)}")
        return all_repos

    def _convert_single_repo(self, repo):
        """
        Convert a single repository to RepoDoc schema format
        """
        try:
            # Create MetaData object using Pydantic
            meta_data = MetaData(
                stars=repo.stargazers_count,
                owner=repo.owner.login,
                url=str(repo.html_url) if repo.html_url else "",
                id=repo.id
            )
            
            # Get description - use LLM-generated if not available
            description = repo.description
            if not description or description.strip() == "":
                logger.debug(f"🤖 Generating description for {repo.full_name}")
                try:
                    # Get README content for better description generation
                    readme_content = ""
                    try:
                        readme = repo.get_readme()
                        readme_content = readme.decoded_content.decode(encoding="utf-8")
                    except:
                        pass  # No README available
                    
                    description = llm_generate_shortdes(
                        repo_name=repo.full_name,
                        repo_topics=repo.get_topics(),
                        repo_readme=readme_content
                    )
                    logger.debug(f"✅ Generated description: {description[:50]}...")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to generate description for {repo.full_name}: {e}")
                    description = f"Repository: {repo.full_name}"
            
            # Generate embedding for vector search
            try:
                # Create text for embedding (combine title, description, and topics)
                embedding_text = f"{repo.full_name} {description}"
                if repo.get_topics():
                    embedding_text += f" {' '.join(repo.get_topics())}"
                
                # Generate embedding using the model
                embedding = model.encode(embedding_text).tolist()
                logger.debug(f"📊 Generated embedding for {repo.full_name} (dim: {len(embedding)})")
            except Exception as e:
                logger.warning(f"⚠️ Failed to generate embedding for {repo.full_name}: {e}")
                embedding = []  # Empty embedding as fallback
            
            # Create RepoDoc object using Pydantic
            repo_doc = RepoDoc(
                title=repo.full_name,  # Use full_name as title
                short_des=description,  # Use description or generated description
                tags=repo.get_topics(),  # Use topics as tags
                date=str(repo.created_at),  # Use created_at as date
                meta_data=meta_data,
                score=0.0,  # Default score
                vector=embedding  # Add embedding vector
            )
            
            return repo_doc, None
            
        except Exception as e:
            logger.error(f"❌ Failed to convert repo {repo.full_name}: {e}")
            return None, str(e)

    def convert_repos_to_schema(self, repos, batch_size=10, max_workers=4, resume_file=None):
        """
        Convert GitHub repository objects to RepoDoc schema format using Pydantic
        with batch processing and resume functionality
        
        Args:
            repos: List of GitHub repository objects
            batch_size: Number of repos to process in each batch
            max_workers: Maximum number of concurrent workers
            resume_file: Path to resume file for checkpointing
        """
        repo_docs = []
        processed_ids = set()
        
        # Load resume state if file exists
        if resume_file and Path(resume_file).exists():
            try:
                with open(resume_file, 'rb') as f:
                    resume_data = pickle.load(f)
                    repo_docs = resume_data.get('repo_docs', [])
                    processed_ids = set(resume_data.get('processed_ids', []))
                logger.info(f"🔄 Resuming from checkpoint: {len(repo_docs)} repos already processed")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load resume file: {e}")
        
        # Filter out already processed repos
        remaining_repos = [repo for repo in repos if repo.id not in processed_ids]
        logger.info(f"📊 Processing {len(remaining_repos)} remaining repos out of {len(repos)} total")
        
        if not remaining_repos:
            logger.info("✅ All repos already processed!")
            return repo_docs
        
        # Process in batches
        total_batches = (len(remaining_repos) + batch_size - 1) // batch_size
        
        with tqdm(total=len(remaining_repos), desc="🔄 Converting to schema", unit="repo") as pbar:
            for batch_idx in range(0, len(remaining_repos), batch_size):
                batch = remaining_repos[batch_idx:batch_idx + batch_size]
                batch_num = batch_idx // batch_size + 1
                
                logger.info(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} repos)")
                
                # Process batch with ThreadPoolExecutor for parallel processing
                batch_results = []
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all tasks in the batch
                    future_to_repo = {executor.submit(self._convert_single_repo, repo): repo for repo in batch}
                    
                    # Collect results as they complete
                    for future in as_completed(future_to_repo):
                        repo = future_to_repo[future]
                        try:
                            repo_doc, error = future.result()
                            if repo_doc:
                                batch_results.append(repo_doc)
                                processed_ids.add(repo.id)
                                logger.debug(f"✅ Converted: {repo.full_name}")
                            else:
                                logger.warning(f"❌ Failed to convert {repo.full_name}: {error}")
                        except Exception as e:
                            logger.error(f"❌ Exception processing {repo.full_name}: {e}")
                        
                        pbar.update(1)
                        pbar.set_postfix({
                            "batch": f"{batch_num}/{total_batches}",
                            "converted": len(repo_docs) + len(batch_results),
                            "total_processed": len(processed_ids)
                        })
                
                # Add batch results to main list
                repo_docs.extend(batch_results)
                
                # Save checkpoint after each batch
                if resume_file:
                    try:
                        checkpoint_data = {
                            'repo_docs': repo_docs,
                            'processed_ids': list(processed_ids),
                            'total_repos': len(repos),
                            'batch_num': batch_num,
                            'total_batches': total_batches
                        }
                        with open(resume_file, 'wb') as f:
                            pickle.dump(checkpoint_data, f)
                        logger.debug(f"💾 Saved checkpoint after batch {batch_num}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to save checkpoint: {e}")
                
                # Add small delay between batches to avoid rate limiting
                time.sleep(1)
        
        logger.info(f"✅ Conversion complete! Processed {len(repo_docs)} repos successfully")
        return repo_docs

    def convert_repos_to_schema_simple(self, repos):
        """
        Simple version of convert_repos_to_schema for backward compatibility
        """
        return self.convert_repos_to_schema(repos, batch_size=1, max_workers=1)

if __name__ == "__main__":
    # github_client = GithubClient()
    # repos = github_client.search_diverse_repos(max_repos=5000)
    # print(f"Total unique repos collected: {len(repos)}")
    
    # # Example: print first 5 repo names
    # for repo in repos[:5]:
    #     print(f"{repo.full_name} | ⭐ {repo.stargazers_count}")

    # # Convert to schema format with batch processing and resume capability
    # resume_file = "./mock_data/conversion_checkpoint.pkl"
    # repo_docs = github_client.convert_repos_to_schema(
    #     repos, 
    #     batch_size=20,  # Process 20 repos per batch
    #     max_workers=4,  # Use 4 concurrent workers
    #     resume_file=resume_file
    # )
    # print(f"✅ Converted {len(repo_docs)} repos to schema format")
    
    # # Save as JSON in schema format using Pydantic's model_dump()
    # repo_dicts = [doc.model_dump() for doc in repo_docs]
    # with open("./mock_data/github_repos_schema.json", "w", encoding="utf-8") as f:
    #     json.dump(repo_dicts, f, ensure_ascii=False, indent=2)
    # print("✅ Saved to github_repos_schema.json")
    
    # # Clean up checkpoint file after successful completion
    # if Path(resume_file).exists():
    #     Path(resume_file).unlink()
    #     print("🧹 Cleaned up checkpoint file")
    
    # from azure.cosmos import CosmosClient
    # from src.data.push_azure_cosmosdb import COSMOS_ENDPOINT, COSMOS_KEY, DATABASE_NAME, CONTAINER_NAME
    
    # # Check if environment variables are set
    # if not COSMOS_ENDPOINT or not COSMOS_KEY:
    #     print("❌ COSMOS_ENDPOINT and COSMOS_KEY environment variables are required")
    #     exit(1)
    
    # try:
    #     # Initialize client with proper credential handling
    #     cosmos_endpoint = str(COSMOS_ENDPOINT)
    #     cosmos_key = str(COSMOS_KEY)
        
    #     client = CosmosClient(cosmos_endpoint, cosmos_key)
    #     database = client.get_database_client(DATABASE_NAME)
    #     container = database.get_container_client(CONTAINER_NAME)

    #     # Count documents
    #     query = "SELECT VALUE COUNT(1) FROM c"
    #     count = list(container.query_items(query=query, enable_cross_partition_query=True))[0]

    #     print(f"✅ Total items in container: {count}")
        
    # except Exception as e:
    #     print(f"❌ Error connecting to CosmosDB: {e}")
    #     print("Please check your COSMOS_ENDPOINT and COSMOS_KEY environment variables")