import logging  
import time     

from app.services.request_context import get_request_id  
from app.services.rag_retrieval import rag_retrieve
from app.services.prompt_builder import build_messages
from app.services.llm_service import generate_answer, stream_answer

logger = logging.getLogger("rag.perf")  # （也可以叫 rag.chat）


def chat_with_rag(question: str):
    """
    Day16：统一版（非流式）
    chat_service 不关心检索细节（vector/hybrid/rerank）
    """
    rid = get_request_id()   
    start = time.time()      

    logger.info(f"chat start | rid={rid} | question_len={len(question)}")  # ✅ NEW

    try:
        chunks = rag_retrieve(question)
        messages = build_messages(question, chunks)
        answer = generate_answer(messages)

        elapsed = time.time() - start 
        logger.info(
            f"chat done  | rid={rid} | chunks={len(chunks)} | answer_chars={len(answer)} | time={elapsed:.3f}s"
        )
        return {
            "question": question,
            "answer": answer,
            "chunks": chunks,
        }

    except Exception as e:
        elapsed = time.time() - start  
        logger.error(f"chat fail | rid={rid} | time={elapsed:.3f}s | error={e}")
        raise


def stream_chat_with_rag(question: str):
    """
    ✅ 流式版 RAG
    1) 先检索（一次性）
    2) 构建 messages（一次性）
    3) 调用 LLM 的 stream_answer，把 token/chunk 逐段 yield 出去
    """
    rid = get_request_id()   
    start = time.time()      

    logger.info(f"chat stream start | rid={rid} | question_len={len(question)}")  # ✅ NEW

    try:
        chunks = rag_retrieve(question)
        messages = build_messages(question, chunks)

        out_chars = 0
        for token in stream_answer(messages):
            out_chars += len(token)
            yield token

        elapsed = time.time() - start 
        logger.info(
            f"chat stream done  | rid={rid} | chunks={len(chunks)} | out_chars={out_chars} | time={elapsed:.3f}s"
        )

    except Exception as e:
        elapsed = time.time() - start 
        logger.error(f"chat stream fail | rid={rid} | time={elapsed:.3f}s | error={e}")
        raise
