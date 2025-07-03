from typing import List, Dict, Optional, Any
from pydantic import BaseModel

# ===== Result Schema =====
class MetaData(BaseModel):
    stars: Optional[int]
    owner: Optional[str]
    url: Optional[str]
    id: Optional[int]

class SearchResult(BaseModel):
    score: Optional[float]
    title: Optional[str]
    short_des: Optional[str]
    tags: Optional[List[str]]
    date: Optional[str]
    meta_data: Optional[MetaData]
    highlight: Optional[dict] = None

class SearchTextResponse(BaseModel):
    result: List[SearchResult]