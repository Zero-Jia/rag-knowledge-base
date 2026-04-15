from app.agent.graph import agent_graph


def main():
    state = {
        "question": "什么是深度学习？",
        "session_id": "test-session-005",
        "chat_history": [],
        "debug_info": {
            "user_id": 1,
            "top_k": 5,
            "rerank_top_n": 3,
        },
    }

    result = agent_graph.invoke(state)

    print("=== Agent Graph Day5 Result ===")

    for k, v in result.items():
        if k == "retrieved_docs" and isinstance(v, list):
            print(f"{k}: 共 {len(v)} 条")
            for i, doc in enumerate(v[:2], 1):
                print(
                    f"  [retrieved {i}] source={doc.get('source')} "
                    f"document_id={doc.get('document_id')} "
                    f"score={doc.get('score')}"
                )
                print(f"      text={doc.get('text', '')[:80]}")
        elif k == "reranked_docs" and isinstance(v, list):
            print(f"{k}: 共 {len(v)} 条")
            for i, doc in enumerate(v[:2], 1):
                print(
                    f"  [reranked {i}] source={doc.get('source')} "
                    f"document_id={doc.get('document_id')} "
                    f"rerank_score={doc.get('rerank_score')}"
                )
                print(f"      text={doc.get('text', '')[:80]}")
        elif k == "final_answer":
            print(f"{k}:")
            print(v)
        else:
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()