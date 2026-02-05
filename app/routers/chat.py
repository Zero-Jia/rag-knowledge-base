from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.security import get_current_user
from app.services.chat_service import chat_with_rag, stream_chat_with_rag
from app.services.llm_service import LLMServiceError

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str


@router.post("/")
def chat_api(req: ChatRequest, current_user=Depends(get_current_user)):
    try:
        # chat_with_rag 你现在返回的是 dict（含 answer/chunks），
        # 但 Day16 step4 建议 router 只返回 question/answer
        result = chat_with_rag(req.question)
        answer = result["answer"] if isinstance(result, dict) else result
        return {"question": req.question, "answer": answer}

    except LLMServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@router.post("/stream")
def chat_stream_api(req: ChatRequest, current_user=Depends(get_current_user)):
    # Day16：router 不处理检索策略，不传 top_k
    return StreamingResponse(
        stream_chat_with_rag(req.question),
        media_type="text/plain",
    )
