# LLM 服务封装（DeepSeek 版）
import os
import time
from typing import List,Dict,Optional,Iterator
from openai import OpenAI

class LLMServiceError(RuntimeError):
    """统一的 LLM 异常类型，方便上层处理"""
    pass

# ✅ Day13：统一配置（工程化）
MAX_RETRIES = 3
BASE_DELAY = 1
TIMEOUT_SECONDS = 20

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
        max_retries:int = MAX_RETRIES,
        timeout:int = TIMEOUT_SECONDS, # 超时参数
)->str:
    """
    调用 DeepSeek Chat API 生成回答，非流式调用，返回完整答案（有限重试 + 指数退避 + 超时）
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
                timeout=timeout,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                # 简单指数退避
                time.sleep(0.8*(2**attempt))
                continue
    
    raise LLMServiceError(f"DeepSeek API failed after retries: {last_error}")

def stream_answer(
        messages:List[Dict[str,str]],
        temperature:float=0.2,
        timeout:int = TIMEOUT_SECONDS,
)->Iterator[str]:
    """
    ✅ Day13：流式调用（工程取舍：不做复杂重试）
    - 流式中途失败很难“无缝续上”，所以只做一次调用
    - 失败就 yield 清晰错误给前端（不断流）
    """
    client = _create_client()
    model = os.getenv("OPENAI_MODEL")

    last_error:Optional[Exception] = None

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True,
            timeout=timeout,  # ✅ Day13：关键改动（超时）
        )

        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and getattr(delta, "content", None):
                yield delta.content

    except Exception:
        yield "\n[ERROR]: LLM service unavailable, please retry later."
        return