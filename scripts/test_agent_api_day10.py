import requests


def main():
    url = "http://127.0.0.1:8000/chat/agent"

    # 这里需要你替换成你自己的 Bearer token
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZSIsImV4cCI6MTc3NjM4ODg2MH0.LGyoq9QSUczio3V98BL_cRCH8tWF9b4fNLyLDre4O2Y"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "question": "什么是深度学习？",
        "top_k": 5,
        "retrieval_mode": "hybrid"
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=60)

    print("status_code:", resp.status_code)
    try:
        print(resp.json())
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    main()