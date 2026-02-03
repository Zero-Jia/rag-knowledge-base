# 请求/响应定义
from pydantic import BaseModel,Field
from typing import List

class QueryRequest(BaseModel):
    query:str = Field(...,min_length=1,description="User question")
    top_k:int = Field(5,ge=1,le=20,description="How many chunks to retrieve")

class RetrievedChunk(BaseModel):
    text:str
    document_id:int
    score:float

class QueryResponse(BaseModel):
    query:str
    results:List[RetrievedChunk]