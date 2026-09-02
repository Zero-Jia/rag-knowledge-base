# Prompt 组装
# 关键点：不要“随便拼一个大字符串”，而是把 System / Context / User 分开，让模型更稳定、更不乱编
import logging

from typing import List,Dict
from app.services.request_context import get_request_id

logger = logging.getLogger("rag.prompt")

SYSTEM_PROMPT = (
    "You are a question-answering assistant.\n"
    "Answer strictly based on the provided context.\n"
    "If the context does not contain the answer, say you don't know.\n"
    "The context passages are numbered as [1], [2], ... .\n"
    "When you use information from a passage, cite it by appending its number in square brackets "
    "(e.g. [1] or [2][3]) right after the supporting sentence. "
    "Never invent citation numbers that do not exist in the context."
)

def build_messages(question:str,chunks:List[Dict])->List[Dict[str,str]]:
    """
    构建 LLM Prompt
    """
    rid = get_request_id()
    logger.info(
        f"Build prompt start | rid={rid} | chunks_used={len(chunks)} | question_len={len(question)}"
    )

    # P0-1：context 按顺序编号为 [1]...[N]，供 LLM 输出 inline citation
    context_parts = []
    for idx, c in enumerate(chunks, start=1):
        context_parts.append(f"[{idx}]\n{c['text']}")
    context = "\n\n".join(context_parts)

    user_prompt = f"""
                Context:
                {context}

                Question:
                {question}

                回答要求（必须严格遵守）：
                1. 仅使用上面 Context 中的信息回答；Context 没有的内容不要编造。
                2. 每使用一条 Context 的信息，必须紧跟在该句后面标注对应的编号标记，如 [1]、[2]，多条可连写如 [1][3]。
                3. 输出格式示例（假设 Context 有 [1][2][3] 三段）：
                   "深度学习是机器学习的重要分支[1]，其核心是通过多层神经网络学习特征表示[2][3]。"
                4. 不要输出其他解释，直接给出答案正文。
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
