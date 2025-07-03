import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse
import uvicorn
import logging
import time

# from src.qdrant.client import QdrantClientWrapper
# from src.qdrant.push_data import load_data
from src.api.schemas import *
from src.azure_client.azure_search import (
    text_search_with_semantic_cache,
    full_text_search, 
    vector_search, 
    hybrid_search, 
    search_by_tag
    )
from src.azure_client.azure_recommend import handle_recommendations
from src.cache.cache_client import text_search_cache, hybrid_search_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Code-Semantic-Search API")
# qdrant = QdrantClientWrapper()

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "API is running"}

# Endpoint to index data
# @app.post("/index", response_model=dict)
# async def index_data(request: IndexRequest):
#     try:
#         data = load_data(request.data_path)
#         if not data:
#             raise HTTPException(status_code=400, detail="No data loaded from file")

#         # Push to Qdrant for both vector and full text search
#         qdrant.load_and_push_data(request.data_path)
#         logger.info(f"Indexed {len(data)} repositories to Qdrant")
#         return {"message": f"Indexed {len(data)} repositories successfully"}
#     except Exception as e:
#         logger.error(f"Error indexing data: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# Endpoint for vector search
@app.post("/search/vector", response_model=SearchResponse)
async def vector_search_api(request: SearchRequest):
    try:
        start_time = time.time()

        result = vector_search(request.query, request.limit)

        elapsed = time.time() - start_time
        logger.info(f"[VECTOR SEARCH] Query: '{request.query}' | Time: {elapsed:.3f} s")

        return {"result": result}
    except Exception as e:
        logger.error(f"Error in vector search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint for full text search using Qdrant payload filtering
@app.post("/search/text", response_model=SearchResponse)
async def text_search_api(request: SearchRequestTextCache):
    try:
        start_time = time.time()

        result = text_search_with_semantic_cache(
            request.query,
            text_search_cache.cache,
            top_k=request.limit,
            threshold=request.threshold
        )

        elapsed = time.time() - start_time
        logger.info(f"[TEXT SEARCH] Query: '{request.query}' | Time: {elapsed:.3f} s")
        return {"result": result}
    except Exception as e:
        logger.error(f"Error in full text search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/search/hybrid", response_model=SearchResponseHybrid)
async def hybrid_search_api(request: SearchRequest):
    try:
        start_time = time.time()

        search_result = hybrid_search(request.query, request.limit)
        # print(search_result)
        # result=search_result.get('result',[])
        suggest_topic=search_result.get('suggest_topic',{})
        suggest_filter=search_result.get('suggest_filter',[])
        # print(suggest_topic)
        # print(suggest_filter)
        elapsed = time.time() - start_time
        logger.info(f"[HYBRID SEARCH] Query: '{request.query}' | Time: {elapsed:.3f} s")

        return search_result
    except Exception as e:
        logger.error(f"Error in hybrid search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search/tag", response_model=SearchResponse)
async def tag_search_api(request: SearchRequest):
    try:
        start_time = time.time()

        result = search_by_tag(request.query, request.limit)

        elapsed = time.time() - start_time
        logger.info(f"[TAG SEARCH] Query: '{request.query}' | Time: {elapsed:.3f} s")

        return {"result": result}
    except Exception as e:
        logger.error(f"Error in tag search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/recommendations")
def recommendations_post(request: RecommendationRequest = Body(...)):
    response = handle_recommendations(limit=request.limit)
    return JSONResponse(content=response)
    
if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8080)