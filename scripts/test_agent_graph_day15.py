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
    print("final_answer:", result.get("final_answer"))
    print("debug_info:", result.get("debug_info"))


def main():
    # 真正需要 followup + rewrite
    run_case(
        title="real_followup_case",
        question="那它有什么优点？",
        chat_history=[
            {"role": "user", "content": "什么是深度学习？"},
            {"role": "assistant", "content": "深度学习是机器学习的一个重要分支。"},
        ],
    )

    # 看起来像 followup，但本身其实已经比较完整
    run_case(
        title="self_contained_case_1",
        question="这个项目的缓存机制是什么？",
        chat_history=[
            {"role": "user", "content": "可以介绍一下这个项目吗？"},
            {"role": "assistant", "content": "这是一个 Agentic RAG 项目。"},
        ],
    )

    # 本身已经有明确主题词，不应强行 rewrite
    run_case(
        title="self_contained_case_2",
        question="RAG项目中的缓存机制是什么？",
        chat_history=[
            {"role": "user", "content": "可以介绍一下这个项目吗？"},
            {"role": "assistant", "content": "这是一个 Agentic RAG 项目。"},
        ],
    )

    # 边界问题：短句 + 有上下文
    run_case(
        title="borderline_case",
        question="那缓存呢？",
        chat_history=[
            {"role": "user", "content": "RAG项目中为什么要加缓存？"},
            {"role": "assistant", "content": "缓存可以减少重复检索和重复调用LLM。"},
        ],
    )


if __name__ == "__main__":
    main()