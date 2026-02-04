from fastapi import APIRouter,Depends,Request,HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.chat_service import chat_with_rag,stream_chat_with_rag
from app.security import get_current_user
from app.services.llm_service import LLMServiceError

router = APIRouter(prefix="/chat",tags=["chat"])

class ChatRequest(BaseModel):
    question:str
    top_k:int = 5

@router.post("/")
def chat(req:ChatRequest,current_user=Depends(get_current_user)):
    # 旧接口：一次性返回完整答案
    # 捕获 LLM 异常，避免 500 炸穿
    try:
        return chat_with_rag(req.question,req.top_k)
    except LLMServiceError as e:
        # LLM 多次失败/超时：服务不可用（但主服务不挂）
        raise HTTPException(status_code=503,detail=str(e))
    except Exception as e:
        # 其他未预期错误：仍然返回 500，但信息更清晰
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

def sse_pack(data:str)->str:
    """
    SSE 协议要求：
    每条消息以 'data: ' 开头，以两个换行结尾
    """
    return f"data: {data}\n\n"

@router.post("/stream")
def chat_stream(
    req:ChatRequest,
    request:Request,
    current_user=Depends(get_current_user),
):
    """
    新接口：SSE 流式输出
    - 后端逐段输出 token/chunk
    - 客户端逐段接收并拼接显示
    流式里也要兜底，把错误以 data: 输出，保证不断流
    """
    def event_generator():
        try:
            # stream_chat_with_rag 返回 generator，会不断 yield token
            for token in stream_chat_with_rag(req.question,req.top_k):
                # 客户端断开连接：及时停止，避免浪费 token / 资源
                # 注意：这里 request.is_disconnected() 在同步函数里是可调用的，
                # 但不同版本实现可能返回 awaitable；若你运行报错，我再给你改 async 版本
                disconnected = False
                try:
                    disconnected = request.is_disconnected()
                    # 某些版本返回 coroutine，需要兼容一下
                    if hasattr(disconnected,"__await__"):
                        # 不支持在 sync 里 await，就先不处理断开（或改 async 版本）
                        disconnected = False
                except Exception:
                    disconnected = False
            
                if disconnected:
                    break

                yield sse_pack(token)
        
            # 可选：结束事件，方便前端收尾
            yield "event: end\ndata: [DONE]\n\n"
        except LLMServiceError:
            # LLM 错误 -> 给前端友好提示（不断流）
            yield sse_pack("[ERROR]: LLM service unavailable, please retry later.")
            yield "event: end\ndata: [DONE]\n\n"
        except Exception as e:
            # 兜底：其他异常也流出去，方便你 debug
            yield sse_pack(f"[ERROR]: {str(e)}")
            yield "event: end\ndata: [DONE]\n\n"
            
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )