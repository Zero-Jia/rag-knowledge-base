import { useState } from "react";
import { search } from "../api/search";

export default function Search() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("semantic");
  const [topK, setTopK] = useState(5);

  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  async function handleSearch() {
    if (!query.trim()) return;

    setLoading(true);
    setErrorMsg("");
    setResults([]);

    try {
      // 👇 就是你问的这两行
      const items = await search(query, mode, topK);
      setResults(items);
    } catch (err) {
      setErrorMsg(err.message || "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>Search</h2>

      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter your question..."
          style={{ flex: 1, padding: 8 }}
        />

        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="semantic">Semantic</option>
          <option value="hybrid">Hybrid</option>
          <option value="rerank">Rerank</option>
        </select>

        <button onClick={handleSearch}>
          {loading ? "Searching..." : "Search"}
        </button>
      </div>

      {loading && <p>Loading...</p>}
      {errorMsg && <p style={{ color: "red" }}>{errorMsg}</p>}

      <ul style={{ marginTop: 20 }}>
        {results.map((item, idx) => (
          <li key={idx} style={{ marginBottom: 16 }}>
            <p>
              <b>Score:</b>{" "}
              {typeof item.score === "number"
                ? item.score.toFixed(4)
                : item.score}
            </p>
            <p>{item.text?.slice(0, 300)}...</p>
            <hr />
          </li>
        ))}
      </ul>
    </div>
  );
}