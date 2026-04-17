import requests


def main():
    url = "http://127.0.0.1:8000/chat/agent"

    # 替换成你自己的 token
    token = "YOUR_ACCESS_TOKEN"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "question": "那它有什么优点？",
        "session_id": "demo-session-001",
        "chat_history": [
            {
                "role": "user",
                "content": "什么是深度学习？"
            },
            {
                "role": "assistant",
                "content": "深度学习是机器学习的一个重要分支。"
            }
        ],
        "top_k": 5,
        "rerank_top_n": 3,
        "rerank_score_threshold": 0.1
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=60)

    print("status_code:", resp.status_code)
    try:
        data = resp.json()
        print(data)
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    main()