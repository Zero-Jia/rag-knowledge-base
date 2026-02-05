import time
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.security import get_current_user
from app.services.chat_service import chat_with_rag, stream_chat_with_rag
from app.services.llm_service import LLMServiceError
from app.services.request_context import get_request_id

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger("api.chat") 

class ChatRequest(BaseModel):
    question: str


@router.post("/")
def chat_api(req: ChatRequest, current_user=Depends(get_current_user)):
    rid = get_request_id()         
    start = time.time()            

    # 请求级业务日志（不要打太多，记录关键字段即可）
    q_preview = (req.question or "").replace("\n", " ")[:80]
    logger.info(
        f"/chat | rid={rid} | user={current_user.id} | q_len={len(req.question)} | q_preview='{q_preview}'"
    )

    try:
        result = chat_with_rag(req.question)
        answer = result["answer"] if isinstance(result, dict) else result

        elapsed = time.time() - start 
        logger.info(f"/chat done | rid={rid} | user={current_user.id} | time={elapsed:.3f}s")
        return {"question": req.question, "answer": answer}

    except LLMServiceError as e:
        elapsed = time.time() - start  
        logger.error(f"/chat llm_error | rid={rid} | user={current_user.id} | time={elapsed:.3f}s | error={e}")
        raise HTTPException(status_code=503, detail=str(e))

    except Exception as e:
        elapsed = time.time() - start  
        logger.error(f"/chat error | rid={rid} | user={current_user.id} | time={elapsed:.3f}s | error={e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@router.post("/stream")
def chat_stream_api(req: ChatRequest, current_user=Depends(get_current_user)):
    rid = get_request_id()  

    q_preview = (req.question or "").replace("\n", " ")[:80]
    logger.info(
        f"/chat/stream | rid={rid} | user={current_user.id} | q_len={len(req.question)} | q_preview='{q_preview}'"
    )

    return StreamingResponse(
        stream_chat_with_rag(req.question),
        media_type="text/plain",
    )