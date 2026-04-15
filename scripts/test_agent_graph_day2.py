from app.agent.graph import agent_graph


def main():
    state = {
        "question": "什么是深度学习？",
        "session_id": "test-session-001",
        "chat_history": [],
        "debug_info": {
            "user_id": 1,
            "top_k": 5,
        },
    }

    result = agent_graph.invoke(state)

    print("=== Agent Graph Result ===")
    for k, v in result.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()