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
            "rerank_score_threshold": 0.1,
        },
    }

    result = agent_graph.invoke(state)

    print("question:", question)
    print("route:", result.get("route"))
    print("rewritten_question:", result.get("rewritten_question"))
    print("cache_hit:", result.get("cache_hit"))
    print("need_fallback:", result.get("need_fallback"))
    print("final_answer:", result.get("final_answer"))
    print("debug_info:", result.get("debug_info"))


def main():
    # 明显 chat
    run_case(
        title="chat_case",
        question="你好，你是谁？",
    )

    # 明显 kb_qa
    run_case(
        title="kb_case",
        question="什么是深度学习？",
    )

    # 明显 followup
    run_case(
        title="followup_case",
        question="那它有什么优点？",
        chat_history=[
            {"role": "user", "content": "什么是深度学习？"},
            {"role": "assistant", "content": "深度学习是机器学习的一个重要分支。"},
        ],
    )

    # 边界问题：不那么像闲聊，也不完全像 followup
    run_case(
        title="borderline_case_1",
        question="可以介绍一下这个项目吗？",
        chat_history=[],
    )

    # 边界问题：有历史，且当前问题较短
    run_case(
        title="borderline_case_2",
        question="那缓存呢？",
        chat_history=[
            {"role": "user", "content": "RAG项目中为什么要加缓存？"},
            {"role": "assistant", "content": "缓存可以减少重复检索和重复调用LLM。"},
        ],
    )


if __name__ == "__main__":
    main()