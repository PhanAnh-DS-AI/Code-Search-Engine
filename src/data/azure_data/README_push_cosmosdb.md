# Push GitHub Repositories to CosmosDB

This module provides functionality to push GitHub repository data to Azure CosmosDB.

## Features

- ✅ Fetch repositories from GitHub and push to CosmosDB
- ✅ Push repositories from JSON files to CosmosDB
- ✅ Automatic schema validation using Pydantic
- ✅ Progress tracking with tqdm
- ✅ Strict schema validation for data integrity
- ✅ Automatic embedding generation for vector search
- ✅ AI-powered description generation for repositories without descriptions

## Usage

### 1. Fetch from GitHub and Push

```bash
# Fetch 100 repositories from GitHub and push to CosmosDB
python src/data/push_azure_cosmosdb.py --mode fetch --max-repos 100

# Fetch 5000 repositories (default)
python src/data/push_azure_cosmosdb.py --mode fetch --max-repos 5000
```

### 2. Push from JSON File

```bash
# Push from default JSON file (github_repos_schema.json)
python src/data/push_azure_cosmosdb.py --mode json

# Push from custom JSON file
python src/data/push_azure_cosmosdb.py --mode json --json-file my_repos.json
```

### 3. Command Line Options

```bash
python src/data/push_azure_cosmosdb.py --help
```

Options:
- `--mode`: Choose between "fetch" (GitHub) or "json" (JSON file)
- `--json-file`: Path to JSON file (default: github_repos_schema.json)
- `--max-repos`: Maximum repositories to fetch (default: 100)

## Environment Variables

Required environment variables:

```bash
COSMOS_ENDPOINT=your-cosmos-endpoint
COSMOS_KEY=your-cosmos-key
GITHUB_TOKEN=your-github-token  # Only needed for fetch mode
```

## JSON Schema Format

The JSON file must follow the Pydantic schema format:

```json
[
  {
    "title": "owner/repo",
    "short_des": "Repository description",
    "tags": ["tag1", "tag2"],
    "date": "2024-01-01T00:00:00Z",
    "meta_data": {
      "stars": 1000,
      "owner": "owner",
      "url": "https://github.com/owner/repo",
      "id": 12345
    },
    "score": 0.0,
    "vector": [0.1, 0.2, 0.3, ...]
  }
]
```

### Required Fields

#### Top Level:
- `title`: Repository full name (e.g., "microsoft/vscode")
- `short_des`: Repository description
- `tags`: Array of repository topics/tags
- `date`: Repository creation date (ISO format)
- `meta_data`: Metadata object
- `score`: Search relevance score (float)
- `vector`: Embedding vector for Azure AI Search vector search (array of floats)

#### Meta Data:
- `stars`: Number of stars (integer)
- `owner`: Repository owner username (string)
- `url`: Repository URL (string)
- `id`: Repository ID (integer)

## Database Configuration

The script uses these default database settings:
- Database: `github-repositories`
- Container: `github-container`
- Partition Key: `/id`

## Progress Tracking

The script shows progress bars for:
- 🔍 Processing GitHub queries
- 🔄 Converting repositories to schema
- 📤 Pushing to CosmosDB

## Error Handling

- ✅ Validates JSON files before processing
- ✅ Shows preview of data before pushing
- ✅ Strict schema validation
- ✅ Continues processing even if some items fail
- ✅ Detailed error logging

## Example Output

```
🚀 Starting GitHub to CosmosDB pipeline...
📂 Pushing from JSON file: github_repos_schema.json
🔍 Validating JSON file...
✅ Validation passed!
📊 Total items: 5000
📏 Estimated size: 15.23 MB
📋 Preview:
  ✅ Item 0: microsoft/vscode (⭐1500) - microsoft
  ✅ Item 1: facebook/react (⭐2000) - facebook
  ✅ Item 2: tensorflow/tensorflow (⭐1800) - tensorflow

🤔 Proceed with push? (y/N): y
📤 Pushing from JSON to CosmosDB: 100%|██████████| 5000/5000 [05:20<00:00, 15.63doc/s]
📊 JSON push completed: 4987 successful, 13 failed
```

## Schema Validation

The script validates that each JSON item contains:
- All required top-level fields
- Proper meta_data structure
- Correct data types
- Non-empty required fields

Invalid items are skipped and logged for review. 