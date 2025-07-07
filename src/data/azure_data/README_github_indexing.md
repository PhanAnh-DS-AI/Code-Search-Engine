# GitHub Container to Azure AI Search Indexing

This guide explains how to index data from the `github-examples-prompt` CosmosDB container to the `github-example-index` Azure AI Search index.

## Prerequisites

Make sure you have the following environment variables set:

```bash
# Azure AI Search
AZURE_AI_SEARCH_ENDPOINT=your_search_endpoint
AZURE_AI_SEARCH_KEY=your_search_key
AZURE_AI_SEARCH_GITHUB=github-example-index

# CosmosDB
COSMOS_ENDPOINT=your_cosmos_endpoint
COSMOS_KEY=your_cosmos_key
```

## Usage

### Method 1: Using the Command Line

Navigate to the `src/data/azure_data/` directory and run:

```bash
# Index all documents from github-examples-prompt container
python cosmos_to_azure_search.py --github-container

# Index with custom batch size
python cosmos_to_azure_search.py --github-container --batch-size 50

# Index only first 1000 documents
python cosmos_to_azure_search.py --github-container --max-documents 1000

# Force recreate the index (delete existing and create new)
python cosmos_to_azure_search.py --github-container --force-recreate

# Check statistics only
python cosmos_to_azure_search.py --github-container --stats-only
```

### Method 2: Using the Interactive Test Script

Run the interactive test script:

```bash
python test_github_indexing.py
```

This will provide a menu-driven interface to:
1. Test the full indexing process
2. Check statistics only
3. Exit

### Method 3: Using Python Code

```python
from cosmos_to_azure_search import CosmosToAzureSearchIndexer

# Initialize indexer for GitHub container
indexer = CosmosToAzureSearchIndexer(use_github_container=True)

# Check current statistics
cosmos_count = list(indexer.container.query_items(
    "SELECT VALUE COUNT(1) FROM c", 
    enable_cross_partition_query=True
))[0]
search_count = indexer.get_index_stats()

print(f"CosmosDB documents: {cosmos_count}")
print(f"Azure AI Search documents: {search_count}")

# Index documents
total_indexed, total_errors = indexer.index_documents(
    batch_size=100,
    max_documents=None,  # Index all documents
    force_recreate=False
)

print(f"Indexed: {total_indexed}, Errors: {total_errors}")
```

## Index Schema

The `github-example-index` includes the following fields:

- **id** (String, Key): Document identifier
- **title** (String, Searchable): Repository title
- **description** (String, Searchable): Repository description
- **content** (String, Searchable): Repository content
- **tags** (Collection[String], Searchable): Repository tags
- **date** (String): Creation/update date
- **stars** (Int32): Number of stars
- **owner** (String): Repository owner
- **url** (String): Repository URL
- **language** (String): Programming language
- **category** (String): Repository category
- **vector** (Collection[Single], 384 dimensions): Embedding vector
- **score** (Double): Search score

## Features

- **Batch Processing**: Processes documents in configurable batches
- **Error Handling**: Continues processing even if individual documents fail
- **Progress Tracking**: Shows detailed progress and statistics
- **Resume Capability**: Can be stopped and restarted
- **Flexible Configuration**: Customizable batch size and document limits
- **Statistics**: Provides detailed statistics about the indexing process

## Troubleshooting

### Common Issues

1. **Environment Variables Not Set**
   ```
   ValueError: Missing required environment variables
   ```
   Solution: Ensure all required environment variables are set.

2. **Azure AI Search Service Disabled**
   ```
   azure.core.exceptions.ServiceRequestError: The service is currently disabled
   ```
   Solution: Check your Azure AI Search service status in the Azure portal.

3. **Vector Dimension Mismatch**
   ```
   The vector field dimensions do not match
   ```
   Solution: The index is configured for 384-dimensional vectors (BAAI/bge-small-en-v1.5).

4. **Container Not Found**
   ```
   azure.cosmos.exceptions.CosmosResourceNotFoundError
   ```
   Solution: Verify the container name and database exist in your CosmosDB account.

### Logs

The script provides detailed logging with different levels:
- INFO: General progress information
- WARNING: Non-critical issues (e.g., document transformation failures)
- ERROR: Critical errors that stop processing

## Performance Tips

1. **Batch Size**: Use larger batch sizes (100-200) for better performance
2. **Parallel Processing**: The script processes documents sequentially to avoid overwhelming the service
3. **Rate Limiting**: Built-in delays prevent hitting Azure AI Search rate limits
4. **Memory Usage**: Large documents may require smaller batch sizes

## Monitoring

Monitor the indexing process through:
- Console output with progress indicators
- Azure AI Search metrics in the Azure portal
- CosmosDB metrics for read operations
- Application logs for detailed error information 