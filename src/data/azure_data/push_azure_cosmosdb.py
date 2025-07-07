import os
import sys
# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

import logging
from azure.cosmos import CosmosClient, PartitionKey
from src.data.github_client import GithubClient
from src.data.schema import RepoDoc, MetaData
from src.llm.llm_helpers import llm_generate_shortdes
from tqdm import tqdm
import json
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = "github-repositories"
CONTAINER_NAME = "github-container"
PROMPT_CONTAINER_NAME = "github-examples-prompt"

def push_to_cosmosdb(docs):
    """
    Push RepoDoc objects to CosmosDB
    """
    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        raise ValueError("COSMOS_ENDPOINT and COSMOS_KEY environment variables are required")
        
    # Ensure we have valid strings
    cosmos_endpoint = str(COSMOS_ENDPOINT)
    cosmos_key = str(COSMOS_KEY)
    
    client = CosmosClient(cosmos_endpoint, cosmos_key)
    db = client.create_database_if_not_exists(DATABASE_NAME)
    container = db.create_container_if_not_exists(
        id=CONTAINER_NAME,
        partition_key=PartitionKey(path="/id"),
    )
    
    success_count = 0
    error_count = 0
    
    # Progress bar for pushing to CosmosDB
    with tqdm(total=len(docs), desc="📤 Pushing to CosmosDB", unit="doc") as pbar:
        for doc in docs:
            try:
                # Convert RepoDoc to dictionary if it's not already
                if isinstance(doc, RepoDoc):
                    doc_dict = doc.model_dump()  # Use Pydantic's model_dump()
                else:
                    doc_dict = doc
                    
                container.upsert_item(doc_dict)
                success_count += 1
                pbar.set_postfix({"success": success_count, "errors": error_count})
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Failed to insert: {e}")
                pbar.set_postfix({"success": success_count, "errors": error_count})
            finally:
                pbar.update(1)
    
    logger.info(f"📊 Push completed: {success_count} successful, {error_count} failed")
    return success_count, error_count

def validate_json_file(json_file_path: str, preview_count: int = 3):
    """
    Validate and preview a JSON file before pushing to CosmosDB (new schema format only)
    
    Args:
        json_file_path (str): Path to the JSON file
        preview_count (int): Number of items to preview
    
    Returns:
        dict: Validation results
    """
    if not os.path.exists(json_file_path):
        return {"valid": False, "error": f"File not found: {json_file_path}"}
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            return {"valid": False, "error": "JSON file should contain a list of repositories"}
        
        if len(data) == 0:
            return {"valid": False, "error": "JSON file is empty"}
        
        # Validate schema format
        required_fields = ['title', 'short_des', 'tags', 'date', 'meta_data', 'vector']
        required_meta_fields = ['stars', 'owner', 'url', 'id']
        
        invalid_items = []
        preview_items = []
        
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                invalid_items.append(f"Item {i}: Not a dictionary")
                continue
            
            # Check required fields
            missing_fields = [field for field in required_fields if field not in item]
            if missing_fields:
                invalid_items.append(f"Item {i}: Missing fields {missing_fields}")
                continue
            
            # Check meta_data structure
            meta_data = item.get('meta_data', {})
            if not isinstance(meta_data, dict):
                invalid_items.append(f"Item {i}: meta_data is not a dictionary")
                continue
            
            missing_meta_fields = [field for field in required_meta_fields if field not in meta_data]
            if missing_meta_fields:
                invalid_items.append(f"Item {i}: Missing meta_data fields {missing_meta_fields}")
                continue
            
            # Add to preview if valid
            if i < preview_count:
                preview_items.append({
                    "index": i,
                    "title": item.get('title', 'Unknown'),
                    "stars": meta_data.get('stars', 0),
                    "owner": meta_data.get('owner', 'Unknown')
                })
        
        if invalid_items:
            return {
                "valid": False, 
                "error": f"Invalid schema format. Issues: {invalid_items[:3]}{'...' if len(invalid_items) > 3 else ''}"
            }
        
        return {
            "valid": True,
            "total_items": len(data),
            "preview": preview_items,
            "estimated_size_mb": len(json.dumps(data)) / (1024 * 1024)
        }
        
    except json.JSONDecodeError as e:
        return {"valid": False, "error": f"Invalid JSON format: {e}"}
    except Exception as e:
        return {"valid": False, "error": f"Error reading file: {e}"}

def push_from_json_file(json_file_path: str):
    """
    Push repositories to CosmosDB from a JSON file (new schema format only)
    
    Args:
        json_file_path (str): Path to the JSON file containing repository data
    """
    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        raise ValueError("COSMOS_ENDPOINT and COSMOS_KEY environment variables are required")
    
    # Check if JSON file exists
    if not os.path.exists(json_file_path):
        raise FileNotFoundError(f"JSON file not found: {json_file_path}")
    
    # Load JSON data
    logger.info(f"📂 Loading data from {json_file_path}")
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"✅ Loaded {len(data)} repositories from JSON file")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in {json_file_path}: {e}")
    except Exception as e:
        raise ValueError(f"Error reading JSON file {json_file_path}: {e}")
    
    # Ensure we have valid strings
    cosmos_endpoint = str(COSMOS_ENDPOINT)
    cosmos_key = str(COSMOS_KEY)
    
    client = CosmosClient(cosmos_endpoint, cosmos_key)
    db = client.create_database_if_not_exists(DATABASE_NAME)
    container = db.create_container_if_not_exists(
        id=CONTAINER_NAME,
        partition_key=PartitionKey(path="/id"),
    )

    success_count = 0
    error_count = 0
    
    # Progress bar for pushing to CosmosDB
    with tqdm(total=len(data), desc="📤 Pushing from JSON to CosmosDB", unit="doc") as pbar:
        for item in data:
            try:
                # Validate that item is in the correct schema format
                if not isinstance(item, dict):
                    logger.warning(f"⚠️ Skipping non-dict item: {type(item)}")
                    error_count += 1
                    pbar.update(1)
                    continue
                
                # Check for required schema fields
                required_fields = ['title', 'short_des', 'tags', 'date', 'meta_data', 'vector']
                missing_fields = [field for field in required_fields if field not in item]
                
                if missing_fields:
                    logger.warning(f"⚠️ Skipping item missing required fields: {missing_fields}")
                    error_count += 1
                    pbar.update(1)
                    continue
                
                # Validate meta_data structure
                meta_data = item.get('meta_data', {})
                required_meta_fields = ['stars', 'owner', 'url', 'id']
                missing_meta_fields = [field for field in required_meta_fields if field not in meta_data]
                
                if missing_meta_fields:
                    logger.warning(f"⚠️ Skipping item with invalid meta_data: {missing_meta_fields}")
                    error_count += 1
                    pbar.update(1)
                    continue
                
                # Push to CosmosDB
                container.upsert_item(item)
                success_count += 1
                pbar.set_postfix({"success": success_count, "errors": error_count})
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Failed to insert item: {e}")
                pbar.set_postfix({"success": success_count, "errors": error_count})
            finally:
                pbar.update(1)
    
    logger.info(f"📊 Push from JSON completed: {success_count} successful, {error_count} failed")
    return success_count, error_count

def fetch_and_push_repos(max_repos=1000):
    """
    Fetch repositories from GitHub and push to CosmosDB
    """
    try:
        # Fetch repositories
        github_client = GithubClient()
        repos = github_client.search_diverse_repos(max_repos=max_repos)
        logger.info(f"🔍 Fetched {len(repos)} repositories from GitHub")
        
        # Convert to schema format
        repo_docs = github_client.convert_repos_to_schema(repos)
        logger.info(f"🔄 Converted {len(repo_docs)} repositories to schema format")
        
        # Push to CosmosDB
        success, errors = push_to_cosmosdb(repo_docs)
        logger.info(f"📤 Push result: {success} successful, {errors} failed")
        
        return success, errors
        
    except Exception as e:
        logger.error(f"❌ Error in fetch_and_push_repos: {e}")
        return 0, 0

def push_query_metadata_to_cosmosdb(json_file_path: str):
    """
    Push GitHub query metadata to CosmosDB in the github-examples-prompt container
    
    Args:
        json_file_path (str): Path to the JSON file containing query metadata
    """
    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        raise ValueError("COSMOS_ENDPOINT and COSMOS_KEY environment variables are required")
    
    # Check if JSON file exists
    if not os.path.exists(json_file_path):
        raise FileNotFoundError(f"JSON file not found: {json_file_path}")
    
    # Load JSON data
    logger.info(f"📂 Loading query metadata from {json_file_path}")
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"✅ Loaded {len(data)} query examples from JSON file")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in {json_file_path}: {e}")
    except Exception as e:
        raise ValueError(f"Error reading JSON file {json_file_path}: {e}")
    
    # Validate data structure
    if not isinstance(data, list):
        raise ValueError("JSON file should contain a list of query examples")
    
    if len(data) == 0:
        raise ValueError("JSON file is empty")
    
    # Validate each item has required fields
    required_fields = ['id', 'original_query', 'rewritten_query', 'llm_output', 'true_label']
    invalid_items = []
    
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            invalid_items.append(f"Item {i}: Not a dictionary")
            continue
        
        missing_fields = [field for field in required_fields if field not in item]
        if missing_fields:
            invalid_items.append(f"Item {i}: Missing fields {missing_fields}")
            continue
    
    if invalid_items:
        logger.warning(f"⚠️ Found {len(invalid_items)} invalid items: {invalid_items[:3]}{'...' if len(invalid_items) > 3 else ''}")
    
    # Ensure we have valid strings
    cosmos_endpoint = str(COSMOS_ENDPOINT)
    cosmos_key = str(COSMOS_KEY)
    
    client = CosmosClient(cosmos_endpoint, cosmos_key)
    db = client.create_database_if_not_exists(DATABASE_NAME)
    container = db.create_container_if_not_exists(
        id=PROMPT_CONTAINER_NAME,
        partition_key=PartitionKey(path="/id"),
    )

    success_count = 0
    error_count = 0
    
    # Progress bar for pushing to CosmosDB
    with tqdm(total=len(data), desc="📤 Pushing query metadata to CosmosDB", unit="doc") as pbar:
        for item in data:
            try:
                # Validate that item is a dictionary
                if not isinstance(item, dict):
                    logger.warning(f"⚠️ Skipping non-dict item: {type(item)}")
                    error_count += 1
                    pbar.update(1)
                    continue
                
                # Check for required fields
                missing_fields = [field for field in required_fields if field not in item]
                if missing_fields:
                    logger.warning(f"⚠️ Skipping item missing required fields: {missing_fields}")
                    error_count += 1
                    pbar.update(1)
                    continue
                
                # Push to CosmosDB
                container.upsert_item(item)
                success_count += 1
                pbar.set_postfix({"success": success_count, "errors": error_count})
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Failed to insert item: {e}")
                pbar.set_postfix({"success": success_count, "errors": error_count})
            finally:
                pbar.update(1)
    
    logger.info(f"📊 Query metadata push completed: {success_count} successful, {error_count} failed")
    return success_count, error_count

def validate_query_metadata_file(json_file_path: str, preview_count: int = 3):
    """
    Validate and preview a JSON file containing query metadata before pushing to CosmosDB
    
    Args:
        json_file_path (str): Path to the JSON file
        preview_count (int): Number of items to preview
    
    Returns:
        dict: Validation results
    """
    if not os.path.exists(json_file_path):
        return {"valid": False, "error": f"File not found: {json_file_path}"}
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            return {"valid": False, "error": "JSON file should contain a list of query examples"}
        
        if len(data) == 0:
            return {"valid": False, "error": "JSON file is empty"}
        
        # Validate schema format for query metadata
        required_fields = ['id', 'original_query', 'rewritten_query', 'llm_output', 'true_label']
        
        invalid_items = []
        preview_items = []
        
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                invalid_items.append(f"Item {i}: Not a dictionary")
                continue
            
            # Check required fields
            missing_fields = [field for field in required_fields if field not in item]
            if missing_fields:
                invalid_items.append(f"Item {i}: Missing fields {missing_fields}")
                continue
            
            # Add to preview if valid
            if i < preview_count:
                preview_items.append({
                    "index": i,
                    "id": item.get('id', 'Unknown'),
                    "original_query": item.get('original_query', 'Unknown')[:50] + "..." if len(item.get('original_query', '')) > 50 else item.get('original_query', 'Unknown'),
                    "rewritten_query": item.get('rewritten_query', 'Unknown')[:50] + "..." if len(item.get('rewritten_query', '')) > 50 else item.get('rewritten_query', 'Unknown'),
                    "true_label": item.get('true_label', False)
                })
        
        if invalid_items:
            return {
                "valid": False, 
                "error": f"Invalid query metadata format. Issues: {invalid_items[:3]}{'...' if len(invalid_items) > 3 else ''}"
            }
        
        return {
            "valid": True,
            "total_items": len(data),
            "preview": preview_items,
            "estimated_size_mb": len(json.dumps(data)) / (1024 * 1024)
        }
        
    except json.JSONDecodeError as e:
        return {"valid": False, "error": f"Invalid JSON format: {e}"}
    except Exception as e:
        return {"valid": False, "error": f"Error reading file: {e}"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Push GitHub repositories to CosmosDB")
    parser.add_argument("--mode", choices=["fetch", "json", "query"], default="fetch", 
                       help="Mode: 'fetch' to get data from GitHub, 'json' to push from JSON file, 'query' to push query metadata")
    parser.add_argument("--json-file", type=str, default="github_repos_schema.json",
                       help="Path to JSON file (used with --mode json or query)")
    parser.add_argument("--max-repos", type=int, default=100,
                       help="Maximum number of repositories to fetch (used with --mode fetch)")
    
    args = parser.parse_args()
    
    print("🚀 Starting GitHub to CosmosDB pipeline...")
    
    if args.mode == "fetch":
        # Option 1: Fetch and push repositories from GitHub
        print(f"📥 Fetching up to {args.max_repos} repositories from GitHub...")
        success, errors = fetch_and_push_repos(max_repos=args.max_repos)
        print(f"📊 Pipeline completed: {success} successful, {errors} failed")
        
    elif args.mode == "json":
        # Option 2: Push from JSON file
        print(f"📂 Pushing from JSON file: {args.json_file}")
        
        # Validate JSON file first
        print("🔍 Validating JSON file...")
        validation = validate_json_file(args.json_file)
        
        if not validation["valid"]:
            print(f"❌ Validation failed: {validation['error']}")
            sys.exit(1)
        
        print(f"✅ Validation passed!")
        print(f"📊 Total items: {validation['total_items']}")
        print(f"📏 Estimated size: {validation['estimated_size_mb']:.2f} MB")
        print("📋 Preview:")
        for item in validation['preview']:
            if 'error' in item:
                print(f"  ❌ Item {item['index']}: {item['error']}")
            else:
                print(f"  ✅ Item {item['index']}: {item['title']} (⭐{item['stars']}) - {item['owner']}")
        
        # Ask for confirmation
        response = input("\n🤔 Proceed with push? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("❌ Push cancelled")
            sys.exit(1)
        
        try:
            success, errors = push_from_json_file(args.json_file)
            print(f"📊 JSON push completed: {success} successful, {errors} failed")
        except Exception as e:
            print(f"❌ Error pushing from JSON: {e}")
    
    elif args.mode == "query":
        # Option 3: Push query metadata
        print(f"📂 Pushing query metadata from: {args.json_file}")
        
        # Validate JSON file first
        print("🔍 Validating query metadata file...")
        validation = validate_query_metadata_file(args.json_file)
        
        if not validation["valid"]:
            print(f"❌ Validation failed: {validation['error']}")
            sys.exit(1)
        
        print(f"✅ Validation passed!")
        print(f"📊 Total items: {validation['total_items']}")
        print(f"📏 Estimated size: {validation['estimated_size_mb']:.2f} MB")
        print("📋 Preview:")
        for item in validation['preview']:
            if 'error' in item:
                print(f"  ❌ Item {item['index']}: {item['error']}")
            else:
                print(f"  ✅ Item {item['index']}: ID={item['id']}, Original='{item['original_query']}', Rewritten='{item['rewritten_query']}', Label={item['true_label']}")
        
        # Ask for confirmation
        response = input("\n🤔 Proceed with push to github-examples-prompt container? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("❌ Push cancelled")
            sys.exit(1)
        
        try:
            success, errors = push_query_metadata_to_cosmosdb(args.json_file)
            print(f"📊 Query metadata push completed: {success} successful, {errors} failed")
        except Exception as e:
            print(f"❌ Error pushing query metadata: {e}")
    
    # Option 4: Test with sample document (uncomment to test)
    # client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    # db = client.create_database_if_not_exists(DATABASE_NAME)
    # container = db.create_container_if_not_exists(
    #     id=CONTAINER_NAME,
    #     partition_key=PartitionKey(path="/id"),
    # )


