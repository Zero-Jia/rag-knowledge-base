from app.services.rag_retrieval import rag_retrieve
from app.services.prompt_builder import build_messages
from app.services.llm_service import generate_answer,stream_answer

def chat_with_rag(question:str):
    """
    Day16：统一版（非流式）
    chat_service 不关心检索细节（vector/hybrid/rerank）
    """
    chunks = rag_retrieve(question)
    messages = build_messages(question,chunks)
    answer = generate_answer(messages)
    return{
        "question": question,
        "answer": answer,
        "chunks": chunks,   
    }

def stream_chat_with_rag(question:str):
    """
    ✅ 新增：流式版 RAG

    作用：
    1) 先检索（一次性）
    2) 构建 messages（一次性）
    3) 调用 LLM 的 stream_answer，把 token/chunk 逐段 yield 出去
       （后端不拼接全文，router/前端负责拼接展示）
    """
    chunks = rag_retrieve(question)
    messages = build_messages(question,chunks)
    # 关键：stream_answer 本身是 generator，这里直接把内容逐段转发
    for token in stream_answer(messages):
        yield token