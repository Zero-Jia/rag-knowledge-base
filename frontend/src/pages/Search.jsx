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
      const items = await search(query, mode, topK);
      setResults(items);
    } catch (err) {
      setErrorMsg(err.message || "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Search</h2>

      <div className="flex gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter your question..."
          className="flex-1 border rounded-lg px-3 py-2"
        />

        <select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="border rounded-lg px-3 py-2"
        >
          <option value="semantic">Semantic</option>
          <option value="hybrid">Hybrid</option>
          <option value="rerank">Rerank</option>
        </select>

        <button
          onClick={handleSearch}
          className="px-4 py-2 rounded-lg bg-black text-white"
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </div>

      {errorMsg && <p className="text-red-600">{errorMsg}</p>}

      <div className="space-y-4">
        {results.map((item, idx) => (
          <div key={idx} className="border rounded-lg p-4">
            <p className="text-sm text-gray-500">
              Score: {typeof item.score === "number"
                ? item.score.toFixed(4)
                : item.score}
            </p>
            <p className="mt-2">{item.text?.slice(0, 300)}...</p>
          </div>
        ))}
      </div>
    </div>
  );
}