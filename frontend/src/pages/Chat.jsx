import { useState } from "react";
import { streamChat } from "../api/chat";

export default function Chat() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleAsk() {
    if (!question.trim()) return;

    setAnswer("");
    setLoading(true);

    try {
      const reader = await streamChat(question);
      const decoder = new TextDecoder("utf-8");

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });

        // 🔥 今天最重要的一行
        setAnswer(prev => prev + chunk);
      }

    } catch (err) {
      setAnswer("Error occurred.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2>Chat</h2>

      <input
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask something..."
      />

      <button onClick={handleAsk} disabled={loading}>
        Ask
      </button>

      {loading && <p>Thinking...</p>}

      <div style={{ marginTop: 20, whiteSpace: "pre-wrap" }}>
        {answer}
      </div>
    </div>
  );
}