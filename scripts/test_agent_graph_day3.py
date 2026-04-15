from app.agent.graph import agent_graph


def main():
    state = {
        "question": "什么是深度学习？",
        "session_id": "test-session-003",
        "chat_history": [],
        "debug_info": {
            "user_id": 1,
            "top_k": 5,
        },
    }

    result = agent_graph.invoke(state)

    print("=== Agent Graph Day3 Result ===")
    for k, v in result.items():
        if k == "retrieved_docs" and isinstance(v, list):
            print(f"{k}: 共 {len(v)} 条")
            for i, doc in enumerate(v[:3], 1):
                print(f"  [{i}] source={doc.get('source')} document_id={doc.get('document_id')} score={doc.get('score')}")
                print(f"      text={doc.get('text', '')[:80]}")
        else:
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()