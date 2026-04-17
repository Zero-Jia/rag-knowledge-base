from app.agent.graph import agent_graph


def run_case(title: str, question: str, chat_history):
    print(f"\n===== {title} =====")
    state = {
        "question": question,
        "session_id": f"test-{title}",
        "chat_history": chat_history,
        "debug_info": {
            "user_id": 1,
            "top_k": 5,
            "rerank_top_n": 3,
            "rerank_score_threshold": 0.1,
        },
    }

    result = agent_graph.invoke(state)

    print("question:", question)
    print("route:", result.get("route"))
    print("rewritten_question:", result.get("rewritten_question"))
    print("final_answer:", result.get("final_answer"))
    print("debug_info:", result.get("debug_info"))


def main():
    long_history = [
        {"role": "user", "content": "什么是深度学习？"},
        {"role": "assistant", "content": "深度学习是机器学习的一个重要分支。"},
        {"role": "user", "content": "RAG为什么要做chunk切分？"},
        {"role": "assistant", "content": "为了控制上下文长度并减少语义断裂。"},
        {"role": "user", "content": "那缓存有什么作用？"},
        {"role": "assistant", "content": "缓存可以减少重复检索和重复调用LLM。"},
        {"role": "user", "content": "rerank为什么能提升效果？"},
        {"role": "assistant", "content": "因为它能对初步召回结果再做精排。"},
    ]

    run_case(
        title="followup_with_long_history",
        question="那它有什么优点？",
        chat_history=long_history,
    )

    short_history = [
        {"role": "user", "content": "什么是深度学习？"},
        {"role": "assistant", "content": "深度学习是机器学习的一个重要分支。"},
    ]

    run_case(
        title="followup_with_short_history",
        question="那它有什么优点？",
        chat_history=short_history,
    )


if __name__ == "__main__":
    main()