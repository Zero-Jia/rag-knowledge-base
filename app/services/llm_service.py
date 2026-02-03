# LLM 服务封装（DeepSeek 版）
import os
import time
from typing import List,Dict,Optional,Iterator
from openai import OpenAI

class LLMServiceError(RuntimeError):
    """统一的 LLM 异常类型，方便上层处理"""
    pass

def _create_client()->OpenAI:
    """
    创建 LLM Client（DeepSeek / OpenAI 通用）
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL")

    if not api_key:
        raise LLMServiceError("Missing OPENAI_API_KEY")
    if not base_url:
        raise LLMServiceError("Missing OPENAI_BASE_URL")
    if not model:
        raise LLMServiceError("Missing OPENAI_MODEL")
    
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

def generate_answer(
        messages:List[Dict[str,str]],
        temperature:float=0.2,
        max_retries:int = 2,
)->str:
    """
    调用 DeepSeek Chat API 生成回答，非流式调用，返回完整答案（保留，兼容旧接口）
    """
    client = _create_client()
    model = os.getenv("OPENAI_MODEL")

    last_error:Optional[Exception] = None

    for attempt in range(max_retries+1):
        try:
            response = client.chat.completions.create(
                model = model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            last_error = e
            # 简单指数退避
            time.sleep(0.8*(2**attempt))
    
    raise LLMServiceError(f"DeepSeek API failed: {last_error}")

def stream_answer(
        messages:List[Dict[str,str]],
        temperature:float=0.2,
        max_retries:int = 0,
)->Iterator[str]:
    """
    ✅ 新增：流式调用，逐段 yield 输出内容（token/chunk）

    作用：
    - 给 Day12 的 /chat/stream 用
    - 后端不拼接全文，客户端自己拼接
    - 中途异常也用 yield 输出，保证不断流
    """
    client = _create_client()
    model = os.getenv("OPENAI_MODEL")

    last_error:Optional[Exception] = None

    for attempt in range(max_retries+1):
        try:
            stream = client.chat.completions.create(
                model = model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )

            for chunk in stream:
                # DeepSeek(OpenAI-compatible) 流式 chunk：choices[0].delta.content
                delta = chunk.choices[0].delta
                if delta and getattr(delta,"content",None):
                    yield delta.content
            
            return
        except Exception as e:
            last_error = e
            if attempt<max_retries:
                time.sleep(0.8*(2**attempt))
                continue

            # 最后一次仍失败：把错误“流”出去(便于前端看到)
            yield f"\n[ERROR]: {str(e)}"
            return