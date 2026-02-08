# Prompt 组装
# 关键点：不要“随便拼一个大字符串”，而是把 System / Context / User 分开，让模型更稳定、更不乱编
import logging

from typing import List,Dict
from app.services.request_context import get_request_id

logger = logging.getLogger("rag.prompt")

SYSTEM_PROMPT = (
    "You are a question-answering assistant.\n"
    "Answer strictly based on the provided context.\n"
    "If the context does not contain the answer, say you don't know."
)

def build_messages(question:str,chunks:List[Dict])->List[Dict[str,str]]:
    """
    构建 LLM Prompt
    """
    rid = get_request_id()
    logger.info(
        f"Build prompt start | rid={rid} | chunks_used={len(chunks)} | question_len={len(question)}"
    )

    context = "\n\n".join(
        f"[Document {c['document_id']}]\n{c['text']}"
        for c in chunks
    )

    user_prompt = f"""
                Context:
                {context}

                Question:
                {question}

                Answer using only the information in the context.
                """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt.strip()},
    ]
    # 记录 prompt 规模（不打印全文，避免日志爆炸/泄露）
    context_chars = len(context)
    user_chars = len(messages[1]["content"])
    logger.info(
        f"Build prompt done  | rid={rid} | context_chars={context_chars} | user_prompt_chars={user_chars}"
    )

    return messages
