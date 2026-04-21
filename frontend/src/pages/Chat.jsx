import { useEffect, useMemo, useRef, useState } from "react";
import {
  getAgentSessionMessages,
  listAgentSessions,
  streamAgentChat,
} from "../api/chat";

const stepLabels = {
  start: "Start",
  classify: "Classify",
  cache: "Cache",
  rewrite: "Rewrite",
  retrieve_initial: "Initial retrieval",
  rerank_initial: "Initial rerank",
  grade_documents: "Grade documents",
  query_expansion: "Query expansion",
  retrieve_expanded: "Expanded retrieval",
  rerank_expanded: "Expanded rerank",
  answer: "Answer",
  fallback: "Fallback",
};

function newSessionId() {
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function parseSse(buffer) {
  const parts = buffer.split(/\n\n/);
  const rest = parts.pop() || "";
  const events = parts
    .map((part) => {
      const lines = part.split(/\n/);
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      try {
        return { event, data: data ? JSON.parse(data) : {} };
      } catch {
        return { event, data: { text: data } };
      }
    })
    .filter(Boolean);
  return { events, rest };
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString();
}

function TracePanel({ trace }) {
  if (!trace) {
    return (
      <div className="trace-empty">
        rag_trace will appear after the agent finishes a turn.
      </div>
    );
  }

  const initialChunks = trace.initial_chunks || [];
  const mergedChunks = trace.merged_chunks || [];
  const timing = trace.timing || {};

  return (
    <div className="trace-panel">
      <div className="trace-grid">
        <div className="trace-metric">
          <span>Mode</span>
          <strong>{trace.retrieval_mode || "agentic_stream"}</strong>
        </div>
        <div className="trace-metric">
          <span>Cache</span>
          <strong>{trace.cache_hit ? "hit" : "miss"}</strong>
        </div>
        <div className="trace-metric">
          <span>Initial</span>
          <strong>{initialChunks.length}</strong>
        </div>
        <div className="trace-metric">
          <span>Merged</span>
          <strong>{mergedChunks.length}</strong>
        </div>
      </div>

      {trace.fallback_reason && (
        <div className="alert error">Fallback: {trace.fallback_reason}</div>
      )}

      <div className="trace-section">
        <h4>Timing</h4>
        <div className="trace-kv">
          {Object.entries(timing).map(([key, value]) => (
            <span key={key}>
              {key}: {Number(value).toFixed ? Number(value).toFixed(1) : value}
              ms
            </span>
          ))}
          {Object.keys(timing).length === 0 && <span>No timing data</span>}
        </div>
      </div>

      <details className="raw-trace">
        <summary>Raw trace JSON</summary>
        <pre>{JSON.stringify(trace, null, 2)}</pre>
      </details>
    </div>
  );
}

export default function Chat() {
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState(newSessionId);
  const [sessions, setSessions] = useState([]);
  const [messages, setMessages] = useState([]);
  const [activeTrace, setActiveTrace] = useState(null);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const messagesEndRef = useRef(null);

  const lastAssistantTrace = useMemo(() => {
    const item = [...messages].reverse().find((msg) => msg.role === "assistant");
    return item?.ragTrace || activeTrace;
  }, [activeTrace, messages]);

  async function refreshSessions() {
    try {
      const items = await listAgentSessions();
      setSessions(items);
    } catch {
      setSessions([]);
    }
  }

  async function loadSession(targetSessionId) {
    if (!targetSessionId || loading) return;
    setHistoryLoading(true);
    setError("");
    try {
      const rows = await getAgentSessionMessages(targetSessionId, true);
      setSessionId(targetSessionId);
      setActiveTrace(null);
      setMessages(
        rows.map((row) => ({
          id: `${row.session_id}-${row.id}`,
          role: row.role === "assistant" ? "assistant" : "user",
          text: row.content,
          ragTrace: row.rag_trace || null,
          steps: [],
          createdAt: row.created_at,
        }))
      );
    } catch (err) {
      setError(err?.message || "Failed to load session");
    } finally {
      setHistoryLoading(false);
    }
  }

  function updateAssistant(id, updater) {
    setMessages((prev) =>
      prev.map((msg) => (msg.id === id ? updater(msg) : msg))
    );
  }

  async function handleAsk(e) {
    e?.preventDefault();
    const q = question.trim();
    if (!q || loading) return;

    const activeSessionId = sessionId || newSessionId();
    const assistantId = `assistant-${Date.now()}`;
    const userMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text: q,
      createdAt: new Date().toISOString(),
    };
    const assistantMessage = {
      id: assistantId,
      role: "assistant",
      text: "",
      steps: [],
      ragTrace: null,
      streaming: true,
      createdAt: new Date().toISOString(),
    };

    setSessionId(activeSessionId);
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setQuestion("");
    setLoading(true);
    setError("");
    setActiveTrace(null);

    try {
      const reader = await streamAgentChat({
        question: q,
        sessionId: activeSessionId,
      });
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let done = false;

      while (!done) {
        const result = await reader.read();
        done = result.done;
        buffer += decoder.decode(result.value || new Uint8Array(), {
          stream: !done,
        });

        const parsed = parseSse(buffer);
        buffer = parsed.rest;

        for (const item of parsed.events) {
          if (item.event === "rag_step") {
            const step = {
              node: item.data.node || "unknown",
              label: stepLabels[item.data.node] || item.data.node || "Step",
              payload: item.data,
            };
            if (item.data.session_id) setSessionId(item.data.session_id);
            updateAssistant(assistantId, (msg) => ({
              ...msg,
              steps: [...(msg.steps || []), step],
            }));
          }

          if (item.event === "content") {
            updateAssistant(assistantId, (msg) => ({
              ...msg,
              text: `${msg.text}${item.data.text || ""}`,
            }));
          }

          if (item.event === "trace") {
            const trace = item.data.rag_trace || item.data;
            setActiveTrace(trace);
            updateAssistant(assistantId, (msg) => ({
              ...msg,
              ragTrace: trace,
            }));
          }

          if (item.event === "error") {
            const message = item.data.details || item.data.message || "Stream failed";
            setError(message);
            updateAssistant(assistantId, (msg) => ({
              ...msg,
              text: msg.text || message,
              error: message,
            }));
          }

          if (item.event === "done") {
            updateAssistant(assistantId, (msg) => ({
              ...msg,
              streaming: false,
            }));
          }
        }
      }

      await refreshSessions();
    } catch (err) {
      setError(err?.message || "Chat failed");
      updateAssistant(assistantId, (msg) => ({
        ...msg,
        streaming: false,
        error: err?.message || "Chat failed",
        text: msg.text || "Chat failed.",
      }));
    } finally {
      setLoading(false);
    }
  }

  function startNewSession() {
    if (loading) return;
    setSessionId(newSessionId());
    setMessages([]);
    setActiveTrace(null);
    setQuestion("");
    setError("");
  }

  useEffect(() => {
    refreshSessions();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-layout">
      <aside className="history-panel panel">
        <div className="panel-header compact">
          <div>
            <h2 className="panel-title">Sessions</h2>
            <p className="panel-subtitle">Persistent agent memory</p>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={refreshSessions}
            title="Refresh sessions"
          >
            R
          </button>
        </div>

        <button
          type="button"
          onClick={startNewSession}
          className="primary-button full-width"
          disabled={loading}
        >
          <span className="button-icon">+</span>
          New session
        </button>

        <div className="session-list">
          {historyLoading && <div className="muted-text small-text">Loading...</div>}
          {sessions.map((item) => (
            <button
              type="button"
              key={item.session_id}
              className={`session-item ${
                item.session_id === sessionId ? "active" : ""
              }`}
              onClick={() => loadSession(item.session_id)}
              title={item.session_id}
            >
              <span>{item.title || "Untitled session"}</span>
              <small>{formatTime(item.updated_at)}</small>
            </button>
          ))}
          {!historyLoading && sessions.length === 0 && (
            <div className="empty-state slim">No saved sessions yet.</div>
          )}
        </div>
      </aside>

      <section className="chat-panel panel">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="empty-state">
              Ask a question to see Agentic RAG steps, answer streaming, and
              trace details in one place.
            </div>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={`message-row ${
                message.role === "user" ? "from-user" : "from-assistant"
              }`}
            >
              <div className="message-bubble">
                <div className="message-meta">
                  <span>{message.role === "user" ? "You" : "Agent"}</span>
                  {message.streaming && <span>Streaming</span>}
                </div>
                <div className="message-text">{message.text}</div>
                {message.error && (
                  <div className="alert error message-alert">{message.error}</div>
                )}
                {message.steps?.length > 0 && (
                  <div className="rag-step-list">
                    {message.steps.map((step, index) => (
                      <span key={`${step.node}-${index}`} className="rag-step-pill">
                        {step.label}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {error && <div className="alert error">{error}</div>}

        <form className="chat-composer" onSubmit={handleAsk}>
          <textarea
            className="textarea-field"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask about your indexed documents..."
            disabled={loading}
          />
          <div className="composer-actions">
            <div className="small-text muted-text mono">{sessionId}</div>
            <button
              type="submit"
              className="primary-button"
              disabled={!question.trim() || loading}
            >
              <span className="button-icon">S</span>
              {loading ? "Running" : "Send"}
            </button>
          </div>
        </form>
      </section>

      <aside className="trace-sidebar panel">
        <div className="panel-header compact">
          <div>
            <h2 className="panel-title">rag_trace</h2>
            <p className="panel-subtitle">Retrieval and answer telemetry</p>
          </div>
        </div>
        <TracePanel trace={lastAssistantTrace} />
      </aside>
    </div>
  );
}
