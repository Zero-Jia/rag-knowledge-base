# LLM 服务封装（DeepSeek 版）
import os
import time
from typing import List,Dict,Optional
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
    调用 DeepSeek Chat API 生成回答
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