from app.services.retrieval_service import retrieve_chunks
from app.services.prompt_builder import build_messages
from app.services.llm_service import generate_answer,stream_answer

def chat_with_rag(question:str,top_k:int = 5):
    """
    旧版：非流式，一次性返回完整 answer（保留给原 /chat 用）
    """
    chunks = retrieve_chunks(question,top_k=top_k)
    messages = build_messages(question,chunks)
    answer = generate_answer(messages)
    return{
        "question": question,
        "answer": answer,
        "chunks": chunks,   
    }

def stream_chat_with_rag(question:str,top_k:int = 5):
    """
    ✅ 新增：流式版 RAG

    作用：
    1) 先检索（一次性）
    2) 构建 messages（一次性）
    3) 调用 LLM 的 stream_answer，把 token/chunk 逐段 yield 出去
       （后端不拼接全文，router/前端负责拼接展示）
    """
    chunks = retrieve_chunks(question,top_k=top_k)
    messages = build_messages(question,chunks)
    # 关键：stream_answer 本身是 generator，这里直接把内容逐段转发
    for token in stream_answer(messages):
        yield token