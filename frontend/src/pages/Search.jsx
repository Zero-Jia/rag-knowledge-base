import { useMemo, useState } from "react";
import { search } from "../api/search";

const modes = [
  { key: "vector", label: "Vector", detail: "Dense retrieval" },
  { key: "hybrid", label: "Hybrid", detail: "Dense + BM25" },
  { key: "rerank", label: "Rerank", detail: "Hybrid + reranker" },
];

function formatScore(score) {
  if (typeof score !== "number" || Number.isNaN(score)) return "-";
  return score.toFixed(4);
}

function metadataOf(item) {
  return item.metadata || item.metadata_json || item.meta || {};
}

export default function Search() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const selectedMode = useMemo(
    () => modes.find((item) => item.key === mode) || modes[0],
    [mode]
  );

  async function handleSearch(event) {
    event?.preventDefault();
    if (!query.trim() || loading) return;

    setLoading(true);
    setError("");
    setResults([]);

    try {
      const items = await search(query, mode, topK);
      setResults(items);
    } catch (err) {
      setError(err?.message || "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="two-column-grid">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Retrieval query</h2>
            <p className="panel-subtitle">
              Run the same question across the existing backend search modes.
            </p>
          </div>
          <span className="metric-chip">{selectedMode.detail}</span>
        </div>

        <form className="search-form" onSubmit={handleSearch}>
          <textarea
            className="textarea-field"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Enter a question or factual query..."
          />

          <div className="mode-tabs">
            {modes.map((item) => (
              <button
                type="button"
                key={item.key}
                className={`mode-tab ${mode === item.key ? "active" : ""}`}
                onClick={() => setMode(item.key)}
              >
                <strong>{item.label}</strong>
                <small>{item.detail}</small>
              </button>
            ))}
          </div>

          <div className="search-row">
            <label className="topk-field">
              <span>Top K</span>
              <input
                className="field"
                type="number"
                min="1"
                max="20"
                value={topK}
                onChange={(event) => setTopK(event.target.value)}
              />
            </label>
            <button
              type="submit"
              className="primary-button"
              disabled={!query.trim() || loading}
            >
              <span className="button-icon">S</span>
              {loading ? "Searching" : "Search"}
            </button>
          </div>
        </form>

        {error && <div className="alert error">{error}</div>}
      </section>

      <section className="panel results-panel">
        <div className="panel-header compact">
          <div>
            <h2 className="panel-title">Results</h2>
            <p className="panel-subtitle">{results.length} chunks returned</p>
          </div>
        </div>

        <div className="result-list">
          {results.map((item, index) => {
            const metadata = metadataOf(item);
            const id = item.chunk_id || metadata.chunk_id || index;
            return (
              <article key={`${id}-${index}`} className="item-card result-card">
                <div className="result-topline">
                  <span className="metric-chip">#{index + 1}</span>
                  <span className="metric-chip">Score {formatScore(item.score)}</span>
                  {metadata.chunk_level && (
                    <span className="metric-chip">{metadata.chunk_level}</span>
                  )}
                  {metadata.parent_chunk_id && (
                    <span className="metric-chip">parent</span>
                  )}
                </div>
                <p>{item.text || item.content || ""}</p>
                <div className="result-meta mono">
                  {metadata.chunk_id || item.chunk_id || "chunk id unavailable"}
                </div>
              </article>
            );
          })}

          {!loading && results.length === 0 && (
            <div className="empty-state">
              Results will appear here after a retrieval request.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
