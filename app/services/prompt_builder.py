# Prompt 组装
# 关键点：不要“随便拼一个大字符串”，而是把 System / Context / User 分开，让模型更稳定、更不乱编
from typing import List,Dict

SYSTEM_PROMPT = (
    "You are a question-answering assistant.\n"
    "Answer strictly based on the provided context.\n"
    "If the context does not contain the answer, say you don't know."
)

def build_messages(question:str,chunks:List[Dict])->List[Dict[str,str]]:
    """
    构建 LLM Prompt
    """
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
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt.strip()},
    ]    