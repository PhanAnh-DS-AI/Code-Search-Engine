import os
import sys
# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

import logging
import json
import time
from typing import List, Dict, Any, Optional
from azure.cosmos import CosmosClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticField,
    ScoringProfile,
    TextWeights,
    HnswParameters
)
from azure.core.credentials import AzureKeyCredential
from tqdm import tqdm
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Azure AI Search Configuration
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_AI_SEARCH_KEY")
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_AI_SEARCH_INDEX")
AZURE_SEARCH_INDEX_GITHUB = os.getenv("AZURE_AI_SEARCH_GITHUB", "github-example-index")

# CosmosDB Configuration
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = "github-repositories"
CONTAINER_NAME = "github-container"
CONTAINER_NAME_GITHUB = "github-examples-prompt"

class CosmosToAzureSearchIndexer:
    def __init__(self, use_github_container: bool = False, custom_container: Optional[str] = None, custom_index: Optional[str] = None):
        """
        Initialize the indexer with Azure AI Search and CosmosDB clients
        
        Args:
            use_github_container: If True, use github-examples-prompt container and github-example-index
            custom_container: Custom container name to use
            custom_index: Custom index name to use
        """
        if not all([AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, COSMOS_ENDPOINT, COSMOS_KEY]):
            raise ValueError("Missing required environment variables: AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, COSMOS_ENDPOINT, COSMOS_KEY")
        
        self.use_github_container = use_github_container
        
        # Set the appropriate index name and container name
        if custom_container and custom_index:
            self.index_name = custom_index
            self.container_name = custom_container
            logger.info(f"🔧 Using custom container: {self.container_name} -> Index: {self.index_name}")
        elif use_github_container:
            self.index_name = AZURE_SEARCH_INDEX_GITHUB
            self.container_name = CONTAINER_NAME_GITHUB
            logger.info(f"🔧 Using GitHub container: {self.container_name} -> Index: {self.index_name}")
        else:
            self.index_name = AZURE_SEARCH_INDEX_NAME
            self.container_name = CONTAINER_NAME
            logger.info(f"🔧 Using default container: {self.container_name} -> Index: {self.index_name}")
        
        # Validate index name is not None
        if not self.index_name:
            raise ValueError(f"Index name is None. Check environment variable: {'AZURE_AI_SEARCH_GITHUB' if use_github_container else 'AZURE_AI_SEARCH_INDEX'}")
        
        # Ensure index_name is a string (for type safety)
        self.index_name = str(self.index_name)
        
        # Initialize Azure AI Search clients
        self.search_credential = AzureKeyCredential(str(AZURE_SEARCH_KEY))
        self.index_client = SearchIndexClient(
            endpoint=str(AZURE_SEARCH_ENDPOINT),
            credential=self.search_credential
        )
        self.search_client = SearchClient(
            endpoint=str(AZURE_SEARCH_ENDPOINT),
            index_name=self.index_name,
            credential=self.search_credential
        )
        
        # Initialize CosmosDB client
        cosmos_endpoint = str(COSMOS_ENDPOINT)
        cosmos_key = str(COSMOS_KEY)
        self.cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
        self.database = self.cosmos_client.get_database_client(DATABASE_NAME)
        self.container = self.database.get_container_client(self.container_name)
        
        logger.info("✅ Indexer initialized successfully")

    def create_search_index(self, force_recreate: bool = False):
        """
        Create the Azure AI Search index with vector search capabilities
        
        Args:
            force_recreate: If True, delete existing index before creating new one
        """
        try:
            # Check if index exists
            existing_indexes = [index.name for index in self.index_client.list_indexes()]
            
            if self.index_name in existing_indexes:
                if force_recreate:
                    logger.info(f"🗑️ Deleting existing index: {self.index_name}")
                    self.index_client.delete_index(self.index_name)
                else:
                    logger.info(f"✅ Index {self.index_name} already exists")
                    return
            
            logger.info(f"🏗️ Creating new search index: {self.index_name}")
            
            # Define search fields based on container type
            if self.use_github_container:
                # Fields for github-examples-prompt container
                fields = [
                    # Primary key
                    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                    
                    # Searchable text fields
                    SearchableField(name="title", type=SearchFieldDataType.String, 
                                  analyzer_name="standard", searchable=True),
                    SearchableField(name="description", type=SearchFieldDataType.String, 
                                  analyzer_name="standard", searchable=True),
                    SearchableField(name="content", type=SearchFieldDataType.String, 
                                  analyzer_name="standard", searchable=True),
                    SimpleField(name="tags", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
                    
                    # Metadata fields
                    SimpleField(name="date", type=SearchFieldDataType.String),
                    SimpleField(name="stars", type=SearchFieldDataType.Int32),
                    SimpleField(name="owner", type=SearchFieldDataType.String),
                    SimpleField(name="url", type=SearchFieldDataType.String),
                    SimpleField(name="language", type=SearchFieldDataType.String),
                    SimpleField(name="category", type=SearchFieldDataType.String),
                    
                    # Vector field for semantic search (384 dimensions for BAAI/bge-small-en-v1.5)
                    SearchField(name="vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), 
                               vector_search_dimensions=384, vector_search_profile_name="default-profile"),
                    
                    # Score field
                    SimpleField(name="score", type=SearchFieldDataType.Double)
                ]
            else:
                # Fields for default github-container (with vector field restored)
                fields = [
                    # Primary key
                    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                    
                    # Searchable text fields
                    SearchableField(name="title", type=SearchFieldDataType.String, 
                                  analyzer_name="standard", searchable=True, filterable=True, sortable=True),
                    SearchableField(name="short_des", type=SearchFieldDataType.String, 
                                  analyzer_name="standard", searchable=True, filterable=True, sortable=True),
                    SimpleField(name="tags", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True, searchable=True, facetable=True),
                    
                    # Metadata fields
                    SimpleField(name="date", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True, searchable=True),
                    SimpleField(name="stars", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
                    SimpleField(name="owner", type=SearchFieldDataType.String, filterable=True, sortable=True, searchable=True),
                    SimpleField(name="url", type=SearchFieldDataType.String, filterable=True, sortable=True, searchable=True),
                    
                    # Vector field for semantic search (384 dimensions for BAAI/bge-small-en-v1.5)
                    SearchField(name="vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), 
                               vector_search_dimensions=384, vector_search_profile_name="default-profile"),
                    
                    # Score field
                    SimpleField(name="score", type=SearchFieldDataType.Double, filterable=True, sortable=True)
                ]
            
            # Create vector search configuration
            vector_search = VectorSearch(
                profiles=[
                    VectorSearchProfile(
                        name="default-profile",
                        algorithm_configuration_name="default-algorithm"
                    )
                ],
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="default-algorithm",
                        kind="hnsw",
                        parameters=HnswParameters(
                            m=4,
                            ef_construction=400,
                            ef_search=500,
                            metric="cosine"
                        )
                    )
                ]
            )
            
            # Create the index with vector search configuration
            index = SearchIndex(
                name=str(self.index_name),
                fields=fields,
                vector_search=vector_search
            )
            
            self.index_client.create_index(index)
            logger.info(f"✅ Search index '{self.index_name}' created successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to create search index: {e}")
            raise

    def fetch_documents_from_cosmos(self, batch_size: int = 100, max_documents: Optional[int] = None):
        """
        Fetch documents from CosmosDB in batches
        
        Args:
            batch_size: Number of documents to fetch per batch
            max_documents: Maximum number of documents to fetch (None for all)
        
        Returns:
            Generator yielding batches of documents
        """
        try:
            # Count total documents
            query = "SELECT VALUE COUNT(1) FROM c"
            count_result = list(self.container.query_items(query=query, enable_cross_partition_query=True))[0]
            # Handle both direct value and dictionary formats
            if isinstance(count_result, dict):
                total_count = int(count_result.get("$1", count_result))
            else:
                total_count = int(count_result)
            
            if max_documents:
                total_count = min(total_count, max_documents)
            
            logger.info(f"📊 Total documents in CosmosDB container '{self.container_name}': {total_count}")
            
            # Fetch documents in batches using a different approach to avoid cross-partition issues
            query = "SELECT * FROM c"
            batch = []
            count = 0
            
            for doc in self.container.query_items(query=query, enable_cross_partition_query=True):
                if max_documents and count >= max_documents:
                    break
                
                try:
                    transformed_doc = self._transform_document(doc)
                    if transformed_doc:
                        batch.append(transformed_doc)
                        count += 1
                        
                        # Yield batch when it reaches the batch size
                        if len(batch) >= batch_size:
                            yield batch
                            batch = []
                            
                except Exception as e:
                    logger.warning(f"⚠️ Failed to transform document {doc.get('id', 'unknown')}: {e}")
                    continue
            
            # Yield any remaining documents in the last batch
            if batch:
                yield batch
                    
        except Exception as e:
            logger.error(f"❌ Failed to fetch documents from CosmosDB: {e}")
            raise

    def _transform_document(self, cosmos_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Transform a CosmosDB document to Azure AI Search format
        
        Args:
            cosmos_doc: Document from CosmosDB
        
        Returns:
            Transformed document for Azure AI Search
        """
        try:
            # Debug: Log original document structure for first few documents
            doc_id = cosmos_doc.get('id', 'unknown')
            if doc_id in [' ', '28457824', '28457825']:  # Log first few documents
                logger.info(f"🔍 Debug: Original document {doc_id} keys: {list(cosmos_doc.keys())}")
                for key, value in cosmos_doc.items():
                    if isinstance(value, list):
                        logger.info(f"  {key}: list with {len(value)} items")
                    elif isinstance(value, dict):
                        logger.info(f"  {key}: dict with keys {list(value.keys())}")
                    else:
                        logger.info(f"  {key}: {type(value).__name__} = {str(value)[:50]}")
            if self.use_github_container:
                # Transform for github-examples-prompt container
                search_doc = {
                    'id': str(cosmos_doc.get('id', '')),
                    'title': str(cosmos_doc.get('title', '')),
                    'description': str(cosmos_doc.get('description', '')),
                    'content': str(cosmos_doc.get('content', '')),
                    'tags': self._ensure_list(cosmos_doc.get('tags')),
                    'date': str(cosmos_doc.get('date', '')),
                    'stars': int(cosmos_doc.get('stars', 0)),
                    'owner': str(cosmos_doc.get('owner', '')),
                    'url': str(cosmos_doc.get('url', '')),
                    'language': str(cosmos_doc.get('language', '')),
                    'category': str(cosmos_doc.get('category', '')),
                    'vector': self._ensure_vector(cosmos_doc.get('vector')),
                    'score': self._ensure_float(cosmos_doc.get('score'))
                }
                
                # Remove any fields that are not in the search index schema
                # Only keep the fields that are defined in the index
                allowed_fields = {
                    'id', 'title', 'description', 'content', 'tags', 'date', 'stars', 
                    'owner', 'url', 'language', 'category', 'vector', 'score'
                }
                search_doc = {k: v for k, v in search_doc.items() if k in allowed_fields}
                
                # Debug: Log transformed document for first few documents
                if doc_id in ['28457823', '28457824', '28457825']:
                    logger.info(f"🔍 Debug: Transformed document {doc_id} keys: {list(search_doc.keys())}")
                    for key, value in search_doc.items():
                        if isinstance(value, list):
                            logger.info(f"  {key}: list with {len(value)} items, first few: {value[:3] if value else 'empty'}")
                        else:
                            logger.info(f"  {key}: {type(value).__name__} = {str(value)[:50]}")
            else:
                # Transform for default github-container
                meta_data = cosmos_doc.get('meta_data', {})
                search_doc = {
                    'id': str(cosmos_doc.get('id', meta_data.get('id', ''))),
                    'title': str(cosmos_doc.get('title', '')),
                    'short_des': str(cosmos_doc.get('short_des', '')),
                    'tags': self._ensure_list(cosmos_doc.get('tags')),
                    'date': str(cosmos_doc.get('date', '')),
                    'stars': int(cosmos_doc.get('stars', meta_data.get('stars', 0))),
                    'owner': str(cosmos_doc.get('owner', meta_data.get('owner', ''))),
                    'url': str(cosmos_doc.get('url', meta_data.get('url', ''))),
                    'vector': self._ensure_vector(cosmos_doc.get('vector')),
                    'score': self._ensure_float(cosmos_doc.get('score'))
                }
                
                # Remove any fields that are not in the search index schema
                # Only keep the fields that are defined in the index
                allowed_fields = {
                    'id', 'title', 'short_des', 'tags', 'date', 'stars', 
                    'owner', 'url', 'vector', 'score'
                }
                search_doc = {k: v for k, v in search_doc.items() if k in allowed_fields}
                
                # Debug: Log transformed document for first few documents
                if doc_id in ['28457823', '28457824', '28457825']:
                    logger.info(f"🔍 Debug: Transformed document {doc_id} keys: {list(search_doc.keys())}")
                    for key, value in search_doc.items():
                        if isinstance(value, list):
                            logger.info(f"  {key}: list with {len(value)} items, first few: {value[:3] if value else 'empty'}")
                        else:
                            logger.info(f"  {key}: {type(value).__name__} = {str(value)[:50]}")
            
            # Validate and clean document data types
            search_doc = self._validate_document_types(search_doc)
            
            # Validate required fields
            if not search_doc['id'] or not search_doc['title']:
                logger.warning(f"⚠️ Skipping document with missing required fields: {search_doc.get('id', 'unknown')}")
                return None
            
            return search_doc
            
        except Exception as e:
            logger.error(f"❌ Failed to transform document: {e}")
            return None

    def _ensure_list(self, value: Any) -> List[str]:
        """Ensure value is a list of strings"""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        elif isinstance(value, (dict, set, tuple)):
            # Convert other iterable types to list of strings
            return [str(item) for item in value if item is not None]
        return [str(value)]

    def _ensure_vector(self, value: Any) -> List[float]:
        """Ensure value is a list of floats for vector field"""
        if value is None:
            return []
        if isinstance(value, list):
            return [float(item) for item in value if item is not None]
        return []

    def _ensure_float(self, value: Any) -> float:
        """Ensure value is a float, return 0.0 if None or invalid"""
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _validate_document_types(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean document data types for Azure AI Search"""
        cleaned_doc = {}
        for key, value in doc.items():
            if key == 'vector':
                # Vector field should be a list of floats
                cleaned_doc[key] = self._ensure_vector(value)
            elif key == 'tags':
                # Tags field should be a list of strings
                cleaned_doc[key] = self._ensure_list(value)
            elif key == 'score':
                # Score field should be a float
                cleaned_doc[key] = self._ensure_float(value)
            elif key in ['stars']:
                # Integer fields
                try:
                    cleaned_doc[key] = int(value) if value is not None else 0
                except (ValueError, TypeError):
                    cleaned_doc[key] = 0
            else:
                # All other fields should be strings
                if value is None:
                    cleaned_doc[key] = ""
                elif isinstance(value, (dict, list, set, tuple)):
                    # Convert complex types to string representation
                    cleaned_doc[key] = str(value)
                else:
                    cleaned_doc[key] = str(value)
        
        return cleaned_doc

    def index_documents(self, batch_size: int = 100, max_documents: Optional[int] = None, 
                       force_recreate: bool = False):
        """
        Index documents from CosmosDB to Azure AI Search
        
        Args:
            batch_size: Number of documents to process per batch
            max_documents: Maximum number of documents to index
            force_recreate: Whether to recreate the index
        """
        try:
            # Create or recreate the search index
            self.create_search_index(force_recreate=force_recreate)
            
            # Fetch and index documents
            total_indexed = 0
            total_errors = 0
            
            logger.info(f"🚀 Starting indexing process from '{self.container_name}' to '{self.index_name}'...")
            
            # Get document batches
            document_batches = self.fetch_documents_from_cosmos(batch_size=batch_size, max_documents=max_documents)
            
            for batch_num, batch in enumerate(document_batches, 1):
                if not batch:
                    continue
                
                logger.info(f" Processing batch {batch_num} ({len(batch)} documents)")
                
                try:
                    # Debug: Log the first document structure to see what's being sent
                    if batch_num == 1 and batch:
                        logger.info(f"🔍 Debug: First document structure:")
                        logger.info(f"Document keys: {list(batch[0].keys())}")
                        for key, value in batch[0].items():
                            if isinstance(value, list):
                                logger.info(f"  {key}: list with {len(value)} items, first few: {value[:3] if value else 'empty'}")
                            else:
                                logger.info(f"  {key}: {type(value).__name__} = {str(value)[:100]}")
                    
                    # Debug: Check for any problematic data types in the batch
                    for i, doc in enumerate(batch):
                        for key, value in doc.items():
                            if isinstance(value, list) and key not in ['tags', 'vector']:
                                logger.error(f"❌ Found unexpected list in field '{key}' in document {i}: {value[:5]}")
                            elif value is None and key in ['id', 'title']:
                                logger.error(f"❌ Found None value in required field '{key}' in document {i}")
                            elif isinstance(value, (dict, list)) and key not in ['tags', 'vector']:
                                logger.error(f"❌ Found complex type {type(value).__name__} in field '{key}' in document {i}: {str(value)[:100]}")
                    
                    # Debug: Log the actual JSON being sent to Azure AI Search
                    if batch_num == 1 and batch:
                        import json
                        try:
                            sample_doc = batch[0]
                            json_str = json.dumps(sample_doc, indent=2)
                            logger.info(f"🔍 Debug: Sample document JSON being sent to Azure AI Search:")
                            logger.info(json_str)
                        except Exception as json_error:
                            logger.error(f"❌ Failed to serialize document to JSON: {json_error}")
                    
                    # Debug: Log every document in the problematic batch
                    if batch_num == 18:  # Log the problematic batch
                        logger.info(f"🔍 Debug: Batch 18 contains {len(batch)} documents")
                        for i, doc in enumerate(batch):
                            logger.info(f"🔍 Document {i} (ID: {doc.get('id', 'unknown')}):")
                            for key, value in doc.items():
                                if isinstance(value, list):
                                    logger.info(f"  {key}: list with {len(value)} items, first few: {value[:3] if value else 'empty'}")
                                elif isinstance(value, dict):
                                    logger.info(f"  {key}: dict with keys {list(value.keys())}")
                                else:
                                    logger.info(f"  {key}: {type(value).__name__} = {str(value)[:50]}")
                    
                    # Upload batch to Azure AI Search
                    result = self.search_client.upload_documents(batch)
                    
                    # Count successful and failed uploads
                    batch_success = sum(1 for r in result if r.succeeded)
                    batch_errors = len(result) - batch_success
                    
                    total_indexed += batch_success
                    total_errors += batch_errors
                    
                    logger.info(f"✅ Batch {batch_num}: {batch_success} indexed, {batch_errors} errors")
                    
                    # Log any errors
                    for i, r in enumerate(result):
                        if not r.succeeded:
                            logger.warning(f"⚠️ Document {batch[i].get('id', 'unknown')} failed: {r.status_code}")
                    
                    # Small delay to avoid overwhelming the service
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"❌ Failed to index batch {batch_num}: {e}")
                    total_errors += len(batch)
                    continue
            
            logger.info(f"🎉 Indexing completed!")
            logger.info(f"📊 Total indexed: {total_indexed}")
            logger.info(f"❌ Total errors: {total_errors}")
            
            return total_indexed, total_errors
            
        except Exception as e:
            logger.error(f"❌ Indexing process failed: {e}")
            raise

    def get_index_stats(self):
        """Get statistics about the search index"""
        try:
            stats = self.search_client.get_document_count()
            logger.info(f"📊 Documents in search index '{self.index_name}': {stats}")
            return stats
        except Exception as e:
            logger.error(f"❌ Failed to get index stats: {e}")
            return None

def main():
    parser = argparse.ArgumentParser(description="Index CosmosDB data to Azure AI Search")
    parser.add_argument("--batch-size", type=int, default=100, 
                       help="Number of documents to process per batch (default: 100)")
    parser.add_argument("--max-documents", type=int, default=None,
                       help="Maximum number of documents to index (default: all)")
    parser.add_argument("--force-recreate", action="store_true",
                       help="Force recreate the search index")
    parser.add_argument("--stats-only", action="store_true",
                       help="Only show index statistics")
    parser.add_argument("--github-container", action="store_true",
                       help="Use github-examples-prompt container and github-example-index")
    parser.add_argument("--cosmos-container", type=str, default=None,
                       help="Custom CosmosDB container name")
    parser.add_argument("--search-index", type=str, default=None,
                       help="Custom Azure AI Search index name")
    
    args = parser.parse_args()
    
    try:
        indexer = CosmosToAzureSearchIndexer(
            use_github_container=args.github_container,
            custom_container=args.cosmos_container,
            custom_index=args.search_index
        )
        
        if args.stats_only:
            # Show current stats
            cosmos_count = list(indexer.container.query_items(
                "SELECT VALUE COUNT(1) FROM c", 
                enable_cross_partition_query=True
            ))[0]
            search_count = indexer.get_index_stats()
            
            print(f"📊 CosmosDB documents in '{indexer.container_name}': {cosmos_count}")
            print(f"📊 Azure AI Search documents in '{indexer.index_name}': {search_count}")
            return
        
        # Perform indexing
        total_indexed, total_errors = indexer.index_documents(
            batch_size=args.batch_size,
            max_documents=args.max_documents,
            force_recreate=args.force_recreate
        )
        
        print(f"\n🎉 Indexing Summary:")
        print(f"✅ Successfully indexed: {total_indexed} documents")
        print(f"❌ Errors: {total_errors}")
        
        if total_errors == 0:
            print("🎊 All documents indexed successfully!")
        else:
            print(f"⚠️ {total_errors} documents failed to index")
            
    except Exception as e:
        logger.error(f"❌ Indexing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 