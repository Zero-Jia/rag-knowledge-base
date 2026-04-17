import requests


BASE_URL = "http://127.0.0.1:8000/chat/agent"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZSIsImV4cCI6MTc3NjM5MDA4Mn0.Gy5H07Ge-UgUR5zu8Z5egIMWRZTsWKUnYGacdmebE2A"


def post_agent(payload):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    resp = requests.post(BASE_URL, json=payload, headers=headers, timeout=60)
    print("status_code:", resp.status_code)
    try:
        return resp.json()
    except Exception:
        return resp.text


def main():
    session_id = "demo-session-day12"

    print("\n===== 第一次请求：建立会话 =====")
    payload1 = {
        "question": "什么是深度学习？",
        "session_id": session_id,
        "top_k": 5,
        "rerank_top_n": 3,
        "rerank_score_threshold": 0.1
    }
    result1 = post_agent(payload1)
    print(result1)

    print("\n===== 第二次请求：不传 chat_history，直接追问 =====")
    payload2 = {
        "question": "那它有什么优点？",
        "session_id": session_id,
        "top_k": 5,
        "rerank_top_n": 3,
        "rerank_score_threshold": 0.1
    }
    result2 = post_agent(payload2)
    print(result2)


if __name__ == "__main__":
    main()