from fastapi import APIRouter,Depends
from pydantic import BaseModel

from app.services.chat_service import chat_with_rag
from app.security import get_current_user

router = APIRouter(prefix="/chat",tags=["chat"])

class ChatRequest(BaseModel):
    question:str
    top_k:int = 5

@router.post("/")
def chat(req:ChatRequest,current_user=Depends(get_current_user)):
    return chat_with_rag(req.question,req.top_k)