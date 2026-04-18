from app.agent.graph import agent_graph


def run_case(
    title: str,
    question: str,
    chat_history=None,
    rerank_score_threshold=0.1,
    min_reranked_docs=1,
):
    print(f"\n===== {title} =====")
    state = {
        "question": question,
        "session_id": f"test-{title}",
        "chat_history": chat_history or [],
        "debug_info": {
            "user_id": 1,
            "top_k": 5,
            "rerank_top_n": 3,
            "rerank_score_threshold": rerank_score_threshold,
            "min_reranked_docs": min_reranked_docs,
        },
    }

    result = agent_graph.invoke(state)

    print("question:", question)
    print("route:", result.get("route"))
    print("need_fallback:", result.get("need_fallback"))
    print("fallback_reason:", result.get("fallback_reason"))
    print("final_answer:", result.get("final_answer"))
    print("debug_info:", result.get("debug_info"))

    retrieved_docs = result.get("retrieved_docs", [])
    reranked_docs = result.get("reranked_docs", [])

    print("retrieved_docs_count:", len(retrieved_docs))
    print("reranked_docs_count:", len(reranked_docs))


def main():
    # 1. 正常知识库问题：换一种以前没直接问过的说法
    run_case(
        title="normal_kb_case",
        question="请说明深度学习的基本定义，并概括它和传统机器学习相比的核心特点。",
    )

    # 2. 明显超出当前知识库范围的问题
    run_case(
        title="out_of_scope_case",
        question="请分析月壤基地能源系统在木星轨道环境下的工业部署方案。",
    )

    # 3. 强制低分 fallback：问题本身仍是知识库内的，但阈值拉高
    run_case(
        title="force_low_score_fallback",
        question="请从模型表示学习角度解释深度学习的概念。",
        rerank_score_threshold=100.0,
    )

    # 4. 强制支持文档数量检查：要求至少 2 条支持证据
    run_case(
        title="force_supporting_docs_check",
        question="请介绍深度学习，并说明它为什么属于机器学习的重要分支。",
        rerank_score_threshold=0.1,
        min_reranked_docs=2,
    )

    # 5. chat 场景：换一个从未使用过的闲聊表达
    run_case(
        title="chat_case",
        question="嗨，你可以先做个自我介绍吗？",
    )


if __name__ == "__main__":
    main()