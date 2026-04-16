from app.agent.graph import agent_graph


def run_case(
    title: str,
    question: str,
    chat_history=None,
    top1_rerank_threshold=6.5,
    multi_doc_rerank_threshold=6.0,
    min_support_docs=2,
):
    print(f"\n===== {title} =====")

    state = {
        "question": question,
        "session_id": f"test-{title}",
        "chat_history": chat_history or [],
        "debug_info": {
            "user_id": 999999,
            "top_k": 5,
            "rerank_top_n": 3,
            "top1_rerank_threshold": top1_rerank_threshold,
            "multi_doc_rerank_threshold": multi_doc_rerank_threshold,
            "min_support_docs": min_support_docs,
        },
    }

    result = agent_graph.invoke(state)

    print("route:", result.get("route"))
    print("cache_hit:", result.get("cache_hit"))
    print("need_fallback:", result.get("need_fallback"))
    print("fallback_reason:", result.get("fallback_reason"))
    print("final_answer:", result.get("final_answer"))

    debug = result.get("debug_info", {})
    print("debug_info:", debug)

    docs = result.get("reranked_docs", [])

    if docs:
        print("\nTop reranked docs:")
        for i, d in enumerate(docs, 1):
            print(f"[{i}] score={d.get('rerank_score')} text={(d.get('text') or '')[:60]}")


def main():
    run_case(
        "normal_case",
        "请解释深度学习的基本概念 test1",
    )

    run_case(
        "unknown_case",
        "量子纠缠在室温超导中的工业应用 test2",
    )

    run_case(
        "force_fallback",
        "请解释深度学习 test3",
        top1_rerank_threshold=100,
        multi_doc_rerank_threshold=100,
    )


if __name__ == "__main__":
    main()