from app.agent.graph import agent_graph
from app.agent.debug import build_agent_debug_summary, summarize_agent_result_for_log


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
            "min_reranked_docs": 1,
        },
    }

    result = agent_graph.invoke(state)

    print("question:", question)
    print("route:", result.get("route"))
    print("final_answer:", result.get("final_answer"))

    debug_summary = build_agent_debug_summary(result)
    print("debug_summary:", debug_summary)

    log_summary = summarize_agent_result_for_log(result)
    print("log_summary:", log_summary)


def main():
    run_case(
        title="normal_kb_case",
        question="什么是深度学习？",
    )

    run_case(
        title="followup_case",
        question="那它有什么优点？",
        chat_history=[
            {"role": "user", "content": "什么是深度学习？"},
            {"role": "assistant", "content": "深度学习是机器学习的一个重要分支。"},
        ],
    )

    run_case(
        title="chat_case",
        question="你好，你是谁？",
    )

    run_case(
        title="fallback_case",
        question="量子纠缠在室温超导中的最新工业应用是什么？",
    )


if __name__ == "__main__":
    main()