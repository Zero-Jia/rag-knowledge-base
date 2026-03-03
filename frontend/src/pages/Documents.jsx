import { useEffect, useState } from "react";
import { listDocuments } from "../api/documents";

function StatusBadge({ status }) {
  const styles = {
    DONE: "bg-green-100 text-green-700",
    PROCESSING: "bg-yellow-100 text-yellow-700",
    FAILED: "bg-red-100 text-red-700",
  };

  return (
    <span className={`px-3 py-1 text-xs rounded-full font-medium ${styles[status] || "bg-gray-100"}`}>
      {status}
    </span>
  );
}

export default function Documents() {
  const [docs, setDocs] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function loadDocs() {
    try {
      setLoading(true);
      setError(null);
      const data = await listDocuments();
      const items = Array.isArray(data) ? data : data.items;
      setDocs(items || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDocs();
    const timer = setInterval(loadDocs, 3000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Documents</h2>
        <button
          onClick={loadDocs}
          className="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-100"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {error && <p className="text-red-600">Error: {error}</p>}

      {docs.length === 0 && (
        <p className="text-gray-500">No documents</p>
      )}

      <div className="space-y-3">
        {docs.map((doc) => (
          <div
            key={doc.id}
            className="border rounded-lg p-4 flex justify-between items-center"
          >
            <div>
              <p className="font-medium">{doc.filename}</p>
              <p className="text-sm text-gray-500">ID: {doc.id}</p>
            </div>
            <StatusBadge status={doc.status} />
          </div>
        ))}
      </div>
    </div>
  );
}