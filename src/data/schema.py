from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class MetaData(BaseModel):
    stars: int = Field(description="Number of stars on the repository")
    owner: str = Field(description="Repository owner username")
    url: str = Field(description="Repository URL")
    id: int = Field(description="Repository ID")

class RepoDoc(BaseModel):
    title: str = Field(description="Repository full name (owner/repo)")
    short_des: str = Field(description="Repository description")
    tags: List[str] = Field(default_factory=list, description="Repository topics/tags")
    date: str = Field(description="Repository creation date")
    meta_data: MetaData = Field(description="Repository metadata")
    score: float = Field(default=0.0, description="Search relevance score")
    vector: List[float] = Field(default_factory=list, description="Embedding vector for vector search")
    
    class Config:
        # Allow extra fields for flexibility
        extra = "allow"
        # Use enum values for validation
        use_enum_values = True
        # Validate assignments
        validate_assignment = True