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
        setAnswer((prev) => prev + chunk);
      }
    } catch {
      setAnswer("Error occurred.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Chat</h2>

      <div className="flex gap-3">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask something..."
          className="flex-1 border rounded-lg px-3 py-2"
        />

        <button
          onClick={handleAsk}
          disabled={loading}
          className="px-4 py-2 rounded-lg bg-black text-white disabled:bg-gray-400"
        >
          Ask
        </button>
      </div>

      {loading && (
        <p className="text-sm text-gray-500">Generating...</p>
      )}

      <div className="border rounded-lg p-4 min-h-[150px] whitespace-pre-wrap bg-gray-50">
        {answer}
      </div>
    </div>
  );
}