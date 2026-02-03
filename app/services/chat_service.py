from app.services.retrieval_service import retrieve_chunks
from app.services.prompt_builder import build_messages
from app.services.llm_service import generate_answer

def chat_with_rag(question:str,top_k:int = 5):
    chunks = retrieve_chunks(question,top_k=top_k)
    messages = build_messages(question,chunks)
    answer = generate_answer(messages)
    return{
        "question": question,
        "answer": answer,
        "chunks": chunks,   
    }