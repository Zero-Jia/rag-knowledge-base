# LLM 服务封装（DeepSeek 版）
import os
import time
import logging
from typing import List,Dict,Optional,Iterator
from openai import OpenAI
from app.services.request_context import get_request_id

logger = logging.getLogger("rag.llm")

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
    rid = get_request_id()
    start = time.time()

    client = _create_client()
    model = os.getenv("OPENAI_MODEL")

    # 尽量不要把 messages 全文打出来，记录规模即可
    user_chars = 0
    if messages:
        # 找最后一条 user 内容估算长度（更有意义）
        for m in reversed(messages):
            if m.get("role") == "user":
                user_chars = len(m.get("content", ""))
                break

    logger.info(
        f"LLM call start | rid={rid} | model={model} | temperature={temperature} | user_chars={user_chars} | timeout={timeout}s"
    )

    last_error:Optional[Exception] = None

    for attempt in range(max_retries+1):
        try:
            if attempt > 0:
                logger.warning(f"LLM retry | rid={rid} | attempt={attempt}/{max_retries}")

            response = client.chat.completions.create(
                model = model,
                messages=messages,
                temperature=temperature,
                timeout=timeout,
            )
            result = (response.choices[0].message.content or "").strip()
            elapsed = time.time() - start
            logger.info(
                f"LLM call success | rid={rid} | time={elapsed:.2f}s | out_chars={len(result)}"
            )
            return result
        except Exception as e:
            last_error = e
            # 每次失败打一次 error（带 attempt）
            logger.error(f"LLM call failed | rid={rid} | attempt={attempt}/{max_retries} | error={e}")
            if attempt < max_retries:
                # 简单指数退避
                time.sleep(0.8*(2**attempt))
                continue
    elapsed = time.time() - start  
    logger.error(f"LLM final fail | rid={rid} | time={elapsed:.2f}s | error={last_error}")
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
    rid = get_request_id()
    start = time.time()

    client = _create_client()
    model = os.getenv("OPENAI_MODEL")

    logger.info(
        f"LLM stream start | rid={rid} | model={model} | temperature={temperature} | timeout={timeout}s"
    )

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True,
            timeout=timeout,  # ✅ Day13：关键改动（超时）
        )

        out_chars = 0
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and getattr(delta, "content", None):
                piece = delta.content
                out_chars += len(piece)
                yield piece

        elapsed = time.time() - start
        logger.info(f"LLM stream done | rid={rid} | time={elapsed:.2f}s | out_chars={out_chars}")

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"LLM stream failed | rid={rid} | time={elapsed:.2f}s | error={e}")
        yield "\n[ERROR]: LLM service unavailable, please retry later."
        return