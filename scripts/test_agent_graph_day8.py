from app.agent.graph import agent_graph


def run_case(title: str, question: str, chat_history=None):
    print(f"\n===== {title} =====")
    state = {
        "question": question,
        "session_id": f"test-{title}",
        "chat_history": chat_history or [],
        "debug_info": {
            "user_id": 1,
            "top_k": 5,
            "rerank_top_n": 3,
        },
    }

    result = agent_graph.invoke(state)

    print("route:", result.get("route"))
    print("rewritten_question:", result.get("rewritten_question"))
    print("cache_hit:", result.get("cache_hit"))
    print("final_answer:", result.get("final_answer"))
    print("debug_info:", result.get("debug_info"))

    retrieved_docs = result.get("retrieved_docs", [])
    reranked_docs = result.get("reranked_docs", [])

    print("retrieved_docs_count:", len(retrieved_docs))
    print("reranked_docs_count:", len(reranked_docs))


def main():
    run_case(
        title="followup_deeplearning",
        question="那它有什么优点？",
        chat_history=[
            {"role": "user", "content": "什么是深度学习？"},
            {"role": "assistant", "content": "深度学习是机器学习的一个重要分支。"},
        ],
    )

    run_case(
        title="followup_cache",
        question="那缓存呢？",
        chat_history=[
            {"role": "user", "content": "RAG项目中为什么要加缓存？"},
            {"role": "assistant", "content": "缓存可以减少重复检索和重复调用LLM。"},
        ],
    )

    run_case(
        title="normal_kb",
        question="什么是深度学习？",
        chat_history=[],
    )


if __name__ == "__main__":
    main()