import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from src.elastic.schema import SearchResult


# ======= Pydantic Schema ========
class IndexRequest(BaseModel):
    data_path: str

class SearchResponse(BaseModel):
    result: List[Dict[str, Any]]

class SearchHybridAndTagResponse(BaseModel):
    result: List[SearchResult]

class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    
class SearchRequestTextCache(BaseModel):
    query: str
    limit: int = 50
    threshold: float = 0.8


class SearchResponseHybrid(BaseModel):
    result: List[Dict[str, Any]]
    suggest_filter: List[str]
    suggest_topic: List[str]

class RecommendationRequest(BaseModel):
    limit: int = Field(25, gt=0, description="Number of top recommendations to return")

# ========== Schema for Generated Query ===========
class UserQueryRequest(BaseModel):
    query: str

class RelatedQueriesResponse(BaseModel):
    session_id: str
    related_queries: List[str]

class SearchFromRelatedRequest(BaseModel):
    session_id: str
    index: int  
    method: str  
    limit: Optional[int] = 8

class ShowMoreRequest(BaseModel):
    session_id: str
    method: str
    limit: Optional[int] = 8

class ChooseBestRequest(BaseModel):
    session_id: str
    best_index: int